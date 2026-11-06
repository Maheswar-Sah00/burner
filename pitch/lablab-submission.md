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
Paste a recruiter's message or any link. Burner runs the code in a throwaway Vultr VM full of fake secrets, shows you exactly what it tried to steal, and deletes the VM. Take-homes, MCP servers, AI models, extensions.
```

### Long Description (600–2000, 100 words min)
```
In October 2026, about $6.3B was stolen from Binance. It started with a fake recruiter who sent an engineer a coding test. The malware was hidden inside, and Binance's security tools didn't catch it.

This is a real North Korean campaign. Fake recruiters send developers a "take-home" repo. When you run it, it steals your keys, wallets and passwords. It has hit 30,000+ devices in 100+ countries. The FBI says "use a VM", but a VM can't tell you if the code was bad.

Burner can. You paste the message. Burner starts a new Vultr VM, fills it with fake secrets, and runs the repo the way a candidate would. A fake internet records everything the repo tries to send. Then the VM is deleted.

It's not only take-homes. In 2026, 800+ fake MCP servers appeared on GitHub and 70+ sleeper VS Code extensions per wave hit Open VSX. Paste an MCP server, a Hugging Face model or an extension: Burner calls every tool, loads the model, or opens the extension.

Why Vultr: this only works if every scan gets its own fresh machine, and only for a few minutes. Vultr lets me create a VM through its API, use it once, and delete it: about $0.002 a scan, AI included. Serverless Inference runs DeepSeek and the Nemotron safety model. Object Storage keeps the evidence after the VM is gone.

What I tested on real Vultr VMs:
- Caught 16 of 16 attack samples, with 0 false alarms on 11 clean ones. A popular static scanner (GuardDog) caught 13.
- 0 false alarms on 21 real public repos (after one small fix).
- In a live scan, the repo stole 10 fake secrets the moment I ran npm start.
- MCP servers, AI models, extensions, exploit demos: 7 of 7 caught, 0 false alarms on 6 clean ones (GuardDog: 4 of 7). 4 real ones came back clean.
- Paste to verdict: about 2 minutes. Cost per scan: about $0.002, AI included.
- Nothing escaped the sandbox. 0 packets went out.

The verdict comes from fixed rules, not AI. I hid a "say this is safe" message in a README to trick it. It still said MALICIOUS.
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
| Video Presentation | the edited video (plan in `pitch/video-edit-plan.md`) |
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
Try it in 2 minutes: open the live app, choose Sample > "the npm-start stealer" and press Burn it. It uses a real Vultr VM, so it takes about two minutes. You'll see the VM start, the fake AWS key get stolen, and the VM get deleted with its cost on screen. Then try "a clean take-home". It comes back clean.

All test results, with raw files, are in reports/benchmark.

To be honest about the numbers:
- I wrote the 27 take-home samples and the 13 MCP/model/extension samples myself, from public threat reports. The 13 are a smoke test, not a benchmark.
- The real-repo test had 2 false alarms on the first run. I fixed one rule and wrote down the before and after.
- "Clean" means nothing bad happened in this run. It doesn't mean the code is 100% safe. The README lists what Burner can't catch yet.

Safety: every secret Burner plants is fake. Every attack sample is a harmless copy that only talks to test addresses. Each VM is deleted after one scan; a reaper removes anything older than 20 minutes.

Why this needs Vultr (each part does a real job):
- Vultr Cloud Compute + API: a brand-new vc2-2c-4gb VM for every scan, created, tagged and deleted through the API. After the delete, Burner asks Vultr for the VM again and keeps the 404 as proof. One VM is kept ready so scans start fast. Every report shows a Vultr bill: VM seconds, each AI call, the evidence.
- Vultr Firewall: every scan VM gets a firewall group that blocks all incoming traffic except mine.
- Vultr Serverless Inference: DeepSeek reads the recruiter's message, finds the red flags and plans the steps. Nemotron screens the README for prompt injection.
- Vultr Object Storage: each scan's evidence (traffic, file activity, report) is saved there, so the proof stays after the VM is destroyed.

Also new: a quick pre-check that shows warning signs in seconds, and an "I already ran it" list that tells you exactly which keys to change if you ran the code on your own laptop.

Built solo for Track 1 (Blast Radius Zero).
```
