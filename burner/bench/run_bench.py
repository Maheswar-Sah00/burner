"""Burner benchmark runner: campaign-style vs clean take-homes, Burner vs GuardDog.

  python -m burner.bench.run_bench [--host IP] [--label final] [--only NAME ...] [--setup] [--no-scan]

1. uploads burner/node + samples/benchmark/build.py to the VM (/bench/<label>/)
2. builds the sample repos THERE (they never touch this workstation's disk)
3. on the VM, for each sample: GuardDog static scan, then run_scan.py (default plan, no LLM)
   -- run by a detached driver so a dropped ssh connection does not kill the benchmark
4. downloads every report and writes reports/benchmark/results.json + results.md

Scans run one at a time: run_scan.py uses one fixed fake-internet address on the VM.
"""
import argparse
import io
import json
import os
import statistics
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = ROOT / "burner" / "node"
BUILD = ROOT / "samples" / "benchmark" / "build.py"
KEY = ROOT / ".burner" / "id_ed25519"
OUT = ROOT / "reports" / "benchmark"
DEFAULT_HOST = "139.84.217.2"
SSH_OPTS = ["-i", str(KEY), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=15"]
CLEAN = "NO MALICIOUS BEHAVIOUR OBSERVED"

VM_DRIVER = r'''
import json, os, subprocess, sys, time
base, only = sys.argv[1], set(sys.argv[2:])
man = json.load(open(f"{base}/samples/manifest.json"))
for s in man["samples"]:
    name = s["name"]
    if only and name not in only:
        continue
    r = f"{base}/results/{name}"
    subprocess.run(["rm", "-rf", r]); os.makedirs(r)
    gd = {}
    for eco in s["ecosystem"]:
        t0 = time.time()
        p = subprocess.run(["/opt/guarddog/bin/guarddog", eco, "scan", f"{base}/samples/{name}", "--output-format=json"],
                           capture_output=True, text=True, timeout=900)
        try:
            gd[eco] = json.loads(p.stdout)
        except ValueError:
            gd[eco] = {"error": (p.stdout + p.stderr)[-800:]}
        gd[eco]["_secs"] = round(time.time() - t0, 2)
    json.dump(gd, open(f"{r}/guarddog.json", "w"))
    if os.environ.get("BENCH_NO_SCAN"):
        continue
    t0 = time.time()
    try:
        p = subprocess.run([sys.executable, "-u", f"{base}/burner/run_scan.py", "--repo", f"{base}/samples/{name}",
                            "--out", f"{r}/out"], capture_output=True, text=True, timeout=1200)
        rc, log = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        rc, log = "timeout", str(e)
    open(f"{r}/run.log", "w").write(log)
    json.dump({"secs": round(time.time() - t0, 1), "rc": rc}, open(f"{r}/timing.json", "w"))
open(f"{base}/results/DONE", "w").write("ok")
'''


def ssh(host, cmd, input_bytes=None, timeout=600, retries=4):
    for i in range(retries):
        proc = subprocess.Popen(["ssh", *SSH_OPTS, f"root@{host}", cmd], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, err = proc.communicate(input_bytes, timeout=timeout)
            if proc.returncode != 255:     # 255 = ssh itself failed
                return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        time.sleep(5 * (i + 1))
    raise RuntimeError(f"ssh to {host} failed: {cmd[:80]}")


def upload(host, base):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(NODE_DIR, arcname="burner", filter=lambda ti: None if "__pycache__" in ti.name else ti)
        t.add(BUILD, arcname="build.py")
        data = VM_DRIVER.encode()
        ti = tarfile.TarInfo("vm_driver.py")
        ti.size = len(data)
        t.addfile(ti, io.BytesIO(data))
    p = ssh(host, f"rm -rf {base}/burner {base}/samples && mkdir -p {base} && tar -xzf - -C {base}",
            input_bytes=buf.getvalue())
    if p.returncode:
        raise RuntimeError(p.stderr.decode())


def defender_detections():
    """Windows Defender detections on this workstation that touch the project (pitch data point)."""
    if os.name != "nt":
        return None
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "Get-MpThreatDetection | ForEach-Object { [pscustomobject]@{ThreatID=$_.ThreatID; "
                            "Time=$_.InitialDetectionTime.ToString('s'); Resources=($_.Resources -join ';')} } | "
                            "ConvertTo-Json -Compress; Get-MpThreat | ForEach-Object { [pscustomobject]@{ThreatID=$_.ThreatID;"
                            " Name=$_.ThreatName} } | ConvertTo-Json -Compress"],
                           capture_output=True, text=True, timeout=60)
        lines = [l for l in p.stdout.splitlines() if l.strip()]
        dets = json.loads(lines[0]) if lines else []
        names = json.loads(lines[1]) if len(lines) > 1 else []
        dets = dets if isinstance(dets, list) else [dets]
        names = {n["ThreatID"]: n["Name"] for n in (names if isinstance(names, list) else [names])}
        return [{"threat": names.get(d["ThreatID"], d["ThreatID"]), "time": d["Time"],
                 "file": d["Resources"].replace("file:_", "")} for d in dets if "vultr-lablab" in d["Resources"]]
    except Exception as e:
        return [{"error": str(e)[:200]}]


# ---------------------------------------------------------------- analysis

def guarddog_summary(gd):
    rules, caps, label, secs, errors = set(), set(), None, 0.0, []
    for eco, d in gd.items():
        secs += d.get("_secs", 0)
        if "error" in d and "results" not in d:
            errors.append(f"{eco}: {d['error'][:200]}")
            continue
        for k, v in (d.get("results") or {}).items():
            if v:
                (caps if k.startswith("capability-") else rules).add(k)
        for r in d.get("risks") or []:
            rules.add(r.get("threat_rule") or r.get("name"))
        lab = (d.get("risk_score") or {}).get("label")
        if lab and lab != "no_risks_detected":
            label = lab if label is None else label
    return {"flagged": bool(rules), "flagged_any_rule": bool(rules or caps), "risk_label": label or "no_risks_detected",
            "threat_rules": sorted(rules), "capability_rules": sorted(caps), "secs": round(secs, 2), "errors": errors}


def first_step(report):
    if report.get("stolen"):
        s = min(report["stolen"], key=lambda x: x.get("t", 0))
        return s.get("step")
    for f in report.get("findings", []):
        if f["severity"] in ("critical", "high"):
            return (f.get("evidence") or {}).get("step")
    for f in report.get("findings", []):
        return (f.get("evidence") or {}).get("step")
    return None


def analyse(sample, rdir):
    row = {k: sample[k] for k in ("name", "expected", "technique", "source", "trigger", "ecosystem")}
    gdp = rdir / "guarddog.json"
    row["guarddog"] = guarddog_summary(json.loads(gdp.read_text())) if gdp.exists() else None
    rep = rdir / "out" / "report.json"
    tim = rdir / "timing.json"
    row["secs"] = json.loads(tim.read_text())["secs"] if tim.exists() else None
    if not rep.exists():
        row.update(verdict="ERROR", detected=None, stolen=[], step=None, rules=[])
        return row
    r = json.loads(rep.read_text())
    row["verdict"] = r["verdict"]
    row["detected"] = r["verdict"] != CLEAN
    row["headline"] = r["headline"]
    row["stolen"] = sorted({s["secret"] for s in r.get("stolen", [])})
    row["exfil_channels"] = sorted({f"{s.get('proto') or '?'}->{s['sent_to']}" for s in r.get("stolen", [])})
    row["step"] = first_step(r) if row["detected"] else None
    row["rules"] = sorted({f["rule"] for f in r.get("findings", [])})
    row["findings"] = [f"[{f['severity']}] {f['title']}" for f in r.get("findings", [])][:12]
    row["steps_run"] = [f"{s['name']} (rc={s['rc']}, {s['secs']}s)" for s in r.get("steps", [])]
    return row


def pct(a, b):
    return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "0/0"


def summarise(rows):
    mal = [r for r in rows if r["expected"] == "malicious"]
    ben = [r for r in rows if r["expected"] == "benign"]
    g = lambda r, k: bool(r["guarddog"] and r["guarddog"][k])
    secs = [r["secs"] for r in rows if r["secs"]]
    return {
        "malicious": len(mal), "benign": len(ben),
        "burner_detected": sum(bool(r["detected"]) for r in mal),
        "burner_malicious_verdict": sum(r["verdict"] == "MALICIOUS" for r in mal),
        "burner_named_stolen_secret": sum(bool(r["stolen"]) for r in mal),
        "burner_false_alarms": sum(bool(r["detected"]) for r in ben),
        "guarddog_detected": sum(g(r, "flagged") for r in mal),
        "guarddog_false_alarms": sum(g(r, "flagged") for r in ben),
        "guarddog_any_rule_detected": sum(g(r, "flagged_any_rule") for r in mal),
        "guarddog_any_rule_false_alarms": sum(g(r, "flagged_any_rule") for r in ben),
        "median_scan_secs": statistics.median(secs) if secs else None,
        "max_scan_secs": max(secs) if secs else None,
        "median_guarddog_secs": statistics.median([r["guarddog"]["secs"] for r in rows if r["guarddog"]] or [0]),
        "errors": [r["name"] for r in rows if r["verdict"] == "ERROR"],
    }


def write_md(path, rows, summ, meta):
    m, b = summ["malicious"], summ["benign"]
    L = [f"# Burner benchmark — {meta['label']}", "",
         f"Run {meta['finished']} on Vultr VM {meta['host']} (gVisor sandbox, fake internet, default candidate plan, no LLM). "
         f"Samples generated by `samples/benchmark/build.py` on the VM; all malicious samples are defanged "
         f"(TEST-NET / *.example targets only).", "",
         "## Headline", "",
         f"- **Burner {summ['burner_detected']}/{m} vs GuardDog {summ['guarddog_detected']}/{m} detected; "
         f"false alarms {summ['burner_false_alarms']}/{b} vs {summ['guarddog_false_alarms']}/{b}.**",
         f"- Burner verdict MALICIOUS on {summ['burner_malicious_verdict']}/{m}; named the exact stolen fake secret "
         f"on {summ['burner_named_stolen_secret']}/{m}.",
         f"- GuardDog counting *any* rule hit (incl. its informational `capability-*` rules): "
         f"{summ['guarddog_any_rule_detected']}/{m} detected, {summ['guarddog_any_rule_false_alarms']}/{b} false alarms.",
         f"- Median Burner scan time {summ['median_scan_secs']}s (max {summ['max_scan_secs']}s) per repo; "
         f"GuardDog median {summ['median_guarddog_secs']}s.", "",
         "Detected = Burner verdict MALICIOUS or SUSPICIOUS. GuardDog flagged = at least one `threat-*` rule / risk "
         "(GuardDog 3.x `capability-*` rules only describe what code *can* do and fire on almost every repo).", "",
         "## Per sample", "",
         "| sample | technique | expected | Burner verdict | secrets caught (exfil seen) | step | secs | GuardDog |",
         "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        gd = r["guarddog"]
        gds = ("FLAGGED: " + ", ".join(x.replace("threat-", "") for x in gd["threat_rules"])) if gd and gd["flagged"] \
            else ("clean" if gd else "n/a")
        caught = ", ".join(r["stolen"]) or ("—" if not r["detected"] else "(none decoded; " + ", ".join(r["rules"]) + ")")
        L.append(f"| {r['name']} | {r['technique']} | {r['expected']} | {r['verdict']} | {caught} | {r['step'] or '—'} "
                 f"| {r['secs']} | {gds} |")
    L += ["", "## Sources the malicious samples are modelled on", ""]
    L += [f"- **{r['name']}** ({r['trigger']}): {r['source']}" for r in rows if r["expected"] == "malicious"]
    L += ["", "## Burner findings per sample", ""]
    for r in rows:
        L.append(f"- **{r['name']}** — {r['verdict']}" + (f"; steps: {'; '.join(r.get('steps_run', []))}" if r.get("steps_run") else ""))
        L += [f"  - {f}" for f in r.get("findings", [])]
    if meta.get("defender") is not None:
        L += ["", "## Windows Defender (workstation, at write time)", ""]
        if meta["defender"]:
            L += [f"- {d.get('time')}: {d.get('threat')} on `{d.get('file')}`" for d in meta["defender"]]
        else:
            L.append("- no detections")
        L.append(f"- The benchmark generator itself (`samples/benchmark/build.py`, folderOpen lure stored base64) "
                 f"was not flagged, although the other {m - 1} malicious samples are plain text inside it: static AV "
                 f"caught the obvious folderOpen lure file but none of the stealers.")
    if meta.get("baseline"):
        bs = meta["baseline"]
        L += ["", "## Before detection fixes (same samples, original rules)", "",
              f"- Burner {bs['burner_detected']}/{bs['malicious']} detected, MALICIOUS on {bs['burner_malicious_verdict']}, "
              f"named stolen secret on {bs['burner_named_stolen_secret']}; false alarms {bs['burner_false_alarms']}/{bs['benign']}"
              + (f" (baseline predates the {m - bs['malicious']} newer sample(s))." if m > bs["malicious"] else ".")]
    L += ["", "## What Burner cannot catch (honest limits)", "",
          "- **Code that never runs during the scan**: payloads gated on a real user action we don't simulate "
          "(e.g. `git commit` hooks, a specific CLI flag, a date more than 45 days out, a geo/IP check that wants a real "
          "public IP). Burner only judges what executes.",
          "- **Sandbox killers**: a payload that first exhausts memory/processes kills the sandbox before it acts. "
          "Burner reports this (SANDBOX_DIED → SUSPICIOUS, never clean) but cannot say what would have been stolen.",
          "- **Second stages**: the fake internet never serves real payloads, so for download-and-run loaders Burner sees "
          "the download+execute attempt (REMOTE_CODE), not what stage 2 would do.",
          "- **Custom encryption**: exfil under real crypto (AES with an embedded key) can't be matched to a honeytoken; "
          "the verdict then rests on 'read your keys + contacted an unknown server'. Base64/hex/base32/url/gzip/zip and "
          "repeating-key XOR are decoded.",
          "- **Sandbox-aware malware that stops**: m11 checks for VM artefacts and proceeds anyway; one that exits "
          "cleanly when it detects gVisor/Docker would look clean (we log SANDBOX_CHECK as a low-severity hint)."]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("BURNER_BENCH_HOST", DEFAULT_HOST))
    ap.add_argument("--label", default="final")
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--setup", action="store_true", help="re-run setup.sh on the VM first")
    ap.add_argument("--no-scan", action="store_true", help="GuardDog only")
    ap.add_argument("--analyse-only", action="store_true", help="re-analyse already downloaded results")
    ap.add_argument("--collect", action="store_true", help="don't start anything: wait for / download a run")
    a = ap.parse_args()

    base = f"/bench/{a.label}"
    local = OUT / "runs" / a.label
    if not a.analyse_only and not a.collect:
        print(f"[bench] uploading to {a.host}:{base}", flush=True)
        upload(a.host, base)
        if a.setup:
            p = ssh(a.host, f"bash {base}/burner/setup.sh > {base}/setup.log 2>&1 || tail -30 {base}/setup.log", timeout=1800)
            print(p.stdout.decode()[-2000:])
        p = ssh(a.host, f"python3 {base}/build.py {base}/samples")
        print("[bench]", p.stdout.decode().strip(), p.stderr.decode()[-500:], flush=True)
        env = "BENCH_NO_SCAN=1 " if a.no_scan else ""
        # the whole background job must have its fds redirected, or ssh waits for it; never retry a launch
        ssh(a.host, f"rm -f {base}/results/DONE; mkdir -p {base}/results; "
                    f"(cd {base} && {env}exec setsid flock /bench/.lock python3 vm_driver.py {base} {' '.join(a.only)}) "
                    f"> {base}/driver.log 2>&1 < /dev/null &", timeout=60, retries=1)
    if not a.analyse_only:
        t0, seen = time.time(), -1
        while True:
            time.sleep(20)
            try:
                p = ssh(a.host, f"test -f {base}/results/DONE && echo DONE; ls {base}/results/*/timing.json 2>/dev/null | wc -l",
                        timeout=60)
            except RuntimeError as e:
                print("[bench] (ssh hiccup)", e, flush=True)
                continue
            out = p.stdout.decode()
            n = int(out.split()[-1]) if out.split() else 0
            if n != seen:
                print(f"[bench] {n} scans finished ({time.time() - t0:.0f}s)", flush=True)
                seen = n
            if "DONE" in out:
                break
        p = ssh(a.host, f"tar -czf - -C {base} --exclude=syscalls.log --exclude=_work results samples/manifest.json "
                        f"driver.log", timeout=600)
        local.mkdir(parents=True, exist_ok=True)
        tarfile.open(fileobj=io.BytesIO(p.stdout), mode="r:gz").extractall(local, filter="data")

    manifest = json.loads((local / "samples" / "manifest.json").read_text())
    rows = [analyse(s, local / "results" / s["name"]) for s in manifest["samples"]
            if (local / "results" / s["name"]).exists()]
    summ = summarise(rows)
    meta = {"label": a.label, "host": a.host, "finished": time.strftime("%Y-%m-%d %H:%M"),
            "built_at": manifest["built_at"], "defender": defender_detections()}
    bl = OUT / "runs" / "baseline" / "summary.json"
    if a.label != "baseline" and bl.exists():
        meta["baseline"] = json.loads(bl.read_text())
    (local / "summary.json").write_text(json.dumps(summ, indent=1))
    res = {"meta": meta, "summary": summ, "samples": rows}
    if a.label == "final":
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "results.json").write_text(json.dumps(res, indent=1))
        write_md(OUT / "results.md", rows, summ, meta)
    (local / "results.json").write_text(json.dumps(res, indent=1))
    write_md(local / "results.md", rows, summ, meta)
    print(json.dumps(summ, indent=1))
    for r in rows:
        print(f"  {r['name']:28} {r['expected']:9} {r['verdict']:32} stolen={r['stolen']} step={r['step']} "
              f"gd={'Y' if r['guarddog'] and r['guarddog']['flagged'] else 'n'} {r['secs']}s")


if __name__ == "__main__":
    sys.exit(main())
