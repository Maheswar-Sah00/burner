# Burner UI v3 — "Burn chamber" design brief

Babel was the *quality bar*, not the template. v3 must not look like Babel (no centered serif hero over a dotted world map, no blue SaaS accent, no Babel tabs-in-a-card clone). Burner gets its own identity.

## Concept
An **incident dossier from a burn chamber**. Everything Burner shows is *evidence* from something that was detonated somewhere else and then destroyed. Visual grammar:
- **Case-file labels**: tiny mono uppercase micro-labels with tracking (`CASE 7F3A · BLR · VC2-2C-4GB`, `EXHIBIT 03`, `T+42.1s`). Section numbering `01 — Paste`, `02 — Detonate`, `03 — Read the evidence`.
- **Ember heat** is the only brand colour. A heat gradient (`--heat`: amber → ember → crimson) is used sparingly: primary button, the live fuse, the verdict stamp, the "stolen" state. Everything else is ink on paper / soot.
- **Redaction bars**: fake secrets render as solid ink bars (█████) with the secret's name in mono; when stolen they "burn" — the bar turns heat-gradient, chars flicker away, revealing destination. Untouched ones stay cold/grey.
- **Rubber-stamp verdict**: the report header carries a rotated (−4°) double-outline stamp, `MALICIOUS` (crimson), `SUSPICIOUS` (amber), `NOTHING OBSERVED` (ink/green). Slight ink-texture via SVG noise mask. It "thunks" in (scale 1.3→1, 220ms) unless reduced motion.
- **The fuse**: run progress is a single horizontal line that burns left→right through the phase markers with a glowing spark at its head; when "VM destroyed" happens the fuse ends in a small ash puff and the timer freezes. That's the signature moment.
- **Hairlines over shadows**: 1px rules, paper-like cards, very soft shadows only on floating things (tooltips, menus, the stamp).
- **Grain**: a fixed, pointer-events:none SVG-noise overlay at ~3–4% opacity (dark) / 2.5% (light). Must not tank perf (use one tiny inline SVG data URI, background-repeat).
- **Asymmetric editorial layout**: left-aligned hero, 12-col grid, generous whitespace, large tabular numerals for stats.

## Type (keep the same fonts as before)
- Display: **Newsreader** (opsz) — headlines, big numerals, italic for emphasis (`<em>`), e.g. "Run the take-home *before it runs you.*"
- UI/body: **Figtree** 400/500/600/700.
- Evidence/labels/code: **JetBrains Mono** 400/500 (add to the one Google Fonts link). Only for micro-labels, paths, IPs, secrets, code, timers.
- Numerals: `font-variant-numeric: tabular-nums` on all stats/timers.
- Scale: hero 76–104px clamp, h2 40–52px, section micro-label 11px/0.14em tracking.

## Tokens (defined once in `static/tokens.css`; every other stylesheet uses them)
See tokens.css. Light = **Bone**, dark = **Soot**. Keep the legacy variable names used by charts.css/hero.js/app.js (`--bg --surface --surface-2 --ink --ink-2 --ink-3 --line --line-2 --ok* --warn* --bad* --fake* --llm* --ember --accent --font-*` etc.) mapped onto the new palette so nothing breaks; then restyle.

## Motion
- 180–260ms, `cubic-bezier(.2,.7,.1,1)`. Staggered reveals on scroll (IntersectionObserver, once). Everything off under `prefers-reduced-motion`.
- Theme switch: keep the circular view-transition reveal in theme.js.

## Pages
1. **Landing `/`**
   - Nav: wordmark (flame-in-a-box glyph + "Burner" in Newsreader), links (How it works · Track record · Tour), GitHub, theme toggle, CTA. Thin, sticky, blurs on scroll.
   - Hero, two columns: LEFT = micro-label `CONTAGIOUS INTERVIEW · 2023–2026`, headline, one-paragraph sub, the input console (see below), trust line. RIGHT = **the chamber**: a tall card showing a looping, scripted replay of a real scan (use data from mock_report.json shape, hard-coded in hero.js): a mono "tape" of events scrolling (`T+00.4 clone github.com/…` → `T+31.2 npm start` → `T+33.0 open ~/.aws/credentials` → `T+33.4 POST 203.0.113.55:1224/uploads ← AWS key, GitHub token` → `captured by fake internet`), a column of redaction-bar secrets that burn as they're taken, and at the end `VM DESTROYED · 240 s · $0.0018` then it resets. Pause on hover; static final frame under reduced motion.
   - Input console: not Babel's pill tabs — a segmented "mode" switch rendered like a dossier tab strip (Recruiter message / Repo link / Sample), a large textarea, and a heat-gradient "Burn it" button with a tiny spark on hover. Keep all existing ids/behaviour.
   - Proof strip: 4 big numerals with mono captions — `13/13` caught · `0/11` false alarms · `~91 s` median scan · `10/10` escapes contained — linking to /track.
   - "How it works" as a 3-step horizontal diagram (01 Paste → 02 Detonate in a throwaway Vultr VM → 03 Evidence, then the VM is destroyed), with the puzzle line somewhere honest: "Platforms each solve a piece… nobody has put the whole puzzle together in a candidate's hands."
2. **Run `/` (live)**: dossier header (`CASE <id> · LIVE`, title, timer in big mono tabular), **the fuse** across the phases, current phase detail card, live event tape (mono, newest first, coloured lane dots), "VM destroyed" moment.
3. **Report `/r/{id}`**: stamp verdict + headline in Newsreader; KPI row as big numerals with hairline dividers (not boxed tiles); "What it stole" as redaction bars burned open; the charts panel (timeline, flow, bait board) inside a quiet framed "Exhibit" panel with mono exhibit labels; campaign match as a sourced indicator list; recruiter red flags; "Report it" kit; evidence download. Print stylesheet stays.
4. **Track `/track`**: "Case log". Headline numbers huge; Burner vs GuardDog score bars; the matrix as a ledger; scan-time strip; containment table with mono result tags; honest caveat in a margin note.

## Rules
- Don't change any element id, API call, data shape, route or behaviour in app.js — restyle and restructure markup only. All attacker-controlled strings via textContent (as now).
- Phone width 375px: no horizontal scroll, 16px gutters, hero stacks (chamber below the console, shortened).
- Contrast AA in both themes. Focus rings visible (ember 2px).
- No new JS libraries. d3 stays for charts.
- Test with `BURNER_MOCK=1 python -m uvicorn burner.web.app:app --port <port>` and headless Edge screenshots in both themes (`--force-dark-mode` or set localStorage via a `?theme=dark` param if theme.js supports it — add that param support if missing). No git commits, no real scans.
