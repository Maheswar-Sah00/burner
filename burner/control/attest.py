"""Burner Verified: a signed statement, per commit, that Burner ran this repo and what it saw.

An employer puts the badge in the take-home's README (or runs the GitHub Action on every push). A candidate who gets
the link can then check two things before running anything: who owns the repo (GitHub's own verified-organisation
flag and site), and that this exact commit was burned in a throwaway Vultr VM with nothing malicious observed.

The statement is canonical JSON signed with Ed25519. Anyone can check it with the public key at
/.well-known/burner-attest.pub; the verify page does it in the browser. A statement says what was observed in one
run of one commit. It is never a guarantee, and any new commit voids it.
"""
import base64
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import threading
import time
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

ROOT = Path(__file__).resolve().parents[2]
KEY_FILE = Path(os.environ.get("BURNER_ATTEST_KEY", ROOT / ".burner" / "attest_ed25519.pem"))
STORE = Path(os.environ.get("BURNER_ATTEST_DIR", ROOT / "scans" / "_attest"))
PUBLIC_URL = os.environ.get("BURNER_PUBLIC_URL", "https://139-84-215-1.sslip.io").rstrip("/")
TYPE = "burner.verified/take-home/v1"
CLEAN = "NO MALICIOUS BEHAVIOUR OBSERVED"
RESULTS = {"MALICIOUS": "malicious", "SUSPICIOUS": "suspicious", CLEAN: "clean", "INCONCLUSIVE": "inconclusive"}
GH_REPO = re.compile(r"^https://github\.com/([A-Za-z0-9](?:[A-Za-z0-9-]{0,38}))/([A-Za-z0-9._-]{1,100})$")
SHA = re.compile(r"[0-9a-f]{40}")
HISTORY = 50          # statements kept in a repo's index
OWNER_TTL = 3600      # GitHub owner facts cached this long
HEAD_TTL = 120        # `git ls-remote` of the default branch cached this long

_lock = threading.Lock()
_key = None
_owner_cache = {}
_head_cache = {}


# ---- keys -----------------------------------------------------------------------------------------------------
def private_key():
    """The signing key; created on first use and kept in .burner/ (gitignored, shipped by deploy.py)."""
    global _key
    with _lock:
        if _key is None:
            if KEY_FILE.exists():
                _key = serialization.load_pem_private_key(KEY_FILE.read_bytes(), password=None)
            else:
                _key = Ed25519PrivateKey.generate()
                KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
                KEY_FILE.write_bytes(_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                                        serialization.NoEncryption()))
                try:
                    os.chmod(KEY_FILE, 0o600)
                except OSError:
                    pass
        return _key


def public_raw():
    return private_key().public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def public_b64():
    return base64.b64encode(public_raw()).decode()


def public_pem():
    return private_key().public_key().public_bytes(serialization.Encoding.PEM,
                                                   serialization.PublicFormat.SubjectPublicKeyInfo).decode()


def key_id(raw=None):
    return hashlib.sha256(raw or public_raw()).hexdigest()[:16]


# ---- signing --------------------------------------------------------------------------------------------------
def canonical(obj):
    """The exact bytes that are signed: sorted keys, no whitespace, UTF-8. The browser rebuilds the same bytes."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign(statement):
    sig = private_key().sign(canonical(statement))
    return {"statement": statement, "signature": base64.b64encode(sig).decode(), "alg": "Ed25519", "key_id": key_id()}


def verify(envelope, pub_raw=None):
    """True if the envelope's signature matches its statement under Burner's key (or `pub_raw`)."""
    try:
        pub = Ed25519PublicKey.from_public_bytes(pub_raw or public_raw())
        pub.verify(base64.b64decode(envelope["signature"]), canonical(envelope["statement"]))
        return True
    except Exception:
        return False


# ---- who owns the repo ----------------------------------------------------------------------------------------
def _iso_days(iso):
    try:
        t = dt.datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (dt.datetime.now(dt.timezone.utc) - t).days
    except ValueError:
        return None


def _gh_json(url, tries=2):
    from burner.control import precheck   # shared fetcher (tests monkeypatch precheck.fetch_json)
    tok = os.environ.get("GITHUB_TOKEN")
    hdr = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {tok}"} if tok else {})}
    for i in range(tries):   # GitHub's API has the odd 5xx/timeout; one retry covers most of them
        try:
            return precheck.fetch_json(url, timeout=8.0, headers=hdr)[0]
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5)


def owner_identity(owner):
    """What GitHub itself says about the account that owns the repo. `verified` is GitHub's verified-domain flag
    for organisations (GET /orgs/{org} is_verified): the org proved it controls its website's domain."""
    hit = _owner_cache.get(owner.lower())
    if hit and time.monotonic() - hit[0] < (OWNER_TTL if "error" not in hit[1] else 60):   # retry failures soon
        return hit[1]
    out = {"login": owner, "kind": "unknown", "verified": False, "site": None, "name": None, "age_days": None,
           "checked_at": _now()}
    try:
        u = _gh_json(f"https://api.github.com/users/{owner}")
        out.update(login=u.get("login") or owner, name=u.get("name"), age_days=_iso_days(u.get("created_at")),
                   site=(u.get("blog") or None), public_repos=u.get("public_repos"))
        if u.get("type") == "Organization":
            out["kind"] = "organisation"
            o = _gh_json(f"https://api.github.com/orgs/{owner}")
            out.update(verified=bool(o.get("is_verified")), site=(o.get("blog") or out["site"]),
                       name=o.get("name") or out["name"])
        else:
            out["kind"] = "personal account"
    except Exception as e:
        out["error"] = f"couldn't ask GitHub ({type(e).__name__})"
    if out["site"] and not str(out["site"]).startswith("http"):
        out["site"] = "https://" + str(out["site"])
    _owner_cache[owner.lower()] = (time.monotonic(), out)
    return out


def owner_summary(ident):
    """One plain line for the badge page."""
    if ident.get("kind") == "organisation" and ident.get("verified"):
        dom = re.sub(r"^https?://(www\.)?", "", ident.get("site") or "").strip("/")
        return f"GitHub-verified organisation{f' ({dom})' if dom else ''}"
    if ident.get("kind") == "organisation":
        return "GitHub organisation, not verified by GitHub"
    if ident.get("kind") == "personal account":
        return "a personal GitHub account, not a company organisation"
    return "unknown owner"


# ---- the statement --------------------------------------------------------------------------------------------
def _now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def subject_of(report):
    """(owner, name, source) when the report scanned a pinned GitHub commit, else None."""
    src = (report or {}).get("source") or {}
    m = GH_REPO.match(str(src.get("repo") or "").removesuffix(".git"))
    if not m or not SHA.fullmatch(str(src.get("commit") or "")):
        return None
    return m.group(1), m.group(2), src


def statement(report, scan_id, ident=None):
    """The facts Burner signs for one scan of one GitHub commit, or None if the scan can't be attested."""
    subj = subject_of(report)
    verdict = (report or {}).get("verdict")
    if not subj or verdict not in RESULTS:
        return None
    owner, name, src = subj
    vm = report.get("vm") or {}
    deletion = vm.get("deletion") or {}
    cov = report.get("coverage") or {}
    ran = [{"name": s.get("name"), "rc": s.get("rc"), **({"outcome": s["outcome"]} if s.get("outcome") else {})}
           for s in (cov.get("steps") or report.get("steps") or [])][:12]
    stolen = report.get("stolen") or []
    return {
        "type": TYPE,
        "subject": {"repo": f"https://github.com/{owner}/{name}", "commit": src["commit"],
                    "branch": src.get("branch"), "committed_at": src.get("committed_at")},
        "owner": {k: (ident or {}).get(k) for k in ("login", "kind", "verified", "site", "name")},
        "result": RESULTS[verdict],
        "verdict": verdict,
        "headline": (report.get("headline") or "")[:300],
        "burn": {
            "scan_id": scan_id, "report": f"{PUBLIC_URL}/r/{scan_id}",
            "ran": ran, "app_started": bool(cov.get("started")),
            "fake_secrets_planted": len(report.get("bait") or []),
            "fake_secrets_sent": len({s.get("secret") for s in stolen if isinstance(s, dict) and s.get("secret")}),
            "sandbox": "gVisor (runsc) container on a throwaway Vultr VM, fake internet, no real secrets",
            "vm": {"region": vm.get("region"), "plan": vm.get("plan"), "alive_secs": vm.get("lifetime_secs"),
                   "deleted": deletion.get("http_status") == 404, "deleted_confirmed_at": deletion.get("confirmed_at")},
        },
        "issuer": {"name": "Burner", "url": PUBLIC_URL, "key": f"{PUBLIC_URL}/.well-known/burner-attest.pub"},
        "issued_at": _now(),
        "meaning": ("Observed in one run of this exact commit. Not a guarantee; any new commit needs a new burn."),
    }


# ---- storage --------------------------------------------------------------------------------------------------
def _dir(owner, name):
    return STORE / "github.com" / owner.lower() / name.lower()


def _obj_key(owner, name, leaf):
    return f"attest/github.com/{owner.lower()}/{name.lower()}/{leaf}"


def _write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _backup(owner, name, leaf, obj):
    """Copy to Vultr Object Storage so statements outlive the control VM (best effort, in the background)."""
    if os.environ.get("BURNER_MOCK") == "1" or os.environ.get("BURNER_ATTEST_NO_S3") == "1":
        return

    def go():
        try:
            from burner.control import evidence
            evidence.put_json(_obj_key(owner, name, leaf), obj)
        except Exception as e:
            print(f"attest {owner}/{name}/{leaf}: object storage copy failed:", str(e)[:200])
    threading.Thread(target=go, daemon=True).start()


def _restore(owner, name, leaf):
    if os.environ.get("BURNER_MOCK") == "1" or os.environ.get("BURNER_ATTEST_NO_S3") == "1":
        return None
    try:
        from burner.control import evidence
        return evidence.get_json(_obj_key(owner, name, leaf))
    except Exception:
        return None


def history(owner, name):
    """Newest-first list of {commit, result, issued_at, scan_id, branch} for a repo."""
    f = _dir(owner, name) / "index.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    got = _restore(owner, name, "index.json")
    if got is not None:
        _write(f, got)
        return got
    return []


def load(owner, name, commit):
    if not SHA.fullmatch(commit or ""):
        return None
    f = _dir(owner, name) / f"{commit}.json"
    if f.exists():
        return json.loads(f.read_text(encoding="utf-8"))
    got = _restore(owner, name, f"{commit}.json")
    if got is not None:
        _write(f, got)
    return got


def issue(report, scan_id):
    """Sign and store a statement for a finished scan. Returns the envelope, or None if not attestable."""
    subj = subject_of(report)
    if not subj:
        return None
    owner, name, _ = subj
    st = statement(report, scan_id, owner_identity(owner))
    if not st:
        return None
    env = sign(st)
    commit = st["subject"]["commit"]
    with _lock:
        _write(_dir(owner, name) / f"{commit}.json", env)
        idx = [h for h in history(owner, name) if h.get("scan_id") != scan_id]
        idx.insert(0, {"commit": commit, "result": st["result"], "issued_at": st["issued_at"], "scan_id": scan_id,
                       "branch": st["subject"]["branch"]})
        idx = idx[:HISTORY]
        _write(_dir(owner, name) / "index.json", idx)
    _backup(owner, name, f"{commit}.json", env)
    _backup(owner, name, "index.json", idx)
    return env


def summary(env):
    """What the report carries about its own statement."""
    st = env["statement"]
    owner, name = st["subject"]["repo"].rsplit("/", 2)[-2:]
    return {"result": st["result"], "commit": st["subject"]["commit"], "key_id": env["key_id"],
            "verify": f"/v/github.com/{owner}/{name}?commit={st['subject']['commit']}",
            "badge": f"/badge/github.com/{owner}/{name}.svg"}


# ---- the badge ------------------------------------------------------------------------------------------------
def head_commit(owner, name, ls_remote=None):
    """The default branch's current commit (cached). None if the repo is gone or unreachable."""
    k = f"{owner}/{name}".lower()
    hit = _head_cache.get(k)
    if hit and time.monotonic() - hit[0] < HEAD_TTL:
        return hit[1]
    sha = None
    try:
        if ls_remote:
            sha = ls_remote(owner, name)
        else:
            p = subprocess.run(["git", "-c", "credential.helper=", "ls-remote", "--", f"https://github.com/{owner}/{name}",
                                "HEAD"], capture_output=True, text=True, timeout=15,
                               env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"})
            sha = (p.stdout.split() or [None])[0] if p.returncode == 0 else None
    except Exception:
        sha = None
    _head_cache[k] = (time.monotonic(), sha)
    return sha


def state(owner, name, ls_remote=None):
    """Badge state for the repo's default branch right now:
    clean / malicious / suspicious / inconclusive (this exact HEAD was burned), changed (burned before, HEAD moved
    since), none (never burned), gone (repo unreachable)."""
    hist = history(owner, name)
    head = head_commit(owner, name, ls_remote)
    at_head = next((h for h in hist if h["commit"] == head), None) if head else None
    last_clean = next((h for h in hist if h["result"] == "clean"), None)
    if at_head:
        return {"state": at_head["result"], "commit": head, "scan_id": at_head["scan_id"],
                "issued_at": at_head["issued_at"], "head": head, "last_clean": last_clean}
    if head is None:
        return {"state": "gone" if hist else "none", "head": None, "last_clean": last_clean,
                "commit": hist[0]["commit"] if hist else None}
    if hist:
        return {"state": "changed", "head": head, "commit": hist[0]["commit"], "last": hist[0],
                "last_clean": last_clean}
    return {"state": "none", "head": head, "commit": None, "last_clean": None}


BADGE = {   # state -> (right-hand text, colour)
    "clean": ("burned clean", "#2f9e44"),
    "malicious": ("malicious", "#e5392c"),
    "suspicious": ("suspicious", "#e0a019"),
    "inconclusive": ("inconclusive", "#7a7a7a"),
    "changed": ("changed since burn", "#e0a019"),
    "none": ("not burned yet", "#7a7a7a"),
    "gone": ("repo unreachable", "#7a7a7a"),
}


def _w(text, px=6.6):
    return int(len(text) * px + 18)


def badge_svg(st):
    """A shields-style badge in Burner's colours: [flame burner | burned clean · 1a2b3c4]."""
    label, colour = BADGE.get(st.get("state"), BADGE["none"])
    sha = (st.get("commit") or "")[:7] if st.get("state") in ("clean", "malicious", "suspicious", "inconclusive") else ""
    right = f"{label} · {sha}" if sha else label
    lw, rw = 74, _w(right)
    w = lw + rw
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="20" role="img" aria-label="Burner: {esc(right)}">
<title>Burner: {esc(right)}</title>
<linearGradient id="s" x2="0" y2="100%"><stop offset="0" stop-color="#bbb" stop-opacity=".1"/><stop offset="1" stop-opacity=".1"/></linearGradient>
<clipPath id="r"><rect width="{w}" height="20" rx="3" fill="#fff"/></clipPath>
<g clip-path="url(#r)"><rect width="{lw}" height="20" fill="#0a0a0a"/><rect x="{lw}" width="{rw}" height="20" fill="{colour}"/><rect width="{w}" height="20" fill="url(#s)"/></g>
<path fill="#ff6a2b" transform="translate(6 3) scale(.5)" d="M16.2 9.6c.5 2.5-.9 3.9-2.2 5.2-1.2 1.2-2.2 2.6-2.2 4.5a4.4 4.4 0 0 0 8.8 0c0-1.8-.8-3-1.7-4 .1 1.2-.4 2.2-1.4 2.6.3-2.6-.3-5.6-1.3-8.3z"/>
<g fill="#fff" text-anchor="middle" font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">
<text x="{(lw + 14) / 2}" y="14">burner</text><text x="{lw + rw / 2}" y="14">{esc(right)}</text></g>
</svg>"""
