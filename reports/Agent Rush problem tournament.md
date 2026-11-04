# Agent Rush problem tournament

Vultr Agent Rush (lablab.ai), 3–8 Nov 2026. Written 4 Nov 2026. Submission closes **Mon 9 Nov 03:30 IST**; target 22:00 IST Sun 8 Nov.

Inputs: four parallel research passes (Vultr strategy and competitors, previous builders and current entries, Track 1 problems, Track 2 problems), plus checks I ran directly on 4 Nov (live Vultr model catalogue, the Hugging Face tender dataset, the DataDog malware dataset). Notes: `research_notes/Agent Rush problem tournament/`. Earlier logistics report: `reports/Vultr Agent Rush hackathon edges.md`.

---

## 1. Winner in one paragraph

**Burner: "Before you run the take-home, let a burner run it."** Fake recruiters (North Korea-linked "Contagious Interview", active since Dec 2022) send developers coding tests whose repos steal wallets, `.env` files and passwords the moment you run `npm install` or just open the folder in VS Code. Microsoft's own recommended defence is "a dedicated, isolated environment for coding tests and take-home assignments", and no consumer tool gives job seekers that. Burner is a web agent: paste the repo link (or the recruiter's message). It clones the repo into a throwaway sandbox on Vultr, plants **fake** secrets as bait, runs the install, VS Code tasks and start scripts with every outbound connection blocked, and reports in plain English what the code tried to steal and where it tried to send it. Then it destroys the sandbox. The headline number comes from real data: detection rate on real malicious npm packages from DataDog's public dataset against benign top packages. **You are the user**: a student developer who gets take-home repos from people you don't know.

---

## 2. Facts that shaped the scoring

**What Vultr is selling right now: agents with guardrails.**
- Vultr published its own guide, "Agent Sandboxing on Vultr Cloud Compute with Microsandbox" (28 Sep 2026): one microVM per agent task, Vultr Serverless Inference as the model. [Vultr Docs](https://docs.vultr.com/how-to-set-up-agent-sandboxing-on-vultr-cloud-compute)
- Its 19 Oct release adds Audit Logs that record **AI agents as a separate actor** from humans, and frames the product as getting agentic AI "from POC to production". [HPCwire](https://www.hpcwire.com/aiwire/2026/10/19/vultr-advances-agentic-ai-infrastructure-with-new-platform-upgrades/), [Techzine](https://www.techzine.eu/news/infrastructure/145145/vultr-expands-to-run-agentic-ai-in-production/)
- Its hosted MCP server is read-only by design and "cannot spend money". [Vultr blog](https://blogs.vultr.com/vultr-mcp-server-public-preview)
- Competitors already sell managed sandboxes: AWS AgentCore, Cloudflare Sandboxes and Browser Run, E2B, Daytona, Modal, and Akamai Agent Sandbox (beta, 27 Oct). Vultr has no managed sandbox API. A project showing that Vultr VMs plus Vultr inference **are** a production sandbox platform shows exactly what Vultr wants to be known for.

**What Vultr's catalogue lets you do (live `GET /v1/models`, 4 Nov, 35 models):**
- Planners: `deepseek-v4.1-flash-1017`, and `minimax-m3.1-flash` (described as for "agentic coding, computer use").
- `nemotron-3.5-content-safety`: a NVIDIA safety classifier for text, images and files, $0.05 per million tokens.
- Calibrated decision models (`clef-flash`, `pplx-decider-v1.2`): they return probabilities for yes/no questions and accept up to 8 screenshots.
- All served from US data centres only.

**The field (4 Nov):**
- **Size:** 2,331 participants, 617 teams. About 51 Agent Rush projects are visible.
- **Generic "containment runtime / sandboxed code runner" projects:** about 20. This is the most crowded category.
- **Finance:** 6. One of them, caveo, already detonates invoices in gVisor.
- **Package or file detonation:** 3, including derKosi's PyPI triage.
- **HR:** 0.
- **Visible-entry source:** [lablab live](https://lablab.ai/ai-hackathons/vultr-hackathon/live).

**What wins Vultr tracks:**
- **HackTX 2026, Breadcrumbs:** an AI honeypot that caught about 1,900 real attack events, with a two-VM trust split on Vultr. [GitHub](https://github.com/aryansvt/hacktx2026)
- **RAISE 2026, Overturn:** a solo build on Vultr inference only, with a "refuse when the insurer is right" branch. [GitHub](https://github.com/MeohamedYassineAgourram/Overturn)
- **Milan 2026, Deals Machine:** a solo build.
- **The pattern:** one sharp job for a named user, a real-world proof moment, Vultr doing structural work, and deterministic tools around the LLM.

---

## 3. The ten contenders

Fourteen candidates came out of research. Four were cut before the bracket:
- **AI-generated fake receipts:** the fraudulent examples would have to be synthetic, and AppZen and Ramp already sell this.
- **GST reconciliation:** there's no public invoice-level data.
- **MSME late-payment recovery:** only aggregate data exists.
- **WhatsApp support for D2C brands:** crowded (Wati, Interakt), and setting up Meta's API is a risk.

| # | Problem | Track | One-line solution |
|---|---|---|---|
| P1 | Malicious take-home repos from fake recruiters (Contagious Interview) | T1 | Burner: run the repo in a decoy sandbox, report what it tried to steal |
| P2 | Malicious npm/PyPI packages (supply-chain worms like Shai-Hulud) | T1 | Detonate any package version, diff its behaviour, explain it |
| P3 | Malicious agent add-ons: MCP servers and skills (ClawHub, postmark-mcp) | T1 | Quarantine an MCP server or skill, exercise its tools against fake creds |
| P4 | Scam links and APKs sent to Indian families on WhatsApp | T1 | Open the link in a burner browser, explain the scam in voice |
| P5 | Prompt injection hijacking browser agents | T1 | Injection-proof research browser with an egress allowlist |
| P6 | Leaking sensitive spreadsheets to AI tools | T1 | Contained analyst that never lets data leave |
| P7 | MSMEs missing government tenders they're eligible for | T2 | Tender discovery and eligibility agent on 3.95M real tenders |
| P8 | Job scams and fake recruiters hitting students | T2 | Placement-cell screening agent for job offers and recruiters |
| P9 | Vendor bank-detail swap fraud during supplier onboarding | T1/T2 | Vetted: sandboxed supplier due-diligence with an approval gate |
| P10 | HR onboarding agents tricked into granting admin access | T2 | Access-provisioning agent with a credential broker |

---

## 4. Scoring

Weights (out of 100):
- **Pain evidence, primary-sourced:** 15
- **It's your problem:** 10
- **Real public data for the headline:** 15
- **Sandbox is essential, not decorative:** 15
- **Depth of Vultr use:** 10
- **White space vs the Agent Rush field and past winners:** 15
- **Feasible in 4 days, solo:** 10
- **Demo legibility (the filmed moment):** 10

Each criterion is scored 1–5, then weighted and rescaled to 100.

| # | Pain | Yours | Data | Sandbox | Vultr | White space | Feasible | Demo | **Score** |
|---|---|---|---|---|---|---|---|---|---|
| **P1 Take-home repo** | 5 | 5 | 4 | 5 | 5 | 4 | 4 | 5 | **92** |
| P2 Package detonation | 5 | 3 | 5 | 5 | 4 | 2 | 4 | 4 | 81 |
| P3 MCP/skill quarantine | 4 | 4 | 2 | 5 | 4 | 5 | 3 | 5 | 80 |
| P8 Job-scam screening | 5 | 5 | 3 | 4 | 4 | 3 | 4 | 4 | 79 |
| P4 WhatsApp link detonator | 4 | 4 | 4 | 4 | 4 | 2 | 3 | 4 | 72 |
| P7 MSME tenders | 4 | 2 | 5 | 2 | 3 | 5 | 3 | 3 | 70 |
| P9 Vetted supplier onboarding | 4 | 1 | 4 | 4 | 4 | 3 | 3 | 4 | 69 |
| P5 Injection-proof browser | 4 | 2 | 4 | 4 | 3 | 1 | 3 | 4 | 63 |
| P10 HR access provisioning | 3 | 1 | 1 | 4 | 4 | 5 | 3 | 4 | 63 |
| P6 Contained spreadsheet analyst | 3 | 2 | 4 | 2 | 3 | 1 | 5 | 2 | 54 |

---

## 5. Head-to-head bracket

**Quarter-finals**
- **P1 take-home repo vs P8 job-scam screening → P1.** Same victim (you, job hunting), but P8's best dataset (EMSCAD) is a 2012–14 US Kaggle classic that many students have already used. In P1 the sandbox *is* the product. P8 becomes P1's front door: paste the recruiter's message, and Burner pulls out the repo link and flags the red-flag patterns.
- **P2 package detonation vs P9 Vetted → P2.** P9 has no personal connection, and caveo already owns "AP agent that can't be phished". P2 has the largest labelled real dataset found (verified below).
- **P3 MCP quarantine vs P4 WhatsApp detonator → P3.** P4 runs into VirusTotal and urlscan.io, and APKs can't run without KVM. P3's category has about 0 visible entries and the most legible demo (a hidden BCC caught by a fake mail server).
- **P7 tenders vs P10 HR access → P7.** P10 would be demoed on synthetic data, which goes against the "real-data headline" rule. P7's dataset is verified real.

**Semi-finals**
- **P1 vs P2 → P1.** They share about 90% of the engine (clone, install in gVisor, honeytokens, egress log). P2 is crowded (derKosi, OpenSSF Package Analysis) and generic. P1 has a named victim, a documented nation-state campaign, Microsoft's own instruction to do exactly this, and a clear buyer (job seekers, bootcamps, placement cells, hiring platforms). **P1 takes P2's dataset as its benchmark.**
- **P3 vs P7 → P3.** P7's sandbox is decorative: injection in tender PDFs is a stretch. It is also a Track 2 entry against a crowded finance and procurement field, with a 13.9 GB dataset and portal captchas to deal with in 4 days.

**Final: P1 vs P3 → P1.**
- P3 has the fresher category, but its data is weak: 341 out of 2,857 is Koi Security's number, not one you can reproduce.
- P1 gives your own measured number on public data, a real, personal victim story, and better feasibility.
- **P3 becomes P1's day-5 stretch:** the same burner engine, pointed at an MCP server or skill. DataDog's dataset includes an `ai-skills` folder, verified below.

---

## 6. The winner: Burner

### The problem, with numbers

- **The campaign.** Fake recruiters from "crypto-trading or AI firms" run multi-step hiring processes with malware "directly into interview tools, coding exercises, and assessment workflows". It has been active since at least Dec 2022. [Microsoft Security Blog, Mar 2026](https://www.microsoft.com/en-us/security/blog/?p=145718)
- **Three ways in** (Microsoft):
  1. `npm install` a repo hosted on GitHub, GitLab or Bitbucket.
  2. Open the folder in VS Code and click "trust", which auto-runs `.vscode/tasks.json` with `runOn: folderOpen`.
  3. A fake "error" page tells you to paste a fix command.
- **What it steals.** The payloads (OtterCookie, InvisibleFerret, FlexibleFerret) take wallet seed phrases, KeePass and 1Password files, **environment files**, keys, keystrokes, screenshots and the clipboard. OtterCookie checks whether it is running in a VM. [Microsoft](https://www.microsoft.com/en-us/security/blog/?p=145718)
- **Scale.** 338+ malicious npm packages are tied to the campaign as of Feb 2026, per Socket (secondhand). [eSecurityPlanet](https://www.esecurityplanet.com/de/news/338-malicious-npm-packages-linked-to-north-korean-hackers/)
- **The wider wave.** Sonatype counts **over 1.233M malicious open-source packages**, with malware growing 75%. [Sonatype, 28 Jan 2026](https://www.sonatype.com/press-releases/sonatype-research-reveals-open-malware-grows-75-percent) The Shai-Hulud worm stole `~/.npmrc`, `~/.aws` and `~/.ssh` secrets during installs and republished infected packages with stolen tokens. [Wiz](https://wiz.io/blog/shai-hulud-npm-supply-chain-attack)
- **First-person accounts.**
  - "A LinkedIn recruiter sent me malware disguised as a pre-interview code review." [DEV](https://dev.to/vladimirnovick/a-linkedin-recruiter-sent-me-malware-disguised-as-a-pre-interview-code-review-2k3j)
  - "How a fake job interview repo tried to steal my keys and how I caught it." [DEV](https://dev.to/pavelespitia/how-a-fake-job-interview-repo-tried-to-steal-my-keys-and-how-i-caught-it-1pkp)
- **The defence experts recommend.** "a dedicated, isolated environment for coding tests and take-home assignments". [Microsoft](https://www.microsoft.com/en-us/security/blog/?p=145718)
- **Why today's workarounds fail.**
  - Reading `package.json` by hand fails against obfuscated payloads.
  - `--ignore-scripts` doesn't stop malicious code that runs on `npm start`.
  - A naive VM can make OtterCookie go quiet.
  - No consumer "paste a repo, get a behaviour report" tool for candidates was found. That is absence of evidence, so still verify.

### Real data for the headline (verified 4 Nov)

- **[DataDog malicious-software-packages-dataset](https://github.com/DataDog/malicious-software-packages-dataset):**
  - Apache-2.0; last pushed 3 Nov 2026.
  - Ecosystems: `npm`, `pypi`, `ide_extensions` and `ai-skills`.
  - The npm manifest lists **48,571 package entries**, split into `malicious_intent` and `compromised_lib`.
  - Samples are ZIPs encrypted with the password `infected`.
- **Headline to produce:** "Burner ran N real malicious npm packages and N top-downloaded benign packages. It flagged X% of the malicious ones from observed behaviour, with a Y% false-positive rate. 0 honeytokens left the sandbox."
- **The filmed demo:** a faithful, **defanged** replica of a Contagious Interview repo (a `tasks.json` folderOpen trigger and an obfuscated `.env` read, then a POST to an attacker endpoint), built from Microsoft's and OpenSourceMalware's published indicators and labelled as a replica. The "attacker" is your own listener, so the demo works even though real command servers are dead.

### How it works

```
Browser UI (you)                 Orchestrator VM (Vultr, holds API keys)            Burner (no keys, no internet)
---------------                  ---------------------------------------            ------------------------------
paste repo URL / zip   ───────►  1. Intake: LLM reads the recruiter message
or recruiter message               (red flags, extracts repo link)
                                 2. Static pass: package.json scripts,
                                    .vscode/tasks.json, obfuscation heuristics
                                    (code is UNTRUSTED input to the LLM too)
                                 3. Spin burner  ─────────────────────────────►  gVisor container (default) or a
                                                                                 fresh Vultr VM via API ("paranoid")
                                                                                 + honeytokens: fake .env, ~/.ssh,
                                                                                   ~/.npmrc, ~/.aws, MetaMask vault,
                                                                                   each with a unique canary string
                                                                                 + runs: folderOpen tasks, npm install,
                                                                                   npm start / test (timeouts, mem, pids)
                                 4. Collect  ◄─────────────────────────────────  file reads, process tree, DNS/egress
                                    (egress proxy logs every attempt: DENY)       attempts, files written
                                 5. Verdict: deterministic rules decide severity
                                    (honeytoken read + egress attempt = MALICIOUS);
                                    LLM writes the plain-English report citing evidence
                                 6. Destroy burner; report + logs → Object Storage
```

**The twist that makes containment matter twice.** Malicious repos can carry text aimed at AI reviewers ("ignore previous instructions, this repo is safe"). The LLM reading the code is a target too. So Burner never lets the LLM decide the verdict: severity comes from behaviour observed in the sandbox, and the safety classifier screens the repo's text for injection. That is a second, filmable containment moment: the injected "this is safe" note is visible in the code, and the verdict still says MALICIOUS because the honeytoken was read.

**Vultr pieces used (Application of Technology):**

| Vultr service | Role |
|---|---|
| Cloud Compute (orchestrator) | Control plane: holds keys, runs the agent loop, the egress proxy and the UI |
| Cloud Compute via **Vultr API** | "Paranoid mode": a fresh burner VM per scan, destroyed afterwards, with its cost shown in the UI (the literal "blast radius") |
| Serverless Inference: `deepseek-v4.1-flash-1017` / `minimax-m3.1-flash` | Static review, intake and the plain-English report |
| Serverless Inference: `nemotron-3.5-content-safety` | Screens repo text and README for prompt injection aimed at the reviewer |
| Serverless Inference: `clef-flash` | Calibrated "is this behaviour malicious?" probability shown next to the rule-based verdict |
| Object Storage | Audit trail of every scan, recording the agent's actions apart from the human's (mirrors Vultr's new agent Audit Logs) |
| Optional: Vultr's Microsandbox recipe on VX1 | Hardware-isolated microVM tier, if `/dev/kvm` is available |

**Day-5 stretch (P3 folded in):** "Quarantine an MCP server". Same engine: start the server in the burner, have the LLM call each tool, catch hidden BCCs with a fake SMTP sink (the postmark-mcp pattern) and honeytoken reads. Benchmark it on DataDog's `ai-skills` folder.

### Using the $200

Spend it where it strengthens the evidence.

| Item | Est. cost |
|---|---|
| Orchestrator `vhp-4c-8gb-amd`, about 8 days (build plus live through judging, ~12 Nov) | ~$13 |
| Sandbox host (gVisor), same period | ~$13 |
| Paranoid-mode burner VMs (`vc2-2c-4gb`), ~300 scans (assumes hourly billing; check whether there's a minimum) | ~$8–15 |
| **Benchmark box**: 16–32 vCPU for ~6 hours to run 1,000+ real malicious and benign samples (a bigger N makes a stronger headline) | ~$10–20 |
| Object Storage (prorated) | ~$5–18 |
| Inference: static review, reports and classifiers across benchmark and demo | ~$10–25 |
| Optional load balancer, plus a bigger box for demo day | ~$5–15 |
| **Total** | **~$65–120**, leaving a $80+ buffer |

### Risks and mitigations

1. **Vultr's acceptable-use policy on executing malware.** The policy page returned 403, so it's unverified. Mitigation: ask in the Agent Rush Discord first. Run real samples only in the benchmark, with no network, then destroy. The filmed demo uses the defanged replica.
2. **Samples that stay quiet** (dead command servers, VM detection). Count *attempted* behaviour (honeytoken reads, DNS lookups, connection attempts), not successful callbacks. Make the burner look like a real dev laptop (realistic hostname, git config, home directory). Report "nothing observed" as **not** "safe".
3. **Node or Chromium under gVisor.** Untested; check it on day 1. Fallback: hardened Docker with `--network` pointed at an internal proxy, read-only root filesystem, `--cap-drop ALL`, and pids/memory limits.
4. **Overlap with derKosi's package triage.** Your angle is different: the take-home *repo* (VS Code tasks, `npm start`, recruiter intake), a job-seeker persona, a measured benchmark and Vultr burner VMs. Say this in the pitch.
5. **Uncited stats.** Use Microsoft and Sonatype as primary sources, and mark Socket's 338 figure as reported by eSecurityPlanet. India-specific targeting is unverified, so don't claim it.
6. **Instance cap on new accounts.** The burner-VM mode depends on it. Check the limit on day 1 and keep gVisor as the default tier.

### Build plan (IST)

| Day | Goal |
|---|---|
| **Wed 4 Nov** | Redeem credits. Orchestrator VM plus sandbox host. gVisor, the egress proxy (deny all, log everything) and honeytokens. Ask about the acceptable-use policy in Discord. Build the defanged replica repo. |
| **Thu 5** | Agent loop: intake, static pass, burner run, event collection, rule-based verdict, LLM report. Minimal UI: paste a URL, watch the live event feed. |
| **Fri 6** | Paranoid mode (burner VM per scan via the Vultr API) with the cost shown. Object Storage audit log. Benchmark harness: DataDog npm `malicious_intent` subset plus top benign packages. |
| **Sat 7** | Run the benchmark and fix the headline numbers. UI polish (verdict card, "what it tried to steal" timeline). Recruiter-message intake. Stretch: MCP quarantine. |
| **Sun 8** | A 3–5 minute video (containment moment: the honeytoken is read, the POST to the attacker is blocked, the attacker's listener receives nothing, the burner is destroyed), PDF deck, README with Vultr architecture. **Submit by 22:00 IST.** |

### Pitch line

> "You're a developer looking for work. A recruiter sends a take-home. Opening it in VS Code is enough to empty your wallet. Burner opens it for you, on a Vultr burner that holds nothing real, and tells you what it tried to steal."

---

## 7. Runners-up, in case you want a different shape

- **P2, package detonation (81):** same engine, broader market, but more crowded.
- **P3, MCP/skill quarantine (80):** freshest category, but its data is weak. Best used as Burner's stretch goal.
- **P7, MSME tenders (70):** the strongest Track 2 option. Its dataset is verified real (CC-BY-4.0, 3.95M tenders): [Hugging Face](https://huggingface.co/datasets/fireboy21/tenders_aoc). But its sandbox would be decorative.

## 8. Not verified

- Vultr's acceptable-use policy on running malware (page blocked).
- Whether promo credits cover Serverless Inference.
- Whether short-lived VMs have a minimum billing period, and how fast they boot.
- Whether `/dev/kvm` is available outside VX1.
- Whether DataDog's npm samples still show behaviour when run today.
- Socket's 338-package count (secondhand).
- Whether the "no consumer take-home scanner exists" gap holds; I found none, but searching isn't proof.
