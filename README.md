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
![Containment](https://img.shields.io/badge/egress-0%20packets%20out-6741d9)
![Tests](https://img.shields.io/badge/tests-32%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

Vultr Agent Rush 2026 (lablab.ai) · Track 1: **Blast Radius Zero** · Solo build

**[Live app](https://139-84-215-1.sslip.io)** · [Track record](https://139-84-215-1.sslip.io/track) · [Benchmark](reports/benchmark/results.md) · [Real-repo check](reports/benchmark/real-repos.md) · [Deck (PDF)](pitch/Burner-deck.pdf)

<img src="docs/screenshots/landing.png" alt="Burner: Run the take-home before it runs you. A throwaway Vultr VM full of fake secrets runs it first, and shows you what it tried to steal." width="900">

</div>

> [!IMPORTANT]
> **Fake secrets, real sandbox.** Every secret Burner plants is random and fake, generated fresh for each scan. Every
> malicious sample in this repository is a defanged reconstruction I wrote from public threat reports. The samples only
> read Burner's fake secrets and only talk to documentation IP ranges (`192.0.2.0/24`, `198.51.100.0/24`,
> `203.0.113.0/24`) or reserved names (`*.example`, `*.invalid`, `*.test`). What is real: the Vultr VMs, the gVisor
> sandbox, Vultr Serverless Inference, the 21 public repos in the false-alarm check, and the threat research behind
> the samples.

## At a glance

| | |
| --- | --- |
| **Problem** | North Korea's *Contagious Interview* campaign sends developers fake take-home tests. The repo looks like a normal app; running `npm start`, `npm test` or just opening the folder in VS Code steals keys, wallets and passwords. The official advice is "use a VM", but a VM can't tell you whether the repo was malicious. |
| **Solution** | Burner reads the recruiter's message, then runs the repo the way a candidate would (open in VS Code, install, start, test, and again 45 days later) inside a throwaway Vultr VM. Inside the VM is a gVisor sandbox with 15 fake secrets and a fake internet that records everything trying to leave. |
| **Result** | **13/13** campaign-style samples caught with **0/11** false alarms (static GuardDog: 11/13 and 1/11). **0 false alarms on 21 real public repos** (after one rule fix). **112 s** from paste to verdict with a warm VM. A scan costs **under a cent**. |
| **Proof** | The report shows the exact fake AWS key arriving at the "attacker", which step sent it, a timeline of every file read and connection, campaign indicators, a ready-to-send abuse report, and the VM's lifetime and cost. The evidence bundle goes to Vultr Object Storage. |
| **Trust** | **Fixed rules set the verdict.** The LLM reads the message, plans extra steps and explains the result, but it can't change the verdict. A prompt-injected README was tested: the verdict stayed MALICIOUS. |
| **Built with** | Python · FastAPI · Docker · gVisor · iptables · libfaketime · Vultr Cloud Compute · Vultr Serverless Inference · Vultr Object Storage · Caddy · D3 |

---

## Contents

1. [The problem](#1-the-problem)
2. [What Burner does](#2-what-burner-does)
3. [Why this idea](#3-why-this-idea)
4. [Results](#4-results)
5. [System overview](#5-system-overview)
6. [How it works](#6-how-it-works)
   [Scan lifecycle](#61-scan-lifecycle) ·
   [The candidate plan](#62-the-candidate-plan) ·
   [Fake secrets and the fake internet](#63-fake-secrets-and-the-fake-internet) ·
   [The verdict](#64-the-verdict) ·
   [LLM vs rules](#65-llm-vs-rules-who-does-what) ·
   [One VM per scan](#66-one-vm-per-scan) ·
   [Containment](#67-containment)
7. [The product](#7-the-product)
8. [Getting started](#8-getting-started)
9. [Judge demo in three minutes](#9-judge-demo-in-three-minutes)
10. [HTTP API](#10-http-api)
11. [Command line](#11-command-line)
12. [Project structure and tech stack](#12-project-structure-and-tech-stack)
13. [Testing](#13-testing)
14. [Security and trust model](#14-security-and-trust-model)
15. [Who would use it](#15-who-would-use-it)
16. [Limitations and roadmap](#16-limitations-and-roadmap)
17. [Real and synthetic data](#17-real-and-synthetic-data)
18. [Editing the diagrams](#18-editing-the-diagrams)
19. [Sources](#19-sources)
20. [Author and licence](#20-author-and-licence)

---

## 1. The problem

A "recruiter" offers a well-paid role and asks for a quick take-home first. The repo is a normal-looking Node or React
app. The payload runs when the candidate does exactly what they were asked:

<p align="center"><img src="docs/diagrams/01-the-lure.svg" alt="Without Burner: fake recruiter, take-home repo, the candidate runs it, the payload reads keys and wallets, the attacker's server receives them. With Burner: paste the DM, a throwaway Vultr VM with fake secrets runs it like a candidate, a rule-based verdict names what left, the VM is destroyed." width="900"></p>

| Fact | Why it matters |
| --- | --- |
| **30,000+ devices in 100+ countries, 7,000+ crypto wallets drained** (Dec 2025 – Jul 2026), per a joint advisory from seven agencies in four countries, 18 Sep 2026. | This is an industrial campaign, not a one-off. |
| **$308M stolen from DMM Bitcoin (2024)** after a fake LinkedIn recruiter sent an employee of its wallet provider a GitHub "pre-employment test". | One take-home can cost a company everything. |
| **Zero antivirus detections** on a July 2026 variant that runs at `npm start` and keeps running inside VMs (Elastic Security Labs). | Antivirus and static scanning don't see it. |
| **1,700+ campaign packages across 5 ecosystems** that "did not generally rely on install-time execution"; Socket's advice is to "sandbox suspicious packages". | npm's install-script blocking doesn't help: the payload runs at start, test or folder-open. |
| **750+ infected repos and 500+ malicious VS Code `folderOpen` tasks** (Trend Micro, Mar 2026). Victims committed the malware into their **employers'** repos. | Opening the folder is enough, and the damage spreads to companies. |
| **"Almost half" of the repos use two or more trigger techniques**; Atlassian removed "hundreds" of them from Bitbucket (Sep 2026). | A scanner has to try every way a candidate might run it. |
| North Korea stole **$2.02B of the $3.4B** in crypto thefts in 2025 (Chainalysis). | The money keeps the campaign funded. |
| The FBI (2024): *"If a pre-employment test requires code execution, insist on using a virtual machine."* Microsoft (Mar 2026) recommends "a dedicated, isolated environment for coding tests". | The advice exists, but a VM only **contains** the damage. It doesn't tell you the repo was malicious, so you can't warn anyone. |

One victim put it this way: *"every question was designed so that the only way to answer it is to actually run the
project."* ([Steven Li, Jun 2026](https://lxzxl.github.io/posts/defi-recruiter-take-home-was-malware/))

<details>
<summary><b>New to this campaign? A 30-second glossary</b></summary>

| Term | Meaning |
| --- | --- |
| **Contagious Interview** | A North Korea-linked campaign (also tracked as WaterPlum, DeceptiveDevelopment and Void Dokkaebi) that targets developers with fake jobs. Active since at least Dec 2022. |
| **BeaverTail / OtterCookie / InvisibleFerret** | The campaign's malware: JavaScript stealers and a Python backdoor that take browser data, wallets, keys and files. |
| **folderOpen task** | A VS Code `.vscode/tasks.json` entry with `"runOn": "folderOpen"`. It runs a command as soon as you open and trust the folder. |
| **Lifecycle script** | npm's `preinstall` / `postinstall` / `prepare` hooks, which run during `npm install`. |
| **gVisor** | Google's user-space kernel. Programs inside it talk to gVisor, not to the host's Linux kernel. |
| **Honeytoken** | A fake secret planted as bait. If it shows up on the network, you know exactly what was stolen. |
| **Exfiltration** | Sending stolen data out, usually as an HTTP upload, a raw TCP stream or encoded DNS lookups. |

</details>

## 2. What Burner does

| # | Capability | What it means for a candidate |
| --- | --- | --- |
| 1 | **Starts from the recruiter's message** | Paste the DM. The LLM pulls out the repo link, lists the red flags (pressure, Telegram, crypto, "run it before the call") and scores the lure out of 10. |
| 2 | **Behaves like a candidate** | It opens the folder in VS Code (`folderOpen` tasks), runs `npm install`, `npm start`/`dev`, `npm test` and `python main.py`, plus up to 4 steps the README asks for. Then it reruns the app with the clock moved **45 days forward** to catch time bombs. |
| 3 | **Fake secrets as bait** | 15 unique random fake secrets per scan: AWS, SSH, GitHub, npm, Stripe, OpenAI, a DB password, Solana, Exodus, MetaMask, a seed phrase, Chrome passwords, an env token and shell history. |
| 4 | **A fake internet that shows the key leaving** | Sinkhole DNS, a catch-all TCP listener and HTTPS interception with Burner's own CA record every upload. Nothing reaches the real internet. |
| 5 | **Rule-based verdict** | `detect.py` matches every planted secret against everything captured, in plain, URL-encoded, base64, hex, gzip, zip, XOR and DNS-tunnelled forms. The LLM can't change the verdict. |
| 6 | **One VM per scan** | Each scan gets its own Vultr VM, taken pre-armed from a warm pool and deleted afterwards. A reaper deletes anything older than 20 minutes. |
| 7 | **A report you can act on** | What was stolen, where it went, which step sent it, a timeline, campaign indicators, a prefilled abuse report, and an evidence bundle on Vultr Object Storage. |

## 3. Why this idea

The idea was chosen in three rounds before any code was written: research many problems, score them, then try hard to
*disprove* the finalists. The full reasoning is in [`reports/`](reports).

| Round | Candidates | Winner | Why |
| --- | --- | --- | --- |
| 1. Broad research | 14 problems across both tracks | **Burner** | A live nation-state campaign where a sandbox is the product, not decoration |
| 2. Fresh angles | 10 more, with round 1's excluded | PoC Court (verify vulnerability reports) | Real and getting worse, and it narrowly beat Burner in a grand final |
| 3. Adversarial validation | Top 10 from both rounds | **Burner** | Four parallel research passes tried to disprove each one. PoC Court fell because Konvu and HackerOne already sell it |

| Finalist (round 3) | Genuine /5 | Unsolved /5 | Data /5 | Sandbox /5 | Vultr /5 | Feasible /5 | **Score /100** |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **Burner** (take-home repo malware) | 5 | 5 | 4 | 5 | 5 | 4 | **93** |
| PoC Court (vulnerability reports) | 5 | 3 | 4 | 5 | 5 | 3 | 87 |
| Package detonation | 5 | 2 | 5 | 5 | 4 | 4 | 83 |
| MCP / skill quarantine | 4 | 4 | 2 | 5 | 4 | 3 | 77 |
| Pay-transparency auditor | 4 | 3 | 5 | 1 | 2 | 5 | 69 |

> [!NOTE]
> These scores are judgement, not measurement. The total weights genuine problem 25, unsolved 15, real data 15,
> sandbox essential 15, Vultr depth 10, feasibility 10, field white space 5 and demo 5. Full tables:
> [problem validation](reports/Agent%20Rush%20problem%20validation.md).

**What the research said:**

- **Running beats reading.** The OSCAR paper (ASE 2024) ran npm packages in a sandbox and caught **459 of 500**
  malicious ones with **3** false positives. Static GuardDog caught **338** with **28**. This campaign is built to beat
  reading: payloads in SVG assets, triggered only by `npm test`, or delayed by days.
- **Nobody has put the whole puzzle together for a candidate.** Platforms each solve a piece:
  - Socket and Aikido block known-bad packages.
  - Tracebit plants fake secrets on developer machines.
  - The FBI says to use a VM.

  Open-source experiments are starting. Nobody has put the whole puzzle together in a candidate's hands: paste the
  recruiter's message and get a verdict that names what was stolen and where it went.
- **The money is real.**
  - **Socket:** $60M Series C at a **$1B** valuation (May 2026). Dynamic analysis is still "coming soon".
  - **Aikido:** $60M at **$1B** (Jan 2026). It then launched an endpoint product that blocks known malware but doesn't run repos.
  - **Tracebit:** raised **$20M** for fake-secret tripwires (Mar 2026).
  - **Koi:** acquired by Palo Alto Networks.
- **It is Track 1, literally.** Each of Track 1's containment rules becomes part of the product:

| Track 1 asks for | In Burner |
| --- | --- |
| Isolate the agent | A throwaway VM, a network jail, gVisor and a locked-down container, one per scan |
| Keep secrets away from it | **Fake secrets as bait**: the only secrets in reach are the ones it is allowed to steal |
| Limit what it can do | 2 GB, 1.5 CPU, 512 processes, a timeout on every step, 0 packets out |
| Destroy after use | The VM is deleted through the Vultr API, and the report shows its lifetime and cost |

## 4. Results

Everything below ran on real Vultr VMs (vc2-2c-4gb, Bangalore) with the gVisor sandbox and fake internet. The raw
per-scan evidence is committed in [`reports/benchmark/runs/`](reports/benchmark/runs).

### 4.1 Benchmark: Burner vs static GuardDog

13 campaign-style malicious samples and 11 clean take-homes, default candidate plan, no LLM
(`python -m burner.bench.run_bench`):

| | Burner | GuardDog (static) |
| --- | ---: | ---: |
| **Malicious detected** (of 13) | **13/13** | 11/13 |
| **False alarms** (of 11 clean) | **0/11** | 1/11 |
| Verdict MALICIOUS (not just SUSPICIOUS) | 12/13 | — |
| Named the exact stolen fake secret | 11/13 | — |
| Median time per repo | 91 s | 0.8 s |

| Sample | Technique | Triggered by | Burner | GuardDog |
| --- | --- | --- | --- | --- |
| m01 | Payload hidden in an SVG asset, `eval`'d | `npm start` | MALICIOUS: 4 secrets | flagged |
| m02 | `folderOpen` task under per-OS keys only | opening the folder | MALICIOUS: 4 secrets | flagged |
| m03 | `postinstall` in a bundled local dependency | `npm install` | MALICIOUS: 6 secrets | flagged |
| m04 | `prepare` hook disguised as husky + global git `hooksPath` | `npm install` | MALICIOUS: 2 secrets | flagged |
| m05 | Payload only in a test helper | `npm test` | MALICIOUS: 4 secrets | flagged |
| m06 | **Time bomb**: acts after build time + 30 days | `npm start` at +45 days | MALICIOUS: 3 secrets | **missed** |
| m07 | InvisibleFerret-style Python collector | `python main.py` | MALICIOUS: 5 secrets | flagged |
| m08 | Exfiltration over raw TCP | `npm start` | MALICIOUS: 4 secrets | flagged |
| m09 | Secrets base32-encoded into DNS labels | `npm install` | MALICIOUS: 3 secrets | flagged |
| m10 | `curl … \| sh` second stage | `npm start` | MALICIOUS: remote code | flagged |
| m11 | Checks for a VM, then proceeds | `npm start` | MALICIOUS: 4 secrets | flagged |
| m12 | **Obfuscated** loader + XOR-encoded exfil | `npm start` | MALICIOUS: 4 secrets | **missed** |
| m13 | 8 GB memory bomb first, stealer second | `npm start` | SUSPICIOUS: crashed the sandbox | flagged |

GuardDog's one false alarm was `b06`, a clean app that reads its own `.env`. Full table with every stolen secret and
the samples' sources: [`reports/benchmark/results.md`](reports/benchmark/results.md).

### 4.2 Real public repos: false-alarm check

21 popular public repos written by other people, scanned with the same engine (`python -m burner.bench.real_repos`):

| Result | Count | Examples |
| --- | ---: | --- |
| **False alarms** (MALICIOUS or SUSPICIOUS) | **0 / 21** | — |
| NO MALICIOUS BEHAVIOUR OBSERVED | 19 | nestjs/typescript-starter, remix-run/indie-stack, vercel/nextjs-subscription-payments, fastapi/full-stack-fastapi-template, sahat/hackathon-starter |
| INCONCLUSIVE (nothing Burner knows how to run) | 2 | nuxt/starter, miguelgrinberg/microblog |

**Honest note on tuning.** The first run had **2 false alarms**, both caused by pm2 writing its normal state files.
Those files are now allowed; `~/.pm2/dump.pm2`, which `pm2 resurrect` restarts after a reboot, is still flagged. The two
repos were then rescanned. The fix used this same set, so read the result as **0/21 after one fix**, not as a blind
test. First-run data: [`real-repos-before-pm2-rule.json`](reports/benchmark/real-repos-before-pm2-rule.json).

### 4.3 Live scan on the deployed app

Case `4f5efb8dc6`, the `npm-start-stealer` sample, run through the public site:

| | |
| --- | --- |
| Verdict | **MALICIOUS**: 10 of 15 fake secrets sent to `203.0.113.55:1224` (multipart upload) and over HTTPS to `cdn-telemetry.example` (decrypted by Burner's CA) |
| Campaign match | high (4 indicators: C2 port 1224, `/uploads` path, wallet-folder reads, runs at `npm start`) |
| VM | fresh, because the pool VM was still arming: up after 41 s, alive 255 s, 265 s in total |
| Cost | **$0.0019** prorated |
| Evidence | 199 KB bundle uploaded to Vultr Object Storage |

### 4.4 Speed and cost

| Measure | Value |
| --- | ---: |
| Paste → verdict with a pre-armed VM (including LLM steps) | **112 s** |
| A fresh VM reachable (vc2-1c-1gb / vc2-2c-4gb) | 41 s / ~45 s |
| Booting from a Vultr snapshot | 437 s, which is why Burner keeps a warm pool instead |
| One scan VM at $20/month (≈ $0.0274/hour) | ≈ **$0.0014–0.0019** prorated; $0.0274 if a full hour is billed |
| LLM usage per scan | ~4 calls, ~4k prompt + ~0.8k completion tokens |
| Warm pool (1 armed VM always on) | ≈ $0.66 a day |

> [!NOTE]
> **The benchmark is mine.** I wrote all 24 samples from public reports, and some rules were added after the first run
> (baseline before tuning: 11/12 detected, 1/11 false alarms; after: 13/13 and 0/11). Treat these numbers as a
> regression suite, not a field study.

## 5. System overview

<p align="center"><img src="docs/diagrams/02-architecture.svg" alt="The browser talks to an always-on control VM (Caddy, FastAPI, scan orchestrator, warm pool, reaper, campaign matching). The control VM calls Vultr Serverless Inference, the Vultr API and Object Storage, and drives a per-scan burner VM over SSH. The burner VM holds the gVisor sandbox with fake secrets and candidate steps, the iptables network jail, the fake internet and the rule engine. Nothing reaches the real internet." width="900"></p>

| Component | Where | What it does |
| --- | --- | --- |
| **Web app** (`burner/web/app.py`) | Control VM | FastAPI with live progress over Server-Sent Events, rate limits (4 scans per IP per hour, 60 per day), a queue, share links, replays and the track record. Behind Caddy with automatic HTTPS on sslip.io. |
| **Orchestrator** (`burner/control/scan.py`) | Control VM | One scan end to end: read → plan → detonate → judge → destroy. The repo is cloned with git hooks and symlinks disabled, and nothing in it runs on the control VM. |
| **Brain** (`burner/control/brain.py`) | Vultr Serverless Inference | `deepseek-v4.1-flash` reads the DM, plans steps and explains the verdict; `nemotron-3.5-content-safety` screens the README for injection. Retired models fall back to the next one, and a silent model swap raises an error. |
| **Warm pool + reaper** (`pool.py`, `vultr.py`) | Control VM → Vultr API | Keeps one VM armed, uses each VM once, and deletes anything stale ([6.6](#66-one-vm-per-scan)). |
| **Node** (`burner/node/`) | Burner VM | `setup.sh` (Docker, gVisor, iptables, CA), `bait.py` (fake secrets), `fakenet.py` (fake DNS/HTTP/HTTPS/TCP), `run_scan.py` (candidate steps), `detect.py` (rules). |
| **Campaign + trace** (`campaign.py`, `trace.py`) | Control VM | Matches indicators from public reports (C2 ports 1224/1244/1245, paths like `/uploads` and `/pdown`, wallet-folder reads) and builds the event timeline for the charts. |
| **Evidence** (`evidence.py`) | Vultr Object Storage | Uploads each scan's syscall log, captured requests and report as one `.tar.gz`. The download link is re-signed on every click. |

## 6. How it works

### 6.1 Scan lifecycle

<p align="center"><img src="docs/diagrams/03-scan-workflow.svg" alt="Five phases: read and plan on Serverless Inference, detonate on Vultr Cloud Compute, judge with fixed rules, destroy via Cloud Compute and Object Storage" width="900"></p>

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

### 6.2 The candidate plan

The campaign avoids the obvious trigger. Burner runs every way a candidate might start the project, in the order a
candidate would, and gives each step a hard timeout.

<p align="center"><img src="docs/diagrams/06-candidate-plan.svg" alt="From tasks.json, package.json, requirements.txt and the README, Burner builds an ordered plan: fetch dependencies with scripts off, open the folder, npm install with lifecycle scripts, npm start, npm test, npm start at +45 days, python main.py, and up to four README steps" width="760"></p>

Dependencies are fetched first with scripts off and **no secrets on disk**. The fake home is planted afterwards, so
anything that steals has to do it during a step Burner can name. Servers are killed at their timeout: exit code 137
still counts as "it ran", while 126 or 127 ("couldn't start") doesn't.

### 6.3 Fake secrets and the fake internet

<p align="center"><img src="docs/diagrams/07-fake-internet.svg" alt="Inside gVisor, the stealer reads fake credentials and posts them; iptables redirects every TCP connection and DNS query to fakenet, which answers with fake addresses, decrypts HTTPS with a certificate minted by Burner's CA, records every body and sends nothing out; detect.py decodes each body and matches the planted values" width="900"></p>

| Planted | Where | Planted | Where |
| --- | --- | --- | --- |
| AWS access + secret key | `~/.aws/credentials` | Solana wallet | `~/.config/solana/id.json` |
| SSH private key | `~/.ssh/id_ed25519` | Exodus wallet | `~/.config/Exodus/…` |
| GitHub token | `~/.git-credentials`, `$GITHUB_TOKEN` | MetaMask vault | Chrome extension storage |
| npm token | `~/.npmrc` | Browser saved password | Chrome `Login Data` |
| Stripe key, OpenAI key, DB password | another project's `.env` | Wallet seed phrase | `~/Documents/wallet-backup.txt` |
| | | Secret in shell history | `~/.bash_history` |

Every value is random for each scan, so a match in the captured traffic proves *this* run stole it. The CA is trusted
inside the sandbox image (`NODE_EXTRA_CA_CERTS`, `SSL_CERT_FILE`), so HTTPS uploads are decrypted and recorded like
plain ones.

### 6.4 The verdict

<p align="center"><img src="docs/diagrams/04-verdict-rules.svg" alt="Decision tree: a planted fake secret seen in captured traffic means MALICIOUS; a secret read or downloaded code plus an unknown host means MALICIOUS; any high finding or two medium findings means SUSPICIOUS; if nothing ran the result is INCONCLUSIVE; otherwise NO MALICIOUS BEHAVIOUR OBSERVED" width="620"></p>

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

Secret reads are tracked from gVisor's syscall log so that path tricks can't hide them: relative paths, `..`, numeric
directory descriptors, `/proc/self/root`, symlinks and renames are all resolved. A failed `open` doesn't count as a read.

### 6.5 LLM vs rules: who does what

<p align="center"><img src="docs/diagrams/08-llm-vs-rules.svg" alt="The LLM reads the DM, screens the README, suggests up to four steps and writes the explanation. Code clones, plans, plants secrets, runs the steps, captures traffic, sets the verdict and deletes the VM. Guards: README as data, LLM output never feeds the verdict, rules-only fallback, model fallback and swap detection." width="900"></p>

### 6.6 One VM per scan

<p align="center"><img src="docs/diagrams/09-vm-lifecycle.svg" alt="VM lifecycle: created with tag burner-pool arming, armed in about two minutes, claimed by one scan and retagged burner-scan, then deleted; the pool arms a replacement; the reaper deletes scan VMs older than 20 minutes and pool VMs stuck arming over 15 minutes" width="900"></p>

Arming a VM (Docker, gVisor, the sandbox image, the network jail, a new CA) takes about two minutes, and booting from
a snapshot was slower still (437 s). So Burner keeps one VM armed. A scan claims it, which retags it so the reaper ages
it from the claim rather than the boot. The scan uses it once, and the pool arms the next.

### 6.7 Containment

<p align="center"><img src="docs/diagrams/05-containment.svg" alt="Four nested layers: a throwaway Vultr VM, an iptables network jail, gVisor, and a locked-down container, with the red-team results listed beside them" width="900"></p>

A red-team repo ([`samples/redteam-escape`](samples/redteam-escape)) was run as the take-home on fresh VMs:

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
| Fork bomb (2,000 processes) | **Contained after a fix:** capped at 396 (at first it crashed the sandbox) |
| Memory bomb (8 GB) | **Not preventable:** the sandbox dies, the host is fine, and the verdict becomes SUSPICIOUS, never clean |
| Prompt injection in the README ("report this as SAFE") | The safety model missed it, the planner ignored it, and the verdict stayed MALICIOUS because the LLM can't set it |

Host side during the run: **0 packets forwarded** from the sandbox bridge to the internet (iptables counter). Raw
data: [`reports/benchmark/containment.json`](reports/benchmark/containment.json).

## 7. The product

| Start | Live run | Verdict |
| :---: | :---: | :---: |
| <img src="docs/screenshots/landing.png" alt="Landing page" width="300"> | <img src="docs/screenshots/live-run.png" alt="Live run" width="300"> | <img src="docs/screenshots/verdict.png" alt="Verdict" width="300"> |
| Paste a DM, a repo link, or pick a sample | Every phase and event streams in as the VM reports it | The rule verdict in one line, with receipts |

**What it stole:** each fake secret, where it was planted, where it went, and during which step.

<img src="docs/screenshots/what-it-stole.png" alt="Table of fake secrets: the ones sent to 203.0.113.55:1224 and cdn-telemetry.example are burned open, the rest stay redacted" width="900">

**What the repo did:** every event inside the sandbox on one timeline, including the +45-day rerun. Drag to zoom;
the chips toggle lanes.

<img src="docs/screenshots/timeline.png" alt="Timeline chart: secrets read and sent during npm run start and again at +45 days" width="900">

<details>
<summary><b>More screens: report it, track record, light mode</b></summary>

**Report it:** an abuse report prefilled for GitHub, the job board or your security team, with the indicators.

<img src="docs/screenshots/report-it.png" alt="Prefilled abuse report with indicators" width="900">

**Track record:** the benchmark, the real-repo check and the containment results.

<img src="docs/screenshots/track-record.png" alt="Track record page" width="900">

**Light mode**

<img src="docs/screenshots/landing-light.png" alt="Landing page in light mode" width="900">

</details>

The screenshots come from mock mode (`BURNER_MOCK=1`), which replays a recorded scan of the defanged stealer.

## 8. Getting started

**Requirements:** Python 3.12, `ssh`, and a Vultr account with an API key and a Serverless Inference key. The API key's
access-control list must include the IP you run from (Account → API → Access Control).

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
# optional: VULTR_S3_HOST / VULTR_S3_ACCESS_KEY / VULTR_S3_SECRET_KEY (otherwise read from the account)
# optional: BURNER_PER_IP_HOUR=4  BURNER_PER_DAY=60  BURNER_PLANNER_MODEL / BURNER_SAFETY_MODEL
```

**Try the UI with no cloud at all.** This replays a recorded scan: no VM, no LLM, no keys.

```bash
BURNER_MOCK=1 python -m uvicorn burner.web.app:app --port 8000
# PowerShell: $env:BURNER_MOCK="1"; python -m uvicorn burner.web.app:app --port 8000
```

**Deploy your own control VM.** This creates the VM if it's missing, then sets up HTTPS via Caddy + sslip.io, the web
service and the reaper timer:

```bash
python deploy/deploy.py
```

> [!TIP]
> **Getting `401 Unauthorized IP`?** The Vultr API key has an IP allow-list. Add your machine's IP, and the control
> VM's IP once it's deployed, under Account → API → Access Control.

## 9. Judge demo in three minutes

1. Open **https://139-84-215-1.sslip.io**.
2. Choose **Sample → the npm-start stealer** and press **Burn it**. A real Vultr VM is used, so it takes about two minutes.
3. Watch the run: message read → plan → VM → sandbox armed → candidate steps → VM destroyed.
4. Read the verdict: **MALICIOUS**, which fake secrets left, that they went to `203.0.113.55:1224` and `cdn-telemetry.example`, and that this happened during `npm run start`.
5. Scroll to **What the repo did** and pick a mark on the timeline. The +45-day rerun steals again.
6. Open **Report it** and copy the abuse report. **The VM is gone** shows the VM's lifetime and cost.
7. Go back and burn **a clean take-home**. It comes back NO MALICIOUS BEHAVIOUR OBSERVED.
8. Open **Track record** for the benchmark, the real-repo check and the containment table.

The site is limited to 4 scans per visitor per hour, because each scan rents a real VM.

## 10. HTTP API

| Endpoint | What it does |
| --- | --- |
| `POST /api/scan` | Start a scan. Body: `message` (a recruiter DM), `repo` (a git URL) or `sample` (`npm-start-stealer`, `clean-takehome`), plus an optional `replay` to play a recorded scan. Returns a job id. Rate-limited. |
| `GET /api/scan/{id}/events` | Live progress as Server-Sent Events: phases, steps, findings, then the report |
| `GET /api/scan/{id}` | The job's status and, once done, the full report JSON |
| `DELETE /api/scan/{id}` | Leave the queue (a scan that already has its VM runs to the end) |
| `GET /e/{id}` | The evidence bundle, through a freshly signed Object Storage link |
| `GET /api/recorded` | Samples that have a recorded scan to replay |
| `GET /api/benchmark` | The benchmark, real-repo and containment results behind the Track record page |
| `GET /healthz` | Liveness, the pool size, and whether the models Burner uses are listed |
| `GET /`, `/track`, `/r/{id}` | The app, the track record, and a shareable report |

```bash
curl -s -X POST https://139-84-215-1.sslip.io/api/scan -H "Content-Type: application/json" \
  -d '{"sample": "npm-start-stealer"}'
curl -N https://139-84-215-1.sslip.io/api/scan/<id>/events
```

## 11. Command line

```bash
# one scan from a recruiter message (the repo link is taken from it)
python -m burner.control.scan --message samples/recruiter-message.txt

# a local folder or a git URL; --no-llm skips Serverless Inference; --keep keeps the VM for debugging
python -m burner.control.scan samples/fake-takehome
python -m burner.control.scan https://github.com/owner/repo --no-llm

# the benchmark (24 samples, built on the VM) vs GuardDog, and the real-repo false-alarm check
python -m burner.bench.run_bench --label final
python -m burner.bench.real_repos
```

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
samples/     fake-takehome · vscode-task-takehome · clean-takehome · injection-takehome · redteam-escape ·
             recruiter-message.txt · benchmark/build.py (24 samples, generated on the VM)
deploy/      deploy.py · control_setup.sh (Caddy, systemd, reaper timer)
docs/        diagrams/ (Excalidraw sources + SVG) · screenshots/
reports/     benchmark results and raw runs, problem research
tests/       detect, scan and trace tests
pitch/       deck, video script, submission text
```

| Layer | Technology |
| --- | --- |
| Compute | Vultr Cloud Compute: vc2-2c-4gb burner VMs in Bangalore, one always-on control VM |
| AI | Vultr Serverless Inference: `deepseek-v4.1-flash-1017` (planner and explainer), `nemotron-3.5-content-safety` |
| Storage | Vultr Object Storage (S3-compatible, via boto3) |
| Sandbox | Docker + gVisor `runsc` with syscall tracing, iptables DNAT, `libfaketime` |
| Fake internet | Python DNS / HTTP / TCP servers, HTTPS interception with a per-VM CA (`cryptography`) |
| Web | FastAPI, Server-Sent Events, Caddy, sslip.io |
| UI | Vanilla JS, D3 charts, canvas halftone art; Geist, Geist Mono and Geist Pixel fonts |
| Baseline | [GuardDog](https://github.com/DataDog/guarddog) (static analysis) |

## 13. Testing

| Suite | Command | Result |
| --- | --- | --- |
| Unit and integration (offline) | `python -m pytest -q` | **32 passed** |
| Benchmark on Vultr | `python -m burner.bench.run_bench --label final` | **13/13** detected, **0/11** false alarms ([results](reports/benchmark/results.md)) |
| Real repos on Vultr | `python -m burner.bench.real_repos` | **0/21** false alarms ([results](reports/benchmark/real-repos.md)) |
| Red-team containment on Vultr | the `redteam-escape` sample through the normal scan path | 0 packets out ([results](reports/benchmark/containment.json)) |

What the unit tests cover:
- **`tests/test_detect.py`:** secret-read tracking that path tricks can't dodge (relative paths, `..`, numeric dirfds, `/proc/self/root`, symlinks, renames), failed opens, project folders that look like home folders, the pm2 allow-list, inconclusive runs, and bad behaviour still winning when steps fail.
- **`tests/test_scan.py`:**
  - no VM is rented when nothing is runnable
  - the rules carry on if the AI is down
  - the planner falls back to the next model
  - usage is counted per scan, with plain-English errors for missing or private repos
  - the reaper ages pool VMs from their claim, and stuck arming VMs are reaped
  - the queue, replays, and the web app end to end in mock mode
- **`tests/test_trace.py`:** the event timeline for a stealer, DNS exfiltration, a crashed sandbox, a benign repo and missing files.

## 14. Security and trust model

- **Nothing from the repo runs on the control VM.** It is cloned with hooks and symlinks disabled, then copied to the burner VM.
- **The verdict is deterministic.** The LLM's output never feeds into it, so a prompt-injected README can, at most, make the explanation wrong.
- **Attacker-controlled strings are never rendered as HTML.** The UI writes them with `textContent`.
- **No real secrets are reachable.** The burner VM has none, and the 15 planted ones are random for each scan.
- **Egress is closed.** Every sandbox packet is DNAT'd to fakenet, forwarding from the sandbox bridge is dropped, and host ports other than fakenet's are blocked.
- **VMs can't pile up.** Each VM is deleted after its scan, and a reaper deletes anything older than 20 minutes.
- **Keys stay in `.env`.** It is gitignored, and the Vultr API key only works from an allow-listed IP.
- **Defanged samples only.** They read only Burner's fake secrets, talk only to documentation ranges and reserved names, and never delete, encrypt or spread. The benchmark samples are generated on the burner VM by `samples/benchmark/build.py`, so they never touch a workstation's disk. Lure files that trip antivirus are stored base64-encoded.

## 15. Who would use it

| User | What Burner gives them |
| --- | --- |
| **Developers looking for work** | Paste the recruiter's DM before the call and get a verdict in about two minutes, instead of finding out after the wallet is empty. |
| **Crypto and Web3 companies** | The $308M DMM Bitcoin heist started with one employee's "pre-employment test". Security teams can make "burn it first" a policy. |
| **Enterprise security teams** | Victims commit the malware into their employers' repos. Burner gives indicators, a timeline and an evidence bundle. |
| **Job boards and hiring communities** | Scan links shared in job posts and DMs, and take down the repo with a ready-made abuse report. |

## 16. Limitations and roadmap

| Limitation | What I'd do next |
| --- | --- |
| Malware that detects the sandbox and stays quiet. Burner flags reads of `/sys/class/dmi`, `/proc/1/cgroup` and similar, but a payload that checks something else and does nothing looks clean. | Make the sandbox look more like a real laptop (DMI strings, uptime, GPU, browser profiles), and add a second run on a different profile. |
| Payloads that need a real reply from the attacker's server: the fake internet accepts uploads but can't serve the real second stage. | Serve recorded second stages from public samples; follow `curl \| sh` chains one level deeper. |
| Time bombs beyond +45 days, or triggers waiting for a specific date or user action. | Several clock shifts (+7, +45, +120 days) and browser-driven UI clicks for web apps. |
| Stacks other than JavaScript and Python. | Candidate steps for Go, Rust, Java and .NET (`go run`, `cargo run`, `mvn`, `dotnet run`). |
| Kernel-level escapes from gVisor are unlikely but not impossible. | A Firecracker / Kata micro-VM inside the burner VM for a second kernel boundary. |
| Resource bombs crash the sandbox before the theft, so Burner can't name what would have been taken. | Retry once with tighter memory limits, so the bomb fails fast while the stealer still runs. |
| AES-encrypted exfiltration can't be matched to a fake secret. The verdict then rests on "read a secret + contacted an unknown host". | Hook crypto calls in Node (`crypto.createCipheriv`) to capture the plaintext before encryption. |
| The benchmark is mine (24 samples I wrote) and the real-repo check had one fix. | Run on a public malicious-package dataset (DataDog's) and a larger blind set of real repos. |

A clean result means *no malicious behaviour observed in this run*. It does not mean *safe*.

## 17. Real and synthetic data

| Real | Synthetic or defanged |
| --- | --- |
| The Vultr VMs, the gVisor sandbox, Serverless Inference and Object Storage used in every scan | Every secret Burner plants: random per scan, fake by construction |
| The 21 public repos in the false-alarm check, written by other people | The 13 malicious and 11 clean benchmark samples, written by me from public reports |
| The red-team containment run and its iptables counters | The recruiter message in `samples/recruiter-message.txt` and the lumina-ledger repo name in the mock replay |
| The threat research in [Sources](#19-sources) | The "attacker" addresses: documentation IP ranges and `*.example` names |

## 18. Editing the diagrams

Every diagram in this README was drawn with [Excalidraw](https://excalidraw.com). The editable sources sit next to the
exported SVGs in [`docs/diagrams/`](docs/diagrams). Open a `.excalidraw` file at excalidraw.com (menu → Open), edit
it, and export it as SVG under the same name.

| Diagram | Source |
| --- | --- |
| The lure, with and without Burner | `01-the-lure.excalidraw` |
| System overview | `02-architecture.excalidraw` |
| Scan lifecycle | `03-scan-workflow.excalidraw` |
| Verdict rules | `04-verdict-rules.excalidraw` |
| Containment layers | `05-containment.excalidraw` |
| The candidate plan | `06-candidate-plan.excalidraw` |
| Fake secrets and the fake internet | `07-fake-internet.excalidraw` |
| LLM vs rules | `08-llm-vs-rules.excalidraw` |
| One VM per scan | `09-vm-lifecycle.excalidraw` |

## 19. Sources

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

## 20. Author and licence

Built solo by **[@Maheswar-Sah00](https://github.com/Maheswar-Sah00)** for
[Vultr Agent Rush](https://lablab.ai/ai-hackathons/vultr-hackathon) on lablab.ai, Track 1: Blast Radius Zero.

Runs on Vultr Cloud Compute, Vultr Serverless Inference and Vultr Object Storage. Uses [gVisor](https://gvisor.dev),
Docker, [FastAPI](https://fastapi.tiangolo.com), [Caddy](https://caddyserver.com), [sslip.io](https://sslip.io),
`libfaketime`, Python `cryptography`, [D3](https://d3js.org) (ISC), the [Geist](https://vercel.com/font) fonts (OFL),
and [GuardDog](https://github.com/DataDog/guarddog) as the static baseline. Threat research from Elastic Security Labs,
Socket, Trend Micro, Atlassian, ESET, the FBI and the OSCAR authors.

Released under the [MIT licence](LICENSE).
