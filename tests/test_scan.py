"""Control-plane failure modes that must never become a wrong verdict or a dead demo. No VM, no real LLM.

  python -m pytest tests/test_scan.py
"""
import importlib
import os
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burner.control import brain, scan, vultr  # noqa: E402


@pytest.fixture
def no_vm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a VM must not be rented for this scan")
    monkeypatch.setattr(vultr, "create_instance", boom)
    monkeypatch.setattr(scan.pool, "claim", boom)


@pytest.fixture
def ai_down(monkeypatch):
    def down(*a, **k):
        raise RuntimeError("HTTP Error 404: model not found")
    monkeypatch.setattr(brain, "chat", down)


def repo_with(files):
    d = Path(tempfile.mkdtemp(prefix="burner-test-"))
    for name, text in files.items():
        (d / name).write_text(text)
    return d


def test_nothing_runnable_is_inconclusive_and_rents_no_vm(no_vm):
    rep = scan.run(str(repo_with({"README.md": "# a Go take-home\n", "main.go": "package main\n"})),
                   use_llm=False, emit=lambda *a: None)
    assert rep["verdict"] == "INCONCLUSIVE" and rep["vm"] is None
    assert "safe" in rep["headline"]


def test_ai_down_carries_on_with_rules(no_vm, ai_down):
    events = []
    msg = "Hi! Urgent take-home, run it today: https://github.com/example/takehome"
    rep = scan.run(str(repo_with({"README.md": "# hi\n"})), message=msg, emit=lambda s, t: events.append(t))
    assert rep["recruiter"]["repo_urls"] == ["https://github.com/example/takehome"]   # regex still finds the link
    assert {e["step"] for e in rep["llm_errors"]} == {"reading the message", "screening the README",
                                                      "planning extra steps"}
    assert any("AI unavailable" in t for t in events)


def test_planner_falls_back_to_next_model(monkeypatch):
    tried = []

    def chat(model, messages, **kw):
        tried.append(model)
        if model == brain.PLANNER:
            raise RuntimeError("HTTP Error 404: model retired")
        return "ok"
    monkeypatch.setattr(brain, "chat", chat)
    assert brain.plan_chat([], "plan") == "ok" and tried[:2] == [brain.PLANNER, brain.PLANNER_FALLBACKS[0]]


def test_usage_is_per_scan():
    brain.reset_usage()["calls"] = 5
    assert brain.reset_usage()["calls"] == 0


def test_missing_repo_link_is_plain_english():
    with pytest.raises(scan.ScanError, match="No repo link"):
        scan.run(None, message="hello, no link here", use_llm=False, emit=lambda *a: None)


def test_private_or_missing_repo_is_plain_english(tmp_path):
    try:
        scan.clone("https://github.com/burner-test-does-not-exist-7f3a/nope", tmp_path / "r")
    except scan.ScanError as e:
        assert "private" in str(e) or "download" in str(e)
        return
    pytest.fail("cloning a missing repo should raise ScanError")


def _fake_vms(monkeypatch, vms):
    deleted = []
    monkeypatch.setattr(vultr, "list_instances", lambda tag="burner": [v for v in vms if tag in v["tags"]])
    monkeypatch.setattr(vultr, "delete_instance", lambda iid: deleted.append(iid))
    return deleted


def test_reaper_ages_pool_vms_from_their_claim_not_their_boot(monkeypatch):
    import datetime
    import time as _t
    old = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=5)).isoformat()
    deleted = _fake_vms(monkeypatch, [
        {"id": "claimed-just-now", "date_created": old, "tags": ["burner-scan", f"claimed-{int(_t.time()) - 60}"]},
        {"id": "claimed-long-ago", "date_created": old, "tags": ["burner-scan", f"claimed-{int(_t.time()) - 3600}"]},
        {"id": "fresh-scan-vm-old", "date_created": old, "tags": ["burner-scan"]}])
    vultr.reap(max_age_min=20)
    assert deleted == ["claimed-long-ago", "fresh-scan-vm-old"]


def test_deleting_a_vm_that_is_already_gone_is_not_an_error(monkeypatch):
    def gone(method, path, body=None):
        raise RuntimeError(f'Vultr {method} {path} -> 404: {{"error":"Instance not found","status":404}}')
    monkeypatch.setattr(vultr, "_call", gone)
    assert vultr.delete_instance("b40fff8e") is False


def test_stuck_arming_pool_vms_are_reaped(monkeypatch):
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)
    deleted = _fake_vms(monkeypatch, [
        {"id": "stuck", "date_created": (now - datetime.timedelta(minutes=40)).isoformat(), "tags": ["burner-pool", "arming"]},
        {"id": "arming-now", "date_created": (now - datetime.timedelta(minutes=3)).isoformat(), "tags": ["burner-pool", "arming"]},
        {"id": "armed-old", "date_created": (now - datetime.timedelta(hours=9)).isoformat(), "tags": ["burner-pool", "armed"]}])
    vultr.reap_stuck_pool()
    assert deleted == ["stuck"]


def _mock_client(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("BURNER_MOCK", "1")
    import burner.web.app as web
    web = importlib.reload(web)
    monkeypatch.setattr(web.time, "sleep", lambda s: None)
    return web, TestClient(web.app)


def test_queue_shows_position_and_can_be_left(monkeypatch):
    import threading
    import time as _t
    web, c = _mock_client(monkeypatch)
    web.slots = threading.Semaphore(0)                      # every VM busy
    jid = c.post("/api/scan", json={"sample": "npm-start-stealer"}).json()["id"]
    tick, deadline = threading.Event(), _t.monotonic() + 10   # time.sleep is patched out by _mock_client
    while _t.monotonic() < deadline and not any("in line" in e["text"] for e in web.jobs[jid]["events"]):
        tick.wait(0.1)
    assert any("in line" in e["text"] for e in web.jobs[jid]["events"])
    assert c.delete(f"/api/scan/{jid}").json()["cancelled"]
    assert "Cancelled" in c.get(f"/api/scan/{jid}/events").text


def test_replay_needs_a_recorded_scan_and_is_labelled(monkeypatch, tmp_path):
    web, c = _mock_client(monkeypatch)
    monkeypatch.setattr(web, "RECORDED_DIR", tmp_path)
    assert c.post("/api/scan", json={"sample": "npm-start-stealer", "replay": True}).status_code == 400
    (tmp_path / "npm-start-stealer.json").write_text((Path(web.MOCK_DIR) / "mock_report.json").read_text(encoding="utf-8"),
                                                     encoding="utf-8")
    jid = c.post("/api/scan", json={"sample": "npm-start-stealer", "replay": True}).json()["id"]
    c.get(f"/api/scan/{jid}/events")
    rep = c.get(f"/api/scan/{jid}").json()["report"]
    assert rep["replay"]["recorded"] and "No new VM" in rep["replay"]["note"]


def test_web_app_end_to_end_in_mock_mode(monkeypatch):
    """The judging-week fallback: BURNER_MOCK=1 must serve a full scan, report and benchmark."""
    from fastapi.testclient import TestClient
    monkeypatch.setenv("BURNER_MOCK", "1")
    import burner.web.app as web
    web = importlib.reload(web)
    monkeypatch.setattr(web.time, "sleep", lambda s: None)
    c = TestClient(web.app)
    assert c.get("/").status_code == 200 and c.get("/healthz").json()["ok"]
    for body in ({"sample": "npm-start-stealer"}, {"sample": "clean-takehome"},
                 {"repo": "https://github.com/example/takehome"}):
        jid = c.post("/api/scan", json=body).json()["id"]
        stream = c.get(f"/api/scan/{jid}/events").text
        assert "event: end" in stream
        res = c.get(f"/api/scan/{jid}").json()
        assert res["status"] == "done" and res["report"]["verdict"]
    assert c.post("/api/scan", json={"repo": "https://evil.example/x"}).status_code == 400
    assert c.get("/api/benchmark").json()["summary"]
    monkeypatch.delenv("BURNER_MOCK")
    importlib.reload(web)


def _plan_names(files):
    from burner.node import run_scan as rs
    with tempfile.TemporaryDirectory() as d:
        for rel, body in files.items():
            Path(d, rel).parent.mkdir(parents=True, exist_ok=True)
            Path(d, rel).write_text(body)
        return [s["name"] for s in rs.default_plan(d)]


def test_plan_runs_a_lone_poc_script_and_python_mcp_servers():
    # a proof-of-concept repo is often one script and a README, with no requirements file
    assert _plan_names({"exploit.py": "print(1)", "README.md": "# CVE-2026-0001 PoC"}) == ["python exploit.py"]
    # a Python MCP server packaged with pyproject.toml
    assert _plan_names({"server.py": "print(1)", "pyproject.toml": "[project]\nname='x'"}) == ["python server.py"]
    # the take-home order is unchanged: main.py wins over server.py
    assert _plan_names({"main.py": "", "server.py": "", "requirements.txt": ""}) == ["python main.py"]
    # a Node project with a stray helper script is still a Node project
    assert "python run.py" not in _plan_names({"package.json": '{"scripts":{"start":"node a.js"}}', "run.py": ""})
