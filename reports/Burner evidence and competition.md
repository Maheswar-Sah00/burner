# Burner: evidence and competition

Vultr Agent Rush (lablab.ai). Written 4 Nov 2026 (evening). Submission closes **Mon 9 Nov 03:30 IST**.

Four research passes (threat evidence, the live Agent Rush field, lablab winners across events, market and sponsor fit), plus my own checks. Notes: `research_notes/Burner evidence and competition/`.

---

## 1. Bottom line

- **The problem is stronger than we thought.** Seven agencies in four countries issued a joint advisory on 18 Sep 2026. It says this campaign infected **30,000+ devices in 100+ countries** and drained **7,000+ crypto wallets**. The FBI has been telling candidates to "insist on using a virtual machine" since 2024.
- **The idea is no longer uncontested.** One direct in-event competitor, **Detonation Chamber** (1 commit), and one strong outside tool, **honeyrun** (15 commits since 3 Nov, about 85% overlap), already exist. "Nobody is doing this" is no longer true.
- **Burner can still win**, but only on *execution and framing*, not on the idea alone:
  1. Own the fake-recruiter take-home story end to end.
  2. Show the fake key **actually leaving** and being caught by a fake internet.
  3. Run one throwaway Vultr VM per scan.
  4. Use a defanged reconstruction of a real sample.
  5. Ship a polished live URL.

---

## 2. Evidence for the problem (verified items marked ✔)

| Fact | Source |
|---|---|
| ✔ Joint advisory, 18 Sep 2026 (Japan NPA/NCO, FBI, DC3, Australia ACSC, Germany BND/BfV; the agency list varies by outlet): "WaterPlum" (= Contagious Interview) infected **30,000+ devices in 100+ countries** and stole from **7,000+ wallets**, about **¥1.7bn / $10.7M**, Dec 2025–Jul 2026 | [BleepingComputer](https://www.bleepingcomputer.com/news/security/north-korean-waterplum-hackers-infected-30-000-devices-worldwide/), [The Record](https://therecord.media/north-korean-hackers-infect-thousands-of-devices-waterplum-scheme), [Infosecurity](https://www.infosecurity-magazine.com/news/north-korean-waterplum-30000/) |
| ✔ **DMM Bitcoin, $308M (2024):** a fake LinkedIn recruiter sent a Ginco employee a GitHub Python "pre-employment test"; FBI, DC3 and Japan's NPA attribution | [BleepingComputer](https://www.bleepingcomputer.com/news/security/fbi-links-north-korean-hackers-to-308-million-crypto-heist), [The Hacker News](https://thehackernews.com/2024/12/north-korean-hackers-pull-off-308m.html) |
| ✔ Elastic, Jul 2026: a new variant in 7 repos, **zero antivirus detections**, runs at `npm start`, keeps running inside VMs | [Elastic](https://www.elastic.co/security-labs/threat-command/contagious-interview-malware-svg-steganography) |
| ✔ Socket, Apr 2026: **1,700+ campaign packages** across 5 ecosystems; not install-time; "sandbox suspicious packages" | [Socket](https://socket.dev/blog/contagious-interview-campaign-spreads-across-5-ecosystems) |
| FBI PSA, 3 Sep 2024: "If a pre-employment test requires code execution, insist on using a virtual machine" | in notes (read directly by the researcher) |
| Trend Micro, Mar 2026: **750+ infected repos**, 500+ malicious VS Code `folderOpen` tasks; victims committed the malware into their **employers'** repos (DataStax, Neutralinojs) | [Trend Micro](https://www.trendmicro.com/en_gb/research/26/d/void-dokkaebi-uses-fake-job-interview-lure-to-spread-malware-via-code-repositories.html) |
| Atlassian, 21 Sep 2026: "hundreds" of these repos removed from Bitbucket; "almost half" use two or more trigger techniques | in notes |
| Chainalysis: North Korea stole **$2.02B of $3.4B** in crypto thefts in 2025 | [The Record](https://therecord.media/over-3-billion-crypto-stolen-2025-north-korea) |
| India: CoinDCX, $44M (Jul 2025). Bengaluru police say fake recruiters got an engineer to install malware (not attributed to North Korea; a part-time job lure) | in notes |
| Victim voice: "every question was designed so that the only way to answer it is to actually run the project" (Steven Li, 11 Jun 2026) | in notes |
| **Running beats reading (academic):** OSCAR (ASE 2024) caught **459/500** malicious npm packages with 3 false positives, against static GuardDog's **338** with 28 | in notes |

**Don't use:**
- "Binance $6.4B" (Binance reported no losses).
- "Bybit was a fake interview" (Safe says a compromised developer machine; the lure isn't confirmed).
- "Ronin fake job PDF" as fact (it rests on anonymous sources).

---

## 3. Why Burner can win

**Sponsor fit.**
- Vultr's 2026 story is "agents with guardrails": a sandboxing guide, audit logs that track agents separately, and a read-only MCP server. It has no managed sandbox, and Akamai shipped one on 27 Oct.
- Burner turns Track 1's *required* containment rules into the product itself:
  - isolation becomes the detonation chamber
  - "no secrets" becomes **fake secrets as bait**
  - limits become the run budget
  - destroy-after becomes a visible cost line

**Business value.** The money is real:
- **Socket**: $60M Series C at **$1B**, May 2026. Dynamic analysis is still "soon".
- **Aikido**: $60M at **$1B**, Jan 2026. It launched an Endpoint product for developer machines that blocks known malware but doesn't run repos.
- **Koi**: bought by Palo Alto, closed Apr 2026, reported at about $300–400M.
- **Tracebit**: raised $20M in Mar 2026 for fake-secret tripwires on developer machines.
- **Snyk** (static scanning): stalling at 7% growth, with layoffs in Oct 2026.
- **Buyers, ranked:**
  1. Crypto/Web3 firms (DMM Bitcoin, Bybit, Radiant)
  2. Enterprise security teams (victims infect their employers' repos)
  3. Individual developers (free tier)
  4. Hiring platforms and communities
  5. Acquirers

**Judging patterns (lablab winners, Jun–Oct 2026).**
- About 9 of 11 podium agent projects led with a **deterministic gate, an audit trail and a measured result**:
  - IBM Bob 2.0 (1,129 submissions): Amend, Inbin Gate, SoloTrace.
  - Alpaca: Autobelay, Killswitch.
  - Band of Agents: Freight Room, ClaimArbiter.
- **No lablab winner has done malware or repo detonation, fake secrets as bait, or fake-recruiter analysis.**
- The closest analogues show what wins:
  - Amend planted a fake-SSN canary and swept for leaks.
  - Inbin Gate showed runs with and without its gate, and 144/144 on AgentDojo.
- Winners are mostly solo or teams of 2, business-facing, and every one has a PDF deck.
- AMD ACT II disqualified 248 of 1,148 entries for missing deliverables.

---

## 4. The competition, honestly

**Agent Rush (4 Nov evening):** 2,370 participants, 636 teams, 9 submitted, 8 drafts. About 67 projects are visible on GitHub and lablab.

| Category | Visible projects |
|---|---|
| Generic sandbox runtime | 24 (crowded) |
| Verifying a coding agent's claims | 7 (fastest-growing) |
| Sandboxed browser agents | 5 |
| Detonating untrusted files or packages | 3–4 |
| Fake-recruiter / take-home framing | **0** |
| Dedicated MCP quarantine | 0 |

**Projects that overlap Burner:**

| Project | Overlap | Status (checked by me) | Their gap = your edge |
|---|---|---|---|
| **honeyrun** ([GitHub](https://github.com/m4xkushnir/honeyrun)) | ~85% | Created 3 Nov, **15 commits**; README doesn't mention Vultr or lablab, so it may not be an entry | Repos, npm/PyPI and MCP with 20 fake keys, a fake internet, a +45-day time-shift, VS Code tasks and git hooks; self-reports 25/25 fixtures. **This sets the technical bar.** No recruiter story, no Vultr burner VMs, no hosted product |
| **Detonation Chamber** ([GitHub](https://github.com/bibekgyawali2/vultr-hacathon)) | ~75% | Created 3 Nov, **1 commit**, not submitted | Synthetic replays, no fake internet (stolen values can't be seen leaving), no per-job VM yet, no recruiter story |
| MiniLocker ([GitHub](https://github.com/Unavailable4u/draft)) | Partial | 26 commits, mature | Plants decoys to protect its *own* agent, not to analyse a suspicious repo |
| derKosi (PyPI triage) | Partial | Stalled at 1 commit | — |

**What this means for the "puzzle" line in your pitch.** It still holds for *products*: Socket, Aikido, OpenSSF, Microsoft's "use a VM" advice and malware sandboxes each cover one piece. But **don't say nobody is building it.** Say: "Platforms each solve a piece, and open-source experiments are starting. Nobody has put the whole thing in a candidate's hands."

---

## 5. How Burner beats the field

Priority order:

1. **Own the take-home story.** The agent behaves like a candidate: reads the README, opens the folder in VS Code (`folderOpen` tasks), installs, starts, runs tests. The input can be **the recruiter's message**. The output is a verdict a candidate can act on: "Don't run this. It reads your wallet files and SSH keys and sends them to X."
2. **Show the theft, not just the block.** A fake internet (sinkhole DNS plus an HTTPS-intercepting proxy) captures the exfiltration request, so the video shows **the planted fake AWS key arriving at the "attacker"**. Detonation Chamber can't show this.
3. **One throwaway Vultr VM per scan**, created and destroyed through the Vultr API, with cost and timing on screen ("created → detonated → destroyed, $0.01"). This is where Vultr does the structural work, and the closest competitors don't have it.
4. **A defanged reconstruction of a real sample** (Elastic's July 2026 runtime trigger plus a hidden payload, or a Trend Micro `folderOpen` task) instead of a labelled synthetic replay.
5. **Match honeyrun's depth where it's cheap:** VS Code tasks, devcontainer, git hooks, wallet and browser-profile bait, a time-shift pass.
6. **A number, with a static baseline:** campaign-style samples and benign repos, detection and false-positive rate, compared side by side with static GuardDog (as OSCAR did). Include a "what Burner can't catch" slide.
7. **A live hosted URL, a result-first description, a PDF deck and a 3–5 minute video.**
8. **MCP quarantine as a second mode only**, not the headline.
9. **Avoid headlining "blast radius" or "receipts".** Both words are saturated in the field.

---

## 6. Risks

1. **honeyrun enters Agent Rush.** Answer it by moving faster on product and story (a hosted app, the recruiter flow, Vultr burner VMs) rather than racing on engine depth.
2. **Vultr's acceptable-use policy on malware.** DigitalOcean restricts malware research without prior written consent, so Vultr may too. Ask in Discord. Use defanged samples only, with egress sinkholed.
3. **Large field.** Recent lablab events had 1,100+ submissions. Polish and complete deliverables decide it.
4. **Re-scan the field on 6–7 Nov.**
