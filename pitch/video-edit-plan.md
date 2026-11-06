# Burner: video edit plan (~3:25)

Format: your usual style. Face to camera from two angles (**FRONT** and **SIDE**, about 45°), **VO** (voice only over visuals),
plus the new documentary layer: **ART** (news articles with the numbers highlighted), slow motion and fast motion.
The look comes from `Downloads/inspo.mp4`, with the colour switched to Burner's ember.

---

## 1. Style guide (taken from inspo.mp4)

What inspo does, and how to use it here:

| In inspo | For Burner |
| --- | --- |
| Big blue ALL-CAPS headline, heavy grotesk, set **behind the person** (heads cover part of the letters) | Same, in ember `#FF6A2B`. Use it for the 5 biggest moments only |
| Karaoke captions at the bottom: spoken word turns white + bold with a thin blue underline, words not yet spoken stay grey | Same. Active word white `#FFFFFF` Bold, underline ember, upcoming words white at 45% |
| Mid-frame two-line statement, one word in accent colour ("manual testing isn't **scalable.**") | Same: "A VM can't tell you what it **stole.**" |
| White pills stacking top-left ("Every device / Every browser / Every change"), older ones fade | Same, for stats: "30,000+ devices", "100+ countries", "7,000+ wallets" |
| Logo chips in a row (Uber, Ramp, Shopify) | Real repos tested: NestJS, Remix, Vercel, FastAPI |
| Clean white explainer scenes with UI pieces, a progress number counting up, then going **red** ("0% Progress reset") | Counter `0 → 10 / 18 fake secrets stolen` turning red (use your take's number); bars `16/16 vs 13/16` |
| Solid brand end card: logo, tagline, URL | Near-black `#0A0A0A` card, ember logo, "Run the take-home before it runs you.", URL |

**Fonts**
- Headlines: **Geist Black/Bold**, ALL CAPS, tight tracking (-2%), line height ~0.9. Fallback: Inter Black.
- Captions and statements: **Geist Medium**, with the active word in Geist Bold.
- Numbers, IPs, sources, timers: **Geist Mono**.
- Geist is free (vercel.com/font) and is already the app's font, so the video and the product match. Install it in Windows first. Newer CapCut desktop builds can also import fonts from the text panel.

**Colours:** ember `#FF6A2B` (on dark) / `#E2501A` (on light), ink `#0A0A0A`, paper `#F7F7F5`, clean green `#2F9E44`.

---

## 2. Effects, and how to build each in CapCut

| ID | Effect | How |
| --- | --- | --- |
| **E1** | Text behind the person | Duplicate the face clip onto the track above. On the top copy: Remove background (auto). Put the text layer on a track between the two copies. Pop the text in with a 6-frame scale from 110% to 100%. |
| **E2** | Karaoke captions | Auto captions, then a word-highlight template. Restyle it: Geist Medium, white at 45%, active word Bold white with an ember underline. Keep 1–2 lines, bottom third. |
| **E3** | Stat pills | Rounded rectangle (white, radius max) with black Geist Medium text, top-left. Each new pill slides in from the left over 6 frames; the older ones drop to 60% opacity. |
| **E4** | **Article, documentary style (new)** | Screenshot the article. Put it on `#0A0A0A` at -1° rotation with a soft shadow. Slow push-in: keyframe scale 100% → 108% over the shot (Ken Burns). Dim the rest of the page: duplicate it, blur the bottom copy, and mask the top copy to the line you want. Then a **highlighter sweep** over the number: an ember rectangle at 55% opacity, blend Multiply, mask wiping left to right over 8 frames. Then a hard zoom (punch-in to 160% over 4 frames) on the number. Source and date go in the bottom-left in Geist Mono, 60% white. Add a 10% film-grain overlay. |
| **E5** | Slow motion | Speed → Curve → custom ramp: 1x → 0.35x on the key moment → back to 1x. Turn on smooth slow-mo (optical flow). Face shots slow down much better if you **film at 60 fps**. |
| **E6** | Fast motion | 8x–16x on waiting parts (VM boot, npm install). Keep the app's own timer visible and put a small `8×` tag in the corner (Geist Mono), so nobody thinks the timing is fake. |
| **E7** | Counter going red | A big Geist Mono number on the paper background counts up (keyframe the text or use a counter template). At the final value it turns ember with a 2-frame shake and a short low hit on the audio. |
| **E8** | Freeze + desaturate | Freeze frame on a key line, saturation -60, slow 3% zoom, then unfreeze. Use it on the Binance quote and the MALICIOUS verdict. |

**Sound:** a low drone bed under the cold open and the theft, soft whooshes on punch-ins, a tick per count in E7, music ducked under the voice. Leave a 0.5 s silence just before "MALICIOUS".

---

## 3. Shot-by-shot script

Spoken lines are written the way you'd say them. Don't read them word for word; keep the numbers exact.

### 0:00–0:12 · Cold open: Binance  ·  `ART` + `VO`
- **ART (E4):** BleepingComputer, 3 Nov 2026: Binance article. Highlight **"$6.3 billion"**, then **"fake job interview"**, then the endpoint-security quote. **E8** freeze on the quote.
- **VO:**
  > "On October 29th, about six point three billion dollars was stolen from Binance. *(beat)* It started with a fake recruiter… and a coding assignment. And Binance says its security tools never even saw the malware."

### 0:12–0:18 · The hook  ·  `FRONT`
- **E1** headline behind you: **ONE TAKE-HOME. $6.3B.**
  > "The biggest crypto theft yet. It started with a take-home test."

### 0:18–0:40 · How big this is  ·  `SIDE` cut with fast `ART` shots (1.5–2 s each)
- **E3** pills stack while you talk: `30,000+ devices` · `100+ countries` · `7,000+ wallets drained`
- **ART** quick cuts, each with a highlighter sweep:
  1. BleepingComputer (WaterPlum advisory, 18 Sep 2026): **30,000**
  2. BleepingComputer (DMM Bitcoin): **$308 million**
  3. Elastic Security Labs (Jul 2026): **zero** detections
  4. Trend Micro (Mar 2026): **750+** repos
  > "It's a North Korean campaign called Contagious Interview. A 'recruiter' sends you a repo. You run npm start, or you just open the folder in VS Code, and your keys, your wallets, your passwords are gone. More than thirty thousand devices. A hundred countries. And antivirus doesn't help. Elastic found one version with zero detections."

### 0:40–0:55 · The gap  ·  `FRONT`
- **ART** (2 s): FBI IC3 PSA, highlight **"insist on using a virtual machine"**.
- Then a **mid-frame statement** over you: "A VM can't tell you / what it **stole.**"
  > "The FBI's advice is: use a virtual machine. And that keeps you safe. But it doesn't tell you anything. Was it malware? What did it take? Who do you warn? You have no idea."

### 0:55–1:05 · Burner  ·  `SIDE` → logo sting
- 1 s logo sting (dark card, ember logo).
  > "So I built Burner. You paste the recruiter's message, and a throwaway Vultr VM full of fake secrets runs the repo before you do, and shows you exactly what it tried to steal."

### 1:05–1:25 · Paste the message  ·  `VO` + screen
- Live app (real scan, not mock). Paste the DM, press **Burn it**. Zoom on the pre-check card and the red flags as they appear.
  > "I paste the message. The AI on Vultr Serverless Inference pulls out the repo link and the red flags: Telegram, a deadline, crypto, 'run it before the call'."
  - Say the red-flag count and lure score that are **actually on screen** in your take.

### 1:25–1:50 · A brand-new VM  ·  `VO` + screen + white card
- **E6** fast motion (8×) on the progress card, split with the Vultr console where the new `burner-…` instance appears.
- White explainer card: 18 bait chips pop in one by one (AWS key, SSH key, GitHub token, npm token, Stripe key, OpenAI key, DB password, Solana, Exodus, MetaMask, seed phrase, Chrome passwords, env token, shell history, Hugging Face token, Claude Desktop MCP key, Cursor MCP key…).
  > "Burner asks Vultr for a brand-new machine, just for this one repo. Inside, the repo runs in a gVisor sandbox, and the home folder is full of fake secrets. AWS keys, an SSH key, wallets, browser passwords, even the keys your AI tools keep. Eighteen of them, random, made just for this scan. The internet is fake too. Everything gets recorded, and nothing gets out."
  > "And this is only possible because of Vultr. A fresh VM for every single scan, made and deleted through the API, for a fifth of a cent. The AI runs on Vultr Serverless Inference, and the evidence is saved on Vultr Object Storage, so the proof stays even after the machine is gone."

### 1:50–2:20 · The theft  ·  `VO` + screen, **slow motion**
- **E5** ramp into the step `npm run start`, then the red **MALICIOUS** card. **E8** freeze on it.
- Open the captured upload and highlight the fake `AKIA…` key (E4 highlighter on the screen recording).
- **E7** counter on paper: `0 → N / 18` fake secrets stolen (N = the count on your screen), turning ember.
  > "Now watch npm start. *(beat)* It opens the AWS keys, the SSH key, the wallets… and uploads them to a server on port 1224. Same port the real BeaverTail malware uses. Ten of my eighteen fake secrets, gone, in seconds. *(say the number on your screen)* And it sent a second copy over HTTPS, which Burner decrypted too."

### 2:20–2:30 · Rules, not AI  ·  `FRONT`
- **E1** headline: **RULES DECIDE.**
  > "The verdict doesn't come from the AI. It's fixed rules: a secret was read, and the same secret was seen leaving. I even hid a prompt injection in a README telling it to say 'safe'. It still said malicious."

### 2:30–2:45 · Containment  ·  `VO` + Vultr console
- Show "VM destroyed" in the app, then refresh the Vultr console: the instance is gone. **Don't cut this shot.** Click **Check with Vultr now** (the 404 lands), then zoom on the **What Vultr did** card (Cloud Compute seconds, each Serverless Inference call, the Object Storage bundle, the total). Then **E1** on the front cam: **0 PACKETS OUT.**
  > "Then the whole VM is destroyed. Refresh Vultr: gone. That machine lived about ninety-five seconds *(say the number on your screen)*, and Vultr's own API confirms it's gone. The **What Vultr did** card shows the whole scan: the machine, the AI, the evidence, a fifth of a cent. And every escape I tried from inside, the real internet, cloud metadata, the host, root, got nothing."

### 2:45–2:57 · Not just take-homes  ·  `VO` + screen + `ART`
- **ART (E4, 2 s):** BleepingComputer, FakeGit (Jul 2026): highlight **"7,600"** and the MCP-server line.
- Screen, **E6** fast motion: Sample → **Fake MCP server** → Burn it → **MALICIOUS**. Zoom on the stolen **MCP server token (Claude Desktop config)** and the line **"Modified ~/.config/Claude/claude_desktop_config.json to run again later"**.
- **E3** pill: `800+ fake MCP servers`.
  > "And it's not just take-homes. This year, more than eight hundred fake MCP servers showed up on GitHub. Burn one: it steals the keys your AI tools hold, and adds itself to Claude Desktop. GitHub doesn't scan for this. Burner runs it first. Same for a Hugging Face model or a VS Code extension: paste the link."

### 2:57–3:15 · Does it hold up?  ·  `SIDE` + white cards
- Card 1: bars animating, **Burner 16/16 · GuardDog 13/16**, and false alarms **0/11 vs 1/11**. GuardDog's three misses labelled "time bomb", "obfuscated" and "hex-eval loader".
- Card 2: logo chips for the real repos (NestJS, Remix, Vercel, FastAPI) and the big number **0 / 21 false alarms**.
  > "Does it actually work? I built sixteen attack samples from real threat reports. Burner caught all sixteen. GuardDog, a static scanner, caught thirteen. It missed the time bomb, the obfuscated one and the hex-eval loader. Zero false alarms on the clean ones. Then I ran it on twenty-one real public repos, NestJS, Remix, FastAPI. Zero false alarms. To be fair, one pm2 rule needed a fix first, and that's written down in the repo."

### 3:15–3:25 · Close  ·  `FRONT` → end card
  > "The FBI said use a VM. Burner is that VM, but it tells you what the repo tried to steal. It's live right now. Paste the message before you run the repo."
- End card: `#0A0A0A`, ember logo, **Run the take-home before it runs you.**, `139-84-215-1.sslip.io` and `github.com/Maheswar-Sah00/burner` in Geist Mono. Hold for 3 s.

---

## 4. Articles to capture

Screenshot each at 125–150% browser zoom with the outlet's name, the headline and the date in frame. **Highlight the words as they appear on the page.** The phrases below come from the README and may be worded slightly differently in the article.

| # | Outlet / date | Highlight | Link |
| --- | --- | --- | --- |
| A1 | BleepingComputer, 3 Nov 2026 | $6.3 billion · fake job interview · not detected by endpoint security | https://www.bleepingcomputer.com/news/security/binance-says-fake-job-interview-led-to-63-billion-crypto-heist/ |
| A2 | BleepingComputer, Sep 2026 | 30,000 devices | https://www.bleepingcomputer.com/news/security/north-korean-waterplum-hackers-infected-30-000-devices-worldwide/ |
| A3 | BleepingComputer | $308 million (DMM Bitcoin) | https://www.bleepingcomputer.com/news/security/fbi-links-north-korean-hackers-to-308-million-crypto-heist |
| A4 | Elastic Security Labs, Jul 2026 | zero detections · npm start | https://www.elastic.co/security-labs/threat-command/contagious-interview-malware-svg-steganography |
| A5 | Trend Micro, Mar 2026 | 750+ repos · 500+ folderOpen tasks | https://www.trendmicro.com/en_gb/research/26/d/void-dokkaebi-uses-fake-job-interview-lure-to-spread-malware-via-code-repositories.html |
| A6 | FBI IC3 PSA, 3 Sep 2024 | insist on using a virtual machine | https://www.ic3.gov/PSA/2024/PSA240903 |
| A7 | BleepingComputer, Jul 2026 | 7,600 GitHub repos · MCP servers | https://bleepingcomputer.com/news/security/fakegit-campaign-uses-7-600-github-repos-to-push-smartloader-malware |

---

## 5. Every number you say, and where it comes from

| Said in the video | Source in the repo |
| --- | --- |
| 16/16 caught, 0/11 false alarms; GuardDog 13/16, 1/11 | `reports/benchmark/results.md` |
| GuardDog missed the time bomb (m06) and the obfuscated loader (m12) | same |
| 0/21 false alarms on real repos, after one pm2 fix | `reports/benchmark/real-repos.md` |
| 10 kinds of fake secret to port 1224, VM alive 95 s, $0.0023 whole scan | README §4.3 (case `efafff21e7`, v5, before the 3 AI-tool secrets were added) |
| 800+ fake MCP servers / AI skills on GitHub | FakeGit, Island, Jul 2026 (README §1.1) |
| Fake MCP server sample: MALICIOUS, MCP keys taken, Claude Desktop config modified | README §4.5 (`reports/benchmark/runs/beyond`) |
| Prompt-injected README, verdict stayed MALICIOUS | README §6.7, `reports/benchmark/containment.json` |
| 0 packets out | `containment.json` (iptables counter) |

If your live take shows different numbers (VM lifetime, cost, secrets stolen), **say the numbers on your screen**, not these.

---

## 6. Recording checklist

- [ ] FRONT and SIDE (about 45°) on the same takes, or record each line twice. **60 fps** so the slow motion is smooth.
- [ ] Lav or close mic. VO recorded in the same room so the sound matches.
- [ ] Screen at 1920×1080. **Real scan on the live app** (not `BURNER_MOCK`), with the LLM on.
- [ ] Vultr console in a second tab, filtered to the `burner-scan` tag. Capture the instance appearing, then gone after a refresh.
- [ ] Clean take-home scan as a 3 s cutaway (the green result).
- [ ] Never show `.env`, API keys or the Vultr account ID.
- [ ] Export 1080p, 30 fps, H.264. Burn the captions in.
