"""Turn a scan's raw evidence into a timeline (report.trace) and a theft graph (report.flows).

  python -m burner.control.trace SCAN_DIR      # prints a summary

Reads the files the node leaves in a scan dir: steps.json, syscalls.log (optional: older scans and
benchmark bundles may not have it), net.jsonl, tokens.json, plus report["stolen"] / ["bait"].
Shapes are defined in burner/web/CONTRACT.md.
"""
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("burner_detect", ROOT / "burner" / "node" / "detect.py")
detect = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(detect)

MAX_EVENTS = 400
DEDUPE_SECS = 1.0
SEV_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
# bait tokens whose "path" in tokens.json is a label rather than a file (see node/bait.py)
BAIT_REAL_PATH = {"chrome MetaMask extension": ".config/google-chrome/Default/Local Extension Settings",
                  "chrome Login Data": ".config/google-chrome/Default/Login Data"}
# execve noise: shells, package managers / runtimes starting up, Burner's own helpers
NOISE_EXEC = {"bash", "sh", "dash", "zsh", "ksh", "node", "nodejs", "npm", "npx", "yarn", "pnpm", "corepack",
              "id", "sleep", "timeout", "faketime", "env", "uname", "dirname", "basename", "cat", "true",
              "false", "test", "[", "mkdir", "rm", "cp", "mv", "ls", "seq", "tr", "sed", "grep", "head", "tail",
              "which", "readlink", "realpath", "tput", "locale", "nice", *detect.OWN_TOOLS}
INTERESTING_EXEC = {"python", "python3", "pip", "pip3", "perl", "ruby", "php", "git", "ssh", "scp", "base64",
                    "openssl", "xxd", "gpg", "tar", "zip", "unzip", "crontab", "systemctl", "chmod", "su",
                    "sudo", "mount", "nohup", "setsid", "dig", "nslookup", "host", "osascript", "security"}
# npm reading its own config / threads of the node runtime
NPM_COMMS = {"npm", "npx", "yarn", "pnpm", "libuv-worker"}
LOGIN_FILES = {".profile", ".bashrc", ".bash_profile", ".bash_login", ".zshrc", ".zprofile"}
THREAD_ALIAS = {"libuv-worker": "node", "node-main": "node", "V8 WorkerThread": "node"}
UA_PROC = [("curl", "curl"), ("wget", "wget"), ("python", "python"), ("aiohttp", "python"), ("go-http", "go"),
           ("node", "node"), ("axios", "node"), ("undici", "node"), ("npm", "npm"), ("powershell", "powershell")]


def _load_json(p, default):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return default


def _load_jsonl(p):
    out = []
    try:
        for line in Path(p).read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def _proc(comm):
    return THREAD_ALIAS.get(comm, comm or "?")


def _kb(n):
    if not n:
        return ""
    return f"{n} B" if n < 1024 else f"{n / 1024:.1f} KB"


def _bait_paths(tokens):
    """[(relative path under home, kind, severity)] for every planted token."""
    out = []
    for t in tokens:
        rel = BAIT_REAL_PATH.get(t.get("path", ""), t.get("path", ""))
        if rel:
            out.append((rel, t.get("kind", "?"), t.get("severity", "high")))
    return out


def _secrets_in(d, e, tokens):
    """Token kinds found (plain or decoded) in a captured request's path + body."""
    data = (e.get("path") or "").encode()
    if e.get("body_file"):
        try:
            data += b"\n" + (d / "bodies" / e["body_file"]).read_bytes()[:4_000_000]
        except OSError:
            pass
    if len(data) < 8:
        return []
    hay = list(detect.blobs(data))
    out = []
    for t in tokens:
        v = str(t.get("value", "")).encode()
        if len(v) >= 8 and t.get("kind") not in out and any(v in h for h in hay):
            out.append(t["kind"])
    return out


def _normal_read(rel, comm):
    """Why this read of a bait/sensitive file is routine (or '' if it isn't)."""
    if rel == ".npmrc" and comm in NPM_COMMS:
        return "npm reading its own config"
    if rel in LOGIN_FILES and comm in detect.SHELLS:
        return "login shell reading its startup file"
    return ""


def _bait_for(rel, bait):
    """Bait entries whose file is `rel` (or lives under the directory `rel`)."""
    return [b for b in bait if rel == b[0] or rel.startswith(b[0].rstrip("/") + "/")
            or b[0].startswith(rel.rstrip("/") + "/")]


def build(scan_dir, report):
    """-> (trace, flows) for the scan in `scan_dir`; `report` is that scan's report dict."""
    d = Path(scan_dir)
    steps_raw = _load_json(d / "steps.json", [])
    tokens = _load_json(d / "tokens.json", [])
    net = _load_jsonl(d / "net.jsonl")
    sysev = detect.parse_syscalls(str(d / "syscalls.log")) if (d / "syscalls.log").exists() else []
    stolen = report.get("stolen") or []

    if steps_raw:
        base = steps_raw[0]["t0"]
    else:
        ts = [e["t"] for e in net] + [e["t"] for e in sysev]
        base = min(ts) if ts else 0.0

    def rel_t(t):
        return round(t - base, 3)

    def step_of(t):
        return detect.step_at(steps_raw, t) if steps_raw else ""

    steps = []
    for s in steps_raw:
        st = {"name": s["name"], "t0": rel_t(s["t0"]), "t1": rel_t(s["t1"]), "rc": s.get("rc"),
              "sandbox_died": bool(s.get("sandbox_died"))}
        if isinstance(s.get("sandbox_died"), dict):
            st["died_reason"] = s["sandbox_died"].get("reason")
        steps.append(st)

    bait = _bait_paths(tokens)
    events = []
    last = {}   # dedupe key -> event (merge repeats within DEDUPE_SECS of the previous one)

    def add(t, lane, label, detail, severity, key=None, **extra):
        if t < base - 0.5:          # container boot noise before the first step
            return
        if key is not None:
            prev = last.get(key)
            if prev and t - prev["_last"] <= DEDUPE_SECS:
                prev["_last"] = t
                prev["count"] = prev.get("count", 1) + 1
                return
        ev = {"t": rel_t(t), "lane": lane, "label": str(label)[:160], "detail": str(detail)[:300],
              "severity": severity, "step": step_of(t), "_last": t, **extra}
        if key is not None:
            last[key] = ev
        events.append(ev)

    # ---- syscalls: secrets / files / processes
    reads = {}   # bait kind -> {process: first t}
    for e in sysev:
        call, comm = e["call"], e["comm"]
        if e.get("failed"):
            continue
        if call in ("open", "openat", "creat"):
            p = e.get("path", "")
            if not p.startswith(detect.HOME):
                continue
            rel = p[len(detect.HOME):]
            if not e.get("write"):
                label, sev = detect.classify(rel)
                hits = _bait_for(rel, bait)
                if not (label or hits):
                    continue
                sev = sev or (hits[0][2] if hits else "medium")
                normal = _normal_read(rel, comm)
                detail = f"opened by {_proc(comm)}" + (f" ({normal})" if normal else "")
                kinds = sorted({h[1] for h in hits})
                add(e["t"], "secrets", "~/" + rel, detail, "info" if normal else sev,
                    key=("open", p, comm), process=_proc(comm), **({"secrets": kinds} if kinds else {}))
                if not normal:
                    for k in kinds:
                        reads.setdefault(k, {}).setdefault(_proc(comm), e["t"])
            else:
                if any(rel.startswith(x) or p.startswith(x) for x in detect.PERSISTENCE):
                    add(e["t"], "files", "~/" + rel, f"modified by {_proc(comm)} to run again later",
                        "high", key=("write", p, comm), process=_proc(comm))
                elif not any(rel.startswith(x) for x in detect.NORMAL_HOME_WRITES) and not detect.classify(rel)[0]:
                    add(e["t"], "files", "~/" + rel, f"written by {_proc(comm)} outside the project",
                        "medium", key=("write", p, comm), process=_proc(comm))
        elif call in ("execve", "execveat"):
            exe = os.path.basename(e.get("path", "?"))
            argv = e.get("argv") or [exe]
            cmdline = " ".join(argv)
            sev = None
            if exe in detect.SHELLS and detect.REMOTE_EXEC.search(" ".join(argv[1:])):
                sev, why = "high", "downloaded code and ran it"
            elif exe in detect.DOWNLOADERS:
                sev, why = "medium", "network tool"
            elif comm in detect.OWN_TOOLS or comm.startswith("docker-entry") or exe in NOISE_EXEC:
                continue
            elif exe in INTERESTING_EXEC or re.match(r"python\d", exe):
                sev, why = "low", ""
            else:
                sev, why = "info", ""
            add(e["t"], "processes", exe, (f"{why}: " if why else "") + f"{cmdline[:220]} (started by {_proc(comm)})",
                sev, key=("exec", tuple(argv)), process=exe)

    # sandbox fingerprinting reads go in the files lane (informational)
    for e in sysev:
        if e["call"] in ("open", "openat") and not e.get("failed") and e["comm"] not in detect.OWN_TOOLS \
                and any(e.get("path", "").startswith(x) for x in detect.SANDBOX_PROBES):
            add(e["t"], "files", e["path"], f"sandbox check by {_proc(e['comm'])}", "low",
                key=("probe", e["comm"]), process=_proc(e["comm"]))

    # ---- network / dns
    for e in net:
        if e.get("type") == "tcp":
            host = detect.hostname_of(e)
            dest = host or f"{e.get('dst_ip')}:{e.get('dst_port')}"
            benign = (host or "") in detect.KNOWN_BENIGN_HOSTS
            sev = "info" if benign else ("medium" if host is None or e.get("dst_port") not in (80, 443) else "low")
            what = " ".join(x for x in (e.get("method"), e.get("path")) if x) or "connection"
            bits = [b for b in (e.get("proto"), _kb(e.get("body_len"))) if b]
            add(e["t"], "network", dest, what[:120] + (f" ({', '.join(bits)})" if bits else ""), sev,
                key=None, event_id=e.get("id"), raw_ip=host is None)
        elif e.get("type") == "dns":
            q = e.get("qname", "?")
            longest = max((len(x) for x in q.split(".")), default=0)
            benign = q in detect.KNOWN_BENIGN_HOSTS
            sev = "medium" if longest >= 25 else ("info" if benign else "low")
            add(e["t"], "dns", q, "DNS lookup" + (" (data hidden in the name?)" if longest >= 25 else ""), sev,
                key=("dns", q))
        elif e.get("type") == "udp":
            add(e["t"], "network", f"UDP from {e.get('src')}", "non-DNS UDP packet", "medium", key=("udp",))

    # ---- exfil: one event per request that carried secrets. detect.py records each (secret, dest)
    # once; re-check every request so a repeat (e.g. the +45 day re-run) shows up too.
    by_req = {}
    known = {(s.get("sent_to"), s.get("event_id")) for s in stolen}
    for e in net:
        if e.get("type") != "tcp" or not (e.get("body_file") or e.get("path")):
            continue
        dest = detect.hostname_of(e) or f"{e.get('dst_ip')}:{e.get('dst_port')}"
        if (dest, e.get("id")) in known:
            continue
        found = _secrets_in(d, e, tokens)
        if found:
            by_req[(dest, e.get("id"))] = {"dest": dest, "t": e["t"], "secrets": found, "bytes": e.get("body_len"),
                                           "event_id": e.get("id")}
    for s in stolen:
        k = (s.get("sent_to"), s.get("event_id"))
        r = by_req.setdefault(k, {"dest": s.get("sent_to"), "t": s.get("t"), "secrets": [], "bytes": s.get("bytes"),
                                  "method": s.get("method"), "proto": s.get("proto"), "event_id": s.get("event_id")})
        if s.get("secret") not in r["secrets"]:
            r["secrets"].append(s["secret"])
    for r in by_req.values():
        if r["t"] is None:
            continue
        add(r["t"], "exfil", r["dest"], ", ".join(r["secrets"]), "critical", key=None,
            secrets=r["secrets"], bytes=r["bytes"], event_id=r["event_id"])

    # ---- the repo crashed the sandbox (fork / memory bomb)
    for s in steps_raw:
        if s.get("sandbox_died"):
            why = s["sandbox_died"].get("reason") if isinstance(s["sandbox_died"], dict) else ""
            add(s["t1"], "processes", "sandbox crashed", why or "the sandbox died during this step", "high",
                step=s["name"])

    # ---- cap at MAX_EVENTS keeping the most severe, then chronological
    events.sort(key=lambda ev: ev["t"])
    if len(events) > MAX_EVENTS:
        keep = sorted(range(len(events)), key=lambda i: (SEV_RANK.get(events[i]["severity"], 9), events[i]["t"]))
        keep = set(keep[:MAX_EVENTS])
        events = [ev for i, ev in enumerate(events) if i in keep]
    for ev in events:
        ev.pop("_last", None)
        if ev.get("count", 1) > 1:
            ev["detail"] = f"{ev['detail']} (x{ev['count']})"

    ends = [s["t1"] for s in steps] + [ev["t"] for ev in events]
    trace = {"duration": round(max(ends), 1) if ends else 0.0, "steps": steps, "events": events,
             "source": {"syscalls": bool(sysev), "net_events": len(net)}}

    flows = _flows(tokens, report, stolen, reads, net, sysev)
    return trace, flows


def _flows(tokens, report, stolen, reads, net, sysev):
    nodes, links, seen = [], [], set()

    def node(nid, **kw):
        if nid not in seen:
            seen.add(nid)
            nodes.append({"id": nid, **kw})

    taken = {s.get("secret") for s in stolen}
    kinds = [t.get("kind") for t in tokens] or [b.get("kind") for b in report.get("bait") or []]
    for k in dict.fromkeys(kinds):
        node(f"s:{k}", label=k, kind="secret", taken=k in taken)
    for s in stolen:   # a stolen secret that wasn't in the bait list (shouldn't happen)
        node(f"s:{s.get('secret')}", label=s.get("secret"), kind="secret", taken=True)

    net_by_id = {e.get("id"): e for e in net}
    connects = [e for e in sysev if e["call"] == "connect"]

    def sender(s):
        """Which process made the request that carried secret s."""
        ev = net_by_id.get(s.get("event_id")) or {}
        ip, port, t = ev.get("dst_ip"), ev.get("dst_port"), s.get("t") or 0
        cands = [c for c in connects if c.get("addr") == ip and c.get("port") == port and abs(c["t"] - t) < 10]
        if cands:
            return _proc(min(cands, key=lambda c: abs(c["t"] - t))["comm"])
        readers = reads.get(s.get("secret")) or {}
        before = [(rt, p) for p, rt in readers.items() if rt <= t + 1]
        if before:
            return max(before)[1]
        if readers:
            return next(iter(readers))
        ua = (ev.get("user_agent") or "").lower()
        for needle, p in UA_PROC:
            if needle in ua:
                return p
        return "unknown process"

    sent = {}   # (process, dest) -> {secrets, events}
    senders = {}
    for s in stolen:
        p = sender(s)
        senders.setdefault(s.get("secret"), set()).add(p)
        k = (p, s.get("sent_to"))
        g = sent.setdefault(k, {"secrets": [], "events": {}, "dns": s.get("proto") == "dns"})
        if s.get("secret") not in g["secrets"]:
            g["secrets"].append(s.get("secret"))
        g["events"][s.get("event_id")] = s.get("bytes") or 0

    read_links = set()
    for k, procs in reads.items():
        for p in procs:
            read_links.add((k, p))
    for k, procs in senders.items():   # stolen but the read wasn't traced: still connect secret -> sender
        if not any(rk == k for rk, _ in read_links):
            for p in procs:
                read_links.add((k, p))
    for k, p in sorted(read_links):
        node(f"p:{p}", label=p, kind="process")
        links.append({"source": f"s:{k}", "target": f"p:{p}", "kind": "read"})
    for (p, dest), g in sent.items():
        node(f"p:{p}", label=p, kind="process")
        raw = bool(re.fullmatch(r"[\d.]+(:\d+)?", dest or ""))
        node(f"d:{dest}", label=dest, kind="destination", raw_ip=raw, **({"via": "dns"} if g["dns"] else {}))
        links.append({"source": f"p:{p}", "target": f"d:{dest}", "kind": "sent", "secrets": g["secrets"],
                      "bytes": sum(g["events"].values())})
    return {"nodes": nodes, "links": links}


def attach(report, scan_dir):
    """Set report['trace'] / report['flows'] in place."""
    report["trace"], report["flows"] = build(scan_dir, report)
    return report


def summary(trace, flows):
    from collections import Counter
    lanes = Counter(e["lane"] for e in trace["events"])
    sev = Counter(e["severity"] for e in trace["events"])
    kinds = Counter(n["kind"] for n in flows["nodes"])
    taken = sum(1 for n in flows["nodes"] if n["kind"] == "secret" and n.get("taken"))
    return (f"duration {trace['duration']}s, {len(trace['steps'])} steps, {len(trace['events'])} events "
            f"lanes={dict(lanes)} sev={dict(sev)} | flows nodes={dict(kinds)} taken={taken} "
            f"links={len(flows['links'])}")


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        rep = _load_json(Path(arg) / "report.json", {})
        t, f = build(arg, rep)
        print(arg, "\n  ", summary(t, f))
