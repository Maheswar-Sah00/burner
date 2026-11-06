"""Pre-check: red flags found in seconds WITHOUT running anything. Warnings only; never sets the verdict.

Reads the already-cloned repo as text (read-only, size-capped, skips .git and node_modules) and asks a few
public APIs about where it came from (GitHub owner/repo age, npm dependency age, company-domain age via RDAP).
Every network call is bounded (<= 3 s each, <= 6 s in total) and fails soft.

  python -m burner.control.precheck PATH_OR_GIT_URL [--message recruiter.txt] [--no-network]

Output: {"flags": [{"id", "severity": "info|warn|high", "title", "detail", "source", "file"?}],
         "counts": {"high", "warn", "info"}, "ms", "sources": {...}, "note"}
"""
import base64
import binascii
import concurrent.futures as cf
import datetime as dt
import ipaddress
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

NOTE = "Pre-check · warnings only — the verdict comes from running it"
SKIP_DIRS = {".git", "node_modules", "bower_components", ".venv", "venv", "__pycache__"}
MAX_FILES = 3000
MAX_FILE_BYTES = 512 * 1024
MAX_TOTAL_BYTES = 24 * 1024 * 1024
CODE_EXT = {".js", ".cjs", ".mjs", ".jsx", ".ts", ".tsx", ".vue", ".svelte"}
SCRIPT_EXT = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd", ".py"}
CONFIGISH = re.compile(r"(^|/)(config|configs|assets|public|static|fonts?|images?|img|vendor|lib/config|setup)(/|\.|$)"
                       r"|(config|conf|settings|setup)\.[cm]?[jt]s$", re.I)
LIFECYCLE = ("preinstall", "install", "postinstall", "prepare", "preprepare", "postprepare", "prepublish")
C2_PORTS = ("1224", "1244", "1245")
POPULAR = ["express", "react", "lodash", "axios", "dotenv", "chalk", "moment", "request", "mongoose", "webpack",
           "typescript", "jsonwebtoken", "bcrypt", "bcryptjs", "nodemon", "eslint", "socket.io", "commander",
           "body-parser", "cookie-parser", "ethers", "web3", "dayjs", "prettier", "sequelize", "passport",
           "multer", "helmet", "morgan", "winston", "redux", "next", "uuid", "cors"]
NOT_SQUATS = {"preact", "color", "colors", "chai", "ether", "web3js", "nexe", "core", "corsa", "axiom", "vuex"}
SENSITIVE = [(r"\.aws/credentials", "AWS credentials"), (r"\.ssh/id_(rsa|ed25519|ecdsa)", "SSH private keys"),
             (r"Login Data", "browser saved passwords"), (r"Local Extension Settings", "browser extension storage"),
             (r"nkbihfbeogaeaoehlefnkodbefgpgknn", "MetaMask's extension ID"),
             (r"solana/id\.json", "a Solana wallet"), (r"exodus\.wallet|Exodus/", "an Exodus wallet"),
             (r"\.config/google-chrome|Google/Chrome/User Data|BraveSoftware", "browser profiles"),
             (r"login\.keychain|Keychains/", "the macOS keychain"),
             (r"claude_desktop_config\.json|\.cursor/mcp\.json|\.codeium/windsurf/mcp_config",
              "AI tools' MCP configs (API keys)"),
             (r"huggingface/token", "the Hugging Face token")]
PRIVATE_NETS = [ipaddress.ip_network(n) for n in ("0.0.0.0/8", "10.0.0.0/8", "127.0.0.0/8", "169.254.0.0/16",
                                                     "172.16.0.0/12", "192.168.0.0/16", "224.0.0.0/3")]
IP_RE = re.compile(r"(?<![\w.])((?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3})(?![\w.])")
B64_BLOB = re.compile(r"[A-Za-z0-9+/]{240,}={0,2}")
HEX_BLOB = re.compile(r"(?:[0-9a-fA-F]{2}){160,}")
B64_CALL = re.compile(r"""(?:Buffer\.from|atob)\(\s*(['"`])([A-Za-z0-9+/=]{8,4000})\1(?:\s*,\s*(['"`])base64\3)?""")
DOMAIN_RE = re.compile(r"^(?=.{4,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,24}$", re.I)
PIPE_SHELL = re.compile(r"\b(curl|wget|iwr|Invoke-WebRequest)\b[^\n|;]{0,240}\|\s*(sudo\s+)?(ba|z)?sh\b|"
                        r"\b(iex|Invoke-Expression)\b", re.I)
CHILD = re.compile(r"""require\(\s*['"](node:)?child_process['"]\s*\)|from\s+['"](node:)?child_process['"]""")
EXEC_NET = re.compile(r"""\b(exec|execSync|spawn|spawnSync)\s*\(\s*[`'"][^`'"]{0,80}\b(curl|wget|powershell|bash\s+-c|nc|python\s+-c)\b""")


def _flag(fid, severity, title, detail="", source="files", file=None):
    f = {"id": fid, "severity": severity, "title": title, "detail": detail[:300], "source": source}
    if file:
        f["file"] = file
    return f


def _short(s, n=140):
    s = re.sub(r"\s+", " ", str(s)).strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def _jsonc(text):
    """Parse VS Code style JSON (comments, trailing commas). Returns None if it still isn't JSON."""
    out, i, n, in_str = [], 0, len(text), False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(text[i + 1]); i += 2; continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True; out.append(c)
        elif text.startswith("//", i):
            j = text.find("\n", i); i = n if j < 0 else j; continue
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2); i = n if j < 0 else j + 2; continue
        else:
            out.append(c)
        i += 1
    try:
        return json.loads(re.sub(r",\s*([}\]])", r"\1", "".join(out)))
    except ValueError:
        return None


def _walk(repo):
    """(relative posix path, absolute Path) for every file, capped; never follows symlinks."""
    repo = Path(repo)
    count = 0
    for root, dirs, files in os.walk(repo, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
        for f in sorted(files):
            p = Path(root) / f
            if p.is_symlink():
                continue
            yield p.relative_to(repo).as_posix(), p
            count += 1
            if count >= MAX_FILES:
                return


def _read(p):
    try:
        with open(p, "rb") as fh:
            return fh.read(MAX_FILE_BYTES).decode("utf-8", errors="replace")
    except OSError:
        return ""


def _public_ip(s):
    try:
        ip = ipaddress.ip_address(s)
    except ValueError:
        return False
    return not any(ip in n for n in PRIVATE_NETS) and not s.endswith(".255")


def _edit1(a, b):
    """True if a and b differ by one insert/delete/substitution or one adjacent swap."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        d = [i for i in range(len(a)) if a[i] != b[i]]
        return len(d) == 1 or (len(d) == 2 and d[1] == d[0] + 1 and a[d[0]] == b[d[1]] and a[d[1]] == b[d[0]])
    s, l = (a, b) if len(a) < len(b) else (b, a)
    i = 0
    while i < len(s) and s[i] == l[i]:
        i += 1
    return s[i:] == l[i + 1:]


def typosquat_of(name):
    base = name.split("/")[-1].lower()
    if base in POPULAR or base in NOT_SQUATS or len(base) < 4:
        return None
    for p in POPULAR:
        if len(p) >= 4 and _edit1(base, p):
            return p
        if base.replace("-", "").replace(".", "") == p.replace("-", "").replace(".", "") and base != p:
            return p
    return None


# ---------------------------------------------------------------------------------------------- static
def static_flags(repo):
    """Every signal that needs only the files. Pure reads; nothing from the repo is executed or imported."""
    repo = Path(repo)
    flags, total = [], 0
    hits = {}          # id -> list of files (aggregated into one flag each)

    def hit(fid, rel):
        hits.setdefault(fid, [])
        if rel not in hits[fid]:
            hits[fid].append(rel)

    ips, decoded, sensitive, c2 = {}, [], {}, []
    for rel, p in _walk(repo):
        low = rel.lower()
        name = low.rsplit("/", 1)[-1]
        ext = os.path.splitext(name)[1]
        try:
            size = p.stat().st_size
        except OSError:
            continue

        # committed .env (not the examples)
        if re.fullmatch(r"\.env(\.(local|development|production|dev|prod))?", name):
            text = _read(p)
            keys = [k for k, v in re.findall(r"^\s*([A-Z0-9_]+)\s*=\s*(.*)$", text, re.M)]
            secretish = [k for k, v in re.findall(r"^\s*([A-Z0-9_]+)\s*=\s*(\S.*)$", text, re.M)
                         if re.search(r"KEY|SECRET|TOKEN|PASS|PRIVATE|MNEMONIC", k)]
            flags.append(_flag("env-committed", "warn" if secretish else "info", "A .env file is committed",
                               f"{rel}: {', '.join(keys[:6]) or 'empty'}" +
                               (" — has secret-looking keys" if secretish else ""), file=rel))
        if re.fullmatch(r"\.env\.(example|sample|template|dist)", name):
            urls = re.findall(r"https?://[^\s\"']+", _read(p))
            ext_urls = [u for u in urls if not re.search(r"//(localhost|127\.|0\.0\.0\.0|example\.)", u)]
            if ext_urls:
                flags.append(_flag("env-example-url", "info", "Example .env points at an outside server",
                                   f"{rel}: {_short(ext_urls[0], 90)}", file=rel))

        # git hooks shipped with the repo (they don't run on clone, but husky/hooksPath installs them on npm install)
        if re.search(r"(^|/)(\.githooks|\.husky|\.git-hooks)/[^/_]+$", low) and not name.startswith("."):
            hit("git-hooks", rel)

        if size > MAX_FILE_BYTES * 4 and ext not in CODE_EXT:
            continue
        if total > MAX_TOTAL_BYTES:
            continue
        is_code = ext in CODE_EXT
        is_script = ext in SCRIPT_EXT or name in ("dockerfile", "makefile")
        is_json = ext == ".json"
        is_svg = ext == ".svg"
        if not (is_code or is_script or is_json or is_svg or name in ("tasks.json",)):
            continue
        text = _read(p)
        total += len(text)

        if is_svg and re.search(r"<script|onload\s*=|javascript:", text, re.I):
            flags.append(_flag("svg-script", "warn", "An image file contains script", rel, file=rel))

        if "core.hooksPath" in text or "core.hookspath" in text:
            hit("hookspath", rel)

        if is_code or is_script or is_json:
            for m in PIPE_SHELL.finditer(text):
                hit("pipe-to-shell", rel)
                break
            for rx, what in SENSITIVE:
                if re.search(rx, text):
                    sensitive.setdefault(what, rel)

        if is_code:
            configish = bool(CONFIGISH.search(rel))
            reasons = []
            for kw, label in ((r"\beval\s*\(", "eval("), (r"\bnew\s+Function\s*\(", "new Function"),
                              (r"\batob\s*\(", "atob"),
                              (r"""Buffer\.from\([^)]{0,4000},\s*['"`]base64['"`]\)""", "Buffer.from(…, 'base64')")):
                if re.search(kw, text):
                    reasons.append(label)
            hexesc = len(re.findall(r"\\x[0-9a-fA-F]{2}", text))
            if hexesc >= 60:
                reasons.append(f"{hexesc} \\x escapes")
            ox = len(set(re.findall(r"\b_0x[0-9a-f]{4,6}\b", text)))
            if ox >= 10:
                reasons.append(f"{ox} _0x… names (obfuscator output)")
            if B64_BLOB.search(text):
                reasons.append("long base64 blob")
            if HEX_BLOB.search(text):
                reasons.append("long hex blob")
            if reasons and not name.endswith(".min.js"):
                strong = any(r.startswith(("eval", "new Function")) for r in reasons) and \
                    any("blob" in r or "escapes" in r or "_0x" in r or "base64" in r or r == "atob" for r in reasons)
                sev = "high" if (strong or (configish and len(reasons) >= 1 and any(
                    "base64" in r or "blob" in r or "_0x" in r for r in reasons))) else "warn"
                flags.append(_flag("obfuscation", sev,
                                   "Hidden or encoded code" + (" in a config/asset file" if configish else ""),
                                   f"{rel}: {', '.join(reasons)}", file=rel))
            # base64 literals that decode to an address: the classic way to hide a C2 server
            for m in B64_CALL.finditer(text):
                try:
                    raw = base64.b64decode(m.group(2) + "=" * (-len(m.group(2)) % 4), validate=True)
                    s = raw.decode("ascii").strip()
                except (binascii.Error, ValueError, UnicodeDecodeError):
                    continue
                if (IP_RE.fullmatch(s) and _public_ip(s)) or re.match(r"^https?://", s) or DOMAIN_RE.match(s):
                    decoded.append((rel, s))
            if CHILD.search(text):
                hit("child-process-net" if EXEC_NET.search(text) else "child-process", rel)

        if is_code or is_script or (is_json and name != "package-lock.json"):
            for m in IP_RE.finditer(text):
                if _public_ip(m.group(1)) and not re.search(r"version|\d\.\d\.\d\.\d-", text[max(0, m.start() - 12):m.start()], re.I):
                    ips.setdefault(m.group(1), rel)
            for port in C2_PORTS:
                if re.search(rf"(port\s*[:=]\s*['\"]?{port}\b|:{port}\b|['\"]{port}['\"])", text):
                    c2.append((rel, port))

        if name == "package.json":
            flags += _package_flags(rel, text)
        if name == "tasks.json" and "/.vscode/" in "/" + low:
            flags += _vscode_flags(rel, text)

    if hits.get("git-hooks"):
        flags.append(_flag("git-hooks", "info", "Ships git hooks",
                           f"{', '.join(hits['git-hooks'][:3])} — installed by husky/hooksPath during npm install"))
    if hits.get("hookspath"):
        flags.append(_flag("hookspath", "warn", "Changes git's hooks folder (core.hooksPath)",
                           ", ".join(hits["hookspath"][:3]), file=hits["hookspath"][0]))
    if hits.get("pipe-to-shell"):
        flags.append(_flag("pipe-to-shell", "high", "Downloads a script and pipes it into a shell",
                           ", ".join(hits["pipe-to-shell"][:3]), file=hits["pipe-to-shell"][0]))
    if hits.get("child-process-net"):
        flags.append(_flag("child-process-net", "high", "Runs network tools from code (curl/wget/powershell)",
                           ", ".join(hits["child-process-net"][:3]), file=hits["child-process-net"][0]))
    elif hits.get("child-process"):
        flags.append(_flag("child-process", "info", "Starts other programs (child_process)",
                           ", ".join(hits["child-process"][:3]), file=hits["child-process"][0]))
    if decoded:
        flags.append(_flag("hidden-address", "high", "Hides a server address in base64",
                           f"{decoded[0][0]}: decodes to " + ", ".join(_short(s, 60) for _, s in decoded[:3]),
                           file=decoded[0][0]))
    if c2:
        ports = sorted({p for _, p in c2})
        flags.append(_flag("c2-port", "high", f"Uses port {'/'.join(ports)} (known stealer servers)",
                           f"{c2[0][0]} — BeaverTail/InvisibleFerret servers listen on 1224/1244/1245",
                           file=c2[0][0]))
    if ips:
        shown = list(ips.items())[:4]
        flags.append(_flag("raw-ip", "warn", "Hard-coded IP address" + ("es" if len(ips) > 1 else ""),
                           ", ".join(f"{ip} ({f})" for ip, f in shown), file=shown[0][1]))
    if sensitive:
        what = list(sensitive)
        flags.append(_flag("credential-paths", "high", "Names wallet / credential files",
                           f"{', '.join(what[:4])} — in {sensitive[what[0]]}", file=sensitive[what[0]]))
    return flags


def _package_flags(rel, text):
    out = []
    try:
        pkg = json.loads(text)
    except ValueError:
        return [_flag("package-json-invalid", "info", "package.json isn't valid JSON", rel, file=rel)]
    if not isinstance(pkg, dict):
        return out
    scripts = pkg.get("scripts") if isinstance(pkg.get("scripts"), dict) else {}
    for k in LIFECYCLE:
        cmd = scripts.get(k)
        if isinstance(cmd, str) and cmd.strip():
            risky = re.search(r"curl|wget|node\s+-e|base64|https?://|powershell|\|\s*(ba)?sh|eval", cmd, re.I)
            if k in ("prepare",) and re.fullmatch(r"\s*(husky( install)?|npm run build|tsc|.*build.*)\s*", cmd) and not risky:
                sev = "info"
            else:
                sev = "high" if risky else "warn"
            out.append(_flag("lifecycle-script", sev, f"Runs code on npm install ({k})",
                             f"{rel}: \"{k}\": {_short(cmd, 120)}", file=rel))
    deps = {}
    for sect in ("dependencies", "devDependencies", "optionalDependencies"):
        if isinstance(pkg.get(sect), dict):
            deps.update(pkg[sect])
    local = [f"{n} → {_short(v, 50)}" for n, v in deps.items() if isinstance(v, str) and v.startswith(("file:", "link:"))]
    if local:
        out.append(_flag("local-dep", "warn", "Depends on code shipped inside the repo (file: dependency)",
                         f"{rel}: {', '.join(local[:3])}", file=rel))
    urls = [f"{n} → {_short(v, 60)}" for n, v in deps.items()
            if isinstance(v, str) and re.match(r"(https?:|git\+|git:|github:|[\w-]+/[\w.-]+(#.*)?$)", v)]
    if urls:
        out.append(_flag("url-dep", "warn", "Installs a dependency straight from a URL or git repo",
                         f"{rel}: {', '.join(urls[:3])}", file=rel))
    squats = [f"{n} (looks like {typosquat_of(n)})" for n in deps if typosquat_of(n)]
    if squats:
        out.append(_flag("typosquat", "high", "Dependency name one letter off a popular package",
                         f"{rel}: {', '.join(squats[:3])}", file=rel))
    return out


def _vscode_flags(rel, text):
    data = _jsonc(text)
    tasks = data.get("tasks") if isinstance(data, dict) else None
    out = []
    if isinstance(tasks, list):
        for t in tasks:
            if not isinstance(t, dict):
                continue
            ro = t.get("runOptions") if isinstance(t.get("runOptions"), dict) else {}
            if ro.get("runOn") != "folderOpen":
                continue
            cmds = []
            for src in [t] + [t.get(k) for k in ("windows", "linux", "osx") if isinstance(t.get(k), dict)]:
                c = src.get("command")
                if isinstance(c, str):
                    args = src.get("args") if isinstance(src.get("args"), list) else []
                    cmds.append(" ".join([c] + [str(a) for a in args]))
            out.append(_flag("vscode-folderopen", "high", "Runs a command as soon as you open the folder in VS Code",
                             f"{rel}: {_short(' | '.join(dict.fromkeys(cmds)) or str(t.get('label') or 'task'), 160)}",
                             file=rel))
    elif re.search(r"""['"]runOn['"]\s*:\s*['"]folderOpen""", text):
        out.append(_flag("vscode-folderopen", "high", "Runs a command as soon as you open the folder in VS Code",
                         f"{rel}: runOn folderOpen (file isn't plain JSON)", file=rel))
    return out


# ---------------------------------------------------------------------------------------------- network
def fetch_json(url, timeout=3.0, headers=None, max_bytes=2_000_000):
    """GET url -> (json, response headers). Raises on any error (callers fail soft). Tests monkeypatch this."""
    req = urllib.request.Request(url, headers={"User-Agent": "burner-precheck", "Accept": "application/json",
                                               **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read(max_bytes).decode("utf-8", errors="replace")), dict(r.headers)


def _age_days(iso):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).days


def _ago(days):
    if days is None:
        return "unknown"
    if days < 60:
        return f"{days} days ago"
    if days < 730:
        return f"{days // 30} months ago"
    return f"{days // 365} years ago"


def github_repo(url):
    m = re.match(r"^https?://(www\.)?github\.com/([A-Za-z0-9-]{1,39})/([\w.-]{1,100}?)(\.git)?/?$", (url or "").strip())
    return (m.group(2), m.group(3)) if m else None


def _github(owner, name):
    tok = os.environ.get("GITHUB_TOKEN")
    hdr = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {tok}"} if tok else {})}
    out = []
    try:
        u, _ = fetch_json(f"https://api.github.com/users/{owner}", headers=hdr)
        age = _age_days(u.get("created_at"))
        kind = "organisation" if u.get("type") == "Organization" else "account"
        facts = f"{owner}: created {_ago(age)}, {u.get('public_repos', 0)} public repos, {u.get('followers', 0)} followers"
        if age is not None and age < 180:
            out.append(_flag("gh-new-account", "high" if age < 30 else "warn", f"Brand-new GitHub {kind}", facts,
                             source="github"))
        elif (u.get("followers") or 0) < 3 and (u.get("public_repos") or 0) <= 3:
            out.append(_flag("gh-thin-account", "warn", f"GitHub {kind} with almost no history", facts, source="github"))
        else:
            out.append(_flag("gh-account", "info", f"GitHub {kind}", facts, source="github"))
    except Exception as e:
        out.append(_flag("gh-unavailable", "info", "Couldn't check the GitHub account", _short(e, 100), source="github"))
        return out
    try:
        r, _ = fetch_json(f"https://api.github.com/repos/{owner}/{name}", headers=hdr)
        created, pushed = _age_days(r.get("created_at")), _age_days(r.get("pushed_at"))
        facts = (f"created {_ago(created)}, last push {_ago(pushed)}, {r.get('stargazers_count', 0)} stars"
                 + (", a fork" if r.get("fork") else ""))
        commits = None
        try:
            c, h = fetch_json(f"https://api.github.com/repos/{owner}/{name}/commits?per_page=1", headers=hdr)
            link = h.get("Link") or h.get("link") or ""
            m = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
            commits = int(m.group(1)) if m else (len(c) if isinstance(c, list) else None)
        except Exception:
            pass
        if commits is not None:
            facts += f", {commits} commit{'s' if commits != 1 else ''}"
        if created is not None and created < 30:
            out.append(_flag("gh-new-repo", "warn", "Repo created in the last month", facts, source="github"))
        elif commits is not None and commits <= 2:
            out.append(_flag("gh-few-commits", "info", f"Only {commits} commit{'s' if commits != 1 else ''}", facts,
                             source="github"))
        else:
            out.append(_flag("gh-repo", "info", "Repo history", facts, source="github"))
    except Exception:
        pass
    return out


def direct_deps(repo, limit=15):
    try:
        pkg = json.loads(_read(Path(repo) / "package.json") or "{}")
    except ValueError:
        return []
    names = []
    for sect in ("dependencies", "devDependencies"):
        d = pkg.get(sect) if isinstance(pkg, dict) else None
        if isinstance(d, dict):
            names += [n for n, v in d.items() if isinstance(v, str) and not v.startswith(("file:", "link:", "http", "git"))
                      and re.fullmatch(r"(@[a-z0-9-~][a-z0-9-._~]*/)?[a-z0-9-~][a-z0-9-._~]*", n)]
    return list(dict.fromkeys(names))[:limit]


def _npm_one(name):
    """(name, days since first publish | None, exists). Popular packages are skipped via the downloads count."""
    try:
        d, _ = fetch_json(f"https://registry.npmjs.org/{name.replace('/', '%2F')}", max_bytes=3_000_000)
        return name, _age_days((d.get("time") or {}).get("created")), True
    except urllib.error.HTTPError as e:
        return name, None, e.code != 404
    except Exception:
        return name, None, None


def _npm(deps, pool):
    out = []
    if not deps:
        return out
    popular = set()
    unscoped = [d for d in deps if not d.startswith("@")]
    if unscoped:   # one tiny bulk call; packages with real usage aren't brand-new
        try:
            d, _ = fetch_json("https://api.npmjs.org/downloads/point/last-week/" + ",".join(unscoped))
            if len(unscoped) == 1:
                d = {unscoped[0]: d}
            popular = {k for k, v in (d or {}).items() if isinstance(v, dict) and (v.get("downloads") or 0) > 50_000}
        except Exception:
            pass
    todo = [d for d in deps if d not in popular]
    results = list(pool.map(_npm_one, todo)) if todo else []
    new = [(n, a) for n, a, _ in results if a is not None and a < 30]
    missing = [n for n, a, ok in results if ok is False]
    if new:
        out.append(_flag("npm-new-package", "warn", "Depends on a package published in the last 30 days",
                         ", ".join(f"{n} ({a} days old)" for n, a in new[:4]), source="npm"))
    if missing:
        out.append(_flag("npm-missing", "warn", "Depends on a package that isn't on npm",
                         ", ".join(missing[:4]), source="npm"))
    checked = len(popular) + sum(1 for _, a, _ in results if a is not None)
    if not new and not missing and checked:
        out.append(_flag("npm-ok", "info", "Dependencies are established packages",
                         f"{checked} of {len(deps)} direct dependencies checked on npm", source="npm"))
    return out


SKIP_DOMAINS = re.compile(r"(^|\.)(github\.com|gitlab\.com|bitbucket\.org|linkedin\.com|t\.me|telegram\.org|"
                          r"gmail\.com|outlook\.com|hotmail\.com|yahoo\.com|proton\.me|protonmail\.com|icloud\.com|"
                          r"google\.com|calendly\.com|zoom\.us|example\.\w+|discord\.(gg|com)|wa\.me|whatsapp\.com)$", re.I)


def message_domain(message):
    """The company domain in a recruiter message (email or link), skipping code hosts and webmail."""
    if not message:
        return None
    cands = re.findall(r"[\w.+-]+@([\w-]+(?:\.[\w-]+)+)", message) + \
        re.findall(r"https?://(?:www\.)?([\w-]+(?:\.[\w-]+)+)", message) + \
        re.findall(r"(?<![@\w.])(?:www\.)?((?:[a-z0-9-]+\.)+(?:com|io|ai|co|xyz|net|org|dev|app|tech|finance|capital|"
                   r"exchange|network|group|ltd|inc|uk|de|in|sg))(?![\w-]|\.\w)", message, re.I)
    for c in cands:
        c = c.lower().rstrip(".")
        if SKIP_DOMAINS.search(c) or not DOMAIN_RE.match(c):
            continue
        parts = c.split(".")
        two_level = len(parts) > 2 and parts[-2] in ("co", "com", "org", "net", "ac") and len(parts[-1]) == 2
        return ".".join(parts[-3:] if two_level else parts[-2:])
    return None


def _rdap(domain):
    try:
        d, _ = fetch_json(f"https://rdap.org/domain/{domain}")
    except Exception as e:
        return [_flag("domain-unavailable", "info", "Couldn't look up the company's domain", f"{domain}: {_short(e, 80)}",
                      source="rdap")]
    reg = next((e.get("eventDate") for e in d.get("events") or [] if e.get("eventAction") == "registration"), None)
    age = _age_days(reg) if reg else None
    if age is None:
        return [_flag("domain-age", "info", "Company domain", f"{domain}: registration date not published", source="rdap")]
    if age < 90:
        return [_flag("domain-new", "high" if age < 30 else "warn", "Company domain registered recently",
                      f"{domain}: registered {_ago(age)}", source="rdap")]
    return [_flag("domain-age", "info", "Company domain", f"{domain}: registered {_ago(age)}", source="rdap")]


def network_flags(repo=None, url=None, message=None, budget=6.0):
    """Provenance signals. Each lookup <= 3 s, all of them together <= `budget` s; anything slower is dropped."""
    gh = github_repo(url)
    deps = direct_deps(repo) if repo else []
    dom = message_domain(message)
    sources = {"github": "skipped" if not gh else "timeout", "npm": "skipped" if not deps else "timeout",
               "rdap": "skipped" if not dom else "timeout"}
    flags = []
    pool = cf.ThreadPoolExecutor(max_workers=12, thread_name_prefix="precheck")
    jobs = {}
    if gh:
        jobs[pool.submit(_github, *gh)] = "github"
    if deps:
        jobs[pool.submit(_npm, deps, pool)] = "npm"
    if dom:
        jobs[pool.submit(_rdap, dom)] = "rdap"
    try:
        for fut in cf.as_completed(jobs, timeout=budget):
            try:
                got = fut.result()
                flags += got
                sources[jobs[fut]] = "error" if any(f["id"].endswith("unavailable") for f in got) else "ok"
            except Exception:
                sources[jobs[fut]] = "error"
    except cf.TimeoutError:
        pass
    pool.shutdown(wait=False, cancel_futures=True)
    return flags, sources


# ---------------------------------------------------------------------------------------------- entry point
SEV_ORDER = {"high": 0, "warn": 1, "info": 2}


def run(repo, url=None, message=None, network=True, budget=6.0):
    """The whole pre-check. Never raises: a broken check becomes an info flag."""
    t0 = time.time()
    flags, sources = [], {"files": "ok"}
    try:
        flags += static_flags(repo)
    except Exception as e:
        sources["files"] = "error"
        flags.append(_flag("precheck-error", "info", "Part of the file check failed", _short(e, 120)))
    if network:
        try:
            nf, ns = network_flags(repo, url, message, budget=budget)
            flags += nf
            sources.update(ns)
        except Exception as e:
            flags.append(_flag("precheck-error", "info", "The provenance check failed", _short(e, 120), source="network"))
    flags.sort(key=lambda f: SEV_ORDER.get(f["severity"], 3))
    counts = {s: sum(1 for f in flags if f["severity"] == s) for s in ("high", "warn", "info")}
    return {"flags": flags, "counts": counts, "ms": round((time.time() - t0) * 1000), "sources": sources, "note": NOTE}


def summary(pc):
    c = pc.get("counts") or {}
    n = (c.get("high") or 0) + (c.get("warn") or 0)
    if not n:
        return f"no warning signs found ({pc.get('ms', 0)} ms; warnings only, the verdict comes from running it)"
    return (f"{n} warning sign{'s' if n != 1 else ''} before running anything ({c.get('high', 0)} serious) in "
            f"{pc.get('ms', 0)} ms; warnings only, the verdict comes from running it")


def main():
    import argparse
    import shutil
    import tempfile
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--message")
    ap.add_argument("--no-network", action="store_true")
    a = ap.parse_args()
    msg = Path(a.message).read_text(encoding="utf-8") if a.message else None
    tmp = None
    if os.path.isdir(a.target):
        repo, url = Path(a.target), None
    else:
        from . import scan   # the same safe clone: hooks and symlinks off, nothing from the repo executed
        tmp = Path(tempfile.mkdtemp(prefix="burner-pre-"))
        repo, url = tmp / "repo", a.target
        scan.clone(url, repo)
    try:
        pc = run(repo, url=url, message=msg, network=not a.no_network)
    finally:
        if tmp:
            shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(pc, indent=1))
    print(summary(pc))


if __name__ == "__main__":
    main()
