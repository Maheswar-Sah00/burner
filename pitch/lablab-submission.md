# lablab.ai submission: Burner (form-ready)

Copy each block into the matching field. Character counts are checked against the form limits.

---

## STEP 1 · Basic Information

### Submission Title (5–50)
```
Burner: Run the Take-Home Before It Runs You
```

### Short Description (50–255)
```
Paste a recruiter's message or any repo link. Burner runs the code in a throwaway Vultr VM full of fake secrets and shows what it tried to steal. Real employers get a signed badge proving their take-home is theirs and was burned clean.
```

### Long Description (600–2000, 100 words min)
```
In October 2026, about $6.3B was stolen from Binance. It started with a fake recruiter who sent an engineer a coding test. Binance says its security tools didn't catch the malware.

This is a real North Korean campaign. Fake recruiters send developers a "take-home" repo. When you run it, it steals your keys, wallets and passwords. It has hit 30,000+ devices in 100+ countries. The FBI says "use a VM", but a VM can't tell you if the code was bad.

Burner can. You paste the recruiter's message. Burner starts a new Vultr VM, fills it with fake secrets, and runs the repo the way a candidate would. A fake internet records everything the repo tries to send. Then the VM is deleted, and Vultr's API confirms it's gone.

New: Burner Verified, for the companies being impersonated. One in three recruiters say someone has posed as them. Now a real employer can prove its take-home is theirs: every push is burned on a Vultr VM, and Burner signs what it saw for that exact commit, next to who owns the repo according to GitHub. The README badge opens a page where candidates check it. When a pull request slipped a stealer into our demo take-home, the GitHub Action failed the check and commented "Don't merge this".

What I tested on real Vultr VMs:
- 16 of 16 attack samples caught, 0 false alarms on 11 clean ones. GuardDog, a static scanner, caught 13.
- 0 false alarms on 21 real public repos.
- In a live scan, 10 kinds of fake secrets left as soon as npm start ran. The VM lived 95 seconds.
- Nothing escaped the sandbox. 0 packets went out.

Why Vultr: every scan needs its own fresh machine for a few minutes, created and deleted through the API. Serverless Inference runs the AI (DeepSeek, Nemotron). Object Storage keeps the evidence and the signed statements. A scan costs about $0.002.

The verdict comes from fixed rules, not AI. A README that told the AI to say "safe" still got MALICIOUS.
```

### Participation Mode
Online

### Categories
Type into the search box and pick what exists. In order of priority:
1. The Vultr Agent Rush track, if it is listed (search `Vultr`, `Blast Radius`, `Agent Rush`). **Don't pick "Vultr Track - Raise"** unless you are actually entered in the Raise hackathon; it belongs to a different event.
2. `Cybersecurity` / `Security` (search `secur`)
3. `Cloud Application`
4. `Web Application`
5. `AI Agents` / `Agents` (search `agent`, but skip the "INTERNET OF AGENTS" tracks, which belong to a different hackathon)
6. `Developer Tools` / `Coding` if there is room

### Technologies Used
Search and add whichever exist in the list:
`Vultr`, `Vultr Cloud Compute`, `Vultr Serverless Inference`, `Vultr Object Storage`, `DeepSeek`, `NVIDIA Nemotron` (or `NVIDIA`), `Python`, `FastAPI`, `Docker`, `gVisor`, `Linux`, `D3.js`, `JavaScript`
If a name isn't listed, skip it. The README covers the full stack.

---

## STEP 2 · Media

| Field | What to upload |
| --- | --- |
| Cover Image | `pitch/cover.png` (1920×1080, built in the app's own design from `pitch/build/cover.html`) |
| Video Presentation | the edited video, 3:00–3:15 (script in `pitch/video-edit-plan.md`) |
| Slide Presentation (PDF) | `pitch/Burner-slides.pdf` (8 slides, built from `pitch/build/slides.html`; re-render with `python pitch/build/render.py`) |

---

## STEP 3 · Links

### GitHub Repository
```
https://github.com/Maheswar-Sah00/burner
```

### Demo Application Platform
Pick the web option (`Web` / `Web App` / `Website`, whichever the dropdown has). Avoid Hugging Face / Streamlit: the app runs on my own Vultr VM.

### Application URL
```
https://139-84-215-1.sslip.io
```

### Additional Information (≤2000)
```
Try it in 2 minutes: open the live app, choose Sample > "the npm-start stealer" and press Burn it. It uses a real Vultr VM, so it takes about two minutes. You'll see the fake AWS key get stolen and the VM get deleted. Click "Check with Vultr now" and Vultr's API answers 404.

Burner Verified (new), all live:
- A demo employer take-home with the badge: github.com/Maheswar-Sah00/acme-takehome
- The PR that slipped a stealer in, blocked by the GitHub Action: github.com/Maheswar-Sah00/acme-takehome/pull/1
- A verified organisation's repo, burned clean and signed: 139-84-215-1.sslip.io/v/github.com/fastify/demo
The signature is checked in your browser (Ed25519). Add the badge to any take-home with one line of GitHub Actions: uses: Maheswar-Sah00/burner@main

All test results, with raw files from every scan, are in reports/benchmark.

To be honest about the numbers:
- I wrote the 27 test samples myself, based on public threat reports.
- Of the 21 real repos, 12 ran clean and 9 were INCONCLUSIVE (the app never started or there was nothing to run). The first run had 2 false alarms from pm2; I fixed that rule and kept the before data.
- "Clean" means nothing bad happened in this run, not 100% safe. A signed statement covers one commit; any new commit is burned again.

Safety: every secret Burner plants is fake. Every attack sample is a harmless copy that only talks to test addresses. Each VM is used once and deleted.

Why this needs Vultr:
- Cloud Compute + API: a brand-new VM for every scan and every push, created, tagged and deleted by code.
- Firewall: every scan VM blocks all incoming traffic except the control server.
- Serverless Inference: DeepSeek reads the message and plans the steps. Nemotron screens the README for prompt injection.
- Object Storage: evidence and signed statements stay after the VM is destroyed.

Built for Track 1 (Blast Radius Zero).
```
