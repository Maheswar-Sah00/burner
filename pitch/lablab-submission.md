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
Paste a recruiter's message or any repo link. Burner runs the code in a throwaway Vultr VM full of fake secrets, shows you exactly what it tried to steal, and then deletes the VM.
```

### Long Description (600–2000, 100 words min)
```
In October 2026, about $6.3B was stolen from Binance. It started with a fake recruiter who sent an engineer a coding test. Binance says its security tools didn't catch the malware.

This is a real North Korean campaign. Fake recruiters send developers a "take-home" repo. When you run it, it steals your keys, wallets and passwords. It has hit 30,000+ devices in 100+ countries. The FBI says "use a VM", but a VM can't tell you if the code was bad.

Burner can. You paste the recruiter's message. Burner starts a new Vultr VM, fills it with 18 fake secrets, and runs the repo the way a candidate would. A fake internet records everything the repo tries to send. Then the VM is deleted, and Vultr's API confirms it's gone.

Why Vultr: every scan needs its own fresh machine for a few minutes. Vultr lets me create a VM through its API, use it once and delete it. Serverless Inference runs the AI (DeepSeek reads the message, Nemotron checks the README). Object Storage keeps the evidence after the VM is gone. A whole scan costs about $0.002.

What I tested on real Vultr VMs:
- 16 of 16 attack samples caught, 0 false alarms on 11 clean ones. A popular static scanner (GuardDog) caught 13.
- 0 false alarms on 21 real public repos.
- In a live scan, the repo sent 10 kinds of fake secrets to the attacker as soon as npm start ran. The VM lived 95 seconds.
- It also works on fake MCP servers, Hugging Face models and VS Code extensions: 7 of 7 attacks caught, 0 of 6 false alarms.
- Nothing escaped the sandbox. 0 packets went out.

The verdict comes from fixed rules, not AI. I hid a "say this is safe" message in a README to trick it. It still said MALICIOUS.

Who pays: company security teams. Binance's victim was an employee doing a coding test at work. Burner makes running someone else's code safe by default.
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
| Cover Image | `pitch/cover.png` (1920×1080, cropped from the landing page) |
| Video Presentation | the edited video, 3:00–3:15 (script in `pitch/video-edit-plan.md`) |
| Slide Presentation (PDF) | `pitch/Burner-deck.pdf` |

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
Try it in 2 minutes: open the live app, choose Sample > "the npm-start stealer" and press Burn it. It uses a real Vultr VM, so it takes about two minutes. You'll see the VM start, the fake AWS key get stolen, and the VM get deleted. Click "Check with Vultr now" and Vultr's API answers 404. Then try "a clean take-home" (comes back clean) and "Fake MCP server" (caught adding itself to Claude Desktop).

All test results, with raw files from every scan, are in reports/benchmark.

To be honest about the numbers:
- I wrote the 27 test samples myself, based on public threat reports (Elastic, Socket, Trend Micro, ESET, Island).
- Of the 21 real repos, 12 ran and came back clean, and 9 were INCONCLUSIVE (the app never started or there was nothing to run). The first run had 2 false alarms from pm2; I fixed that rule and kept the before data.
- "Clean" means nothing bad happened in this run. It doesn't mean 100% safe. The README lists what Burner can't catch yet.

Safety: every secret Burner plants is fake. Every attack sample is a harmless copy that only talks to test addresses. Each VM is used once and deleted, and anything older than 20 minutes is cleaned up automatically.

Why this needs Vultr (each part does a real job):
- Cloud Compute + API: a brand-new VM for every scan, created, tagged and deleted by code. One VM is kept ready so scans start fast. Without cheap hourly VMs I can control through an API, one VM per scan would cost too much to offer for free.
- Firewall: every scan VM gets a firewall group that blocks all incoming traffic except mine.
- Serverless Inference: DeepSeek reads the message and plans the steps. Nemotron screens the README for prompt injection.
- Object Storage: the evidence (traffic, file activity, report) stays after the VM is destroyed.
The "What Vultr did" card in every report shows each service used and the cost.

Built solo for Track 1 (Blast Radius Zero).
```
