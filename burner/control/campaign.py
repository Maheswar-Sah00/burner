"""Behavioural campaign matching + a ready-to-send abuse report.

Compares what the repo actually did (captured on the fake internet / syscall trace)
with publicly documented behaviour of North Korea's "Contagious Interview" tooling
(BeaverTail / InvisibleFerret). This is behavioural similarity, NOT attribution.
"""
import json
import re
from pathlib import Path

SOURCES = {
    "mitre": "https://attack.mitre.org/software/S1246",
    "anyrun": "https://any.run/cybersecurity-blog/invisibleferret-malware-analysis/",
}
C2_PORTS = {1224, 1244, 1245}
C2_PATHS = re.compile(r"^/(uploads|keys|pdown|client/|p$|j/)", re.I)
WALLET_EXT_READ = re.compile(r"MetaMask|Local Extension Settings|Exodus|Solana", re.I)


def match(report, scan_dir):
    net = []
    f = Path(scan_dir) / "net.jsonl"
    if f.exists():
        net = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    tcp = [e for e in net if e.get("type") == "tcp"]
    ind = []

    ports = sorted({e["dst_port"] for e in tcp if e.get("dst_port") in C2_PORTS and not e.get("host")})
    if ports:
        ind.append({"what": f"talks to a hard-coded IP on port {', '.join(map(str, ports))}",
                    "why": "BeaverTail/InvisibleFerret C2 commonly uses ports 1224, 1244, 1245",
                    "source": SOURCES["mitre"]})
    paths = sorted({e["path"].split("?")[0] for e in tcp if e.get("path") and C2_PATHS.match(e["path"])})
    if paths:
        ind.append({"what": f"uses C2-style endpoints {', '.join(paths)}",
                    "why": "documented BeaverTail endpoints include /uploads, /keys, /pdown, /client/",
                    "source": SOURCES["mitre"]})
    if any(f["rule"] == "SECRET_READ" and WALLET_EXT_READ.search(f["title"]) for f in report.get("findings", [])):
        ind.append({"what": "reads crypto-wallet browser-extension and wallet folders",
                    "why": "BeaverTail searches browser extension folders of crypto wallets",
                    "source": SOURCES["mitre"]})
    if any((e.get("user_agent") or "").startswith("python-requests") for e in tcp):
        ind.append({"what": "a Python 'requests' client sent data out",
                    "why": "InvisibleFerret (Python) traffic used the default python-requests User-Agent",
                    "source": SOURCES["anyrun"]})
    if any(re.search(r"\.zip$|/pdown", e.get("path") or "") and e.get("method") == "GET" for e in tcp):
        ind.append({"what": "tried to download a second stage (zip / /pdown)",
                    "why": "BeaverTail downloads a Python runtime (p.zip) from /pdown",
                    "source": SOURCES["anyrun"]})
    if report.get("stolen") and any(s.get("step", "").startswith(("npm run", "npm start", "open folder"))
                                    for s in report["stolen"]):
        ind.append({"what": "steals only once the app is started or the folder is opened, not at install",
                    "why": "the 2025-26 variants moved the trigger from install to run time",
                    "source": "https://www.elastic.co/security-labs/threat-command/contagious-interview-malware-svg-steganography"})

    n = len(ind)
    level = "high" if n >= 3 else "medium" if n == 2 else "low" if n == 1 else None
    return {"campaign": "Contagious Interview (BeaverTail / InvisibleFerret)" if level else None,
            "similarity": level, "indicators": ind,
            "note": "Behavioural similarity to public reports, not attribution."}


def abuse_kit(report):
    iocs = []   # destinations only; 198.18.x addresses are Burner's own fake-DNS answers, never IOCs
    for s in report.get("stolen", []):
        if s["sent_to"] not in iocs:
            iocs.append(s["sent_to"])
    for c in report.get("network", []):
        d = f"{c['dest']}:{c['port']}" if c["raw_ip"] else c["dest"]
        if d not in iocs and c["dest"] != "registry.npmjs.org":
            iocs.append(d)
    target = report.get("target") or ""
    gh = re.match(r"https?://github\.com/([\w.-]+)/([\w.-]+)", target)
    lines = [
        "This repository was sent to me as a job-interview take-home. Running it in an isolated sandbox "
        "(Burner) showed malicious behaviour:",
        f"- Verdict: {report.get('verdict')} — {report.get('headline')}",
        *[f"- {f['title']}" for f in report.get("findings", [])[:8]],
        "Network indicators: " + (", ".join(iocs) if iocs else "none"),
        "All credentials it took were fake decoys planted by the sandbox.",
    ]
    recruiter = report.get("recruiter") or {}
    if recruiter.get("company"):
        lines.insert(1, f"Recruiter claimed to be from: {recruiter['company']} ({recruiter.get('role') or 'role n/a'}).")
    return {
        "iocs": iocs,
        "text": "\n".join(lines),
        "where": [
            {"name": "GitHub (report the repo/account)",
             "url": f"https://github.com/contact/report-abuse?report={gh.group(1)}" if gh
             else "https://github.com/contact/report-abuse"},
            {"name": "LinkedIn (recruiter profile → More → Report)", "url": "https://www.linkedin.com/help/linkedin"},
            {"name": "FBI IC3", "url": "https://www.ic3.gov/"},
            {"name": "India: cybercrime.gov.in / CERT-In", "url": "https://cybercrime.gov.in/"},
        ],
    }
