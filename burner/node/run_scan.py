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
if HERE not in sys.path:
    sys.path.insert(0, HERE)   # bait.py / detect.py live next to this file
IMAGE = "burner-sandbox"
HOME_IN_SANDBOX = "/home/dev"
# Burner's own client programs (MCP client, model loader, VS Code host), mounted read-only into the sandbox
DEVKIT = "/usr/local/lib/devkit"
HARNESS_TAGS = ("BURNER_MCP ", "BURNER_MODEL ", "BURNER_VSCODE ")


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
    """What a candidate does with a take-home, in order; for an MCP server, a model or an extension, what its
    user does."""
    steps = []
    if os.path.isfile(os.path.join(repo, "extension.vsixmanifest")) and \
            os.path.isfile(os.path.join(repo, "extension", "package.json")):
        # an installed VSIX: no npm scripts run on install, the editor just activates it
        return [{"name": "install and open the extension (VS Code)", "cmd": f"node {DEVKIT}/vscode_host.js extension",
                 "timeout": 45, "kind": "vscode",
                 "why": "installing an extension and opening the editor runs its activate()"}]
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
    # Python: a take-home's main.py, an MCP server's server.py, a PoC's exploit.py. A PoC is often a lone script
    # with no requirements file, so a top-level entry file is enough when there is no package.json.
    py_project = any(os.path.exists(os.path.join(repo, f)) for f in ("requirements.txt", "pyproject.toml", "setup.py"))
    py_entry = None
    if py_project or not os.path.exists(pkg):
        for f, why in PY_ENTRIES:
            if os.path.isfile(os.path.join(repo, f)):
                steps.append({"name": f"python {f}", "cmd": f"python3 {f}", "timeout": 45, "why": why})
                py_entry = f
                break
    extra = []
    pj = read_package_json(repo)
    if is_vscode_extension(pj):
        main = shell_safe(pj.get("main"))
        extra.append({"name": "install and open the extension (VS Code)", "kind": "vscode", "timeout": 90,
                      "cmd": f"( test -f '{main}' || test -f '{main}.js' || npm run -s vscode:prepublish || "
                             f"npm run -s compile ) >/dev/null 2>&1; node {DEVKIT}/vscode_host.js .",
                      "why": "installing an extension and opening the editor runs its activate()"})
    if is_model_repo(repo):
        extra.append({"name": "load the model (torch / pickle / trust_remote_code)", "kind": "model", "timeout": 60,
                      "cmd": f"python3 {DEVKIT}/load_model.py .",
                      "why": "loading pickle weights or a model's custom code runs whatever the file says"})
    server = mcp_server_command(repo, pj, py_entry)
    if server:
        extra.append({"name": "connect as an AI app (MCP: list and call every tool 4x)", "kind": "mcp", "timeout": 75,
                      "kill_before": True, "cmd": f"python3 {DEVKIT}/mcp_client.py --rounds 4 -- {server}",
                      "why": "some MCP servers only act when a tool is called, or after a few calls"})
    later = [s for s in steps if "(+45 days)" in s["name"]]
    return [s for s in steps if s not in later] + extra + later


def shell_safe(s):
    return re.sub(r"[^\w./@-]", "", s or "")


def read_package_json(repo):
    try:
        d = json.load(open(os.path.join(repo, "package.json"), encoding="utf-8", errors="replace"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def is_vscode_extension(pj):
    return isinstance(pj.get("engines"), dict) and "vscode" in pj["engines"] and bool(pj.get("main"))


MODEL_WEIGHTS = (".bin", ".pt", ".pth", ".ckpt", ".pkl", ".pickle", ".joblib")


def is_model_repo(repo):
    """A Hugging Face style model: pickle weights next to a config.json (or a checkpoint/pickle file on its own),
    or a config.json whose auto_map names custom code."""
    try:
        top = os.listdir(repo)
    except OSError:
        return False
    weights = [f for f in top if f.endswith(MODEL_WEIGHTS) and not f.startswith(".")]
    if weights and ("config.json" in top or any(not f.endswith(".bin") for f in weights)
                    or any(f.startswith("pytorch_model") for f in weights)):
        return True
    if "config.json" in top:
        try:
            return bool((json.load(open(os.path.join(repo, "config.json"))) or {}).get("auto_map"))
        except (OSError, ValueError, AttributeError):
            return False
    return False


MCP_DEP = re.compile(r"(?im)^\s*[\"']?(?:mcp|fastmcp|mcp-server[\w-]*)\b")
MCP_CODE = re.compile(r"@modelcontextprotocol/sdk|FastMCP\(|McpServer\(|from mcp\.server|\bmcp\.server\.")


def mcp_server_command(repo, pj, py_entry):
    """The command that starts this repo as a stdio MCP server, or None if it doesn't look like one."""
    deps = {**(pj.get("dependencies") or {}), **(pj.get("devDependencies") or {})} if pj else {}
    signal = any(k.startswith("@modelcontextprotocol/") or k in ("fastmcp", "mcp-framework") for k in deps)
    for f in ("requirements.txt", "pyproject.toml"):
        try:
            signal = signal or bool(MCP_DEP.search(open(os.path.join(repo, f), errors="replace").read()))
        except OSError:
            pass
    for f in ("README.md", "readme.md", "README"):
        try:
            signal = signal or bool(re.search(r"(?i)\bMCP server\b|model context protocol",
                                             open(os.path.join(repo, f), errors="replace").read(20000)))
        except OSError:
            pass
    if not signal:
        for f in sorted(os.listdir(repo))[:200]:
            p = os.path.join(repo, f)
            if f.endswith((".js", ".mjs", ".ts", ".py")) and os.path.isfile(p) and os.path.getsize(p) < 300_000:
                if MCP_CODE.search(open(p, errors="replace").read()):
                    signal = True
                    break
    if not signal:
        return None
    if pj:
        scripts = pj.get("scripts") if isinstance(pj.get("scripts"), dict) else {}
        if "start" in scripts:
            return "npm run -s start"
        b = pj.get("bin")
        b = b if isinstance(b, str) else (next(iter(b.values()), None) if isinstance(b, dict) and b else None)
        main = b or pj.get("main")
        if main:
            return f"node {shell_safe(main)}"
    if py_entry:
        return f"python3 {py_entry}"
    return None


PY_ENTRIES = [("main.py", "the take-home asks you to run it"), ("app.py", "the take-home asks you to run it"),
              ("manage.py", "the take-home asks you to run it"),
              ("server.py", "an MCP server or API is started with its server script"),
              ("exploit.py", "a proof-of-concept is run to check the vulnerability"),
              ("poc.py", "a proof-of-concept is run to check the vulnerability"),
              ("run.py", "the README's usual entry point"), ("cli.py", "the tool's command-line entry point")]


NPM_REGISTRY = "https://registry.npmjs.org/"
PYPI_INDEX = "https://pypi.org/simple/"
# Project files that point npm / yarn / pip at another registry (a lookalike package server is how a repo
# swaps in a different "lodash" than the one on npmjs.org).
REGISTRY_FILES = (".npmrc", ".yarnrc", ".yarnrc.yml", "pip.conf", "pip.ini")
INDEX_FLAGS = ("--index-url", "--extra-index-url", "--trusted-host", "--find-links", "-i", "-f")
SKIP_DIRS = {".git", "node_modules", ".burner_site"}


def harden_fetch(project, stash):
    """Take registry overrides out of the project before the download. Originals go to STASH (outside the project)
    and come back afterwards, so the detonation sees the repo exactly as the candidate would.

    -> (removed, restore): removed = [".npmrc", "requirements.txt: --extra-index-url https://..."]."""
    removed, moved = [], []
    for root, dirs, files in os.walk(project):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for f in files:
            path = os.path.join(root, f)
            rel = os.path.relpath(path, project).replace(os.sep, "/")
            if f in REGISTRY_FILES:
                keep = os.path.join(stash, str(len(moved)))
                os.makedirs(stash, exist_ok=True)
                shutil.move(path, keep)
                moved.append((keep, path, None))
                removed.append(rel)
            elif re.fullmatch(r"requirements[\w.-]*\.txt", f) and not os.path.islink(path):
                text = open(path, encoding="utf-8", errors="replace").read()
                lines = text.splitlines(keepends=True)
                kept = [ln for ln in lines if not ln.strip().startswith(INDEX_FLAGS)]
                if len(kept) != len(lines):
                    removed += [f"{rel}: {ln.strip()[:120]}" for ln in lines if ln.strip().startswith(INDEX_FLAGS)]
                    moved.append((None, path, text))
                    open(path, "w", encoding="utf-8").write("".join(kept))

    def restore():
        for keep, path, text in moved:
            if keep:
                shutil.move(keep, path)
            else:
                open(path, "w", encoding="utf-8").write(text)
    return removed, restore


def fetch_dependencies(project, out, stash=None):
    """Real internet, but no secrets mounted, no scripts allowed to run, and only the public registries."""
    removed, restore = harden_fetch(project, stash or os.path.join(out, "_work", "fetch_stash"))
    log = [{"cmd": "fetch hardening", "removed": removed}]
    try:
        if os.path.exists(os.path.join(project, "package.json")):
            p = sh(["docker", "run", "--rm", "--runtime=runsc", "-u", "1000", "-v", f"{project}:/w", "-w", "/w",
                    "-e", f"npm_config_registry={NPM_REGISTRY}", "--memory", "2g", IMAGE,
                    "npm", "install", "--ignore-scripts", "--no-audit", "--no-fund", f"--registry={NPM_REGISTRY}"],
                   timeout=300)
            log.append({"cmd": "npm install --ignore-scripts", "rc": p.returncode, "tail": (p.stdout + p.stderr)[-1500:]})
            if p.returncode:   # npm 10 can crash on peer-dependency trees ("reading 'edgesOut'"): retry the npm 6 way
                p = sh(["docker", "run", "--rm", "--runtime=runsc", "-u", "1000", "-v", f"{project}:/w", "-w", "/w",
                        "-e", f"npm_config_registry={NPM_REGISTRY}", "--memory", "2g", IMAGE,
                        "npm", "install", "--ignore-scripts", "--legacy-peer-deps", "--no-audit", "--no-fund",
                        f"--registry={NPM_REGISTRY}"], timeout=300)
                log.append({"cmd": "npm install --ignore-scripts --legacy-peer-deps", "rc": p.returncode,
                            "tail": (p.stdout + p.stderr)[-1500:]})
        req = os.path.join(project, "requirements.txt")
        if os.path.exists(req):
            p = sh(["docker", "run", "--rm", "--runtime=runsc", "-u", "1000", "-v", f"{project}:/w", "-w", "/w",
                    "-e", "PIP_CONFIG_FILE=/dev/null", IMAGE, "pip", "install", "--only-binary=:all:",
                    "--break-system-packages", "--no-warn-script-location", "--index-url", PYPI_INDEX,
                    "-t", "/w/.burner_site", "-r", "requirements.txt"], timeout=300)
            log.append({"cmd": "pip install (wheels only)", "rc": p.returncode, "tail": (p.stdout + p.stderr)[-1500:]})
    finally:
        restore()
    json.dump(log, open(os.path.join(out, "fetch.json"), "w"), indent=1)
    return log


def setup_env(project, home, out):
    """.env from .env.example (bait.fill_env); its bait values are added to tokens.json. Writes env_setup.json."""
    import bait
    rel = os.path.relpath(project, home).replace(os.sep, "/")
    env_setup, toks = bait.fill_env(project, rel)
    if toks:
        path = os.path.join(out, "tokens.json")
        tokens = json.load(open(path))
        json.dump(tokens + toks, open(path, "w"), indent=1)
    json.dump(env_setup, open(os.path.join(out, "env_setup.json"), "w"), indent=1)
    if env_setup and hasattr(os, "chown"):
        sh(["chown", "1000:1000", os.path.join(project, ".env")])
    return env_setup


def step_result(step, rc, so, se, t0, t1, tokens):
    """One steps.json entry: the plan step echoed back (why/source), exit code, real seconds, masked tail."""
    import detect
    res = {**step, "source": step.get("source", "default"), "why": step.get("why", ""), "rc": rc,
           "t0": round(t0, 3), "t1": round(t1, 3), "secs": round(t1 - t0, 2), "stdout": so[-3000:], "stderr": se[-3000:]}
    res["tail"] = detect.make_tail({"stdout": so, "stderr": se}, tokens)
    return res


def harness_output(stdout):
    """{"mcp"|"model"|"vscode": summary} from the BURNER_* line Burner's own client printed."""
    out = {}
    for ln in (stdout or "").splitlines():
        for tag in HARNESS_TAGS:
            if ln.startswith(tag):
                try:
                    out[tag.strip().split("_")[1].lower()] = json.loads(ln[len(tag):])
                except ValueError:
                    pass
    return out


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

    ident = os.path.join(out, "identity.json")   # per-scan hostname written by bait.py (FINGERPRINT rule)
    hostname = json.load(open(ident)).get("hostname", "dev-laptop") if os.path.exists(ident) else "dev-laptop"

    plan = json.load(open(a.plan)) if a.plan else default_plan(project)
    json.dump(plan, open(os.path.join(out, "plan.json"), "w"), indent=1)
    mark("plan", steps=[s["name"] for s in plan])

    mark("fetch dependencies (scripts disabled, no secrets)")
    fetch_dependencies(project, out, os.path.join(work, "fetch_stash"))

    env_setup = setup_env(project, home, out)
    if env_setup:
        mark("wrote .env from " + env_setup["from"], filled=env_setup["filled"])
    tokens = json.load(open(os.path.join(out, "tokens.json")))

    ensure_network_rules()
    resolv = os.path.join(work, "resolv.conf")
    open(resolv, "w").write("nameserver 10.77.0.1\n")
    fakenet = subprocess.Popen([sys.executable, f"{HERE}/fakenet.py", "--ca", "/opt/burner", "--out", out],
                               stdout=open(os.path.join(out, "fakenet.log"), "w"), stderr=subprocess.STDOUT)
    time.sleep(1)

    mark("start sandbox (gVisor, fake internet, syscall trace)")
    cid = sh(["docker", "run", "-d", "--runtime=runsc-trace", "--network", "burnernet",
              "--hostname", hostname, "-v", f"{home}:{HOME_IN_SANDBOX}", "-v", f"{resolv}:/etc/resolv.conf:ro",
              # pids-limit leaves headroom for gVisor's own sentry threads; nproc caps the repo's processes
              # (a fork bomb stops at ~400 instead of killing the whole sandbox)
              "--memory", "3g", "--cpus", "1.5", "--pids-limit", "4096", "--ulimit", "nproc=400:400",
              "--cap-drop", "ALL",
              "--security-opt", "no-new-privileges", "-u", "1000",
              "-v", f"{os.path.join(HERE, 'harness')}:{DEVKIT}:ro", IMAGE, "sleep", "infinity"],
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
            res = step_result(step, rc, so, se, t0, time.time(), tokens)
            harness = harness_output(so)
            if harness:
                res["harness"] = harness
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
