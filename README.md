<div align="center">

# Burner

**Paste a recruiter's message. Burner runs the take-home repo the way a candidate would, inside a throwaway Vultr VM full of fake secrets, and shows you exactly what it tried to steal before the VM is destroyed.**

*Run the take-home before it runs you.*

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-SSE-009688?logo=fastapi&logoColor=white)
![gVisor](https://img.shields.io/badge/sandbox-gVisor%20runsc-4285F4)
![Vultr](https://img.shields.io/badge/Vultr-Compute%20·%20Inference%20·%20Object%20Storage-007BFC?logo=vultr&logoColor=white)
![Benchmark](https://img.shields.io/badge/benchmark-13%2F13%20caught%20·%200%2F11%20false%20alarms-e2501a)
![Real repos](https://img.shields.io/badge/real%20repos-0%2F21%20false%20alarms-2f9e44)
![Tests](https://img.shields.io/badge/tests-32%20passing-brightgreen)

Vultr Agent Rush (lablab.ai) · Track 1: **Blast Radius Zero** · built solo by **[@Maheswar-Sah00](https://github.com/Maheswar-Sah00)**

**[Live app](https://139-84-215-1.sslip.io)** · [Track record](https://139-84-215-1.sslip.io/track) · [Benchmark](reports/benchmark/results.md) · [Real-repo check](reports/benchmark/real-repos.md) · [Deck (PDF)](pitch/Burner-deck.pdf)

<img src="docs/screenshots/landing.png" alt="Burner landing page: Run the take-home before it runs you" width="900">

</div>

> [!IMPORTANT]
> **Everything malicious in this repo is defanged, and every secret is fake.** The stealer samples were written by me from
> public threat reports. They only read the fake secrets that Burner plants, and they only talk to documentation IP ranges
> (`203.0.113.0/24` and similar) or reserved names (`*.example`). Inside the sandbox, all traffic goes to Burner's fake internet anyway.

## At a glance

| | |
| --- | --- |
| **Problem** | North Korea's *Contagious Interview* campaign sends developers fake take-home tests. The repo looks normal. Running `npm start` steals keys, wallets and passwords. The FBI's advice is "use a virtual machine", but a VM can't tell you whether the repo was malicious. |
| **Solution** | Burner runs the repo the way a candidate would (open in VS Code, install, start, test, then again 45 days later) inside a throwaway Vultr VM. The VM is a gVisor sandbox with 15 fake secrets and a fake internet that records everything that tries to leave. |
| **Result** | **13/13** campaign-style samples caught, **0/11** false alarms (static GuardDog: 11/13, 1/11). **0 false alarms on 21 real public repos** (after one rule fix). **112 s** from paste to verdict with a warm VM. A scan costs **under a cent**. |
| **Proof** | The report shows the exact fake AWS key arriving at the "attacker", which step sent it, how long the VM lived and what it cost. An evidence bundle is uploaded to Object Storage. |
| **Trust** | **Fixed rules set the verdict.** The LLM reads the message, plans the steps and explains the result, but it can't change the verdict. |
| **Built with** | Python · FastAPI · gVisor · Docker · iptables · Vultr Cloud Compute · Vultr Serverless Inference · Vultr Object Storage · Caddy · D3 |

---

## Contents

1. [The problem](#1-the-problem)
2. [Why I chose this problem](#2-why-i-chose-this-problem)
3. [What Burner does](#3-what-burner-does)
4. [Results](#4-results)
5. [System architecture](#5-system-architecture)
6. [How a scan works](#6-how-a-scan-works)
7. [The verdict rules](#7-the-verdict-rules)
8. [Containment](#8-containment)
9. [The product](#9-the-product)
10. [Getting started](#10-getting-started)
11. [Demo in three minutes](#11-demo-in-three-minutes)
12. [Project structure and tech stack](#12-project-structure-and-tech-stack)
13. [Testing](#13-testing)
14. [Security and trust model](#14-security-and-trust-model)
15. [Who would use it](#15-who-would-use-it)
16. [What Burner can't catch (yet)](#16-what-burner-cant-catch-yet)
17. [Editing the diagrams](#17-editing-the-diagrams)
18. [Sources](#18-sources)
19. [Author](#19-author)

---

## 1. The problem

A "recruiter" offers a well-paid role and asks for a quick take-home first. The repo is a normal-looking Node or React
app. The payload runs when the candidate does exactly what the recruiter asked:

<p align="center"><img src="docs/diagrams/01-the-lure.svg" alt="Without Burner, the fake recruiter's take-home steals keys and wallets from the candidate's laptop. With Burner, it runs in a throwaway Vultr VM full of fake secrets and the candidate gets a verdict." width="900"></p>

| Fact | Why it matters |
| --- | --- |
| **30,000+ devices in 100+ countries, 7,000+ crypto wallets drained** (Dec 2025 to Jul 2026), per a joint advisory from seven agencies in four countries on 18 Sep 2026. | This is an industrial campaign, not a one-off. |
| **$308M stolen from DMM Bitcoin (2024)** after a fake LinkedIn recruiter sent an employee of its wallet provider a GitHub "pre-employment test". | One take-home can cost a company everything. |
| **Zero antivirus detections** on a July 2026 variant that runs at `npm start` and keeps running inside VMs (Elastic). | Antivirus and static scanning don't see it. |
| **1,700+ campaign packages across 5 ecosystems** that "did not generally rely on install-time execution"; Socket's advice is to "sandbox suspicious packages". | npm's install-script blocking doesn't help: the payload runs at start, test or folder-open. |
| **750+ infected repos and 500+ malicious VS Code `folderOpen` tasks** (Trend Micro, Mar 2026). Victims committed the malware into their **employers'** repos. | Opening the folder is enough, and the damage spreads to companies. |
| **"Almost half" of the repos use two or more trigger techniques**; Atlassian removed "hundreds" from Bitbucket (Sep 2026). | A scanner has to try every way a candidate might run it. |
| North Korea stole **$2.02B of the $3.4B** in crypto thefts in 2025 (Chainalysis). | The money keeps the campaign funded. |
| The FBI (2024): *"If a pre-employment test requires code execution, insist on using a virtual machine."* Microsoft (Mar 2026) recommends "a dedicated, isolated environment for coding tests". | The official advice exists, but a VM only **contains** the damage. It doesn't tell you the repo was malicious, so you can't warn anyone. |

One victim put it this way: *"every question was designed so that the only way to answer it is to actually run the
project."* ([Steven Li, Jun 2026](https://lxzxl.github.io/posts/defi-recruiter-take-home-was-malware/))

<details>
<summary><b>New to this campaign? A 30-second glossary</b></summary>

| Term | Meaning |
| --- | --- |
| **Contagious Interview** | A North Korea-linked campaign (also tracked as WaterPlum, DeceptiveDevelopment, Void Dokkaebi) that targets developers with fake jobs. Active since at least Dec 2022. |
| **BeaverTail / OtterCookie / InvisibleFerret** | The campaign's malware families: JavaScript stealers and a Python backdoor that take browser data, wallets, keys and files. |
| **folderOpen task** | A VS Code `.vscode/tasks.json` entry with `"runOn": "folderOpen"`. It runs a command as soon as you open the folder and trust it. |
| **Lifecycle script** | npm's `preinstall`/`postinstall`/`prepare` hooks, which run during `npm install`. |
| **gVisor** | Google's user-space kernel. Programs inside it talk to gVisor, not to the host's Linux kernel. |
| **Honeytoken** | A fake secret planted as bait. If it shows up on the network, you know exactly what was stolen. |

</details>

## 2. Why I chose this problem

I didn't start with Burner. I ran a **problem tournament**: 24 candidate problems across two rounds, each scored on
evidence, then the top 10 put through **adversarial validation**, where four parallel research passes were told to try
to *disprove* each problem. Burner won because it was the **most genuine and least solved** problem left standing.
The reports are in [`reports/`](reports).

**1. The problem is live, large and getting worse.**
The numbers in [section 1](#1-the-problem) are all from 2024–2026, most from the last six months: 30,000+ devices,
7,000+ wallets, 1,700+ packages, 750+ repos, a zero-detection variant in July 2026.

**2. Running beats reading, and the research shows it.**
The OSCAR paper (ASE 2024) ran npm packages in a sandbox and caught **459 of 500** malicious ones with **3** false
positives. Static GuardDog caught **338** with **28**. This campaign is built to beat reading: payloads hidden in SVG
assets, triggered only by `npm test`, or delayed by days. My own benchmark repeats the gap on a small scale:
Burner **13/13**, GuardDog **11/13**.

**3. Nobody has put the whole puzzle together for a candidate.**
Platforms each solve a piece:
- Socket and Aikido block known-bad packages.
- Tracebit plants fake secrets on developer machines.
- The FBI says to use a VM.

Open-source experiments are starting. **Nobody has put the whole puzzle together in a candidate's hands:** paste the
recruiter's message, get a verdict that names what was stolen and where it went, in about two minutes.

**4. The money is real.**
- **Socket:** $60M Series C at a **$1B** valuation (May 2026). Dynamic analysis is still "coming soon".
- **Aikido:** $60M at **$1B** (Jan 2026). It then launched an endpoint product for developer machines that blocks known malware but doesn't run repos.
- **Tracebit:** raised **$20M** (Mar 2026) for fake-secret tripwires.
- **Koi:** acquired by Palo Alto Networks (closed Apr 2026).

**5. It fits Track 1 exactly.** Track 1 asks for sandboxed agents with a zero blast radius. Burner turns each
containment rule into the product itself:

| Track 1 rule | In Burner |
| --- | --- |
| Isolate the agent | A throwaway VM, a network jail, gVisor and a locked-down container, one per scan |
| Keep secrets away from it | **Fake secrets as bait**: the only secrets in reach are the ones it is allowed to steal |
| Limit what it can do | 2 GB, 1.5 CPU, 512 processes, every step on a timeout, 0 packets out |
| Destroy after use | The VM is deleted through the Vultr API, and the report shows its lifetime and cost |

Vultr published its own agent-sandboxing guide in Sep 2026 but has no managed sandbox API. Burner shows that Vultr
Compute plus Serverless Inference already works as one.

## 3. What Burner does

| # | Capability | What it means for a candidate |
| --- | --- | --- |
| 1 | **Starts from the recruiter's message** | Paste the DM. The LLM pulls out the repo link, lists the red flags (pressure, Telegram, crypto, "run it before the call") and scores the lure. |
| 2 | **Behaves like a candidate** | Opens the folder in VS Code (`folderOpen` tasks), runs `npm install`, `npm start`/`dev`, `npm test` and `python main.py`, plus up to 4 steps the README asks for. Then it reruns with the clock moved **45 days forward** to catch time bombs. |
| 3 | **Fake secrets as bait** | 15 unique, random fake secrets per scan: AWS, SSH, GitHub, npm, Stripe, OpenAI, a DB password, Solana, Exodus, MetaMask, a seed phrase, Chrome passwords, an env token and shell history. |
| 4 | **A fake internet that shows the key leaving** | Sinkhole DNS, a catch-all TCP listener and an HTTPS proxy with Burner's own CA record every upload. Nothing reaches the real internet. |
| 5 | **Rule-based verdict** | `detect.py` matches every planted secret against everything captured, including URL-encoded, base64, hex, gzip, zip, XOR and DNS-tunnelled forms. The LLM can't change the verdict. |
| 6 | **One VM per scan** | Each scan gets its own Vultr VM, taken pre-armed from a warm pool and deleted afterwards. A reaper deletes anything older than 20 minutes. |
| 7 | **A report you can act on** | What was stolen, where it went, which step sent it, a timeline, campaign indicators, a ready-to-send abuse report and an evidence bundle on Vultr Object Storage. |

## 4. Results

### 4.1 Benchmark: Burner vs static GuardDog

13 campaign-style malicious samples and 11 clean take-homes, run on a throwaway Vultr VM (vc2-2c-4gb, Bangalore)
with the default candidate plan and no LLM (`python -m burner.bench.run_bench`).

| | Burner | GuardDog (static) |
| --- | ---: | ---: |
| **Malicious detected** (of 13) | **13/13** | 11/13 |
| **False alarms** (of 11 clean) | **0/11** | 1/11 |
| Verdict MALICIOUS (not just SUSPICIOUS) | 12/13 | — |
| Named the exact stolen fake secret | 11/13 | — |
| Median time per repo | 91 s | 0.8 s |

GuardDog missed the **time bomb** (`m06`) and the **obfuscated XOR loader** (`m12`). It raised a false alarm on a
clean app that reads its own `.env` (`b06`).

The samples cover: an SVG-asset `eval`, OS-keyed `folderOpen`, a local dependency's `postinstall`, a `prepare` hook,
a payload that runs only under `npm test`, a +30-day time bomb, a Python stealer, raw TCP, DNS exfiltration,
`curl | sh`, a sandbox check, obfuscation and a resource bomb.
Full per-sample table: [`reports/benchmark/results.md`](reports/benchmark/results.md).

> [!NOTE]
> **The benchmark is mine.** I wrote all 24 samples from public reports, and some rules were added after the first run
> (baseline before tuning: 11/12 detected, 1/11 false alarms). Treat these numbers as a regression suite, not a field study.

### 4.2 Real public repos: false-alarm check

21 popular public repos written by other people (Express, NestJS, Remix, Next.js + Stripe, FastAPI, Koa, Fastify,
SvelteKit, json-server and others), scanned with the same engine.

| Result | Count |
| --- | ---: |
| **False alarms** (MALICIOUS or SUSPICIOUS on a clean repo) | **0 / 21** |
| NO MALICIOUS BEHAVIOUR OBSERVED | 19 |
| INCONCLUSIVE (nothing Burner knows how to run) | 2 |

The first run had **2 false alarms**, both caused by pm2 writing its normal state files. Those files were then allowed
(`~/.pm2/dump.pm2`, which survives reboots, is still flagged) and the two repos were rescanned. So read this as
**0/21 after one fix**. Details: [`reports/benchmark/real-repos.md`](reports/benchmark/real-repos.md).

### 4.3 Live end-to-end scan on the deployed app

Case `4f5efb8dc6`, the `npm-start-stealer` sample, through the public site:

| | |
| --- | --- |
| Verdict | **MALICIOUS**: 10 of 15 fake secrets sent to `203.0.113.55:1224` and over HTTPS to `cdn-telemetry.example` |
| Campaign match | high (4 indicators) |
| VM | fresh (the pool VM was still arming): up after 41 s, alive 255 s, total 265 s |
| Cost | **$0.0019** prorated |
| Evidence | 199 KB bundle uploaded to Vultr Object Storage |

### 4.4 Speed and cost

| Measure | Value |
| --- | ---: |
| Paste → verdict with a pre-armed VM (including LLM steps) | **112 s** |
| Fresh VM ready (vc2-1c-1gb / vc2-2c-4gb) | 41 s / ~45 s |
| Booting from a Vultr snapshot | 437 s, which is why Burner keeps a warm pool instead |
| One scan VM at $20/month (≈ $0.0274/hour) | ≈ **$0.0014–0.0019** prorated, $0.0274 if a full hour is billed |
| LLM usage per scan | ~4 calls, ~4k prompt + ~0.8k completion tokens |
| Warm pool (1 armed VM always on) | ≈ $0.66/day |

## 5. System architecture

<p align="center"><img src="docs/diagrams/02-architecture.svg" alt="The browser talks to an always-on control VM (Caddy, FastAPI, scan orchestrator, warm pool, reaper). The control VM calls Vultr Serverless Inference, the Vultr API and Object Storage, and drives a per-scan burner VM over SSH. The burner VM holds the gVisor sandbox with fake secrets, the iptables network jail, the fake internet and the rule engine. Nothing reaches the real internet." width="900"></p>

| Component | Where | What it does |
| --- | --- | --- |
| **Web app** (`burner/web/app.py`) | Control VM | FastAPI with live progress over Server-Sent Events, rate limits (4 scans per IP per hour, 60 per day), share links and the track-record page. Behind Caddy with automatic HTTPS on sslip.io. |
| **Orchestrator** (`burner/control/scan.py`) | Control VM | One scan end to end: read → plan → detonate → judge → destroy. The repo is cloned with git hooks and symlinks disabled; nothing in it runs on the control VM. |
| **Brain** (`burner/control/brain.py`) | Vultr Serverless Inference | `deepseek-v4.1-flash` reads the DM, plans the steps and explains the verdict. `nemotron-3.5-content-safety` screens the README for prompt injection. A fallback list handles retired models, and a silent model swap raises an error. |
| **Warm pool + reaper** (`pool.py`, `vultr.py`) | Control VM → Vultr API | Keeps one VM pre-armed (tagged `burner-pool`, `armed`). Each VM is used once. A systemd timer deletes any scan VM older than 20 minutes. |
| **Node** (`burner/node/`) | Burner VM | `setup.sh` (Docker, gVisor, iptables, CA), `bait.py` (fake secrets), `fakenet.py` (fake DNS/HTTP/HTTPS/TCP), `run_scan.py` (candidate steps), `detect.py` (rules). |
| **Campaign + trace** (`campaign.py`, `trace.py`) | Control VM | Matches indicators from public reports (C2 ports 1224/1244/1245, C2 paths like `/uploads` and `/pdown`, wallet-folder reads) and builds the event timeline for the charts. |
| **Evidence** (`evidence.py`) | Vultr Object Storage | Uploads each scan's syscall log, captured requests and report as one `.tar.gz`. The download link is re-signed on every click. |

## 6. How a scan works

<p align="center"><img src="docs/diagrams/03-scan-workflow.svg" alt="Five phases: read (Serverless Inference), plan (Serverless Inference), detonate (Vultr Cloud Compute), judge (fixed rules, no LLM), destroy (Cloud Compute and Object Storage)." width="900"></p>

The same flow as a sequence:

```mermaid
sequenceDiagram
    autonumber
    actor C as Candidate
    participant W as Control VM (FastAPI + scan.py)
    participant L as Vultr Serverless Inference
    participant V as Vultr API
    participant B as Burner VM (gVisor + fakenet)
    participant S as Vultr Object Storage

    C->>W: paste recruiter DM (or repo link)
    W->>L: extract repo link, red flags, lure score
    W->>W: git clone (hooks + symlinks off), nothing executed
    W->>L: safety model screens README for injection
    W->>L: plan the candidate's steps (README = data)
    W->>V: take the pre-armed VM from the warm pool
    W->>B: SSH: copy repo + plan
    B->>B: fetch deps (scripts off, no secrets present)
    B->>B: plant 15 fresh fake secrets
    loop each candidate step
        B->>B: folderOpen → npm install → npm start → npm test → npm start +45 days
        B-->>B: every DNS / TCP packet DNAT'd to fakenet and recorded
    end
    B->>B: detect.py: fixed rules → verdict
    B-->>W: report, traffic, syscall log
    W->>V: delete the VM (reaper backstop: 20 min)
    W->>L: explain the verdict in plain English (can't change it)
    W->>S: upload evidence bundle
    W-->>C: live progress over SSE, then the report
```

**Step by step:**

1. **Read.** The LLM pulls the repo link and red flags out of the recruiter's message. The repo is cloned with git
   hooks and symlinks disabled.
2. **Plan.** Burner builds the steps a candidate would take from what it finds: `.vscode/tasks.json`, `package.json`
   scripts, `main.py`. The LLM adds up to 4 steps the README asks for. The README is screened for prompt injection
   and treated as untrusted data.
3. **Detonate.** A pre-armed VM is taken from the pool. Dependencies are fetched with scripts disabled and no secrets
   present. Then the fake home is planted and every step runs inside gVisor, with a final pass at +45 days via `libfaketime`.
4. **Judge.** `detect.py` reads the gVisor syscall log and everything the fake internet captured, and applies fixed
   rules ([section 7](#7-the-verdict-rules)).
5. **Destroy.** Results come back over SSH, the VM is deleted through the Vultr API, the LLM writes the explanation,
   and the evidence bundle goes to Object Storage.

## 7. The verdict rules

<p align="center"><img src="docs/diagrams/04-verdict-rules.svg" alt="Decision tree: a planted fake secret seen in captured traffic means MALICIOUS; a secret read or downloaded code plus an unknown host means MALICIOUS; any high finding or two medium findings means SUSPICIOUS; if nothing ran the result is INCONCLUSIVE; otherwise NO MALICIOUS BEHAVIOUR OBSERVED." width="620"></p>

| Rule | Severity | Example |
| --- | --- | --- |
| `EXFIL`: a planted secret appears in captured traffic (any encoding) | critical | AWS key inside a multipart upload to `203.0.113.55:1224` |
| `SECRET_READ`: opened a secret file | high | `~/.aws/credentials`, `~/.ssh/id_ed25519`, wallet folders, Chrome `Login Data` |
| `PERSISTENCE`: changed something that runs later | high | `.bashrc`, cron, global git `hooksPath`, `~/.pm2/dump.pm2` |
| `REMOTE_CODE`: downloaded code and ran it | high | `curl … \| sh` |
| `DNS_TUNNEL`: data encoded into DNS names | high / medium | base32 secrets in subdomain labels |
| `SANDBOX_DIED`: crashed the sandbox | high | memory or fork bomb before the theft |
| `NETWORK`: contacted an unknown host | medium (raw IP or odd port) / low | `203.0.113.77:1244` |
| `DOWNLOADER`: ran a download tool | medium | `curl`, `wget` |
| `DROPPED_FILE`: wrote a file outside the project | medium | `~/.n2/pay.js` |
| `SANDBOX_CHECK`: fingerprinted the VM | low | reads of `/sys/class/dmi`, `/proc/1/cgroup` |

**MALICIOUS** = any critical finding, or (a high secret read or remote code) **and** an unknown contact.
**SUSPICIOUS** = any high finding, or 2+ medium. **INCONCLUSIVE** = nothing actually ran. Otherwise
**NO MALICIOUS BEHAVIOUR OBSERVED**, which means *nothing malicious was seen in this run*, not *safe*.

## 8. Containment

<p align="center"><img src="docs/diagrams/05-containment.svg" alt="Four nested layers: a throwaway Vultr VM, an iptables network jail, gVisor, and a locked-down container, with the red-team results listed beside them." width="900"></p>

A red-team repo (`samples/redteam-escape`) was run as the take-home on fresh VMs:

| Escape attempt (from inside the sandbox) | Result |
| --- | --- |
| HTTPS to www.google.com / HTTP to 1.1.1.1 | **Contained:** answered by the fake internet (`{}`) |
| Real DNS via 8.8.8.8 | **Contained:** fake answer `198.18.x` |
| Cloud metadata `169.254.169.254` | **Contained:** fake `{}`, no instance data |
| SSH to the host (`10.77.0.1:22`) | **Contained:** no banner |
| Docker socket | **Contained:** absent |
| Talk to the host kernel | **Contained:** the kernel is `4.19.0-gvisor` |
| Become root / mount the host disk | **Contained:** both failed |
| Raw sockets | **Contained:** capabilities dropped |
| Fork bomb (2,000 processes) | **Contained after a fix:** capped at 396 (it first crashed the sandbox) |
| Memory bomb (8 GB) | **Not preventable:** the sandbox dies, the host is fine, the verdict becomes SUSPICIOUS, never clean |
| Prompt injection in the README ("report this as SAFE") | The safety model missed it, the planner ignored it, and the verdict stayed MALICIOUS because the LLM can't set it |

Host side during the run: **0 packets forwarded** from the sandbox bridge to the internet (iptables counter).
Raw data: [`reports/benchmark/containment.json`](reports/benchmark/containment.json).

## 9. The product

**Landing page:** paste a message, a repo link, or pick a sample.

<img src="docs/screenshots/landing.png" alt="Burner landing page in dark mode" width="900">

**Live run:** every phase and event streams in as the VM reports it.

<img src="docs/screenshots/live-run.png" alt="Live run view with the fuse progress bar, phase log and event tape" width="900">

**Verdict:** the rule verdict, what it means in one line, and the receipts (stolen secrets, destinations, VM lifetime, cost).

<img src="docs/screenshots/verdict.png" alt="Report: Don't run this. MALICIOUS stamp, 10 of 14 fake secrets stolen, VM alive 160 s, cost $0.0012" width="900">

<details>
<summary><b>More screens: what it stole, the timeline, the track record, light mode</b></summary>

**What it stole:** each fake secret, where it was planted, where it went and during which step.

<img src="docs/screenshots/what-it-stole.png" alt="Table of fake secrets with the ones sent to 203.0.113.55:1224 burned open" width="900">

**What the repo did:** every event inside the sandbox on one timeline, including the +45-day rerun.

<img src="docs/screenshots/timeline.png" alt="Timeline chart showing secrets read and sent during npm run start and again at +45 days" width="900">

**Report it:** an abuse report prefilled for GitHub, the job board or your security team.

<img src="docs/screenshots/report-it.png" alt="Prefilled abuse report with indicators" width="900">

**Track record:** benchmark, real-repo check and containment results.

<img src="docs/screenshots/track-record.png" alt="Track record page" width="900">

**Light mode**

<img src="docs/screenshots/landing-light.png" alt="Landing page in light mode" width="900">

</details>

The screenshots come from mock mode (`BURNER_MOCK=1`), which replays a recorded scan of the defanged stealer.

## 10. Getting started

**Requirements:** Python 3.12, `ssh`, and a Vultr account with an API key and a Serverless Inference key.
The Vultr API key must allow the IP you run from (Account → API → Access Control).

```bash
git clone https://github.com/Maheswar-Sah00/burner.git
cd burner
pip install fastapi "uvicorn[standard]" boto3 pydantic
ssh-keygen -t ed25519 -f .burner/id_ed25519 -N ""
```

Create `.env` (gitignored):

```ini
VULTR_API_KEY=...
VULTR_INFERENCE_KEY=...
BURNER_POOL_SIZE=1            # pre-armed VMs kept ready for the web app
# optional: VULTR_S3_HOST / VULTR_S3_ACCESS_KEY / VULTR_S3_SECRET_KEY (else read from the account)
```

**Try the UI with no cloud at all** (replays a recorded scan, no VM, no LLM):

```bash
BURNER_MOCK=1 python -m uvicorn burner.web.app:app --port 8000
# PowerShell: $env:BURNER_MOCK="1"; python -m uvicorn burner.web.app:app --port 8000
```

**Run real scans from the command line:**

```bash
# from a recruiter message (the repo link is taken from it)
python -m burner.control.scan --message samples/recruiter-message.txt

# a local folder or a git URL; --no-llm skips Serverless Inference; --keep keeps the VM for debugging
python -m burner.control.scan samples/fake-takehome
python -m burner.control.scan https://github.com/owner/repo --no-llm
```

**Deploy your own control VM** (creates it if missing; HTTPS via Caddy + sslip.io; reaper timer):

```bash
python deploy/deploy.py
```

**Benchmarks:**

```bash
python -m burner.bench.run_bench --label final     # 24 samples vs GuardDog on a burner VM
python -m burner.bench.real_repos                   # 21 real public repos, false-alarm check
```

## 11. Demo in three minutes

1. Open **https://139-84-215-1.sslip.io**.
2. Choose **Sample → the npm-start stealer** and press **Burn it**.
3. Watch the run: message read → plan → VM → sandbox armed → candidate steps → VM destroyed.
4. Read the verdict: **MALICIOUS**, which fake secrets left, to `203.0.113.55:1224` and `cdn-telemetry.example`, and during `npm run start`.
5. Scroll to **What the repo did** and pick a mark on the timeline. The +45-day rerun steals again.
6. Open **Report it** and copy the abuse report. **The VM is gone** shows its lifetime and cost.
7. Go back and burn **a clean take-home**. It comes back NO MALICIOUS BEHAVIOUR OBSERVED.
8. Open **Track record** for the benchmark, the real-repo check and the containment table.

## 12. Project structure and tech stack

```
burner/
  control/   scan.py      one scan, end to end (read → plan → detonate → judge → destroy)
             brain.py     Serverless Inference: message, safety screen, plan, explain
             vultr.py     Vultr API v2: create / tag / delete VMs, reaper
             pool.py      warm pool of pre-armed VMs
             campaign.py  campaign indicators from public reports
             trace.py     event timeline for the charts
             evidence.py  evidence bundles → Vultr Object Storage
  node/      runs on the burner VM
             setup.sh     Docker, gVisor (runsc + syscall trace), iptables jail, CA
             bait.py      15 unique fake secrets per scan
             fakenet.py   fake DNS / HTTP / HTTPS (own CA) / raw TCP
             run_scan.py  the candidate's steps, +45-day rerun via libfaketime
             detect.py    rule-based verdict (no LLM)
             sandbox/Dockerfile   the "dev-laptop" image
  web/       app.py (FastAPI + SSE) · static/ (UI, D3 charts, halftone canvas art) · recorded/ (mock replays)
  bench/     run_bench.py (Burner vs GuardDog) · real_repos.py (false-alarm check)
samples/     fake-takehome · vscode-task-takehome · clean-takehome · injection-takehome ·
             redteam-escape · recruiter-message.txt · benchmark/build.py (24 samples, built on the VM)
deploy/      deploy.py · control_setup.sh (Caddy, systemd, reaper timer)
docs/        diagrams/ (Excalidraw sources + SVG) · screenshots/
reports/     benchmark results, problem research
tests/       detect, scan and trace tests
pitch/       deck, video script, submission text
```

| Layer | Technology |
| --- | --- |
| Compute | Vultr Cloud Compute (vc2-2c-4gb burner VMs, Bangalore; one always-on control VM) |
| AI | Vultr Serverless Inference: `deepseek-v4.1-flash-1017` (planner/explainer), `nemotron-3.5-content-safety` |
| Storage | Vultr Object Storage (S3-compatible, boto3) |
| Sandbox | Docker + gVisor `runsc` (with syscall tracing), iptables DNAT, `libfaketime` |
| Fake internet | Python asyncio DNS/HTTP/TCP servers, HTTPS interception with a per-VM CA (`cryptography`) |
| Web | FastAPI, Server-Sent Events, Caddy, sslip.io |
| UI | Vanilla JS, D3 charts, canvas halftone art; Geist, Geist Mono, Geist Pixel |
| Baseline | [GuardDog](https://github.com/DataDog/guarddog) (static) |

## 13. Testing

```bash
python -m pytest -q        # 32 passing
```

- `tests/test_detect.py`: secret-read tracking that path tricks can't dodge (relative paths, `..`, numeric dirfds, `/proc/self/root`, symlinks, renames), the pm2 allow-list, and inconclusive runs.
- `tests/test_scan.py`: the scan pipeline: no VM rented when nothing is runnable, rules carry on if the AI is down, planner model fallback, reaper and pool ageing, the queue, replays, and the web app end to end in mock mode.
- `tests/test_trace.py`: event-timeline building for the charts (stealer, DNS exfil, crashed sandbox, benign, missing files).
- End to end: the benchmark (24 samples), the real-repo check (21 repos) and the red-team containment run, all on real Vultr VMs. Results are in [`reports/benchmark/`](reports/benchmark).

## 14. Security and trust model

- **Nothing from the repo runs on the control VM.** It is cloned with hooks and symlinks disabled and copied to the burner VM.
- **The verdict is deterministic.** The LLM's output never feeds into it. A prompt-injected README can, at most, make the explanation wrong.
- **Attacker-controlled strings are never rendered as HTML.** The UI writes them with `textContent`.
- **No real secrets are reachable.** The burner VM has none, and the 15 planted ones are random per scan.
- **Egress is closed.** Every sandbox packet is DNAT'd to fakenet, and forwarding from the sandbox bridge is dropped.
- **VMs can't pile up.** Each is deleted after its scan, and a reaper deletes anything older than 20 minutes.
- **Keys stay in `.env`.** It is gitignored, and the Vultr API key is limited to an IP allow-list.

**Defanged samples.** Every malicious sample is a reconstruction written from public reports. It reads only the fake
secrets Burner plants, talks only to documentation IP ranges (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`)
or reserved names (`*.example`, `*.invalid`, `*.test`), and never deletes, encrypts or spreads. Benchmark samples are
generated on the burner VM by `samples/benchmark/build.py`, so they never touch a workstation's disk. Lure files that
trip antivirus are stored base64-encoded.

## 15. Who would use it

| User | Why |
| --- | --- |
| **Developers looking for work** | Paste the recruiter's DM before the call. Get a verdict in about two minutes instead of finding out after the wallet is empty. |
| **Crypto and Web3 companies** | The $308M DMM Bitcoin heist started with one employee's "pre-employment test". Security teams can make "burn it first" a policy. |
| **Enterprise security teams** | Victims commit the malware into their employers' repos. Burner gives IOCs and an evidence bundle. |
| **Job boards and hiring communities** | Scan links shared in job posts and DMs, then take down the repo with a ready-made abuse report. |

## 16. What Burner can't catch (yet)

- **Malware that detects the sandbox and stays quiet.** Burner flags reads of `/sys/class/dmi`, `/proc/1/cgroup` and similar, but a payload that checks something else and does nothing looks clean.
- **Payloads that need a real C2 reply.** The fake internet accepts uploads but can't serve the attacker's real second stage.
- **Time bombs beyond the shift.** Burner reruns at +45 days. A payload set for +90 days, or one waiting for a user action, is missed.
- **Stacks other than JS and Python.** Go, Rust, Java and .NET need their own candidate steps.
- **Kernel-level escapes from gVisor.** gVisor plus a throwaway VM limits the damage. It doesn't make an escape impossible.
- **Steps the README doesn't ask for.** If the trigger is a click in the UI or a specific API call, the candidate agent may not reach it.
- **Resource bombs.** A repo that exhausts memory first crashes the sandbox before it steals. The verdict is SUSPICIOUS, but Burner can't name what it would have taken.
- **Real encryption.** AES-encrypted exfiltration can't be matched to a fake secret. The verdict then rests on "read a secret + contacted an unknown host".

A clean result means *no malicious behaviour observed in this run*. It does not mean *safe*.

## 17. Editing the diagrams

Every diagram in this README was drawn with [Excalidraw](https://excalidraw.com). The editable sources sit next to
the exported SVGs in [`docs/diagrams/`](docs/diagrams). Open a `.excalidraw` file at excalidraw.com
(menu → Open), edit it, and export it as SVG with the same name.

| Diagram | Source |
| --- | --- |
| The lure, with and without Burner | `01-the-lure.excalidraw` |
| System architecture | `02-architecture.excalidraw` |
| Scan workflow | `03-scan-workflow.excalidraw` |
| Verdict rules | `04-verdict-rules.excalidraw` |
| Containment layers | `05-containment.excalidraw` |

## 18. Sources

**The campaign**
- Joint advisory on WaterPlum, 18 Sep 2026: [BleepingComputer](https://www.bleepingcomputer.com/news/security/north-korean-waterplum-hackers-infected-30-000-devices-worldwide/) · [The Record](https://therecord.media/north-korean-hackers-infect-thousands-of-devices-waterplum-scheme)
- DMM Bitcoin, $308M: [BleepingComputer](https://www.bleepingcomputer.com/news/security/fbi-links-north-korean-hackers-to-308-million-crypto-heist)
- Elastic Security Labs, Jul 2026 (zero detections, `npm start`): [Elastic](https://www.elastic.co/security-labs/threat-command/contagious-interview-malware-svg-steganography)
- Socket, Apr 2026 (1,700+ packages, 5 ecosystems): [Socket](https://socket.dev/blog/contagious-interview-campaign-spreads-across-5-ecosystems)
- Trend Micro, Mar 2026 (750+ repos, 500+ `folderOpen` tasks): [Trend Micro](https://www.trendmicro.com/en_gb/research/26/d/void-dokkaebi-uses-fake-job-interview-lure-to-spread-malware-via-code-repositories.html)
- Atlassian, Sep 2026: [Atlassian](https://www.atlassian.com/blog/bitbucket/disrupting-contagious-interview)
- ESET, DeceptiveDevelopment: [WeLiveSecurity](https://welivesecurity.com/en/eset-research/deceptivedevelopment-from-primitive-crypto-theft-to-sophisticated-ai-based-deception)
- Chainalysis via The Record, 2025 thefts: [The Record](https://therecord.media/over-3-billion-crypto-stolen-2025-north-korea)
- FBI IC3 PSA, 3 Sep 2024: [IC3](https://www.ic3.gov/PSA/2024/PSA240903) · Microsoft, Mar 2026: [Microsoft Security](https://www.microsoft.com/en-us/security/blog/?p=145718)
- A victim's write-up: [Steven Li, Jun 2026](https://lxzxl.github.io/posts/defi-recruiter-take-home-was-malware/)

**Running vs reading**
- OSCAR (ASE 2024), dynamic vs static npm detection: [arXiv 2409.09356](https://arxiv.org/html/2409.09356v1)

**Market**
- Socket Series C: [Socket](https://socket.dev/blog/socket-raises-60m-series-c-press-release) · Aikido: [SiliconANGLE](https://siliconangle.com/2026/01/14/aikido-security-raises-60m-series-b-1b-valuation-unify-application-security/), [Tech.eu](https://tech.eu/2026/04/20/aikido-launches-endpoint-to-secure-ai-native-developer-workflows/) · Tracebit: [Tech.eu](https://tech.eu/2026/03/17/tracebit-raises-20m-series-a-to-expand-cloud-native-deception-tech/)

**Vultr**
- Agent sandboxing on Vultr Cloud Compute: [Vultr Docs](https://docs.vultr.com/how-to-set-up-agent-sandboxing-on-vultr-cloud-compute)

## 19. Author

Built solo by **[@Maheswar-Sah00](https://github.com/Maheswar-Sah00)** for
[Vultr Agent Rush](https://lablab.ai/ai-hackathons/vultr-hackathon) on lablab.ai, Track 1: Blast Radius Zero.

Runs on Vultr Cloud Compute, Vultr Serverless Inference and Vultr Object Storage. Uses [gVisor](https://gvisor.dev),
Docker, [FastAPI](https://fastapi.tiangolo.com), [Caddy](https://caddyserver.com), [sslip.io](https://sslip.io),
`libfaketime`, Python `cryptography`, [D3](https://d3js.org), the [Geist](https://vercel.com/font) fonts (OFL), and
[GuardDog](https://github.com/DataDog/guarddog) as the static baseline. Threat research from Elastic Security Labs,
Socket, Trend Micro, Atlassian, ESET, the FBI and the OSCAR authors.
