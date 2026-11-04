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
from fastapi.responses import FileResponse, StreamingResponse
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
                    killed = vultr.reap(max_age_min=20)
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


def _mock_scan(req, emit):
    """Replay a realistic event sequence (~15 s) and return a stored report. Never touches Vultr."""
    rep = json.loads((MOCK_DIR / MOCK_FIXTURES.get(req.sample, "mock_report.json")).read_text(encoding="utf-8"))
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
    seq += [(0.7, "plan", "screening the README for prompt injection"),
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
    for delay, stage, text in seq:
        time.sleep(delay)
        emit(stage, text)
    return rep


def _worker(job):
    def emit(stage, text):
        job["events"].append({"t": round(time.time() - job["created"], 1), "stage": stage, "text": text})
        job["q"].put(None)

    try:
        job["status"] = "queued"
        emit("queue", "waiting for a free burner VM")
        with slots:
            job["status"] = "running"
            req = job["req"]
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
            (ROOT / "scans" / "_web").mkdir(parents=True, exist_ok=True)
            (ROOT / "scans" / "_web" / f"{job['id']}.json").write_text(json.dumps(rep, default=list))
            job["status"] = "done"
    except Exception as e:
        job["status"] = "error"
        emit("error", str(e)[:400])
    finally:
        job["q"].put(None)


@app.post("/api/scan")
def start_scan(req: ScanRequest, request: Request):
    if req.sample and req.sample not in SAMPLES and not (MOCK and req.sample in MOCK_FIXTURES):
        raise HTTPException(400, "unknown sample")
    if not (req.sample or (req.repo or "").strip() or (req.message or "").strip()):
        raise HTTPException(400, "paste a recruiter message or a repo link")
    if req.repo and not scan.brain.URL_RE.fullmatch(req.repo.strip()):
        raise HTTPException(400, "only github.com / gitlab.com / bitbucket.org repo links")
    if not MOCK:
        ip = (request.headers.get("x-forwarded-for") or request.client.host).split(",")[0].strip()
        _rate_limit(ip)
    jid = uuid.uuid4().hex[:10]
    jobs[jid] = {"id": jid, "req": req, "events": [], "status": "new", "created": time.time(),
                 "q": queue.Queue(), "report": None}
    threading.Thread(target=_worker, args=(jobs[jid],), daemon=True).start()
    return {"id": jid}


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


@app.get("/")
@app.get("/track")
@app.get("/r/{jid}")
def index(jid: str | None = None):
    return FileResponse(STATIC / "index.html")
