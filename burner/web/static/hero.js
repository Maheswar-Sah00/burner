// The landing page: the showcase "chamber" (a scripted, looping replay of a real Burner scan of the npm-start stealer
// sample, drawn as an editor window: the planted bait on top, the event tape as the terminal), the nav that docks into a
// floating bar on scroll, one-shot scroll reveals ([data-reveal]) and mounting every <canvas data-dither> (dither.js).
// The replay is decorative (its container has an aria-label; inner nodes are aria-hidden). It pauses on hover, in a
// hidden tab, off screen and on other views; under prefers-reduced-motion it shows the final frame. Text via textContent.
(function () {
  "use strict";

  var BAIT = [
    { name: "aws_access_key_id", path: "~/.aws/credentials", value: "AKIAADAAFXJMRDBZMT5N", taken: true },
    { name: "id_ed25519", path: "~/.ssh/id_ed25519", value: "b3BlbnNzaC1rZXktdjEA2OyQ", taken: true },
    { name: "github_token", path: "~/.git-credentials", value: "ghp_7Qx2vKc9Lr0aTf3Ws8Yb", taken: true },
    { name: "solana_wallet", path: "~/.config/solana/id.json", value: "[174,22,9,201,63,88,140", taken: true },
    { name: "npm_token", path: "~/.npmrc", value: "npm_x81LqP0rT4bWm2", taken: false },
    { name: "STRIPE_KEY", path: "~/work/client-api/.env", value: "sk_live_51Hx9", taken: false }
  ];
  var DEST = "203.0.113.55:1224";
  // at = ms into the loop; t = the sandbox clock shown on the tape; lane = colour; act = what happens to the bait
  var TAPE = [
    { at: 300, t: 0.0, lane: "vm", text: "VM 1a2b3c4d up · vc2-2c-4gb · blr" },
    { at: 1000, t: 0.6, lane: "setup", text: "plant 15 fake secrets · fake internet on" },
    { at: 1800, t: 1.2, lane: "run", text: "$ code . && npm install" },
    { at: 2700, t: 3.5, lane: "run", text: "$ npm start" },
    { at: 3600, t: 31.2, lane: "proc", text: "node server/index.js → spawn node -e …" },
    { at: 4400, t: 33.0, lane: "file", text: "open ~/.aws/credentials", read: 0 },
    { at: 4800, t: 33.1, lane: "file", text: "open ~/.ssh/id_ed25519", read: 1 },
    { at: 5200, t: 33.2, lane: "file", text: "open ~/.git-credentials", read: 2 },
    { at: 5600, t: 33.3, lane: "file", text: "open ~/.config/solana/id.json", read: 3 },
    { at: 6500, t: 33.4, lane: "exfil", text: "POST " + DEST + "/uploads ← 4 secrets · 11.1 KB", burn: true },
    { at: 7600, t: 33.5, lane: "net", text: "captured by the fake internet · real one unreachable" },
    { at: 8700, t: 78.0, lane: "run", text: "$ faketime +45d npm start" },
    { at: 9800, t: 90, lane: "vm", text: "VM destroyed · evidence → Object Storage", end: true }
  ];
  var HOLD = 3600;      // ms the final frame stays up
  var FADE = 600;
  var LOOP = 9800 + HOLD + FADE;
  var MAX_LINES = 7;

  function reduced() { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }
  function clock(t) { return "T+" + (t < 100 ? (t < 10 ? "00" : "0") : "") + t.toFixed(1); }

  var st = null;

  function build(root) {
    while (root.firstChild) root.removeChild(root.firstChild);
    var win = el("div", "ch-inner");
    win.setAttribute("aria-hidden", "true");

    var bar = el("div", "ch-bar");
    var lights = el("span", "ch-lights"); lights.appendChild(el("i")); lights.appendChild(el("i")); lights.appendChild(el("i"));
    bar.appendChild(lights);
    var tabs = el("span", "ch-tabs");
    tabs.appendChild(el("span", "ch-tab is-on", "bait.env"));
    tabs.appendChild(el("span", "ch-tab", "package.json"));
    tabs.appendChild(el("span", "ch-tab", "server/index.js"));
    bar.appendChild(tabs);
    var rec = el("span", "ch-rec"); rec.appendChild(el("i")); rec.appendChild(el("span", null, "Replay"));
    bar.appendChild(rec);

    var code = el("ol", "ch-code");
    var rows = BAIT.map(function (b, i) {
      var li = el("li", "bait"); li.setAttribute("data-state", "cold");
      li.appendChild(el("span", "bait-n", String(i + 1)));
      li.appendChild(el("span", "bait-name", b.name));
      var val = el("span", "bait-bar");
      val.appendChild(el("span", "bait-redact"));
      val.appendChild(el("span", "bait-val", b.value));
      li.appendChild(val);
      li.appendChild(el("span", "bait-dest", "→ " + DEST));
      code.appendChild(li);
      return li;
    });

    var th = el("div", "ch-term-head");
    var tt = el("span", "ch-ttabs");
    tt.appendChild(el("span", "ch-ttab is-on", "Terminal"));
    tt.appendChild(el("span", "ch-ttab", "Network"));
    tt.appendChild(el("span", "ch-ttab", "Bait"));
    th.appendChild(tt);
    var meta = el("span", "ch-meta");
    var tally = el("span", "ch-tally", "0 / 15 taken");
    var clk = el("span", "ch-clock", clock(0));
    var cost = el("span", "ch-cost", "$0.0000");
    meta.appendChild(tally); meta.appendChild(clk); meta.appendChild(cost);
    th.appendChild(meta);

    var tape = el("ol", "ch-tape");

    var stamp = el("div", "ch-stamp");
    stamp.appendChild(el("span", "ch-stamp-word", "VM destroyed"));
    stamp.appendChild(el("span", "ch-stamp-sub", "90 s · ~$0.002 · nothing on your laptop"));

    win.appendChild(bar); win.appendChild(code); win.appendChild(th); win.appendChild(tape); win.appendChild(stamp);
    root.appendChild(win);
    return { root: root, inner: win, rows: rows, tape: tape, tally: tally, clk: clk, cost: cost };
  }

  function reset(ui) {
    while (ui.tape.firstChild) ui.tape.removeChild(ui.tape.firstChild);
    ui.rows.forEach(function (r) { r.setAttribute("data-state", "cold"); });
    ui.tally.textContent = "0 / 15 taken";
    ui.clk.textContent = clock(0);
    ui.cost.textContent = "$0.0000";
    ui.root.classList.remove("is-ended", "is-fading", "is-hit");
  }

  function fire(ui, ev, animate) {
    var li = el("li", "tl tl-" + ev.lane + (animate ? " is-new" : ""));
    li.appendChild(el("span", "tl-t", clock(ev.t)));
    li.appendChild(el("span", "tl-x", ev.text));
    ui.tape.appendChild(li);
    while (ui.tape.children.length > MAX_LINES) ui.tape.removeChild(ui.tape.firstChild);
    ui.clk.textContent = clock(ev.t);
    ui.cost.textContent = "$" + (0.002 * Math.min(1, ev.t / 90)).toFixed(4);
    if (ev.read != null) ui.rows[ev.read].setAttribute("data-state", "read");
    if (ev.burn) {
      var n = 0;
      BAIT.forEach(function (b, i) { if (b.taken) { n++; ui.rows[i].setAttribute("data-state", "burned"); ui.rows[i].style.setProperty("--k", n); } });
      ui.tally.textContent = n + " / 15 taken";
      ui.root.classList.add("is-hit");
    }
    if (ev.end) {
      ui.clk.textContent = "90 s";
      ui.cost.textContent = "~$0.002";
      ui.root.classList.add("is-ended");
    }
  }

  function finalFrame(ui) {
    reset(ui);
    TAPE.slice(-MAX_LINES).forEach(function (ev) { fire(ui, ev, false); });
    BAIT.forEach(function (b, i) { if (b.taken) ui.rows[i].setAttribute("data-state", "burned"); });
    ui.tally.textContent = "4 / 15 taken";
    ui.root.classList.add("is-hit");
  }

  function init() {
    var root = document.getElementById("chamber");
    if (!root) return;
    var ui = build(root);
    st = { ui: ui, t: 0, idx: 0, last: 0, timer: 0, hover: false, visible: true, still: reduced() };
    if (st.still) { finalFrame(ui); return; }
    root.addEventListener("mouseenter", function () { st.hover = true; root.classList.add("is-paused"); });
    root.addEventListener("mouseleave", function () { st.hover = false; root.classList.remove("is-paused"); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { st.visible = es[es.length - 1].isIntersecting; }).observe(root);
    }
    reset(ui);
    st.timer = setInterval(function () { frame(performance.now()); }, 50);   // timers, not rAF: steadier, and headless captures advance it
  }

  function frame(now) {
    var dt = st.last ? Math.min(100, now - st.last) : 0;
    st.last = now;
    if (st.hover || !st.visible || document.hidden || view() !== "start") return;
    st.t += dt;
    var ui = st.ui;
    while (st.idx < TAPE.length && st.t >= TAPE[st.idx].at) { fire(ui, TAPE[st.idx], true); st.idx++; }
    // between events, let the clock run so the tape feels live
    if (st.idx > 0 && st.idx < TAPE.length) {
      var a = TAPE[st.idx - 1], b = TAPE[st.idx];
      var f = Math.min(1, (st.t - a.at) / (b.at - a.at));
      ui.clk.textContent = clock(a.t + (b.t - a.t) * f * 0.9);
    }
    if (st.t >= LOOP - FADE && !ui.root.classList.contains("is-fading")) ui.root.classList.add("is-fading");
    if (st.t >= LOOP) { st.t = 0; st.idx = 0; reset(ui); }
  }
  function view() { return document.body.dataset.view || "start"; }

  // ---------------------------------------------------------------- nav dock + reveals + dither art
  function navState() {
    document.documentElement.classList.toggle("is-scrolled", window.scrollY > 40);
  }
  function reveals() {
    var els = Array.prototype.slice.call(document.querySelectorAll("[data-reveal]"));
    if (reduced() || !("IntersectionObserver" in window)) { els.forEach(function (e) { e.classList.add("is-in"); }); return; }
    document.documentElement.classList.add("can-reveal");
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add("is-in");
        io.unobserve(en.target);
      });
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.06 });
    els.forEach(function (e) {
      var sib = e.parentNode ? Array.prototype.indexOf.call(e.parentNode.querySelectorAll(":scope > [data-reveal]"), e) : 0;
      e.style.setProperty("--d", Math.max(0, sib) * 60 + "ms");
      io.observe(e);
    });
  }
  function art() { if (window.BurnerDither) window.BurnerDither.auto(document); }

  var bootAt = 0;
  function boot() {
    bootAt = performance.now();
    init();
    reveals();
    navState();
    art();
    window.addEventListener("scroll", navState, { passive: true });
  }

  window.BurnerHero = {
    refresh: function () {
      if (st) st.last = 0;
      art();
      // coming back to the landing from another view: show everything at once (the first load reveals on scroll)
      if (!bootAt || performance.now() - bootAt < 1500) return;
      Array.prototype.forEach.call(document.querySelectorAll("#view-start [data-reveal]"), function (e) { e.classList.add("is-in"); });
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
