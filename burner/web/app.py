"""Burner web app.

  uvicorn burner.web.app:app --host 0.0.0.0 --port 8000
"""
import json
import os
import queue
import threading
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from burner.control import pool, scan, vultr

ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "static"
SAMPLES = {   # one-click demos (defanged samples shipped in this repo)
    "npm-start-stealer": {"path": ROOT / "samples" / "fake-takehome",
                          "message": (ROOT / "samples" / "recruiter-message.txt")},
    "clean-takehome": {"path": ROOT / "samples" / "clean-takehome", "message": None},
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
PER_DAY = int(os.environ.get("BURNER_PER_DAY", "60"))        # budget guard: each scan = one Vultr VM
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


def _rate_limit(ip):
    now = time.time()
    _hits[ip] = [t for t in _hits.get(ip, []) if now - t < 3600]
    day = [t for v in _hits.values() for t in v if now - t < 86400]
    if len(_hits[ip]) >= PER_IP_HOUR:
        raise HTTPException(429, f"limit: {PER_IP_HOUR} scans per hour per visitor (each scan rents a real VM)")
    if len(day) >= PER_DAY:
        raise HTTPException(429, "daily scan budget used up; try a sample or come back tomorrow")
    _hits[ip].append(now)
jobs = {}
slots = threading.Semaphore(MAX_PARALLEL)


class ScanRequest(BaseModel):
    message: str | None = None
    repo: str | None = None
    sample: str | None = None
    replay: bool = False   # watch a recorded real scan of this sample (no VM, instant, not rate-limited)


def recorded(sample):
    f = RECORDED_DIR / f"{sample}.json"
    return f if sample and f.exists() else None


def _mock_scan(req, emit, source=None):
    """Replay a realistic event sequence (~15 s) and return a stored report. Never touches Vultr."""
    source = source or MOCK_DIR / MOCK_FIXTURES.get(req.sample, "mock_report.json")
    rep = json.loads(Path(source).read_text(encoding="utf-8"))
    urls = scan.brain.URL_RE.findall(req.message or "")
    if not req.sample and (req.repo or urls):          # echo the user's own repo link back
        rep["target"] = (req.repo or "").strip() or urls[0].rstrip(".,)")
        if rep.get("recruiter"):
            rep["recruiter"]["repo_urls"] = [rep["target"]]
        if rep.get("abuse_kit"):
            from burner.control import campaign
            rep["abuse_kit"] = campaign.abuse_kit(rep)
    steps = [s["name"] for s in rep["steps"]]
    vm = rep["vm"]
    if MOCK_POOL:
        vm.update(from_pool=True, ready_secs=0)
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


def _save(job):
    """Keep finished reports so share links (/r/<id>) outlive the process (deploys keep scans/)."""
    (ROOT / "scans" / "_web").mkdir(parents=True, exist_ok=True)
    (ROOT / "scans" / "_web" / f"{job['id']}.json").write_text(json.dumps(job["report"], default=list))


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
                job["status"] = "done"
                return
            rep = scan.run(target or None, message=message or None, host=DEV_HOST, emit=emit,
                           use_pool=bool(POOL_SIZE))
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
    if req.repo and not scan.brain.URL_RE.fullmatch(req.repo.strip()):
        raise HTTPException(400, "only github.com / gitlab.com / bitbucket.org repo links")
    if not MOCK and not req.replay:   # replays rent nothing
        ip = (request.headers.get("x-forwarded-for") or request.client.host).split(",")[0].strip()
        _rate_limit(ip)
    jid = uuid.uuid4().hex[:10]
    jobs[jid] = {"id": jid, "req": req, "events": [], "status": "new", "created": time.time(),
                 "q": queue.Queue(), "report": None}
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
    f = ROOT / "scans" / "_web" / f"{jid}.json"
    rep = jobs[jid]["report"] if jid in jobs and jobs[jid]["report"] else (
        json.loads(f.read_text()) if f.exists() else None)
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
        return {"status": j["status"], "events": j["events"], "report": j["report"]}
    f = ROOT / "scans" / "_web" / f"{jid}.json"
    if f.exists():
        return {"status": "done", "events": [], "report": json.loads(f.read_text())}
    raise HTTPException(404)


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
