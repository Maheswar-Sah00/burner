"""Burner Verified: signed per-commit statements, owner identity, badge states."""
import copy
import json
from pathlib import Path

import pytest

from burner.control import attest, precheck

ROOT = Path(__file__).resolve().parents[1]
CLEAN = json.loads((ROOT / "burner" / "web" / "recorded" / "clean-takehome.json").read_text(encoding="utf-8"))
BAD = json.loads((ROOT / "burner" / "web" / "recorded" / "npm-start-stealer.json").read_text(encoding="utf-8"))
SHA1, SHA2 = "a" * 40, "b" * 40


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(attest, "KEY_FILE", tmp_path / "key.pem")
    monkeypatch.setattr(attest, "STORE", tmp_path / "attest")
    monkeypatch.setattr(attest, "_key", None)
    monkeypatch.setenv("BURNER_ATTEST_NO_S3", "1")
    attest._owner_cache.clear()
    attest._head_cache.clear()

    def fake_fetch(url, timeout=3.0, headers=None, max_bytes=2_000_000):
        if url.endswith("/users/acme-hiring"):
            return {"login": "acme-hiring", "type": "Organization", "created_at": "2019-01-01T00:00:00Z"}, {}
        if url.endswith("/orgs/acme-hiring"):
            return {"login": "acme-hiring", "is_verified": True, "blog": "acme.example", "name": "Acme"}, {}
        if url.endswith("/users/lumina-ledger"):
            return {"login": "lumina-ledger", "type": "User", "created_at": "2026-11-01T00:00:00Z"}, {}
        raise OSError("offline")
    monkeypatch.setattr(precheck, "fetch_json", fake_fetch)


def with_source(rep, owner="acme-hiring", name="take-home", commit=SHA1):
    r = copy.deepcopy(rep)
    r["source"] = {"repo": f"https://github.com/{owner}/{name}", "branch": "main", "commit": commit,
                   "committed_at": "2026-11-07T10:00:00Z"}
    return r


def test_sign_and_verify_roundtrip():
    env = attest.sign({"x": 1, "y": "ü"})
    assert attest.verify(env)
    env["statement"]["x"] = 2
    assert not attest.verify(env)


def test_key_persists_between_loads(tmp_path):
    kid = attest.key_id()
    attest._key = None
    assert attest.key_id() == kid
    assert (tmp_path / "key.pem").exists()


def test_clean_scan_is_attested_with_verified_owner():
    env = attest.issue(with_source(CLEAN), "abc1234567")
    st = env["statement"]
    assert attest.verify(env)
    assert st["result"] == "clean" and st["subject"]["commit"] == SHA1
    assert st["owner"]["kind"] == "organisation" and st["owner"]["verified"] is True
    assert st["owner"]["site"] == "https://acme.example"
    assert st["burn"]["vm"]["deleted"] is True and st["burn"]["fake_secrets_planted"] == len(CLEAN["bait"])
    assert st["burn"]["app_started"] is True
    assert attest.load("acme-hiring", "take-home", SHA1) == env
    assert attest.history("acme-hiring", "take-home")[0]["scan_id"] == "abc1234567"


def test_malicious_scan_is_attested_too():
    env = attest.issue(with_source(BAD, owner="lumina-ledger"), "bad0000001")
    st = env["statement"]
    assert st["result"] == "malicious" and st["burn"]["fake_secrets_sent"] >= 5
    assert st["owner"]["kind"] == "personal account" and st["owner"]["verified"] is False


def test_local_sample_or_unpinned_scan_is_not_attested():
    assert attest.issue(CLEAN, "x") is None                       # sample folder: no source
    r = with_source(CLEAN)
    r["source"]["commit"] = None
    assert attest.issue(r, "x") is None
    r = with_source(CLEAN)
    r["source"]["repo"] = "https://gitlab.com/a/b"
    assert attest.issue(r, "x") is None


def test_badge_states_follow_the_default_branch():
    head = {"sha": SHA1}
    ls = lambda o, n: head["sha"]
    assert attest.state("acme-hiring", "take-home", ls)["state"] == "none"
    attest.issue(with_source(CLEAN), "s1")
    attest._head_cache.clear()
    st = attest.state("acme-hiring", "take-home", ls)
    assert st["state"] == "clean" and st["commit"] == SHA1
    head["sha"] = SHA2                       # someone pushed: the old statement no longer covers HEAD
    attest._head_cache.clear()
    st = attest.state("acme-hiring", "take-home", ls)
    assert st["state"] == "changed" and st["last_clean"]["commit"] == SHA1
    attest.issue(with_source(BAD, commit=SHA2), "s2")
    attest._head_cache.clear()
    assert attest.state("acme-hiring", "take-home", ls)["state"] == "malicious"


def test_badge_svg_has_state_and_commit():
    svg = attest.badge_svg({"state": "clean", "commit": SHA1})
    assert "burned clean · aaaaaaa" in svg and "#2f9e44" in svg
    assert "changed since burn" in attest.badge_svg({"state": "changed", "commit": SHA1})
    assert "<script" not in attest.badge_svg({"state": "<script>", "commit": None})


def test_canonical_bytes_are_stable():
    assert attest.canonical({"b": 1, "a": [1, {"d": 2, "c": "é"}]}) == '{"a":[1,{"c":"é","d":2}],"b":1}'.encode()
