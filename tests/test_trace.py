"""Shape checks for report.trace / report.flows (burner/web/CONTRACT.md).

  python tests/test_trace.py      (or: python -m pytest tests/test_trace.py)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from burner.control import trace  # noqa: E402

BENCH = ROOT / "reports" / "benchmark" / "runs" / "final" / "results"
LANES = {"secrets", "files", "processes", "network", "exfil", "dns"}
SEVS = {"critical", "high", "medium", "low", "info"}


def check(scan_dir):
    rep = json.loads((scan_dir / "report.json").read_text(encoding="utf-8"))
    t, f = trace.build(scan_dir, rep)
    json.dumps(t), json.dumps(f)                        # serialisable

    assert isinstance(t["duration"], (int, float)) and t["duration"] >= 0
    for s in t["steps"]:
        assert set(s) >= {"name", "t0", "t1", "rc", "sandbox_died"}
        assert s["t1"] >= s["t0"] and isinstance(s["sandbox_died"], bool)
    assert t["steps"] and t["steps"][0]["t0"] == 0     # relative to the first step
    assert len(t["events"]) <= trace.MAX_EVENTS
    assert [e["t"] for e in t["events"]] == sorted(e["t"] for e in t["events"])
    for e in t["events"]:
        assert set(e) >= {"t", "lane", "label", "detail", "severity", "step"}, e
        assert e["lane"] in LANES and e["severity"] in SEVS, e

    ids = [n["id"] for n in f["nodes"]]
    assert len(ids) == len(set(ids))
    for n in f["nodes"]:
        assert n["kind"] in ("secret", "process", "destination") and n["id"][:2] in ("s:", "p:", "d:")
    secrets = {n["label"]: n for n in f["nodes"] if n["kind"] == "secret"}
    for b in rep["bait"]:                               # every planted bait is a secret node
        assert b["kind"] in secrets, b
    taken = {s["secret"] for s in rep["stolen"]}
    assert {k for k, n in secrets.items() if n["taken"]} == taken
    for link in f["links"]:
        assert link["source"] in ids and link["target"] in ids
        assert link["kind"] in ("read", "sent")
        if link["kind"] == "sent":
            assert link["secrets"] and isinstance(link["bytes"], int)
    exfil = [e for e in t["events"] if e["lane"] == "exfil"]
    assert bool(exfil) == bool(rep["stolen"])
    return t, f


def test_stealer_benchmark():                           # committed bundle, no syscalls.log
    t, f = check(BENCH / "m01-svg-asset-eval" / "out")
    assert any(l["kind"] == "sent" for l in f["links"])


def test_dns_exfil():
    t, f = check(BENCH / "m09-dns-exfil" / "out")
    assert any(n.get("via") == "dns" for n in f["nodes"])


def test_sandbox_died():
    t, _ = check(BENCH / "m13-resource-bomb" / "out")
    assert any(s["sandbox_died"] for s in t["steps"])


def test_benign():
    t, f = check(BENCH / "b01-express-api" / "out")
    assert not [e for e in t["events"] if e["lane"] == "exfil"] and not f["links"]


def test_full_scan_with_syscalls():                     # local scans/ (gitignored): skipped if absent
    scans = sorted(p for p in (ROOT / "scans").glob("*-fake-takehome") if (p / "syscalls.log").exists()
                   and json.loads((p / "report.json").read_text())["stolen"])
    if not scans:
        return
    t, f = check(scans[-1])
    lanes = {e["lane"] for e in t["events"]}
    assert {"secrets", "network", "exfil"} <= lanes
    assert any(n["kind"] == "process" and n["label"] == "node" for n in f["nodes"])


def test_missing_files(tmp=None):
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        t, f = trace.build(d, {})
        assert t["events"] == [] and t["steps"] == [] and f == {"nodes": [], "links": []}


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
