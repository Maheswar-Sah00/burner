#!/usr/bin/env python3
"""Detonate one repo on this (throwaway) VM.

  run_scan.py --repo /scan/input/repo --out /scan/out [--plan plan.json]

Phases
  1. fetch     : download dependencies WITHOUT running any of their scripts
                 (gVisor, real internet, no secrets present)
  2. detonate  : behave like a candidate inside gVisor, home full of fake
                 secrets, network = fake internet only, every syscall logged
  3. judge     : detect.py turns observations into a rule-based verdict
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
IMAGE = "burner-sandbox"
HOME_IN_SANDBOX = "/home/dev"


def sh(cmd, timeout=None, check=False):
    p = subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, timeout=timeout)
    if check and p.returncode:
        raise RuntimeError(f"{cmd}\n{p.stdout}\n{p.stderr}")
    return p


def strip_jsonc(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r'(^|[^:"])//[^\n]*', r"\1", text)
    return re.sub(r",(\s*[}\]])", r"\1", text)


def task_command(task, tasks_file=None):
    """The shell command VS Code would run for a task on a Linux/macOS machine.

    VS Code lets the per-OS keys ("linux", "osx", "windows") override the top-level
    command/args, both on the task and file-wide; lures often hide the command there.
    """
    merged = {}
    for layer in ((tasks_file or {}).get("linux"), task, task.get("linux") or (None if task.get("command") else task.get("osx"))):
        if isinstance(layer, dict):
            merged.update({k: layer[k] for k in ("command", "args", "script", "type") if k in layer})
    if merged.get("type") == "npm" and merged.get("script") and not merged.get("command"):
        return f"npm run {merged['script']}"
    cmd = merged.get("command") or ""
    if isinstance(cmd, list):
        cmd = " ".join(cmd)
    if isinstance(cmd, dict):
        cmd = cmd.get("value", "")
    args = [a if isinstance(a, str) else (a or {}).get("value", "") for a in merged.get("args", []) or []]
    return " ".join([cmd] + args).strip()


def default_plan(repo):
    """What a candidate does with a take-home, in order."""
    steps = []
    tasks = os.path.join(repo, ".vscode", "tasks.json")
    if os.path.exists(tasks):
        try:
            data = json.loads(strip_jsonc(open(tasks, encoding="utf-8", errors="replace").read()))
            for t in data.get("tasks", []):
                if (t.get("runOptions") or {}).get("runOn") == "folderOpen":
                    cmd = task_command(t, data)
                    steps.append({"name": "open folder in VS Code (auto-run task)", "cmd": cmd or "true", "timeout": 40,
                                  "why": f"task '{t.get('label', '?')}' runs automatically when the folder opens"})
        except Exception as e:
            steps.append({"name": "open folder in VS Code", "cmd": "true", "timeout": 5,
                          "why": f"tasks.json present but unparsable ({e})"})
    pkg = os.path.join(repo, "package.json")
    if os.path.exists(pkg):
        try:
            scripts = json.load(open(pkg, encoding="utf-8", errors="replace")).get("scripts", {})
            scripts = scripts if isinstance(scripts, dict) else {}
        except (ValueError, AttributeError):   # malformed package.json: npm will still try to run it
            scripts = {"start": "?"}
        steps.append({"name": "npm install", "timeout": 120,
                      "cmd": "npm rebuild --foreground-scripts; for s in preinstall install postinstall prepare; "
                             "do npm run --if-present $s; done",
                      "why": "install runs lifecycle scripts of the project and its dependencies"})
        start = "start" if "start" in scripts else ("dev" if "dev" in scripts else None)
        if start:
            steps.append({"name": f"npm run {start}", "cmd": f"npm run {start}", "timeout": 45,
                          "why": "the take-home asks you to start the app"})
        if "test" in scripts:
            steps.append({"name": "npm test", "cmd": "npm test", "timeout": 45, "why": "candidates run the tests"})
        if start:
            steps.append({"name": f"npm run {start} (+45 days)", "cmd": f"faketime -f +45d npm run {start}",
                          "timeout": 30, "kill_before": True,
                          "why": "some payloads wait days before acting"})
    req = os.path.join(repo, "requirements.txt")
    if os.path.exists(req):
        for f in ("main.py", "app.py", "manage.py"):
            if os.path.exists(os.path.join(repo, f)):
                steps.append({"name": f"python {f}", "cmd": f"python3 {f}", "timeout": 45,
                              "why": "the take-home asks you to run it"})
                break
    return steps


def fetch_dependencies(project, out):
    """Real internet, but no secrets mounted and no scripts allowed to run."""
    log = []
    if os.path.exists(os.path.join(project, "package.json")):
        p = sh(["docker", "run", "--rm", "--runtime=runsc", "-u", "1000", "-v", f"{project}:/w", "-w", "/w",
                "--memory", "2g", IMAGE, "npm", "install", "--ignore-scripts", "--no-audit", "--no-fund"],
               timeout=300)
        log.append({"cmd": "npm install --ignore-scripts", "rc": p.returncode, "tail": (p.stdout + p.stderr)[-1500:]})
    req = os.path.join(project, "requirements.txt")
    if os.path.exists(req):
        p = sh(["docker", "run", "--rm", "--runtime=runsc", "-u", "1000", "-v", f"{project}:/w", "-w", "/w",
                IMAGE, "pip", "install", "--only-binary=:all:", "--break-system-packages", "--no-warn-script-location",
                "-t", "/w/.burner_site", "-r", "requirements.txt"], timeout=300)
        log.append({"cmd": "pip install (wheels only)", "rc": p.returncode, "tail": (p.stdout + p.stderr)[-1500:]})
    json.dump(log, open(os.path.join(out, "fetch.json"), "w"), indent=1)


DEATH_MARKERS = ("is not running", "WaitPID", "containerManager", "urpc method", "No such container")


def sandbox_death(cid, rc, stderr):
    """Why the sandbox died during the last step (resource bomb, crash), or None if it is alive."""
    state = sh(["docker", "inspect", "-f", "{{.State.Running}} {{.State.OOMKilled}} {{.State.ExitCode}}", cid])
    parts = state.stdout.split()
    if state.returncode or not parts or parts[0] != "true" or (len(parts) > 1 and parts[1] == "true"):
        why = "out of memory" if len(parts) > 1 and parts[1] == "true" else "exhausted memory or processes"
        return f"sandbox stopped ({why}; exit {parts[2] if len(parts) > 2 else '?'})"
    marker = next((m for m in DEATH_MARKERS if m in (stderr or "")), None)
    if marker or rc == "hung":
        return f"sandbox stopped responding ({marker or 'docker exec hung'})"
    return None


def ensure_network_rules():
    sh(["bash", "-c", f"source <(sed -n '/^apply_rules()/,/^}}/p' {HERE}/setup.sh); apply_rules"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--plan")
    a = ap.parse_args()

    out = a.out
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    work = os.path.join(out, "_work")
    home = os.path.join(work, "home")
    os.makedirs(home)
    timeline = []

    def mark(event, **kw):
        timeline.append({"t": round(time.time(), 3), "event": event, **kw})
        print(f"[burner] {event} {kw if kw else ''}", flush=True)

    mark("plant fake secrets")
    sh([sys.executable, f"{HERE}/bait.py", home, f"{out}/tokens.json"], check=True)

    name = os.path.basename(os.path.normpath(a.repo)) or "project"
    project = os.path.join(home, "projects", name)
    shutil.copytree(a.repo, project, symlinks=True)
    sh(["chown", "-R", "1000:1000", home])

    plan = json.load(open(a.plan)) if a.plan else default_plan(project)
    json.dump(plan, open(os.path.join(out, "plan.json"), "w"), indent=1)
    mark("plan", steps=[s["name"] for s in plan])

    mark("fetch dependencies (scripts disabled, no secrets)")
    fetch_dependencies(project, out)

    ensure_network_rules()
    resolv = os.path.join(work, "resolv.conf")
    open(resolv, "w").write("nameserver 10.77.0.1\n")
    fakenet = subprocess.Popen([sys.executable, f"{HERE}/fakenet.py", "--ca", "/opt/burner", "--out", out],
                               stdout=open(os.path.join(out, "fakenet.log"), "w"), stderr=subprocess.STDOUT)
    time.sleep(1)

    mark("start sandbox (gVisor, fake internet, syscall trace)")
    cid = sh(["docker", "run", "-d", "--runtime=runsc-trace", "--network", "burnernet",
              "--hostname", "dev-laptop", "-v", f"{home}:{HOME_IN_SANDBOX}", "-v", f"{resolv}:/etc/resolv.conf:ro",
              # pids-limit leaves headroom for gVisor's own sentry threads; nproc caps the repo's processes
              # (a fork bomb stops at ~400 instead of killing the whole sandbox)
              "--memory", "3g", "--cpus", "1.5", "--pids-limit", "4096", "--ulimit", "nproc=400:400",
              "--cap-drop", "ALL",
              "--security-opt", "no-new-privileges", "-u", "1000", IMAGE, "sleep", "infinity"],
             check=True).stdout.strip()
    open(os.path.join(out, "container_id"), "w").write(cid)
    workdir = f"{HOME_IN_SANDBOX}/projects/{name}"
    env = ["-e", f"HOME={HOME_IN_SANDBOX}", "-e", "USER=dev"]
    if os.path.exists(os.path.join(project, ".burner_site")):
        env += ["-e", f"PYTHONPATH={workdir}/.burner_site"]

    results = []
    try:
        for i, step in enumerate(plan):
            if step.get("kill_before"):
                sh(["docker", "exec", cid, "pkill", "-KILL", "-u", "1000", "-f", "node|npm|python"])
                time.sleep(2)
            mark("step", n=i + 1, name=step["name"], cmd=step["cmd"])
            t0 = time.time()
            try:
                p = sh(["docker", "exec", "-u", "1000", "-w", workdir, *env, cid,
                        "timeout", "-s", "KILL", str(step.get("timeout", 45)), "bash", "-lc", step["cmd"]],
                       timeout=step.get("timeout", 45) + 30)
                rc, so, se = p.returncode, p.stdout, p.stderr
            except subprocess.TimeoutExpired as e:   # docker exec itself hung (sandbox wedged)
                rc, so, se = "hung", str(e.stdout or ""), "docker exec did not return"
            res = {**step, "rc": rc, "t0": round(t0, 3), "t1": round(time.time(), 3),
                   "stdout": so[-3000:], "stderr": se[-3000:]}
            reason = sandbox_death(cid, rc, se)
            if reason:
                res["sandbox_died"] = {"step": step["name"], "reason": reason}
                results.append(res)
                mark("sandbox died", step=step["name"], reason=reason)
                break
            results.append(res)
        else:
            mark("grace period (background payloads)")
            time.sleep(8)
    finally:
        sh(["docker", "rm", "-f", cid])
        fakenet.terminate()
        mark("sandbox destroyed")

    json.dump(results, open(os.path.join(out, "steps.json"), "w"), indent=1)
    json.dump(timeline, open(os.path.join(out, "timeline.json"), "w"), indent=1)

    logdir = f"/var/log/runsc/{cid}"
    with open(os.path.join(out, "syscalls.log"), "w") as dst:
        for root, _, files in os.walk(logdir):
            for f in sorted(files):
                with open(os.path.join(root, f), errors="replace") as src:
                    for line in src:
                        if "strace.go" in line:
                            dst.write(line)

    sh([sys.executable, f"{HERE}/detect.py", out], check=True)
    shutil.rmtree(work, ignore_errors=True)
    print(open(os.path.join(out, "report.json")).read())


if __name__ == "__main__":
    main()
