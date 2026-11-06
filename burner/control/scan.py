"""Burner control plane: one throwaway Vultr VM per scan.

  python -m burner.control.scan [PATH_OR_GIT_URL] [--message recruiter.txt] [--host IP] [--keep] [--snapshot ID]
                                [--run "node server.js"]

  --message FILE  the recruiter's message; the repo link is taken from it if no target is given
  --host IP       reuse an existing burner VM (development)
  --keep          don't destroy the VM afterwards
"""
import argparse
import gzip
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
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


GIT_ENV = {"GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true", "GCM_INTERACTIVE": "never"}


def resolve_branch(url, wanted):
    """The real branch/tag a '/tree/<x>' link points at. GitHub puts files after the branch name
    (/tree/main/src/app), so pick the longest remote branch or tag that `wanted` starts with."""
    try:
        p = subprocess.run(["git", "-c", "credential.helper=", "ls-remote", "--heads", "--tags", "--", url],
                           capture_output=True, text=True, timeout=30, env={**os.environ, **GIT_ENV})
    except subprocess.TimeoutExpired:
        return wanted
    refs = {re.sub(r"^refs/(heads|tags)/", "", line.split("\t", 1)[1]).removesuffix("^{}")
            for line in p.stdout.splitlines() if "\t" in line}
    if not refs:
        return wanted                      # unreachable or private: let the clone say so
    hits = [r for r in refs if wanted == r or wanted.startswith(r + "/")]
    if not hits:
        raise ScanError(f"The link names branch '{wanted[:80]}', but that repo has no such branch or tag. "
                        "Check the link the recruiter sent.")
    return max(hits, key=len)


def clone(url, dest):
    """Shallow clone with no hooks, no symlinks, no credential prompt; bounded in time and size.
    A '/tree/<branch>' link clones that branch (the recruiter's branch is what the candidate would run).
    Returns {"repo", "branch", "commit"}: the exact code that was scanned."""
    base, wanted = brain.split_branch(url)
    branch = resolve_branch(base, wanted) if wanted else None
    env = {**os.environ, **GIT_ENV}
    try:
        p = subprocess.run(["git", "clone", "--depth", "1", "--single-branch", "--no-tags",
                            "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false", "-c", "credential.helper=",
                            *([f"--branch={branch}"] if branch else []), "--", base, str(dest)],
                           capture_output=True, text=True, timeout=CLONE_TIMEOUT, env=env)
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
    git = lambda *a: subprocess.run(["git", "-C", str(dest), *a], capture_output=True, text=True, timeout=20,
                                    env=env).stdout.strip()
    return {"repo": base, "branch": branch or git("rev-parse", "--abbrev-ref", "HEAD") or None,
            "branch_from_link": bool(branch), "commit": git("rev-parse", "HEAD") or None,
            "committed_at": git("log", "-1", "--format=%cI") or None, "cloned_at": int(time.time())}


MAX_MODEL_MB = int(os.environ.get("BURNER_MAX_MODEL_MB", "400"))
MAX_VSIX_MB = int(os.environ.get("BURNER_MAX_VSIX_MB", "120"))
UA = {"User-Agent": "burner-scanner/1.0"}
HF_KEEP = (".json", ".py", ".txt", ".md", ".yaml", ".yml", ".cfg", ".bin", ".pt", ".pth", ".ckpt", ".pkl", ".pickle",
           ".joblib", ".model", ".safetensors")


def _get(url, limit_mb, timeout=60):
    """GET with a size cap; nothing downloaded is ever executed on this machine."""
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit_mb * 2**20 + 1)
    if len(data) > limit_mb * 2**20:
        raise ScanError(f"That download is over {limit_mb} MB, so Burner stopped.")
    return data


def fetch_hf_model(url, dest):
    """A Hugging Face model repo, file by file through the public API (git would only give LFS pointers).
    Code, configs and pickle weights are fetched; safetensors are listed but not downloaded (they can't carry code)."""
    repo_id = url.split("huggingface.co/", 1)[1].strip("/")
    try:
        info = json.loads(_get(f"https://huggingface.co/api/models/{repo_id}?blobs=true", 20, timeout=20))
    except urllib.error.HTTPError as e:
        raise ScanError("Couldn't find that model on Hugging Face: it's private, gated, deleted or the link is wrong. "
                        "Burner can only scan public models.") from e
    if info.get("gated") or info.get("private"):
        raise ScanError("That model is gated or private, so Burner can't download it.")
    sha = info.get("sha") or "main"
    dest.mkdir(parents=True, exist_ok=True)
    got, skipped, total = [], [], 0
    for sib in info.get("siblings") or []:
        name = sib.get("rfilename") or ""
        size = (sib.get("size") or (sib.get("lfs") or {}).get("size") or 0) / 2**20
        if not name.lower().endswith(HF_KEEP) or ".." in name.split("/") or name.startswith("/"):
            continue
        if name.endswith(".safetensors"):
            skipped.append({"file": name, "why": "safetensors can't carry code"})
            continue
        if size > MAX_MODEL_MB or total + size > MAX_MODEL_MB:
            skipped.append({"file": name, "why": f"{size:.0f} MB: over Burner's {MAX_MODEL_MB} MB limit"})
            continue
        data = _get(f"https://huggingface.co/{repo_id}/resolve/{sha}/{urllib.parse.quote(name)}", MAX_MODEL_MB, 300)
        p = dest / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        total += len(data) / 2**20
        got.append(name)
    if not got:
        raise ScanError("That model has no files Burner can load (only safetensors, or everything is too big).")
    return {"repo": url, "kind": "hf-model", "commit": sha, "branch": None, "files": len(got), "skipped": skipped[:20],
            "committed_at": info.get("lastModified"), "cloned_at": int(time.time())}


def fetch_vsix(url, dest):
    """A VS Code extension package (.vsix) from Open VSX or the Marketplace, unpacked (no install scripts run)."""
    if "open-vsx.org/" in url:
        ns, name = url.rstrip("/").split("/extension/", 1)[1].split("/")[:2]
        try:
            meta = json.loads(_get(f"https://open-vsx.org/api/{ns}/{name}", 5, timeout=20))
        except urllib.error.HTTPError as e:
            raise ScanError("Couldn't find that extension on Open VSX.") from e
        dl, version = (meta.get("files") or {}).get("download"), meta.get("version")
    else:
        pub, name = url.split("itemName=", 1)[1].split("&")[0].split(".", 1)
        dl = (f"https://marketplace.visualstudio.com/_apis/public/gallery/publishers/{pub}/vsextensions/{name}"
              "/latest/vspackage")
        version = "latest"
    if not dl:
        raise ScanError("That extension has no downloadable package.")
    try:
        data = _get(dl, MAX_VSIX_MB, timeout=120)
    except urllib.error.HTTPError as e:
        raise ScanError("Couldn't download that extension (the store returned an error).") from e
    if data[:2] == b"\x1f\x8b":      # the Marketplace may send it gzip-wrapped
        data = gzip.decompress(data)
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as e:
        raise ScanError("That download isn't a valid .vsix package.") from e
    total = 0
    for zi in z.infolist():
        parts = zi.filename.replace("\\", "/").split("/")
        if zi.filename.startswith("/") or ".." in parts or zi.is_dir():
            continue
        total += zi.file_size
        if total > 4 * MAX_VSIX_MB * 2**20:
            raise ScanError("That extension unpacks to more than Burner allows.")
        p = dest.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(z.read(zi))
    if not (dest / "extension" / "package.json").exists():
        raise ScanError("That package has no extension/package.json, so it isn't a VS Code extension.")
    pj = json.loads((dest / "extension" / "package.json").read_text(encoding="utf-8", errors="replace"))
    return {"repo": url, "kind": "vsix", "commit": None, "branch": None, "version": pj.get("version") or version,
            "extension_id": f"{pj.get('publisher')}.{pj.get('name')}", "cloned_at": int(time.time())}


def fetch_source(url, dest):
    """Download what the link points to (never executed here): a git repo, a Hugging Face model or Space, a VSIX."""
    kind = brain.link_kind(url)
    if kind == "hf-model":
        return fetch_hf_model(url, dest)
    if kind == "vsix":
        return fetch_vsix(url, dest)
    src = clone(url, dest)
    if kind == "hf-space":
        src["kind"] = "hf-space"
    return src


def source_name(url):
    """A folder name for the downloaded thing (the repo, model or extension name)."""
    base = brain.split_branch(url)[0].rstrip("/")
    if "itemName=" in base:
        base = base.split("itemName=", 1)[1].split("&")[0]
    return re.sub(r"[^\w.-]", "-", Path(base).name)[:80] or "project"


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


def pool_idle_secs(claimed, claimed_at):
    """How long a warm-pool VM existed (arming + armed standby) before this scan claimed it, or None."""
    import datetime
    try:
        return max(0.0, claimed_at - datetime.datetime.fromisoformat(claimed["date_created"]).timestamp())
    except (KeyError, TypeError, ValueError):
        return None


def vm_cost(start, end, cost_per_hour):
    """report.vm time and cost for THIS scan: from claim (pool) or create (fresh) to the delete call."""
    life = max(0.0, end - start)
    return {"lifetime_secs": round(life),
            "cost_usd_max": round((cost_per_hour or 0) * -(-life // 3600), 4),
            "cost_usd_prorated": round((cost_per_hour or 0) * life / 3600, 4)}


def _span(secs):
    """3420 -> "57 min", 7300 -> "2.0 h"."""
    return f"{secs / 3600:.1f} h" if secs >= 3600 else f"{max(1, round(secs / 60))} min"


def compute_bill_items(vm):
    """The Cloud Compute lines of vultr_bill: this scan's VM time (from claim/create to the delete call) and,
    for a warm-pool VM, a separate no-total note for the time it sat armed in the pool before this scan."""
    items = []
    if not (vm or {}).get("id"):
        return items
    pooled = vm.get("from_pool")
    how = "taken pre-armed from the warm pool" if pooled else "created for this scan"
    api = ["GET /v2/instances (claim)" if pooled else "POST /v2/instances", "DELETE /v2/instances/{id}"]
    if vm.get("deletion"):
        api.append("GET /v2/instances/{id} (deletion check)")
    items.append({"service": "Cloud Compute", "what": f"one {vm.get('plan')} VM in {vm.get('region')}, {how}, "
                                                      "ran the repo, then deleted via the API",
                  "detail": (f"{vm.get('lifetime_secs')} s alive for this scan "
                             f"(from {'the claim' if pooled else 'creation'} to the delete call)")
                  if vm.get("lifetime_secs") is not None else None,
                  "usd": vm.get("cost_usd_prorated"), "api": api})
    if vm.get("pool_idle_secs"):
        usd = vm.get("pool_idle_cost_usd")
        items.append({"service": "Cloud Compute", "standby": True,
                      "what": "warm-pool standby: the same VM waited armed in the pool before this scan claimed it",
                      "detail": f"{_span(vm['pool_idle_secs'])} on standby", "usd": None,
                      "note": (f"${usd} of standby, " if usd is not None else "") +
                              "paid by the warm pool so scans start instantly; not in this scan's total"})
    return items


def vultr_bill(report, price=None):
    """Every Vultr service this scan used, what it did, and what it cost (from what was actually recorded).
    `price(model) -> (usd/prompt token, usd/completion token)`; defaults to the live catalog."""
    price = price or brain.price
    items = compute_bill_items(report.get("vm"))
    for c in (report.get("llm_usage") or {}).get("by_call", []):
        pin, pout = price(c["model"])
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


def order_plan(plan, extra=(), recruiter_cmds=(), run_cmd=None, reorder=True):
    """Final step order: default steps, AI README steps, what the recruiter asked for (max 2), what the visitor
    asked for, then the time-shifted (+45 days) re-runs last. Asked-for commands already planned are not repeated.
    Every step gets a `source`: "default" | "ai" | "recruiter" | "user"."""
    base = [*plan, *extra]
    asked = brain.asked_steps(base, recruiter_cmds, "recruiter")
    asked += brain.asked_steps(base + asked, [run_cmd] if run_cmd else [], "user")
    if reorder or extra or asked:
        timeshift = [s for s in plan if s.get("kill_before")]
        plan = [s for s in plan if not s.get("kill_before")] + list(extra) + asked + timeshift
    for s in plan:
        s.setdefault("source", "default")
    return plan


def ai(say, stage, what, fn, fallback, errors):
    """Run one LLM step; if Vultr Inference is down or the model was retired, carry on with rules only."""
    try:
        return fn()
    except Exception as e:
        errors.append({"step": what, "error": str(e)[:200]})
        say(stage, f"AI unavailable for {what}; carrying on with rules only (the verdict never depends on AI)")
        return fallback


def run(target=None, message=None, host=None, keep=False, snapshot=DEFAULT_SNAPSHOT, region="blr",
        vm_plan="vc2-2c-4gb", out_root=ROOT / "scans", emit=print, use_llm=True, plan_override=None, use_pool=False,
        run_cmd=None):
    """Full scan. `emit(stage, text)` receives progress. Returns the final report dict.
    `run_cmd`: a command the visitor says they were told to run (one line, <= 200 chars) -> a "user" step."""
    def say(stage, text):
        emit(stage, text)

    if run_cmd is not None and not (run_cmd := run_cmd.strip()):
        run_cmd = None
    if run_cmd and not brain.valid_command(run_cmd):
        raise ScanError("The command you were told to run must be one line of at most 200 characters.")
    started = time.time()
    brain.reset_usage()
    llm_errors = []
    recruiter = None
    if message:
        say("message", "reading the recruiter's message")
        no_ai = {"repo_urls": brain.find_repos(message),
                 "commands": brain.recruiter_commands(message)}
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
    source = None   # the exact code scanned: repo, branch, commit (pinned so a later force-push can't change the story)
    if os.path.isdir(target):
        repo = Path(target)
    else:
        say("fetch", f"downloading {target} (nothing is executed here)")
        repo = tmp / source_name(target)
        try:
            source = fetch_source(target, repo)
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        if source.get("commit"):
            say("fetch", f"pinned commit {source['commit'][:12]} on {source.get('branch') or 'the default branch'}")
    name = repo.name
    # ---- pre-check (static + provenance) runs alongside planning and VM boot; it never changes the verdict
    precheck_result = start_precheck(repo, None if os.path.isdir(target) else brain.split_branch(target)[0], message, emit)

    # ---- plan what the candidate does
    plan = plan_override or node_run_scan.default_plan(str(repo))
    readme = next((read(repo / f) for f in ("README.md", "readme.md", "README", "README.txt") if (repo / f).exists()), "")
    screen, extra = None, []
    if use_llm and not plan_override:
        say("plan", "screening the README for prompt injection")
        screen = ai(say, "plan", "screening the README", lambda: brain.screen_text(readme), None, llm_errors)
        say("plan", "planning what a candidate would run")
        extra = ai(say, "plan", "planning extra steps",
                   lambda: brain.plan_candidate_steps(readme, read(repo / "package.json"), file_tree(repo), plan),
                   [], llm_errors)
    plan = order_plan(plan, extra, (recruiter or {}).get("commands"), run_cmd,
                      reorder=use_llm and not plan_override)
    say("plan", " -> ".join(s["name"] for s in plan) or "(nothing runnable found)")

    if not plan:   # don't rent a VM to run nothing, and never call that "clean"
        shutil.rmtree(tmp, ignore_errors=True)
        report = {"verdict": "INCONCLUSIVE", "headline": node_detect.INCONCLUSIVE_NO_STEPS, "findings": [],
                  "stolen": [], "network": [], "dns": [], "steps": [], "bait": [], "stats": {},
                  "target": shown, "source": source, "recruiter": recruiter, "readme_screen": screen, "vm": None,
                  "total_secs": round(time.time() - started), "llm_usage": brain.usage(),
                  "llm_errors": llm_errors, "campaign": {"similarity": None, "indicators": []},
                  "precheck": precheck_result(), "env_setup": None, "fetch": None,
                  "coverage": {"started": False, "steps": [], "reason": "Nothing in the repo could be run."}}
        report["vultr_bill"] = vultr_bill(report)
        say("done", f"{report['verdict']}: {report['headline']}")
        return report

    iid, created, vm = None, None, {"plan": vm_plan, "region": region, "snapshot": snapshot}
    cost_per_hour = vultr.plan_hourly_cost(vm_plan)
    dest = Path(out_root) / f"{time.strftime('%Y%m%d-%H%M%S')}-{name}"
    try:
        claimed = pool.claim() if (use_pool and not host) else None
        if claimed:
            iid, host = claimed["id"], claimed["main_ip"]
            # this scan's VM time starts at the claim; the hours it sat armed before that are pool standby
            created = claimed.get("claimed_at") or time.time()
            idle = pool_idle_secs(claimed, created)
            vm.update(id=iid, from_pool=True, ready_secs=0, snapshot=None,
                      firewall_group_id=claimed.get("firewall_group_id") or None,
                      pool_idle_secs=None if idle is None else round(idle),
                      pool_idle_cost_usd=None if idle is None else round((cost_per_hour or 0) * idle / 3600, 4))
            say("vm", f"took pre-armed Vultr VM {iid[:8]} from the warm pool (used once, then destroyed)")
        elif not host:
            key_id = vultr.ensure_ssh_key(str(KEY) + ".pub")
            say("vm", f"creating a fresh Vultr VM ({vm_plan}, {region})")
            inst = vultr.create_instance(f"burner-{int(started)}", region=region, plan=vm_plan,
                                         sshkey_id=key_id, snapshot_id=snapshot, tags=["burner-scan"])
            iid, created = inst["id"], time.time()
            vm.update(firewall_group_id=inst.get("firewall_group_id") or None, pool_idle_secs=0, pool_idle_cost_usd=0)
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
            requested = time.time()
            if not vultr.delete_instance(iid):
                vm["note"] = "The VM was already gone when the scan tried to delete it."
            vm.update(destroyed=True, **vm_cost(created, requested, cost_per_hour))
            say("vm", f"VM destroyed after {vm['lifetime_secs']}s")
            vm["deletion"] = vultr.confirm_deleted(iid, requested)   # receipt: Vultr answers 404 (<= 30 s)
            if vm["deletion"]["confirmed_at"]:
                say("vm", "Vultr confirmed the VM is gone (GET /v2/instances/{id} -> 404)")
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
    report.update(target=shown, source=source, recruiter=recruiter, readme_screen=screen, vm=vm,
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
    ap.add_argument("--run", help="a command you were told to run (added as a 'user' step)")
    a = ap.parse_args()
    r = run(a.target, message=read(a.message) if a.message else None, host=a.host, keep=a.keep,
            snapshot=a.snapshot, use_llm=not a.no_llm, run_cmd=a.run,
            emit=lambda stage, text, data=None: print(f"[{time.strftime('%H:%M:%S')}] {stage:8} {text}", flush=True))
    print("\n" + "=" * 70 + f"\n{r['verdict']}\n{r['headline']}\n" + "=" * 70)
    for f in r["findings"]:
        print(f"  [{f['severity']:8}] {f['title']}")
    if r.get("explanation"):
        print("\n" + r["explanation"])
    print(f"\nresults: {r['_dir']}  |  vm: {r['vm']}  |  total {r['total_secs']}s")


if __name__ == "__main__":
    main()
