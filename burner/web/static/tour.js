// The guided walkthrough (tour.css): a spotlight and a popover that walk through Burner over the real UI. It runs the
// real npm-start stealer sample with the same buttons a person uses (window.Burner, app.js) and waits for the
// server's real events, so every number on screen comes from the server. A step whose target is missing (for example
// a chart the report has no data for) is skipped; a demo that cannot start ends the tour with a plain message.
// Arrow keys move between steps, Esc ends it. All text is inserted as text.
(function () {
  "use strict";
  var WAIT = { target: 2500, start: 15000, run: 120000, page: 15000 };
  var STORE_KEY = "burner.tour";
  var GAP = 14, EDGE = 12, PAD = 6, MIN_SIDE = 280;

  function Stale() {}
  function Stop(msg) { this.message = msg; }

  var tour = { active: false, ui: null, steps: [], index: -1, token: 0, opener: null, busy: false, failed: false,
    spec: null, targets: [], key: "", version: 0, raf: 0, timers: [], busyTimer: 0 };

  function $(sel) { return document.querySelector(sel); }
  function $$(sel) { return Array.prototype.slice.call(document.querySelectorAll(sel)); }
  function h(tag, attrs) {
    var el = document.createElement(tag);
    for (var k in attrs || {}) {
      var v = attrs[k];
      if (v == null || v === false) continue;
      if (k === "class") el.className = v;
      else if (k === "text") el.textContent = v;
      else if (k === "hidden") el.hidden = true;
      else if (k.slice(0, 2) === "on") el.addEventListener(k.slice(2), v);
      else el.setAttribute(k, v);
    }
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c != null) el.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return el;
  }
  function reduced() { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function B() { return window.Burner; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }

  // ---------------------------------------------------------------- the steps
  function toStart() { if (B().view() !== "start") B().go("/"); return sleep(60); }
  function scanState() { return B().state(); }
  function demoReady() { var S = scanState(); return S && !S.cancelled && S.info && /npm-start stealer/.test(S.info.title || ""); }

  function runDemo(ctx) {
    if (demoReady()) { B().showRun(); return sleep(60); }
    if (B().view() !== "start") B().go("/");
    ctx.busy("Starting the demo", "The tour pressed npm-start stealer for you. A throwaway VM is being prepared.", ".strip");
    return B().startSample("npm-start-stealer").catch(function (e) {
      throw new Stop("The demo couldn't start: " + (e && e.message ? e.message : "the server said no") + ".");
    }).then(function () {
      return ctx.wait(function () { var S = scanState(); return S && S.cur >= 1; }, WAIT.start);
    });
  }
  function waitContain(ctx) {
    B().showRun();
    if ($(".contain")) return Promise.resolve();
    ctx.busy("Running like a candidate", "Burner is opening the folder, installing and starting the app inside the sandbox. The next step appears when the VM is destroyed.", ".run-card");
    return ctx.wait(function () { return $(".contain") || (scanState() && scanState().ended); }, WAIT.run);
  }
  function toReport(ctx) {
    var S = scanState();
    if (!S) throw new Stop("The demo scan is no longer running.");
    if (S.report) { B().showReport(); return sleep(80); }
    B().showRun();
    ctx.busy("Waiting for the verdict", "Burner is matching what it saw against its rules and writing the explanation.", ".run-card");
    return ctx.wait(function () { var x = scanState(); return x && (x.report || x.ended); }, WAIT.run).then(function () {
      var x = scanState();
      if (!x || !x.report) throw new Stop("The demo scan finished without a report.");
      B().showReport();
      return sleep(120);
    });
  }
  function chart(key) {
    return function (ctx) {
      return toReport(ctx).then(function () { if (!B().selectChart(key)) throw new Error("no " + key); return sleep(250); });
    };
  }
  function toTrack(ctx) {
    if (B().view() !== "track") B().go("/track");
    return ctx.wait(function () { return $("#versus"); }, WAIT.page);
  }

  var STEPS = [
    { id: "start", target: "#scan-form", prepare: toStart, title: "Paste the take-home",
      body: function () {
        return "Fake recruiters send \"take-home\" repos that steal secrets the moment you run them. Paste the recruiter's message, a repo link, or pick a sample, and Burner runs it first on a throwaway Vultr VM full of fake secrets. " +
          (demoReady() ? "The npm-start stealer demo is already running." : "Press Next and the tour starts the npm-start stealer demo for you.");
      },
      note: "Arrow keys move between steps; Esc ends the tour at any time." },
    { id: "run", target: ".run-card", prepare: runDemo, title: "It runs it like you would",
      body: "Read the message, plan like a candidate, take a fresh Vultr VM, arm the sandbox, then open it in VS Code, npm install, npm start, the tests, and again 45 days later.",
      note: "Each line appears the moment the server reports it." },
    { id: "contain", target: ".contain", prepare: waitContain, title: "The VM is gone",
      body: "When the run is over the VM is destroyed, with everything the repo did to it. Nothing ran on your laptop." },
    { id: "verdict", target: [".verdict", ".kpis"], prepare: toReport, title: "A verdict from rules, not an AI",
      body: "Fixed rules over observed behaviour set the verdict; the AI only writes the explanation. Below it: how many fake secrets were taken, where they went, how long the VM lived and what it cost.",
      note: "A clean result means \"no malicious behaviour observed\" in this run, never \"safe\"." },
    { id: "stolen", target: "#stolen-card", prepare: toReport, title: "What it stole",
      body: "Every fake value is unique to this scan, so Burner can show exactly which secrets left the sandbox, where they went and during which step." },
    { id: "kit", target: "#kit-card", prepare: toReport, title: "Report it",
      body: "A prefilled abuse report with the indicators, ready to paste to GitHub, the job board or your security team." },
    { id: "track", target: "#versus", prepare: toTrack, title: "Does it work?",
      body: "13 of 13 campaign-style attacks caught with no false alarms (a static scanner caught 11), 0 false alarms on 21 real public repos, and 0 packets out when we attacked our own sandbox. Paste the next take-home a recruiter sends you before you run it." }
  ];
  function label(x) { return (typeof x === "function" ? x() : x) || ""; }

  // ---------------------------------------------------------------- engine
  function start() {
    var opener = tour.active ? tour.opener : document.activeElement;
    if (tour.active) end({ restore: false });
    remember();
    var inv = $(".tour-invite"); if (inv) inv.remove();
    mount(opener);
    tour.steps = STEPS.slice();
    show(0, []);
  }
  function end(opts) {
    opts = opts || {};
    if (!tour.active) return;
    tour.active = false;
    tour.token += 1;
    cancelAnimationFrame(tour.raf);
    clearTimers();
    clearTimeout(tour.busyTimer);
    mark([]);
    tour.ui.layer.remove();
    document.documentElement.classList.remove("tour-on");
    document.removeEventListener("keydown", onKey);
    window.removeEventListener("resize", refresh);
    window.removeEventListener("scroll", refresh, true);
    if (opts.restore !== false) restoreFocus(tour.opener);
  }
  function move(dir) {
    if (!tour.active) return;
    if (tour.failed) { if (dir > 0) end(); return; }
    if (tour.busy) return;
    var i = tour.index + dir;
    if (i < 0) return;
    if (i >= tour.steps.length) end();
    else go(i, dir);
  }
  function go(startAt, dir) {
    var token = ++tour.token;
    clearTimers();
    busy(true);
    var i = startAt;
    function next() {
      if (i < 0 || i >= tour.steps.length) { if (dir > 0) end(); else show(0, []); return Promise.resolve(); }
      var step = tour.steps[i];
      var p = Promise.resolve();
      if (step.prepare) p = p.then(function () { return step.prepare(context(i, token)); });
      return p.then(function () {
        check(token);
        if (!step.target) return [];
        return waitFor(function () { var l = resolve(step.target); return l.length ? l : null; }, WAIT.target, token).then(function (l) { return l || []; });
      }, function (err) {
        if (err instanceof Stale || err instanceof Stop) throw err;
        return [];   // this step can't be shown here
      }).then(function (els) {
        check(token);
        if (step.target && !els.length) { i += dir; return next(); }
        show(i, els);
      });
    }
    return next().catch(function (err) {
      if (err instanceof Stale || token !== tour.token) return;
      fail(err instanceof Stop ? err.message : "Something went wrong while getting the next step ready.");
    });
  }
  function context(i, token) {
    return {
      wait: function (fn, ms) { return waitFor(fn, ms, token); },
      busy: function (title, body, target) { check(token); interim(i, title, body, target); }
    };
  }
  function check(token) { if (token !== tour.token || !tour.active) throw new Stale(); }
  function waitFor(fn, ms, token) {
    var endAt = Date.now() + ms;
    return new Promise(function (resolveP, reject) {
      (function poll() {
        try { check(token); } catch (e) { reject(e); return; }
        var v = fn();
        if (v) { resolveP(v); return; }
        if (Date.now() >= endAt) { resolveP(null); return; }
        setTimeout(poll, 100);
      })();
    });
  }

  function build() {
    var ui = {
      spot: h("div", { class: "tour-spot", "aria-hidden": "true" }),
      count: h("p", { id: "tour-count", class: "tour-count" }),
      title: h("h2", { id: "tour-title", class: "tour-title" }),
      body: h("p", { id: "tour-body", class: "tour-body" }),
      note: h("p", { id: "tour-note", class: "tour-note", hidden: true }),
      status: h("p", { class: "tour-status", hidden: true }, h("span", { class: "spinner", "aria-hidden": "true" }), "Waiting for Burner…"),
      skip: h("button", { type: "button", class: "link-button tour-skip", onclick: function () { end(); } }, "Skip tour"),
      back: h("button", { type: "button", class: "button button-secondary button-small", onclick: function () { move(-1); } }, "Back"),
      next: h("button", { type: "button", class: "button button-primary button-small", onclick: function () { move(1); } }, "Next"),
      live: h("p", { class: "visually-hidden", "aria-live": "polite" })
    };
    ui.pop = h("div", { class: "tour-pop", role: "dialog", "aria-modal": "false", "aria-labelledby": "tour-title",
      "aria-describedby": "tour-body tour-note", tabindex: "-1" },
      ui.count, ui.title, ui.body, ui.note, ui.status,
      h("div", { class: "tour-actions" }, ui.skip, h("div", { class: "tour-nav" }, ui.back, ui.next)));
    ui.layer = h("div", { class: "tour-layer", "data-state": "ready" }, ui.spot, ui.pop, ui.live);
    return ui;
  }
  function mount(opener) {
    if (!tour.ui) tour.ui = build();
    tour.token += 1;
    tour.active = true; tour.opener = opener; tour.index = -1; tour.busy = false; tour.failed = false;
    tour.spec = null; tour.targets = []; tour.key = "";
    tour.ui.layer.setAttribute("data-state", "ready");
    ($("#tour-root") || document.body).appendChild(tour.ui.layer);
    document.documentElement.classList.add("tour-on");
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", refresh);
    window.addEventListener("scroll", refresh, true);
    tour.raf = requestAnimationFrame(frame);
  }
  function show(i, els) {
    var ui = tour.ui, step = tour.steps[i], first = tour.index === -1;
    tour.index = i;
    busy(false);
    setTargets(step.target || null, els);
    var last = i === tour.steps.length - 1;
    ui.layer.setAttribute("data-step", step.id);
    ui.count.textContent = "Step " + (i + 1) + " of " + tour.steps.length;
    ui.title.textContent = label(step.title);
    ui.body.textContent = label(step.body);
    ui.note.textContent = label(step.note);
    ui.note.hidden = !ui.note.textContent;
    ui.back.hidden = i === 0;
    ui.skip.hidden = last;
    ui.next.textContent = last ? "Finish" : "Next";
    animate();
    reveal(els);
    sync();
    [450, 1100, 2000].forEach(function (ms) { later(function () { reveal(tour.targets); }, ms); });
    if (!first) announce(ui.count.textContent + ": " + ui.title.textContent + ". " + ui.body.textContent);
    focusPop();
  }
  function interim(i, title, body, target) {
    var ui = tour.ui;
    ui.count.textContent = "Step " + (i + 1) + " of " + tour.steps.length;
    ui.title.textContent = title;
    ui.body.textContent = body;
    ui.note.textContent = ""; ui.note.hidden = true;
    clearTimeout(tour.busyTimer);
    ui.status.hidden = false;
    setTargets(target, resolve(target));
    animate();
    sync();
    reveal(tour.targets);
    announce(title + ". " + body);
    focusPop();
  }
  function fail(message) {
    var ui = tour.ui;
    tour.token += 1;
    busy(false);
    tour.failed = true;
    setTargets(null, []);
    ui.layer.setAttribute("data-state", "error");
    ui.count.textContent = "Tour stopped";
    ui.title.textContent = "The tour can't continue";
    ui.body.textContent = message;
    ui.note.textContent = "Everything else in Burner still works, so you can carry on by yourself.";
    ui.note.hidden = false;
    ui.back.hidden = true; ui.skip.hidden = true;
    ui.next.textContent = "Close";
    animate(); sync();
    announce("The tour can't continue. " + message);
    focusPop();
  }
  function busy(on) {
    var ui = tour.ui;
    tour.busy = on;
    ui.layer.setAttribute("data-state", on ? "busy" : tour.failed ? "error" : "ready");
    [ui.back, ui.next].forEach(function (b) { if (on) b.setAttribute("aria-disabled", "true"); else b.removeAttribute("aria-disabled"); });
    clearTimeout(tour.busyTimer);
    ui.status.hidden = true;
    if (on) tour.busyTimer = setTimeout(function () { ui.status.hidden = !tour.busy; tour.key = ""; }, 250);
    tour.version += 1;
  }
  function animate() {
    var ui = tour.ui;
    tour.version += 1;
    ui.pop.classList.remove("is-in");
    void ui.pop.offsetWidth;
    ui.pop.classList.add("is-in");
    ui.layer.classList.add("is-moving");
    later(function () { ui.layer.classList.remove("is-moving"); }, 400);
  }
  function announce(m) { tour.ui.live.textContent = m; }
  function focusPop() {
    var ui = tour.ui, a = document.activeElement;
    if (ui.pop.contains(a) && a !== ui.pop && !a.hidden) return;
    (ui.next.hidden ? ui.pop : ui.next).focus({ preventScroll: true });
  }
  function restoreFocus(opener) {
    var ok = opener && opener.isConnected && opener !== document.body && opener.getClientRects().length > 0 && !opener.disabled;
    var el = ok ? opener : $('[data-action="tour"]');
    if (el) el.focus({ preventScroll: true });
  }
  function onKey(e) {
    if (!tour.active) return;
    var el = e.target instanceof Element ? e.target : null;
    var inPop = !!(el && tour.ui.layer.contains(el));
    var loose = !el || el === document.body || el === document.documentElement;
    if (e.key === "Escape") {
      if (!inPop && !loose && el.matches("input, textarea, select, [contenteditable]")) return;
      e.preventDefault(); end();
    } else if ((e.key === "ArrowRight" || e.key === "ArrowLeft") && (inPop || loose) && !e.altKey && !e.ctrlKey && !e.metaKey && !e.shiftKey) {
      e.preventDefault(); move(e.key === "ArrowRight" ? 1 : -1);
    }
  }

  function visible(el) {
    if (!el || !el.isConnected) return false;
    var r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  }
  function resolve(spec) {
    if (!spec) return [];
    return [].concat(spec).reduce(function (a, sel) { return a.concat($$(sel)); }, []).filter(visible);
  }
  function setTargets(spec, els) { tour.spec = spec; tour.targets = els; mark(els); tour.key = ""; }
  function mark(els) {
    $$(".is-tour-target").forEach(function (el) { if (els.indexOf(el) === -1) el.classList.remove("is-tour-target"); });
    els.forEach(function (el) { el.classList.add("is-tour-target"); });
  }
  function unionRect(els) {
    var rs = els.map(function (el) { return el.getBoundingClientRect(); });
    var top = Math.min.apply(null, rs.map(function (r) { return r.top; })), left = Math.min.apply(null, rs.map(function (r) { return r.left; }));
    var bottom = Math.max.apply(null, rs.map(function (r) { return r.bottom; })), right = Math.max.apply(null, rs.map(function (r) { return r.right; }));
    return { top: top, left: left, bottom: bottom, right: right, width: right - left, height: bottom - top };
  }
  function onScreen(r) {
    if (!r) return null;
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var top = Math.max(r.top, 0), left = Math.max(r.left, 0), bottom = Math.min(r.bottom, vh), right = Math.min(r.right, vw);
    return bottom - top > 1 && right - left > 1 ? { top: top, left: left, bottom: bottom, right: right, width: right - left, height: bottom - top } : null;
  }
  function clamp(v, lo, hi) { return Math.min(Math.max(v, lo), Math.max(lo, hi)); }
  function frame() { if (!tour.active) return; tour.raf = requestAnimationFrame(frame); sync(); }
  function refresh() { tour.key = ""; if (tour.active) sync(); }
  function sync() {
    var ui = tour.ui;
    if (tour.spec && (!tour.targets.length || !tour.targets.every(visible))) { tour.targets = resolve(tour.spec); mark(tour.targets); }
    var rect = tour.targets.length ? onScreen(unionRect(tour.targets)) : null;
    var key = [rect ? [rect.top, rect.left, rect.width, rect.height].map(Math.round).join(",") : "-", window.innerWidth, window.innerHeight, tour.version].join("|");
    if (key === tour.key) return;
    tour.key = key;
    spotlight(rect);
    place(rect);
    void ui;
  }
  function spotlight(rect) {
    var spot = tour.ui.spot;
    spot.classList.toggle("is-none", !rect);
    if (!rect) { spot.style.top = "50%"; spot.style.left = "50%"; spot.style.width = "0px"; spot.style.height = "0px"; return; }
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    var top = Math.max(rect.top - PAD, 3), left = Math.max(rect.left - PAD, 3);
    var bottom = Math.min(rect.bottom + PAD, vh - 3), right = Math.min(rect.right + PAD, vw - 3);
    spot.style.top = top + "px"; spot.style.left = left + "px";
    spot.style.width = Math.max(0, right - left) + "px"; spot.style.height = Math.max(0, bottom - top) + "px";
    spot.style.borderRadius = radius();
  }
  function radius() {
    if (tour.targets.length !== 1) return "";
    var r = getComputedStyle(tour.targets[0]).borderTopLeftRadius;
    var px = parseFloat(r) || 0;
    return px >= 8 ? (px + PAD) + "px" : "";
  }
  function place(rect) {
    var pop = tour.ui.pop;
    var vw = document.documentElement.clientWidth, vh = window.innerHeight;
    pop.style.width = "";
    var w = pop.offsetWidth, ph = pop.offsetHeight;
    var x = (vw - w) / 2, y = (vh - ph) / 2, side = "center";
    if (rect) {
      var room = { bottom: vh - rect.bottom - GAP - EDGE, top: rect.top - GAP - EDGE, right: vw - rect.right - GAP - EDGE, left: rect.left - GAP - EDGE };
      var across = rect.left + rect.width / 2 - w / 2;
      var beside = room.right >= room.left ? "right" : "left";
      if (room.bottom >= ph) { side = "bottom"; x = across; y = rect.bottom + GAP; }
      else if (room.top >= ph) { side = "top"; x = across; y = rect.top - GAP - ph; }
      else if (room[beside] >= MIN_SIDE) {
        w = Math.min(w, room[beside]); pop.style.width = w + "px"; ph = pop.offsetHeight; side = beside;
        x = beside === "right" ? rect.right + GAP : rect.left - GAP - w;
        y = rect.top + rect.height / 2 - ph / 2;
      } else { side = "dock"; x = vw < 720 ? (vw - w) / 2 : EDGE; y = vh - ph - EDGE; }
    }
    pop.style.left = Math.round(clamp(x, EDGE, vw - w - EDGE)) + "px";
    pop.style.top = Math.round(clamp(y, EDGE, vh - ph - EDGE)) + "px";
    pop.setAttribute("data-side", side);
  }
  function reveal(els) {
    if (!tour.active || !els || !els.length || els.some(function (el) { return !el.isConnected; })) return;
    var r = unionRect(els), vh = window.innerHeight, m = 16, pop = tour.ui.pop;
    var width = pop.style.width; pop.style.width = "";
    var ph = pop.offsetHeight + GAP; pop.style.width = width;
    var top = null;
    if (r.height + ph + 2 * m <= vh) {
      var fits = r.top >= m && (r.bottom + ph <= vh - m || (r.top - ph >= m && r.bottom <= vh - m));
      if (!fits) top = (vh - r.height - ph) / 2;
    } else if (r.height + 2 * m <= vh) {
      if (r.top < m || r.bottom > vh - m) top = (vh - r.height) / 2;
    } else top = m;
    if (top !== null && Math.abs(r.top - top) > 2) window.scrollBy({ top: r.top - top, behavior: reduced() ? "instant" : "smooth" });
  }
  function later(fn, ms) { tour.timers.push(setTimeout(fn, ms)); }
  function clearTimers() { tour.timers.forEach(clearTimeout); tour.timers = []; }

  // ---------------------------------------------------------------- the first-visit invitation
  function remember() { try { localStorage.setItem(STORE_KEY, "seen"); } catch (e) { /* the invitation shows again */ } }
  // v4: no first-visit chip in the hero; the tour is started from the nav.

  window.BurnerTour = { start: start, end: end };
})();
