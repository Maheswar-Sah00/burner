"""Cloud firewall for burner VMs, evidence manifest, persistent report links. No network: Vultr and S3 are faked.

  python -m pytest tests/test_integrity.py
"""
import hashlib
import importlib
import io
import json
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burner.control import evidence, pool, vultr  # noqa: E402


class FakeVultr:
    """Just enough of /v2/firewalls and /v2/instances, recording every call."""

    def __init__(self, groups=None, rules=None, attach_on_create=True, fail=None):
        self.groups = groups or []
        self.rules = rules or {}
        self.calls = []
        self.attach_on_create = attach_on_create
        self.fail = fail or (lambda method, path: False)
        self.instances = {}

    def __call__(self, method, path, body=None):
        self.calls.append((method, path, body))
        if self.fail(method, path):
            raise RuntimeError(f"Vultr {method} {path} -> 500: boom")
        base = path.split("?")[0]
        if (method, base) == ("GET", "/firewalls"):
            return {"firewall_groups": self.groups}
        if (method, base) == ("POST", "/firewalls"):
            g = {"id": f"fw-{len(self.groups) + 1}", "description": body["description"]}
            self.groups.append(g)
            self.rules[g["id"]] = []
            return {"firewall_group": g}
        if method == "GET" and base.endswith("/rules"):
            return {"firewall_rules": self.rules[base.split("/")[2]]}
        if method == "POST" and base.endswith("/rules"):
            rs = self.rules[base.split("/")[2]]
            rs.append({"id": len(rs) + 1, **body})
            return {"firewall_rule": rs[-1]}
        if method == "DELETE" and "/rules/" in base:
            gid, rid = base.split("/")[2], int(base.split("/")[4])
            self.rules[gid] = [r for r in self.rules[gid] if r["id"] != rid]
            return {}
        if (method, base) == ("POST", "/instances"):
            inst = {"id": "vm-1", "firewall_group_id": body.get("firewall_group_id", "") if self.attach_on_create else ""}
            self.instances["vm-1"] = inst
            return {"instance": dict(inst)}
        if method == "PATCH" and base.startswith("/instances/"):
            self.instances.setdefault(base.split("/")[2], {}).update(body)
            return {}
        if method == "DELETE" and base.startswith("/instances/"):
            self.instances.pop(base.split("/")[2], None)
            return {}
        raise AssertionError(f"unexpected call {method} {path}")


@pytest.fixture
def fake(monkeypatch):
    monkeypatch.setattr(vultr, "_fw", {"id": None, "at": 0.0})
    monkeypatch.delenv("BURNER_SSH_ALLOW", raising=False)
    monkeypatch.delenv("BURNER_FIREWALL_REQUIRED", raising=False)
    monkeypatch.setattr(vultr, "CONTROL_IP", "139.84.215.1")

    def make(**kw):
        f = FakeVultr(**kw)
        monkeypatch.setattr(vultr, "_call", f)
        return f
    return make


def _ssh_sources(f, gid):
    return sorted(f"{r['subnet']}/{r['subnet_size']}" for r in f.rules[gid] if r["protocol"] == "tcp" and r["port"] == "22")


def test_firewall_group_is_created_with_ssh_from_control_plane_only(fake, monkeypatch):
    f = fake()
    monkeypatch.setenv("BURNER_SSH_ALLOW", " 27.6.72.170 , 10.0.0.0/8,")
    gid = vultr.ensure_firewall_group()
    assert f.groups == [{"id": gid, "description": "burner-scan"}]
    assert _ssh_sources(f, gid) == ["10.0.0.0/8", "139.84.215.1/32", "27.6.72.170/32"]
    assert all(r["port"] == "22" and r["protocol"] == "tcp" for r in f.rules[gid])   # nothing else inbound


def test_firewall_group_is_found_by_description_cached_and_cleaned(fake):
    f = fake(groups=[{"id": "other", "description": "someone-else"}, {"id": "fw-x", "description": "burner-scan"}],
             rules={"fw-x": [{"id": 1, "protocol": "tcp", "port": "9999", "subnet": "0.0.0.0", "subnet_size": 0},
                             {"id": 2, "protocol": "tcp", "port": "22", "subnet": "139.84.215.1", "subnet_size": 32},
                             {"id": 3, "protocol": "tcp", "port": "22", "subnet": "1.2.3.4", "subnet_size": 32}]})
    assert vultr.ensure_firewall_group() == "fw-x"
    assert not any(m == "POST" and p == "/firewalls" for m, p, _ in f.calls)        # reused, not duplicated
    assert [r["id"] for r in f.rules["fw-x"]] == [2, 3]   # 9999 rule deleted; other SSH sources (dev box) kept
    n = len(f.calls)
    assert vultr.ensure_firewall_group() == "fw-x" and len(f.calls) == n           # cached


def test_ssh_allow_refuses_the_whole_internet(fake, monkeypatch):
    fake()
    monkeypatch.setenv("BURNER_SSH_ALLOW", "0.0.0.0/0")
    with pytest.raises(ValueError):
        vultr.ssh_allow_cidrs()


def test_new_vm_gets_the_firewall_in_the_create_call(fake):
    f = fake()
    inst = vultr.create_instance("burner-x", tags=["burner-scan"])
    body = next(b for m, p, b in f.calls if (m, p) == ("POST", "/instances"))
    assert body["firewall_group_id"] == inst["firewall_group_id"] == f.groups[0]["id"]
    assert not any(m == "PATCH" for m, _, _ in f.calls)


def test_firewall_is_patched_on_if_create_ignored_it(fake):
    f = fake(attach_on_create=False)
    inst = vultr.create_instance("burner-x")
    assert ("PATCH", "/instances/vm-1", {"firewall_group_id": "fw-1"}) in f.calls
    assert inst["firewall_group_id"] == "fw-1"


def test_no_firewall_means_no_vm_by_default(fake):
    f = fake(fail=lambda m, p: p.startswith("/firewalls"))
    with pytest.raises(RuntimeError, match="refusing to create"):
        vultr.create_instance("burner-x")
    assert not any(p == "/instances" for _, p, _ in f.calls)


def test_vm_whose_firewall_wont_attach_is_deleted(fake):
    f = fake(attach_on_create=False, fail=lambda m, p: m == "PATCH")
    with pytest.raises(RuntimeError, match="VM deleted"):
        vultr.create_instance("burner-x")
    assert ("DELETE", "/instances/vm-1", None) in f.calls


def test_firewall_override_proceeds_loudly(fake, monkeypatch, capsys):
    f = fake(fail=lambda m, p: p.startswith("/firewalls"))
    monkeypatch.setenv("BURNER_FIREWALL_REQUIRED", "0")
    vultr.create_instance("burner-x")
    body = next(b for m, p, b in f.calls if (m, p) == ("POST", "/instances"))
    assert "firewall_group_id" not in body and "WITHOUT" in capsys.readouterr().err


def test_control_vm_opts_out(fake):
    f = fake()
    vultr.create_instance("burner-control", tags=["burner-control"], firewall=False)
    assert not any(p.startswith("/firewalls") for _, p, _ in f.calls)


def test_pool_claim_attaches_firewall_to_old_pool_vms(fake, monkeypatch):
    f = fake()
    monkeypatch.setattr(vultr, "list_instances", lambda tag: [
        {"id": "old-pool-vm", "tags": ["burner-pool", "armed"], "firewall_group_id": ""}])
    i = pool.claim()
    assert i["firewall_group_id"] == "fw-1"
    assert ("PATCH", "/instances/old-pool-vm", {"firewall_group_id": "fw-1"}) in f.calls


def test_pool_claim_deletes_vm_it_cannot_firewall(fake, monkeypatch):
    f = fake(fail=lambda m, p: p.startswith("/firewalls"))
    monkeypatch.setattr(vultr, "list_instances", lambda tag: [{"id": "old", "tags": ["armed"], "firewall_group_id": ""}])
    assert pool.claim() is None and ("DELETE", "/instances/old", None) in f.calls


# ---- evidence integrity --------------------------------------------------------------------------

def _scan_dir(tmp_path):
    d = tmp_path / "20261106-120000-takehome"
    (d / "net").mkdir(parents=True)
    (d / "report.json").write_text('{"verdict": "MALICIOUS"}')
    (d / "syscalls.log").write_bytes(b"openat(\"/root/.ssh/id_rsa\")\n" * 100)
    (d / "net" / "requests.jsonl").write_text('{"host": "evil.example"}\n')
    return d


def test_manifest_lists_every_file_with_size_and_sha256(tmp_path):
    d = _scan_dir(tmp_path)
    m, sha = evidence.write_manifest(d, verdict="MALICIOUS", vm_id="vm-1", started_at=1793800000, finished_at=1793800100)
    assert [f["path"] for f in m["files"]] == ["net/requests.jsonl", "report.json", "syscalls.log"]
    f = next(f for f in m["files"] if f["path"] == "syscalls.log")
    raw = (d / "syscalls.log").read_bytes()
    assert f["bytes"] == len(raw) and f["sha256"] == hashlib.sha256(raw).hexdigest()
    assert m["scan_id"] == d.name and m["verdict"] == "MALICIOUS" and m["vm_id"] == "vm-1"
    assert m["started_at"].startswith("2026-") and m["file_count"] == 3
    assert sha == hashlib.sha256((d / "manifest.json").read_bytes()).hexdigest()
    # re-sealing doesn't list the manifest itself
    m2, _ = evidence.write_manifest(d)
    assert "manifest.json" not in [f["path"] for f in m2["files"]]


def test_manifest_detects_tampering(tmp_path):
    d = _scan_dir(tmp_path)
    evidence.write_manifest(d)
    assert evidence.verify_manifest(d) == []
    (d / "syscalls.log").write_bytes(b"nothing to see here\n")
    (d / "net" / "requests.jsonl").unlink()
    assert evidence.verify_manifest(d) == ["net/requests.jsonl", "syscalls.log"]


class FakeS3:
    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise type("NoSuchKey", (Exception,), {})()
        return {"Body": io.BytesIO(self.objects[Key])}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://s3.example/{Params['Key']}?exp={ExpiresIn}"


def test_upload_seals_bundle_and_report_goes_next_to_it(tmp_path, monkeypatch):
    s3 = FakeS3()
    monkeypatch.setattr(evidence, "_client", s3)
    d = _scan_dir(tmp_path)
    ev = evidence.upload(d, f"scans/{d.name}", verdict="MALICIOUS")
    body = s3.objects[ev["key"]]
    assert ev["key"] == f"scans/{d.name}.tar.gz" and ev["sha256"] == hashlib.sha256(body).hexdigest()
    with tarfile.open(fileobj=io.BytesIO(body)) as t:     # the manifest inside the bundle is the one hashed
        inner = t.extractfile(f"{d.name}/manifest.json").read()
    assert hashlib.sha256(inner).hexdigest() == ev["manifest_sha256"] and ev["file_count"] == 3
    assert evidence.upload_report({"verdict": "MALICIOUS", "evidence": ev}, f"scans/{d.name}") == f"scans/{d.name}.report.json"
    assert json.loads(s3.objects[f"scans/{d.name}.report.json"])["evidence"]["manifest_sha256"] == ev["manifest_sha256"]
    assert evidence.get_json("scans/nope.json") is None


# ---- permanent report links ----------------------------------------------------------------------

def test_share_link_survives_restart_and_lost_disk(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    monkeypatch.delenv("BURNER_MOCK", raising=False)
    import burner.web.app as web
    web = importlib.reload(web)
    monkeypatch.setattr(web, "WEB_DIR", tmp_path / "_web")
    s3 = FakeS3()
    monkeypatch.setattr(evidence, "_client", s3)
    monkeypatch.setattr(web, "POOL_SIZE", 0)
    rep = {"verdict": "MALICIOUS", "evidence": {"key": "scans/x.tar.gz"}}
    web._save({"id": "abcdef0123", "report": rep, "req": web.ScanRequest(repo="https://github.com/a/b")})
    assert json.loads((tmp_path / "_web" / "abcdef0123.json").read_text()) == rep
    import threading
    import time as _t
    deadline, tick = _t.monotonic() + 5, threading.Event()   # the Object Storage copy is made in the background
    while _t.monotonic() < deadline and "scans/_web/abcdef0123.json" not in s3.objects:
        tick.wait(0.05)
    assert "scans/_web/abcdef0123.json" in s3.objects

    web.jobs.clear()                                       # process restarted
    c = TestClient(web.app)
    assert c.get("/api/scan/abcdef0123").json()["report"] == rep
    (tmp_path / "_web" / "abcdef0123.json").unlink()      # control VM rebuilt: disk gone, Object Storage remains
    assert c.get("/api/scan/abcdef0123").json()["report"] == rep
    assert (tmp_path / "_web" / "abcdef0123.json").exists()   # re-cached
    r = c.get("/e/abcdef0123", follow_redirects=False)
    assert r.status_code in (302, 307) and "scans/x.tar.gz" in r.headers["location"]
    assert c.get("/api/scan/0000000000").status_code == 404
    assert c.get("/api/scan/..%2Fsecret").status_code == 404
