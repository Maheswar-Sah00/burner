"""Burner control plane: one throwaway Vultr VM per scan.

  python -m burner.control.scan [PATH_OR_GIT_URL] [--message recruiter.txt] [--host IP] [--keep] [--snapshot ID]

  --message FILE  the recruiter's message; the repo link is taken from it if no target is given
  --host IP       reuse an existing burner VM (development)
  --keep          don't destroy the VM afterwards
"""
import argparse
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
from pathlib import Path

from . import brain, campaign, evidence, pool, precheck, vultr

ROOT = Path(__file__).resolve().parents[2]
NODE_DIR = ROOT / "burner" / "node"
KEY = ROOT / ".burner" / "id_ed25519"
SSH_OPTS = ["-i", str(KEY), "-o", "StrictHostKeyChecking=no", "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR", "-o", "ConnectTimeout=10", "-o", "ServerAliveInterval=15"]
DEFAULT_SNAPSHOT = os.environ.get("BURNER_SNAPSHOT_ID")

_spec = importlib.util.spec_from_file_location("run_scan", NODE_DIR / "run_scan.py")
node_run_scan = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(node_run_scan)


def ssh(host, cmd, input_bytes=None, timeout=1800):
    return subprocess.run(["ssh", *SSH_OPTS, f"root@{host}", cmd], input=input_bytes, capture_output=True,
                          timeout=timeout)


def wait_ssh(host, timeout=300):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if ssh(host, "true", timeout=20).returncode == 0:
            return
        time.sleep(3)
    raise TimeoutError("ssh not reachable")


def tar_dirs(entries):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        for src, arc in entries:
            t.add(src, arcname=arc,
                  filter=lambda ti: None if "node_modules" in ti.name or "__pycache__" in ti.name else ti)
    return buf.getvalue()


def file_tree(repo, limit=120):
    out = []
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules")]
        for f in files:
            out.append(os.path.relpath(os.path.join(root, f), repo).replace("\\", "/"))
            if len(out) >= limit:
                return "\n".join(out)
    return "\n".join(out)


def read(p, n=20000):
    try:
        return Path(p).read_text(encoding="utf-8", errors="replace")[:n]
    except OSError:
        return ""


class ScanError(Exception):
    """A problem with the user's input, in plain English (shown as-is in the web UI)."""


CLONE_TIMEOUT = int(os.environ.get("BURNER_CLONE_TIMEOUT", "90"))
MAX_REPO_MB = int(os.environ.get("BURNER_MAX_REPO_MB", "200"))
_detect_spec = importlib.util.spec_from_file_location("detect", NODE_DIR / "detect.py")
node_detect = importlib.util.module_from_spec(_detect_spec)
_detect_spec.loader.exec_module(node_detect)


def clone(url, dest):
    """Shallow clone with no hooks, no symlinks, no credential prompt; bounded in time and size."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "GCM_INTERACTIVE": "never"}
    try:
        p = subprocess.run(["git", "clone", "--depth", "1", "--single-branch", "--no-tags",
                            "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false", "-c", "credential.helper=",
                            url, str(dest)], capture_output=True, text=True, timeout=CLONE_TIMEOUT, env=env)
    except subprocess.TimeoutExpired:
        raise ScanError(f"The repo took longer than {CLONE_TIMEOUT} s to download, so Burner stopped. "
                        "Take-homes are small; a repo this big is unusual.")
    if p.returncode:
        err = (p.stderr or "").lower()
        if any(s in err for s in ("could not read username", "authentication", "not found", "does not exist",
                                  "terminal prompts disabled", "403", "404")):
            raise ScanError("Couldn't download that repo: it's private, deleted or the link is wrong. "
                            "Burner can only scan public repos.")
        last = (p.stderr or "").strip().splitlines()[-1:] or ["unknown error"]
        raise ScanError(f"Couldn't download that repo (git: {last[0][:160]}).")
    size = sum(f.stat().st_size for f in Path(dest).rglob("*") if f.is_file()) / 1e6
    if size > MAX_REPO_MB:
        raise ScanError(f"That repo is {size:.0f} MB; Burner stops at {MAX_REPO_MB} MB. Take-homes are small.")


def start_precheck(repo, url, message, emit):
    """Pre-check in a background thread: static tripwires + provenance, no code run. Warnings only, never the verdict.
    Emits one "precheck" event (with the full result as `data` when the emitter accepts it). Returns a getter."""
    box = {}

    def work():
        try:
            pc = precheck.run(repo, url=url, message=message)
        except Exception as e:   # never breaks a scan
            pc = {"flags": [], "counts": {"high": 0, "warn": 0, "info": 0}, "ms": 0, "error": str(e)[:200],
                  "note": precheck.NOTE}
        box["pc"] = pc
        try:
            emit("precheck", precheck.summary(pc), data=pc)
        except TypeError:        # an emitter that only takes (stage, text), e.g. the CLI's
            emit("precheck", precheck.summary(pc))

    t = threading.Thread(target=work, name="precheck", daemon=True)
    t.start()

    def get(timeout=8):
        t.join(timeout)
        return box.get("pc")
    return get


def vultr_bill(report):
    """Every Vultr service this scan used, what it did, and what it cost (from what was actually recorded)."""
    items = []
    vm = report.get("vm") or {}
    if vm.get("id"):
        how = "taken pre-armed from the warm pool" if vm.get("from_pool") else "created for this scan"
        items.append({"service": "Cloud Compute", "what": f"one {vm.get('plan')} VM in {vm.get('region')}, {how}, "
                                                          "ran the repo, then deleted via the API",
                      "detail": f"{vm.get('lifetime_secs')} s alive" if vm.get("lifetime_secs") is not None else None,
                      "usd": vm.get("cost_usd_prorated"),
                      "api": ["GET /v2/instances (claim)" if vm.get("from_pool") else "POST /v2/instances",
                              "DELETE /v2/instances/{id}"]})
    for c in (report.get("llm_usage") or {}).get("by_call", []):
        pin, pout = brain.price(c["model"])
        usd = (c["prompt_tokens"] * pin + c["completion_tokens"] * pout) if pin is not None and pout is not None else None
        items.append({"service": "Serverless Inference", "what": brain.ROLES.get(c.get("role"), c.get("role") or "LLM call"),
                      "model": c["model"], "detail": f"{c['prompt_tokens'] + c['completion_tokens']:,} tokens, {c['secs']} s",
                      "usd": round(usd, 6) if usd is not None else None})
    ev = report.get("evidence") or {}
    if ev.get("key"):
        items.append({"service": "Object Storage", "what": "stored the evidence bundle (syscall log, captured requests, report)",
                      "detail": f"{max(1, round((ev.get('bytes') or 0) / 1024))} KB", "usd": None,
                      "note": "flat-rate subscription"})
    known = [i["usd"] for i in items if i.get("usd") is not None]
    return {"items": items, "total_usd": round(sum(known), 6) if known else None,
            "note": "The verdict comes from rules; the AI rows only read, plan and explain."}


def ai(say, stage, what, fn, fallback, errors):
    """Run one LLM step; if Vultr Inference is down or the model was retired, carry on with rules only."""
    try:
        return fn()
    except Exception as e:
        errors.append({"step": what, "error": str(e)[:200]})
        say(stage, f"AI unavailable for {what}; carrying on with rules only (the verdict never depends on AI)")
        return fallback


def run(target=None, message=None, host=None, keep=False, snapshot=DEFAULT_SNAPSHOT, region="blr",
        vm_plan="vc2-2c-4gb", out_root=ROOT / "scans", emit=print, use_llm=True, plan_override=None, use_pool=False):
    """Full scan. `emit(stage, text)` receives progress. Returns the final report dict."""
    def say(stage, text):
        emit(stage, text)

    started = time.time()
    brain.reset_usage()
    llm_errors = []
    recruiter = None
    if message:
        say("message", "reading the recruiter's message")
        no_ai = {"repo_urls": [u.rstrip(".,)") for u in brain.URL_RE.findall(message)]}
        recruiter = ai(say, "message", "reading the message", lambda: brain.read_recruiter_message(message),
                       no_ai, llm_errors) if use_llm else no_ai
        if not target and recruiter.get("repo_urls"):
            target = recruiter["repo_urls"][0]
        say("message", f"red flags: {len(recruiter.get('red_flags', []))}, repo: "
                       f"{(f'sample: {Path(target).name}' if os.path.isdir(target) else target) if target else 'none found'}")
    if not target:
        raise ScanError("No repo link found. Paste a github.com, gitlab.com or bitbucket.org link, "
                        "or the recruiter's message that contains one.")
    shown = f"sample: {Path(target).name}" if os.path.isdir(target) else target   # never leak server paths

    tmp = Path(tempfile.mkdtemp(prefix="burner-"))
    if os.path.isdir(target):
        repo = Path(target)
    else:
        say("fetch", f"downloading {target} (nothing is executed here)")
        repo = tmp / Path(target.rstrip("/")).stem
        try:
            clone(target, repo)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
    name = repo.name
    # ---- pre-check (static + provenance) runs alongside planning and VM boot; it never changes the verdict
    precheck_result = start_precheck(repo, None if os.path.isdir(target) else target, message, emit)

    # ---- plan what the candidate does
    plan = plan_override or node_run_scan.default_plan(str(repo))
    readme = next((read(repo / f) for f in ("README.md", "readme.md", "README", "README.txt") if (repo / f).exists()), "")
    screen = None
    if use_llm and not plan_override:
        say("plan", "screening the README for prompt injection")
        screen = ai(say, "plan", "screening the README", lambda: brain.screen_text(readme), None, llm_errors)
        say("plan", "planning what a candidate would run")
        extra = ai(say, "plan", "planning extra steps",
                   lambda: brain.plan_candidate_steps(readme, read(repo / "package.json"), file_tree(repo), plan),
                   [], llm_errors)
        timeshift = [s for s in plan if s.get("kill_before")]
        plan = [s for s in plan if not s.get("kill_before")] + extra + timeshift
    say("plan", " -> ".join(s["name"] for s in plan) or "(nothing runnable found)")

    if not plan:   # don't rent a VM to run nothing, and never call that "clean"
        shutil.rmtree(tmp, ignore_errors=True)
        report = {"verdict": "INCONCLUSIVE", "headline": node_detect.INCONCLUSIVE_NO_STEPS, "findings": [],
                  "stolen": [], "network": [], "dns": [], "steps": [], "bait": [], "stats": {},
                  "target": shown, "recruiter": recruiter, "readme_screen": screen, "vm": None,
                  "total_secs": round(time.time() - started), "llm_usage": brain.usage(),
                  "llm_errors": llm_errors, "campaign": {"similarity": None, "indicators": []},
                  "precheck": precheck_result()}
        report["vultr_bill"] = vultr_bill(report)
        say("done", f"{report['verdict']}: {report['headline']}")
        return report

    iid, created, vm = None, None, {"plan": vm_plan, "region": region, "snapshot": snapshot}
    cost_per_hour = vultr.plan_hourly_cost(vm_plan)
    dest = Path(out_root) / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    try:
        claimed = pool.claim() if (use_pool and not host) else None
        if claimed:
            import datetime
            iid, host = claimed["id"], claimed["main_ip"]
            created = datetime.datetime.fromisoformat(claimed["date_created"]).timestamp()
            vm.update(id=iid, from_pool=True, ready_secs=0, snapshot=None,
                      firewall_group_id=claimed.get("firewall_group_id") or None)
            say("vm", f"took pre-armed Vultr VM {iid[:8]} from the warm pool (used once, then destroyed)")
        elif not host:
            key_id = vultr.ensure_ssh_key(str(KEY) + ".pub")
            say("vm", f"creating a fresh Vultr VM ({vm_plan}, {region})")
            inst = vultr.create_instance(f"burner-{int(started)}", region=region, plan=vm_plan,
                                         sshkey_id=key_id, snapshot_id=snapshot, tags=["burner-scan"])
            iid, created = inst["id"], time.time()
            vm["firewall_group_id"] = inst.get("firewall_group_id") or None
            inst = vultr.wait_ready(iid)
            host = inst["main_ip"]
            vm.update(id=iid, ready_secs=round(time.time() - created))
            say("vm", f"VM {iid[:8]} is up after {time.time() - created:.0f}s")
        wait_ssh(host)
        bundle = tar_dirs([(NODE_DIR, "burner"), (repo, f"input/{name}")])
        p = ssh(host, "rm -rf /scan && mkdir -p /scan && tar -xzf - -C /scan", input_bytes=bundle)
        if p.returncode:
            raise RuntimeError(p.stderr.decode())
        ssh(host, "cat > /scan/plan.json", input_bytes=json.dumps(plan).encode())

        say("setup", "arming the sandbox: gVisor, fake secrets, fake internet")
        p = ssh(host, "bash /scan/burner/setup.sh > /scan/setup.log 2>&1 || (tail -40 /scan/setup.log; exit 1)")
        if p.returncode:
            raise RuntimeError("setup failed: " + p.stdout.decode()[-2000:])

        say("run", "running it like a candidate would")
        proc = subprocess.Popen(["ssh", *SSH_OPTS, f"root@{host}",
                                 f"python3 -u /scan/burner/run_scan.py --repo /scan/input/{name} --out /scan/out "
                                 f"--plan /scan/plan.json 2>&1 | tee /scan/run.log"],
                                stdout=subprocess.PIPE, text=True)
        for line in proc.stdout:
            if line.startswith("[burner]"):
                say("run", line[len("[burner] "):].strip())
        proc.wait()

        dest.mkdir(parents=True)
        p = ssh(host, "cp /scan/run.log /scan/setup.log /scan/out/ 2>/dev/null; tar -czf - -C /scan/out .")
        tarfile.open(fileobj=io.BytesIO(p.stdout), mode="r:gz").extractall(dest, filter="data")
    finally:
        if iid and not keep:
            if not vultr.delete_instance(iid):
                vm["note"] = "The VM was already gone when the scan tried to delete it."
            life = time.time() - created
            vm.update(destroyed=True, lifetime_secs=round(life),
                      cost_usd_max=round((cost_per_hour or 0) * -(-life // 3600), 4),
                      cost_usd_prorated=round((cost_per_hour or 0) * life / 3600, 4))
            say("vm", f"VM destroyed after {life:.0f}s")
        elif iid:
            say("vm", f"VM kept: {iid} {host}")
        shutil.rmtree(tmp, ignore_errors=True)

    rep_path = dest / "report.json"
    report = json.loads(rep_path.read_text())
    try:  # timeline + theft graph for the web UI (report.trace / report.flows); never breaks a scan
        from . import trace
        trace.attach(report, dest)
    except Exception as e:
        report["trace_error"] = str(e)[:200]
    report.update(target=shown, recruiter=recruiter, readme_screen=screen, vm=vm,
                  total_secs=round(time.time() - started), precheck=precheck_result(timeout=2))
    report["campaign"] = campaign.match(report, dest)
    if report["campaign"]["similarity"]:
        say("match", f"behaves like {report['campaign']['campaign']} "
                     f"({len(report['campaign']['indicators'])} public indicators)")
    if report["verdict"] in ("MALICIOUS", "SUSPICIOUS"):
        report["abuse_kit"] = campaign.abuse_kit(report)
    if use_llm:
        say("explain", "writing the explanation")
        report["explanation"] = ai(say, "explain", "writing the explanation", lambda: brain.explain(report, recruiter),
                                   None, llm_errors)
    report["llm_usage"] = brain.usage()
    report["llm_errors"] = llm_errors
    rep_path.write_text(json.dumps(report, indent=1, default=list))
    try:
        say("evidence", "saving the evidence bundle to Vultr Object Storage")
        report["evidence"] = evidence.upload(dest, f"scans/{dest.name}", scan_id=dest.name,
                                             verdict=report.get("verdict"), vm_id=vm.get("id"),
                                             started_at=started, finished_at=time.time())
        report["evidence"]["report_key"] = f"scans/{dest.name}.report.json"
        rep_path.write_text(json.dumps(report, indent=1, default=list))
    except Exception as e:
        report["evidence"] = {"error": str(e)[:200]}
    report["vultr_bill"] = vultr_bill(report)
    rep_path.write_text(json.dumps(report, indent=1, default=list))
    if report["evidence"].get("key"):
        try:   # the final report outlives the VM and the control plane's disk
            evidence.upload_report(report, f"scans/{dest.name}")
        except Exception as e:
            report["evidence"].pop("report_key", None)
            report["evidence"]["report_error"] = str(e)[:200]
            rep_path.write_text(json.dumps(report, indent=1, default=list))
    report["_dir"] = str(dest)
    say("done", f"{report['verdict']}: {report['headline']}")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="local repo folder or git URL")
    ap.add_argument("--message", help="file with the recruiter's message")
    ap.add_argument("--host")
    ap.add_argument("--keep", action="store_true")
    ap.add_argument("--snapshot", default=DEFAULT_SNAPSHOT)
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    r = run(a.target, message=read(a.message) if a.message else None, host=a.host, keep=a.keep,
            snapshot=a.snapshot, use_llm=not a.no_llm,
            emit=lambda stage, text, data=None: print(f"[{time.strftime('%H:%M:%S')}] {stage:8} {text}", flush=True))
    print("\n" + "=" * 70 + f"\n{r['verdict']}\n{r['headline']}\n" + "=" * 70)
    for f in r["findings"]:
        print(f"  [{f['severity']:8}] {f['title']}")
    if r.get("explanation"):
        print("\n" + r["explanation"])
    print(f"\nresults: {r['_dir']}  |  vm: {r['vm']}  |  total {r['total_secs']}s")


if __name__ == "__main__":
    main()
