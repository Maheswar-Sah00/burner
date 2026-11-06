# Agent Rush problem validation (round 3)

Vultr Agent Rush (lablab.ai). Written 4 Nov 2026. Submission closes **Mon 9 Nov 03:30 IST**; target 22:00 IST Sun 8 Nov.

**Why this round exists.** Rounds 1 and 2 scored "it's your problem" at 10%. That was a misreading. The requirement is that the problem is **genuine**: current, evidenced, costly and still unsolved, whoever has it. This round removes personal fit and puts the top 10 finalists from both rounds through **adversarial validation**: four parallel research passes told to try to *disprove* each problem. I then verified the decisive sources myself.

Notes: `research_notes/Agent Rush problem validation/`.

---

## 1. Result

**Champion: Burner.** A sandbox agent that runs a take-home or "test challenge" repo from an unknown recruiter, baits it with fake secrets, and reports what it tried to steal before a developer runs it.

**Why it won.** Once personal fit is removed, it is the **most genuine and least solved** problem of the ten:
- **Live campaign:** a new variant in July 2026 had **zero antivirus detections**.
- **npm's new defaults miss it:** npm v12's install-script blocking doesn't help, because the payload runs at `npm start`, not at install.
- **No shipping tool executes and watches the repo:** every scanner found only reads code.

**PoC Court, the round-2 champion, fell to second.** Its problem is real and getting worse (Google froze its open-source bounty on 1 Oct 2026). But validation found **Konvu already sells exactly "deploy the reported version, run the exploit in a sandbox, return a verdict"**, and HackerOne sells h1 Validation.

---

## 2. Verified by me (4 Nov)

| Claim | Check | Source |
|---|---|---|
| A new Contagious Interview variant evades antivirus and runs at server start | ✔ Elastic, 18 Jul 2026: a fake recruiter "Maxwell" in Elastic's community Slack (26 May 2026); 7 trojanised repos "not flagged by any AV vendors"; payload runs on `npm run dev` / `npm start`; checks for VMs but **keeps running** and just tags them "(VM)"; steals `.env`, `.pem`, `.ssh`, `.aws`, 25 crypto wallets, browser logins, clipboard | [Elastic Security Labs](https://www.elastic.co/security-labs/threat-command/contagious-interview-malware-svg-steganography) |
| The campaign is industrial and avoids install-time execution | ✔ Socket, 7 Apr 2026: "more than 1,700 malicious packages" across npm, PyPI, Go, crates.io and Packagist; "did not generally rely on install-time execution"; recommends teams "sandbox suspicious packages" | [Socket](https://socket.dev/blog/contagious-interview-campaign-spreads-across-5-ecosystems) |
| Google froze its open-source bounty over automated reports | ✔ Paused from 1 Oct 2026, at least until Q1 2027; "vast majority" invalid; supply-chain reports still open | [BleepingComputer](https://bleepingcomputer.com/news/google/google-halts-open-source-bug-bounty-program-amid-ai-spam-surge), [The Hacker News](https://thehackernews.com/2026/10/google-pauses-oss-product-bug-bounty.html) |
| PoC execution is already a product | ✔ Konvu: "deployed at the exact reported version", disposable infrastructure per report, verdict with transcript; integrates with HackerOne, Bugcrowd, Intigriti and YesWeHack (vendor claims) | [Konvu Bug Bounty Triage](https://konvu-website.pages.dev/product/bug-bounty-triage) |
| Pay-transparency non-compliance | ✔ NY Fed: "approximately 24 percent of ads do not comply" in Colorado, California, Washington and NYC (Lightcast data, Jan 2025) | [Liberty Street Economics](https://libertystreeteconomics.newyorkfed.org/2025/10/do-employers-comply-with-pay-transparency-requirements-in-job-postings) |
| Earlier live tests carried forward | Six indexed gov.in hijacks: 0 still live. curl slop list: 49 of 49 fetched as JSON, 45 with code PoCs. curl CVE feed: 239 entries. Greenhouse: Airbnb 175 of 213, GitLab 105 of 239 jobs with pay ranges | Round-2 report |

---

## 3. Validation verdicts

| Candidate | Verdict | Strongest evidence for | Strongest evidence against |
|---|---|---|---|
| **Burner** (take-home repo malware) | **Genuine and unsolved**, medium-high confidence | Elastic Jul 2026 zero-detection variant; Socket's 1,700+ packages; runs at `npm start` so npm v12 misses it | A disposable VM already contains damage (but gives no verdict); loss figures are vendor-reported; attackers tag VMs and could hold back later stages |
| **PoC Court** (verify vulnerability reports) | Genuine but **partly solved**, medium-high | Google OSS VRP freeze (Oct 2026); HackerOne submissions up 76% year on year (Mar 2026); kernel now asks for a working reproducer (May 2026) | Konvu and h1 Validation already execute PoCs; curl says slop is "not a problem anymore" (Apr 2026), so the 49-report set measures 2025's problem; only ~6% of Glasswing vulnerabilities were patched (so the bottleneck may be fixing) |
| Package detonation | Genuine but **largely solved** | ChainDrop (Aug 2026, 400+ packages, some with valid provenance) | npm v12 disables install scripts by default; Socket Firewall and Aikido Safe Chain are free; OpenSSF already runs packages in gVisor |
| MCP/skill quarantine | Genuine and **dynamically unsolved**, medium | Unit 42 Jun 2026: 5 evasive skills passed VirusTotal and ClawScan; scanners only read descriptions | Volume fell after scanning was added; Palo Alto bought Koi; 2 of 5 threats steal no credentials, so honeytokens alone miss them |
| Bug-report reproduction | Genuine but **solved** | Metabase and Sentry built repro bots (2026) | Metabase Repro-Bot (open source), Devin with Jam, Sentry Seer; hard cases need the customer's environment |
| Pay-transparency auditor | Genuine; continuous audit with proof of cure **unsolved**, medium-high | NY Fed 24% non-compliance; 200–300 Washington class actions, still live in 2026 | Greenhouse has built-in rules; Apify checkers exist; Washington's 5-day cure provision softens suits |
| Change Twin (test changes on a copy) | Genuine but **partly solved** | Cloudflare 20 Feb 2026 (6h07m); Coinbase 14 Jul 2026 | Cloudflare's production-like staging still missed it; AWS's bug only appears at scale; Forward Predict ships digital-twin change checks |
| Cloak Hunter (gov.in hijacks) | Genuine, but **demo-fatal right now** | Infoblox 26 Oct 2026: maharashtra.gov.in and ESIC subdomain takeover, live about 14 months | Nothing live on 4 Nov (my 0/6, plus certificate-log sweep); the attack moved to DNS takeovers that certificate logs catch cheaply |
| MSME tenders | Genuine but **crowded** | MSE relaxations "rarely implemented in practice" | MSEs already win 43.6% of central procurement against a 25% target; 5+ vendors sell AI eligibility checks |
| Security questionnaire check | **Mostly solved** | Vanta: 9 weeks a year on reviews (vendor survey) | SecurityScorecard, UpGuard and BitSight already scan TLS and DMARC and run questionnaire workflows |

---

## 4. Re-scored

The personal-fit criterion is removed. Weights:
- **Genuine problem:** 25 (current evidence, cost, who suffers)
- **Unsolved by incumbents:** 15
- **Real public data for the headline:** 15
- **Sandbox essential:** 15
- **Depth of Vultr use:** 10
- **Hackathon white space:** 5
- **Feasible in 4 days:** 10
- **Demo:** 5

| # | Genuine | Unsolved | Data | Sandbox | Vultr | Field | Feasible | Demo | **Score** |
|---|---|---|---|---|---|---|---|---|---|
| **Burner** | 5 | 5 | 4 | 5 | 5 | 3 | 4 | 5 | **93** |
| PoC Court | 5 | 3 | 4 | 5 | 5 | 5 | 3 | 5 | 87 |
| Package detonation | 5 | 2 | 5 | 5 | 4 | 2 | 4 | 4 | 83 |
| MCP quarantine | 4 | 4 | 2 | 5 | 4 | 5 | 3 | 5 | 77 |
| Pay transparency | 4 | 3 | 5 | 1 | 2 | 5 | 5 | 3 | 69 |
| Change Twin | 4 | 2 | 2 | 4 | 5 | 5 | 3 | 4 | 69 |
| Bug-report repro | 4 | 2 | 4 | 4 | 3 | 3 | 3 | 3 | 68 |
| Cloak Hunter | 4 | 3 | 2 | 3 | 4 | 5 | 2 | 3 | 64 |
| MSME tenders | 3 | 2 | 5 | 1 | 2 | 4 | 3 | 3 | 56 |
| Questionnaire check | 3 | 1 | 3 | 3 | 2 | 4 | 3 | 4 | 54 |

**Caveat.** "Sandbox essential" penalises Track 2 ideas, which aren't required to have one. Both tracks share one prize ladder and Track 1 judges score containment, so I kept the weight. **If you want Track 2, the best-validated pick is the pay-transparency auditor** (69): real data (NY Fed, Greenhouse API), live lawsuits, and an unsolved continuous-audit-with-proof gap.

---

## 5. Bracket

**Quarter-finals**
- **Burner vs Cloak Hunter → Burner.** Nothing to demo live for Cloak Hunter.
- **PoC Court vs Bug-report repro → PoC Court.** Bug repro is solved by open-source and commercial bots.
- **Package detonation vs Change Twin → Package detonation.** Real labelled data versus synthetic. Change Twin has also been undercut by Cloudflare's own postmortem: staging missed the bug.
- **MCP quarantine vs Pay transparency → MCP quarantine.** On Track 1 fit; pay transparency stays the Track 2 alternate.

**Semi-finals**
- **Burner vs MCP quarantine → Burner.** MCP's malware volume fell after scanning arrived, its data is thin, and Palo Alto and Koi are moving in. It folds into Burner as a stretch goal ("same sandbox, agent add-ons").
- **PoC Court vs Package detonation → PoC Court.** npm v12, Socket Firewall, Aikido and OpenSSF have largely closed the install-time gap. Package detonation's dataset becomes Burner's benchmark.

**Final: Burner vs PoC Court → Burner.**

| | Burner | PoC Court |
|---|---|---|
| Problem current in 2026? | Yes: new variant Jul 2026, 1,700+ packages (Apr 2026) | Yes: Google freeze Oct 2026, HackerOne +76% |
| Already solved? | **No.** Every tool found is static; a VM contains damage but gives no verdict | **Partly.** Konvu and h1 Validation execute PoCs (web apps, enterprise) |
| Is the headline data the current problem? | Yes: campaign-tagged packages plus the Elastic variant's behaviour | Partly: the 49 slop reports are 2025's problem |
| Feasible in 4 days | Higher: install, run, observe | Medium: build versions with ASAN; many PoCs aren't runnable |
| Judges' likely rebuttal | "Just use a VM." Answer: a VM contains but explains nothing, and nobody watches it | "Konvu does this." Answer: we focus on native-code OSS volunteers, which is narrower |

---

## 6. The champion: Burner

### Problem statement (all sources verified)

North Korea-linked operators pose as recruiters on LinkedIn, Slack and Telegram and hand developers a "test challenge" repo.
- **The July 2026 variant:**
  - It hides its payload in SVG images and runs every time the dev server starts.
  - At the time Elastic published, **no antivirus vendor flagged any of the 7 repos**.
  - It steals `.env`, SSH and AWS keys, 25 crypto wallets, browser logins and the clipboard, and opens a remote shell.
  - It detects VMs but keeps running, tagging them "(VM)".
  - Source: [Elastic](https://www.elastic.co/security-labs/threat-command/contagious-interview-malware-svg-steganography)
- **Scale:** Socket tracks more than 1,700 campaign packages across 5 registries. The attackers avoid install-time execution, and Socket advises teams to sandbox. [Socket](https://socket.dev/blog/contagious-interview-campaign-spreads-across-5-ecosystems)
- **Microsoft's advice:** run coding tests in "a dedicated, isolated environment". [Microsoft, Mar 2026](https://www.microsoft.com/en-us/security/blog/?p=145718)
- **The gap:** every tool found (repocanary, devguard-scanner, repo-security-scanner, code-threat-scan) **refuses to run the repo**, so it can't see payloads hidden in images or triggered at runtime. A disposable VM contains the damage but **gives no verdict**.

### Solution

Paste a repo URL, or the recruiter's message.
1. A burner (gVisor container by default, or a fresh Vultr VM per scan through the API) gets honeytoken secrets planted in it: a fake `.env`, `~/.ssh`, `~/.aws`, a wallet extension directory and browser profile files, each holding a unique canary.
2. Burner runs what a candidate would run: `npm install`, then `npm run dev` / `npm start` / `npm test`, plus the VS Code `folderOpen` tasks.
3. It records every file read, process and outbound attempt. Egress is denied and logged.
4. **Rules decide the verdict**: a canary read plus an outbound attempt means MALICIOUS. The LLM explains the evidence. The repo's own text is treated as hostile to the reviewer and screened with `nemotron-3.5-content-safety`.
5. The burner is destroyed and the audit log goes to Vultr Object Storage.

**Containment moment for the video:** the repo reads the fake `.env` and wallet files, tries to POST them to the attacker host, and gets **BLOCKED**. The attacker listener on screen receives nothing, the burner is destroyed, and the verdict card shows what was taken.

**Headline benchmark:**
- Run campaign-tagged packages (Socket IoCs, plus DataDog's labelled npm set) and top benign packages, giving detection rate and false-positive rate. Also run a defanged replica of Elastic's SVG and runtime-trigger pattern.
- **Compare against a static baseline** (DataDog's open-source GuardDog scanner, plus antivirus). This shows what only running the code catches.
- Caveat: DataDog's dataset was mostly found by GuardDog, so use Socket-tagged and runtime-trigger samples for the comparison.

**Stretch (day 5):** the same burner for MCP servers and skills, with an LLM driving the tools. This covers Unit 42's evasive skills, which static scanners passed.

**$200:** about $65–120. That covers the orchestrator and sandbox host live through judging, about 300 burner VMs, a 16–32 vCPU benchmark box for about 6 hours, Object Storage and inference, leaving an $80+ buffer. The breakdown is in the round-1 report.

**Risks:**
1. **Vultr's acceptable-use policy on running malware** (page blocked). Ask in Discord. Run live samples only with no network; film the demo with the defanged replica.
2. **Dead command servers.** Score *attempted* reads and connections, not successful callbacks.
3. **Node under gVisor is untested.** Fallback is hardened Docker.
4. **"Just use a VM" rebuttal.** Answer it in the pitch.

### Pitch line

> "In July, fake recruiters handed developers seven repos that no antivirus flagged. Installing them was safe; running `npm start` emptied your wallet. Burner runs it for you on a Vultr burner full of fake secrets, and shows you exactly what it tried to steal."

---

## 7. Not verified

- Vultr's acceptable-use policy.
- Whether the Elastic repos or Socket's IoC packages can still be downloaded.
- Node and Chromium under gVisor.
- Konvu's accuracy and pricing (vendor claims only).
- The HackerOne +76% figure and the kernel reproducer patch (from the validation notes, not opened by me).
- Whether Uptime Institute's 2026 change-cause share is right (paywalled).
