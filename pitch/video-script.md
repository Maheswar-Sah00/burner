# Burner: demo video script (3:40)

Target length 3:30–3:50. Record the screen at 1920×1080. The voice-over is the spoken lines; **On screen** says what to show.
Do the demo with a **real scan** (not `BURNER_MOCK`) so the Vultr VM really appears and disappears. Keep the Vultr console open in a second tab, filtered to the `burner-scan` tag.
If a step is slow, cut the waiting but keep the on-screen timer visible, so it's clear the timing is real.

---

### 0:00–0:25 · The message

**On screen:** A chat window (LinkedIn-style, fictional) showing the text of `samples/recruiter-message.txt`. Highlight these phrases one by one: *"$180–220k"*, *"run it locally"*, *"before our call tomorrow at 10am"*, *"Telegram"*.

> "Meet Priya. She's a backend developer, and this morning she got a message from Daniel at Lumina Ledger, a DeFi company. Senior role, $220k, fully remote. All she has to do is clone their take-home and run it before tomorrow's call."
>
> "Lumina Ledger isn't real. But this exact play is: fake recruiters, fake take-homes, real malware."

### 0:25–0:55 · Why this matters

**On screen:** Slide 2 of the deck (the numbers), then slide 3.

> "A joint advisory from seven agencies in September says this campaign infected more than 30,000 devices in over 100 countries and drained more than 7,000 crypto wallets. DMM Bitcoin lost $308 million after a fake recruiter's pre-employment test."
>
> "Antivirus doesn't help much. Elastic found a variant with zero detections. On my own PC, Windows Defender caught one of my two test samples and missed the one that steals at `npm start`. The FBI's advice is 'use a virtual machine'. That keeps you safe, but it doesn't tell you anything."

### 0:55–1:15 · The puzzle

**On screen:** Slide 4 (the puzzle).

> "Platforms each solve a piece of this: scanners, sandboxes, VMs, takedowns. Open-source experiments are starting too. Nobody has put the whole puzzle together in a candidate's hands. That's Burner."

### 1:15–1:35 · Paste the message

**On screen:** The live app at `https://139-84-215-1.sslip.io`. Paste the full recruiter message. Click **Burn it**. The progress card appears and the timer starts.

> "Priya pastes the recruiter's message into Burner. That's all she does."
>
> "Burner's AI, running on Vultr Serverless Inference, pulls out the repo link and flags the lure: running code before any interview, a deadline, Telegram, crypto, a salary that's too high. Then it reads the README the way a candidate would and plans the steps."

**On screen:** Zoom on the progress lines: `red flags: 5`, `screening the README for prompt injection`, then the plan `npm install → npm run start → npm test → npm run start (+45 days)`.

### 1:35–2:05 · A brand-new VM

**On screen:** Split screen. Left: the Burner progress card, `creating a fresh Vultr VM (vc2-2c-4gb, blr)`. Right: the Vultr console, where a new `burner-…` instance appears with status *Installing*, then *Running*.

> "Now Burner asks the Vultr API for a brand-new machine, just for this one repo. There it is in the Vultr console, ready in about 45 seconds."
>
> "Inside, the repo runs in a gVisor sandbox as 'dev-laptop'. The home folder is full of fake secrets: AWS keys, an SSH key, another project's `.env`, Solana and Exodus wallets, a MetaMask vault, saved Chrome passwords. Every one is random and unique to this scan."
>
> "The network is fake too. Every connection goes to our own sinkhole, which records it and sends nothing out."

### 2:05–2:40 · The theft

**On screen:** Steps tick through: `npm install`, `npm run start`. Then the red **MALICIOUS** card. Scroll slowly through **What it stole**: AWS access key, `~/.aws/credentials`, `203.0.113.55:1224`, step `npm run start`. Open **Captured on our fake internet** and show the multipart body containing `aws_access_key_id = AKIA…`.

> "Here's the moment. As soon as the app starts, it opens the AWS credentials, the SSH key, the wallets, the browser passwords. And then it uploads them to a hard-coded server on port 1224, the same pattern as the real BeaverTail malware. It also sends a second copy over HTTPS, which Burner decrypts with its own certificate."
>
> "This is the fake AWS key we planted, arriving at the attacker. Ten of our fake secrets left the sandbox."
>
> "The verdict comes from rules, not the AI: a secret was read, and the same secret was seen leaving. The AI only writes the plain-English explanation underneath."

### 2:40–3:05 · Containment moment

**On screen:** The progress card shows `sandbox destroyed`, then `VM destroyed after Ns`, then the green box **"VM destroyed — nothing touched your laptop"**. Cut to the Vultr console tab and refresh: the `burner-…` instance is gone. Hold for 2 seconds. Then show the cost line on screen.

> "And now the containment. The sandbox is destroyed, and then the whole VM. Refresh the Vultr console: it's gone. The malware, the fake secrets it stole, the machine it ran on. That VM lived about three minutes. Prorated, it cost about a tenth of a cent. Even if Vultr billed a full hour, it's under three cents."
>
> "If anything crashes mid-scan, a reaper deletes any scan VM older than 20 minutes."

**On screen (optional, 5 s):** The containment table from the deck: real internet, host SSH, cloud metadata, fork bomb, memory bomb, prompt injection, each with its result. 10 of 10 escape attempts contained (real internet, DNS, cloud metadata, host SSH, Docker socket, host kernel, root, host disk, raw sockets); fork bomb capped at 396 processes; a memory bomb crashes the sandbox but is flagged SUSPICIOUS, never clean; a README prompt injection fooled the safety screen but not the rule-based verdict

### 3:05–3:25 · Does it hold up?

**On screen:** Slide 8 (benchmark table). Then a 3-second clip of the **clean take-home** sample in the app, coming back green: "No malicious behaviour observed".

> "We built 13 defanged attack samples from published reports: VS Code auto-run tasks, postinstall hooks, a payload that only fires in the tests, a time bomb, DNS exfiltration, obfuscation. We also built 11 ordinary take-homes. Burner caught 13/13 with 0/11 false alarms. GuardDog, a static scanner, caught 11/13."
>
> "A normal take-home comes back clean. And Burner is honest about it: clean means nothing malicious was seen in this run, not that the repo is guaranteed safe."

### 3:25–3:40 · Close

**On screen:** Back to Priya's chat. She types "Thanks, I'll pass." and blocks the contact. Fade to the closing slide with the URL large.

> "Priya never ran a stranger's code on her laptop. A throwaway Vultr VM ran it for her, showed her the theft, and was destroyed."
>
> "Burner. Paste the message before you run the repo. It's live at 139-84-215-1.sslip.io."

---

## Shot checklist

- [ ] Chat mock-up with the Lumina Ledger message (fictional; no real company names or logos)
- [ ] Live scan on the real host, run with the LLM on (not `BURNER_MOCK`)
- [ ] Vultr console: the instance appears, then disappears after a refresh. **This is the containment shot, so don't cut it.**
- [ ] "What it stole" table plus one captured request body showing the fake AWS key
- [ ] Clean sample result (green)
- [ ] Deck slides 2, 3, 4 and 8 as cutaways
- [ ] The URL on screen for the last 5 seconds
- [ ] Never show `.env`, API keys or the Vultr account ID on screen
