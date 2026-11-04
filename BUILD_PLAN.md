# Burner — build plan

Vultr Agent Rush, Track 1 (Blast Radius Zero). Locked 4 Nov 2026.
Hard deadline: **Mon 9 Nov 03:30 IST**. Our target: **Sun 8 Nov 22:00 IST**.

**One line:** paste the recruiter's message or the take-home repo link. Burner runs the repo the way a candidate would, inside a throwaway Vultr VM full of fake secrets, and tells you what it tried to steal.

---

## Architecture

```
Browser (live URL)
   │  repo URL + recruiter message
   ▼
Control VM (small Vultr VM, always on)
   ├─ Web app + API (FastAPI) + job queue
   ├─ Vultr API client ── creates ──► Burner VM (one per scan, made from a snapshot)
   │                                     ├─ gVisor (runsc) container: the repo runs here
   │                                     │    seeded with fake secrets (bait):
   │                                     │    ~/.aws, ~/.ssh, .env, wallet folders, browser profile
   │                                     ├─ Fake internet: sinkhole DNS + HTTPS-intercepting proxy
   │                                     │    (catches the outgoing requests, sends nothing out)
   │                                     ├─ Watcher: which files were opened, which processes started
   │                                     └─ Agent ("the candidate"): reads README, opens in VS Code
   │                                          (folderOpen tasks), install → start → test, time-shift pass
   ├─ Verdict = RULES on observed behaviour (a fake key read + the same key seen leaving = MALICIOUS)
   ├─ Vultr Serverless Inference: plans the candidate's steps, writes the plain-English explanation,
   │     nemotron content-safety screens README/issue text for prompt injection
   ├─ Evidence bundle (logs, captured requests, timeline) → Vultr Object Storage
   └─ Destroys the Burner VM; shows "created → ran → destroyed, $0.0x"
```

**Rule:** the LLM never decides the verdict. It only drives the run and explains the result.

**Measured 4 Nov:** a fresh vc2-1c-1gb Ubuntu 24.04 VM in Bangalore (blr) was ready in 41s and deleted at 43s, so one VM per scan is practical.

**Fallback if VM boot is too slow (>2 min):** keep one warm Burner VM ready, rebuild it after each scan. For the demo, still show one scan with a fresh VM made from scratch.

---

## Day plan

| Day | Goal | Done when |
|---|---|---|
| **Wed 4 Nov (night)** | Accounts and keys ready. Repo set up. Ask about malware policy in Discord. | Vultr API key and Inference key work from code; one test VM made and destroyed with code |
| **Thu 5 Nov** | Sandbox core: Docker + gVisor on a VM, fake secrets, fake internet, watcher | A harmless test repo that reads `~/.aws/credentials` and POSTs it is **caught**, with the captured request shown |
| **Fri 6 Nov** | Agent + verdict + one VM per scan + snapshot | One command: repo URL → new VM → run → verdict JSON → VM destroyed |
| **Sat 7 Nov** | Web UI, recruiter-message input, evidence page, benchmark vs GuardDog, re-check competitors | Live URL works end to end; a results table with numbers |
| **Sun 8 Nov** | Video (3–5 min, containment moment), PDF deck, lablab submission | Submitted by 22:00 IST |

**Test samples** (harmless copies we write ourselves, modelled on the reported attacks):
1. Runs at `npm start`, hidden payload, steals `.env` and wallet files (Elastic, Jul 2026)
2. VS Code `folderOpen` task (Trend Micro, Mar 2026)
3. `postinstall` script (classic)
4. Waits until a later date before acting (time-shift pass catches it)
5–10. Clean, real take-home repos (to measure false alarms)

Every sample is defanged: it only ever "steals" our fake keys and sends them to our fake internet.

---

## What I need from you

1. Claim the $200 credit: console.vultr.com/billing/?promo=HACKATHON
2. Make two keys and put them in `b:\Projects\vultr-lablab\.env` (don't paste them in chat):
   ```
   VULTR_API_KEY=...        # Account → API → enable, allow your IP
   VULTR_INFERENCE_KEY=...  # Serverless Inference → subscribe → key
   ```
3. Post in the hackathon Discord: "Is it OK to run defanged malware samples (only stealing fake keys, network sinkholed) on Vultr VMs for a Track 1 sandbox project?"
4. ~~Solo or team?~~ Solo (confirmed 4 Nov).

## Rules for the pitch
- Include the puzzle line: "Platforms each solve a piece, and open-source experiments are starting. Nobody has put the whole thing in a candidate's hands."
- Never say "nobody is building this". Avoid headlining "blast radius" or "receipts".
