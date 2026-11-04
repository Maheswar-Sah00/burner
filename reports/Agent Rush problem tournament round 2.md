# Agent Rush problem tournament, round 2

Vultr Agent Rush (lablab.ai). Written 4 Nov 2026. Submission closes **Mon 9 Nov 03:30 IST**; target 22:00 IST Sun 8 Nov.

**Process:** same as round 1.
- Four parallel research passes: Vultr-native problems, consumer browser agents, new enterprise workflows, and wildcard domains (open source, research, education, civic, healthcare).
- Round 1's 14 candidates were excluded.
- I then ran live tests myself.
- Ten candidates were scored and bracketed.
- The round-2 champion then played round 1's champion (Burner) in a grand final.

Notes: `research_notes/Agent Rush problem tournament round 2/`. Round 1: `reports/Agent Rush problem tournament.md`.

---

## 1. Result

**Round-2 champion: PoC Court.** An agent that **reproduces or refutes vulnerability reports** sent to open-source maintainers:
1. It builds the exact affected version of the software in a throwaway Vultr sandbox.
2. It writes and runs the harness for the reporter's proof of concept (PoC).
3. It returns a verdict backed by evidence: CONFIRMED with a memory-error trace, REFUTED with the clean run, or DUPLICATE of an existing CVE.

The sandbox is essential: about **10% of public GitHub exploit PoCs are themselves malicious**.

**Grand final: PoC Court beats Burner, narrowly** (section 6). Burner remains the pick if you weight "my own problem" above everything else.

---

## 2. Live tests I ran (4 Nov)

| Test | Result | What it means |
|---|---|---|
| curl's public AI-slop list ([gist](https://gist.github.com/bagder/07f7581f6e3d78ef37dfbfc81fd1d1cd), updated 28 Oct 2026) | 49 unique HackerOne report links | Real, labelled fake reports |
| Fetch all 49 as `hackerone.com/reports/<id>.json` | **49/49 fetched**; **45 contain code-style PoCs**. HackerOne labels: 42 not-applicable, 6 spam, 1 informative | The benchmark is machine-readable today, with no scraping |
| curl's CVE feed (`curl.se/docs/vuln.json`) | **239 CVEs**, 107 since 2023, newest 14 Oct 2026, with affected versions | Ground-truth real vulnerabilities to reproduce |
| Greenhouse public jobs API, `?pay_transparency=true` | Airbnb 175 of 213 jobs with pay ranges, GitLab 105 of 239, Stripe 0 of 745 | The pay-transparency audit data is real |
| Six gov.in pages search engines index as gambling spam, each requested as a desktop visitor, a phone visitor arriving from Google, and Googlebot | **0 of 6 still serve gambling content** (they now return 404, 403 or no response). One (governor.mp.gov.in) returns a *different* response to phone visitors from Google (410, 35 bytes) than to desktop visitors and Googlebot (404, 1,243 bytes) | The hijacks are real but the search index is stale. A live demo is high-risk |

---

## 3. The ten contenders

Cut before the bracket:
- **Decoy AI endpoints:** too close to Breadcrumbs, the HackTX Vultr winner.
- **Backup restore drill:** synthetic headline.
- **Spreadsheet model audit:** finance is the most crowded domain.
- **Checking delivered software:** overlaps package triage.
- **SEC XBRL filing checks:** weak containment.
- **Safe lab autograder:** a generic code runner.
- **Malicious model file scanner:** adjacent to round 1's package-detonation idea.
- **Hospital price-transparency files:** the sandbox would be decorative.
- **Accessibility agent for government portals:** thin containment.
- **Consumer complaint filing:** no per-case data.
- **Data-broker removal:** US-only.

| # | Problem | Track | Solution |
|---|---|---|---|
| A | Maintainers drowning in AI-generated vulnerability reports | T1 | **PoC Court**: build the version, run the PoC, verdict with evidence |
| B | Customer bug reports engineering can't reproduce (~17% never reproduced) | T2/T1 | Support agent reproduces the report in a sandbox before escalating (SWE-bench Verified) |
| C | gov.in sites hijacked to show betting redirects only to Google visitors | T1 | Cloak Hunter: India-region burner browsers compare visitor types |
| D | Config changes cause outages (Cloudflare Nov 2025, AWS Oct 2025) | T1/T2 | Change Twin: apply the change to a throwaway Vultr copy first, then promote |
| E | ₹1 trials that roll into recurring UPI AutoPay debits | T1 | Trial-Trap Exit: contained cancellation agent, payment gateways blocked |
| F | Account deletion obstructed in Indian apps (DPDP deletion right from May 2027) | T1 | Audit the Play-mandated deletion links for the top 100 apps |
| G | Job posts missing legally required pay ranges (Washington, EU directive) | T2 | Pay-transparency auditor on Greenhouse/Lever APIs, fix-and-prove loop |
| H | Security questionnaires answered from stale answer libraries | T2 | Check each answer against the live product (TLS, HSTS, DMARC) before sending |
| I | Research notebooks that don't run or reproduce (24% run, ~4% reproduce) | T1 | Repro Runner: run the paper's code, report where it breaks |
| J | Sites track before consent, and differently by region (DPDP Rules Nov 2025) | T1/T2 | Consent Truth: identical crawl from Vultr India, EU and US regions |

---

## 4. Scoring

Same weights as round 1:
- **Pain:** 15
- **It's your problem:** 10
- **Real data:** 15
- **Sandbox essential:** 15
- **Depth of Vultr use:** 10
- **White space:** 15
- **Feasible:** 10
- **Demo:** 10

| # | Pain | Yours | Data | Sandbox | Vultr | White space | Feasible | Demo | **Score** |
|---|---|---|---|---|---|---|---|---|---|
| **A PoC Court** | 5 | 3 | 5 | 5 | 5 | 5 | 3 | 5 | **92** |
| C Cloak Hunter | 5 | 3 | 2 | 4 | 5 | 5 | 2 | 4 | 76 |
| B Bug-report repro | 4 | 3 | 5 | 4 | 4 | 3 | 3 | 3 | 74 |
| D Change Twin | 5 | 1 | 2 | 4 | 5 | 5 | 3 | 4 | 74 |
| G Pay transparency | 4 | 1 | 5 | 2 | 3 | 5 | 5 | 3 | 72 |
| I Repro Runner | 4 | 4 | 5 | 3 | 3 | 4 | 3 | 2 | 72 |
| E Trial-Trap Exit | 4 | 4 | 3 | 4 | 3 | 3 | 2 | 4 | 68 |
| F Delete-My-Account | 3 | 3 | 4 | 3 | 3 | 4 | 4 | 3 | 68 |
| H Questionnaire verify | 4 | 1 | 4 | 3 | 3 | 4 | 3 | 4 | 67 |
| J Consent Truth | 3 | 2 | 4 | 2 | 5 | 4 | 4 | 3 | 67 |

Score notes:
- **C's data was cut to 2 by my live test** (0 of 6 indexed hijacks still live).
- **E's feasibility is 2** because cancelling a UPI AutoPay mandate happens inside UPI apps, not on the web, and the demo needs real paid accounts and OTP logins.

---

## 5. Bracket

The top 8 seeds went through; H and J (67) were out.

**Quarter-finals**
- **A PoC Court vs F Delete-My-Account → A.** F's sandbox is modest (browsing public pages). A has the strongest verified dataset in either round.
- **C Cloak Hunter vs E Trial-Trap → C.** E's core action (cancelling the UPI mandate) can't be done in a browser.
- **B Bug-report repro vs I Repro Runner → B.** Both "run the claim". With no GPUs, many ML papers can't be reproduced at all, which caps I.
- **D Change Twin vs G Pay transparency → D.** G's sandbox would be decorative. D uses Vultr literally as the control plane, which is exactly what the brief asks for.

**Semi-finals**
- **A vs D → A.** D has the most original Vultr story, but its headline is synthetic (replayed postmortems). A's headline is measured on 49 real fake reports plus real CVEs.
- **B vs C → B.** C lost on evidence: my test found the hijack index stale, cloaking kits block datacenter IPs, and finding live targets could eat the whole build.

**Final: A PoC Court vs B Bug-report repro → A.**
- Both are "reproduce the claim before a human spends time on it".
- B targets SWE-bench reproduction, a heavily researched area (SWT-bench, LIBRO), with 30 GiB of images and test generation that open models find hard.
- A has a sharper user (maintainers and bug-bounty triagers), a fresh policy hook, a containment threat that's essential (malicious PoCs), and zero visible competitors.

---

## 6. Grand final: PoC Court (round 2) vs Burner (round 1)

Both scored 92 on the matrix. Head to head:

| Question | Burner | PoC Court | Edge |
|---|---|---|---|
| Is it your problem? | Yes. You're a student developer receiving take-homes | Partly. You're a developer, but not a maintainer triaging reports | **Burner** |
| Real data, verified end to end by me? | DataDog dataset exists (48,571 npm entries), but samples may be dormant (dead C2, VM detection) and running live malware has acceptable-use risk | 49 of 49 slop reports fetched as JSON with 45 code PoCs, plus 239 CVEs with affected versions; running curl PoCs is mostly benign | **PoC Court** |
| White space in the field | 3 detonation entries, including derKosi's package triage | 0 found | **PoC Court** |
| Business value (judging criterion) | Consumers (job seekers); buyers are fuzzy (bootcamps, hiring platforms) | Clear B2B buyers: bug-bounty platforms, OSS foundations, security teams. GitHub's bounty has required "a working proof of concept" since 15 May 2026 | **PoC Court** |
| Track 1 pattern fit | Pattern A (runs code) | **Pattern A exactly**: the model writes the harness, runs it, explains the real output and retries on error | **PoC Court** |
| Containment is essential | Yes: the code is malware by design | Yes: ~10% of public PoCs are malicious, and reporters can be hostile | Tie |
| Demo | Honeytoken read, then exfiltration blocked (visceral) | AI report claims overflow → REFUTED (clean ASAN run); real CVE → CONFIRMED (heap-overflow trace); malicious PoC → exfiltration blocked | Tie (PoC Court has three beats) |
| Feasibility | Higher: install, run, observe | Medium: building curl versions with ASAN takes ~minutes each; slop PoCs are often not runnable as written | **Burner** |
| Freshness of the pain | Active campaign (Microsoft, Mar 2026) | Shifted: Stenberg (Apr 2026) says slop "is not a problem anymore"; now the issue is volume (about 2× the 2025 rate) and arguments over whether a bug is a vulnerability | **Burner**, unless PoC Court is pitched as "verify the volume" |

**Verdict: PoC Court, 5–3 with 2 ties.** It wins on the things judges score (Business Value, Originality, Application of Technology) and on data I verified end to end. Burner wins on personal fit and ease. **Pick Burner instead** if "it must be my own problem" is non-negotiable for you.

---

## 7. The champion: PoC Court

### The problem, with numbers (primary sources unless flagged)

- **Cost per report.** curl's security team is 7 people; each report takes 3–4 of them, 30 minutes to 3 hours each. Real vulnerabilities fell from over 15% of reports before 2025 to under 5% in 2025, and about 20% of 2025 reports were AI slop. [Stenberg, Jul 2025](https://daniel.haxx.se/blog/2025/07/14/death-by-a-thousand-slops/)
- **Bounty ended.** curl closed its bug bounty in Jan 2026. [Stenberg, Jan 2026](https://daniel.haxx.se/blog/2026/01/26/the-end-of-the-curl-bug-bounty/)
- **The shift.** In April 2026 Stenberg wrote that slop is no longer the problem. Volume is about twice the 2025 rate, about 15–16% of reports are real, and "almost every security report now uses AI". [Stenberg, Apr 2026](https://daniel.haxx.se/blog/2026/04/22/high-quality-chaos/) The work moved from spotting slop to **verifying a flood of plausible reports**. Torvalds made the same complaint on LKML in May 2026 (per the research notes).
- **Policy.** GitHub's bug bounty has required "a working proof of concept that demonstrates real exploitation" since 15 May 2026 (per the research notes). Someone has to run those PoCs.
- **Danger.** A Leiden study of **47,313** GitHub CVE PoC repos found **4,893 (10.3%) malicious**. [arXiv 2210.08374](https://arxiv.org/abs/2210.08374) A triager running PoCs on their own laptop is the victim profile.

### How it works

```
Maintainer UI                Orchestrator VM (Vultr, holds keys)                  Burner (no keys, no internet)
-------------                ------------------------------------                 -----------------------------
paste a HackerOne URL  ───►  1. Parse the report (JSON): claimed bug, version,
or report text                  PoC code; check against curl's CVE feed for duplicates
                             2. Safety screen: nemotron-content-safety plus rules
                                on the PoC (exfil, download-and-execute patterns)
                             3. Spin a burner  ───────────────────────────────►  build the claimed curl version
                                                                                 (+ the latest) with ASAN/UBSan
                             4. LLM writes the harness from the PoC  ─────────►  run it: time, memory, pids limits,
                                (Pattern A: run → read real output → retry)       egress denied and logged
                             5. Evidence  ◄─────────────────────────────────────  sanitizer trace / clean exit /
                                                                                 blocked network attempts
                             6. Verdict by rules (sanitizer crash in the claimed
                                function = CONFIRMED; clean on the claimed version =
                                REFUTED; matches a CVE = DUPLICATE); LLM drafts the reply
                             7. Destroy burner; audit log → Object Storage
```

**Headline to produce:** "PoC Court refuted X of 49 real AI-slop reports with a clean sanitizer run, reproduced Y of Z real curl CVEs, and blocked every malicious PoC attempt."

**Vultr pieces:**

| Vultr service | Role |
|---|---|
| Cloud Compute (orchestrator) | Control plane, UI, egress proxy, keys |
| Vultr API burner VMs (or gVisor containers) | One isolated build-and-run environment per report, destroyed afterwards |
| A larger compute box for a few hours | Builds many curl versions in parallel for the benchmark (where most of the credits go) |
| Serverless Inference: `deepseek-v4.1-flash-1017` / `minimax-m3.1-flash` | Parses reports, writes harnesses, drafts replies |
| `nemotron-3.5-content-safety` | Screens PoC text for hostile instructions |
| `clef-flash` | Calibrated "does this evidence support the claim?" score next to the rule-based verdict |
| Object Storage | Audit log per report, recording agent and human actions separately |

### Using the $200

| Item | Est. cost |
|---|---|
| Orchestrator `vhp-4c-8gb-amd`, about 8 days (live through judging) | ~$13 |
| Sandbox host, same period | ~$13 |
| **Benchmark build farm**: 16–32 vCPU for ~8–10 hours to build about 20 curl versions with ASAN and run 49 slop reports plus about 20 real CVEs | ~$15–30 |
| Burner VMs for the live demo and scans | ~$5–15 |
| Object Storage (prorated) | ~$5–18 |
| Inference: harness writing and retries across the benchmark | ~$10–25 |
| **Total** | **~$60–115**, leaving an $85+ buffer |

### Risks

1. **Slop PoCs often aren't runnable** (they're prose or pseudo-code). That's fine: "no runnable PoC" is itself a verdict. Show the attempt.
2. **Build time.** Cache the built curl versions. Only versions named in reports are needed.
3. **Pitch freshness.** Lead with "verify the volume" (GitHub's PoC requirement, 2× volume, Torvalds), with slop as the origin story.
4. **Real CVE PoCs** aren't always public. Use CVEs whose disclosed HackerOne reports include reproduction steps.
5. **Narrow scope (curl only).** Present it as the reference adapter, and mention that other projects can plug in their own build recipe.

### Build plan (IST)

| Day | Goal |
|---|---|
| **Wed 4** | Redeem credits; VMs; gVisor and the egress proxy. Script that builds any curl version with ASAN. Pull the 49 reports and the CVE feed. |
| **Thu 5** | Agent loop: parse, safety screen, harness, run, evidence, verdict. Minimal UI: paste a report, watch the live log. |
| **Fri 6** | Burner-VM mode via the Vultr API. Duplicate check against the CVE feed. Object Storage audit. A defanged malicious-PoC demo case. |
| **Sat 7** | Benchmark run on the build farm, giving the headline numbers. UI polish (verdict card with the evidence). |
| **Sun 8** | 3–5 minute video (three beats: REFUTED, CONFIRMED, BLOCKED), PDF deck, README. **Submit by 22:00 IST.** |

### Pitch line

> "Every security report now uses AI. Maintainers can't read faster, but they can stop reading reports that don't reproduce. PoC Court builds the version, runs the proof in a Vultr burner, and hands the maintainer a verdict with evidence, before anyone opens the report."

---

## 8. Not verified

- The Leiden 10.3% figure is from the arXiv paper; I didn't re-open the full text.
- The GitHub "working PoC" policy and Torvalds's May 2026 LKML comment come from the research notes; I didn't open them directly.
- How many of the 45 code PoCs actually compile or run.
- curl build time on Vultr.
- The Vultr acceptable-use policy (page blocked; lower risk here than for Burner).
- Whether any Agent Rush team started on PoC verification after 4 Nov.
