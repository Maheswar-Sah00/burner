"""Burner web app.

  uvicorn burner.web.app:app --host 0.0.0.0 --port 8000
"""
import json
import os
import queue
import re
import subprocess
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from burner.control import pool, scan, vultr

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"
SAMPLES = {   # one-click demos (defanged samples shipped in this repo)
    "npm-start-stealer": {"path": ROOT / "samples" / "fake-takehome",
                          "message": (ROOT / "samples" / "recruiter-message.txt")},
    "clean-takehome": {"path": ROOT / "samples" / "clean-takehome", "message": None},
    "fake-mcp-server": {"path": ROOT / "samples" / "fake-mcp-server", "message": None},   # not a take-home
}
DEV_HOST = os.environ.get("BURNER_DEV_HOST")       # reuse one VM while developing
MAX_PARALLEL = int(os.environ.get("BURNER_MAX_PARALLEL", "2"))
MOCK = os.environ.get("BURNER_MOCK") == "1"          # replay a stored scan; no VM, no LLM
MOCK_POOL = os.environ.get("BURNER_MOCK_POOL") == "1"  # mock: pretend the VM came from the warm pool
MOCK_DIR = Path(__file__).parent
MOCK_FIXTURES = {"clean-takehome": "mock_report_clean.json", "vscode-task": "mock_report_vscode.json"}
# real scans of the shipped samples, recorded on real Vultr VMs: what a visitor can watch instead of queueing
RECORDED_DIR = Path(__file__).parent / "recorded"
AVG_SCAN_SECS = int(os.environ.get("BURNER_AVG_SCAN_SECS", "120"))
BENCH_DIR = ROOT / "reports" / "benchmark"
BENCH_FALLBACK = Path(__file__).parent / "bench.json"

POOL_SIZE = int(os.environ.get("BURNER_POOL_SIZE", "0"))   # pre-armed VMs kept ready
PER_IP_HOUR = int(os.environ.get("BURNER_PER_IP_HOUR", "4"))
PER_IP_DAY = int(os.environ.get("BURNER_PER_IP_DAY", "10"))
PER_DAY = int(os.environ.get("BURNER_PER_DAY", "60"))        # budget guard: each scan = one Vultr VM
MAX_QUEUE = int(os.environ.get("BURNER_MAX_QUEUE", "8"))     # scans waiting for a VM; more -> 429
KEEP_JOBS = 200                                              # finished jobs kept in memory (reports are on disk)
VM_CHECK_TTL = 30                                            # vm-check asks Vultr at most this often per scan
_hits = {}

app = FastAPI(title="Burner")
app.mount("/static", StaticFiles(directory=STATIC, check_dir=False), name="static")


@app.on_event("startup")
def _start_pool():
    if POOL_SIZE and not MOCK and not DEV_HOST:
        threading.Thread(target=pool.maintain, kwargs={"size": POOL_SIZE, "log": print}, daemon=True).start()

        def reaper():
            while True:
                try:
                    killed = vultr.reap(max_age_min=20) + vultr.reap_stuck_pool()
                    if killed:
                        print("reaped", killed)
                except Exception as e:
                    print("reaper:", e)
                time.sleep(120)
        threading.Thread(target=reaper, daemon=True).start()


def _client_ip(request):
    """The visitor's IP. Caddy APPENDS the address it saw to X-Forwarded-For, so the last entry is the real one;
    anything before it is whatever the client sent (spoofable)."""
    xff = [p.strip() for p in (request.headers.get("x-forwarded-for") or "").split(",") if p.strip()]
    return xff[-1] if xff else (request.client.host if request.client else "unknown")


def _rate_limit(ip):
    now = time.time()
    for k in list(_hits):   # keep 24 h of history; forget visitors with none
        _hits[k] = [t for t in _hits[k] if now - t < 86400]
        if not _hits[k] and k != ip:
            del _hits[k]
    mine = _hits.setdefault(ip, [])
    if sum(now - t < 3600 for t in mine) >= PER_IP_HOUR:
        raise HTTPException(429, f"limit: {PER_IP_HOUR} scans per hour per visitor (each scan rents a real VM)")
    if len(mine) >= PER_IP_DAY:
        raise HTTPException(429, f"limit: {PER_IP_DAY} scans per day per visitor (each scan rents a real VM)")
    if sum(len(v) for v in _hits.values()) >= PER_DAY:
        raise HTTPException(429, "daily scan budget used up; try a sample or come back tomorrow")
    mine.append(now)


def _busy():
    """429 when MAX_QUEUE scans already wait for a VM (replays never wait, so they stay available)."""
    waiting = sum(1 for j in jobs.values() if j["status"] in ("new", "queued") and not j["req"].replay)
    if waiting >= MAX_QUEUE:
        msg = (f"Burner is busy: {waiting} scans are already waiting for a VM. Try again in a few minutes, "
               "or watch a recorded scan of a sample.")
        return JSONResponse({"error": msg, "detail": msg}, status_code=429)
    return None


def _prune():
    """Drop all but the newest KEEP_JOBS finished jobs from memory; their reports stay on disk (/r/<id> works)."""
    done = sorted((j for j in jobs.values() if j["status"] in ("done", "error")), key=lambda j: j["created"])
    for j in done[:max(0, len(done) - KEEP_JOBS)]:
        jobs.pop(j["id"], None)
        _vm_checks.pop(j["id"], None)


def _public(rep):
    """A report as served to anyone with the link: no presigned evidence URL (a 7-day bearer link to the
    bundle). The UI links /e/<id>, which signs a fresh one on click."""
    if not rep or not isinstance(rep.get("evidence"), dict) or "url" not in rep["evidence"]:
        return rep
    return {**rep, "evidence": {k: v for k, v in rep["evidence"].items() if k != "url"}}
jobs = {}
_vm_checks = {}   # jid -> (monotonic time, vm-check response)
slots = threading.Semaphore(MAX_PARALLEL)


class ScanRequest(BaseModel):
    message: str | None = None
    repo: str | None = None
    sample: str | None = None
    replay: bool = False   # watch a recorded real scan of this sample (no VM, instant, not rate-limited)
    run: str | None = None  # a command the visitor was told to run (one line, <= 200 chars) -> a "user" step


def recorded(sample):
    f = RECORDED_DIR / f"{sample}.json"
    return f if sample and f.exists() else None


def _mock_scan(req, emit, source=None):
    """Replay a realistic event sequence (~15 s) and return a stored report. Never touches Vultr."""
    fixture = source is None
    source = source or MOCK_DIR / MOCK_FIXTURES.get(req.sample, "mock_report.json")
    rep = json.loads(Path(source).read_text(encoding="utf-8"))
    urls = scan.brain.find_repos(req.message or "")
    if not req.sample and (req.repo or urls):          # echo the user's own repo link back
        rep["target"] = (req.repo or "").strip() or urls[0]
        if rep.get("recruiter"):
            rep["recruiter"]["repo_urls"] = [rep["target"]]
        if rep.get("abuse_kit"):
            from burner.control import campaign
            rep["abuse_kit"] = campaign.abuse_kit(rep)
    if fixture:   # the mock fixture, not a recorded real scan: show the v5 fields too
        _mock_v5(rep, req)
    steps = [s["name"] for s in rep["steps"]]
    vm = rep["vm"]
    seq = [(0.6, "message", "reading the recruiter's message")] if rep.get("recruiter") else []
    if rep.get("recruiter"):
        seq.append((1.0, "message", f"red flags: {len(rep['recruiter']['red_flags'])}, repo: {rep['target']}"))
    if str(rep["target"]).startswith("http"):
        seq.append((0.8, "fetch", f"downloading {rep['target']} (nothing is executed here)"))
    seq += [*([(0.4, "precheck", scan.precheck.summary(rep["precheck"]), rep["precheck"])] if rep.get("precheck") else []),
            (0.7, "plan", "screening the README for prompt injection"),
            (0.8, "plan", "planning what a candidate would run"),
            (0.6, "plan", " -> ".join(steps)),
            *([(0.6, "vm", f"took pre-armed Vultr VM {vm['id'][:8]} from the warm pool (used once, then destroyed)")]
              if vm.get("from_pool") else
              [(0.4, "vm", f"creating a fresh Vultr VM ({vm['plan']}, {vm['region']})"),
               (1.8, "vm", f"VM {vm['id'][:8]} is up after {vm['ready_secs']}s")]),
            (0.5, "setup", "arming the sandbox: gVisor, fake secrets, fake internet"),
            (1.0, "run", "running it like a candidate would"),
            (0.4, "run", "plant fake secrets"),
            (0.3, "run", f"plan {{'steps': {steps!r}}}"),
            (0.5, "run", "fetch dependencies (scripts disabled, no secrets)"),
            (0.6, "run", "start sandbox (gVisor, fake internet, syscall trace)")]
    for i, st in enumerate(rep["steps"], 1):
        seq.append((0.4 if i == 1 else 1.0, "run", "step " + str({"n": i, "name": st["name"], "cmd": st["cmd"]})))
    seq += [(1.0, "run", "grace period (background payloads)"),
            (0.6, "run", "sandbox destroyed"),
            (0.7, "vm", f"VM destroyed after {vm['lifetime_secs']}s"),
            *([(0.4, "match", f"behaves like {rep['campaign']['campaign']} "
                              f"({len(rep['campaign']['indicators'])} public indicators)")]
              if (rep.get("campaign") or {}).get("similarity") else []),
            (0.4, "explain", "writing the explanation"),
            (0.8, "evidence", "saving the evidence bundle to Vultr Object Storage"),
            (0.6, "done", f"{rep['verdict']}: {rep['headline']}")]
    for delay, stage, text, *data in seq:   # a 4th item is the event's `data` (the precheck event)
        time.sleep(delay)
        if data:
            emit(stage, text, data=data[0])
        else:
            emit(stage, text)
    return rep


def _iso(t):
    import datetime
    return datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isoformat(timespec="seconds")


def _mock_v5(rep, req):
    """Mock mode only: recruiter/user steps (built by the real code paths), warm-pool standby, the deletion
    receipt and the Cloud Compute bill lines, so the UI can be built against them. Fixture values win."""
    msg = req.message
    if req.sample in SAMPLES and SAMPLES[req.sample]["message"]:
        msg = SAMPLES[req.sample]["message"].read_text(encoding="utf-8")
    cmds = scan.brain.recruiter_commands(msg or "")
    if rep.get("recruiter") is not None:
        rep["recruiter"].setdefault("commands", cmds)
    shifted = [s for s in rep["steps"] if "(+" in s["name"]]
    rest = [s for s in rep["steps"] if "(+" not in s["name"]]
    asked = scan.brain.asked_steps(rep["steps"], cmds, "recruiter")
    asked += scan.brain.asked_steps(rep["steps"] + asked, [req.run] if req.run else [], "user")
    for s in asked:
        s.update(rc=0, secs=3.2, tail=f"$ {s['cmd']}\n(mock) ran in the sandbox; nothing else to show")
    rep["steps"] = rest + asked + shifted
    for s in rep["steps"]:
        s.setdefault("source", "default")
    vm = rep.get("vm")
    if not vm:
        return
    if MOCK_POOL:
        vm.update(from_pool=True, ready_secs=0)
        vm.setdefault("pool_idle_secs", 7260)
        vm.setdefault("pool_idle_cost_usd", round(0.0274 * vm["pool_idle_secs"] / 3600, 4))
    else:
        vm.setdefault("pool_idle_secs", 0)
        vm.setdefault("pool_idle_cost_usd", 0)
    now = time.time()
    if VM_ID_RE.fullmatch(str(vm.get("id") or "")):   # not for the benchmark-host fixture (no real VM id)
        vm.setdefault("deletion", {"requested_at": _iso(now - 4), "confirmed_at": _iso(now - 1), "http_status": 404,
                                   "check": "GET /v2/instances/{id}"})
    bill = rep.get("vultr_bill") or {"items": [], "note": "The verdict comes from rules; "
                                                          "the AI rows only read, plan and explain."}
    bill["items"] = scan.compute_bill_items(vm) + [i for i in bill["items"] if i.get("service") != "Cloud Compute"]
    known = [i["usd"] for i in bill["items"] if i.get("usd") is not None]
    bill["total_usd"] = round(sum(known), 6) if known else None
    rep["vultr_bill"] = bill


WEB_DIR = ROOT / "scans" / "_web"
JID_RE = re.compile(r"[0-9a-f]{10}")


def _report_key(jid):
    return f"scans/_web/{jid}.json"


def _save(job):
    """Keep finished reports so share links (/r/<id>) outlive the process: on disk (deploys keep scans/,
    written atomically) and, for real scans, a copy in Object Storage so they outlive the control VM too."""
    WEB_DIR.mkdir(parents=True, exist_ok=True)
    f = WEB_DIR / f"{job['id']}.json"
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps(job["report"], default=list))
    os.replace(tmp, f)
    if not MOCK and not job["req"].replay:
        def backup():
            try:
                from burner.control import evidence
                evidence.put_json(_report_key(job["id"]), job["report"])
            except Exception as e:
                print(f"report {job['id']}: object storage copy failed:", str(e)[:200])
        threading.Thread(target=backup, daemon=True).start()


def _load_report(jid):
    """A finished report by share id: live job, then disk, then Object Storage (re-cached on disk)."""
    if jid in jobs and jobs[jid]["report"]:
        return jobs[jid]["report"]
    if not JID_RE.fullmatch(jid):
        return None
    f = WEB_DIR / f"{jid}.json"
    if f.exists():
        return json.loads(f.read_text())
    if MOCK:
        return None
    try:
        from burner.control import evidence
        rep = evidence.get_json(_report_key(jid))
    except Exception as e:
        print(f"report {jid}: object storage lookup failed:", str(e)[:200])
        return None
    if rep is not None:
        WEB_DIR.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(rep, default=list))
    return rep


def _worker(job):
    def emit(stage, text, data=None):   # `data`: structured payload for some stages (e.g. "precheck")
        ev = {"t": round(time.time() - job["created"], 1), "stage": stage, "text": text}
        if data is not None:
            ev["data"] = data
        job["events"].append(ev)
        job["q"].put(None)

    try:
        req = job["req"]
        if req.replay:
            rep = _mock_scan(req, emit, source=recorded(req.sample))
            rep["replay"] = {"recorded": True, "note": "A recorded real scan of this sample, replayed (sped up). "
                                                       "No new VM was created for this view."}
            job["report"] = rep
            _save(job)
            job["status"] = "done"
            return
        job["status"] = "queued"
        emit("queue", "waiting for a free burner VM")
        last = None
        while not slots.acquire(timeout=3):
            if job.get("cancelled"):
                job["status"] = "error"
                emit("error", "Cancelled while waiting in the queue.")
                return
            ahead = sum(1 for j in jobs.values() if j["status"] == "queued" and j["created"] < job["created"])
            if ahead != last:
                last = ahead
                mins = max(1, round((ahead // MAX_PARALLEL + 1) * AVG_SCAN_SECS / 60))
                emit("queue", f"{ahead + 1} in line for a free burner VM, about {mins} min "
                              f"(every scan gets its own VM; {MAX_PARALLEL} run at once)")
        try:
            job["status"] = "running"
            target, message = req.repo, req.message
            if req.sample and req.sample in SAMPLES:
                s = SAMPLES[req.sample]
                target = str(s["path"])
                message = s["message"].read_text(encoding="utf-8") if s["message"] else message
            if MOCK:
                job["report"] = _mock_scan(req, emit)
                _save(job)
                job["status"] = "done"
                return
            rep = scan.run(target or None, message=message or None, host=DEV_HOST, emit=emit,
                           use_pool=bool(POOL_SIZE), run_cmd=req.run)
            rep.pop("_dir", None)
            job["report"] = rep
            _save(job)
            job["status"] = "done"
        finally:
            slots.release()
    except scan.ScanError as e:          # the user's input: say what to do
        job["status"] = "error"
        emit("error", str(e)[:400])
    except Exception as e:               # ours: don't leak server output, but keep a hint
        job["status"] = "error"
        print(f"scan {job['id']} failed:", repr(e)[:2000])
        emit("error", "Something went wrong on Burner's side, not with your repo "
                      f"({type(e).__name__}). Try again in a minute, or try a sample scan.")
    finally:
        job["q"].put(None)


@app.post("/api/scan")
def start_scan(req: ScanRequest, request: Request):
    if req.replay and not recorded(req.sample):
        raise HTTPException(400, "no recorded scan for that sample")
    if req.sample and req.sample not in SAMPLES and not (MOCK and req.sample in MOCK_FIXTURES):
        raise HTTPException(400, "unknown sample")
    if not (req.sample or (req.repo or "").strip() or (req.message or "").strip()):
        raise HTTPException(400, "paste a recruiter message or a repo link")
    if req.repo and req.repo.strip():
        link = scan.brain.repo_link(req.repo)
        if not link:
            raise HTTPException(400, "That doesn't look like a link Burner can run. Paste a public GitHub, GitLab or "
                                     "Bitbucket repo, a Hugging Face model or Space, or an Open VSX / VS Code "
                                     "Marketplace extension, e.g. https://github.com/owner/repo")
        req.repo = link
    if req.run is not None:
        if req.run.strip() and not scan.brain.valid_command(req.run):
            raise HTTPException(400, "the command you were told to run must be one line of at most 200 characters")
        req.run = req.run.strip() or None
    if not req.replay:
        busy = _busy()
        if busy:
            return busy
    if not MOCK and not req.replay:   # replays rent nothing
        _rate_limit(_client_ip(request))
    jid = uuid.uuid4().hex[:10]
    jobs[jid] = {"id": jid, "req": req, "events": [], "status": "new", "created": time.time(),
                 "q": queue.Queue(), "report": None}
    _prune()
    threading.Thread(target=_worker, args=(jobs[jid],), daemon=True).start()
    return {"id": jid}


@app.delete("/api/scan/{jid}")
def cancel(jid: str):
    """Leave the queue (e.g. to watch a recorded scan instead). A scan that already has its VM runs to the end."""
    job = jobs.get(jid)
    if not job:
        raise HTTPException(404)
    if job["status"] in ("new", "queued"):
        job["cancelled"] = True
    return {"status": job["status"], "cancelled": bool(job.get("cancelled"))}


@app.get("/e/{jid}")
def evidence_link(jid: str):
    """Evidence download with a freshly signed link (S3 links expire after 7 days; share links must not)."""
    rep = _load_report(jid)
    key = ((rep or {}).get("evidence") or {}).get("key")
    if not key:
        raise HTTPException(404, "no evidence bundle for this scan")
    from burner.control import evidence
    return RedirectResponse(evidence.presign(key, secs=3600))


@app.get("/api/recorded")
def recorded_samples():
    return {"samples": sorted(p.stem for p in RECORDED_DIR.glob("*.json"))}


@app.get("/api/scan/{jid}/events")
def events(jid: str):
    job = jobs.get(jid)
    if not job:
        raise HTTPException(404)

    def gen():
        sent = 0
        while True:
            while sent < len(job["events"]):
                yield f"data: {json.dumps(job['events'][sent])}\n\n"
                sent += 1
            if job["status"] in ("done", "error"):
                yield f"event: end\ndata: {json.dumps({'status': job['status']})}\n\n"
                return
            try:
                job["q"].get(timeout=15)
            except queue.Empty:
                yield ": keep-alive\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/api/scan/{jid}")
def result(jid: str):
    if jid in jobs:
        j = jobs[jid]
        return {"status": j["status"], "events": j["events"], "report": _public(j["report"])}
    rep = _load_report(jid)
    if rep is not None:
        return {"status": "done", "events": [], "report": _public(rep)}
    raise HTTPException(404)


VM_ID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


@app.get("/api/scan/{jid}/vm-check")
def vm_check(jid: str):
    """Ask Vultr, now, whether this scan's VM still exists (GET /v2/instances/{id}; 404 = deleted). The id comes
    from the stored report, never from the client. Cached VM_CHECK_TTL s per scan."""
    hit = _vm_checks.get(jid)
    if hit and time.monotonic() - hit[0] < VM_CHECK_TTL:
        return hit[1]
    vm = (_load_report(jid) or {}).get("vm") or {}
    iid = str(vm.get("id") or "")
    if not VM_ID_RE.fullmatch(iid):   # also skips the benchmark-host fixture, which had no per-scan VM
        msg = "this scan has no Vultr VM to check"
        return JSONResponse({"error": msg, "detail": msg}, status_code=404)
    if MOCK:
        status = 404
    else:
        try:
            status = vultr.instance_status(iid)
        except Exception as e:
            print(f"vm-check {jid}:", str(e)[:200])
            msg = "couldn't reach the Vultr API; try again in a minute"
            return JSONResponse({"error": msg, "detail": msg}, status_code=502)
    out = {"instance_id": iid[:8], "http_status": status, "gone": status == 404,
           "checked_at": _iso(time.time()), "region": vm.get("region")}
    if len(_vm_checks) > 2 * KEEP_JOBS:
        _vm_checks.clear()
    _vm_checks[jid] = (time.monotonic(), out)
    return out


_head_checks = {}
HEAD_CHECK_TTL = 600


@app.get("/api/scan/{jid}/head")
def head_check(jid: str):
    """Has the repo changed since this scan? `git ls-remote` of the scanned branch, compared with the pinned commit.
    Repo, branch and commit come from the stored report, never from the client. Cached HEAD_CHECK_TTL s per scan."""
    hit = _head_checks.get(jid)
    if hit and time.monotonic() - hit[0] < HEAD_CHECK_TTL:
        return hit[1]
    src = (_load_report(jid) or {}).get("source") or {}
    repo, branch, commit = str(src.get("repo") or ""), str(src.get("branch") or ""), str(src.get("commit") or "")
    if not (scan.brain.repo_link(repo) == repo and re.fullmatch(r"[0-9a-f]{40}", commit)):
        msg = "this scan has no pinned commit to compare"
        return JSONResponse({"error": msg, "detail": msg}, status_code=404)
    ref = f"refs/heads/{branch}" if branch and branch != "HEAD" and re.fullmatch(r"[\w./-]{1,200}", branch) else "HEAD"
    try:
        p = subprocess.run(["git", "-c", "credential.helper=", "ls-remote", "--", repo, ref], capture_output=True, text=True,
                           timeout=20, env={**os.environ, **scan.GIT_ENV})
        now = "" if p.returncode else (p.stdout.split() or [""])[0]
    except subprocess.TimeoutExpired:
        msg = "couldn't reach the repo host; try again in a minute"
        return JSONResponse({"error": msg, "detail": msg}, status_code=502)
    if not now:
        # repo deleted, made private, or the branch is gone: that is itself worth saying
        out = {"state": "gone", "scanned": commit[:12], "checked_at": _iso(time.time())}
    else:
        out = {"state": "same" if now == commit else "changed", "scanned": commit[:12], "now": now[:12],
               "checked_at": _iso(time.time())}
    if len(_head_checks) > 2 * KEEP_JOBS:
        _head_checks.clear()
    _head_checks[jid] = (time.monotonic(), out)
    return out


def build_benchmark(bench_dir=BENCH_DIR):
    """The /api/benchmark payload from reports/benchmark/results.json + containment.json."""
    res = json.loads((bench_dir / "results.json").read_text(encoding="utf-8"))
    con = json.loads((bench_dir / "containment.json").read_text(encoding="utf-8"))
    base = res.get("meta", {}).get("baseline") or {}
    return {"summary": res["summary"], "samples": res["samples"],
            "baseline": {"detected": base.get("burner_detected"), "of": base.get("malicious"),
                         "false_alarms": base.get("burner_false_alarms")},
            "containment": con["tests"], "defender": con.get("defender") or {},
            "meta": {"finished": res.get("meta", {}).get("finished"), "containment_tested": con.get("tested"),
                     "containment_environment": con.get("environment")}}


_bench_cache = {}


@app.get("/api/benchmark")
def benchmark():
    if "data" not in _bench_cache:
        try:
            _bench_cache["data"] = build_benchmark()
        except (OSError, KeyError, ValueError):   # reports/ not deployed: use the shipped copy
            _bench_cache["data"] = json.loads(BENCH_FALLBACK.read_text(encoding="utf-8"))
    return _bench_cache["data"]


@app.get("/healthz")
def healthz():
    """For the canary / uptime check: are the models Burner needs still listed, and is the pool warm?"""
    out = {"ok": True, "mock": MOCK, "queued_or_running": sum(j["status"] in ("queued", "running") for j in jobs.values())}
    if not MOCK:
        try:
            models = scan.brain.models_available()
            out["models"] = models
            # rules-only scans still work without AI, so a missing model degrades, it doesn't fail
            out["ai"] = "ok" if models.get(scan.brain.SAFETY) and any(
                models.get(m) for m in [scan.brain.PLANNER, *scan.brain.PLANNER_FALLBACKS]) else "degraded"
        except Exception as e:
            out.update(ai="unknown", ai_error=str(e)[:200])
        if POOL_SIZE:
            try:
                pool_vms = vultr.list_instances(pool.POOL_TAG)
                out["pool"] = {"size": POOL_SIZE, "armed": sum("armed" in i.get("tags", []) for i in pool_vms),
                               "arming": sum("arming" in i.get("tags", []) for i in pool_vms)}
            except Exception as e:
                out.update(ok=False, pool_error=str(e)[:200])
    return out


@app.get("/")
@app.get("/track")
@app.get("/r/{jid}")
def index(jid: str | None = None):
    return FileResponse(STATIC / "index.html")


# "put burner in front of the link": /github.com/owner/repo serves the page, which fills in the form (never auto-starts)
for _host in ("github.com", "www.github.com", "gitlab.com", "bitbucket.org", "huggingface.co", "hf.co", "open-vsx.org",
              "marketplace.visualstudio.com"):
    app.add_api_route(f"/{_host}/{{rest:path}}", lambda rest: FileResponse(STATIC / "index.html"),
                      methods=["GET"], include_in_schema=False)
