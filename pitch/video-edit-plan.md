# Burner: final video script (3:10)

**Length: 3:00–3:15.** lablab's rule book puts videos under 3 minutes in the "Limited" tier, so don't cut below 3:00.

Three kinds of shot:
- **FACE · FRONT**: you, talking straight to camera.
- **FACE · SIDE**: you at about 45°, closer and more personal.
- **NO FACE**: your voice only, over the screen recording, an article or a graphic.

The look comes from `Downloads/inspo.mp4` (big caps headlines behind you, karaoke captions, stat pills, white explainer cards), recoloured to Burner's ember. The new documentary layer is **ART**: real news articles with the numbers highlighted, plus slow motion and fast motion.

Face time is about 1:05, no-face about 2:05. The product is on screen for most of the video, which is what judges score.

---

## 1. The script

Say the lines naturally; you don't have to read them word for word. **Keep the numbers exact.** If your live take shows a different number (VM seconds, secrets stolen, cost), say the one on your screen.

### ① 0:00–0:10 · Binance  ·  NO FACE (article)
**On screen:** ART A1 (BleepingComputer, Binance). Slow push-in. The highlighter sweeps **"$6.34 billion"**, then **"download a coding assignment"**. Freeze and desaturate on **"The 0-day malware was not detected by the endpoint security protection tools at the time."**
**Say:**
> "On October 29th, about six point three billion dollars was stolen from Binance. It started with a fake recruiter… and a coding assignment. And Binance says its security tools never saw it."

### ② 0:10–0:16 · The hook  ·  FACE · FRONT
**On screen:** Headline behind you: **ONE TAKE-HOME. $6.3B.**
**Say:**
> "The biggest crypto theft yet. And it started with a take-home test."

### ③ 0:16–0:34 · How big this is  ·  FACE · SIDE, with two 1.5 s article flashes
**On screen:** Stat pills stack top-left while you talk: `30,000+ devices` · `100+ countries` · `7,000+ wallets`.
Flash ART A2 (highlight **"at least 30,000 devices in more than 100 countries"**), then ART A4 (highlight **"zero detections"**).
**Say:**
> "It's a North Korean campaign called Contagious Interview. A fake recruiter sends you a repo. You run npm start, or you just open the folder in VS Code, and your keys, your wallets, your passwords are gone. Thirty thousand devices. A hundred countries. And antivirus? One version had zero detections."

### ④ 0:34–0:46 · The gap  ·  FACE · FRONT, with a 2 s article flash
**On screen:** Flash ART A6 (FBI), highlight **"insist on using a virtual machine"**. Then a mid-frame statement over you: *A VM can't tell you* / *what it* **stole.**
**Say:**
> "The FBI says: use a virtual machine. Fine, that keeps you safe. But it tells you nothing. Was it malware? What did it take? You have no idea."

### ⑤ 0:46–0:54 · Burner  ·  FACE · SIDE → 1 s logo sting
**Say:**
> "So I built Burner. Paste the recruiter's message, and a throwaway Vultr VM runs the code before you do, and shows you what it tried to steal."

### ⑥ 0:54–1:08 · Paste the message  ·  NO FACE (screen)
**On screen:** The live app. Paste `samples/recruiter-message.txt`, click **Burn it**. Eased zoom on the pre-check card and the red flags appearing one by one.
**Say:**
> "I paste the message. The AI on Vultr Serverless Inference finds the repo and the red flags. Telegram, a deadline, crypto, 'run it before the call'."

### ⑦ 1:08–1:28 · A brand-new VM  ·  NO FACE (screen, **fast motion 8×**)
**On screen:** Split screen. Left: the progress card. Right: the Vultr console, where a new `burner-…` instance appears. Keep the timer visible, with an `8×` tag in the corner. Then a white card with 18 bait chips popping in (AWS key, SSH key, wallets, Chrome passwords, Claude Desktop MCP key, Cursor MCP key…).
**Say:**
> "Burner asks Vultr for a brand-new machine, just for this one repo. Inside, the code runs in a sandbox, on a laptop full of fake secrets. Eighteen of them, AWS keys, SSH, wallets, even your AI tools' keys, made fresh for this scan. And the internet is fake too. Nothing gets out."

### ⑧ 1:28–1:56 · The theft  ·  NO FACE (screen, **slow motion**)
**On screen:** Speed ramp down (0.35×) as `npm run start` ticks. 0.5 s of silence, then the red **MALICIOUS** card, frozen and desaturated. Scroll **What it stole**, open the captured upload, and run the highlighter over `aws_access_key_id = AKIA…`. Then a white card: counter `0 → N` fake secrets stolen, turning ember.
**Say:**
> "Now watch npm start. *(beat)* It opens the AWS keys, the SSH key, the wallets… and uploads them to a server on port 1224. That's the same pattern as the real BeaverTail malware. That's the fake key I planted, arriving at the attacker."

### ⑨ 1:56–2:06 · Rules decide  ·  FACE · FRONT
**On screen:** Headline behind you: **RULES DECIDE.**
**Say:**
> "And the verdict isn't the AI's opinion. It's fixed rules. I even hid a message in a README telling it to say 'safe'. It still said malicious."

### ⑩ 2:06–2:24 · Gone, and what Vultr did  ·  NO FACE (screen)
**On screen:** "VM destroyed" in the app. Refresh the Vultr console: the instance is gone. **Don't cut this shot.** Click **Check with Vultr now**: the 404 lands. Zoom on the **What Vultr did** card (Cloud Compute seconds, each AI call, the Object Storage bundle, the total).
**Say:**
> "Then the whole VM is destroyed. Refresh Vultr: gone, and Vultr's own API confirms it. This card shows everything Vultr did for this scan: the machine, the AI, the evidence. About a fifth of a cent. Without throwaway VMs like this, Burner couldn't exist."

### ⑪ 2:24–2:40 · Not just take-homes  ·  NO FACE (article + screen, fast motion)
**On screen:** ART A7 (FakeGit), highlight **"Over 800 repositories pretended to be AI skills or MCP servers"**. Then Sample → **Fake MCP server** → Burn it at 8× → **MALICIOUS**. Zoom on **"Modified ~/.config/Claude/claude_desktop_config.json to run again later"**.
**Say:**
> "And it's not just take-homes. This year, more than eight hundred fake MCP servers showed up on GitHub. Burner runs one, and catches it stealing your AI keys and adding itself to Claude Desktop. Same for Hugging Face models and VS Code extensions."

### ⑫ 2:40–2:58 · Does it hold up?  ·  FACE · SIDE, with white cards
**On screen:** Card 1: bars animating, **Burner 16/16 · GuardDog 13/16**, with false alarms **0/11 vs 1/11**. Card 2: logo chips (NestJS, Remix, Vercel, FastAPI) and the big number **0 / 21**. Then a 2 s clip of the clean sample coming back green.
**Say:**
> "Does it actually work? Sixteen attack samples, built from real threat reports. Burner caught all sixteen. A static scanner caught thirteen. Zero false alarms on the clean ones. And on twenty-one real public repos, zero false alarms."

### ⑬ 2:58–3:10 · Close  ·  FACE · FRONT → end card
**Say:**
> "The FBI said use a VM. Burner is that VM, but it tells you what the code tried to steal. It's live right now. Paste the message before you run the repo."

**End card** (hold 3 s): near-black, ember logo, **Run the take-home before it runs you.**, then `139-84-215-1.sslip.io` and `github.com/Maheswar-Sah00/burner` in Geist Mono.

---

## 2. Article research (checked 6 Nov 2026)

I opened every article and copied the exact words to highlight. **Highlight these words exactly.** They are what the page says.

| # | Article | Date | Highlight exactly | Use in |
| --- | --- | --- | --- | --- |
| **A1** | BleepingComputer: *"Binance says fake job interview led to $6.3 billion crypto heist"* (Lawrence Abrams) | 3 Nov 2026 | "steal about $6.34 billion in digital assets" · "instructed to download a coding assignment from an online code repository" · "The 0-day malware was not detected by the endpoint security protection tools at the time." | ① |
| **A2** | BleepingComputer: *"North Korean WaterPlum hackers infected 30,000 devices worldwide"* | 19 Sep 2026 | "infected at least 30,000 devices in more than 100 countries" · "over 7,000 cryptocurrency wallets" | ③ |
| **A4** | Elastic Security Labs: *"New North Korean campaign uses fake coding interviews to steal developer credentials"* | 18 Jul 2026 | "have zero detections and are not flagged by any AV vendors" (subtitle: "Not one antivirus vendor caught it.") | ③ |
| **A6** | FBI IC3 PSA: *"North Korea Aggressively Targeting Crypto Industry with Well-Disguised Social Engineering Attacks"* | 3 Sep 2024 | "If a pre-employment test requires code execution, insist on using a virtual machine" | ④ |
| **A7** | BleepingComputer: *"FakeGit campaign uses 7,600 GitHub repos to push SmartLoader malware"* | 21 Jul 2026 | "Over 800 repositories pretended to be AI skills or MCP servers" | ⑪ |

Spare articles, if you want more documentary cutaways:

| # | Article | Date | Highlight exactly |
| --- | --- | --- | --- |
| A3 | BleepingComputer: *"FBI links North Korean hackers to $308 million crypto heist"* | 24 Dec 2024 | "pretended to be a legitimate recruiter on LinkedIn" · "a pre-employment test on GitHub" · "$308 million" |
| A5 | Trend Micro: *"Void Dokkaebi Uses Fake Job Interview Lure to Spread Malware via Code Repositories"* | 21 Apr 2026 | "more than 750 infected repositories, over 500 malicious VS Code task configurations" |

Links:
- A1 https://www.bleepingcomputer.com/news/security/binance-says-fake-job-interview-led-to-63-billion-crypto-heist/
- A2 https://www.bleepingcomputer.com/news/security/north-korean-waterplum-hackers-infected-30-000-devices-worldwide/
- A3 https://www.bleepingcomputer.com/news/security/fbi-links-north-korean-hackers-to-308-million-crypto-heist
- A4 https://www.elastic.co/security-labs/threat-command/contagious-interview-malware-svg-steganography
- A5 https://www.trendmicro.com/en_gb/research/26/d/void-dokkaebi-uses-fake-job-interview-lure-to-spread-malware-via-code-repositories.html
- A6 https://www.ic3.gov/PSA/2024/PSA240903
- A7 https://bleepingcomputer.com/news/security/fakegit-campaign-uses-7-600-github-repos-to-push-smartloader-malware

What the research changed:
- Binance says **$6.34B**. Saying "about six point three billion" is accurate.
- The 30,000-devices advisory came from **Japan, the US, Australia and Germany**. If you name them, say "four countries".
- The Trend Micro article is dated **21 Apr 2026**; the analysis was done in March.
- The FBI line continues "…on a non-company connected device". Cutting the highlight after "virtual machine" is fine.

**How to capture:** screenshot at 125–150% browser zoom, with the outlet's logo, the headline and the date in frame. Close cookie banners and ads first.

---

## 3. Style and effects (from inspo.mp4)

**Fonts:** Geist Black/Bold for ALL-CAPS headlines (tracking -2%), Geist Medium for captions, Geist Mono for numbers, URLs and sources. Fallback: Inter.
**Colours:** ember `#FF6A2B` (on dark) / `#E2501A` (on light), ink `#0A0A0A`, paper `#F7F7F5`, clean green `#2F9E44`.

| Effect | Where | How in CapCut |
| --- | --- | --- |
| Text behind you | ② ⑨ | Duplicate the face clip on the track above → Remove background on the top copy → text layer between the two. Pop in 110% → 100% over 6 frames. |
| Karaoke captions | whole video | Auto captions → word-highlight template. Upcoming words white at 45%, active word bold white with an ember underline. |
| Stat pills | ③ ⑪ | White rounded rectangles, black text, top-left. Slide in over 6 frames; older pills drop to 60%. |
| **Article, documentary style** | ① ③ ④ ⑪ | Screenshot on near-black, rotated -1°, soft shadow. Push in 100% → 108%. Blur everything except the target line. Ember highlighter (55%, Multiply) wipes left to right over 8 frames, then punch in to 160% on the number. Source and date bottom-left in Geist Mono. 10% film grain. |
| Slow motion | ⑧ (and face beats in ② ⑨) | Speed curve 1× → 0.35× → 1×, smooth slow-mo on. Film the face shots at 60 fps. |
| Fast motion | ⑦ ⑪ | 8×, timer visible, `8×` tag in the corner, so the timing stays honest. |
| Freeze + desaturate | ① ⑧ | Freeze frame, saturation -60, 3% slow zoom. |
| Counter going red | ⑧ | Big Geist Mono number counts up, turns ember on the last value, 2-frame shake and a low hit. |

**Sound:** a dark synth bed ducked about 12 dB under your voice. It lifts at MALICIOUS ⑧, resolves when the VM disappears ⑩, and lifts again for the MCP hit ⑪. Whoosh on every punch-in, a tick per counter step, and 0.5 s of silence before MALICIOUS.

---

## 4. Every number you say, and where it comes from

| In the video | Source |
| --- | --- |
| $6.3B Binance, coding assignment, endpoint tools missed it | A1 |
| 30,000 devices, 100 countries, 7,000 wallets | A2 |
| Zero antivirus detections | A4 |
| "Use a virtual machine" | A6 |
| 800+ fake MCP servers / AI skills | A7 |
| 18 fake secrets | README "At a glance" |
| Port 1224, VM alive 95 s, 404 after delete, $0.0023 | README §4.3 (case `efafff21e7`) |
| 16/16 vs GuardDog 13/16; 0/11 vs 1/11 | `reports/benchmark/results.md` |
| 0/21 false alarms on real repos | `reports/benchmark/real-repos.md` |
| Fake MCP server caught editing the Claude Desktop config | README §4.5 |
| Prompt injection, verdict stayed MALICIOUS | README §6.7 |

---

## 5. Recording checklist

**Face (FRONT + SIDE)**
- [ ] Shots ② ④ ⑨ ⑬ facing the front camera, ③ ⑤ ⑫ on the 45° side camera. With one camera, record each line twice.
- [ ] 60 fps, lav or close mic, the same room as your VO.
- [ ] Leave about 30% of empty space above your head in ② and ⑨ for the text-behind-you headline.

**No face (screen + VO)**
- [ ] 1920×1080, **real scan on the live app** (not mock), AI on.
- [ ] Vultr console in a second tab, filtered to the `burner-scan` tag: the instance appearing, then gone after a refresh.
- [ ] "Check with Vultr now" (the 404) and the **What Vultr did** card.
- [ ] Fake MCP server sample → MALICIOUS, with the Claude Desktop line visible.
- [ ] Clean take-home sample coming back green (2 s).
- [ ] Never show `.env`, API keys or the Vultr account ID.

**Articles**
- [ ] A1, A2, A4, A6, A7 captured (A3, A5 optional).

**Export:** 1080p, 30 fps, H.264, captions burned in, 3:00–3:15.
