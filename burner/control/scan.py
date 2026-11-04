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
import time
from pathlib import Path

from . import brain, campaign, evidence, pool, vultr

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


def run(target=None, message=None, host=None, keep=False, snapshot=DEFAULT_SNAPSHOT, region="blr",
        vm_plan="vc2-2c-4gb", out_root=ROOT / "scans", emit=print, use_llm=True, plan_override=None, use_pool=False):
    """Full scan. `emit(stage, text)` receives progress. Returns the final report dict."""
    def say(stage, text):
        emit(stage, text)

    started = time.time()
    recruiter = None
    if message:
        say("message", "reading the recruiter's message")
        recruiter = brain.read_recruiter_message(message) if use_llm else {"repo_urls": brain.URL_RE.findall(message)}
        if not target and recruiter.get("repo_urls"):
            target = recruiter["repo_urls"][0]
        say("message", f"red flags: {len(recruiter.get('red_flags', []))}, repo: {target}")
    if not target:
        raise ValueError("no repo given and none found in the message")

    tmp = Path(tempfile.mkdtemp(prefix="burner-"))
    if os.path.isdir(target):
        repo = Path(target)
    else:
        say("fetch", f"downloading {target} (nothing is executed here)")
        repo = tmp / Path(target.rstrip("/")).stem
        subprocess.run(["git", "clone", "--depth", "1", "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false",
                        target, str(repo)], check=True, capture_output=True)
    name = repo.name

    # ---- plan what the candidate does
    plan = plan_override or node_run_scan.default_plan(str(repo))
    readme = next((read(repo / f) for f in ("README.md", "readme.md", "README", "README.txt") if (repo / f).exists()), "")
    screen = None
    if use_llm and not plan_override:
        say("plan", "screening the README for prompt injection")
        screen = brain.screen_text(readme)
        say("plan", "planning what a candidate would run")
        extra = brain.plan_candidate_steps(readme, read(repo / "package.json"), file_tree(repo), plan)
        timeshift = [s for s in plan if s.get("kill_before")]
        plan = [s for s in plan if not s.get("kill_before")] + extra + timeshift
    say("plan", " -> ".join(s["name"] for s in plan) or "(nothing runnable found)")

    iid, created, vm = None, None, {"plan": vm_plan, "region": region, "snapshot": snapshot}
    cost_per_hour = vultr.plan_hourly_cost(vm_plan)
    dest = Path(out_root) / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    try:
        claimed = pool.claim() if (use_pool and not host) else None
        if claimed:
            import datetime
            iid, host = claimed["id"], claimed["main_ip"]
            created = datetime.datetime.fromisoformat(claimed["date_created"]).timestamp()
            vm.update(id=iid, from_pool=True, ready_secs=0, snapshot=None)
            say("vm", f"took pre-armed Vultr VM {iid[:8]} from the warm pool (used once, then destroyed)")
        elif not host:
            key_id = vultr.ensure_ssh_key(str(KEY) + ".pub")
            say("vm", f"creating a fresh Vultr VM ({vm_plan}, {region})")
            inst = vultr.create_instance(f"burner-{int(started)}", region=region, plan=vm_plan,
                                         sshkey_id=key_id, snapshot_id=snapshot, tags=["burner-scan"])
            iid, created = inst["id"], time.time()
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
            vultr.delete_instance(iid)
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
    report.update(target=target, recruiter=recruiter, readme_screen=screen, vm=vm,
                  total_secs=round(time.time() - started))
    report["campaign"] = campaign.match(report, dest)
    if report["campaign"]["similarity"]:
        say("match", f"behaves like {report['campaign']['campaign']} "
                     f"({len(report['campaign']['indicators'])} public indicators)")
    if report["verdict"] != "NO MALICIOUS BEHAVIOUR OBSERVED":
        report["abuse_kit"] = campaign.abuse_kit(report)
    if use_llm:
        say("explain", "writing the explanation")
        try:
            report["explanation"] = brain.explain(report, recruiter)
        except Exception as e:  # explanation is optional; the verdict stands without it
            report["explanation"] = None
            report["explanation_error"] = str(e)[:200]
    report["llm_usage"] = dict(brain.USAGE)
    rep_path.write_text(json.dumps(report, indent=1, default=list))
    try:
        say("evidence", "saving the evidence bundle to Vultr Object Storage")
        key, url, size = evidence.upload(dest, f"scans/{dest.name}")
        report["evidence"] = {"bucket": evidence.BUCKET, "key": key, "url": url, "bytes": size}
        rep_path.write_text(json.dumps(report, indent=1, default=list))
    except Exception as e:
        report["evidence"] = {"error": str(e)[:200]}
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
            emit=lambda stage, text: print(f"[{time.strftime('%H:%M:%S')}] {stage:8} {text}", flush=True))
    print("\n" + "=" * 70 + f"\n{r['verdict']}\n{r['headline']}\n" + "=" * 70)
    for f in r["findings"]:
        print(f"  [{f['severity']:8}] {f['title']}")
    if r.get("explanation"):
        print("\n" + r["explanation"])
    print(f"\nresults: {r['_dir']}  |  vm: {r['vm']}  |  total {r['total_secs']}s")


if __name__ == "__main__":
    main()
