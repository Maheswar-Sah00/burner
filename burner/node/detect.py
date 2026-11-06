#!/usr/bin/env python3
"""Rule-based verdict from what the repo actually did. No LLM involved.

  detect.py OUT_DIR   (reads tokens.json, syscalls.log, net.jsonl, steps.json; writes report.json)
"""
import base64
import binascii
import datetime
import functools
import gzip
import io
import json
import os
import posixpath
import re
import sys
import urllib.parse
import zipfile
import zlib

HOME = "/home/dev/"
SENSITIVE = [  # (prefix under home, label, severity)
    (".aws/", "AWS credentials", "high"),
    (".ssh/id_", "SSH private key", "high"),
    (".ssh", "SSH folder", "high"),
    (".git-credentials", "GitHub token file", "high"),
    ("work/", "another project's secrets (.env)", "high"),
    (".config/solana", "Solana wallet", "high"),
    (".config/Exodus", "Exodus wallet", "high"),
    (".config/google-chrome/Default/Local Extension Settings", "MetaMask wallet (Chrome extension)", "high"),
    (".config/google-chrome/Default/Login Data", "Chrome saved passwords", "high"),
    (".config/google-chrome", "Chrome profile", "high"),
    ("Documents/", "Documents folder", "high"),
    (".bash_history", "shell history", "medium"),
]
PERSISTENCE = [".bashrc", ".profile", ".bash_profile", ".zshrc", ".config/autostart", ".config/systemd",
               ".ssh/authorized_keys", "/var/spool/cron", "/etc/cron",
               # global git config can set core.hooksPath / core.fsmonitor = code that runs on every git command
               ".gitconfig", ".config/git/"]
# VM / sandbox fingerprinting (malware that checks before it acts)
SANDBOX_PROBES = ["/sys/class/dmi/id/", "/proc/1/cgroup", "/proc/scsi/", "/sys/hypervisor", "/.dockerenv"]
SHELLS = {"sh", "bash", "dash", "zsh", "ksh"}
OWN_TOOLS = {"pkill", "pgrep", "ps", "timeout"}   # Burner's own helpers inside the sandbox scan /proc
# "fetch code from the network and run it": curl/wget piped or chained into a shell / interpreter
REMOTE_EXEC = re.compile(r"\b(curl|wget)\b[^|;&]*\|\s*(sudo\s+)?(ba|da|z|k)?sh\b"
                         r"|\b(curl|wget)\b[^|;&]*\|\s*(python3?|node|perl)\b"
                         r"|\b(ba|da|z)?sh\s+-c\s+[\"']?\$\((curl|wget)\b"
                         r"|\b(curl|wget)\b[^;&|]*-[oO]\s*(\S+)[^;&|]*(;|&&)\s*(ba|da|z)?sh\s+\9")
NORMAL_HOME_WRITES = [".npm/", ".cache/", ".config/configstore", ".local/", ".node_repl_history", ".node-gyp",
                      ".yarn", ".pnpm", ".config/yarn", "projects/",
                      # pm2 (process manager many Express boilerplates start with): logs, pids, sockets, config.
                      # Not ~/.pm2/dump.pm2: that is what `pm2 resurrect` restarts after a reboot (persistence).
                      ".pm2/logs/", ".pm2/pids/", ".pm2/pm2.log", ".pm2/pm2.pid", ".pm2/module_conf.json",
                      ".pm2/touch", ".pm2/rpc.sock", ".pm2/pub.sock", ".pm2/conf.js", ".pm2/modules/"]
KNOWN_BENIGN_HOSTS = {"registry.npmjs.org", "registry.yarnpkg.com", "pypi.org", "files.pythonhosted.org",
                      "nodejs.org", "github.com", "objects.githubusercontent.com", "codeload.github.com"}
DOWNLOADERS = {"curl", "wget", "nc", "ncat", "socat", "powershell", "pwsh"}
# Swapped tool binaries (Binance heist, BleepingComputer 3 Nov 2026: the take-home replaced the pyenv executable,
# so the attacker's code ran the next time the developer used their own toolchain).
# Folders the shell searches for commands: ANY file put there is a command the developer may run.
SHIM_DIRS = re.compile(r"^(?:/home/dev/(?:\.pyenv/shims|\.pyenv/bin|\.local/bin|bin|\.npm-global/bin|\.nvm/(?:.+/)?bin"
                       r"|\.cargo/bin)|/usr/local/bin|/opt/homebrew/bin|/home/linuxbrew/\.linuxbrew/bin)/[^/]+$")
# Anywhere else, only a file named like a developer tool in a bin/sbin/shims folder counts.
DEV_TOOLS = {"git", "ssh", "node", "npm", "npx", "python", "python3", "pip", "pip3", "pyenv", "code", "sudo", "zsh",
             "bash"}
PATH_LIKE_DIRS = {"bin", "sbin", "shims"}
# The project's own ./bin, installed packages' node_modules/.bin, package caches and scratch space are not PATH.
NOT_PATH = re.compile(r"/node_modules/|^/home/dev/(?:projects|\.npm|\.cache|\.yarn|\.pnpm-store)/|^/(?:tmp|var/tmp|proc|dev)/")
SWAP_CALLS = {"open": "write", "openat": "write", "creat": "write", "rename": "rename", "renameat": "rename",
              "renameat2": "rename", "link": "hard link", "linkat": "hard link", "symlink": "symlink",
              "symlinkat": "symlink", "chmod": "chmod", "fchmod": "chmod", "fchmodat": "chmod"}
INCONCLUSIVE_NO_STEPS = ("Can't tell. Burner found nothing it knows how to run here (it runs Node/npm projects, VS Code "
                         "auto-run tasks and Python apps with requirements.txt). Don't treat this as safe.")

LINE = re.compile(r"^[IWDE](\d{4}) (\d\d:\d\d:\d\d\.\d+)\s+\d+ strace\.go:\d+\] \[\s*(\d+):\s*(\d+)\] (\S+) ([EX]) (\w+)\((.*)$")

# gVisor prints a directory fd as "AT_FDCWD /cwd" or "0x3 /dir", and a path argument as "0xADDR <string as passed>",
# so a relative path ("../../.ssh/id_ed25519") comes with the directory it is relative to.
_FD = r"(?:AT_FDCWD|0x[0-9a-f]+|-?\d+)(?: (/[^,]*?))?(?: \(bad FD\))?"
_P = r"0x[0-9a-f]+ ([^,]*?)"
PATH_ARGS = {   # call -> (regex over the argument list, [(dir group or None, path group), ...])
    "open": (re.compile(rf"{_P}(?=, )"), [(None, 1)]),
    "creat": (re.compile(rf"{_P}(?=, )"), [(None, 1)]),
    "openat": (re.compile(rf"{_FD}, {_P}(?=, )"), [(1, 2)]),
    "execve": (re.compile(rf"{_P}(?=, )"), [(None, 1)]),
    "execveat": (re.compile(rf"{_FD}, {_P}(?=, )"), [(1, 2)]),
    "unlink": (re.compile(rf"{_P}(?=\))"), [(None, 1)]),
    "unlinkat": (re.compile(rf"{_FD}, {_P}(?=, )"), [(1, 2)]),
    "rename": (re.compile(rf"{_P}, {_P}(?=\))"), [(None, 1), (None, 2)]),
    "renameat": (re.compile(rf"{_FD}, {_P}, {_FD}, {_P}(?=\))"), [(1, 2), (3, 4)]),
    "renameat2": (re.compile(rf"{_FD}, {_P}, {_FD}, {_P}(?=, )"), [(1, 2), (3, 4)]),   # mv uses this one
    "link": (re.compile(rf"{_P}, {_P}(?=\))"), [(None, 1), (None, 2)]),
    "linkat": (re.compile(rf"{_FD}, {_P}, {_FD}, {_P}(?=, )"), [(1, 2), (3, 4)]),
    # (target, linkpath); False = leave as given: a relative target is relative to the link, not the cwd
    "symlink": (re.compile(rf"{_P}, {_P}(?=\))"), [(False, 1), (None, 2)]),
    "symlinkat": (re.compile(rf"{_P}, {_FD}, {_P}(?=\))"), [(False, 1), (2, 3)]),
    "chmod": (re.compile(rf"{_P}(?=, )"), [(None, 1)]),
    "fchmod": (re.compile(rf"{_P}(?=, )"), [(None, 1)]),    # fd printed as "0x3 /path/of/the/file"
    "fchmodat": (re.compile(rf"{_FD}, {_P}(?=, )"), [(1, 2)]),
}
PROC_ROOT = re.compile(r"^/proc/(?:self|thread-self|\d+)/root(?=/|$)")
PROC_CWD = re.compile(r"^/proc/(?:self|thread-self|\d+)/cwd(?=/|$)")


def resolve(path, base):
    """Absolute, normalised path ('..' and /proc/self/root|cwd folded), or the bare relative path if no base is known."""
    if path is None:
        return None
    if base and PROC_CWD.match(path):
        path = PROC_CWD.sub(base.rstrip("/"), path)
    if not path.startswith("/"):
        if not base:
            return path
        path = base.rstrip("/") + "/" + path
    path = posixpath.normpath(PROC_ROOT.sub("", path) or "/")
    return "/" + path.lstrip("/")


def home_rel(path):
    """Path relative to the fake home, or None. A relative path with no known base is matched by its tail
    ('../../.ssh/id_ed25519' -> '.ssh/id_ed25519') so an unresolvable read of a secret is still a read."""
    if not path:
        return None
    if path.startswith(HOME):
        return path[len(HOME):]
    if not path.startswith("/"):
        tail = re.sub(r"^(?:\.\.?/)+", "", path)
        # only hidden locations (.ssh, .aws, .config/...): a project's own "work/" or "Documents/" folder is not home
        return tail if tail.startswith(".") and classify(tail)[0] else None
    return None


def ts(mmdd, hms):
    y = datetime.datetime.now(datetime.timezone.utc).year
    d = datetime.datetime.strptime(f"{y}{mmdd} {hms[:15]}", "%Y%m%d %H:%M:%S.%f")
    return d.replace(tzinfo=datetime.timezone.utc).timestamp()


def path_args(call, rest, cwd):
    """The path arguments of a syscall, each resolved to an absolute normalised path where possible."""
    spec = PATH_ARGS.get(call)
    m = spec and spec[0].match(rest)
    if not m:   # unexpected format: fall back to any absolute path printed in the arguments
        return [resolve(p, None) for p in re.findall(r"0x[0-9a-f]+ (/[^,]*?)(?=, |\))", rest)]
    out = []
    for dir_group, path_group in spec[1]:
        if dir_group is False:
            out.append(resolve(m.group(path_group), None))
            continue
        base = m.group(dir_group) if dir_group else None
        out.append(resolve(m.group(path_group), base or cwd))
    return out


def parse_syscalls(path):
    ev = []
    if not os.path.exists(path):
        return ev
    cwd = {}   # pid -> last working directory gVisor showed for it (AT_FDCWD /dir)
    for line in open(path, errors="replace"):
        m = LINE.match(line)
        if not m or m.group(6) != "X":
            continue
        mmdd, hms, pid, tid, comm, _, call, rest = m.groups()
        failed = bool(re.search(r"errno=\d+", rest.rsplit(") = ", 1)[-1])) if ") = " in rest else False
        e = {"t": ts(mmdd, hms), "pid": int(pid), "comm": comm, "call": call, "failed": failed}
        at = re.match(r"AT_FDCWD (/[^,]*?), ", rest)
        if at:
            cwd[e["pid"]] = at.group(1)
        paths = path_args(call, rest, cwd.get(e["pid"])) if call in PATH_ARGS else []
        if call in ("open", "openat", "creat"):
            if not paths or not paths[0]:
                continue
            e["path"] = paths[0]
            e["write"] = call == "creat" or any(f in rest for f in ("O_WRONLY", "O_RDWR", "O_CREAT"))
            e["read"] = call != "creat" and "O_WRONLY" not in rest   # O_RDWR ('r+') reads too
            e["dir"] = "O_DIRECTORY" in rest
        elif call in ("execve", "execveat"):
            argv = re.search(r"\[(.*?)\]", rest)
            e["path"] = (paths[0] if paths else None) or "?"
            e["argv"] = re.findall(r'"((?:[^"\\]|\\.)*)"', argv.group(1)) if argv else []
        elif call == "connect":
            a = re.search(r"Addr: ([0-9a-fA-F.:]+), Port: (\d+)", rest)
            if not a:
                continue
            e["addr"], e["port"] = a.group(1), int(a.group(2))
        elif call in ("unlink", "unlinkat"):
            e["path"] = (paths[0] if paths else None) or "?"
        elif call in ("chmod", "fchmod", "fchmodat"):
            if not paths or not paths[0]:
                continue
            e["path"] = paths[0]
        elif call in ("rename", "renameat", "renameat2", "link", "linkat", "symlink", "symlinkat"):
            src, dst = (paths + [None, None])[:2]
            if call.startswith("symlink") and src and not src.startswith("/"):
                # a relative symlink target is relative to the link's own directory
                src = resolve(src, posixpath.dirname(dst)) if dst and dst.startswith("/") else src
            e["path"], e["to"] = src or "?", dst or "?"
        ev.append(e)
    return ev


def blobs(data, depth=0):
    """Yield data plus decoded forms (url, base64, hex, gzip/zlib, zip members)."""
    yield data
    if depth > 2 or not data:
        return
    try:
        u = urllib.parse.unquote_to_bytes(data)
        if u != data:
            yield from blobs(u, depth + 1)
    except Exception:
        pass
    for chunk in re.findall(rb"[A-Za-z0-9+/_-]{24,}={0,2}", data)[:200]:
        try:
            d = base64.b64decode(chunk + b"=" * (-len(chunk) % 4), altchars=b"-_" if b"-" in chunk or b"_" in chunk else None)
            if d:
                yield from blobs(d, depth + 1)
        except (binascii.Error, ValueError):
            pass
    for chunk in re.findall(rb"(?:[0-9a-fA-F]{2}){16,}", data)[:50]:
        try:
            yield from blobs(bytes.fromhex(chunk.decode()), depth + 1)
        except ValueError:
            pass
    for fn in (gzip.decompress, zlib.decompress):
        try:
            yield from blobs(fn(data), depth + 1)
        except Exception:
            pass
    for m in re.finditer(rb"PK\x03\x04", data):
        try:
            z = zipfile.ZipFile(io.BytesIO(data[m.start():]))
            for n in z.namelist()[:100]:
                yield n.encode()
                yield from blobs(z.read(n), depth + 1)
        except Exception:
            pass


@functools.lru_cache(maxsize=2048)
def self_xor(b, L):
    """b[i] ^ b[i+L] for every i, at C speed."""
    n = len(b) - L
    return (int.from_bytes(b[:n], "big") ^ int.from_bytes(b[L:], "big")).to_bytes(n, "big")


def xor_find(hay, value, max_key=16):
    """Find `value` hidden under a repeating-key XOR (key length 1..max_key) in `hay`.

    Known-plaintext trick: with c = p ^ k and k periodic with period L,
    c[i] ^ c[i+L] == p[i] ^ p[i+L], so we search the token's self-XOR in the data's self-XOR.
    Returns (offset, key) or None.
    """
    if len(hay) > 4_000_000 or len(hay) < 32 or len(value) < 16:
        return None
    for L in range(1, max_key + 1):
        if len(value) - L < 12 or len(hay) <= L:
            continue
        pv = self_xor(value, L)
        if not any(pv):
            continue   # degenerate (periodic token)
        i = self_xor(hay, L).find(pv)
        if i >= 0:
            key = bytes(hay[i + j] ^ value[j] for j in range(L))
            if any(key):
                return i, key
    return None


def unxor(data, off, key):
    return bytes(c ^ key[(i - off) % len(key)] for i, c in enumerate(data))


def b32_decode_loose(s):
    s = re.sub(r"[^A-Z2-7]", "", s.upper())
    for cut in range(0, 8):
        t = s[:len(s) - cut] if cut else s
        try:
            return base64.b32decode(t + "=" * (-len(t) % 8))
        except (binascii.Error, ValueError):
            continue
    return b""


def dns_payloads(net):
    """Group DNS lookups by parent domain and rebuild what was smuggled in the subdomain labels.

    Yields (parent_domain, [events], [candidate decoded byte strings]).
    """
    groups = {}
    for e in net:
        if e["type"] != "dns":
            continue
        labels = [l for l in e["qname"].split(".") if l]
        if len(labels) < 3:
            continue
        g = groups.setdefault(".".join(labels[-2:]), [])
        if not g or g[-1][0]["qname"] != e["qname"]:   # drop resolver retries
            g.append((e, labels[:-2]))
    for parent, items in groups.items():
        data_len = sum(len(l) for _, ls in items for l in ls)
        if data_len < 20:
            continue
        joins = {"".join(ls[0] for _, ls in items),                       # data in the first label
                 "".join("".join(ls) for _, ls in items),                 # data spread over labels
                 "".join(max(ls, key=len) for _, ls in items)}            # data in the longest label
        cands = []
        for s in joins:
            cands.append(s.encode())
            hx = re.sub(r"[^0-9a-f]", "", s)
            if len(hx) >= 16:
                try:
                    cands.append(bytes.fromhex(hx[:len(hx) // 2 * 2]))
                except ValueError:
                    pass
            b = b32_decode_loose(s)
            if b:
                cands.append(b)
        yield parent, [e for e, _ in items], cands


def hostname_of(e):
    """Best name for where a connection went: TLS SNI, HTTP Host (minus port), or DNS name."""
    h = e.get("sni") or (e.get("http_host") or "").rsplit(":", 1)[0] or e.get("host")
    if h and re.fullmatch(r"[\d.]+", h):
        return None   # literal IP
    return h or None


def step_at(steps, t):
    for slack in (0, 1.5):
        for s in steps:
            if s["t0"] - slack <= t <= s["t1"] + slack:
                return s["name"]
    if steps and t < steps[0]["t0"]:
        return "before the first step"
    return "after the steps (background process)"


def classify(rel):
    for prefix, label, sev in SENSITIVE:
        if rel.startswith(prefix):
            return label, sev
    return None, None


def swap_target(e):
    """(path, action) if this syscall puts or changes a command in a folder on the shell's PATH, else None."""
    action = SWAP_CALLS.get(e["call"])
    if not action or (action == "write" and (not e.get("write") or e.get("dir"))):
        return None
    p = e.get("to") if action in ("rename", "hard link", "symlink") else e.get("path")
    if not p or not p.startswith("/") or NOT_PATH.search(p):
        return None
    if SHIM_DIRS.match(p):
        return p, action
    parent, name = posixpath.split(p)
    if name in DEV_TOOLS and posixpath.basename(parent) in PATH_LIKE_DIRS:
        return p, action
    return None


def main(out):
    tokens = json.load(open(f"{out}/tokens.json"))
    steps = json.load(open(f"{out}/steps.json")) if os.path.exists(f"{out}/steps.json") else []
    sysev = parse_syscalls(f"{out}/syscalls.log")
    net = [json.loads(l) for l in open(f"{out}/net.jsonl")] if os.path.exists(f"{out}/net.jsonl") else []

    findings = []

    seen = set()

    def add(rule, severity, title, evidence, key=None):
        """One finding per behaviour: the same file written / command run again in a later step
        (e.g. the +45 day re-run) is not new evidence."""
        if key is not None:
            if (rule, key) in seen:
                return
            seen.add((rule, key))
        findings.append({"rule": rule, "severity": severity, "title": title, "evidence": evidence})

    # 1. fake secrets that LEFT the machine
    stolen = {}

    def find_token(hay, v):
        """-> (decoded_bytes, index, how) where how is None (plain), 'decoded' or 'xor key ...'."""
        for n, h in enumerate(hay):
            i = h.find(v)
            if i >= 0:
                return h, i, None if n == 0 else "decoded"
        for h in hay:
            r = xor_find(h, v)
            if r:
                off, key = r
                lo = max(0, off - 90)
                return unxor(h[lo:off + len(v) + 30], off - lo, key), off - lo, f"xor key {key.hex()}"
        return None

    def record(t, dest, ev, found, **extra):
        k = (t["kind"], dest)
        if k in stolen:
            return
        h, i, how = found
        v = t["value"].encode()
        stolen[k] = {"secret": t["kind"], "from_file": "~/" + t["path"], "sent_to": dest,
                     "dst": extra.get("dst") or f"{ev.get('dst_ip')}:{ev.get('dst_port')}",
                     "method": extra.get("method", ev.get("method")), "url_path": extra.get("url_path", ev.get("path")),
                     "proto": extra.get("proto", ev.get("proto")), "bytes": extra.get("bytes", ev.get("body_len")),
                     "event_id": ev["id"], "severity": t["severity"], "t": ev["t"],
                     "step": step_at(steps, ev["t"]), "value": t["value"],
                     "snippet": h[max(0, i - 90):i + len(v) + 30].decode("utf-8", "replace"),
                     "encoded": how is not None, **({"encoding": how} if how and how != "decoded" else {})}

    for e in net:
        if e["type"] == "tcp":
            data = (e.get("path") or "").encode()
            dest = hostname_of(e) or f"{e['dst_ip']}:{e['dst_port']}"
        elif e["type"] == "udp" and e.get("body_file"):   # non-DNS UDP
            data, dest = b"", f"udp from {e.get('src')}"
            e = {**e, "proto": "udp", "dst_ip": "?", "dst_port": "?"}
        else:
            continue
        if e.get("body_file"):
            data += b"\n" + open(f"{out}/bodies/{e['body_file']}", "rb").read()
        hay = list(blobs(data))
        for t in tokens:
            found = find_token(hay, t["value"].encode())
            if found:
                record(t, dest, e, found)

    # secrets smuggled out inside DNS lookups (subdomain labels, hex/base32/...)
    dns_tunnels = []
    for parent, evs, cands in dns_payloads(net):
        hay = [h for c in cands for h in blobs(c)]
        hit = False
        for t in tokens:
            found = find_token(hay, t["value"].encode())
            if found:
                hit = True
                record(t, parent, evs[0], found, dst=f"DNS ({len(evs)} lookups)", method="DNS", proto="dns",
                       url_path=evs[0]["qname"], bytes=sum(len(x["qname"]) for x in evs))
        long_labels = [x for x in evs if max(len(l) for l in x["qname"].split(".")) >= 25]
        if hit or len({x["qname"] for x in long_labels}) >= 3:
            dns_tunnels.append({"parent": parent, "lookups": len(evs), "example": evs[0]["qname"],
                                "step": step_at(steps, evs[0]["t"]), "carried_secrets": hit})
    by_dest = {}
    for s in stolen.values():
        by_dest.setdefault(s["sent_to"], []).append(s)
    for dest, items in by_dest.items():
        kinds = sorted({s["secret"] for s in items})
        sev = "critical" if any(s["severity"] == "high" for s in items) else "high"
        add("EXFIL", sev, f"Sent {len(kinds)} of your secrets to {dest}: {', '.join(kinds)}",
            {"sent_to": dest, "secrets": items})
    for d in dns_tunnels:
        add("DNS_TUNNEL", "high" if d["carried_secrets"] else "medium",
            f"Hid data in {d['lookups']} DNS lookups to *.{d['parent']}", d)

    # 2. fake secrets that were READ
    reads = {}
    # moving, hard-linking or symlinking a secret is a way to read it under another name
    GRABS = ("rename", "renameat", "renameat2", "link", "linkat", "symlink", "symlinkat")
    for e in sysev:
        if e.get("failed"):
            continue
        if not ((e["call"] in ("open", "openat") and e.get("read")) or e["call"] in GRABS):
            continue
        rel = home_rel(e.get("path", ""))
        label, sev = classify(rel) if rel is not None else (None, None)
        if not label and rel and e["call"] in GRABS:   # linking/moving a whole folder (~/.aws, ~/.ssh)
            label, sev = classify(rel.rstrip("/") + "/")
        if not label:
            continue
        key = (label, e["comm"])
        reads.setdefault(key, {"what": label, "process": e["comm"], "pid": e["pid"], "files": set(),
                               "step": step_at(steps, e["t"]), "severity": sev, "t": e["t"]})
        reads[key]["files"].add("~/" + rel)
        if e["call"] in GRABS:
            reads[key].setdefault("via", set()).add(f"{e['call']} -> {e.get('to', '?')}")
    for r in reads.values():
        r["files"] = sorted(r["files"])[:10]
        if "via" in r:
            r["via"] = sorted(r["via"])[:5]
        add("SECRET_READ", r["severity"], f"Opened {r['what']} ({r['process']}, during {r['step']})", r)

    # 2b. swapped tool binaries: a file written, moved, linked or chmod-ed into a folder on the shell's PATH
    #     (failed attempts count too: trying to overwrite /usr/local/bin/node is the intent that matters)
    swaps = {}
    for e in sysev:
        hit = swap_target(e)
        if not hit:
            continue
        p, action = hit
        s = swaps.setdefault(p, {"file": "~/" + p[len(HOME):] if p.startswith(HOME) else p, "actions": [],
                                 "process": e["comm"], "step": step_at(steps, e["t"]), "done": False})
        a = action + (" (failed)" if e.get("failed") else "")
        if a not in s["actions"]:
            s["actions"].append(a)
        s["done"] = s["done"] or not e.get("failed")
    for p, s in swaps.items():
        verb = "Replaced" if s.pop("done") else "Tried to replace"
        add("BINARY_SWAP", "high", f"{verb} {s['file']}, a command your shell runs ({', '.join(s['actions'])}) "
            f"— your own tools would run its code", s, key=p)

    # 3. persistence + dropped files
    for e in sysev:
        if e["call"] in ("open", "openat", "creat") and e.get("write") and not e.get("failed") \
                and e.get("path") not in swaps:
            p = e.get("path", "")
            rel = p[len(HOME):] if p.startswith(HOME) else p
            if any(rel.startswith(x) or p.startswith(x) for x in PERSISTENCE):
                add("PERSISTENCE", "high", f"Modified {rel} to run again later",
                    {"file": p, "process": e["comm"], "step": step_at(steps, e["t"])}, key=p)
            elif p.startswith(HOME) and not any(rel.startswith(x) for x in NORMAL_HOME_WRITES) \
                    and not classify(rel)[0]:
                add("DROPPED_FILE", "medium", f"Wrote ~/{rel} outside the project",
                    {"file": p, "process": e["comm"], "step": step_at(steps, e["t"])}, key=p)

    # 3b. VM / sandbox fingerprinting (informational: malware checks before acting)
    probes = {}
    for e in sysev:
        if e["call"] in ("open", "openat") and e["comm"] not in OWN_TOOLS                 and any(e.get("path", "").startswith(x) for x in SANDBOX_PROBES):
            probes.setdefault(e["comm"], {"process": e["comm"], "files": set(), "step": step_at(steps, e["t"])})
            probes[e["comm"]]["files"].add(e["path"])
    for pr in probes.values():
        pr["files"] = sorted(pr["files"])[:10]
        add("SANDBOX_CHECK", "low", f"Checked whether it is running in a VM/sandbox ({pr['process']})", pr)

    # 4. processes
    remote_exec = False
    for e in sysev:
        if e["call"].startswith("execve") and not e.get("failed"):
            base = os.path.basename(e["path"])
            argv = e.get("argv", [])
            if base in DOWNLOADERS:
                add("DOWNLOADER", "medium", f"Ran {base}",
                    {"argv": argv[:12], "parent": e["comm"], "step": step_at(steps, e["t"])}, key=tuple(argv))
            if base in SHELLS and REMOTE_EXEC.search(" ".join(argv[1:])):
                remote_exec = True
                add("REMOTE_CODE", "high", "Downloaded code from the internet and ran it",
                    {"argv": argv[:12], "parent": e["comm"], "step": step_at(steps, e["t"])}, key=tuple(argv))

    # 5. network
    contacts = {}
    for e in net:
        if e["type"] != "tcp":
            continue
        host = hostname_of(e)
        dest = host or e["dst_ip"]
        c = contacts.setdefault(f"{dest}:{e['dst_port']}", {"dest": dest, "port": e["dst_port"], "raw_ip": host is None,
                                                         "requests": 0, "bytes_out": 0, "protos": set(),
                                                         "step": step_at(steps, e["t"])})
        c["requests"] += 1
        c["bytes_out"] += e.get("body_len") or 0
        c["protos"].add(e.get("proto", "?"))
    for c in contacts.values():
        c["protos"] = sorted(c["protos"])
        hostname = c["dest"].split(":")[0]
        if hostname in KNOWN_BENIGN_HOSTS:
            continue
        sev = "medium" if c["raw_ip"] or c["port"] not in (80, 443) else "low"
        add("NETWORK", sev, f"Contacted {c['dest']} on port {c['port']}" + (" (hard-coded IP)" if c["raw_ip"] else ""), c)
    dns_names = sorted({e["qname"] for e in net if e["type"] == "dns"})

    # 6. the repo killed the sandbox (fork / memory bomb): what we saw is only part of the story
    died = next((s["sandbox_died"] for s in steps if s.get("sandbox_died")), None)
    if died:
        plan = json.load(open(f"{out}/plan.json")) if os.path.exists(f"{out}/plan.json") else steps
        add("SANDBOX_DIED", "high",
            f"Crashed the sandbox during {died['step']} (exhausted memory or processes) — analysis cut short",
            {**died, "steps_not_run": [p["name"] for p in plan[len(steps):]]})

    # verdict
    sevs = [f["severity"] for f in findings]
    high_reads = [r for r in reads.values() if r["severity"] == "high"]
    unknown_contacts = [f for f in findings if f["rule"] == "NETWORK"]
    binary_swap = any(f["rule"] == "BINARY_SWAP" for f in findings)
    if "critical" in sevs or ((high_reads or remote_exec or binary_swap) and unknown_contacts):
        verdict = "MALICIOUS"
    elif "high" in sevs or sevs.count("medium") >= 2:
        verdict = "SUSPICIOUS"
    else:
        verdict = "NO MALICIOUS BEHAVIOUR OBSERVED"
    # "nothing observed" is only meaningful if the repo's code actually ran
    # (a server killed at the step timeout exits 137 and did run; 126/127 = the command couldn't even start)
    ran = [s for s in steps if s.get("rc") not in (126, 127) or s.get("sandbox_died")]
    if verdict == "NO MALICIOUS BEHAVIOUR OBSERVED" and not ran:
        verdict = "INCONCLUSIVE"
    if verdict == "INCONCLUSIVE":
        headline = (INCONCLUSIVE_NO_STEPS if not steps else
                    "Can't tell. None of the steps could start, so Burner saw too little to judge it. "
                    "Don't treat this as safe.")
    elif verdict == "MALICIOUS" and stolen:
        kinds = sorted({s["secret"] for s in stolen.values()})
        dests = sorted({s["sent_to"] for s in stolen.values()})
        headline = f"Don't run this. It stole your {', '.join(kinds)} and sent them to {', '.join(dests)}."
    elif verdict == "MALICIOUS" and remote_exec and not high_reads and "critical" not in sevs:
        headline = "Don't run this. It downloaded code from an unknown server and ran it."
    elif verdict == "MALICIOUS" and binary_swap and not high_reads and "critical" not in sevs:
        swapped = sorted(f["evidence"]["file"] for f in findings if f["rule"] == "BINARY_SWAP")
        headline = (f"Don't run this. It replaced {', '.join(swapped[:3])} with its own program and contacted an "
                    "unknown server: your own tools would run the attacker's code.")
    elif verdict == "MALICIOUS":
        headline = "Don't run this. It opened your private keys/wallets and contacted an unknown server."
    elif verdict == "SUSPICIOUS" and died:
        headline = ("It crashed our sandbox before the analysis finished. Legit take-homes don't do that "
                    "— treat it as unsafe.")
    elif verdict == "SUSPICIOUS":
        headline = "Be careful. It did things a take-home never needs to do."
    else:
        headline = "Nothing malicious happened while we ran it the way a candidate would. That is not a guarantee."

    order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    findings.sort(key=lambda f: order[f["severity"]])
    report = {"verdict": verdict, "headline": headline, "findings": findings,
              "stolen": list(stolen.values()), "network": list(contacts.values()), "dns": dns_names,
              "steps": [{k: s[k] for k in ("name", "cmd", "rc", "why")} | {"secs": round(s["t1"] - s["t0"], 1)}
                        | ({"sandbox_died": s["sandbox_died"]} if s.get("sandbox_died") else {}) for s in steps],
              "bait": [{"kind": t["kind"], "file": "~/" + t["path"]} for t in tokens],
              "stats": {"syscall_events": len(sysev), "net_events": len(net)}}
    json.dump(report, open(f"{out}/report.json", "w"), indent=1, default=list)


if __name__ == "__main__":
    main(sys.argv[1])
