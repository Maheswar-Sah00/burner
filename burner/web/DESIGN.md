# Burner UI v4 — Maritime-style "pixel burn chamber"

Reference: https://maritime.sh (a YC sandbox-infra company — same domain as Burner: sandboxes / throwaway VMs). The user wants that **visual language** — pure black, framed hero over a halftone dot field, centered grotesk headline, white near-square buttons, dither/pixel-dot isometric illustrations inside hairline grid cells, floating nav that docks on scroll, giant dithered pixel display text — applied to Burner, keeping Burner's theme (ember = something stolen/burning) and **only the components Burner needs**. Similar, not a copy: no "Backed by YC", no customer-logo marquee, no pricing page, no add-ons carousel, no "copy instructions for your agent" button.

## Type (same fonts as maritime.sh)
- **Geist** (300–700) — everything: headlines (500, tracking −0.035em, line-height 1.02), body, UI.
- **Geist Mono** (400/500) — code, paths, IPs, timers, micro-labels.
- **Geist Pixel** (`--font-pixel`, self-hosted at /static/vendor/fonts, OFL) — used like Maritime's dithered "Customize your agent's computer." line: one giant pixel statement per page, stat numerals, small badges. Don't overuse.
- Tabular numerals on all numbers.

## Visual system
- Dark is default (`theme.js` now defaults to dark). Page `--bg #0a0a0a`, framed panels `--panel #000`, hairlines `--line #1f1f1f`. Light theme is a faithful mirror (white panels, black dots, black buttons).
- **Halftone / dither art** is the signature. Drawn on `<canvas>` (devicePixelRatio aware), dots on a fixed grid (≈4–6px pitch) whose size/alpha comes from a field (noise, shape SDF, or a rasterised glyph). Colours from `--dot` / `--dot-dim`, with **ember** dots marking "stolen / hot" parts. Slow drift animation (≤ 30 fps, paused off-screen / hidden tab / reduced motion → static frame).
- Shared library `static/dither.js` → `window.BurnerDither`:
  - `field(canvas, opts)` — full-bleed animated halftone field (hero background: rolling smoke/heat-haze shapes rising from below, a few ember hot-spots).
  - `icon(canvas, name, opts)` — isometric dot illustrations: `vm` (cube), `vm-burning` (cube with ember dots rising), `key`, `globe` (fake internet), `nested` (sandbox in VM), `stamp`, `shield`, `clock`, `bars`, `ash` (cube dissolving into falling dots), `laptop`. Static unless `animate:true`.
  - `text(canvas, string, opts)` — rasterises text and redraws it as dots (the giant dithered statement).
  - All re-read colours on document event `burner:theme`.
- Buttons: primary = solid `--btn` (white on dark), `--radius-btn` 6px, Geist 500, arrow `→`. Secondary = dark pill with hairline. Ember is never a big button fill — it's the burn colour, used for stolen things, the live fuse, the verdict.
- Cards: Maritime grid — cells share 1px hairlines (grid with `gap:1px; background: var(--line)` trick), no shadows, no rounded corners inside the grid, outer radius ~12px.
- Nav: full-width at top; after ~40px scroll it docks into a floating rounded bar (max ~1340px, `--glass` + backdrop blur, hairline). Logo + Burner wordmark left; How it works · Track record centered; GitHub + theme toggle + "Burn a repo →" right. Theme toggle keeps the circular reveal.
- Motion: subtle; 200–300ms; scroll reveals once; everything off under prefers-reduced-motion.

## Page plan — landing `/` (only these sections)
1. **Hero frame** (rounded 28px black panel inset 16px from viewport edges, dither field behind): small top label `Contagious Interview · fake-recruiter take-homes` (mono, ember dot), headline centered "Run the take-home / before it runs you.", one-line sub "A throwaway Vultr VM full of fake secrets runs it first — and shows you what it tried to steal.", then the **input console** (the product action — replaces Maritime's CTA pair): a wide dark rounded input area with a tiny mode switch (Message · Repo link · Sample) and a solid white "Burn it →" button; under it a quiet "or try the npm-start stealer · clean take-home" link row. Keep every existing id/aria/behaviour of the start form.
2. **"Built on"** quiet line (instead of a logo wall — honest, not customers): `Vultr Cloud Compute · Vultr Serverless Inference · Vultr Object Storage · gVisor` in grey monochrome text marks.
3. **"One VM. One repo. Then it burns."** — 3×2 hairline grid of dither-illustrated cells (Maritime "Sandboxes, desktops and phones" grid), each: illustration, title, one-sentence body, bottom row with a fact on the left (Maritime's price slot) and a link on the right:
   - Throwaway VM (`vm`) — "$0.0018 a scan"
   - 15 fake secrets (`key`) — "unique per scan"
   - Fake internet (`globe`) — "0 packets out"
   - gVisor sandbox (`nested`) — "10/10 escapes contained"
   - Runs it like you would (`laptop`) — "folder open → install → start → test → +45 days"
   - Rule-based verdict (`stamp`) — "AI explains, never decides"
4. **Showcase pair** (Maritime "Built for every kind of agent"): two big dithered-background panels each holding a realistic UI mock: LEFT = the live replay (terminal tape of a real scan — reuse/rework hero.js replay: npm start → open ~/.aws/credentials → POST 203.0.113.55:1224 ← 4 secrets → VM destroyed · 240 s · $0.0018); RIGHT = a mini report card (MALICIOUS stamp, 10/14 secrets taken, campaign match high). Captions: "**For candidates.** Paste the recruiter's message before the call. Get a verdict in about two minutes." / "**For job boards & security teams.** Get the IOCs, the evidence bundle and a ready-to-send abuse report."
5. **Proof row** (Maritime 6-cell icon row): `13/13 caught` · `0/11 false alarms` · `~91 s median` · `10/10 escapes contained` · `1 VM per scan` · `$0.0018 per scan` — small dither icon + Geist Pixel numeral + caption; links to /track. Honest footnote: "24 defanged samples we wrote · rules tuned after a baseline run · GuardDog (static) caught 11/13 with 1 false alarm."
6. **Why** — one line, two-tone like "Agents will do most…/Get yours a computer today.": "Platforms each solve a piece — open-source experiments are starting." (ink) / "Nobody has put the whole puzzle together in a candidate's hands." (grey). Never say "nobody is building this".
7. **Giant dithered pixel statement** (Maritime's "Customize your agent's computer."): "Let it burn somewhere else." drawn with `BurnerDither.text` (ember-tinted at the end), full width.
8. Footer: wordmark, one-line honesty note ("All secrets inside the sandbox are fake. Verdicts come from observed behaviour, not from an AI's opinion."), links.
Remove the tour invite chip from the hero (keep "Tour" reachable from the nav only if it still works; otherwise drop the nav link — the tour is optional).

## Run view, report, track
Same language: black frame panels, hairline grids, Geist/Geist Mono, pixel numerals for the timer and KPIs, dither icons as section marks, the fuse as a dotted pixel line that fills ember. Report keeps the verdict stamp, "what it stole" redaction bars (ember when taken), exhibits (charts), campaign match, red flags, report-it kit, burn receipt — restyled to v4. Track keeps its content restyled to the grid language with pixel numerals.

## Rules
- Don't change element ids, API calls, data shapes, routes or behaviour; all attacker-controlled strings via textContent.
- 375px phone: no horizontal scroll, 16px gutters, grids collapse to 1 column, canvases scale down (cap dpr at 2).
- AA contrast both themes; visible focus rings (ember 2px).
- Perf: canvases ≤ 30fps, pause off-screen; total new JS small; no new libraries (d3 stays for charts).
- Test: `$env:BURNER_MOCK="1"; python -m uvicorn burner.web.app:app --port <port>`; Playwright with Edge (`p.chromium.launch(channel="msedge")`, see scratchpad v3-final/e2e.py) — headless Edge CLI freezes animations. `?theme=light|dark` forces a theme. No git commits, no real scans.
