"""False-alarm check on real, popular public repos (starters, boilerplates, tutorial apps).

  python -m burner.bench.real_repos [--host IP] [--only owner/repo ...] [--collect] [--keep]

The shipped benchmark's clean samples are ones we wrote. This runs Burner, exactly as the benchmark does
(default candidate plan, no LLM, one repo at a time), on real repos nobody wrote for us, and reports every
verdict honestly: a MALICIOUS/SUSPICIOUS here is a false alarm, INCONCLUSIVE means Burner found nothing it
knows how to run. No malware is involved.

1. creates a throwaway Vultr VM (or uses --host), arms it with burner/node/setup.sh
2. on the VM, a detached driver clones each repo (no hooks, no symlinks) and runs run_scan.py on it
3. downloads the reports, writes reports/benchmark/real-repos.json + .md, deletes the VM
"""
import argparse
import io
import json
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from burner.bench.run_bench import NODE_DIR, OUT, ssh  # noqa: E402
from burner.control import vultr  # noqa: E402
from burner.control.scan import KEY, wait_ssh  # noqa: E402

REPOS = [   # (owner/repo, what it is) -- checked to exist on 4 Nov 2026
    ("hagopj13/node-express-boilerplate", "Express + MongoDB REST boilerplate"),
    ("gothinkster/node-express-realworld-example-app", "RealWorld API (Express + Prisma)"),
    ("nestjs/typescript-starter", "official NestJS starter"),
    ("sahat/hackathon-starter", "Express starter with many OAuth/API integrations"),
    ("danielfsousa/express-rest-boilerplate", "Express REST boilerplate"),
    ("remix-run/indie-stack", "official Remix stack"),
    ("bradtraversy/proshop_mern", "MERN e-commerce tutorial app"),
    ("gothinkster/react-redux-realworld-example-app", "RealWorld frontend (React + Redux)"),
    ("koajs/examples", "official Koa examples"),
    ("fastify/demo", "official Fastify demo app"),
    ("bezkoder/node-js-jwt-auth-mongodb", "JWT auth tutorial (Express + MongoDB)"),
    ("developit/express-es6-rest-api", "ES6 REST API boilerplate"),
    ("antfu/vitesse-lite", "Vite + Vue starter"),
    ("sveltejs/realworld", "RealWorld app (SvelteKit)"),
    ("typicode/json-server", "json-server (fake REST API tool)"),
    ("nuxt/starter", "official Nuxt starter"),
    ("vercel/nextjs-subscription-payments", "Next.js + Stripe + Supabase starter"),
    ("w3tecch/express-typescript-boilerplate", "Express + TypeScript boilerplate"),
    ("jsynowiec/node-typescript-boilerplate", "Node + TypeScript boilerplate"),
    ("miguelgrinberg/microblog", "Flask Mega-Tutorial app (Python)"),
    ("fastapi/full-stack-fastapi-template", "official FastAPI full-stack template (Python)"),
]
BASE = "/bench/real"

DRIVER = r'''
import json, os, subprocess, sys, time
base, repos = sys.argv[1], json.load(open(sys.argv[2]))
env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
for slug in repos:
    name = slug.replace("/", "__")
    r = f"{base}/results/{name}"
    subprocess.run(["rm", "-rf", r, f"{base}/repos/{name}"]); os.makedirs(r)
    t0 = time.time()
    c = subprocess.run(["git", "clone", "--depth", "1", "-c", "core.hooksPath=/dev/null", "-c", "core.symlinks=false",
                        f"https://github.com/{slug}", f"{base}/repos/{name}"], capture_output=True, text=True, timeout=300, env=env)
    if c.returncode:
        json.dump({"secs": 0, "rc": "clone failed", "err": c.stderr[-500:]}, open(f"{r}/timing.json", "w"))
        continue
    try:
        p = subprocess.run([sys.executable, "-u", f"{base}/burner/run_scan.py", "--repo", f"{base}/repos/{name}",
                            "--out", f"{r}/out"], capture_output=True, text=True, timeout=1500)
        rc, log = p.returncode, p.stdout + p.stderr
    except subprocess.TimeoutExpired as e:
        rc, log = "timeout", str(e)
    open(f"{r}/run.log", "w").write(log[-20000:])
    json.dump({"secs": round(time.time() - t0, 1), "rc": rc}, open(f"{r}/timing.json", "w"))
    subprocess.run(["rm", "-rf", f"{base}/repos/{name}"])
open(f"{base}/results/DONE", "w").write("ok")
'''


def create_vm():
    key_id = vultr.ensure_ssh_key(str(KEY) + ".pub")
    inst = vultr.create_instance(f"burner-realrepos-{int(time.time())}", region="blr", plan="vc2-2c-4gb",
                                 sshkey_id=key_id, tags=["burner-bench"])
    inst = vultr.wait_ready(inst["id"])
    return inst["id"], inst["main_ip"]


def upload(host, repos):
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as t:
        t.add(NODE_DIR, arcname="burner", filter=lambda ti: None if "__pycache__" in ti.name else ti)
        for name, data in (("driver.py", DRIVER.encode()), ("repos.json", json.dumps(repos).encode())):
            ti = tarfile.TarInfo(name)
            ti.size = len(data)
            t.addfile(ti, io.BytesIO(data))
    p = ssh(host, f"rm -rf {BASE} && mkdir -p {BASE} && tar -xzf - -C {BASE}", input_bytes=buf.getvalue())
    if p.returncode:
        raise RuntimeError(p.stderr.decode())


def analyse(local):
    rows = []
    for slug, what in REPOS:
        d = local / "results" / slug.replace("/", "__")
        if not d.exists():
            continue
        tim = json.loads((d / "timing.json").read_text()) if (d / "timing.json").exists() else {}
        rep = d / "out" / "report.json"
        row = {"repo": slug, "what": what, "url": f"https://github.com/{slug}", "secs": tim.get("secs")}
        if not rep.exists():
            row.update(verdict="ERROR", error=str(tim.get("rc")))
        else:
            r = json.loads(rep.read_text())
            row.update(verdict=r["verdict"], headline=r["headline"],
                       findings=[f"[{f['severity']}] {f['title']}" for f in r.get("findings", [])][:10],
                       steps=[f"{s['name']} (rc={s['rc']}, {s['secs']}s)" for s in r.get("steps", [])])
        rows.append(row)
    count = lambda v: [r["repo"] for r in rows if r["verdict"] == v]
    summ = {"repos": len(rows), "clean": len(count("NO MALICIOUS BEHAVIOUR OBSERVED")),
            "false_alarms": count("MALICIOUS") + count("SUSPICIOUS"), "inconclusive": count("INCONCLUSIVE"),
            "errors": count("ERROR")}
    return rows, summ


def write_md(path, rows, summ, meta):
    fa = summ["false_alarms"]
    lines = [f"# Burner on real public repos (false-alarm check)", "",
             f"Run {meta['finished']} on a throwaway Vultr VM ({meta['plan']}, {meta['region']}). Same engine and "
             "default candidate plan as the benchmark (no LLM). These repos were written by other people; none is malicious.", "",
             f"- **{summ['repos']} repos scanned**",
             f"- **{len(fa)} false alarms** (MALICIOUS or SUSPICIOUS on a clean repo){': ' + ', '.join(fa) if fa else ''}",
             f"- {summ['clean']} came back NO MALICIOUS BEHAVIOUR OBSERVED",
             f"- {len(summ['inconclusive'])} INCONCLUSIVE (nothing Burner knows how to run)"
             + (f": {', '.join(summ['inconclusive'])}" if summ["inconclusive"] else ""),
             *( [f"- {len(summ['errors'])} errors: {', '.join(summ['errors'])}"] if summ["errors"] else []), "",
             "| Repo | What it is | Verdict | Findings | Time |", "|---|---|---|---|---|"]
    for r in rows:
        f = "<br>".join(r.get("findings") or []) or "—"
        lines.append(f"| [{r['repo']}]({r['url']}) | {r['what']} | {r['verdict']} | {f} | {r['secs'] or '—'} s |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host")
    ap.add_argument("--only", nargs="*", default=[])
    ap.add_argument("--collect", action="store_true", help="don't start: wait for / download a run on --host")
    ap.add_argument("--keep", action="store_true", help="don't delete the VM afterwards")
    a = ap.parse_args()
    repos = [s for s, _ in REPOS if not a.only or s in a.only]
    iid, host = None, a.host
    started = time.time()
    try:
        if not host:
            iid, host = create_vm()
            print(f"[real] VM {iid[:8]} at {host}", flush=True)
            wait_ssh(host)
        if not a.collect:
            upload(host, repos)
            print("[real] arming the VM (docker, gVisor, sandbox image)", flush=True)
            p = ssh(host, f"bash {BASE}/burner/setup.sh > {BASE}/setup.log 2>&1 || tail -30 {BASE}/setup.log", timeout=1800)
            if p.returncode:
                raise RuntimeError("setup failed: " + p.stdout.decode()[-1500:])
            ssh(host, f"rm -f {BASE}/results/DONE; mkdir -p {BASE}/results; (cd {BASE} && exec setsid python3 driver.py "
                      f"{BASE} {BASE}/repos.json) > {BASE}/driver.log 2>&1 < /dev/null &", timeout=60, retries=1)
        seen = -1
        while True:
            time.sleep(30)
            try:
                p = ssh(host, f"test -f {BASE}/results/DONE && echo DONE; ls {BASE}/results/*/timing.json 2>/dev/null | wc -l",
                        timeout=60)
            except RuntimeError as e:
                print("[real] (ssh hiccup)", e, flush=True)
                continue
            out = p.stdout.decode()
            n = int(out.split()[-1]) if out.split() else 0
            if n != seen:
                print(f"[real] {n}/{len(repos)} repos scanned ({time.time() - started:.0f}s)", flush=True)
                seen = n
            if "DONE" in out:
                break
        p = ssh(host, f"tar -czf - -C {BASE} --exclude=syscalls.log --exclude=_work --exclude=bodies results driver.log",
                timeout=600)
        local = OUT / "runs" / "real-repos"
        local.mkdir(parents=True, exist_ok=True)
        tarfile.open(fileobj=io.BytesIO(p.stdout), mode="r:gz").extractall(local, filter="data")
    finally:
        if iid and not a.keep:
            vultr.delete_instance(iid)
            print(f"[real] VM {iid[:8]} deleted", flush=True)
    rows, summ = analyse(local)
    meta = {"finished": time.strftime("%Y-%m-%d %H:%M"), "plan": "vc2-2c-4gb", "region": "blr",
            "wall_secs": round(time.time() - started)}
    (OUT / "real-repos.json").write_text(json.dumps({"meta": meta, "summary": summ, "repos": rows}, indent=1))
    write_md(OUT / "real-repos.md", rows, summ, meta)
    print(json.dumps(summ, indent=1))
    for r in rows:
        print(f"  {r['repo']:50} {r['verdict']:32} {r['secs']}s  {(r.get('findings') or [''])[0]}")


if __name__ == "__main__":
    main()
