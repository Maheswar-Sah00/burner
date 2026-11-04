# lablab.ai submission: Burner

## Project title
Burner: run a recruiter's take-home in a throwaway VM before you do

## Short description (≤ 255 characters)
Paste a recruiter's message. Burner runs the take-home repo like a candidate would, inside a fresh Vultr VM full of fake secrets, shows which keys it stole and where they went, then destroys the VM.

<!-- 197 characters -->

## Long description

**Result first.** We gave Burner a defanged copy of a fake-recruiter take-home. As soon as `npm start` ran, the repo sent 10 of our planted fake secrets to a hard-coded IP on port 1224, as a multipart upload in the style of BeaverTail. It also sent a second copy over HTTPS, which Burner decrypted with its own CA. The stolen items were AWS keys, an SSH key, Solana and Exodus wallets, a MetaMask vault, saved Chrome passwords and another project's `.env`.

Burner showed every secret, the file it came from, where it was sent, and the step that sent it. Then it deleted the Vultr VM it ran on. A VS Code `folderOpen` sample was caught sending 4 secrets with curl and adding `.bashrc` persistence, and a clean take-home came back clean. Windows Defender on the developer's PC flagged only one of the two malicious samples.

On a benchmark of 13 campaign-style samples and 11 clean take-homes, Burner caught 13/13 with 0/11 false alarms. The static scanner GuardDog caught 11/13. Median scan time was 91 s.

**The problem.** North Korea's "Contagious Interview" campaign sends developers fake job take-homes that steal keys and crypto when run. A joint advisory from seven agencies in four countries (18 Sep 2026) counts 30,000+ infected devices in 100+ countries and 7,000+ drained wallets. Elastic found a July 2026 variant with zero antivirus detections that fires at `npm start`. The FBI's advice is to use a VM, but a VM keeps you safe without telling you what the code did. Platforms each solve a piece of this: scanners, sandboxes, VMs, takedowns. Open-source experiments are starting. Nobody has put the whole puzzle together in a candidate's hands.

**How it works.**
1. **Read.** The user pastes the recruiter's message. Vultr Serverless Inference (`deepseek-v4.1-flash`) extracts the repo link and red flags and gives a lure score. On our sample it found 5 red flags and scored 8/10. `nemotron-3.5-content-safety` screens the README for prompt injection.
2. **Boot.** The control plane creates a brand-new Vultr VM through the Vultr API, one per scan, taken pre-armed from a warm pool (a cold VM is ready in ~30-45 s; arming takes ~2 min, so one is always kept ready).
3. **Bait and run.** The repo runs in a gVisor container with all capabilities dropped and memory, CPU and pid limits. The home folder holds 15 unique fake secrets. The agent behaves like a candidate: VS Code `folderOpen` tasks, `npm install` lifecycle scripts, `npm start`, `npm test`, any steps the README asks for, and a rerun with the clock 45 days ahead.
4. **Catch.** iptables sends all DNS and TCP to a fake internet that terminates TLS with Burner's CA, records every request and forwards nothing. gVisor logs every file open, exec and connect.
5. **Judge.** The verdict is rule-based: a fake secret read, plus the same secret seen leaving (including base64, hex, gzip, zip, XOR and DNS-tunnelled forms), means MALICIOUS. Persistence, `curl | sh`, hard-coded IPs and sandbox checks are flagged. The LLM only explains the verdict and can't change it.
6. **Destroy.** The VM is deleted through the API, with its lifetime and cost shown on screen. The evidence bundle goes to Vultr Object Storage behind a 7-day presigned link. A reaper deletes any scan VM older than 20 minutes.

**Containment.** 10 of 10 escape attempts contained (real internet, DNS, cloud metadata, host SSH, Docker socket, host kernel, root, host disk, raw sockets); fork bomb capped at 396 processes; a memory bomb crashes the sandbox but is flagged SUSPICIOUS, never clean; a README prompt injection fooled the safety screen but not the rule-based verdict (escape attempts tested: real internet, host SSH, cloud metadata 169.254.169.254, fork bomb, memory bomb, prompt injection of Burner's own AI).

**Cost.** A 3-minute scan VM (vc2-2c-4gb, $20/mo) costs about $0.0014 prorated, or $0.027 if a full hour is billed. A scan uses about 4 LLM calls and ~5k tokens.

**What it can't catch.** Malware that detects the VM and stays quiet, payloads that need a real reply from the attacker, time bombs beyond +45 days, stacks other than JS and Python, and kernel-level gVisor escapes. A clean result means nothing malicious was observed, not that the repo is safe.

**Who it's for.** Crypto/Web3 firms, enterprise security teams (victims have committed this malware into their employers' repos), individual developers (free tier), and hiring platforms.

## Technologies used
Vultr Cloud Compute (per-scan VMs via the Vultr API, warm pool), Vultr Serverless Inference (deepseek-v4.1-flash-1017, nemotron-3.5-content-safety), Vultr Object Storage, gVisor (runsc), Docker, iptables, Python 3.12, FastAPI, Server-Sent Events, Caddy, sslip.io, libfaketime, Python cryptography, boto3, GuardDog (baseline)

## Tags
security, sandbox, malware-analysis, supply-chain-security, honeytokens, ai-agents, developer-tools, vultr, gvisor, crypto, fake-recruiter

## Category / track
Track 1: Blast Radius Zero (sandboxed code/browser agent)

## Links
- GitHub: `{{GITHUB_URL}}`
- Live app: https://139-84-215-1.sslip.io
- Demo video: `{{VIDEO_URL}}`
- Slides (PDF): `pitch/Burner-deck.pdf`, uploaded as `{{DECK_URL}}`
