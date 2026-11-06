// Burner web UI: routing (/, /r/{id}, /track), the scan form, the live run (SSE), the report and the track record.
// Every string that comes from a report or the server is inserted with textContent (attacker-controlled data);
// links only ever become hrefs when they are http(s). Charts come from window.BurnerCharts (charts.js) when present.
(function () {
  "use strict";

  // ---------------------------------------------------------------- tiny DOM helpers
  function h(tag, attrs) {
    var el = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (!Object.prototype.hasOwnProperty.call(attrs, k)) continue;
        var v = attrs[k];
        if (v == null || v === false) continue;
        if (k === "class") el.className = v;
        else if (k === "text") el.textContent = String(v);
        else if (k.slice(0, 2) === "on" && typeof v === "function") el.addEventListener(k.slice(2), v);
        else if (k === "hidden") el.hidden = !!v;
        else el.setAttribute(k, v === true ? "" : String(v));
      }
    }
    for (var i = 2; i < arguments.length; i++) add(el, arguments[i]);
    return el;
  }
  function add(el, c) {
    if (c == null || c === false) return;
    if (Array.isArray(c)) { c.forEach(function (x) { add(el, x); }); return; }
    el.appendChild(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  var SVG_NS = "http://www.w3.org/2000/svg";
  function s(tag, attrs) {
    var el = document.createElementNS(SVG_NS, tag);
    for (var k in attrs || {}) el.setAttribute(k, String(attrs[k]));
    for (var i = 2; i < arguments.length; i++) if (arguments[i]) el.appendChild(arguments[i]);
    return el;
  }
  function $(id) { return document.getElementById(id); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }
  function str(v) { return v == null ? "" : String(v); }
  function arr(v) { return Array.isArray(v) ? v : []; }
  function fmtClock(sec) { sec = Math.max(0, Math.floor(sec)); return Math.floor(sec / 60) + ":" + String(sec % 60).padStart(2, "0"); }
  function fmtBytes(n) {
    n = Number(n) || 0;
    if (n < 1024) return n + " B";
    if (n < 1048576) return (n / 1024).toFixed(1) + " KB";
    return (n / 1048576).toFixed(1) + " MB";
  }
  function plural(n, w, ws) { return n + " " + (n === 1 ? w : (ws || w + "s")); }
  function printable(x) { return str(x).replace(/\r/g, "").replace(/[\x00-\x08\x0b-\x1f\x7f]/g, "·"); }
  function safeUrl(u) { u = str(u).trim(); return u === "#" || /^https?:\/\//i.test(u) ? u : null; }
  function reduced() { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function shortTarget(t) {
    t = str(t);
    var m = /^(?:https?:\/\/)?(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)\/([^/?#\s]+\/[^/?#\s]+)/i.exec(t);
    if (m) return m[1].replace(/\.git$/, "");
    if (/[\\/]samples[\\/]/.test(t)) return t.split(/[\\/]/).pop() + " (sample)";
    return t.length > 60 ? t.slice(0, 57) + "…" : t;
  }
  function cssVar(name, fallback) {
    var v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return v || fallback;
  }
  function noop() { /* handled where it happened */ }
  function charts() { return window.BurnerCharts || null; }
  function badge(kind, text) { return h("span", { class: "badge badge-" + kind, text: text }); }

  function copyText(text, flag) {
    var done = function () { flag.hidden = false; setTimeout(function () { flag.hidden = true; }, 2000); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
    else { fallbackCopy(text); done(); }
  }
  function fallbackCopy(text) {
    var ta = h("textarea", { style: "position:fixed;left:-9999px;top:0" });
    ta.value = text; document.body.appendChild(ta); ta.select();
    try { document.execCommand("copy"); } catch (e) { /* nothing else to try */ }
    document.body.removeChild(ta);
  }

  // ---------------------------------------------------------------- theme toggle
  var toggle = $("theme-toggle");
  function syncToggle() {
    var dark = window.burnerTheme && window.burnerTheme.get() === "dark";
    toggle.setAttribute("aria-pressed", dark ? "true" : "false");
    toggle.setAttribute("aria-label", dark ? "Light mode" : "Dark mode");
  }
  toggle.addEventListener("click", function (e) {
    if (!window.burnerTheme) return;
    var r = toggle.getBoundingClientRect();
    var x = e.clientX || r.left + r.width / 2, y = e.clientY || r.top + r.height / 2;
    window.burnerTheme.toggle(x, y);
  });
  document.addEventListener("burner:theme", function () { syncToggle(); rethemeDonuts(); });
  syncToggle();

  // ---------------------------------------------------------------- views + routing
  var VIEWS = ["start", "run", "report", "track"];
  var view = "start";
  var BASE_TITLE = document.title;
  // the tab says what's happening, so a user who switched to their inbox sees the verdict land
  function tabTitle(t) { document.title = t ? t + " · Burner" : BASE_TITLE; }
  function setView(name, opts) {
    opts = opts || {};
    view = name;
    if (name === "start") tabTitle(null);
    else if (name === "track") tabTitle("Track record");
    VIEWS.forEach(function (v) { $("view-" + v).hidden = v !== name; });
    document.body.dataset.view = name;
    $$(".nav-track").forEach(function (a) { if (name === "track") a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    if (!opts.keepScroll) window.scrollTo({ top: 0, behavior: "instant" });
    var head = { run: "run-title", track: "track-title", report: "report-title" }[name];
    if (head && opts.focus !== false && $(head)) $(head).focus({ preventScroll: true });
    if (name === "start" && window.BurnerHero) window.BurnerHero.refresh();
  }
  function go(path, push) {
    if (push !== false && location.pathname + location.hash !== path) history.pushState(null, "", path);
    route();
  }
  function route() {
    var p = location.pathname;
    var m = /^\/r\/([A-Za-z0-9_-]+)\/?$/.exec(p);
    if (m) {
      if (S && S.id === m[1]) setView(S.report ? "report" : "run");
      else loadShared(m[1]);
      return;
    }
    if (/^\/track\/?$/.test(p)) { setView("track"); loadTrack(); return; }
    setView("start", { focus: false });
    if (location.hash === "#how") requestAnimationFrame(function () { $("how").scrollIntoView({ behavior: reduced() ? "auto" : "smooth" }); });
  }
  window.addEventListener("popstate", route);
  document.addEventListener("click", function (e) {
    var a = e.target.closest && e.target.closest("[data-route]");
    if (a && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) { e.preventDefault(); go(a.getAttribute("data-route")); return; }
    var act = e.target.closest && e.target.closest("[data-action]");
    if (!act) return;
    var what = act.getAttribute("data-action");
    if (what === "how") {
      e.preventDefault();
      go("/#how");
      $("how-title").focus({ preventScroll: true });
    } else if (what === "focus-start") {
      e.preventDefault();
      go("/");
      requestAnimationFrame(function () {
        $("scan-form").scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "center" });
        var f = mode === "repo" ? $("repo") : mode === "sample" ? $$(".sample-option[aria-checked='true']")[0] : $("msg");
        if (f) f.focus({ preventScroll: true });
      });
    } else if (what === "tour") {
      e.preventDefault();
      if (window.BurnerTour) window.BurnerTour.start();
    }
  });

  // ---------------------------------------------------------------- the form
  var mode = "message";
  var sample = "npm-start-stealer";
  var tabs = $$('.segmented [role="tab"]');
  function setMode(m, focus) {
    mode = m;
    tabs.forEach(function (t) {
      var on = t.getAttribute("data-mode") === m;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      $(t.getAttribute("aria-controls")).hidden = !on;
      if (on && focus) t.focus();
    });
    $("run-hint").hidden = m === "sample";   // samples run their own fixed steps
    formError(null);
  }
  tabs.forEach(function (t, i) {
    t.addEventListener("click", function () { setMode(t.getAttribute("data-mode")); });
    t.addEventListener("keydown", function (e) {
      var j = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: tabs.length - 1 }[e.key];
      if (j == null) return;
      e.preventDefault();
      setMode(tabs[(j + tabs.length) % tabs.length].getAttribute("data-mode"), true);
    });
  });
  var opts = $$(".sample-option");
  function setSample(name, focus) {
    sample = name;
    opts.forEach(function (o) {
      var on = o.getAttribute("data-sample") === name;
      o.setAttribute("aria-checked", on ? "true" : "false");
      o.tabIndex = on ? 0 : -1;
      if (on && focus) o.focus();
    });
  }
  opts.forEach(function (o, i) {
    o.addEventListener("click", function () { setSample(o.getAttribute("data-sample")); });
    o.addEventListener("keydown", function (e) {
      var j = { ArrowRight: i + 1, ArrowDown: i + 1, ArrowLeft: i - 1, ArrowUp: i - 1 }[e.key];
      if (j == null) return;
      e.preventDefault();
      setSample(opts[(j + opts.length) % opts.length].getAttribute("data-sample"), true);
    });
  });
  setSample(sample);

  function formError(msg, field) {
    var el = $("form-error");
    [$("msg"), $("repo"), $("run-cmd")].forEach(function (f) { f.removeAttribute("aria-invalid"); });
    if (!msg) { el.hidden = true; el.textContent = ""; return; }
    el.textContent = msg; el.hidden = false;
    if (field) { field.setAttribute("aria-invalid", "true"); field.focus(); }
  }
  function setBusy(b) {
    var btn = $("burn-btn");
    btn.disabled = b;
    if (b) btn.setAttribute("aria-busy", "true"); else btn.removeAttribute("aria-busy");
    btn.textContent = b ? "Starting…" : "Burn it";
    $$("button.strip-tab").forEach(function (x) { x.disabled = b; });
  }
  var SAMPLE_NAMES = { "npm-start-stealer": "the npm-start stealer sample", "clean-takehome": "the clean take-home sample" };
  var REPO_LINK = /(?:^|[^\w.@/-])(?:https?:\/\/)?(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)\/[\w.-]+\/[\w.-]+/i;

  $("scan-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var msg = $("msg").value.trim(), repo = $("repo").value.trim();
    if (mode === "sample") { start({ sample: sample }, { title: SAMPLE_NAMES[sample], hasMessage: sample === "npm-start-stealer" }).catch(noop); return; }
    if (mode === "message" && !msg && !repo) { formError("Paste the recruiter's message first, or switch to Repo link.", $("msg")); return; }
    if (mode === "repo" && !repo) { formError("Paste the repo link first.", $("repo")); return; }
    // the server normalises what people paste (no https://, www., trailing /, /tree/<branch>); this only catches
    // the dead ends before a scan starts
    if (mode === "repo" && !REPO_LINK.test(repo)) {
      formError("That doesn't look like a repo link. Paste a public github.com, gitlab.com or bitbucket.org link, like github.com/owner/repo.", $("repo")); return;
    }
    if (mode === "message" && !repo && !REPO_LINK.test(msg)) {
      formError("There's no github.com, gitlab.com or bitbucket.org link in this message, and Burner needs one to run it. " +
        "If they sent a zip, a Google Drive file or an installer instead, treat that as a red flag: ask for a public repo link.", $("msg")); return;
    }
    var run = $("run-cmd").value.trim();
    if (run && (run.length > 200 || /[\x00-\x1f\x7f]/.test(run))) { $("run-hint").open = true; formError("Keep the command to one line, up to 200 characters.", $("run-cmd")); return; }
    var body = {};
    if (msg) body.message = msg;
    if (repo) body.repo = repo;
    if (run) body.run = run;   // becomes a "you asked" step
    start(body, { title: repo ? shortTarget(repo) : "the recruiter's take-home", target: repo || "", hasMessage: !!msg }).catch(noop);
  });
  $$(".strip-tab[data-demo]").forEach(function (b) {
    b.addEventListener("click", function () {
      var d = b.getAttribute("data-demo");
      if (d === "own") {
        setMode("repo");
        $("scan-form").scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "center" });
        $("repo").focus({ preventScroll: true });
        return;
      }
      setMode("sample"); setSample(d);
      start({ sample: d }, { title: SAMPLE_NAMES[d], hasMessage: d === "npm-start-stealer", sample: d }).catch(noop);
    });
  });

  // a recorded real scan, replayed: no VM, about 15 s, always on offer (and again while queued)
  var REAL_SCAN = "efafff21e7";   // a real finished v5 scan on the live server (95 s VM, $0.0007, deletion confirmed)
  var realLink = $("real-scan-link");
  if (realLink) { realLink.href = "/r/" + REAL_SCAN; realLink.setAttribute("data-route", "/r/" + REAL_SCAN); }
  function startReplay(pick) {
    if (RECORDED && RECORDED.length && RECORDED.indexOf(pick) < 0) pick = RECORDED[0];
    return start({ sample: pick, replay: true }, { title: SAMPLE_NAMES[pick] || "a recorded scan", hasMessage: pick === "npm-start-stealer", replay: true, sample: pick });
  }
  $("replay-btn").addEventListener("click", function () { startReplay($("replay-btn").getAttribute("data-replay")).catch(noop); });

  // ---------------------------------------------------------------- the live run
  var PHASES = [
    { key: "message", label: "Read the recruiter message", short: "Read" },
    { key: "plan", label: "Plan like a candidate", short: "Plan" },
    { key: "vm", label: "Fresh Vultr VM", short: "Boot VM" },
    { key: "setup", label: "Arm the sandbox", short: "Arm" },
    { key: "run", label: "Run like a candidate", short: "Detonate" },
    { key: "destroy", label: "Destroy the VM", short: "Destroy" },
    { key: "verdict", label: "Verdict", short: "Verdict" }
  ];
  var STATE_TEXT = { pending: "", running: "working…", done: "done", warning: "check", failed: "failed" };
  var S = null;
  var timerId = null;
  var es = null;

  function newState(id, info) {
    return { id: id, info: info || {}, cur: -1, seen: 0, ended: false, lastT: 0, base: Date.now(), phases: [], steps: [],
      vmDestroyed: false, sandboxDestroyed: false, vmLife: null, report: null, events: [], sawMessage: false,
      warn: {}, autoTimer: 0 };
  }

  function buildPhases() {
    var ol = $("phases"); clear(ol);
    S.phases = PHASES.map(function (p, i) {
      var label = p.label;
      if (i === 0 && S.info.hasMessage === false) label = "Get the repo";
      var name = h("span", { class: "step-name", text: label });
      var state = h("span", { class: "step-state" });
      var msgs = h("ul", { class: "step-messages" });
      var sub = p.key === "run" ? h("ol", { class: "substeps", "aria-label": "Candidate steps" }) : null;
      var li = h("li", { class: "step", "data-state": "pending", "data-k": p.key },
        h("span", { class: "step-icon", "aria-hidden": "true" }), name, state, msgs, sub);
      ol.appendChild(li);
      var mark = h("li", { class: "fuse-mark", "data-state": "pending" }, h("span", { class: "fuse-dot" }),
        h("span", { class: "fuse-label", text: p.key === "message" && S.info.hasMessage === false ? "Fetch" : p.short }));
      return { li: li, name: name, state: state, msgs: msgs, sub: sub, mark: mark };
    });
    var marks = $("fuse-marks");
    if (marks) { clear(marks); S.phases.forEach(function (p) { marks.appendChild(p.mark); }); }
    fuse(0, "");
    clear($("contain-slot")); clear($("error-slot")); clear($("events-list")); clearPrecheck();
    $("events-count").textContent = "";
    $("run-after").hidden = true;
  }
  function setState(i, st) {
    var p = S.phases[i];
    if (!p) return;
    if (st === "done" && S.warn[i]) st = "warning";
    p.li.setAttribute("data-state", st);
    p.state.textContent = STATE_TEXT[st] || "";
    if (p.mark) p.mark.setAttribute("data-state", st);
  }
  // the fuse (decorative): burns left to right through the phase markers; "ash" once the VM is destroyed
  function fuse(burn, cls) {
    var f = $("fuse");
    if (!f) return;
    if (burn != null) f.style.setProperty("--burn", String(Math.max(0, Math.min(1, burn))));
    if (cls === "") f.classList.remove("is-ash", "is-lit", "is-failed");
    else if (cls) f.classList.add(cls);
  }
  function phaseOf(ev) {
    var st = ev.stage, tx = str(ev.text);
    if (st === "queue" || st === "message" || st === "fetch") return 0;
    if (st === "plan") return 1;
    if (st === "vm") return /^VM (destroyed|kept)/.test(tx) ? 5 : 2;
    if (st === "setup") return 3;
    if (st === "run") return tx === "sandbox destroyed" ? 5 : 4;
    if (st === "explain" || st === "done" || st === "match" || st === "evidence") return 6;
    return Math.max(S.cur, 0);
  }
  function setPhase(idx) {
    if (idx < S.cur) return;
    S.cur = idx;
    S.phases.forEach(function (p, i) { setState(i, i < idx ? "done" : i === idx ? "running" : "pending"); });
    fuse((idx + 0.5) / PHASES.length, "is-lit");
    if (idx > 4) finishSteps();
  }
  function finishSteps() { S.steps.forEach(function (x) { x.className = "substep is-fin"; }); }
  function parseStep(tx) {
    // "step {'n': 2, 'name': 'npm run start', 'cmd': 'npm run start'}" (Python repr)
    var m = /^(?:step )?\{.*?'name': (['"])(.*?)\1, 'cmd': (['"])(.*)\3\}\s*$/.exec(tx);
    if (!m) return null;
    var n = /'n': (\d+)/.exec(tx);
    return { n: n ? n[1] : "", name: m[2], cmd: m[4] };
  }
  function tapeText(tx) {   // server lines carry Python reprs; show them as readable text
    var p = parseStep(tx);
    if (p) return "step " + p.n + " · " + p.name + (p.cmd && p.cmd !== p.name ? "  $ " + p.cmd : "");
    var m = /^plan \{'steps': \[(.*)\]\}\s*$/.exec(tx);
    if (m) return "plan: " + m[1].split(/',\s*'|",\s*"/).map(function (x) { return x.replace(/^['"]|['"]$/g, ""); }).join(" → ");
    return tx;
  }
  function logEvent(ev) {
    var list = $("events-list");   // newest first: the tape reads from the top
    list.insertBefore(h("li", { class: ev.stage === "error" ? "is-error" : null, "data-stage": str(ev.stage).replace(/[^a-z]/g, "") },
      h("span", { class: "ev-t", text: "T+" + (Number(ev.t) || 0).toFixed(1) }),
      h("span", { class: "ev-s", text: str(ev.stage) }),
      h("span", { text: tapeText(str(ev.text)) })), list.firstChild);
    $("events-count").textContent = "(" + list.children.length + ")";
  }
  function setRunTitle(t) { $("run-title").textContent = "Burning " + t; }

  function handleEvent(ev) {
    var tx = str(ev.text);
    S.events.push(ev);
    logEvent(ev);
    S.lastT = Number(ev.t) || S.lastT;
    if (!S.ended) S.base = Date.now() - S.lastT * 1000;
    if (ev.stage === "precheck") { showPrecheck(ev.data, tx); return; }   // warnings only: no phase change
    var idx = phaseOf(ev);
    var p = S.phases[idx];
    if (ev.stage === "error") {
      setState(idx, "failed");
      p.msgs.appendChild(h("li", { class: "is-error", text: tx }));
      showRunError(tx);
      return;
    }
    if (ev.stage === "message") S.sawMessage = true;
    if (ev.stage === "queue" && /in line/.test(tx)) offerReplay();
    setPhase(idx);
    if (ev.stage === "vm" && /warm pool/.test(tx)) {
      p.name.textContent = "Pre-armed VM from the warm pool";
      S.phases[3].name.textContent = "Arm the sandbox (armed in the pool)";
    }
    // the repo link from the message or the download line names the run
    var rm = /repo: (\S+)/.exec(tx) || (ev.stage === "fetch" ? /downloading (\S+)/.exec(tx) : null);
    if (rm && S.info.autoTitle !== false) {
      setRunTitle(shortTarget(rm[1]));
      $("run-sub").textContent = rm[1];
    }
    var step = ev.stage === "run" ? parseStep(tx) : null;
    if (step) {
      S.steps.forEach(function (x) { x.className = "substep is-fin"; });
      var li = h("li", { class: "substep is-cur" }, h("span", { class: "sdot", "aria-hidden": "true" }),
        h("div", null, h("span", { class: "sname", text: (step.n ? "Step " + step.n + " · " : "") + step.name }),
          h("span", { class: "scmd", text: "$ " + step.cmd })));
      p.sub.appendChild(li);
      S.steps.push(li);
      return;
    }
    if (ev.stage === "run" && tx === "grace period (background payloads)") finishSteps();
    if (/^plan \{/.test(tx)) return;   // the plan was already shown in the Plan phase
    var shown = ev.stage === "plan" ? tx.replace(/ -> /g, " → ") : tx;
    var cls = null;
    if (ev.stage === "plan" && / → /.test(shown)) cls = "is-plan";
    if (/sandbox died|crashed|killed|timed out|warning|AI unavailable/i.test(tx) && ev.stage !== "done") { cls = "is-warning"; S.warn[idx] = true; }
    if (ev.stage === "done") {
      shown = tx.length > 180 ? tx.slice(0, 177) + "…" : tx;
      cls = /^MALICIOUS/.test(tx) ? "is-error" : /^(SUSPICIOUS|INCONCLUSIVE)/.test(tx) ? "is-warning" : null;
    }
    p.msgs.appendChild(h("li", { class: cls, text: shown }));
    var vmm = /^VM destroyed after (\d+)s/.exec(tx);
    if (vmm) { S.vmDestroyed = true; S.vmLife = vmm[1]; showContain(); }
    else if (tx === "sandbox destroyed") { S.sandboxDestroyed = true; showContain(); }
    if (ev.stage === "done") {
      S.phases.forEach(function (q, i) { setState(i, "done"); });
      fuse(1, null);
      if (!S.sawMessage && S.info.hasMessage !== true) S.phases[0].name.textContent = "Get the repo";
    }
  }

  // ---------------------------------------------------------------- pre-check (warnings only; never the verdict)
  // Red flags found WITHOUT running anything (burner/control/precheck.py), streamed as one "precheck" SSE event with
  // the result in ev.data, and kept as report.precheck. Every string in it is attacker-influenced: textContent only.
  var PC_NOTE = "warnings only — the verdict comes from running it";
  var PC_SRC = { files: "files", github: "GitHub", npm: "npm", rdap: "domain", network: "network" };
  var PC_SEV = { high: "High", warn: "Warn", info: "Info" };
  function precheckFlags(pc) {
    return arr(pc && pc.flags).filter(function (f) { return f && typeof f === "object"; });
  }
  function precheckWarnCount(pc) {
    return precheckFlags(pc).filter(function (f) { return f.severity === "high" || f.severity === "warn"; }).length;
  }
  function precheckChip(sev) {
    var k = PC_SEV[sev] ? sev : "info";
    return h("span", { class: "pc-chip is-" + k, text: PC_SEV[k] });
  }
  function precheckRow(f) {
    var sev = PC_SEV[f.severity] ? f.severity : "info";
    return h("li", { class: "pc-row is-" + sev },
      precheckChip(sev),
      h("span", { class: "pc-row-title", text: str(f.title) || str(f.id) }),
      h("span", { class: "pc-src", text: PC_SRC[f.source] || str(f.source) }),
      f.detail ? h("span", { class: "pc-row-detail", text: printable(f.detail) }) : null);
  }
  function precheckSources(pc) {
    var src = (pc && pc.sources) || {}, bits = [];
    ["files", "github", "npm", "rdap"].forEach(function (k) {
      var v = src[k];
      if (!v || v === "skipped") return;
      bits.push(PC_SRC[k] + (v === "ok" ? " ✓" : v === "timeout" ? " (too slow, skipped)" : " (unavailable)"));
    });
    return bits.length ? "Checked: " + bits.join(" · ") : "";
  }
  function precheckCard(pc, text) {
    var flags = precheckFlags(pc), n = precheckWarnCount(pc), high = flags.filter(function (f) { return f.severity === "high"; }).length;
    var ms = Number(pc && pc.ms);
    var sum = (n ? plural(n, "warning sign") : "no warning signs") + (isFinite(ms) && ms > 0 ? " · " + (ms / 1000).toFixed(1) + " s" : "");
    var card = h("section", { class: "pc-card", "aria-label": "Pre-check, " + PC_NOTE },
      h("header", { class: "pc-head" },
        h("h2", { class: "pc-title" }, h("span", { class: "pc-label", text: "Pre-check" }), h("span", { class: "pc-note", text: "· " + PC_NOTE })),
        h("span", { class: "pc-sum" + (high ? " is-hot" : ""), text: sum })));
    if (!pc) {   // an emitter that sent no data: the one-line summary is all there is
      card.appendChild(h("p", { class: "pc-empty", text: printable(text) || "Pre-check finished." }));
      return card;
    }
    var warn = flags.filter(function (f) { return f.severity === "high" || f.severity === "warn"; });
    var info = flags.filter(function (f) { return !(f.severity === "high" || f.severity === "warn"); });
    var list = h("ol", { class: "pc-list" });
    var shown = warn.length ? warn.slice(0, 6) : info.slice(0, 4);
    var rest = warn.length ? warn.slice(6).concat(info) : info.slice(4);
    shown.forEach(function (f) { list.appendChild(precheckRow(f)); });
    if (!warn.length) card.appendChild(h("p", { class: "pc-empty", text: "Nothing stood out in the files" + (info.length ? " or where it came from." : ".") + " That's why Burner runs it anyway." }));
    if (shown.length) card.appendChild(list);
    var more = null;
    if (rest.length) {
      more = h("button", { type: "button", class: "pc-more", "aria-expanded": "false", text: "+ " + rest.length + " more (" + (warn.length > 6 ? "incl. context" : "context") + ")" });
      more.addEventListener("click", function () {
        rest.forEach(function (f) { list.appendChild(precheckRow(f)); });
        if (!list.parentNode) card.insertBefore(list, card.lastChild);
        more.remove();
      });
    }
    card.appendChild(h("footer", { class: "pc-foot" },
      h("span", { text: "Nothing was run to find these. " + precheckSources(pc) }), more));
    return card;
  }
  function clearPrecheck() { var slot = $("precheck-slot"); if (slot) clear(slot); }
  function showPrecheck(pc, text) {
    var slot = $("precheck-slot");
    if (!slot) return;
    clear(slot);
    slot.appendChild(precheckCard(pc && typeof pc === "object" ? pc : null, text));
  }
  // report: "Before it ran: N warning signs", self-contained, placed under the verdict head
  function renderPrecheckReport(out, pc) {
    if (!pc || typeof pc !== "object") return;
    var flags = precheckFlags(pc), n = precheckWarnCount(pc);
    var high = flags.filter(function (f) { return f.severity === "high"; }).length;
    var warn = flags.filter(function (f) { return f.severity === "high" || f.severity === "warn"; });
    var card = h("section", { class: "pc-card pc-report" + (high ? " is-hot" : ""), "aria-labelledby": "pc-report-h" },
      h("header", { class: "pc-head" },
        h("h2", { class: "pc-report-h", id: "pc-report-h" }, "Before it ran: ",
          h("span", { class: "pc-n", text: n ? String(n) : "no" }), n === 1 ? " warning sign" : " warning signs"),
        h("span", { class: "pc-note", text: "Pre-check · " + PC_NOTE })));
    if (warn.length) {
      var list = h("ol", { class: "pc-list" });
      warn.slice(0, 5).forEach(function (f) { list.appendChild(precheckRow(f)); });
      card.appendChild(list);
    } else {
      card.appendChild(h("p", { class: "pc-empty", text: "The files and where they came from looked ordinary. Only running it could tell." }));
    }
    card.appendChild(h("footer", { class: "pc-foot" },
      h("span", { text: (warn.length > 5 ? "+" + (warn.length - 5) + " more. " : "") + "Found by reading the files, nothing was run. The verdict above comes from what it did." })));
    out.appendChild(card);
  }

  function showContain() {
    var slot = $("contain-slot");
    var big = S.vmDestroyed ? ["VM destroyed. ", "Nothing touched your laptop."] : ["Sandbox destroyed. ", "Nothing touched your laptop."];
    var small = S.vmDestroyed
      ? "The repo only ever ran on a throwaway Vultr VM" + (S.vmLife ? " that lived " + S.vmLife + " seconds" : "") + ". It's gone now, with the fake secrets it took."
      : "The repo ran inside a gVisor sandbox on a burner VM, with fake secrets and a fake internet. The VM goes next.";
    if (S.vmDestroyed) fuse(null, "is-ash");
    var box = document.querySelector("#phases .contain, #contain-slot .contain");
    if (box) {   // already shown: update the words, don't replay the animation
      box.querySelector(".contain-big").lastChild.textContent = big[1];
      box.querySelector(".contain-big").firstChild.textContent = big[0];
      box.querySelector(".contain-small").textContent = small;
      if (S.vmDestroyed) containArt(box.querySelector(".contain-art"), true);
      return;
    }
    var art = h("canvas", { class: "contain-art", "aria-hidden": "true" });
    var host = S.phases[5] ? S.phases[5].li : slot;
    var beat = host.appendChild(h("div", { class: "contain", role: "status" },
      art,
      h("div", null,
        h("p", { class: "contain-big" }, big[0], h("b", { text: big[1] })),
        h("p", { class: "contain-small", text: small }),
        h("div", { class: "contain-chips" }, badge("observed", "Fake secrets only"), badge("rule", "gVisor + throwaway VM")))));
    containArt(art, S.vmDestroyed);
    if (view === "run") {
      var r = beat.getBoundingClientRect();
      if (r.bottom > innerHeight || r.top < 0) beat.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "center" });
    }
  }
  // dither art for the containment beat: the VM cube, then (once it's destroyed) the cube dissolving into ash, played once
  function containArt(cv, ash) {
    var D = window.BurnerDither;
    if (!cv || !D) return;
    var want = ash ? "ash" : "vm";
    if (cv.getAttribute("data-art") === want) return;
    cv.setAttribute("data-art", want);
    if (ash) D.icon(cv, "ash", { animate: true, until: 3.2, end: 0.66, fill: 0.92 });
    else D.icon(cv, "vm", { fill: 0.86 });
  }
  // stuck in the queue: after a short wait, offer a recorded real scan instead (no VM, ~15 s)
  var RECORDED = null;
  fetch("/api/recorded").then(function (r) { return r.ok ? r.json() : { samples: [] }; })
    .then(function (j) { RECORDED = arr(j.samples); }).catch(function () { RECORDED = []; });
  function offerReplay() {
    if (!S || S.replayOffer || S.info.replay) return;
    var id = S.id;
    S.replayOffer = setTimeout(function () {
      if (!S || S.id !== id || S.ended || S.cur > 0 || !RECORDED || !RECORDED.length) return;
      var pick = RECORDED.indexOf(S.info.sample) >= 0 ? S.info.sample : RECORDED.indexOf("npm-start-stealer") >= 0 ? "npm-start-stealer" : RECORDED[0];
      var slot = $("error-slot"); clear(slot);
      slot.appendChild(h("div", { class: "run-error run-offer", role: "status" },
        h("b", { text: "Every scan gets its own VM, so there's a short line right now." }),
        h("span", { text: " Keep your place, or watch a recorded real scan of a sample while you wait (about 15 s, no new VM)." }),
        h("div", { class: "run-offer-actions" },
          h("button", { type: "button", class: "button", onclick: function () {
            fetch("/api/scan/" + encodeURIComponent(id), { method: "DELETE" }).catch(noop);
            startReplay(pick).catch(noop);
          } }, "Watch a recorded scan"),
          h("button", { type: "button", class: "button button-secondary", onclick: function () { clear(slot); } }, "Keep my place"))));
    }, 20000);
  }
  function showRunError(text) {
    var slot = $("error-slot"); clear(slot);
    slot.appendChild(h("div", { class: "run-error", role: "alert" }, h("b", { text: "The scan stopped with an error" }),
      h("code", { text: text || "unknown error" })));
    $("run-title").textContent = "Scan failed";
    tabTitle("Scan failed");
    $("run-eyebrow").textContent = "Live run · stopped";
    $("view-run").setAttribute("data-state", "failed");
    fuse(null, "is-failed");
    showAfter(false);
  }
  function showAfter(hasReport) {
    $("run-after").hidden = false;
    $("run-report").hidden = !hasReport;
    $("run-cancel").textContent = "Scan another";
  }
  function tick() {
    if (!S || S.ended) return;
    var clock = fmtClock((Date.now() - S.base) / 1000);
    $("timer").textContent = clock;
    tabTitle("● " + (S.info.replay ? "Replaying " : "Burning ") + clock);
  }
  function startTimer() { stopTimer(); timerId = setInterval(tick, 250); tick(); }
  function stopTimer() { if (timerId) clearInterval(timerId); timerId = null; }

  function showRun(info) {
    $("run-eyebrow").textContent = info.replay ? "Replay · a recorded real scan, sped up" : "Live run";
    $("run-case").textContent = "Case " + (S && S.id ? str(S.id).slice(0, 8).toUpperCase() : "—");
    $("view-run").setAttribute("data-state", "live");
    setRunTitle(info.title || "it");
    $("run-sub").textContent = info.target || (info.hasMessage ? "From the recruiter's message" : "");
    $("timer").textContent = "0:00";
    $("run-cancel").textContent = "Cancel";
    $("events-log").open = false;
    buildPhases();
  }

  function follow(id) {
    if (es) es.close();
    es = new EventSource("/api/scan/" + encodeURIComponent(id) + "/events");
    var mine = es, conn = 0;   // the server replays from the start on reconnect; skip what we've seen
    es.onmessage = function (m) {
      if (!S || S.id !== id) { mine.close(); return; }
      conn++;
      if (conn <= S.seen) return;
      S.seen = conn;
      var ev; try { ev = JSON.parse(m.data); } catch (e) { return; }
      handleEvent(ev);
    };
    es.addEventListener("end", function (m) {
      mine.close();
      var st = "done"; try { st = JSON.parse(m.data).status; } catch (e) { /* keep "done" */ }
      if (S && S.id === id) finish(id, st);
    });
    es.onerror = function () {
      if (!S || S.id !== id || S.ended) { mine.close(); return; }
      conn = 0;
      if (mine.readyState === EventSource.CLOSED) setTimeout(function () { poll(id); }, 2000);
    };
  }
  function poll(id) {
    if (!S || S.id !== id || S.ended) return;
    fetch("/api/scan/" + encodeURIComponent(id)).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (j) {
      if (!S || S.id !== id) return;
      (j.events || []).slice(S.seen).forEach(handleEvent);
      S.seen = (j.events || []).length;
      if (j.status === "done" || j.status === "error") finish(id, j.status, j);
      else setTimeout(function () { poll(id); }, 2000);
    }).catch(function () { setTimeout(function () { poll(id); }, 4000); });
  }
  function finish(id, status, data) {
    if (S.ended) return;
    S.ended = true;
    stopTimer();
    $("timer").textContent = fmtClock(S.lastT);
    setBusy(false);
    var p = data ? Promise.resolve(data) : fetch("/api/scan/" + encodeURIComponent(id)).then(function (r) { return r.json(); });
    p.then(function (j) {
      if (!S || S.id !== id) return;
      if (status === "error" || j.status === "error") {
        if (!$("error-slot").firstChild) {
          var errs = (j.events || []).filter(function (e) { return e.stage === "error"; });
          showRunError(errs.length ? errs[errs.length - 1].text : "The scan did not finish.");
        }
        return;
      }
      $("run-eyebrow").textContent = (S.info.replay ? "Replay · finished in " : "Live run · finished in ") + fmtClock(S.lastT);
      $("view-run").setAttribute("data-state", "done");
      if (j.report) {
        S.report = j.report;
        renderReport(j.report, id);
        showAfter(true);
        S.autoTimer = setTimeout(function () { if (view === "run" && S && S.id === id) setView("report"); }, 3200);   // let the "VM destroyed" beat land
      }
    }).catch(function (e) { showRunError("Could not load the report: " + e.message); });
  }

  function stopWatching() {
    if (es) { es.close(); es = null; }
    stopTimer();
    if (S) { clearTimeout(S.autoTimer); if (!S.ended) S.cancelled = true; }
    setBusy(false);
  }
  $("run-cancel").addEventListener("click", function () {
    if (S && !S.ended) { stopWatching(); S = null; }
    go("/");
    $("scan-form").scrollIntoView({ block: "center" });
  });
  $("run-again").addEventListener("click", function () { go("/"); $("scan-form").scrollIntoView({ block: "center" }); });
  $("run-report").addEventListener("click", function () { if (S) clearTimeout(S.autoTimer); setView("report"); });

  function start(body, info) {
    formError(null);
    setBusy(true);
    return fetch("/api/scan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
      .then(function (r) {
        return r.json().catch(function () { return {}; }).then(function (j) { return { ok: r.ok, status: r.status, j: j }; });
      })
      .then(function (res) {
        if (!res.ok) {
          var d = res.j && res.j.detail;
          if (Array.isArray(d)) d = d.map(function (x) { return x && x.msg ? x.msg : JSON.stringify(x); }).join("; ");
          var msg = d ? String(d) : "Request failed (HTTP " + res.status + ")";
          if (res.status === 429) msg = "Slow down: " + msg + ". You can still watch a recorded scan of a sample.";
          throw new Error(msg);
        }
        stopWatching();
        S = newState(res.j.id, info);
        setBusy(true);
        showRun(info);
        history.pushState(null, "", "/r/" + res.j.id);
        setView("run");
        startTimer();
        follow(res.j.id);
        return res.j.id;
      })
      .catch(function (e) {
        setBusy(false);
        if (view !== "start") go("/");
        formError(e.message || String(e));
        throw e;
      });
  }

  function loadShared(id) {
    stopWatching();
    S = newState(id, { title: "scan " + id, autoTitle: true });
    showRun(S.info);
    setView("run", { focus: false });
    $("run-eyebrow").textContent = "Loading…";
    fetch("/api/scan/" + encodeURIComponent(id)).then(function (r) {
      if (r.status === 404) throw new Error("This scan was not found. Links only last while the server keeps the result.");
      if (!r.ok) throw new Error("Could not load this scan (HTTP " + r.status + ").");
      return r.json();
    }).then(function (j) {
      if (!S || S.id !== id) return;
      $("run-eyebrow").textContent = "Live run";
      if (j.status === "done" && j.report) {
        (j.events || []).forEach(handleEvent);
        S.seen = (j.events || []).length; S.ended = true;
        $("timer").textContent = fmtClock(S.lastT);
        if (j.report.target) { setRunTitle(shortTarget(j.report.target)); $("run-sub").textContent = str(j.report.target); }
        $("run-eyebrow").textContent = "Live run · finished";
        $("view-run").setAttribute("data-state", "done");
        if (!j.events || !j.events.length) $("events-log").hidden = true;
        S.report = j.report;
        renderReport(j.report, id);
        showAfter(true);
        setView("report");
        return;
      }
      if (j.status === "error") {
        (j.events || []).forEach(handleEvent);
        S.ended = true; $("timer").textContent = fmtClock(S.lastT);
        if (!$("error-slot").firstChild) showRunError("The scan did not finish.");
        return;
      }
      setBusy(true); startTimer(); follow(id);   // still running: watch it live
    }).catch(function (e) {
      $("run-eyebrow").textContent = "Not found";
      $("run-title").textContent = "This scan isn't here";
      showRunError(e.message);
      $("run-title").textContent = "This scan isn't here";
    });
  }

  // ---------------------------------------------------------------- report
  var donuts = [];
  function rethemeDonuts() { donuts.forEach(function (d) { d(); }); }

  // dossier helpers: mono micro-labels, square evidence tags, numbered sections
  function ml(text, cls) { return h("span", { class: "ml" + (cls ? " " + cls : ""), text: text }); }
  function etag(kind, text) { return h("span", { class: "etag etag-" + kind, text: text }); }
  function pad2(n) { return String(n).padStart(2, "0"); }
  // a dither section mark (BurnerDither.icon); stays hidden unless the library draws it
  function mark(name, cls) { return h("canvas", { class: "dm" + (cls ? " " + cls : ""), "data-icon": name, "aria-hidden": "true", hidden: true }); }
  function paintMarks(root) {
    var D = window.BurnerDither;
    $$("canvas.dm", root).forEach(function (c) {
      if (!D || typeof D.icon !== "function") { c.hidden = true; return; }
      c.hidden = false;
      var small = Math.min(c.clientWidth || 60, c.clientHeight || 60) < 64;
      var left = !!(c.closest && c.closest(".rp-kpi, .tk-margin"));
      try {
        D.icon(c, c.getAttribute("data-icon"), { ember: c.classList.contains("is-hot"), pitch: small ? 2 : 3, fill: 0.9, align: left ? "left" : "center" });
      } catch (e) { c.hidden = true; }
    });
  }
  window.addEventListener("load", function () {
    ["report", "track"].forEach(function (k) { var el = $(k); if (el && el.firstChild) paintMarks(el); });
  });
  // standalone sections: the head sits on the page, everything else goes into one framed body
  function frameSections(root) {
    Array.prototype.slice.call(root.children).forEach(function (sec) {
      if (!sec.classList.contains("rp-sec") || sec.classList.contains("rp-exhibits") || $$(".rp-body", sec).length) return;
      var kids = Array.prototype.slice.call(sec.children).filter(function (k) { return !k.classList.contains("rp-sec-head"); });
      if (!kids.length) return;
      var body = h("div", { class: "rp-body" });
      kids.forEach(function (k) { body.appendChild(k); });
      sec.appendChild(body);
    });
  }
  function panel(title, opts) {
    opts = opts || {};
    var sec = h("section", { class: "rp-sec " + (opts.cls || ""), id: opts.id || null });
    sec.appendChild(h("header", { class: "rp-sec-head" },
      h("p", { class: "rp-kicker" }, opts.icon ? mark(opts.icon.replace("!", ""), /!$/.test(opts.icon) ? "is-hot" : null) : null, opts.num ? h("span", { class: "rp-num", text: opts.num }) : null,
        opts.eyebrow ? h("span", { class: "rp-eyebrow", text: opts.eyebrow }) : null,
        opts.tags ? h("span", { class: "rp-tags" }, opts.tags) : null),
      h("h2", { class: "rp-h2", text: title }),
      opts.sub ? h("p", { class: "rp-sub", text: opts.sub }) : null));
    return sec;
  }
  function highlight(snippet, value) {
    var pre = h("pre", { class: "snip" });
    var sn = printable(snippet), v = printable(value);
    if (!v) { pre.textContent = sn; return pre; }
    var i = 0, j;
    while ((j = sn.indexOf(v, i)) !== -1) {
      add(pre, sn.slice(i, j));
      pre.appendChild(h("mark", { title: "fake value planted by Burner", text: v }));
      i = j + v.length;
    }
    add(pre, sn.slice(i));
    return pre;
  }
  // a row of small segments, one per planted secret; taken ones burn
  function burnMeter(taken, total) {
    var el = h("span", { class: "burnmeter", role: "img", "aria-label": taken + " of " + total + " fake secrets stolen" });
    for (var i = 0; i < total; i++) el.appendChild(h("i", { class: i < taken ? "is-hot" : null, style: "--i:" + i }));
    return el;
  }
  function kpi(label, value, sub, cls, extra, icon) {
    return h("div", { class: "rp-kpi " + (cls || "") }, icon ? mark(icon, cls === "is-hot" ? "is-hot" : null) : null, ml(label), h("span", { class: "rp-kpi-v" }, value), extra || null,
      sub ? h("span", { class: "rp-kpi-sub", text: sub }) : null);
  }
  function unit(v, u) { return h("span", null, String(v), h("small", { text: u })); }

  function groupStolen(stolen) {
    var groups = [], byKey = {};
    stolen.forEach(function (x) {
      var k = str(x.secret) + "\u0000" + str(x.from_file);
      if (!byKey[k]) { byKey[k] = { secret: x.secret, from_file: x.from_file, dests: [], steps: [] }; groups.push(byKey[k]); }
      var g = byKey[k], d = str(x.sent_to || x.dst);
      if (!g.dests.some(function (y) { return y.d === d; })) g.dests.push({ d: d, enc: !!x.encoded });
      if (x.step && g.steps.indexOf(x.step) === -1) g.steps.push(x.step);
    });
    return groups;
  }

  // "I already ran it": a clean-up checklist built only from what this scan observed (rules, not the AI).
  // Every attacker-controlled string (paths, hosts, step names) goes in via textContent.
  var RAN_SOURCES = [
    { name: "Atlassian, Sep 2026", url: "https://www.atlassian.com/blog/bitbucket/disrupting-contagious-interview" },
    { name: "FBI IC3 PSA, Sep 2024", url: "https://www.ic3.gov/PSA/2024/PSA240903" }
  ];
  // one category per fake secret / file label; order matters (MetaMask lives inside the Chrome profile)
  var RAN_KINDS = [
    ["wallet", /solana|exodus|metamask|seed phrase|wallet|documents folder/],
    ["aws", /aws/],
    ["ssh", /ssh/],
    ["github", /github|git-credentials/],
    ["npm", /npm/],
    ["apikeys", /stripe|openai|database|\.env|another project/],
    ["browser", /browser|chrome/],
    ["history", /history/]
  ];
  function ranKind(label) {
    var s = str(label).toLowerCase();
    for (var i = 0; i < RAN_KINDS.length; i++) if (RAN_KINDS[i][1].test(s)) return RAN_KINDS[i][0];
    return null;
  }
  function tildePath(p) { return str(p).replace(/^\/home\/[^/]+\//, "~/").replace(/^\/root\//, "~/"); }

  function ranExposure(r) {
    // kind -> {sent: bool, names: [..]}
    var ex = {};
    function note(label, sent) {
      var k = ranKind(label); if (!k) return;
      var e = ex[k] || (ex[k] = { sent: false, names: [], readNames: [] });
      if (sent) e.sent = true;
      var nm = str(label), list = sent ? e.names : e.readNames;
      if (nm && list.indexOf(nm) === -1 && list.length < 6) list.push(nm);
    }
    arr(r.stolen).forEach(function (x) { note(x.secret, true); });
    arr(r.findings).forEach(function (f) {
      if (f.rule !== "SECRET_READ" || str(f.severity).toLowerCase() === "info") return;
      var m = /^Opened (.+?) \(/.exec(str(f.title));
      note(m ? m[1] : f.title, false);
    });
    var tr = r.trace || {};
    arr(tr.events).forEach(function (e) {
      if (e.lane !== "secrets" || str(e.severity).toLowerCase() === "info") return;
      arr(e.secrets).forEach(function (s) { note(s, false); });
    });
    // name what was sent; fall back to what was only read
    Object.keys(ex).forEach(function (k) { if (!ex[k].names.length) ex[k].names = ex[k].readNames; });
    return ex;
  }

  function ranItems(r, verdictCls) {
    var findings = arr(r.findings), steps = arr(r.steps);
    var ex = ranExposure(r);
    var by = function (rule) { return findings.filter(function (f) { return f.rule === rule; }); };
    var now = [], then = [], prevent = [];
    var how = function (k) { return ex[k].sent ? "sent out" : "read (not seen leaving; treat it as taken)"; };
    var named = function (k) { return ex[k].names.join(", "); };
    var bad = verdictCls !== "is-ok";

    if (bad) now.push({ key: "isolate", t: "Take this machine off the network and do the rest from a different, clean device",
      d: "A stealer or backdoor may still be running. Don't log in to anything important on it until it's reinstalled." });
    if (bad) now.push({ key: "work", t: "If this was a work laptop, tell your security team now",
      d: "Don't try to clean it yourself. People hit by this campaign have committed the malware into their employer's repos." });
    if (ex.wallet) now.push({ key: "wallet", hot: true, t: "Move funds out of your crypto wallets to a new wallet with a new seed phrase",
      d: named("wallet") + (ex.wallet.names.length > 1 ? " were " : " was ") + (ex.wallet.sent ? "sent out" : "read") + ". Create the new wallet on a clean device; never import the old seed phrase again." });
    if (ex.aws) now.push({ key: "aws", hot: true, t: "Rotate your AWS access keys",
      d: "IAM → Users → Security credentials: create a new key, then deactivate and delete the old one. Check CloudTrail for any use since the day you ran the repo. Your keys were " + how("aws") + "." });
    if (ex.github) now.push({ key: "github", hot: true, t: "Revoke your GitHub tokens",
      d: "github.com/settings/tokens: revoke and recreate them, then review github.com/settings/security-log. " + named("github") + (ex.github.names.length > 1 ? " were " : " was ") + (ex.github.sent ? "sent out." : "read.") });
    if (ex.ssh) now.push({ key: "ssh", hot: true, t: "Replace your SSH keys",
      d: "Make a new key pair. Remove the old public key from github.com/settings/keys, GitLab, Bitbucket and every server's ~/.ssh/authorized_keys. Your private key was " + how("ssh") + "." });
    if (ex.apikeys) now.push({ key: "apikeys", hot: true, t: "Rotate the API keys and database passwords in your other projects' .env files",
      d: named("apikeys") + ": rotate each one in its provider's dashboard and check usage and billing since you ran the repo." });
    if (ex.browser) now.push({ key: "browser", hot: true, t: "Change the passwords saved in your browser, starting with email, banking and work sign-in",
      d: "Saved browser passwords were " + how("browser") + ". Sign out of all sessions and turn on two-factor sign-in where it's off." });
    if (ex.npm) now.push({ key: "npm", hot: true, t: "Revoke your npm token",
      d: "npmjs.com → Access Tokens. Check that no new versions of your packages were published." });
    if (ex.history) now.push({ key: "history", t: "Rotate any token you ever typed or pasted into a terminal",
      d: "Shell history was " + how("history") + ". ~/.bash_history and ~/.zsh_history often hold tokens from export or curl -H commands." });

    by("PERSISTENCE").forEach(function (f, i) {
      var file = tildePath((f.evidence || {}).file) || str(f.title);
      var t, d;
      if (/\.(bashrc|profile|bash_profile|zshrc)$/.test(file)) { t = "Remove the line it added to " + file; d = "Open the file and delete anything you didn't write, usually a node, curl or python command near the end. It runs every time you open a terminal."; }
      else if (/gitconfig|\.config\/git/.test(file)) { t = "Remove core.hooksPath and core.fsmonitor from " + file; d = "Run git config --global --list. Those settings run code on every git command."; }
      else if (/authorized_keys/.test(file)) { t = "Remove keys you don't recognise from " + file; d = "A new key there lets someone log in to this machine over SSH."; }
      else if (/cron/.test(file)) { t = "Remove cron jobs you didn't add"; d = "Run crontab -l and check " + file + "."; }
      else if (/autostart|systemd/.test(file)) { t = "Remove the autostart entry at " + file; d = "It starts the malware again after a reboot or log-in."; }
      else { t = "Undo the change to " + file; d = "It was changed so the code runs again later."; }
      then.push({ key: "persist-" + i, hot: true, t: t, d: d });
    });
    var swaps = by("BINARY_SWAP");
    if (swaps.length) {
      var sf = swaps.map(function (f) { return tildePath((f.evidence || {}).file || (f.evidence || {}).path); }).filter(Boolean);
      then.push({ key: "swap", hot: true, t: "Check ~/.pyenv/shims and ~/.local/bin for replaced tools; reinstall pyenv",
        d: (sf.length ? "Replaced here: " + sf.slice(0, 4).join(", ") + ". " : "") + "Also check your Homebrew bin folder. The Binance theft (Oct 2026) hid this way: a pyenv executable was swapped for a malicious one." });
    }
    var dropped = by("DROPPED_FILE").map(function (f) { return tildePath((f.evidence || {}).file); }).filter(Boolean);
    if (dropped.length) then.push({ key: "dropped", t: "Delete the files it wrote outside the project",
      d: dropped.slice(0, 5).join(", ") + (dropped.length > 5 ? " and " + (dropped.length - 5) + " more" : "") + "." });
    if (by("REMOTE_CODE").length || by("DOWNLOADER").length) then.push({ key: "remote", hot: true, t: "Assume a second stage was installed",
      d: "It downloaded and ran more code that Burner couldn't follow. In this campaign that's usually a backdoor with remote access, so cleaning by hand isn't reliable." });
    if (by("SANDBOX_DIED").length) then.push({ key: "died", t: "Treat it as worse than this report shows",
      d: "It crashed Burner's sandbox, so the run was cut short and it may have done more than Burner saw." });
    var dests = {};
    arr(r.stolen).forEach(function (x) { var d = str(x.sent_to || x.dst); if (d) dests[d] = true; });
    by("NETWORK").forEach(function (f) {
      var e = f.evidence || {}, host = str(e.dest), hp = host + (e.port ? ":" + e.port : "");
      if (!host || dests[host] || dests[hp]) return;
      dests[hp] = true;
    });
    var dl = Object.keys(dests);
    if (bad && dl.length) then.push({ key: "logs", t: "Search your firewall, DNS and proxy logs for these destinations",
      d: dl.slice(0, 6).join(" · ") + ". Any hit shows when the real theft happened." });
    if (bad) then.push({ key: "reimage", t: "Reinstall the operating system once your accounts are safe",
      d: "This campaign's stealers often leave a backdoor behind. A clean reinstall is the only fix you can trust." });
    if (bad && r.abuse_kit) then.push({ key: "report", t: "Report the repo and the recruiter",
      d: "The takedown kit further down is prefilled with the indicators from this scan." });

    var usedVsCode = steps.some(function (s) { return /vs ?code|folder ?open/i.test(str(s.name)); }) &&
      (arr(r.stolen).some(function (x) { return /vs ?code|folder ?open/i.test(str(x.step)); }) ||
       findings.some(function (f) { return /vs ?code|folder ?open/i.test(str(f.title) + " " + str((f.evidence || {}).step)); }));
    prevent.push({ key: "vscode", hot: usedVsCode, tag: usedVsCode ? "This repo used it" : null, t: "Turn off VS Code automatic tasks: \"task.allowAutomaticTasks\": \"off\"",
      d: "And open unfamiliar repos in Restricted Mode (don't click \"Trust\"). A folderOpen task runs the moment you trust the folder." });
    prevent.push({ key: "vm", t: "Run take-homes in a throwaway VM, never on the laptop with your keys and wallets",
      d: "The FBI's advice: if a pre-employment test needs you to run code, insist on a virtual machine. Burner does that for you and shows what the code did." });
    prevent.push({ key: "verify", t: "Verify the recruiter through the company's own website before running anything",
      d: "Be wary of pressure to run code before a real interview, of Telegram or Discord handoffs, and of crypto-heavy roles." });
    if (ex.wallet) prevent.push({ key: "hw", t: "Keep crypto in a hardware wallet, not in browser extensions on your dev machine", d: "" });
    if (ex.aws) prevent.push({ key: "sso", t: "Use short-lived cloud credentials (AWS SSO) instead of keys in ~/.aws/credentials", d: "" });

    return { now: now, then: then, prevent: prevent };
  }

  function cleanItems() {
    return [
      { key: "vm", t: "Run it in a throwaway VM, not on the laptop with your keys and wallets",
        d: "This scan saw nothing bad in one run. Payloads can wait for a date, a user action or a real reply from the attacker." },
      { key: "vscode", t: "Turn off VS Code automatic tasks: \"task.allowAutomaticTasks\": \"off\"",
        d: "And open unfamiliar repos in Restricted Mode (don't click \"Trust\")." },
      { key: "read", t: "Read package.json scripts and .vscode/tasks.json before npm install",
        d: "Look for preinstall / postinstall / prepare hooks and anything that runs on folderOpen." },
      { key: "verify", t: "Verify the recruiter through the company's own website",
        d: "Be wary of pressure to run code before a real interview, Telegram or Discord handoffs, and crypto-heavy roles." },
      { key: "keys", t: "Keep wallets and long-lived cloud keys off the machine you test on", d: "" }
    ];
  }

  function renderRanChecklist(r, id, verdictCls, secNum, nothingRan) {
    var storeKey = "burner:ran:" + id, state = {};
    try { state = JSON.parse(localStorage.getItem(storeKey) || "{}") || {}; } catch (e) { state = {}; }
    function save() { try { localStorage.setItem(storeKey, JSON.stringify(state)); } catch (e) { /* storage blocked */ } }
    var clean = verdictCls === "is-ok" || nothingRan;
    var groups = clean ? [{ key: "before", name: "Before you run any take-home", items: cleanItems() }] : (function () {
      var it = ranItems(r, verdictCls);
      return [{ key: "now", name: "Do now", items: it.now }, { key: "then", name: "Then", items: it.then }, { key: "prevent", name: "Prevent next time", items: it.prevent }]
        .filter(function (g) { return g.items.length; });
    })();
    var total = 0;
    groups.forEach(function (g) { total += g.items.length; });
    var doneOut = h("span", { class: "rp-ran-count", "aria-live": "polite" });
    function count() {
      var d = 0;
      groups.forEach(function (g) { g.items.forEach(function (it) { if (state[g.key + ":" + it.key]) d++; }); });
      doneOut.textContent = d + " / " + total + " done";
    }
    var sec = panel(clean ? "Before you run any take-home" : "I already ran it", { num: secNum, eyebrow: "What to do", icon: clean ? "shield" : "key!", id: "ran-card", cls: "rp-ran",
      tags: clean ? etag("plain", "Prevention") : etag("rule", "From what was observed"),
      sub: clean ? "Nothing bad was seen in this run. These habits still protect you from the ones that hide."
        : "If you ran this repo on your own machine, work through this list. Only the items that match what Burner saw are shown." });
    var grid = h("div", { class: "rp-ran-grid" + (groups.length === 1 ? " is-single" : "") });
    var n = 0;
    groups.forEach(function (g) {
      var col = h("div", { class: "rp-ran-col" }, h("h3", { class: "rp-ran-h" }, ml(g.name, g.key === "now" ? "is-hot" : null), h("span", { class: "c", text: String(g.items.length) })));
      var list = h("ol", { class: "rp-ran-list" });
      g.items.forEach(function (it) {
        n += 1;
        var k = g.key + ":" + it.key, cid = "ran-" + g.key + "-" + it.key;
        var box = h("input", { type: "checkbox", id: cid, class: "rp-ran-box" });
        box.checked = !!state[k];
        box.addEventListener("change", function () { if (box.checked) state[k] = 1; else delete state[k]; save(); count(); li.classList.toggle("is-done", box.checked); });
        var li = h("li", { class: "rp-ran-item" + (it.hot ? " is-hot" : "") + (box.checked ? " is-done" : "") },
          box,
          h("label", { for: cid },
            h("span", { class: "rp-ran-n", text: pad2(n) }),
            h("span", { class: "rp-ran-t", text: it.t }),
            it.tag ? etag("bad", it.tag) : null,
            it.d ? h("span", { class: "rp-ran-d", text: it.d }) : null));
        list.appendChild(li);
      });
      col.appendChild(list);
      grid.appendChild(col);
    });
    sec.appendChild(h("div", { class: "rp-ran-top" }, doneOut, h("span", { class: "rp-ran-hint no-print", text: "Ticks are saved in this browser only." })));
    sec.appendChild(grid);
    sec.appendChild(h("p", { class: "rp-note rp-ran-src" }, "Based on guidance from ",
      RAN_SOURCES.map(function (s, i) { return [i ? " and " : null, h("a", { href: s.url, target: "_blank", rel: "noopener noreferrer", text: s.name })]; }),
      ". Burner can only list what it saw in one run; when in doubt, treat the machine as compromised."));
    count();
    return sec;
  }

  var chartInstances = [], motionIO = null;
  function destroyCharts() {
    chartInstances.forEach(function (c) { try { c.destroy(); } catch (e) { /* already gone */ } });
    chartInstances = [];
    donuts = [];
    if (motionIO) { motionIO.disconnect(); motionIO = null; }
  }
  // the stamp thunk / bars burning play once, when each block first scrolls into view; the resting state is the final frame
  function armMotion(els) {
    if (reduced() || !("IntersectionObserver" in window)) return;
    motionIO = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        if (!e.isIntersecting) return;
        var t = e.target;
        motionIO.unobserve(t);
        t.classList.add("is-live");
        setTimeout(function () { t.classList.remove("is-live"); }, 3200);
      });
    }, { threshold: 0.12 });
    els.forEach(function (el) { if (el) motionIO.observe(el); });
  }
  function mountChart(fn) {
    try { var inst = fn(); if (inst && inst.destroy) chartInstances.push(inst); return true; } catch (e) {
      if (window.console) console.warn("chart failed", e);
      return false;
    }
  }

  var STAMP = { "is-bad": "Malicious", "is-warn": "Suspicious", "is-ok": "Nothing observed" };
  function stamp(cls, id, word) {
    return h("div", { class: "rp-stamp " + cls, "aria-hidden": "true" },
      mark(cls === "is-bad" ? "vm-burning" : cls === "is-warn" ? "vm" : "shield", cls === "is-bad" ? "is-hot" : null),
      h("span", { class: "rp-stamp-in" },
        h("span", { class: "rp-stamp-top", text: "Burner · rule verdict" }),
        h("span", { class: "rp-stamp-word" + ((word || STAMP[cls]).length > 10 ? " is-long" : ""), text: word || STAMP[cls] }),
        h("span", { class: "rp-stamp-bot", text: "case " + id })));
  }
  // one row of the redaction ledger: a fake secret, the ink bar over it, and where it went
  function rxRow(g, i, hot, quiet) {
    return h("li", { class: "rx " + (hot ? "is-burnt" : "is-cold"), style: "--i:" + i },
      h("span", { class: "rx-n", text: pad2(i + 1) }),
      h("span", { class: "rx-id" }, h("span", { class: "rx-name", text: str(g.secret) }), g.from_file ? h("span", { class: "rx-file", text: str(g.from_file) }) : null),
      h("span", { class: "rx-bar" }, h("span", { class: "rx-ink", "aria-hidden": "true" }),
        hot ? h("span", { class: "rx-dest" }, g.dests.map(function (d) {
          return h("span", { class: "rx-d" }, h("span", { class: "rx-arrow", "aria-hidden": "true", text: "→ " }), h("span", { text: d.d }),
            d.enc ? h("em", { text: "encoded" }) : null);
        })) : h("span", { class: "visually-hidden", text: "not taken" })),
      h("span", { class: "rx-step" }, hot ? (g.steps.length ? g.steps.join(", ") : "sent") : quiet ? h("span", { class: "rx-ok", text: "intact" }) : "not taken"));
  }

  // ---- v5: step source + output tail, "what this run covered", VM deletion receipt
  var STEP_SOURCE = { recruiter: ["warn", "Recruiter asked"], user: ["plain", "You asked"] };
  function stepTail(tail) {
    var t = printable(tail).replace(/\s+$/, "");
    if (!t) return null;
    var lines = t.split("\n").length;
    return h("details", { class: "rp-tail" },
      h("summary", null, ml("Output"), h("span", { class: "rp-tail-n", text: "last " + plural(lines, "line") })),
      h("pre", { class: "rp-tail-pre", text: t }));
  }
  function utcClock(iso) {
    var d = new Date(str(iso));
    return isNaN(d) ? str(iso) : d.toISOString().slice(11, 19) + " UTC";
  }
  function fmtDur(sec) {
    sec = Math.max(0, Math.round(Number(sec) || 0));
    if (sec < 90) return sec + " s";
    var m = Math.round(sec / 60);
    return m < 60 ? m + " min" : Math.floor(m / 60) + " h" + (m % 60 ? " " + (m % 60) + " min" : "");
  }
  function usd4(v) { return v == null ? "" : Number(v) < 0.0001 && Number(v) > 0 ? "<$0.0001" : "$" + Number(v).toFixed(4); }
  var NOT_TRIED = "Waits longer than 45 days · clicks in a browser · languages other than Node and Python";
  var COV_OUT = { "kept running": "ok", finished: "plain", crashed: "warn", "not found": "warn" };
  function renderCoverage(r, secNum, amber) {
    var cov = r.coverage && typeof r.coverage === "object" ? r.coverage : null;
    var env = r.env_setup && typeof r.env_setup === "object" ? r.env_setup : null;
    var fetchInfo = r.fetch && typeof r.fetch === "object" && !Array.isArray(r.fetch) ? r.fetch : null;
    if (!cov && !env && !fetchInfo) return null;   // reports from before coverage existed
    var started = cov ? !!cov.started : null;
    var sec = panel("What this run covered", { num: secNum, eyebrow: "Coverage", icon: "laptop", id: "coverage-card", cls: "rp-cov" + (amber ? " is-amber" : ""),
      tags: etag("observed", "Observed") });
    if (cov) {
      sec.appendChild(h("p", { class: "rp-cov-status " + (started && !amber ? "is-ok" : "is-warn") },
        h("span", { class: "rp-cov-dot", "aria-hidden": "true" }),
        h("b", { text: started ? "The app started." : "The app never started." }),
        cov.reason ? h("span", { text: " " + printable(cov.reason) }) : null));
    }
    var grid = h("div", { class: "rp-cov-grid" });
    var covSteps = arr(cov && cov.steps);
    if (covSteps.length) {
      grid.appendChild(h("div", { class: "rp-cov-col" }, ml("Steps that count"),
        h("ol", { class: "rp-cov-steps" }, covSteps.map(function (s) {
          var o = str(s.outcome);
          return h("li", null, h("code", { text: str(s.name) }), etag(COV_OUT[o] || "plain", o || "—"),
            h("span", { class: "rp-cov-secs", text: s.secs != null ? Number(s.secs).toFixed(1) + " s" : "" }));
        }))));
    }
    var facts = h("dl", { class: "rp-cov-facts" });
    var fact = function (k, v) { facts.appendChild(h("div", null, h("dt", null, ml(k)), h("dd", null, v))); };
    if (env) {
      var keys = arr(env.keys).map(str);
      fact(".env", [h("span", { text: "Made from " }), h("code", { text: str(env.from) || ".env.example" }),
        h("span", { text: " · " + plural(keys.length, "key") + (env.filled != null ? ", " + env.filled + " filled with fake values" : "") }),
        keys.length ? h("span", { class: "rp-cov-keys mono", text: keys.slice(0, 8).join(" ") + (keys.length > 8 ? " …" : "") }) : null]);
    }
    if (fetchInfo) {
      var removed = arr(fetchInfo.removed).map(str);
      fact("Removed before install", removed.length
        ? h("span", null, removed.map(function (x, i) { return [i ? ", " : null, h("code", { text: x })]; }), h("span", { class: "rp-cov-dim", text: " (registry overrides; installs used the public registry)" }))
        : h("span", { class: "rp-cov-dim", text: "Nothing: no custom registry settings" }));
    }
    fact("Not tried", h("span", { class: "rp-cov-dim", text: NOT_TRIED }));
    grid.appendChild(facts);
    sec.appendChild(grid);
    return sec;
  }
  function vmCheck(id, btn, out) {
    btn.disabled = true;
    out.className = "rp-del-out";
    out.textContent = "Asking Vultr…";
    var fail = function (msg) { out.className = "rp-del-out is-warn"; out.textContent = msg || "Couldn't reach Vultr right now. Try again in a minute."; };
    fetch("/api/scan/" + encodeURIComponent(id) + "/vm-check", { headers: { Accept: "application/json" } }).then(function (res) {
      return res.json().catch(function () { return null; }).then(function (j) { return { status: res.status, j: j }; });
    }).then(function (x) {
      var j = x.j;
      if (j && typeof j.gone === "boolean") {
        var when = j.checked_at ? " · checked " + utcClock(j.checked_at) : "";
        if (j.gone) { out.className = "rp-del-out is-ok"; out.textContent = "Vultr says: instance not found (" + (j.http_status || 404) + ")" + when; }
        else { out.className = "rp-del-out is-warn"; out.textContent = "Vultr says: the instance still exists (HTTP " + str(j.http_status) + ")" + when; }
        if (j.instance_id) out.title = "instance " + str(j.instance_id) + (j.region ? " · " + str(j.region) : "");
      } else if (x.status === 404 && j && !j.detail) fail("No VM on record for this scan.");
      else fail();
    }).catch(function () { fail(); }).then(function () { btn.disabled = false; });
  }
  function renderDeletion(vm, id, live) {
    var del = vm.deletion && typeof vm.deletion === "object" ? vm.deletion : null;
    if (!del && !(live && vm.id)) return null;
    var line = null;
    if (del && del.confirmed_at) line = h("span", { class: "rp-del-line is-ok", text: "Vultr confirmed deleted " + utcClock(del.confirmed_at) + ", HTTP " + str(del.http_status || 404) });
    else if (del) line = h("span", { class: "rp-del-line is-warn", text: "Delete sent " + (del.requested_at ? utcClock(del.requested_at) : "") + "; Vultr hadn't confirmed it yet" + (del.http_status ? " (HTTP " + del.http_status + ")" : "") });
    var out = h("span", { class: "rp-del-out", "aria-live": "polite" });
    var btn = live ? h("button", { type: "button", class: "button button-secondary button-small no-print" }, "Check with Vultr now") : null;
    if (btn) btn.addEventListener("click", function () { vmCheck(id, btn, out); });
    return h("div", { class: "rp-del" },
      h("span", { class: "rp-del-mark", "aria-hidden": "true" }),
      h("div", { class: "rp-del-main" }, line, del && del.check ? h("code", { class: "rp-del-check", text: str(del.check) }) : null, out),
      btn);
  }

  // back to the form with the repo filled in (never auto-starts: a scan rents a VM, the user clicks Burn it)
  function prefillRepo(url, focusCmd) {
    go("/");
    setMode("repo");
    $("repo").value = url;
    requestAnimationFrame(function () {
      $("scan-form").scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "center" });
      if (focusCmd) { $("run-hint").open = true; $("run-cmd").focus({ preventScroll: true }); }
      else $("burn-btn").focus({ preventScroll: true });
    });
  }
  // has the repo moved on since this scan? (server-side git ls-remote of the scanned branch, cached 10 min)
  function checkHead(id, slot, commit, rescanUrl) {
    fetch("/api/scan/" + encodeURIComponent(id) + "/head").then(function (res) { return res.ok ? res.json() : null; }).then(function (j) {
      if (!j || !slot.isConnected) return;
      clear(slot);
      if (j.state === "changed") {
        slot.className = "rp-headcheck is-changed no-print";
        slot.appendChild(h("p", null, h("b", { text: "The repo changed after this scan. " }),
          "This verdict is about commit " + commit.slice(0, 7) + "; the branch is now at " + str(j.now).slice(0, 7) +
          ", and that code hasn't been checked."));
        if (rescanUrl) slot.appendChild(h("button", { type: "button", class: "button button-primary button-small", onclick: function () { prefillRepo(rescanUrl, false); } }, "Burn the new version"));
      } else if (j.state === "gone") {
        slot.className = "rp-headcheck is-gone no-print";
        slot.appendChild(h("p", null, h("b", { text: "The repo or branch is gone now " }),
          "(deleted, made private or renamed). Keep this report: it's the record of what that code did."));
      } else if (j.state === "same") {
        slot.className = "rp-headcheck is-same no-print";
        slot.appendChild(h("p", { text: "Checked just now: the repo still has exactly this commit." }));
      } else return;
      slot.hidden = false;
    }).catch(noop);
  }
  // ready-to-paste messages: warn a group (link defanged so chat apps don't unfurl it), tell security, reply to the recruiter
  // https://github.com/a/b -> hxxps://github[.]com/a/b ; 203.0.113.55:1224 -> 203[.]0[.]113[.]55:1224
  function defang(s) {
    return str(s).replace(/^http(s?):\/\//i, "hxxp$1://")
      .replace(/^((?:hxxps?:\/\/)?)([^/:\s]+)/i, function (_, p, host) { return p + host.replace(/\./g, "[.]"); });
  }
  function shareTexts(r, id, verdictWord, stolen) {
    var url = location.origin + "/r/" + id;
    var src = r.source || {}, repo = str(src.repo || r.target), commit = str(src.commit);
    var kinds = [], dests = [];
    stolen.forEach(function (x) {
      if (kinds.indexOf(str(x.secret)) < 0) kinds.push(str(x.secret));
      var d = str(x.sent_to || x.dst); if (d && dests.indexOf(d) < 0) dests.push(d);
    });
    var what = kinds.length ? "it took (fake) " + kinds.slice(0, 5).join(", ") + (kinds.length > 5 ? " and more" : "") +
      (dests.length ? " and sent them to " + dests.slice(0, 3).map(defang).join(", ") : "") : str(r.headline).replace(/^Don't run this\.\s*/, "");
    var at = commit ? " (commit " + commit.slice(0, 7) + ")" : "";
    var warn = ["Heads-up: fake-recruiter take-home, don't run it.",
      "Repo: " + defang(repo) + at,
      "Burner ran it in a throwaway VM with fake secrets. Verdict: " + verdictWord + ". " + what.charAt(0).toUpperCase() + what.slice(1) + ".",
      "Full report: " + url].join("\n");
    var ev = r.evidence || {};
    var sec = ["Subject: Fake-recruiter take-home flagged " + verdictWord + " by Burner", "",
      "A recruiter sent me a take-home repo. Burner ran it in an isolated throwaway VM full of fake credentials.",
      "Verdict: " + verdictWord + ". " + str(r.headline),
      "Repo: " + repo + (commit ? " (branch " + (str(src.branch) || "default") + ", commit " + commit + ")" : ""),
      kinds.length ? "Fake secrets it took: " + kinds.join(", ") : null,
      dests.length ? "Sent to: " + dests.join(", ") : null,
      "Did I run it on my own machine? [yes / no: fill in]",
      "Report: " + url,
      ev.manifest_sha256 ? "Evidence manifest SHA-256: " + ev.manifest_sha256 : null].filter(function (x) { return x !== null; }).join("\n");
    var reply = "Thanks for sending this over. I run every take-home in an isolated sandbox before opening it, and this one " +
      (verdictWord === "MALICIOUS" ? "tried to collect credentials and send them to an outside server" : "did things a take-home has no reason to do") +
      ", so I won't be running it. If the role is real, please send the task as a written spec instead.";
    return [{ k: "group", title: "Warn a group chat", note: "The repo link is defanged so chat apps don't preview it.", text: warn },
      { k: "security", title: "Tell your security team", note: "Commit, destinations and the evidence hash they'll ask for.", text: sec },
      { k: "recruiter", title: "Reply to the recruiter", note: "Polite, no details they could use.", text: reply }];
  }

  function renderReport(r, id) {
    destroyCharts();
    var out = $("report"); clear(out);
    out.classList.add("rp");
    var verdict = str(r.verdict).toUpperCase();
    // INCONCLUSIVE (nothing ran) is amber, never the green "nothing observed"
    var inconclusive = verdict === "INCONCLUSIVE";
    var cls = verdict === "MALICIOUS" ? "is-bad" : verdict === "SUSPICIOUS" || inconclusive ? "is-warn" : "is-ok";
    out.setAttribute("data-verdict", cls);
    var findings = arr(r.findings), bait = arr(r.bait), steps = arr(r.steps), network = arr(r.network);
    // a "medium" EXFIL finding = only values from the project's own .env reached that host (an app sending its Stripe
    // key to Stripe is normal): worth a look, not theft. Those captures stay out of the "stolen" ledger and numbers.
    var envOnly = {};
    findings.forEach(function (f) { if (f.rule === "EXFIL" && str(f.severity).toLowerCase() === "medium" && f.evidence && f.evidence.sent_to) envOnly[str(f.evidence.sent_to)] = true; });
    var envSent = arr(r.stolen).filter(function (x) { return envOnly[str(x.sent_to)]; });
    var stolen = arr(r.stolen).filter(function (x) { return !envOnly[str(x.sent_to)]; });
    if (envSent.length) r = Object.assign({}, r, { stolen: stolen });   // checklist + charts see real theft only
    var vm = r.vm || null;
    // INCONCLUSIVE, two kinds: the app never started, or it checked for a sandbox and then did nothing (evasive)
    var cov = r.coverage && typeof r.coverage === "object" ? r.coverage : null;
    var evasive = inconclusive && findings.length > 0 && findings.every(function (f) { return f.rule === "SANDBOX_CHECK"; });
    var covReason = inconclusive && cov && cov.reason ? printable(cov.reason) : "";
    var groups = groupStolen(stolen);
    var takenNames = {};
    stolen.forEach(function (x) { takenNames[str(x.secret)] = true; });
    var takenCount = Object.keys(takenNames).length;
    var n = 0;
    var num = function () { n += 1; return pad2(n); };

    // toolbar
    var url = location.origin + "/r/" + id;
    var linkCopied = h("span", { class: "copied", text: "Link copied", hidden: true });
    out.appendChild(h("div", { class: "report-bar rp-bar no-print" },
      h("div", { class: "report-bar-left" },
        h("button", { type: "button", class: "button button-secondary", onclick: function () { go("/"); } }, "← Scan another"),
        S && S.events.length ? h("button", { type: "button", class: "button button-secondary", onclick: function () { setView("run"); } }, "Replay the run") : null),
      h("div", { class: "report-bar-right" }, linkCopied,
        h("button", { type: "button", class: "button button-secondary", onclick: function () { copyText(url, linkCopied); } }, "Copy share link"),
        h("button", { type: "button", class: "button button-secondary", onclick: function () { window.print(); } }, "Print / save as PDF"))));

    // dossier head: case line, stamp, headline (never the word "safe")
    var caseBits = ["Case " + id];
    if (vm && vm.region) caseBits.push(str(vm.region));
    if (vm && vm.plan) caseBits.push(str(vm.plan));
    if (r.total_secs != null) caseBits.push("T+" + r.total_secs + " s");
    if (r.llm_usage && r.llm_usage.calls) {
      var tok = (Number(r.llm_usage.prompt_tokens) || 0) + (Number(r.llm_usage.completion_tokens) || 0);
      caseBits.push(plural(Number(r.llm_usage.calls), "AI call") + " · " + tok.toLocaleString() + " tok");
    }
    var word = inconclusive ? "Inconclusive." : cls === "is-bad" ? "Malicious." : cls === "is-warn" ? "Suspicious." : "No malicious behaviour observed.";
    tabTitle((inconclusive ? "Inconclusive" : cls === "is-bad" ? "Malicious" : cls === "is-warn" ? "Suspicious" : "Nothing observed") +
      (r.target ? " · " + shortTarget(r.target) : ""));
    var aiDown = arr(r.llm_errors).map(function (x) { return str(x.step); }).filter(Boolean);
    var hl = str(r.headline), m = /^(.{4,48}?[.!])\s+(.+)$/.exec(hl);
    var title = h("h1", { class: "rp-title" + (m ? "" : " is-plain"), id: "report-title", tabindex: "-1" },
      h("span", { class: "visually-hidden", text: word + " " }),
      m ? [h("span", { class: "rp-lead", text: m[1] }), " ", h("span", { class: "rp-rest", text: m[2] })] : (hl || word));
    var bench = r.benchmark || null;
    // the exact code that ran: a verdict covers one commit, and attackers swap code after a clean scan
    var src = r.source && typeof r.source === "object" ? r.source : null;
    var srcCommit = src && /^[0-9a-f]{40}$/.test(str(src.commit)) ? str(src.commit) : "";
    var srcRepo = src && /^https:\/\//.test(str(src.repo)) ? str(src.repo) : "";
    var rescanUrl = srcRepo ? srcRepo + (src.branch_from_link && src.branch ? "/tree/" + str(src.branch) : "") :
      (/^https:\/\//.test(str(r.target)) ? str(r.target) : "");
    var headCheck = h("div", { class: "rp-headcheck no-print", hidden: true, "aria-live": "polite" });
    var codeFact = srcCommit ? [h("dt", { text: "Code scanned" }), h("dd", { class: "mono" },
      h("span", { text: (str(src.branch) || "default branch") + " @ " }), h("span", { title: srcCommit, text: srcCommit.slice(0, 7) }),
      src.committed_at ? h("span", { class: "rp-dim", text: " · committed " + str(src.committed_at).slice(0, 10) }) : null)] : null;
    var head = h("section", { class: "verdict rp-head " + cls, role: "status", "aria-labelledby": "report-title" },
      h("div", { class: "rp-head-main" },
        h("p", { class: "rp-case" }, caseBits.map(function (b, i) { return [i ? h("span", { class: "sep", "aria-hidden": "true", text: "·" }) : null, h("span", { text: b })]; })),
        title,
        cls === "is-ok" ? h("p", { class: "rp-caveat", text: "Burner didn't see it steal, persist or phone home. That's evidence from one run, not a guarantee." }) : null,
        covReason ? h("p", { class: "rp-caveat rp-why-amber" }, h("b", { text: evasive ? "It went quiet. " : "Why: " }), covReason) : null,
        r.replay ? h("p", { class: "rp-caveat", text: str(r.replay.note) || "A recorded real scan, replayed." }) : null,
        aiDown.length ? h("p", { class: "rp-caveat", text: "Vultr's AI was unavailable for " + aiDown.join(", ") + " on this scan, so Burner carried on with rules only. The verdict is unaffected: rules decide it." }) : null,
        inconclusive && rescanUrl && !r.replay ? h("p", { class: "rp-next no-print" },
          h("button", { type: "button", class: "button button-primary button-small", onclick: function () { prefillRepo(rescanUrl, true); } },
            "Run it again with the command they gave you"),
          h("span", { class: "rp-dim", text: " Burner fills in the repo; you add the exact command from the recruiter's instructions." })) : null,
        headCheck,
        h("dl", { class: "rp-facts" },
          r.target ? [h("dt", { text: "Target" }), h("dd", { class: "mono", title: str(r.target), text: str(r.target) })] : null,
          codeFact,
          bench && bench.technique ? [h("dt", { text: "Technique" }), h("dd", { text: str(bench.technique) })] : null,
          [h("dt", { text: "Judged by" }), h("dd", null, etag("rule", "Fixed rules"), " ", etag("observed", "Observed behaviour"))])),
      stamp(cls, id, inconclusive ? "Inconclusive" : null));
    out.appendChild(head);
    if (srcCommit && !r.replay) checkHead(id, headCheck, srcCommit, rescanUrl);
    renderPrecheckReport(out, r.precheck);   // "Before it ran: N warning signs" (warnings only)

    // the run in numbers: big tabular numerals between hairlines
    var destSet = {};
    stolen.forEach(function (x) { destSet[str(x.sent_to || x.dst)] = true; });
    var dests = Object.keys(destSet).filter(Boolean);
    var rawIps = network.filter(function (x) { return x.raw_ip; }).length;
    var total = bait.length || takenCount;
    out.appendChild(h("div", { class: "kpis rp-kpis", role: "group", "aria-label": "Key numbers" },
      kpi("Fake secrets stolen", h("span", null, String(takenCount), h("small", { text: "/" + total })),
        total ? plural(total, "fake secret") + " planted" : "none planted", takenCount ? "is-hot" : "is-calm", total ? burnMeter(takenCount, total) : null, "key"),
      dests.length ? kpi("Sent to", String(dests.length), plural(dests.length, "destination") + (rawIps ? " · " + rawIps + " raw IP" : ""), "is-hot", null, "globe")
        : kpi("Network contacts", String(network.length), "none received secrets", null, null, "globe"),
      kpi("Steps run", String(steps.length), "like a candidate would", null, null, "laptop"),
      kpi("VM alive", vm && vm.lifetime_secs != null ? unit(vm.lifetime_secs, " s") : "—",
        vm ? (vm.destroyed ? "then destroyed" : vm.id ? "kept (dev)" : "reused dev VM") : "no VM data", null, null, "ash"),
      kpi("Scan took", r.total_secs != null ? unit(r.total_secs, " s") : "—", "paste to verdict", null, null, "clock"),
      kpi("Cost", vm && vm.cost_usd_prorated != null ? "$" + Number(vm.cost_usd_prorated).toFixed(4) : "—",
        vm && vm.cost_usd_max != null ? "≤ $" + Number(vm.cost_usd_max).toFixed(4) + " billed hourly" : "Vultr VM, prorated", null, null, "bars")));

    // AI explanation: a quiet margin note, clearly not the verdict
    if (r.explanation) {
      out.appendChild(h("aside", { class: "rp-ai", "aria-label": "AI explanation" },
        h("div", { class: "rp-ai-side" }, etag("ai", "AI explanation"), h("span", { class: "rp-ai-note", text: "Written by an AI after the fact. It can't change the verdict." })),
        h("p", { class: "rp-ai-text", text: str(r.explanation) })));
    }

    // what this run covered: up top when the run was inconclusive (it's the answer), otherwise after the steps
    var hasCov = !!(cov || (r.env_setup && typeof r.env_setup === "object") || (r.fetch && typeof r.fetch === "object" && !Array.isArray(r.fetch)));
    if (inconclusive && hasCov) out.appendChild(renderCoverage(r, num(), true));

    // what it stole: the redaction ledger
    var nothingRan = inconclusive && !stolen.length;
    var sec = panel(stolen.length ? "What it stole" : nothingRan ? "What it stole: unknown" : "What it stole: nothing", { num: num(), eyebrow: "Evidence", id: "stolen-card", icon: stolen.length ? "key!" : "key",
      tags: [etag("observed", "Observed"), etag("fake", "Fake secrets")],
      sub: stolen.length ? groups.length + " of " + (bait.length || groups.length) + " fake secrets left the sandbox. Each bar burned open shows where it went."
        : nothingRan && evasive ? "It looked for signs of a sandbox, then did nothing Burner could see. Quiet is not the same as clean."
        : nothingRan ? "The repo's code never ran, so there was nothing to watch. That is not the same as clean."
        : bait.length ? "None of the " + bait.length + " fake secrets Burner planted left the sandbox." : "Nothing was seen leaving the sandbox." });
    if (envSent.length) {
      var envDests = Object.keys(envOnly);
      sec.appendChild(h("p", { class: "rp-envsent" }, etag("warn", "Worth a look"),
        h("span", { text: " Values from the project's own .env were sent to " + envDests.join(", ") + ". Fine if that's the service the key is for (a Stripe key going to Stripe); not counted as theft." })));
    }
    var untouched = bait.filter(function (b) { return !takenNames[str(b.kind)]; });
    var ledger = h("ol", { class: "rx-list", "aria-label": "Fake secrets planted in the sandbox" });
    groups.forEach(function (g, i) { ledger.appendChild(rxRow(g, i, true)); });
    untouched.forEach(function (b, i) { ledger.appendChild(rxRow({ secret: b.kind, from_file: b.file }, groups.length + i, false, !stolen.length)); });
    if (ledger.children.length) {
      sec.appendChild(h("div", { class: "rx-head", "aria-hidden": "true" }, ml("#"), ml("Fake secret · planted at"), ml(stolen.length ? "Redaction · burned open = sent to" : "Redaction"), ml("During step")));
      sec.appendChild(ledger);
    }
    if (stolen.length) {
      var ev = h("details", { class: "rp-captures" },
        h("summary", null, ml("Captured on our fake internet"), h("span", { class: "rp-count", text: plural(stolen.length, "capture") })));
      var body = h("div", { class: "cap-body" });
      stolen.forEach(function (x) {
        body.appendChild(h("div", { class: "rp-capture" },
          h("div", { class: "cap-head" },
            h("b", { text: str(x.secret) }), h("span", { "aria-hidden": "true", text: "→" }), h("code", { text: str(x.sent_to || x.dst) }),
            h("span", { class: "mono", text: [x.method, x.url_path].filter(Boolean).join(" ") + (x.proto ? " (" + x.proto + ")" : "") }),
            x.bytes ? etag("plain", fmtBytes(x.bytes)) : null,
            x.encoded ? etag("warn", "found after decoding") : null,
            x.step ? etag("plain", "during " + x.step) : null),
          highlight(x.snippet, x.value),
          h("div", { class: "cap-legend" }, h("span", { class: "sw" }), "fake value planted by Burner")));
      });
      ev.appendChild(body);
      sec.appendChild(ev);
    }
    out.appendChild(sec);

    // "I already ran it": what to do now, built from what was observed (prevention list for a clean run)
    try { out.appendChild(renderRanChecklist(r, id, cls, num(), nothingRan)); } catch (e) { if (window.console) console.warn("checklist failed", e); }

    // exhibits
    var chartsCard = renderChartsPanel(r, num());
    if (chartsCard) out.appendChild(chartsCard.el);

    // campaign + recruiter
    var pair = h("div", { class: "rp-pair" });
    var cp = r.campaign;
    var pairNum = null;
    if (cp && cp.similarity) {
      var sim = str(cp.similarity).toLowerCase();
      pairNum = num();
      var cc = panel("Behaves like " + (str(cp.campaign) || "a known campaign"), { num: pairNum, eyebrow: "Campaign match", icon: "globe", cls: "rp-campaign sim-" + sim, id: "campaign-card",
        tags: etag(sim === "high" ? "bad" : sim === "medium" ? "warn" : "plain", sim + " similarity") });
      var inds = arr(cp.indicators);
      if (inds.length) {
        cc.appendChild(h("ol", { class: "rp-inds" }, inds.map(function (x, i) {
          var src = safeUrl(x.source), host = "";
          if (src && src !== "#") { try { host = new URL(src).hostname.replace(/^www\./, ""); } catch (e) { host = "source"; } }
          return h("li", null, h("span", { class: "rp-ind-n", text: "IND-" + pad2(i + 1) }),
            h("div", null, h("b", { text: str(x.what) }), x.why ? h("p", { class: "why", text: str(x.why) }) : null,
              host ? h("a", { class: "rp-src", href: src, target: "_blank", rel: "noopener noreferrer" }, h("span", { class: "visually-hidden", text: "Source: " }), host, " ↗") : null));
        })));
      }
      cc.appendChild(h("p", { class: "rp-note", text: str(cp.note) || "Behavioural similarity to public reports, not attribution." }));
      pair.appendChild(cc);
    }
    var rc = r.recruiter;
    if (rc && ((rc.red_flags && rc.red_flags.length) || rc.lure_score != null || rc.company)) {
      var who = [rc.role, rc.company].filter(Boolean).join(" at ");
      var rs = panel("Recruiter red flags", { num: pairNum ? null : num(), eyebrow: "The message", icon: "stamp", id: "recruiter-card", cls: "rp-recruiter", tags: etag("ai", "Read by AI") });
      if (who) rs.appendChild(h("p", { class: "rp-claimed" }, ml("Claimed to be"), h("span", { text: who })));
      if (rc.lure_score != null) {
        var score = Math.max(0, Math.min(10, Number(rc.lure_score) || 0));
        var ticks = h("span", { class: "rp-lure-ticks", role: "img", "aria-label": "lure score " + score + " of 10" });
        for (var t = 0; t < 10; t++) ticks.appendChild(h("i", { class: t < score ? "is-on" : null, style: "--i:" + t }));
        rs.appendChild(h("div", { class: "rp-lure" }, h("span", { class: "rp-lure-v" }, String(score), h("small", { text: "/10" })),
          h("span", { class: "rp-lure-k" }, ml("Lure score"), ticks)));
      }
      if (rc.red_flags && rc.red_flags.length) rs.appendChild(h("ol", { class: "rp-flags" }, rc.red_flags.map(function (f, i) {
        return h("li", null, h("span", { class: "rp-flag-n", text: pad2(i + 1) }), h("span", { text: str(f) }));
      })));
      else rs.appendChild(h("p", { class: "rp-empty", text: "No red flags spotted in the message." }));
      pair.appendChild(rs);
    }
    if (pair.children.length === 1) pair.classList.add("is-single");
    if (pair.children.length) out.appendChild(pair);

    if (r.readme_screen && r.readme_screen.unsafe) {
      var rd = panel("The README tries to talk to AI tools", { cls: "rp-warnbox", eyebrow: "Prompt injection", icon: "shield" });
      rd.appendChild(h("p", { class: "rp-empty", text: "The repo's README contains text aimed at AI assistants (prompt injection). Burner's verdict does not depend on an AI, so it can't be talked out of it." }));
      out.appendChild(rd);
    }

    // steps + findings
    var pair2 = h("div", { class: "rp-pair" });
    var stepsNum = steps.length || findings.length ? num() : null;
    if (steps.length) {
      var hot = {};
      stolen.forEach(function (x) { if (x.step) hot[x.step] = true; });
      var ts = panel("What Burner ran", { num: stepsNum, eyebrow: "Procedure", icon: "laptop", id: "steps-card", tags: etag("observed", "Observed"), sub: "Like a candidate would, in this order." });
      ts.appendChild(h("ol", { class: "rp-steps" }, steps.map(function (x, i) {
        var rcTxt = x.rc == null ? "" : x.rc === 137 ? "exit 137 · time limit" : "exit " + x.rc;
        var src = STEP_SOURCE[x.source];
        return h("li", { class: hot[x.name] ? "is-hot" : null },
          h("span", { class: "n", text: pad2(i + 1) }),
          h("div", { class: "rp-step-main" }, h("div", { class: "nm" }, h("span", { text: str(x.name) }), src ? etag(src[0], src[1]) : null),
            x.why ? h("div", { class: "why", text: str(x.why) }) : null,
            x.cmd ? h("code",{ class: "cmd", text: "$ " + x.cmd }) : null,
            hot[x.name] ? h("div", { class: "stolen-in" }, etag("fake", "Secrets left during this step")) : null,
            stepTail(x.tail)),
          h("div", { class: "rt" }, h("span", { text: x.secs != null ? x.secs + " s" : "" }), h("span", { text: rcTxt })));
      })));
      pair2.appendChild(ts);
    }
    var died = findings.filter(function (f) { return f.rule === "SANDBOX_DIED"; });
    var other = findings.filter(function (f) { return (f.rule !== "EXFIL" || str(f.severity).toLowerCase() === "medium") && f.rule !== "SANDBOX_DIED"; });
    if (other.length || died.length) {
      var fs = panel("Other findings", { num: steps.length ? null : stepsNum, eyebrow: "Rules that fired", icon: "shield", id: "findings-card", tags: etag("rule", "Rule-based") });
      died.forEach(function (f) {
        fs.appendChild(h("div", { class: "rp-died", role: "note" }, etag("warn", "Sandbox crashed"),
          h("div", null, h("b", { text: str(f.title) }),
            h("p", { text: "The repo crashed Burner's sandbox, so it may have done more than Burner saw. Treat that as a red flag on its own." }))));
      });
      var sevs = ["critical", "high", "medium", "low"];
      sevs.concat(["other"]).forEach(function (sev) {
        var list = other.filter(function (f) { var v = str(f.severity).toLowerCase(); return sev === "other" ? sevs.indexOf(v) === -1 : v === sev; });
        if (!list.length) return;
        fs.appendChild(h("div", { class: "rp-sevgroup" }, h("h3", { class: "rp-sev sev-" + sev }, h("span", { text: sev }), h("span", { class: "c", text: String(list.length) })),
          h("ul", null, list.map(function (f) {
            var look = f.rule === "EXFIL";   // medium EXFIL only: .env values to a host, worth a look
            return h("li", null, h("span", { text: str(f.title) }), look ? etag("warn", "Worth a look") : null, f.rule && !look ? h("code", { class: "rule", text: str(f.rule) }) : null);
          }))));
      });
      pair2.appendChild(fs);
    }
    if (pair2.children.length === 1) pair2.classList.add("is-single");
    if (pair2.children.length) out.appendChild(pair2);
    if (!inconclusive && hasCov) out.appendChild(renderCoverage(r, num(), false));

    // network
    var dnsList = arr(r.dns);
    if (network.length || dnsList.length) {
      var exfilDst = {};
      stolen.forEach(function (x) { exfilDst[str(x.sent_to || x.dst)] = true; });
      var ns = panel("Network contacts", { num: num(), eyebrow: "Fake internet log", icon: "globe", id: "network-card", tags: etag("observed", "Observed"), sub: "Every connection was answered by Burner's fake internet. Nothing reached the real one." });
      if (network.length) {
        var nb = h("tbody");
        network.forEach(function (x) {
          var dp = str(x.dest) + ":" + str(x.port);
          var isHot = exfilDst[dp] || exfilDst[str(x.dest)];
          nb.appendChild(h("tr", { class: isHot ? "is-hot" : null },
            h("td", { "data-l": "Destination" }, h("code", { text: dp }), " ",
              x.raw_ip ? etag("warn", "raw IP") : null, " ", isHot ? etag("bad", "received secrets") : null),
            h("td", { class: "num", "data-l": "Requests", text: str(x.requests) }),
            h("td", { class: "num", "data-l": "Sent", text: fmtBytes(x.bytes_out) }),
            h("td", { class: "mono", "data-l": "Protocol", text: arr(x.protos).filter(function (p) { return p !== "empty"; }).join(", ") }),
            h("td", { "data-l": "Step", text: str(x.step) })));
        });
        ns.appendChild(h("div", { class: "tbl-wrap" }, h("table", { class: "rp-table stack" },
          h("thead", null, h("tr", null, h("th", { text: "Destination" }), h("th", { class: "num", text: "Requests" }), h("th", { class: "num", text: "Sent" }), h("th", { text: "Protocol" }), h("th", { text: "Step" }))), nb)));
      }
      if (dnsList.length) {
        ns.appendChild(h("p", { class: "rp-chiprow" }, ml("DNS lookups"),
          dnsList.map(function (d) { return h("code", { class: "rp-chip", text: str(d) }); })));
      }
      out.appendChild(ns);
    }

    // tell people: three ready-to-paste messages (bad verdicts only)
    if ((cls === "is-bad" || cls === "is-warn") && !inconclusive) {
      var ts = panel("Tell people", { num: num(), eyebrow: "Ready to paste", icon: "globe", id: "tell-card", cls: "rp-tell no-print",
        sub: "The next person this recruiter messages is probably in one of your group chats." });
      var grid = h("div", { class: "rp-tell-grid" });
      shareTexts(r, id, verdict, stolen).forEach(function (t) {
        var done = h("span", { class: "copied", text: "Copied", hidden: true });
        grid.appendChild(h("div", { class: "rp-tell-item", "data-k": t.k },
          h("p", { class: "rp-tell-title", text: t.title }),
          h("p", { class: "rp-tell-note", text: t.note }),
          h("pre", { class: "rp-tell-text", text: t.text }),
          h("div", null, h("button", { type: "button", class: "button button-secondary button-small", onclick: function () { copyText(t.text, done); } }, "Copy"), " ", done)));
      });
      ts.appendChild(grid);
      out.appendChild(ts);
    }

    // report it
    var kit = r.abuse_kit;
    if (kit && cls !== "is-ok") {
      var ks = panel("Report it", { num: num(), eyebrow: "Takedown kit", icon: "stamp", id: "kit-card", cls: "rp-kit", sub: "Prefilled and ready to paste to GitHub, the job board, or your security team." });
      var kitText = str(kit.text);
      var box = h("textarea", { class: "rp-kit-text", readonly: "readonly", rows: Math.min(12, kitText.split("\n").length + 1), "aria-label": "Prefilled abuse report" });
      box.value = kitText;
      var kitCopied = h("span", { class: "copied", text: "Copied", hidden: true });
      var iocCopied = h("span", { class: "copied", text: "Copied", hidden: true });
      var iocs = arr(kit.iocs).map(str);
      var left = h("div", { class: "rp-kit-doc" }, h("div", { class: "rp-kit-docbar" }, ml("abuse-report.txt"), h("span", { class: "rp-kit-docmeta", text: plural(kitText.split("\n").length, "line") })), box,
        h("div", { class: "rp-kit-row no-print" },
          h("button", { class: "button button-primary", type: "button", onclick: function () { copyText(kitText, kitCopied); } }, "Copy report"), kitCopied));
      var right = h("div", { class: "rp-kit-side" });
      if (iocs.length) {
        right.appendChild(h("div", { class: "rp-kit-block" }, ml("Indicators (IOCs)"),
          h("ul", { class: "rp-iocs" }, iocs.map(function (x) { return h("li", null, h("code", { text: x })); })),
          h("div", { class: "no-print" }, h("button", { class: "button button-secondary button-small", type: "button", onclick: function () { copyText(iocs.join("\n"), iocCopied); } }, "Copy IOCs"), " ", iocCopied)));
      }
      var where = arr(kit.where).filter(function (w) { return safeUrl(w.url) && safeUrl(w.url) !== "#"; });
      if (where.length) {
        right.appendChild(h("div", { class: "rp-kit-block" }, ml("Where to send it"),
          h("ul", { class: "rp-where" }, where.map(function (w) {
            return h("li", null, h("a", { href: safeUrl(w.url), target: "_blank", rel: "noopener noreferrer" }, h("span", { text: str(w.name) || str(w.url) }), h("span", { class: "arr", "aria-hidden": "true", text: "↗" })));
          }))));
      }
      ks.appendChild(h("div", { class: "rp-kit-grid" + (right.children.length ? "" : " is-single") }, left, right.children.length ? right : null));
      out.appendChild(ks);
    }

    // the Vultr bill: every service this scan used, what it did, what it cost
    var bill = r.vultr_bill || null;
    if (bill && arr(bill.items).length) {
      var bs = panel("What Vultr did", { num: num(), eyebrow: "Vultr bill", icon: "bars", id: "bill-card", cls: "rp-bill",
        tags: etag("observed", "Recorded"),
        sub: "Every Vultr service this scan used, in order, with what it cost." + (bill.total_usd != null ? " Total: $" + Number(bill.total_usd).toFixed(4) + "." : "") });
      var money = function (u, note) { return u == null ? (note || "—") : u < 0.0001 ? "<$0.0001" : "$" + Number(u).toFixed(4); };
      var tb = h("tbody");
      arr(bill.items).forEach(function (it) {
        tb.appendChild(h("tr", null,
          h("th", { scope: "row" }, h("span", { class: "rp-bill-svc", text: str(it.service) })),
          h("td", null, h("span", { text: str(it.what) }), it.model ? h("code", { class: "rp-bill-model", text: str(it.model) }) : null),
          h("td", { class: "mono", text: str(it.detail || "") }),
          h("td", { class: "mono rp-bill-usd", text: money(it.usd, it.note) })));
      });
      if (bill.total_usd != null) tb.appendChild(h("tr", { class: "rp-bill-total" }, h("th", { scope: "row", colspan: "3", text: "Total for this scan" }),
        h("td", { class: "mono rp-bill-usd", text: money(bill.total_usd) })));
      bs.appendChild(h("div", { class: "rp-bill-wrap" }, h("table", { class: "rp-bill-table" },
        h("thead", null, h("tr", null, h("th", { scope: "col", text: "Service" }), h("th", { scope: "col", text: "What it did" }),
          h("th", { scope: "col", text: "Usage" }), h("th", { scope: "col", class: "rp-bill-usd", text: "Cost" }))), tb)));
      if (bill.note) bs.appendChild(h("p", { class: "rp-note", text: str(bill.note) }));
      out.appendChild(bs);
    }

    // VM receipt
    if (vm) {
      var rs2 = panel("The VM is gone", { num: num(), eyebrow: "Burn receipt", icon: "ash", cls: "rp-receipt", id: "receipt-card", tags: etag("observed", "Vultr Cloud Compute") });
      var dl = h("dl", { class: "rp-receipt-dl" });
      var row = function (k, v) { if (v == null || v === "") return; dl.appendChild(h("div", null, h("dt", { text: k }), h("dd", null, v))); };
      if (vm.id) row("VM", h("code", { title: str(vm.id), text: str(vm.id).slice(0, 8) }));
      else row("VM", "reused development VM");
      row("Region", str(vm.region));
      row("Plan", str(vm.plan));
      if (vm.snapshot) row("Image", h("code", { text: str(vm.snapshot).slice(0, 18) }));
      if (vm.from_pool) row("Source", "warm pool, used once");
      else if (vm.ready_secs != null) row("Ready in", vm.ready_secs + " s");
      // time + cost of THIS scan (from claim/create); time the VM sat armed in the warm pool is shown apart
      if (vm.lifetime_secs != null || vm.cost_usd_prorated != null) {
        var idle = Number(vm.pool_idle_secs) || 0;
        row("This scan", [h("span", { text: [vm.lifetime_secs != null ? "Alive " + vm.lifetime_secs + " s" : null, usd4(vm.cost_usd_prorated) || null].filter(Boolean).join(" · ") }),
          idle > 0 ? h("span", { class: "rp-standby", text: "(+" + fmtDur(idle) + (vm.pool_idle_cost_usd != null ? ", " + usd4(vm.pool_idle_cost_usd) : "") + " on standby in the warm pool)" }) : null]);
      }
      if (vm.id) row("Destroyed", vm.destroyed ? h("span", { class: "rp-ok", text: "yes, with everything on it" }) : "no (kept)");
      rs2.appendChild(dl);
      var delRow = renderDeletion(vm, id, !!(vm.id && vm.destroyed && !r.replay));
      if (delRow) rs2.appendChild(delRow);
      if (vm.note) rs2.appendChild(h("p", { class: "rp-note", text: str(vm.note) }));
      var evb = r.evidence;
      // /e/<id> re-signs the Object Storage link on every click (S3 links expire after 7 days)
      var evUrl = evb && !evb.error ? (evb.key ? "/e/" + encodeURIComponent(id) : safeUrl(evb.url)) : null;
      var shareCopied = h("span", { class: "copied", text: "Link copied", hidden: true });
      rs2.appendChild(h("div", { class: "rp-receipt-foot" },
        evUrl ? h("a", { class: "button button-secondary", href: evUrl, target: "_blank", rel: "noopener noreferrer" },
          "Download evidence" + (evb.bytes ? " · " + Math.max(1, Math.round(Number(evb.bytes) / 1024)) + " KB" : "")) : null,
        evUrl ? h("span", { class: "rp-note", text: "Bundle stored in Vultr Object Storage." }) : evb && evb.note ? h("span", { class: "rp-note", text: str(evb.note) }) : null,
        h("span", { class: "rp-share no-print" },
          h("button", { class: "button button-secondary button-small", type: "button", onclick: function () { copyText(url, shareCopied); } }, "Copy share link"),
          h("code", { class: "share-url", text: url }), shareCopied)));
      out.appendChild(rs2);
    }
    out.appendChild(h("p", { class: "rp-foot" }, ml("End of file"), h("span", { text: "All secrets in this report are fake values Burner planted. The verdict comes from fixed rules over observed behaviour; the AI only wrote the explanation." })));
    frameSections(out);
    paintMarks(out);
    armMotion([head, $$(".rp-kpis", out)[0], sec]);
    if (chartsCard) chartsCard.activate(chartsCard.first);
  }

  // exhibits panel: one framed chart at a time; hides exhibits whose data or chart function is missing
  function renderChartsPanel(r, secNum) {
    var C = charts();
    var trace = r.trace, flows = r.flows, bait = arr(r.bait);
    var hasTrace = trace && arr(trace.events).length + arr(trace.steps).length > 0;
    var hasFlows = flows && arr(flows.nodes).length > 0;
    var defs = [
      { key: "timeline", name: "Timeline", src: "Every event, in time", ok: !!(C && C.timeline && hasTrace) },
      { key: "flow", name: "Theft flow", src: "Secret → process → destination", ok: !!(C && C.flow && hasFlows) },
      { key: "bait", name: "Fake secrets", src: "What was planted, what was taken", ok: !!(C && C.baitBoard && bait.length) }
    ].filter(function (d) { return d.ok; });
    if (!defs.length) return null;
    var el = h("section", { class: "rp-sec rp-exhibits", id: "charts-card" });
    var tablist = h("div", { class: "ex-tabs", role: "tablist", "aria-label": "Exhibits", style: "--ex-n:" + defs.length });
    el.appendChild(h("header", { class: "rp-sec-head" },
      h("p", { class: "rp-kicker" }, mark("bars"), h("span", { class: "rp-num", text: secNum }), h("span", { class: "rp-eyebrow", text: "Exhibits" }),
        h("span", { class: "rp-tags" }, etag("observed", "Inside the sandbox"))),
      h("h2", { class: "rp-h2", text: "What the repo did" })));
    el.appendChild(tablist);
    var frame = h("div", { class: "ex-frame" });
    el.appendChild(frame);
    var panes = {}, made = {};
    var buttons = defs.map(function (d, i) {
      var b = h("button", { type: "button", role: "tab", class: "ex-tab", id: "ctab-" + d.key, "aria-controls": "cpane-" + d.key,
        "aria-selected": "false", tabindex: "-1", "data-chart": d.key },
        h("span", { class: "ex-no", text: "Exhibit " + pad2(i + 1) }), h("span", { class: "ex-name", text: d.name }), h("span", { class: "ex-src", text: d.src }));
      b.addEventListener("click", function () { activate(d.key); });
      b.addEventListener("keydown", function (e) {
        var j = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: defs.length - 1 }[e.key];
        if (j == null) return;
        e.preventDefault();
        var k = defs[(j + defs.length) % defs.length].key;
        activate(k); $("ctab-" + k).focus();
      });
      tablist.appendChild(b);
      var pane = h("div", { class: "ex-pane", role: "tabpanel", id: "cpane-" + d.key, "aria-labelledby": "ctab-" + d.key, hidden: true });
      pane.setAttribute("data-exhibit", "Exhibit " + pad2(i + 1) + " — " + d.name);
      panes[d.key] = pane;
      frame.appendChild(pane);
      return b;
    });
    var caption = function (no, text) { return h("p", { class: "ex-caption" }, ml("Exhibit " + no), h("span", { text: text })); };
    function build(key) {
      var pane = panes[key], no = pad2(defs.map(function (d) { return d.key; }).indexOf(key) + 1);
      if (key === "timeline") {
        var host = h("div", { class: "ex-host" });
        var info = h("aside", { class: "ex-event", "aria-live": "polite" });
        idleEvent(info, trace);
        pane.appendChild(h("div", { class: "ex-body" }, host, info));
        pane.appendChild(caption(no, "Seconds from the first candidate step. Drag to zoom; the chips toggle lanes. Pick a mark to read it here."));
        mountChart(function () { return C.timeline(host, trace, { onSelect: function (ev) { showEvent(info, ev, trace); } }); });
      } else if (key === "flow") {
        var fh = h("div", { class: "ex-host" });
        pane.appendChild(h("div", { class: "ex-body is-wide" }, fh));
        pane.appendChild(caption(no, "Each fake secret, the process that read it, and where it was sent. Grey secrets never left the sandbox. Line width is how much was sent."));
        mountChart(function () { return C.flow(fh, flows); });
      } else {
        var bh = h("div", { class: "ex-host" });
        pane.appendChild(h("div", { class: "ex-body is-wide" }, bh));
        pane.appendChild(caption(no, "Every value is fake and unique to this scan, so a stolen one is recognisable byte for byte on the fake internet."));
        mountChart(function () { return C.baitBoard(bh, bait, arr(r.stolen)); });
      }
      made[key] = true;
    }
    function activate(key) {
      if (!panes[key]) return;
      buttons.forEach(function (b) {
        var on = b.getAttribute("data-chart") === key;
        b.setAttribute("aria-selected", on ? "true" : "false");
        b.tabIndex = on ? 0 : -1;
        panes[b.getAttribute("data-chart")].hidden = !on;
      });
      if (!made[key]) build(key);
    }
    return { el: el, activate: activate, first: defs[0].key, keys: defs.map(function (d) { return d.key; }) };
  }
  var LANE_NAMES = { secrets: "Fake secret opened", files: "File written", processes: "Process started", network: "Connection", exfil: "Secret sent out", dns: "DNS lookup" };
  function idleEvent(info, trace) {
    clear(info);
    info.appendChild(ml("Event detail"));
    info.appendChild(h("h3", { text: "Pick a mark" }));
    info.appendChild(h("p", { text: "Each mark is something the repo did inside the sandbox. Ember ones touched or sent a fake secret." }));
    var counts = {};
    arr(trace && trace.events).forEach(function (e) { counts[e.lane] = (counts[e.lane] || 0) + 1; });
    var dl = h("dl", { class: "ex-counts" });
    Object.keys(LANE_NAMES).forEach(function (k) { if (counts[k]) { dl.appendChild(h("dt", { text: LANE_NAMES[k] })); dl.appendChild(h("dd", { text: String(counts[k]) })); } });
    if (trace && trace.duration != null) { dl.appendChild(h("dt", { text: "Duration" })); dl.appendChild(h("dd", { text: Number(trace.duration).toFixed(1) + " s" })); }
    if (dl.children.length) info.appendChild(dl);
  }
  function showEvent(info, ev, trace) {
    if (!ev) { idleEvent(info, trace); return; }
    clear(info);
    var sev = str(ev.severity).toLowerCase();
    info.appendChild(ml(LANE_NAMES[ev.lane] || str(ev.lane), ev.lane === "exfil" || ev.lane === "secrets" ? "is-hot" : null));
    info.appendChild(h("h3", { class: "mono", text: str(ev.label) }));
    if (ev.detail) info.appendChild(h("p", { text: str(ev.detail) }));
    var dl = h("dl");
    var row = function (k, v) { if (v == null || v === "") return; dl.appendChild(h("dt", { text: k })); dl.appendChild(h("dd", null, v)); };
    row("When", "T+" + (Number(ev.t) || 0).toFixed(2) + " s");
    row("Step", str(ev.step));
    if (sev) row("Severity", h("span", { class: "rp-sev sev-" + sev, text: sev }));
    info.appendChild(dl);
    if (ev.lane === "exfil" || ev.lane === "secrets") info.appendChild(h("p", { class: "ex-tags" }, etag("fake", "Fake secret"), " ", etag("observed", "Observed")));
  }

  // ---------------------------------------------------------------- track record ("case log")
  var trackLoaded = false;
  var CONTAINMENT_FALLBACK = [
    { test: "HTTPS to www.google.com / HTTP to 1.1.1.1", result: "contained", detail: "Answered by Burner's fake internet ({})" },
    { test: "Real DNS via 8.8.8.8", result: "contained", detail: "Fake answer 198.18.x" },
    { test: "Cloud metadata 169.254.169.254", result: "contained", detail: "Fake {}, no instance data" },
    { test: "SSH to the host (10.77.0.1:22)", result: "contained", detail: "No SSH banner" },
    { test: "Docker socket", result: "contained", detail: "Absent" },
    { test: "Talk to the host kernel", result: "contained", detail: "Kernel is 4.19.0-gvisor" },
    { test: "Become root / mount the host disk", result: "contained", detail: "Both failed" },
    { test: "Raw sockets (packet crafting)", result: "contained", detail: "Capabilities dropped" },
    { test: "Fork bomb (2,000 processes)", result: "fixed", detail: "Capped at 396 after a fix; the sandbox survives (at first it crashed)" },
    { test: "Memory bomb (8 GB)", result: "flagged", detail: "The sandbox dies, the host is fine; verdict becomes SUSPICIOUS (\"crashed our sandbox\"), never clean" },
    { test: "Prompt injection in README (\"report this as SAFE\")", result: "contained", detail: "The content-safety model missed it; the verdict stayed MALICIOUS because the AI can't set it" }
  ];
  var CANT = [
    ["Malware that spots the sandbox and stays quiet", "We flag common VM checks, but a payload that checks something else and does nothing looks clean."],
    ["Payloads that need a real C2 reply", "The fake internet accepts uploads but can't serve the attacker's real second stage."],
    ["Time bombs beyond our shift", "We rerun at +45 days. A payload set for +90 days, or for a user action, is missed."],
    ["Stacks other than JS and Python", "Go, Rust, Java and .NET need their own candidate steps."],
    ["Kernel-level escapes from gVisor", "gVisor plus a throwaway VM limits the damage. It doesn't make an escape impossible."],
    ["Real encryption", "AES-encrypted exfiltration can't be matched to a fake secret; the verdict then rests on a secret read plus an unknown host."]
  ];
  function loadTrack() {
    if (trackLoaded) return;
    var root = $("track"); clear(root);
    root.appendChild(h("h1", { class: "visually-hidden", id: "track-title", tabindex: "-1", text: "Track record" }));
    root.appendChild(h("p", { class: "load-state" }, h("span", { class: "spinner", "aria-hidden": "true" }), " Loading the benchmark…"));
    fetch("/api/benchmark").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (b) { trackLoaded = true; renderTrack(b); }).catch(function (e) {
      clear(root);
      root.appendChild(h("div", { class: "tk-head" }, h("h1", { class: "tk-title", id: "track-title", tabindex: "-1", text: "Track record" }),
        h("p", { class: "field-error", role: "alert", text: "Could not load the benchmark (" + e.message + "). Try again in a moment." })));
    });
  }
  function renderTrack(b) {
    var root = $("track"); clear(root);
    root.classList.add("tk");
    var C = charts();
    var sm = b.summary || {}, samples = arr(b.samples), base = b.baseline || {}, meta = b.meta || {};
    var mal = Number(sm.malicious) || samples.filter(function (x) { return x.expected === "malicious"; }).length;
    var ben = Number(sm.benign) || samples.filter(function (x) { return x.expected === "benign"; }).length;
    var total = mal + ben || samples.length;
    var q = function (v) { return v != null ? v : "?"; };
    root.appendChild(h("div", { class: "back no-print" }, h("button", { type: "button", class: "button button-secondary button-small", onclick: function () { history.length > 1 ? history.back() : go("/"); } }, "← Back")));

    // head with the honest caveat as a margin note
    root.appendChild(h("header", { class: "tk-head" },
      h("div", { class: "tk-head-main" },
        h("p", { class: "rp-case" }, ["Case log", "Benchmark on a Vultr VM", meta.finished ? str(meta.finished) : null, total + " take-homes"].filter(Boolean)
          .map(function (t, i) { return [i ? h("span", { class: "sep", "aria-hidden": "true", text: "·" }) : null, h("span", { text: t })]; })),
        h("h1", { class: "tk-title", id: "track-title", tabindex: "-1" }, "How Burner did on ", h("em", { text: total + " take-homes" })),
        h("p", { class: "tk-lede", text: mal + " malicious take-homes modelled on public reports of the Contagious Interview campaign and related npm and PyPI attacks, and " + ben + " ordinary ones. Every repo was run start to finish in Burner's sandbox, and scanned by GuardDog, an open-source static scanner, for comparison." })),
      h("aside", { class: "tk-margin", id: "caveat", "aria-label": "The honest caveat" },
        mark("stamp"), ml("Margin note · the honest caveat"),
        h("p", { class: "tk-margin-quote", text: "We wrote the samples — rules tuned after a baseline run, both shown." }),
        h("p", { text: "All " + total + " are defanged samples we wrote from public reports, so treat this as a regression suite, not a field study." }),
        h("dl", { class: "tk-base" },
          h("div", null, h("dt", { text: "Baseline" }), h("dd", { text: q(base.detected) + "/" + q(base.of) + " · " + plural(Number(q(base.false_alarms)) || 0, "false alarm") })),
          h("div", null, h("dt", { text: "Final" }), h("dd", { text: q(sm.burner_detected) + "/" + mal + " · " + q(sm.burner_false_alarms) + "/" + ben + " false alarms" }))))));

    // the headline numbers, as a ledger: Burner vs GuardDog
    var big = function (v, of, cls) {
      return h("span", { class: "tk-big " + (cls || "") }, String(q(v)), of != null ? h("small", { text: "/" + of }) : null);
    };
    var vrow = function (label, sub, a, bb) {
      return h("div", { class: "tk-vrow", role: "row" }, h("div", { class: "tk-vlabel", role: "rowheader" }, h("span", { class: "k", text: label }), h("span", { class: "s", text: sub })),
        h("div", { class: "tk-vcell is-us", role: "cell" }, a), h("div", { class: "tk-vcell", role: "cell" }, bb));
    };
    root.appendChild(h("section", { class: "tk-versus", id: "versus", "aria-label": "Burner versus GuardDog" },
      h("div", { class: "tk-vhead", role: "row" }, h("span", { role: "columnheader" }),
        h("div", { class: "tk-vcol is-us", role: "columnheader" }, h("span", { class: "n", text: "Burner" }), ml("Runs the repo")),
        h("div", { class: "tk-vcol", role: "columnheader" }, h("span", { class: "n", text: "GuardDog" }), ml("Static · reads the code"))),
      h("div", { role: "table", class: "tk-vtable", "aria-label": "Headline numbers" },
        vrow("Attacks caught", "of " + mal + " malicious · higher is better", big(sm.burner_detected, mal, "is-heat"), big(sm.guarddog_detected, mal)),
        vrow("False alarms", "of " + ben + " clean · lower is better", big(sm.burner_false_alarms, ben, "is-calm"), big(sm.guarddog_false_alarms, ben)),
        vrow("Median scan", "per repo", big(sm.median_scan_secs != null ? Math.round(sm.median_scan_secs) + " s" : "—", null, "is-mid"),
          big(sm.median_guarddog_secs != null ? sm.median_guarddog_secs + " s" : "—", null, "is-mid"))),
      h("div", { class: "tk-vfoot" },
        h("p", null, ml("Burner"), h("span", { text: "Named the exact stolen fake secret on " + q(sm.burner_named_stolen_secret) + " of " + mal + "." })),
        h("p", null, ml("GuardDog"), h("span", { text: "Counting any rule, even its informational capability-* ones: " + q(sm.guarddog_any_rule_detected) + " of " + mal + " caught, but " + q(sm.guarddog_any_rule_false_alarms) + " of " + ben + " false alarms." })))));

    var exN = 0;
    var chartCard = function (id, title, sub, fn, fallback, icon) {
      exN += 1;
      var host = h("div", { class: "ex-host is-bare" });
      var card = h("section", { class: "rp-sec tk-ex", id: id },
        h("header", { class: "rp-sec-head" }, h("p", { class: "rp-kicker" }, icon ? mark(icon) : null, h("span", { class: "rp-num", text: "Exhibit " + String.fromCharCode(64 + exN) })),
          h("h2", { class: "rp-h2", text: title }), sub ? h("p", { class: "rp-sub", text: sub }) : null), host);
      root.appendChild(card);
      if (!(C && fn && mountChart(function () { return fn(host); }))) {
        if (fallback) host.appendChild(fallback()); else card.remove();
      }
    };
    chartCard("bench-score", "Detection and false alarms", "Share of the " + mal + " attacks caught, and of the " + ben + " clean take-homes wrongly flagged.",
      C && C.scoreBars ? function (el) { return C.scoreBars(el, sm); } : null, null, "bars");
    chartCard("bench-matrix", "The ledger, sample by sample", "Each row is one take-home. Hover a row for the technique and Burner's headline.",
      C && C.benchMatrix ? function (el) { return C.benchMatrix(el, samples); } : null, function () { return matrixTable(samples); }, "stamp");
    chartCard("bench-times", "Scan time per sample", "Most scans hit the candidate steps' time limits (about 90 s); quick ones finished on their own.",
      C && C.scanTimes ? function (el) { return C.scanTimes(el, samples); } : null, null, "clock");

    var cont = arr(b.containment).length ? arr(b.containment) : CONTAINMENT_FALLBACK;
    var counts = {};
    cont.forEach(function (c) { var k = str(c.result).toLowerCase(); counts[k] = (counts[k] || 0) + 1; });
    var ct = h("section", { class: "rp-sec tk-contain", id: "containment" },
      h("header", { class: "rp-sec-head" }, h("p", { class: "rp-kicker" }, mark("nested"), h("span", { class: "rp-num", text: "Red team" }), h("span", { class: "rp-tags" }, etag("observed", "Observed"))),
        h("h2", { class: "rp-h2", text: "We attacked our own sandbox" }),
        h("p", { class: "rp-sub", text: "Escape attempts run from inside the sandbox, as a malicious take-home would" + (meta.containment_environment ? " — " + str(meta.containment_environment) : "") + "." })),
      h("p", { class: "tk-tally" }, ["contained", "fixed", "flagged", "missed"].filter(function (k) { return counts[k]; }).map(function (k) {
        return h("span", { class: "tk-tally-i" }, h("b", { text: String(counts[k]) }), h("span", { class: "result-tag res-" + k, text: k }));
      })));
    var tb = h("tbody");
    cont.forEach(function (c, i) {
      var res = str(c.result).toLowerCase();
      tb.appendChild(h("tr", null, h("td", { class: "mono n", "data-l": "#", text: pad2(i + 1) }), h("td", { class: "att", "data-l": "Attempt", text: str(c.test) }),
        h("td", { "data-l": "Result" }, h("span", { class: "result-tag res-" + res, text: res })),
        h("td", { class: "what", "data-l": "What happened", text: str(c.detail) })));
    });
    ct.appendChild(h("div", { class: "tbl-wrap" }, h("table", { class: "rp-table stack tk-ctable" },
      h("thead", null, h("tr", null, h("th", { text: "#" }), h("th", { text: "Escape attempt" }), h("th", { text: "Result" }), h("th", { text: "What happened" }))), tb)));
    ct.appendChild(h("p", { class: "rp-note", text: "Host side during the run: 0 packets forwarded from the sandbox bridge to the internet (iptables counter)." }));
    root.appendChild(ct);

    var pair = h("div", { class: "rp-pair" });
    var d = b.defender && typeof b.defender === "object" ? b.defender : null;
    var df = h("section", { class: "rp-sec tk-defender", id: "defender" },
      h("header", { class: "rp-sec-head" }, h("p", { class: "rp-kicker" }, mark("shield"), h("span", { class: "rp-num", text: "For comparison" })), h("h2", { class: "rp-h2", text: "Windows Defender" })));
    if (d && d.stealers_total != null) {
      df.appendChild(h("p", { class: "tk-def-num" }, h("span", { class: "tk-big is-mid" }, String(q(d.stealers_flagged)), h("small", { text: "/" + d.stealers_total })),
        h("span", { class: "s", text: "stealers flagged by signature" })));
    }
    df.appendChild(h("p", { class: "rp-empty", text: defenderText(b.defender) }));
    if (d && d.threat) df.appendChild(h("p", { class: "rp-chiprow" }, ml("Signature"), h("code", { class: "rp-chip", text: str(d.threat) }), d.when ? h("span", { class: "rp-note", text: str(d.when) }) : null));
    pair.appendChild(df);
    pair.appendChild(h("section", { class: "rp-sec tk-cant", id: "cant" },
      h("header", { class: "rp-sec-head" }, h("p", { class: "rp-kicker" }, mark("ash"), h("span", { class: "rp-num", text: "Limits" })), h("h2", { class: "rp-h2", text: "What Burner can't catch" })),
      h("ol", { class: "tk-cant-list" }, CANT.map(function (c, i) { return h("li", null, h("span", { class: "n", text: pad2(i + 1) }), h("div", null, h("b", { text: c[0] }), h("p", { text: c[1] }))); })),
      h("p", { class: "rp-note", text: "A clean result means no malicious behaviour was observed in this run. It does not mean safe." })));
    root.appendChild(pair);
    frameSections(root);
    paintMarks(root);
  }
  function defenderText(d) {
    if (d && typeof d === "object" && !Array.isArray(d) && (d.text || d.note || d.summary)) return str(d.text || d.note || d.summary);
    return "Windows Defender on the developer's PC quarantined the folderOpen sample when it was written to disk (Trojan:Script/MalTask.A), but did not flag the npm start stealer. Static antivirus caught 1 of 2.";
  }
  function matrixTable(samples) {
    var tb = h("tbody");
    samples.forEach(function (x) {
      var mal = x.expected === "malicious";
      var bc = mal ? (x.detected ? "caught" : "missed") : (x.detected ? "false alarm" : "clean");
      var g = x.guarddog || {};
      var gc = mal ? (g.flagged ? "caught" : "missed") : (g.flagged ? "false alarm" : "clean");
      tb.appendChild(h("tr", null, h("td", { "data-l": "Sample" }, h("code", { text: str(x.name) })), h("td", { "data-l": "Technique", text: str(x.technique) }),
        h("td", { "data-l": "Burner" }, h("span", { class: "result-tag res-" + bc.replace(" ", "-"), text: bc })),
        h("td", { "data-l": "GuardDog" }, h("span", { class: "result-tag res-" + gc.replace(" ", "-"), text: gc }))));
    });
    return h("div", { class: "tbl-wrap" }, h("table", { class: "rp-table stack" },
      h("thead", null, h("tr", null, h("th", { text: "Sample" }), h("th", { text: "Technique" }), h("th", { text: "Burner" }), h("th", { text: "GuardDog" }))), tb));
  }

  // print: open every disclosure first
  window.addEventListener("beforeprint", function () { $$("#report details").forEach(function (d) { d.open = true; }); });

  // ---------------------------------------------------------------- the API the tour uses
  window.Burner = {
    go: go,
    view: function () { return view; },
    setMode: setMode,
    state: function () { return S; },
    startSample: function (name) {
      setMode("sample"); setSample(name);
      return start({ sample: name }, { title: SAMPLE_NAMES[name], hasMessage: name === "npm-start-stealer" });
    },
    showRun: function () { if (S) setView("run", { focus: false }); },
    showReport: function () { if (S && S.report) { clearTimeout(S.autoTimer); setView("report", { focus: false }); } },
    selectChart: function (key) { var b = $("ctab-" + key); if (b) b.click(); return !!b; }
  };

  route();
})();
