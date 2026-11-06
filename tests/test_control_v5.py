"""v5 control plane: VM time measured from the claim, the deletion receipt and vm-check, recruiter/user steps,
and the web app's abuse limits. No VM, no real LLM, no Vultr calls.

  python -m pytest tests/test_control_v5.py
"""
import datetime
import importlib
import sys
import threading
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burner.control import brain, pool, scan, vultr  # noqa: E402


def _mock_client(monkeypatch):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("BURNER_MOCK", "1")
    import burner.web.app as web
    web = importlib.reload(web)
    monkeypatch.setattr(web.time, "sleep", lambda s: None)
    return web, TestClient(web.app)


# ---- VM time + cost ---------------------------------------------------------------------------------------------

def test_pool_vm_cost_is_measured_from_the_claim_not_its_boot(monkeypatch):
    """A pool VM armed 35 h ago and used for 2 minutes costs 2 minutes; the 35 h are reported as standby."""
    boot = datetime.datetime(2026, 11, 5, 0, 0, tzinfo=datetime.timezone.utc)
    claimed_at = boot.timestamp() + 35 * 3600
    vm = dict(id="fb07aaaa-0000-4000-8000-000000000000", plan="vc2-2c-4gb", region="blr", from_pool=True)
    hourly = 0.0274
    idle = scan.pool_idle_secs({"date_created": boot.isoformat()}, claimed_at)
    vm.update(pool_idle_secs=round(idle), pool_idle_cost_usd=round(hourly * idle / 3600, 4),
              **scan.vm_cost(claimed_at, claimed_at + 120, hourly))
    assert vm["lifetime_secs"] == 120
    assert vm["cost_usd_prorated"] == round(hourly * 120 / 3600, 4)
    assert vm["cost_usd_max"] == hourly                       # one billed hour, not 36
    assert vm["pool_idle_secs"] == 35 * 3600 and vm["pool_idle_cost_usd"] == round(hourly * 35, 4)
    items = scan.vultr_bill({"vm": vm}, price=lambda m: (None, None))["items"]
    compute = [i for i in items if i["service"] == "Cloud Compute"]
    assert compute[0]["usd"] == vm["cost_usd_prorated"] and "120 s" in compute[0]["detail"]
    assert compute[1]["standby"] and compute[1]["usd"] is None and "35.0 h" in compute[1]["detail"]
    total = scan.vultr_bill({"vm": vm}, price=lambda m: (None, None))["total_usd"]
    assert total == vm["cost_usd_prorated"]                   # standby is a note, not in this scan's total


def test_claim_records_its_time(monkeypatch):
    calls = []
    monkeypatch.setattr(vultr, "list_instances", lambda tag: [{"id": "x1", "tags": ["burner-pool", "armed"],
                                                                "firewall_group_id": "fw"}])
    monkeypatch.setattr(vultr, "ensure_firewall_group", lambda: "fw")
    monkeypatch.setattr(vultr, "_call", lambda *a: calls.append(a) or {})
    i = pool.claim()
    assert i["claimed_at"] and f"claimed-{int(i['claimed_at'])}" in calls[-1][2]["tags"]


def test_deletion_receipt_polls_until_404(monkeypatch):
    answers = iter([200, 200, 404])

    def call(method, path, body=None):
        code = next(answers)
        if code == 404:
            raise RuntimeError(f"Vultr {method} {path} -> 404: not found")
        return {"instance": {"id": "x"}}
    monkeypatch.setattr(vultr, "_call", call)
    monkeypatch.setattr(vultr.time, "sleep", lambda s: None)
    r = vultr.confirm_deleted("x", 1_700_000_000, timeout=30, interval=0)
    assert r["http_status"] == 404 and r["confirmed_at"] and r["requested_at"].startswith("2023-11-14")
    assert r["check"] == "GET /v2/instances/{id}"


def test_vm_check_in_mock_mode(monkeypatch):
    web, c = _mock_client(monkeypatch)
    jid = c.post("/api/scan", json={"sample": "npm-start-stealer"}).json()["id"]
    c.get(f"/api/scan/{jid}/events")
    rep = c.get(f"/api/scan/{jid}").json()["report"]
    assert rep["vm"]["deletion"]["http_status"] == 404 and "pool_idle_secs" in rep["vm"]
    r = c.get(f"/api/scan/{jid}/vm-check").json()
    assert r["gone"] and r["http_status"] == 404 and r["instance_id"] == rep["vm"]["id"][:8]
    assert r["region"] == "blr" and r["checked_at"]
    assert c.get(f"/api/scan/{jid}/vm-check").json() == r      # cached
    assert c.get("/api/scan/0000000000/vm-check").status_code == 404
    jid = c.post("/api/scan", json={"sample": "vscode-task"}).json()["id"]   # benchmark host: no per-scan VM
    c.get(f"/api/scan/{jid}/events")
    assert c.get(f"/api/scan/{jid}/vm-check").status_code == 404


def test_mock_pool_shows_standby(monkeypatch):
    monkeypatch.setenv("BURNER_MOCK_POOL", "1")
    web, c = _mock_client(monkeypatch)
    jid = c.post("/api/scan", json={"sample": "npm-start-stealer"}).json()["id"]
    c.get(f"/api/scan/{jid}/events")
    rep = c.get(f"/api/scan/{jid}").json()["report"]
    assert rep["vm"]["from_pool"] and rep["vm"]["pool_idle_secs"] > 0
    assert any(i.get("standby") for i in rep["vultr_bill"]["items"])


# ---- recruiter / user steps -------------------------------------------------------------------------------------

def test_recruiter_commands_are_extracted_and_deduped():
    msg = ("Please clone it, `cd app && npm install && node server.js`, then make sure it starts with `npm start`.\n"
           "$ npm run dev\n`npm start` again!")
    assert brain.recruiter_commands(msg) == ["node server.js", "npm start"]          # max 2, no install/cd
    assert brain.recruiter_commands("run `pytest`, not py") == []                    # not a run command we know
    plan = [{"name": "npm run start", "cmd": "npm run start", "timeout": 45},
            {"name": "npm run start (+45 days)", "cmd": "faketime -f +45d npm run start", "kill_before": True}]
    out = scan.order_plan(plan, [], ["npm start", "node server.js"], "node seed.js", reorder=False)
    assert [s["cmd"] for s in out] == ["npm run start", "node server.js", "node seed.js",
                                       "faketime -f +45d npm run start"]
    assert [s["source"] for s in out] == ["default", "recruiter", "user", "default"]
    assert out[1]["why"] == "the recruiter told you to run this" and out[2]["why"] == "you said you were told to run this"


def test_run_field_is_validated_and_becomes_a_user_step(monkeypatch):
    web, c = _mock_client(monkeypatch)
    assert c.post("/api/scan", json={"sample": "npm-start-stealer", "run": "x" * 201}).status_code == 400
    assert c.post("/api/scan", json={"sample": "npm-start-stealer", "run": "node a.js\nrm -rf /"}).status_code == 400
    assert c.post("/api/scan", json={"sample": "npm-start-stealer", "run": "node a.js\0"}).status_code == 400
    jid = c.post("/api/scan", json={"sample": "npm-start-stealer", "run": "node seed.js"}).json()["id"]
    c.get(f"/api/scan/{jid}/events")
    steps = c.get(f"/api/scan/{jid}").json()["report"]["steps"]
    user = [s for s in steps if s["source"] == "user"]
    assert user and user[0]["cmd"] == "node seed.js" and "(+" in steps[-1]["name"]
    with pytest.raises(scan.ScanError):
        scan.run("https://github.com/a/b", run_cmd="a\nb")


# ---- hardening --------------------------------------------------------------------------------------------------

def test_queue_is_capped(monkeypatch):
    web, c = _mock_client(monkeypatch)
    web.slots = threading.Semaphore(0)                      # every VM busy: everything queues
    ids = [c.post("/api/scan", json={"sample": "npm-start-stealer"}) for _ in range(web.MAX_QUEUE)]
    assert all(r.status_code == 200 for r in ids)
    r = c.post("/api/scan", json={"sample": "npm-start-stealer"})
    assert r.status_code == 429 and "busy" in r.json()["error"]
    for x in ids:
        c.delete(f"/api/scan/{x.json()['id']}")


def test_daily_cap_per_ip_and_last_forwarded_for(monkeypatch):
    web, c = _mock_client(monkeypatch)
    monkeypatch.setattr(web, "PER_IP_HOUR", 100)
    web._hits.clear()
    for _ in range(web.PER_IP_DAY):
        web._rate_limit("198.51.100.7")
    with pytest.raises(web.HTTPException) as e:
        web._rate_limit("198.51.100.7")
    assert e.value.status_code == 429 and "per day" in e.value.detail
    web._rate_limit("198.51.100.8")                          # another visitor is fine

    class R:
        headers = {"x-forwarded-for": "1.2.3.4, 203.0.113.9"}
        client = None
    assert web._client_ip(R) == "203.0.113.9"                 # Caddy's entry, not the spoofable first one


def test_public_json_has_no_presigned_url_and_jobs_are_pruned(monkeypatch):
    web, c = _mock_client(monkeypatch)
    rep = {"verdict": "CLEAN", "evidence": {"key": "scans/x.tar.gz", "url": "https://signed?X-Amz-Signature=1"}}
    assert "url" not in web._public(rep)["evidence"] and rep["evidence"]["url"]   # original untouched
    jid = "abcdef0123"
    web.jobs[jid] = {"id": jid, "req": web.ScanRequest(sample="npm-start-stealer"), "events": [], "status": "done",
                     "created": 0, "q": None, "report": rep}
    assert "url" not in c.get(f"/api/scan/{jid}").json()["report"]["evidence"]
    from burner.control import evidence
    monkeypatch.setattr(evidence, "presign", lambda key, secs: f"https://fresh.example/{key}")
    r = c.get(f"/e/{jid}", follow_redirects=False)                # the download link still works
    assert r.status_code in (302, 307) and r.headers["location"] == "https://fresh.example/scans/x.tar.gz"
    for i in range(web.KEEP_JOBS + 5):
        k = f"p{i:09d}"
        web.jobs[k] = {"id": k, "req": None, "events": [], "status": "done", "created": i + 1, "q": None, "report": {}}
    web._prune()
    assert sum(j["status"] == "done" for j in web.jobs.values()) == web.KEEP_JOBS and jid not in web.jobs
