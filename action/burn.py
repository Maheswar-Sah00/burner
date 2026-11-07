"""GitHub Action: burn this repo's branch on Burner, report it, and act on the verdict.

Standard library only, so it runs on any runner. Burner clones the branch, runs it like a candidate in a throwaway
Vultr VM full of fake secrets, signs a Burner Verified statement for the exact commit, and deletes the VM.
Then this script writes the job summary, comments on the PR, opens an issue on a bad push, and fails the check.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

BURNER = os.environ.get("BURNER_URL", "https://139-84-215-1.sslip.io").rstrip("/")
FAIL_ON = {v.strip().upper() for v in os.environ.get("FAIL_ON", "MALICIOUS,SUSPICIOUS").split(",") if v.strip()}
TIMEOUT = 60 * int(os.environ.get("TIMEOUT_MIN", "20") or 20)
EVENT = os.environ.get("EVENT_NAME", "push")
REPO = os.environ.get("REPO", "")
IS_PR = EVENT in ("pull_request", "pull_request_target") and os.environ.get("PR_NUMBER")
HEAD_REPO = (os.environ.get("HEAD_REPO") or REPO) if IS_PR else REPO
REF = (os.environ.get("HEAD_REF") if IS_PR else os.environ.get("REF_NAME")) or "main"
SHA = os.environ.get("SHA", "")
TOKEN = os.environ.get("GH_TOKEN", "")
UA = {"User-Agent": "burner-verified-action", "Content-Type": "application/json"}


def http(method, url, body=None, headers=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={**UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode() or "null")


def gh(method, path, body):
    if not TOKEN:
        print("::warning::no github-token, skipping", path)
        return None
    try:
        return http(method, f"https://api.github.com/repos/{REPO}{path}", body,
                    {"Authorization": f"Bearer {TOKEN}", "Accept": "application/vnd.github+json"})
    except urllib.error.HTTPError as e:
        print(f"::warning::GitHub {method} {path}: HTTP {e.code} {e.read()[:200]!r} (check the workflow's permissions)")
        return None


def out(key, value):
    f = os.environ.get("GITHUB_OUTPUT")
    if f:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(f"{key}={value}\n")


def summary(md):
    f = os.environ.get("GITHUB_STEP_SUMMARY")
    if f:
        with open(f, "a", encoding="utf-8") as fh:
            fh.write(md + "\n")
    print(md)


def start(url):
    """POST /api/scan, waiting politely while Burner is busy (429)."""
    deadline = time.time() + TIMEOUT
    wait = 30
    while True:
        try:
            return http("POST", f"{BURNER}/api/scan", {"repo": url})["id"]
        except urllib.error.HTTPError as e:
            msg = e.read().decode(errors="replace")[:300]
            if e.code == 429 and time.time() + wait < deadline:
                print(f"Burner is busy ({msg.strip()}); retrying in {wait}s")
                time.sleep(wait)
                wait = min(wait * 2, 180)
                continue
            raise SystemExit(f"::error::Burner refused the scan: HTTP {e.code} {msg}")


def wait_for(jid):
    deadline = time.time() + TIMEOUT
    last = 0
    while time.time() < deadline:
        try:
            d = http("GET", f"{BURNER}/api/scan/{jid}")
        except Exception as e:   # transient network trouble: keep waiting
            print("waiting:", type(e).__name__)
            time.sleep(10)
            continue
        for ev in d.get("events", [])[last:]:
            print(f"  [{ev.get('t', 0):>6}s] {ev.get('stage', '')}: {ev.get('text', '')}")
        last = len(d.get("events", []))
        if d.get("status") in ("done", "error"):
            return d
        time.sleep(10)
    raise SystemExit(f"::error::Burner didn't finish within {TIMEOUT // 60} min; see {BURNER}/r/{jid}")


def main():
    url = f"https://github.com/{HEAD_REPO}/tree/{REF}"
    print(f"Burning {url} on {BURNER} (a throwaway Vultr VM, fake secrets, fake internet)")
    jid = start(url)
    d = wait_for(jid)
    report_url = f"{BURNER}/r/{jid}"
    if d.get("status") == "error":
        err = (d.get("events") or [{}])[-1].get("text", "unknown error")
        summary(f"### Burner couldn't burn this commit\n\n{err}\n\nReport: {report_url}")
        print(f"::warning::Burner error: {err}")
        out("verdict", "ERROR")
        return 0
    rep = d.get("report") or {}
    verdict = rep.get("verdict", "UNKNOWN")
    commit = ((rep.get("source") or {}).get("commit") or "")
    owner, name = HEAD_REPO.split("/", 1)
    verify_url = f"{BURNER}/v/github.com/{owner}/{name}" + (f"?commit={commit}" if commit else "")
    badge = f"{BURNER}/badge/github.com/{owner}/{name}.svg"
    out("verdict", verdict)
    out("report-url", report_url)
    out("verify-url", verify_url)

    stolen = rep.get("stolen") or []
    secrets = sorted({s.get("secret") for s in stolen if isinstance(s, dict) and s.get("secret")})
    dests = sorted({s.get("sent_to") for s in stolen if isinstance(s, dict) and s.get("sent_to")})
    steps = " → ".join(s.get("name", "") for s in rep.get("steps") or [])
    vm = rep.get("vm") or {}
    moved = commit and SHA and commit != SHA
    lines = [f"### Burner: {verdict}", "", rep.get("headline", ""), "",
             "| | |", "|---|---|",
             f"| Commit burned | `{commit[:12]}` on `{REF}`{' (the branch moved after this run started)' if moved else ''} |",
             f"| Ran, like a candidate | {steps or '—'} |",
             f"| Throwaway Vultr VM | {vm.get('plan', '?')} in {vm.get('region', '?')}, alive {vm.get('lifetime_secs', '?')} s, then deleted |"]
    if secrets:
        lines.append(f"| Fake secrets sent out | {', '.join(secrets)} |")
        lines.append(f"| Sent to | {', '.join(dests)} |")
    lines += ["", f"[Full report]({report_url}) · [Burner Verified page]({verify_url}) · ![badge]({badge})", "",
              "_Observed in one run of this exact commit. Not a guarantee; every new commit is burned again._"]
    md = "\n".join(lines)
    summary(md)

    bad = verdict.upper() in FAIL_ON
    if IS_PR and os.environ.get("COMMENT_ON_PR", "true") == "true":
        gh("POST", f"/issues/{os.environ['PR_NUMBER']}/comments",
           {"body": md + ("\n\n**Don't merge this:** Burner saw it try to steal." if bad else "")})
    if bad and not IS_PR and os.environ.get("OPEN_ISSUE", "true") == "true":
        title = f"Burner: {REF} at {commit[:7]} is {verdict}. Don't send this take-home to candidates"
        body = (md + "\n\n**What to do now**\n"
                "1. Don't send this repo to anyone, and tell candidates who cloned it since this commit.\n"
                "2. Revert the commit and find out how it got in (compromised account or token?).\n"
                "3. The badge on the README shows this verdict until a clean commit is burned.\n\n"
                f"Workflow run: {os.environ.get('RUN_URL', '')}")
        got = gh("POST", "/issues", {"title": title, "body": body})
        if got and got.get("html_url"):
            print("Opened", got["html_url"])
    if bad:
        print(f"::error::Burner verdict {verdict}: {rep.get('headline', '')}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
