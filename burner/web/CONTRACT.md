# Burner UI v2 — shared contract (three parallel builders)

Design reference: the user's own project **Babel** — copied to `design-ref/babel-web/` (index.html + static/*.css/js, incl. `static/theme.js` circular theme reveal, `static/tour.js`, `static/charts.js`, `static/vendor/d3.min.js` (ISC)) and screenshots in `design-ref/babel-screenshots/` (01-start, 05-working-live, 06-plan-map, 12-report, 13-track-record, 17-tour, 19/20 dark). Reuse its design system closely: tokens (light `--bg #f1f6f6`, white surfaces, blue `#2d6cf3`; dark = monochrome greys, white buttons, only red/amber/green/orange keep hue), Newsreader (display serif) + Figtree (body) from Google Fonts, 16px radius cards, soft shadows, chips/badges, pill tabs, the live-run checklist, KPI tiles, legend chips that filter charts, guided tour, circular view-transition theme toggle. Adapt — don't paste Babel's content.

## File ownership (do not edit files you don't own)
| Owner | Files |
|---|---|
| **UI agent** | `burner/web/static/index.html`, `static/app.css`, `static/app.js`, `static/theme.js`, `static/tour.js`, `static/tour.css`, `static/hero.js`, `static/favicon.svg` |
| **Charts agent** | `burner/web/static/charts.js`, `static/charts.css`, `static/vendor/d3.min.js` (+ LICENSE), `burner/web/static/charts-demo.html` (dev page) |
| **Data agent** | `burner/web/app.py`, `burner/control/trace.py` (new), the call site in `burner/control/scan.py` (one line), `burner/web/mock_report.json`, `mock_report_clean.json`, `reports/benchmark/containment.json`, `burner/web/bench.json` |

Static files are served by app.py at `/static/...` (data agent adds the mount). Pages: `/` (scan), `/r/{id}` (result), `/track` (benchmark & containment "track record" page) — all serve index.html; app.js routes by path.

## Report additions (data agent produces; UI + charts consume)
`report.trace`:
```json
{"duration": 98.4,
 "steps": [{"name": "npm run start", "t0": 2.1, "t1": 47.2, "rc": 137, "sandbox_died": false}],
 "events": [{"t": 3.42, "lane": "secrets|files|processes|network|exfil|dns",
             "label": "~/.aws/credentials", "detail": "opened by node", "severity": "critical|high|medium|low|info",
             "step": "npm run start"}]}
```
Times are seconds relative to the first step's start. ≤ 400 events (dedupe repeated opens of the same file by the same process within 1 s). Lanes: `secrets` = open of a planted bait file, `files` = other writes outside the project / persistence, `processes` = execve (non-trivial: skip bash/sh/node startup noise, keep curl/wget/python/etc. and anything flagged), `network` = TCP connection captured by the fake internet, `dns` = DNS query, `exfil` = a request that carried a fake secret (label = destination, detail = secrets).

`report.flows` (theft graph, for a Sankey/flow chart):
```json
{"nodes": [{"id": "s:AWS access key", "label": "AWS access key", "kind": "secret", "taken": true},
           {"id": "p:node", "label": "node", "kind": "process"},
           {"id": "d:203.0.113.55:1224", "label": "203.0.113.55:1224", "kind": "destination", "raw_ip": true}],
 "links": [{"source": "s:AWS access key", "target": "p:node", "kind": "read"},
           {"source": "p:node", "target": "d:203.0.113.55:1224", "kind": "sent", "secrets": ["AWS access key"], "bytes": 4210}]}
```
Every planted bait appears as a secret node (`taken` false if never sent). 

Existing report fields stay as they are (verdict, headline, explanation, findings, stolen, network, dns, steps, bait, recruiter, readme_screen, vm, evidence, campaign, abuse_kit, llm_usage, total_secs, target).

Added 4 Nov (all optional; old reports lack them):
- `verdict` may also be `"INCONCLUSIVE"`: nothing ran (no runnable steps, or every step exited 126/127), so "nothing observed" would be a lie. Render amber with the word "Inconclusive", never the green "nothing observed". If nothing was runnable, no VM is rented and `vm` is `null`.
- `llm_usage.by_call`: `[{"role": "read_message|screen|plan|explain", "model", "prompt_tokens", "completion_tokens", "secs"}]`. Usage is per scan (it used to be a process-wide running total).
- `llm_errors`: `[{"step", "error"}]` for AI steps that failed (model retired, Vultr Inference down). The scan carries on with rules only; show a quiet note.
- `vultr_bill`: `{"items": [{"service": "Cloud Compute|Serverless Inference|Object Storage", "what", "model"?, "detail", "usd"|null, "note"?, "api"?}], "total_usd", "note"}`. Built only from what the scan recorded, priced from the live model catalog.
- `replay`: `{"recorded": true, "note"}` when the report is a replay of a recorded real scan (`POST /api/scan {"sample", "replay": true}`), not a new run.

Other API added 4 Nov: `DELETE /api/scan/{id}` leaves the queue; `GET /e/{id}` redirects to a freshly signed evidence link; `GET /api/recorded` lists samples with a recorded scan; `GET /healthz` reports model availability and pool state. Queue events now read `"N in line for a free burner VM, about M min (...)"`.

## Benchmark API (data agent)
`GET /api/benchmark` → `{"summary": {...results.json summary...}, "samples": [...results.json samples...], "baseline": {"detected": 11, "of": 12, "false_alarms": 1}, "containment": [{"test", "result": "contained|fixed|flagged|missed", "detail"}], "defender": {...}}`. Built from `reports/benchmark/results.json` + `reports/benchmark/containment.json`; also written to `burner/web/bench.json` as a fallback.

## Charts API (charts agent exposes `window.BurnerCharts`)
Each function renders into a container element, is responsive (ResizeObserver), reads colours from CSS custom properties so it re-themes on `document` event `burner:theme`, has keyboard-focusable marks with tooltips, honours `prefers-reduced-motion`, and returns `{update(data), destroy()}`.
- `timeline(el, report.trace, {onSelect(event)})` — swimlane chart: step bands across the top, one lane per kind, dots/marks per event coloured by severity, brush/zoom on time, legend chips toggle lanes, hover tooltip, click → onSelect.
- `flow(el, report.flows)` — 3-column flow (secrets → process → destination) with link width by count/bytes, untaken secrets greyed, hover highlights a path.
- `baitBoard(el, report.bait, report.stolen)` — grid of the planted fake secrets as tiles (taken = red "stolen → dest", untouched = neutral).
- `benchMatrix(el, bench.samples)` — sample × detector (Burner / GuardDog) matrix, rows grouped malicious/benign, cell = caught/missed/false alarm, hover shows technique + headline.
- `scoreBars(el, bench.summary)` — paired bars: detection and false-alarm rate, Burner vs GuardDog.
- `scanTimes(el, bench.samples)` — dot/strip plot of scan seconds per sample.
- `donut(el, [{label, value, color?}])` — small helper for KPI tiles (e.g. 10 of 15 secrets taken).
Charts must escape/ use textContent for all labels (attacker-controlled strings).

## Events / theme
`theme.js` sets `<html data-theme="light|dark">` and dispatches `burner:theme` on `document` (Babel's `babel:theme` equivalent). Charts listen to it.

## Testing (everyone)
`BURNER_MOCK=1 python -m uvicorn burner.web.app:app --port <yours>` (UI 8021, charts 8022, data 8023). Headless Edge: `"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless --screenshot=out.png --window-size=1440,1000 URL` (add `--force-dark-mode` / test both themes; 375px width for phone). No real scans, no Vultr resources, no git commits.

## Data agent notes
Additions only — nothing in the shapes above was changed or removed.
- `trace.steps[].sandbox_died` is a bool; when true there is also `died_reason` (e.g. "sandbox stopped (out of memory; exit 0)").
- Events may carry extra fields: `process`, `secrets` (bait kinds behind a file / carried by a request), `count` (repeats merged within 1 s; `detail` then ends in "(xN)"), `bytes`, `event_id`, `raw_ip`.
- A request that carried secrets appears in **both** the `network` lane (the connection) and the `exfil` lane (label = destination, detail = secrets). Repeats that detect.py dedupes (e.g. the +45 day re-run sending the same secrets again) are re-checked so they show as exfil too.
- Routine reads of bait files (npm reading `~/.npmrc`, a login shell reading `~/.profile`) stay in the `secrets` lane with severity `info` and a reason in `detail`; they are not drawn as `read` links in flows.
- `files` lane also holds VM/sandbox fingerprinting reads (`/proc/1/cgroup`, `/sys/class/dmi/...`, severity `low`). `processes` lane gets a `"sandbox crashed"` event (severity `high`) at the end of a step whose sandbox died (fork/memory bomb).
- `trace.source = {"syscalls": bool, "net_events": n}`. Benchmark bundles (`reports/benchmark/runs/*/results/*/out`) and old scans have no `syscalls.log`: only network/dns/exfil events, and the sending process in flows is `"unknown process"` (node id `p:unknown process`) unless the request's user-agent names one.
- `flows` destination nodes for DNS-tunnel exfil have `"via": "dns"` (label = parent domain). `sent` link `bytes` = sum of the distinct requests' body sizes.
- If trace building throws inside a real scan, the report gets `trace_error` (string) and no `trace`/`flows` — UI should treat both as optional.
- `/api/benchmark` also returns `meta` (`finished`, `containment_tested`, `containment_environment`). `defender` = `{product, flagged_files, threat, file, when, stealers_flagged, stealers_total, note}`.
- Mock mode accepts a third sample id, `"vscode-task"` (mock only, rejected with 400 in real mode): `mock_report_vscode.json`, the real MALICIOUS benchmark run m02 (folderOpen VS Code task; no syscalls, no recruiter/explanation; `vm` is marked as a benchmark host). The real `samples/vscode-task-takehome/.vscode/tasks.json` was quarantined by Defender, so it is not offered as a live sample.
