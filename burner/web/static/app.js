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
    var m = /^https?:\/\/(?:www\.)?(?:github\.com|gitlab\.com|bitbucket\.org)\/([^/?#]+\/[^/?#]+)/i.exec(t);
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
  function setView(name, opts) {
    opts = opts || {};
    view = name;
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
    [$("msg"), $("repo")].forEach(function (f) { f.removeAttribute("aria-invalid"); });
    if (!msg) { el.hidden = true; el.textContent = ""; return; }
    el.textContent = msg; el.hidden = false;
    if (field) { field.setAttribute("aria-invalid", "true"); field.focus(); }
  }
  function setBusy(b) {
    var btn = $("burn-btn");
    btn.disabled = b;
    if (b) btn.setAttribute("aria-busy", "true"); else btn.removeAttribute("aria-busy");
    btn.textContent = b ? "Starting…" : "Burn it";
    $$(".strip-tab").forEach(function (x) { x.disabled = b; });
  }
  var SAMPLE_NAMES = { "npm-start-stealer": "the npm-start stealer sample", "clean-takehome": "the clean take-home sample" };

  $("scan-form").addEventListener("submit", function (e) {
    e.preventDefault();
    var msg = $("msg").value.trim(), repo = $("repo").value.trim();
    if (mode === "sample") { start({ sample: sample }, { title: SAMPLE_NAMES[sample], hasMessage: sample === "npm-start-stealer" }).catch(noop); return; }
    if (mode === "message" && !msg && !repo) { formError("Paste the recruiter's message first, or switch to Repo link.", $("msg")); return; }
    if (mode === "repo" && !repo) { formError("Paste the repo link first.", $("repo")); return; }
    var body = {};
    if (msg) body.message = msg;
    if (repo) body.repo = repo;
    start(body, { title: repo ? shortTarget(repo) : "the recruiter's take-home", target: repo || "", hasMessage: !!msg }).catch(noop);
  });
  $$(".strip-tab").forEach(function (b) {
    b.addEventListener("click", function () {
      var d = b.getAttribute("data-demo");
      if (d === "own") {
        setMode("repo");
        $("scan-form").scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "center" });
        $("repo").focus({ preventScroll: true });
        return;
      }
      setMode("sample"); setSample(d);
      start({ sample: d }, { title: SAMPLE_NAMES[d], hasMessage: d === "npm-start-stealer" }).catch(noop);
    });
  });

  // ---------------------------------------------------------------- the live run
  var PHASES = [
    { key: "message", label: "Read the recruiter message" },
    { key: "plan", label: "Plan like a candidate" },
    { key: "vm", label: "Fresh Vultr VM" },
    { key: "setup", label: "Arm the sandbox" },
    { key: "run", label: "Run like a candidate" },
    { key: "destroy", label: "Destroy the VM" },
    { key: "verdict", label: "Verdict" }
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
      return { li: li, name: name, state: state, msgs: msgs, sub: sub };
    });
    clear($("contain-slot")); clear($("error-slot")); clear($("events-list"));
    $("events-count").textContent = "";
    $("run-after").hidden = true;
  }
  function setState(i, st) {
    var p = S.phases[i];
    if (!p) return;
    if (st === "done" && S.warn[i]) st = "warning";
    p.li.setAttribute("data-state", st);
    p.state.textContent = STATE_TEXT[st] || "";
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
  function logEvent(ev) {
    var list = $("events-list");
    list.appendChild(h("li", { class: ev.stage === "error" ? "is-error" : null },
      h("span", { class: "ev-t", text: (Number(ev.t) || 0).toFixed(1) + "s" }),
      h("span", { class: "ev-s", text: str(ev.stage) }),
      h("span", { text: str(ev.text) })));
    $("events-count").textContent = "(" + list.children.length + ")";
  }
  function setRunTitle(t) { $("run-title").textContent = "Burning " + t; }

  function handleEvent(ev) {
    var tx = str(ev.text);
    S.events.push(ev);
    logEvent(ev);
    S.lastT = Number(ev.t) || S.lastT;
    if (!S.ended) S.base = Date.now() - S.lastT * 1000;
    var idx = phaseOf(ev);
    var p = S.phases[idx];
    if (ev.stage === "error") {
      setState(idx, "failed");
      p.msgs.appendChild(h("li", { class: "is-error", text: tx }));
      showRunError(tx);
      return;
    }
    if (ev.stage === "message") S.sawMessage = true;
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
    if (/sandbox died|crashed|killed|timed out|warning/i.test(tx) && ev.stage !== "done") { cls = "is-warning"; S.warn[idx] = true; }
    if (ev.stage === "done") {
      shown = tx.length > 180 ? tx.slice(0, 177) + "…" : tx;
      cls = /^MALICIOUS/.test(tx) ? "is-error" : /^SUSPICIOUS/.test(tx) ? "is-warning" : null;
    }
    p.msgs.appendChild(h("li", { class: cls, text: shown }));
    var vmm = /^VM destroyed after (\d+)s/.exec(tx);
    if (vmm) { S.vmDestroyed = true; S.vmLife = vmm[1]; showContain(); }
    else if (tx === "sandbox destroyed") { S.sandboxDestroyed = true; showContain(); }
    if (ev.stage === "done") {
      S.phases.forEach(function (q, i) { setState(i, "done"); });
      if (!S.sawMessage && S.info.hasMessage !== true) S.phases[0].name.textContent = "Get the repo";
    }
  }

  function showContain() {
    var slot = $("contain-slot");
    var big = S.vmDestroyed ? ["VM destroyed. ", "Nothing touched your laptop."] : ["Sandbox destroyed. ", "Nothing touched your laptop."];
    var small = S.vmDestroyed
      ? "The repo only ever ran on a throwaway Vultr VM" + (S.vmLife ? " that lived " + S.vmLife + " seconds" : "") + ". It's gone now, with the fake secrets it took."
      : "The repo ran inside a gVisor sandbox on a burner VM, with fake secrets and a fake internet. The VM goes next.";
    var box = document.querySelector("#phases .contain, #contain-slot .contain");
    if (box) {   // already shown: update the words, don't replay the animation
      box.querySelector(".contain-big").lastChild.textContent = big[1];
      box.querySelector(".contain-big").firstChild.textContent = big[0];
      box.querySelector(".contain-small").textContent = small;
      return;
    }
    var shards = [];
    var dirs = [[-30, -26, -40], [0, -34, 25], [28, -24, 60], [-36, 2, -70], [4, -6, 15], [34, 6, 80], [-26, 30, -30], [2, 36, 45], [30, 28, -55]];
    dirs.forEach(function (d, k) {
      var i = h("i");
      i.style.setProperty("--dx", d[0] + "px"); i.style.setProperty("--dy", d[1] + "px");
      i.style.setProperty("--r", d[2] + "deg"); i.style.setProperty("--k", k);
      shards.push(i);
    });
    var laptop = s("svg", { class: "laptop", viewBox: "0 0 62 62", "aria-hidden": "true" },
      s("circle", { class: "ring", cx: 31, cy: 31, r: 27 }),
      s("rect", { class: "body", x: 17, y: 20, width: 28, height: 18, rx: 2.5 }),
      s("path", { class: "body", d: "M13 41h36l-3 4H16z" }),
      s("path", { class: "tick", d: "M24 29l5 5 9-9" }));
    var host = S.phases[5] ? S.phases[5].li : slot;
    var beat = host.appendChild(h("div", { class: "contain", role: "status" },
      h("div", { class: "contain-art", "aria-hidden": "true" },
        h("div", { class: "vmbox" }, shards), h("span", { class: "vmbox-label", text: "VM" }), laptop),
      h("div", null,
        h("p", { class: "contain-big" }, big[0], h("b", { text: big[1] })),
        h("p", { class: "contain-small", text: small }),
        h("div", { class: "contain-chips" }, badge("observed", "Fake secrets only"), badge("rule", "gVisor + throwaway VM")))));
    if (view === "run") {
      var r = beat.getBoundingClientRect();
      if (r.bottom > innerHeight || r.top < 0) beat.scrollIntoView({ behavior: reduced() ? "auto" : "smooth", block: "center" });
    }
  }
  function showRunError(text) {
    var slot = $("error-slot"); clear(slot);
    slot.appendChild(h("div", { class: "run-error", role: "alert" }, h("b", { text: "The scan stopped with an error" }),
      h("code", { text: text || "unknown error" })));
    $("run-title").textContent = "Scan failed";
    $("run-eyebrow").textContent = "Live run · stopped";
    showAfter(false);
  }
  function showAfter(hasReport) {
    $("run-after").hidden = false;
    $("run-report").hidden = !hasReport;
    $("run-cancel").textContent = "Scan another";
  }
  function tick() { if (S && !S.ended) $("timer").textContent = fmtClock((Date.now() - S.base) / 1000); }
  function startTimer() { stopTimer(); timerId = setInterval(tick, 250); tick(); }
  function stopTimer() { if (timerId) clearInterval(timerId); timerId = null; }

  function showRun(info) {
    $("run-eyebrow").textContent = "Live run";
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
      $("run-eyebrow").textContent = "Live run · finished in " + fmtClock(S.lastT);
      if (j.report) {
        S.report = j.report;
        renderReport(j.report, id);
        showAfter(true);
        S.autoTimer = setTimeout(function () { if (view === "run" && S && S.id === id) setView("report"); }, 1600);
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
          if (res.status === 429) msg = "Slow down: " + msg + ". The samples are always free to try.";
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

  function panel(title, opts) {
    opts = opts || {};
    var head = h("h2", { class: "section-title-sm" }, title, opts.badges || null);
    var sec = h("section", { class: "panel-card " + (opts.cls || ""), id: opts.id || null }, opts.eyebrow ? h("p", { class: "eyebrow", text: opts.eyebrow }) : null, head);
    if (opts.sub) sec.appendChild(h("p", { class: "panel-sub", text: opts.sub }));
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
  function ring(el, taken, total) {
    var draw = function () {
      clear(el);
      var C = charts();
      var bad = cssVar("--bad-solid", "#b3261e"), rest = cssVar("--line-2", "#cfd8da");
      if (C && C.donut) {
        try {
          C.donut(el, [{ label: "Stolen", value: taken, color: "var(--bad-solid)" }, { label: "Not taken", value: Math.max(0, total - taken), color: "var(--line-2)" }], { size: 54, caption: false });
          return;
        } catch (e) { clear(el); }
      }
      var r = 22, c = 2 * Math.PI * r, f = total ? taken / total : 0;
      el.appendChild(s("svg", { class: "ring-fallback", viewBox: "0 0 54 54", role: "img", "aria-label": taken + " of " + total + " stolen" },
        s("circle", { cx: 27, cy: 27, r: r, stroke: rest }),
        s("circle", { cx: 27, cy: 27, r: r, stroke: bad, "stroke-dasharray": (c * f) + " " + c, transform: "rotate(-90 27 27)", "stroke-linecap": "round" })));
    };
    draw();
    donuts.push(draw);
  }
  function kpi(label, value, sub, cls) {
    return h("div", { class: "kpi " + (cls || "") }, h("span", { class: "kpi-label", text: label }),
      h("span", { class: "kpi-value" }, value), sub ? h("span", { class: "kpi-sub", text: sub }) : null);
  }

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

  var chartInstances = [];
  function destroyCharts() {
    chartInstances.forEach(function (c) { try { c.destroy(); } catch (e) { /* already gone */ } });
    chartInstances = [];
    donuts = [];
  }
  function mountChart(fn) {
    try { var inst = fn(); if (inst && inst.destroy) chartInstances.push(inst); return true; } catch (e) {
      if (window.console) console.warn("chart failed", e);
      return false;
    }
  }

  function renderReport(r, id) {
    destroyCharts();
    var out = $("report"); clear(out);
    var verdict = str(r.verdict).toUpperCase();
    var cls = verdict === "MALICIOUS" ? "is-bad" : verdict === "SUSPICIOUS" ? "is-warn" : "is-ok";
    var stolen = arr(r.stolen), findings = arr(r.findings), bait = arr(r.bait), steps = arr(r.steps), network = arr(r.network);
    var vm = r.vm || null;
    var groups = groupStolen(stolen);
    var takenNames = {};
    stolen.forEach(function (x) { takenNames[str(x.secret)] = true; });
    var takenCount = Object.keys(takenNames).length;

    // toolbar
    var url = location.origin + "/r/" + id;
    var linkCopied = h("span", { class: "copied", text: "Link copied", hidden: true });
    out.appendChild(h("div", { class: "report-bar no-print" },
      h("div", { class: "report-bar-left" },
        h("button", { type: "button", class: "button button-secondary", onclick: function () { go("/"); } }, "← Scan another"),
        S && S.events.length ? h("button", { type: "button", class: "button button-secondary", onclick: function () { setView("run"); } }, "Replay the run") : null),
      h("div", { class: "report-bar-right" }, linkCopied,
        h("button", { type: "button", class: "button button-secondary", onclick: function () { copyText(url, linkCopied); } }, "Copy share link"),
        h("button", { type: "button", class: "button button-primary", onclick: function () { window.print(); } }, "Print / save as PDF"))));

    // verdict banner (never the word "safe")
    var word = cls === "is-bad" ? "Malicious." : cls === "is-warn" ? "Suspicious." : "No malicious behaviour observed.";
    var side = h("dl");
    var sideRow = function (k, v) { if (v == null || v === "") return; side.appendChild(h("dt", { text: k })); side.appendChild(h("dd", { text: v })); };
    sideRow("Scan", id);
    if (r.total_secs != null) sideRow("Took", r.total_secs + " s");
    if (r.llm_usage && r.llm_usage.calls) {
      var tok = (Number(r.llm_usage.prompt_tokens) || 0) + (Number(r.llm_usage.completion_tokens) || 0);
      sideRow("AI calls", plural(Number(r.llm_usage.calls), "call") + " · " + tok.toLocaleString() + " tokens");
    }
    var banner = h("section", { class: "verdict " + cls, role: "status", "aria-labelledby": "report-title" },
      h("div", null,
        h("p", { class: "verdict-eyebrow" }, h("span", { text: "Verdict" }), badge("rule", "Rule-based"), badge("observed", "Observed behaviour")),
        h("h1", { class: "verdict-word", id: "report-title", tabindex: "-1", text: word }),
        r.headline ? h("p", { class: "verdict-headline", text: r.headline }) : null,
        cls === "is-ok" ? h("p", { class: "verdict-caveat", text: "Burner didn't see it steal, persist or phone home. That's evidence from one run, not a guarantee." }) : null,
        r.target ? h("div", { class: "verdict-meta" }, h("span", { class: "pill mono", title: str(r.target), text: str(r.target) })) : null),
      h("div", { class: "verdict-side" }, side),
      r.explanation ? h("div", { class: "ai-block" }, badge("ai", "AI explanation — verdict is rule-based"), h("p", { text: r.explanation })) : null);
    out.appendChild(banner);

    // KPI tiles
    var destSet = {};
    stolen.forEach(function (x) { destSet[str(x.sent_to || x.dst)] = true; });
    var dests = Object.keys(destSet).filter(Boolean);
    var rawIps = network.filter(function (n) { return n.raw_ip; }).length;
    var donutHost = h("div", { class: "donut-host" });
    var stolenTile = h("div", { class: "kpi kpi-stolen " + (takenCount ? "is-bad" : "") },
      h("span", { class: "kpi-label", text: "Fake secrets stolen" }),
      h("div", { class: "kpi-donut" }, bait.length ? donutHost : null,
        h("div", null, h("span", { class: "kpi-value" }, String(takenCount), h("small", { text: " / " + (bait.length || takenCount) })),
          h("span", { class: "kpi-sub", style: "display:block", text: bait.length ? plural(bait.length, "fake secret") + " planted" : "planted" }))));
    var kp = h("div", { class: "kpis", role: "group", "aria-label": "Key numbers" }, stolenTile,
      dests.length ? kpi("Sent to", String(dests.length), plural(dests.length, "destination") + (rawIps ? " · " + rawIps + " hard-coded IP" : ""), "is-bad")
        : kpi("Network contacts", String(network.length), "none received secrets"),
      kpi("Steps run", String(steps.length), "like a candidate would"),
      kpi("VM alive", vm && vm.lifetime_secs != null ? h("span", null, String(vm.lifetime_secs), h("small", { text: " s" })) : "—",
        vm ? (vm.destroyed ? "then destroyed" : vm.id ? "kept (dev)" : "reused dev VM") : "no VM data"),
      kpi("Scan took", r.total_secs != null ? h("span", null, String(r.total_secs), h("small", { text: " s" })) : "—", "paste to verdict"),
      kpi("Cost", vm && vm.cost_usd_prorated != null ? "≈ $" + Number(vm.cost_usd_prorated).toFixed(4) : "—",
        vm && vm.cost_usd_max != null ? "max $" + Number(vm.cost_usd_max).toFixed(4) + " if billed hourly" : "Vultr VM, prorated"));
    out.appendChild(kp);
    if (bait.length) ring(donutHost, takenCount, bait.length);

    // charts
    var chartsCard = renderChartsPanel(r);
    if (chartsCard) out.appendChild(chartsCard.el);

    // campaign + recruiter
    var pair = h("div", { class: "grid-2" });
    var cp = r.campaign;
    if (cp && cp.similarity) {
      var sim = str(cp.similarity).toLowerCase();
      var cc = panel("Campaign match", { cls: "campaign sim-" + sim, id: "campaign-card",
        badges: h("span", { class: "badge " + (sim === "high" ? "badge-bad" : sim === "medium" ? "badge-warn" : "badge-plain"), text: sim + " similarity" }) });
      cc.appendChild(h("p", { class: "campaign-name" }, h("span", { class: "muted", text: "Behaves like " }), str(cp.campaign || "a known campaign")));
      var inds = arr(cp.indicators);
      if (inds.length) {
        cc.appendChild(h("ul", { class: "indicators" }, inds.map(function (x) {
          var src = safeUrl(x.source);
          return h("li", null, h("div", null, h("b", { text: str(x.what) }), x.why ? h("span", { class: "why", text: " — " + x.why }) : null,
            src && src !== "#" ? h("a", { class: "link", href: src, target: "_blank", rel: "noopener noreferrer", text: "source" }) : null));
        })));
      }
      cc.appendChild(h("p", { class: "card-note", text: str(cp.note) || "Behavioural similarity to public reports, not attribution." }));
      pair.appendChild(cc);
    }
    var rc = r.recruiter;
    if (rc && ((rc.red_flags && rc.red_flags.length) || rc.lure_score != null || rc.company)) {
      var who = [rc.role, rc.company].filter(Boolean).join(" at ");
      var rs = panel("Recruiter red flags", { id: "recruiter-card", badges: badge("ai", "Read by AI"), sub: who ? "Claimed to be: " + who : null });
      if (rc.lure_score != null) {
        var score = Math.max(0, Math.min(10, Number(rc.lure_score) || 0));
        var fill = h("i", { style: "width:0%" });
        rs.appendChild(h("div", { class: "lure" }, h("span", { class: "lure-score" }, String(score), h("small", { text: " / 10 lure score" })),
          h("div", { class: "meter", role: "img", "aria-label": "lure score " + score + " of 10" }, fill)));
        requestAnimationFrame(function () { requestAnimationFrame(function () { fill.style.width = score * 10 + "%"; }); });
      }
      if (rc.red_flags && rc.red_flags.length) rs.appendChild(h("ul", { class: "flags" }, rc.red_flags.map(function (f) { return h("li", { text: f }); })));
      else rs.appendChild(h("p", { class: "empty", text: "No red flags spotted in the message." }));
      pair.appendChild(rs);
    }
    if (pair.children.length === 1) pair.style.gridTemplateColumns = "minmax(0, 1fr)";
    if (pair.children.length) out.appendChild(pair);

    if (r.readme_screen && r.readme_screen.unsafe) {
      var rd = panel("The README tries to talk to AI tools", { cls: "caveat-card" });
      rd.appendChild(h("p", { class: "empty", text: "The repo's README contains text aimed at AI assistants (prompt injection). Burner's verdict does not depend on an AI, so it can't be talked out of it." }));
      out.appendChild(rd);
    }

    // what it stole
    var sec = panel(stolen.length ? "What it stole" : "What it stole: nothing", { id: "stolen-card", badges: [badge("observed", "Observed"), badge("fake", "Fake secrets")],
      sub: bait.length ? plural(bait.length, "fake secret") + " planted in the sandbox's home directory" : null });
    if (!stolen.length) {
      sec.appendChild(h("p", { class: "empty", text: bait.length
        ? "Nothing. None of the " + bait.length + " fake secrets Burner planted left the sandbox."
        : "Nothing was seen leaving the sandbox." }));
    } else {
      sec.appendChild(h("p", { class: "taken-line", text: groups.length + " of " + (bait.length || groups.length) + " fake secrets were sent out of the sandbox." }));
      var tb = h("tbody");
      groups.forEach(function (g) {
        tb.appendChild(h("tr", null,
          h("td", { class: "secret", "data-l": "Secret", text: g.secret }),
          h("td", { "data-l": "From file" }, h("code", { text: g.from_file })),
          h("td", { "data-l": "Sent to" }, h("div", { class: "dests" }, g.dests.map(function (x) {
            return h("div", null, h("code", { text: x.d }), " ", x.enc ? h("span", { class: "pill is-warn", text: "encoded" }) : null);
          }))),
          h("td", { "data-l": "During step", text: g.steps.join(", ") })));
      });
      sec.appendChild(h("div", { class: "tbl-wrap" }, h("table", { class: "data stack" },
        h("thead", null, h("tr", null, h("th", { text: "Secret" }), h("th", { text: "From file" }), h("th", { text: "Sent to" }), h("th", { text: "During step" }))), tb)));
      var ev = h("details", { class: "captures" },
        h("summary", null, "Captured on our fake internet", h("span", { class: "pill", text: plural(stolen.length, "capture") })));
      var body = h("div", { class: "cap-body" });
      stolen.forEach(function (x) {
        body.appendChild(h("div", { class: "capture" },
          h("div", { class: "cap-head" },
            h("b", { text: str(x.secret) }), "→", h("code", { text: str(x.sent_to || x.dst) }),
            h("span", { class: "mono", text: [x.method, x.url_path].filter(Boolean).join(" ") + (x.proto ? " (" + x.proto + ")" : "") }),
            x.bytes ? h("span", { class: "pill", text: fmtBytes(x.bytes) + " request" }) : null,
            x.encoded ? h("span", { class: "pill is-warn", text: "found after decoding" }) : null,
            x.step ? h("span", { class: "pill", text: "during " + x.step }) : null),
          highlight(x.snippet, x.value),
          h("div", { class: "cap-legend" }, h("span", { class: "sw" }), "fake value planted by Burner")));
      });
      ev.appendChild(body);
      sec.appendChild(ev);
    }
    if (bait.length && stolen.length) {
      var untouched = bait.filter(function (b) { return !takenNames[str(b.kind)]; });
      if (untouched.length) {
        sec.appendChild(h("div", { class: "untaken" }, h("span", { text: "Planted but not taken:" }),
          untouched.map(function (b) { return h("span", { class: "pill", title: str(b.file), text: str(b.kind) }); })));
      }
    }
    out.appendChild(sec);

    // steps + findings
    var pair2 = h("div", { class: "grid-2" });
    if (steps.length) {
      var hot = {};
      stolen.forEach(function (x) { if (x.step) hot[x.step] = true; });
      var ts = panel("What Burner ran", { id: "steps-card", badges: badge("observed", "Observed"), sub: "Like a candidate would, in this order" });
      ts.appendChild(h("ol", { class: "steps-list" }, steps.map(function (x, i) {
        var rcTxt = x.rc == null ? "" : x.rc === 137 ? "exit 137 (stopped at time limit)" : "exit " + x.rc;
        return h("li", { class: hot[x.name] ? "is-hot" : null },
          h("span", { class: "n", text: i + 1 }),
          h("div", null, h("div", { class: "nm", text: str(x.name) }),
            x.why ? h("div", { class: "why", text: str(x.why) }) : null,
            x.cmd ? h("div", { class: "cmd", text: "$ " + x.cmd }) : null,
            hot[x.name] ? h("div", { class: "stolen-in", text: "Secrets were stolen during this step" }) : null),
          h("div", { class: "rt" }, h("div", { text: x.secs != null ? x.secs + " s" : "" }), h("div", { text: rcTxt })));
      })));
      pair2.appendChild(ts);
    }
    var died = findings.filter(function (f) { return f.rule === "SANDBOX_DIED"; });
    var other = findings.filter(function (f) { return f.rule !== "EXFIL" && f.rule !== "SANDBOX_DIED"; });
    if (other.length || died.length) {
      var fs = panel("Other findings", { id: "findings-card", badges: badge("rule", "Rule-based") });
      died.forEach(function (f) {
        fs.appendChild(h("div", { class: "died", role: "note" }, h("span", { class: "died-icon", "aria-hidden": "true", text: "!" }),
          h("div", null, h("b", { text: str(f.title) }),
            h("div", { class: "help", text: "The repo crashed Burner's sandbox, so it may have done more than Burner saw. Treat that as a red flag on its own." }))));
      });
      ["critical", "high", "medium", "low"].forEach(function (sev) {
        var list = other.filter(function (f) { return str(f.severity).toLowerCase() === sev; });
        if (!list.length) return;
        fs.appendChild(h("div", { class: "sev-group" }, h("h3", { class: "sev sev-" + sev, text: sev + " (" + list.length + ")" }),
          h("ul", null, list.map(function (f) { return h("li", null, str(f.title), h("span", { class: "rule", text: str(f.rule) })); }))));
      });
      var rest = other.filter(function (f) { return ["critical", "high", "medium", "low"].indexOf(str(f.severity).toLowerCase()) === -1; });
      if (rest.length) fs.appendChild(h("div", { class: "sev-group" }, h("h3", { class: "sev sev-info", text: "other" }),
        h("ul", null, rest.map(function (f) { return h("li", { text: str(f.title) }); }))));
      pair2.appendChild(fs);
    }
    if (pair2.children.length === 1) pair2.style.gridTemplateColumns = "minmax(0, 1fr)";
    if (pair2.children.length) out.appendChild(pair2);

    // network
    var dnsList = arr(r.dns);
    if (network.length || dnsList.length) {
      var exfilDst = {};
      stolen.forEach(function (x) { exfilDst[str(x.sent_to || x.dst)] = true; });
      var ns = panel("Network contacts", { id: "network-card", badges: badge("observed", "Observed"), sub: "Every connection was answered by Burner's fake internet. Nothing reached the real one." });
      if (network.length) {
        var nb = h("tbody");
        network.forEach(function (n) {
          var dp = str(n.dest) + ":" + str(n.port);
          var isHot = exfilDst[dp] || exfilDst[str(n.dest)];
          nb.appendChild(h("tr", null,
            h("td", { "data-l": "Destination" }, h("code", { text: dp }), " ",
              n.raw_ip ? h("span", { class: "pill is-warn", text: "hard-coded IP" }) : null, " ",
              isHot ? h("span", { class: "pill is-bad", text: "received secrets" }) : null),
            h("td", { class: "num", "data-l": "Requests", text: str(n.requests) }),
            h("td", { class: "num", "data-l": "Sent", text: fmtBytes(n.bytes_out) }),
            h("td", { "data-l": "Protocol", text: arr(n.protos).filter(function (x) { return x !== "empty"; }).join(", ") }),
            h("td", { "data-l": "Step", text: str(n.step) })));
        });
        ns.appendChild(h("div", { class: "tbl-wrap" }, h("table", { class: "data stack" },
          h("thead", null, h("tr", null, h("th", { text: "Destination" }), h("th", { text: "Requests" }), h("th", { text: "Sent" }), h("th", { text: "Protocol" }), h("th", { text: "Step" }))), nb)));
      }
      if (dnsList.length) {
        ns.appendChild(h("div", { class: "dns-row" }, h("span", { text: "DNS lookups:" }),
          dnsList.map(function (d) { return h("span", { class: "pill mono", text: str(d) }); })));
      }
      out.appendChild(ns);
    }

    // report it
    var kit = r.abuse_kit;
    if (kit && cls !== "is-ok") {
      var ks = panel("Report it", { id: "kit-card", sub: "Prefilled and ready to paste to GitHub, the job board, or your security team." });
      var kitText = str(kit.text);
      var box = h("textarea", { class: "kit-text", readonly: "readonly", rows: Math.min(14, kitText.split("\n").length + 1), "aria-label": "Prefilled abuse report" });
      box.value = kitText;
      var kitCopied = h("span", { class: "copied", text: "Copied", hidden: true });
      ks.appendChild(box);
      ks.appendChild(h("div", { class: "kit-row no-print" },
        h("button", { class: "button button-secondary", type: "button", onclick: function () { copyText(kitText, kitCopied); } }, "Copy report"), kitCopied));
      if (kit.iocs && kit.iocs.length) {
        ks.appendChild(h("div", { class: "dns-row" }, h("span", { text: "Indicators (IOCs):" }),
          kit.iocs.map(function (x) { return h("span", { class: "pill mono", text: str(x) }); })));
      }
      var where = arr(kit.where).filter(function (w) { return safeUrl(w.url) && safeUrl(w.url) !== "#"; });
      if (where.length) {
        ks.appendChild(h("ul", { class: "where" }, where.map(function (w) {
          return h("li", null, h("a", { href: safeUrl(w.url), target: "_blank", rel: "noopener noreferrer", text: (str(w.name) || str(w.url)) + " ↗" }));
        })));
      }
      out.appendChild(ks);
    }

    // VM receipt
    if (vm) {
      var rs2 = panel("Burner VM receipt", { cls: "receipt", id: "receipt-card", badges: badge("observed", "Vultr Cloud Compute") });
      var dl = h("dl");
      var row = function (k, v) { if (v == null || v === "") return; dl.appendChild(h("dt", { text: k })); dl.appendChild(h("dd", null, v)); };
      if (vm.id) row("VM", h("code", { title: str(vm.id), text: str(vm.id).slice(0, 8) }));
      else row("VM", "reused development VM");
      row("Region", str(vm.region));
      row("Plan", str(vm.plan));
      if (vm.snapshot) row("Image", h("code", { text: str(vm.snapshot).slice(0, 18) }));
      if (vm.from_pool) row("Source", "pre-armed VM from the warm pool, used once, destroyed");
      else if (vm.ready_secs != null) row("Ready in", vm.ready_secs + " s");
      if (vm.lifetime_secs != null) row("Alive", vm.lifetime_secs + " s");
      if (vm.id) row("Destroyed", vm.destroyed ? h("span", { class: "ok", text: "✓ yes" }) : "no (kept)");
      var evb = r.evidence;
      var evUrl = evb && !evb.error ? safeUrl(evb.url) : null;
      if (evUrl) {
        row("Evidence bundle", h("span", null,
          "stored in Vultr Object Storage" + (evb.bytes ? " (" + Math.max(1, Math.round(Number(evb.bytes) / 1024)) + " KB)" : "") + " — ",
          h("a", { class: "link", href: evUrl, target: "_blank", rel: "noopener noreferrer", text: "Download" })));
      }
      if (vm.cost_usd_prorated != null) {
        row("Cost", "≈ $" + Number(vm.cost_usd_prorated).toFixed(4) +
          (vm.cost_usd_max != null ? " (max $" + Number(vm.cost_usd_max).toFixed(4) + " billed hourly)" : ""));
      }
      rs2.appendChild(dl);
      var shareCopied = h("span", { class: "copied", text: "Link copied", hidden: true });
      rs2.appendChild(h("div", { class: "kit-row no-print" },
        h("button", { class: "button button-secondary", type: "button", onclick: function () { copyText(url, shareCopied); } }, "Copy share link"),
        h("code", { class: "share-url", text: url }), shareCopied));
      out.appendChild(rs2);
    }
    out.appendChild(h("p", { class: "report-foot", text: "All secrets in this report are fake values Burner planted. The verdict comes from fixed rules over observed behaviour; the AI only wrote the explanation." }));
    if (chartsCard) chartsCard.activate(chartsCard.first);
  }

  // charts panel with Babel-style metric tabs; hides tabs whose data or chart function is missing
  function renderChartsPanel(r) {
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
    var el = h("section", { class: "panel-card", id: "charts-card" });
    var tablist = h("div", { class: "metric-switch", role: "tablist", "aria-label": "Charts" });
    el.appendChild(h("div", { class: "panel-head" },
      h("div", null, h("p", { class: "eyebrow", text: "Inside the sandbox" }),
        h("h2", { class: "section-title", text: "What the repo did" })), tablist));
    var panes = {}, made = {};
    var buttons = defs.map(function (d, i) {
      var b = h("button", { type: "button", role: "tab", class: "metric-option", id: "ctab-" + d.key, "aria-controls": "cpane-" + d.key,
        "aria-selected": "false", tabindex: "-1", "data-chart": d.key },
        h("span", { class: "metric-name", text: d.name }), h("span", { class: "metric-src", text: d.src }));
      b.addEventListener("click", function () { activate(d.key); });
      b.addEventListener("keydown", function (e) {
        var j = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: defs.length - 1 }[e.key];
        if (j == null) return;
        e.preventDefault();
        var k = defs[(j + defs.length) % defs.length].key;
        activate(k); $("ctab-" + k).focus();
      });
      tablist.appendChild(b);
      var pane = h("div", { class: "chart-pane", role: "tabpanel", id: "cpane-" + d.key, "aria-labelledby": "ctab-" + d.key, hidden: true });
      panes[d.key] = pane;
      el.appendChild(pane);
      return b;
    });
    function build(key) {
      var pane = panes[key];
      if (key === "timeline") {
        var host = h("div", { class: "chart-host" });
        var info = h("aside", { class: "event-panel", "aria-live": "polite" });
        idleEvent(info, trace);
        pane.appendChild(h("div", { class: "chart-body" }, host, info));
        pane.appendChild(h("p", { class: "chart-note", text: "Times are seconds from the first candidate step. Drag to zoom; the chips toggle lanes. Pick a mark to see it here." }));
        mountChart(function () { return C.timeline(host, trace, { onSelect: function (ev) { showEvent(info, ev, trace); } }); });
      } else if (key === "flow") {
        var fh = h("div", { class: "chart-host" });
        pane.appendChild(h("div", { class: "chart-body is-wide" }, fh));
        pane.appendChild(h("p", { class: "chart-note", text: "Each fake secret, the process that read it, and where it was sent. Grey secrets were planted but never left the sandbox. Line width is how much was sent." }));
        mountChart(function () { return C.flow(fh, flows); });
      } else {
        var bh = h("div", { class: "chart-host is-bare" });
        pane.appendChild(h("div", { class: "chart-body is-wide" }, bh));
        pane.appendChild(h("p", { class: "chart-note", text: "Every value is fake and unique to this scan, so a stolen one is recognisable byte for byte on the fake internet." }));
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
    info.appendChild(h("h3", { text: "Pick a mark" }));
    info.appendChild(h("p", { text: "Each dot is something the repo did inside the sandbox. Red ones touched or sent a fake secret." }));
    var counts = {};
    arr(trace && trace.events).forEach(function (e) { counts[e.lane] = (counts[e.lane] || 0) + 1; });
    var ul = h("ul", { class: "hint-list" });
    Object.keys(LANE_NAMES).forEach(function (k) { if (counts[k]) ul.appendChild(h("li", { text: LANE_NAMES[k] + ": " + counts[k] })); });
    if (trace && trace.duration != null) ul.appendChild(h("li", { text: "Duration: " + Number(trace.duration).toFixed(1) + " s" }));
    if (ul.children.length) info.appendChild(ul);
  }
  function showEvent(info, ev, trace) {
    if (!ev) { idleEvent(info, trace); return; }
    clear(info);
    var sev = str(ev.severity).toLowerCase();
    info.appendChild(h("p", { class: "eyebrow", text: LANE_NAMES[ev.lane] || str(ev.lane) }));
    info.appendChild(h("h3", { text: str(ev.label) }));
    if (ev.detail) info.appendChild(h("p", { text: str(ev.detail) }));
    var dl = h("dl");
    var row = function (k, v) { if (v == null || v === "") return; dl.appendChild(h("dt", { text: k })); dl.appendChild(h("dd", null, v)); };
    row("When", (Number(ev.t) || 0).toFixed(2) + " s");
    row("Step", str(ev.step));
    if (sev) row("Severity", h("span", { class: "sev sev-" + sev, text: sev }));
    info.appendChild(dl);
    if (ev.lane === "exfil" || ev.lane === "secrets") info.appendChild(h("p", null, badge("fake", "Fake secret"), " ", badge("observed", "Observed")));
  }

  // ---------------------------------------------------------------- track record
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
      root.appendChild(h("div", { class: "track-head" }, h("h1", { class: "display display-page", id: "track-title", tabindex: "-1", text: "Track record" }),
        h("p", { class: "field-error", role: "alert", text: "Could not load the benchmark (" + e.message + "). Try again in a moment." })));
    });
  }
  function renderTrack(b) {
    var root = $("track"); clear(root);
    var C = charts();
    var sm = b.summary || {}, samples = arr(b.samples), base = b.baseline || {};
    var mal = Number(sm.malicious) || samples.filter(function (x) { return x.expected === "malicious"; }).length;
    var ben = Number(sm.benign) || samples.filter(function (x) { return x.expected === "benign"; }).length;
    var total = mal + ben || samples.length;
    root.appendChild(h("div", { class: "back" }, h("button", { type: "button", class: "button button-secondary button-small", onclick: function () { history.length > 1 ? history.back() : go("/"); } }, "← Back")));
    root.appendChild(h("header", { class: "track-head" },
      h("p", { class: "eyebrow", text: "Track record · benchmark on a Vultr VM" + (b.meta && b.meta.finished ? ", " + b.meta.finished : "") }),
      h("h1", { class: "display display-page", id: "track-title", tabindex: "-1", text: "How Burner did on " + total + " take-homes" }),
      h("p", { class: "lede", text: mal + " malicious take-homes modelled on public reports of the Contagious Interview campaign and related npm and PyPI attacks, and " + ben + " ordinary ones. Every repo was run start to finish in Burner's sandbox, and scanned by GuardDog, an open-source static scanner, for comparison." }),
      h("ul", { class: "track-chips" },
        ["Defanged samples from public reports", "Run, not read", "We wrote the samples — rules tuned after a baseline run, both shown"].map(function (t) {
          return h("li", { class: "chip-info" }, h("span", { class: "chip-dot", "aria-hidden": "true" }), t);
        }))));
    var bn = function (label, value, of, sub) {
      return h("div", { class: "big-number" }, h("span", { class: "label", text: label }),
        h("span", { class: "value" }, String(value), of != null ? h("small", { text: " / " + of }) : null), sub ? h("span", { class: "sub", text: sub }) : null);
    };
    root.appendChild(h("div", { class: "versus", id: "versus" },
      h("section", { class: "versus-card is-us" }, h("h2", null, "Burner", badge("observed", "Runs the repo")),
        h("p", { class: "panel-sub", text: "Named the exact stolen fake secret on " + (sm.burner_named_stolen_secret != null ? sm.burner_named_stolen_secret : "?") + " of " + mal + "." }),
        h("div", { class: "big-numbers" },
          bn("Attacks caught", sm.burner_detected, mal), bn("False alarms", sm.burner_false_alarms, ben),
          bn("Median scan", sm.median_scan_secs != null ? Math.round(sm.median_scan_secs) + " s" : "—", null, "per repo"))),
      h("section", { class: "versus-card" }, h("h2", null, "GuardDog", badge("plain", "Static, reads the code")),
        h("p", { class: "panel-sub", text: "Counting any rule, even its informational capability-* ones: " + (sm.guarddog_any_rule_detected != null ? sm.guarddog_any_rule_detected : "?") + " of " + mal + " caught, but " + (sm.guarddog_any_rule_false_alarms != null ? sm.guarddog_any_rule_false_alarms : "?") + " of " + ben + " false alarms." }),
        h("div", { class: "big-numbers" },
          bn("Attacks caught", sm.guarddog_detected, mal), bn("False alarms", sm.guarddog_false_alarms, ben),
          bn("Median scan", sm.median_guarddog_secs != null ? sm.median_guarddog_secs + " s" : "—", null, "per repo")))));

    var chartCard = function (id, title, sub, fn, fallback) {
      var host = h("div", { class: "chart-host is-bare" });
      var card = h("section", { class: "panel-card", id: id }, h("h2", { class: "section-title-sm", text: title }), sub ? h("p", { class: "panel-sub", text: sub }) : null, host);
      root.appendChild(card);
      if (!(C && fn && mountChart(function () { return fn(host); }))) {
        if (fallback) host.appendChild(fallback()); else card.remove();
      }
    };
    chartCard("bench-score", "Detection and false alarms", "Share of the " + mal + " attacks caught, and of the " + ben + " clean take-homes wrongly flagged.",
      C && C.scoreBars ? function (el) { return C.scoreBars(el, sm); } : null);
    chartCard("bench-matrix", "Sample by sample", "Each row is one take-home. Hover a cell for the technique and Burner's headline.",
      C && C.benchMatrix ? function (el) { return C.benchMatrix(el, samples); } : null, function () { return matrixTable(samples); });
    chartCard("bench-times", "Scan time per sample", "Most scans hit the candidate steps' time limits (about 90 s); quick ones finished on their own.",
      C && C.scanTimes ? function (el) { return C.scanTimes(el, samples); } : null);

    var cont = arr(b.containment).length ? arr(b.containment) : CONTAINMENT_FALLBACK;
    var ct = h("section", { class: "panel-card", id: "containment" }, h("h2", { class: "section-title-sm" }, "We attacked our own sandbox", badge("observed", "Red team")),
      h("p", { class: "panel-sub", text: "Escape attempts run from inside the sandbox, as a malicious take-home would." }));
    var tb = h("tbody");
    cont.forEach(function (c) {
      var res = str(c.result).toLowerCase();
      tb.appendChild(h("tr", null, h("td", { "data-l": "Attempt", text: str(c.test) }),
        h("td", { "data-l": "Result" }, h("span", { class: "result-tag result-" + res, text: res })),
        h("td", { "data-l": "What happened", text: str(c.detail) })));
    });
    ct.appendChild(h("div", { class: "tbl-wrap" }, h("table", { class: "data stack" },
      h("thead", null, h("tr", null, h("th", { text: "Escape attempt" }), h("th", { text: "Result" }), h("th", { text: "What happened" }))), tb)));
    ct.appendChild(h("p", { class: "card-note", text: "Host side during the run: 0 packets forwarded from the sandbox bridge to the internet (iptables counter)." }));
    root.appendChild(ct);

    var pair = h("div", { class: "grid-2" });
    var dft = defenderText(b.defender);
    pair.appendChild(h("section", { class: "panel-card", id: "defender" }, h("h2", { class: "section-title-sm", text: "Windows Defender, for comparison" }),
      h("p", { class: "empty", text: dft })));
    pair.appendChild(h("section", { class: "panel-card caveat-card", id: "caveat" }, h("h2", { class: "section-title-sm", text: "The honest caveat" }),
      h("p", { text: "We wrote all " + total + " samples ourselves, from public reports, so treat this as a regression suite, not a field study." }),
      h("p", { text: "Some rules were added after the first run. Baseline before tuning: " + (base.detected != null ? base.detected : 11) + "/" + (base.of != null ? base.of : 12) +
        " detected, " + (base.false_alarms != null ? base.false_alarms : 1) + " false alarm. Final: " + sm.burner_detected + "/" + mal + ", " + sm.burner_false_alarms + "/" + ben + "." })));
    root.appendChild(pair);
    root.appendChild(h("section", { class: "panel-card", id: "cant" }, h("h2", { class: "section-title-sm", text: "What Burner can't catch" }),
      h("ul", { class: "cant-list" }, CANT.map(function (c) { return h("li", null, h("b", { text: c[0] }), c[1]); })),
      h("p", { class: "card-note", text: "A clean result means no malicious behaviour was observed in this run. It does not mean safe." })));
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
        h("td", { "data-l": "Burner", text: bc }), h("td", { "data-l": "GuardDog", text: gc })));
    });
    return h("div", { class: "tbl-wrap" }, h("table", { class: "data stack" },
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
