"""Repo links people actually paste, the recruiter's branch, and the pinned commit a verdict is about.

  python -m pytest tests/test_links_and_pin.py
"""
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burner.control import brain, campaign, scan  # noqa: E402

SHA_OLD = "0123456789abcdef0123456789abcdef01234567"
SHA_NEW = "89abcdef0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize("pasted,want", [
    ("https://github.com/a/b", "https://github.com/a/b"),
    ("https://github.com/a/b/", "https://github.com/a/b"),
    ("github.com/a/b", "https://github.com/a/b"),
    ("https://www.github.com/a/b.git", "https://github.com/a/b"),
    ("https://github.com/a/b?tab=readme-ov-file", "https://github.com/a/b"),
    ("https://github.com/a/b/blob/main/README.md", "https://github.com/a/b"),
    ("https://github.com/a/b/tree/interview-task", "https://github.com/a/b/tree/interview-task"),
    ("https://github.com/a/b/tree/feature/x", "https://github.com/a/b/tree/feature/x"),
    ("https://gitlab.com/a/b/-/tree/assessment", "https://gitlab.com/a/b/tree/assessment"),
    ("https://bitbucket.org/a/b/src/task/", "https://bitbucket.org/a/b/tree/task"),
])
def test_repo_links_people_paste_are_accepted(pasted, want):
    assert brain.repo_link(pasted) == want


@pytest.mark.parametrize("bad", ["https://evil.com/github.com/a/b", "notgithub.com/a/b", "https://github.com/settings/tokens",
                                 "https://github.com/a", "hello"])
def test_non_repo_links_are_refused(bad):
    assert brain.repo_link(bad) is None


@pytest.mark.parametrize("branch", ["--upload-pack=touch /tmp/x", "--upload-pack=x", "..%2f..", "-x"])
def test_hostile_branch_names_are_dropped_not_passed_to_git(branch):
    # either the branch is dropped (default branch) or the whole thing isn't a link: never handed to git
    assert brain.repo_link(f"https://github.com/a/b/tree/{branch}") in ("https://github.com/a/b", None)


def test_branch_link_in_a_message_keeps_the_branch():
    msg = "Hi! Please clone https://github.com/acme/take-home/tree/interview-task, then run it before our call."
    assert brain.find_repos(msg) == ["https://github.com/acme/take-home/tree/interview-task"]
    assert brain.split_branch(brain.find_repos(msg)[0]) == ("https://github.com/acme/take-home", "interview-task")


def _fake_git(monkeypatch, heads, record):
    real = subprocess.run

    def run(cmd, *a, **k):
        if cmd[:1] == ["git"] and "ls-remote" in cmd:
            out = "".join(f"{SHA_NEW}\trefs/heads/{h}\n" for h in heads)
            return subprocess.CompletedProcess(cmd, 0, out, "")
        if cmd[:2] == ["git", "clone"]:
            record.append(cmd)
            dest = Path(cmd[-1])
            dest.mkdir(parents=True)
            real(["git", "init", "-q", str(dest)], check=True)
            (dest / "README.md").write_text("hi")
            real(["git", "-C", str(dest), "-c", "user.email=t@t", "-c", "user.name=t", "add", "-A"], check=True)
            real(["git", "-C", str(dest), "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "x"], check=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return real(cmd, *a, **k)
    monkeypatch.setattr(scan.subprocess, "run", run)


def test_tree_link_clones_that_branch_and_pins_the_commit(monkeypatch, tmp_path):
    rec = []
    _fake_git(monkeypatch, ["main", "interview-task"], rec)
    src = scan.clone("https://github.com/acme/take-home/tree/interview-task/src/app", tmp_path / "r")
    assert "--branch=interview-task" in rec[0] and rec[0][-3:-1] == ["--", "https://github.com/acme/take-home"]
    assert src["branch"] == "interview-task" and src["branch_from_link"] and len(src["commit"]) == 40


def test_unknown_branch_is_a_plain_error(monkeypatch, tmp_path):
    _fake_git(monkeypatch, ["main"], [])
    with pytest.raises(scan.ScanError, match="no such branch"):
        scan.clone("https://github.com/acme/take-home/tree/nope", tmp_path / "r")


def test_takedown_report_names_the_exact_commit():
    kit = campaign.abuse_kit({"verdict": "MALICIOUS", "headline": "x", "findings": [], "stolen": [], "network": [],
                              "target": "https://github.com/acme/take-home",
                              "source": {"repo": "https://github.com/acme/take-home", "branch": "main", "commit": SHA_OLD}})
    assert f"commit {SHA_OLD}" in kit["text"] and "branch main" in kit["text"]


def _client(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    monkeypatch.setenv("BURNER_MOCK", "1")
    import burner.web.app as web
    web = importlib.reload(web)
    monkeypatch.setattr(web, "WEB_DIR", tmp_path)
    return web, TestClient(web.app)


def _stored(tmp_path, jid, commit):
    (tmp_path / f"{jid}.json").write_text(json.dumps({"verdict": "MALICIOUS", "headline": "x", "source": {
        "repo": "https://github.com/acme/take-home", "branch": "main", "commit": commit}}))


@pytest.mark.parametrize("ls_out,rc,state", [(f"{SHA_OLD}\trefs/heads/main\n", 0, "same"),
                                             (f"{SHA_NEW}\trefs/heads/main\n", 0, "changed"),
                                             ("", 0, "gone"), ("", 128, "gone")])
def test_changed_since_this_scan(monkeypatch, tmp_path, ls_out, rc, state):
    web, c = _client(monkeypatch, tmp_path)
    _stored(tmp_path, "abcdef0123", SHA_OLD)
    seen = []

    def run(cmd, *a, **k):
        seen.append(cmd)
        return subprocess.CompletedProcess(cmd, rc, ls_out, "")
    monkeypatch.setattr(web.subprocess, "run", run)
    j = c.get("/api/scan/abcdef0123/head").json()
    assert j["state"] == state
    assert seen[0][-3:] == ["--", "https://github.com/acme/take-home", "refs/heads/main"]   # from the report, not the client


def test_changed_check_needs_a_pinned_commit(monkeypatch, tmp_path):
    web, c = _client(monkeypatch, tmp_path)
    (tmp_path / "abcdef0124.json").write_text(json.dumps({"verdict": "MALICIOUS", "headline": "x"}))
    assert c.get("/api/scan/abcdef0124/head").status_code == 404
    assert c.get("/api/scan/nothex/head").status_code == 404


def test_scan_api_accepts_forgiving_links_and_normalises_them(monkeypatch, tmp_path):
    web, c = _client(monkeypatch, tmp_path)
    monkeypatch.setattr(web.time, "sleep", lambda s: None)
    r = c.post("/api/scan", json={"repo": "github.com/acme/take-home/"})
    assert r.status_code == 200
    assert web.jobs[r.json()["id"]]["req"].repo == "https://github.com/acme/take-home"
    assert c.post("/api/scan", json={"repo": "https://evil.example/x"}).status_code == 400
