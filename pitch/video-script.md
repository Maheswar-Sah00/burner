# Burner: demo video script (3:13)

Target 3:00–3:15 (this cut runs 3:13). lablab's rule book puts videos **under 3 minutes in the "Limited" tier**, so don't cut below 3:00.
The product is on screen from the first frame, and there are no slides, no architecture and no code. The news numbers appear as captions and stat pills over the product, and the technical depth stays in the README and deck.

Record at 1920×1080 with a **real scan** (not `BURNER_MOCK`), so the Vultr VM really appears and disappears. Keep the Vultr console open in a second tab, filtered to the `burner-scan` tag. Cut the waiting, but keep the on-screen timer visible so it's clear the timing is real.

**Style** (Backline-style, see the sound and motion notes at the end): eased zooms onto the UI, a cursor highlight on every click, one large caption per step, and a music bed ducked under the VO.

---

### 0:00–0:12 · Paste it

**On screen:** The live landing page at `https://139-84-215-1.sslip.io`. The cursor drifts over the dither field and the pixels light up under it. Paste the recruiter's message (`samples/recruiter-message.txt`) and click **Burn it**. The timer starts.
**Captions** (one at a time, top-left, with the source in small mono): *"29 Oct 2026: about $6.3B stolen from Binance."* / *"It started with a coding assignment."* (BleepingComputer, 3 Nov 2026)

> "On October 29th, about six point three billion dollars was stolen from Binance. It started with a fake recruiter and a coding assignment. So before you run a take-home, paste the message here."

### 0:12–0:32 · It reads the lure

**On screen:** Zoom on the progress card: `red flags: 5`, the flags appearing one by one (*run before the interview*, *deadline*, *Telegram*, *crypto*, *salary too high*), then `screening the README for prompt injection`, then the plan `npm install → npm run start → npm test → npm run start (+45 days)`.
**Caption:** *"Paste the message. Burner does the rest."*

> "Burner's AI, running on Vultr Serverless Inference, pulls out the repo, flags the lure, and reads the README the way a candidate would, so it runs exactly what the recruiter told you to run."

### 0:32–1:02 · A brand-new VM

**On screen:** Split screen. Left: `creating a fresh Vultr VM (vc2-2c-4gb, blr)`. Right: the Vultr console, where a new `burner-…` instance appears as *Installing*, then *Running*.
**Stat pills** stacking top-left while the VM boots: *"30,000+ devices infected"* / *"100+ countries"* / *"7,000+ wallets drained"* (joint advisory, Sep 2026).

> "Burner asks the Vultr API for a brand-new machine, just for this one repo. There it is in the console. This campaign has already infected more than thirty thousand devices in over a hundred countries. Antivirus misses it, and the FBI's advice is 'use a virtual machine'. A VM keeps you safe, but it doesn't tell you anything. Burner does."

### 1:02–1:20 · The bait

**On screen:** Zoom on the setup lines: `plant 18 fake secrets · fake internet on`. Quick cuts of the planted names: AWS keys, SSH key, another project's `.env`, Solana and Exodus wallets, MetaMask vault, saved Chrome passwords, the Claude Desktop and Cursor MCP keys.
**Caption:** *"18 fake secrets. A fake internet."*

> "Inside, the repo runs in a gVisor sandbox on a laptop that looks real: the home folder is full of fake secrets, each one unique to this scan. And the internet is fake too. Every connection lands in our sinkhole."

### 1:20–1:55 · Caught

**On screen:** Steps tick: `npm install`, `npm run start`. The red **MALICIOUS** card lands, with a hit sound. Slow scroll through **What it stole**: the fake AWS key, `~/.aws/credentials`, `203.0.113.55:1224`, step `npm run start`. Open **Captured on our fake internet** and zoom on `aws_access_key_id = AKIA…` in the request body.
**Caption:** *"Caught with the fake key in its hand."*

> "As soon as the app starts, it opens the AWS keys, the SSH key, the wallets and the browser passwords, and uploads them to a hard-coded server on port 1224, the same pattern as the real BeaverTail malware. That's the fake key we planted, arriving at the attacker. The verdict comes from rules, not the AI: a secret was read, and the same secret left."

### 1:55–2:15 · Containment, and what Vultr did

**On screen:** `sandbox destroyed` → `VM destroyed after Ns` → the green box **"VM destroyed — nothing touched your laptop"**. Cut to the Vultr console and refresh: the instance is gone. Hold 2 seconds. **Do not cut this shot.** Back in the report, click **Check with Vultr now**: the `404` lands. Then zoom on the **What Vultr did** card: one line per Vultr service (Cloud Compute: VM seconds · Serverless Inference: each AI call · Object Storage: the evidence bundle) and the total.
**Captions:** *"Then the whole machine is destroyed."* / *"Vultr confirms it: 404."*

> "Then the sandbox is destroyed, and then the whole VM. Refresh the console: it's gone, and Vultr's own API confirms it. Here's everything Vultr did for this one scan: the machine, the AI, the evidence. About a fifth of a cent."

### 2:15–2:30 · Act on it

**On screen:** Scroll to **Tell people**: click *Copy* on the group warning (the copy toast lands). Then **Report it**: the prefilled GitHub abuse report naming the exact commit.
**Caption:** *"Warn your friends. Report it. In one click."*

> "Then it helps you act: a warning for your group chat, and an abuse report that names the exact commit."

### 2:30–2:48 · Not just take-homes

**On screen:** Back to the start page. **Sample** tab → **Fake MCP server** → **Burn it**. Fast-forward the run (8×, timer visible). The red **MALICIOUS** card lands. Zoom on two lines: the stolen **MCP server token (Claude Desktop config)** and the finding **"Modified ~/.config/Claude/claude_desktop_config.json to run again later"**.
**Stat pill** (top-left, small mono source): *"800+ fake MCP servers on GitHub"* (FakeGit, Island, Jul 2026).
**Caption:** *"Not just take-homes. MCP servers, AI models, extensions."*

> "And it's not just take-homes. This year, more than eight hundred fake MCP servers turned up on GitHub. Burn one: it steals the keys your AI tools hold, and adds itself to Claude Desktop so it runs every day. GitHub doesn't scan for this. Burner runs it first. Same for a Hugging Face model or a VS Code extension: paste the link."

### 2:48–3:03 · Does it hold up?

**On screen:** The **Track record** page in the app. Animate the big numbers in: **16/16** attacks caught, **0/11** false alarms (GuardDog 13/16 and 1/11), **0 false alarms on 21 real repos**. Then a 2-second clip of the **clean take-home** sample coming back green.
**Caption:** *"16 of 16 caught. 0 false alarms."*

> "On sixteen attack samples built from published reports, Burner caught every one with zero false alarms. A static scanner caught thirteen. And on twenty-one real public repos, zero false alarms."

### 3:03–3:13 · Close

**On screen:** Near-black end card, ember logo, *"Run the take-home before it runs you."*, a smaller second line *"Any repo. One throwaway VM."*, the URL large.

> "Burner. Run it before it runs you. Live now on Vultr."

---

## Sound and motion

- **Music:** a low, tense electronic bed (dark synth pulse, ~100 BPM). It lifts at the MALICIOUS hit (1:25), resolves at the VM-destroyed moment (2:00), and lifts again for the MCP-server hit (2:40). Duck it about 12 dB under the VO.
- **SFX:** soft click on every button, tick on each step line, a deep hit on MALICIOUS, a whoosh plus a soft "power down" when the VM disappears, a light pop on each stat pill and copy toast.
- **Motion:** eased zooms (about 0.6 s, ease-in-out) onto the line being talked about. Cursor halo on clicks. Captions scale in from 106% over 6 frames.
- **Check before calling it done:** watch frames at every caption change, peak VO around -6 dBFS with the music under -18 dBFS, and the total length between 3:00 and 3:15.

## Shot checklist

- [ ] Landing hover on the dither field (first 3 seconds)
- [ ] Live scan on the real host with the LLM on (not `BURNER_MOCK`)
- [ ] Vultr console: the instance appears, then disappears after a refresh. **This is the containment shot, so don't cut it.**
- [ ] "What it stole" plus one captured request body showing the fake AWS key
- [ ] Tell people → Copy, and the Report it kit
- [ ] "Check with Vultr now" (the 404) and the **What Vultr did** card
- [ ] Sample → **Fake MCP server** → MALICIOUS, with the Claude Desktop config line visible
- [ ] Track record numbers and the clean sample result (green)
- [ ] URL on screen for the last 5 seconds
- [ ] Never show `.env`, API keys or the Vultr account ID on screen
