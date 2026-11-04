// The landing page's "chamber": a scripted, looping replay of a real Burner scan (the npm-start stealer sample).
// A mono event tape scrolls, planted fake secrets sit as redaction bars and burn when the stealer takes them, and the
// loop ends on "VM destroyed" before it resets. Decorative (the container has an aria-label; the inner nodes are
// aria-hidden). Pauses on hover, in a hidden tab and off screen; under prefers-reduced-motion it shows the final frame.
// Also here: the nav's "scrolled" state and the one-shot scroll reveals ([data-reveal]). All text via textContent.
(function () {
  "use strict";

  var BAIT = [
    { name: "AWS access key", path: "~/.aws/credentials", value: "AKIAADAAFXJMRDBZMT5N", taken: true },
    { name: "SSH private key", path: "~/.ssh/id_ed25519", value: "b3BlbnNzaC1rZXktdjEA2OyQ", taken: true },
    { name: "GitHub token", path: "~/.git-credentials", value: "ghp_7Qx2vKc9Lr0aTf3Ws8Yb", taken: true },
    { name: "Solana wallet", path: "~/.config/solana/id.json", value: "[174,22,9,201,63,88,140", taken: true },
    { name: "npm token", path: "~/.npmrc", value: "npm_x81LqP0rT4bWm2", taken: false },
    { name: "Stripe key", path: "~/work/client-api/.env", value: "sk_live_51Hx9", taken: false }
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
    { at: 9800, t: 240, lane: "vm", text: "VM destroyed · evidence → Object Storage", end: true }
  ];
  var HOLD = 3600;      // ms the final frame stays up
  var FADE = 600;
  var LOOP = 9800 + HOLD + FADE;
  var MAX_LINES = 9;

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
    var inner = el("div", "ch-inner");
    inner.setAttribute("aria-hidden", "true");

    var head = el("div", "ch-head");
    head.appendChild(el("span", "ch-id", "Case 7F3A2B · BLR · VC2-2C-4GB"));
    var rec = el("span", "ch-rec"); rec.appendChild(el("i")); rec.appendChild(el("span", null, "Replay"));
    head.appendChild(rec);

    var baitBox = el("div", "ch-bait");
    var bl = el("div", "ch-label");
    bl.appendChild(el("span", null, "Planted bait"));
    var tally = el("span", "ch-tally", "0 / 15 taken");
    bl.appendChild(tally);
    baitBox.appendChild(bl);
    var ul = el("ul", "bait-list");
    var rows = BAIT.map(function (b) {
      var li = el("li", "bait"); li.setAttribute("data-state", "cold");
      var top = el("div", "bait-top");
      top.appendChild(el("span", "bait-name", b.name));
      top.appendChild(el("span", "bait-path", b.path));
      var bar = el("div", "bait-bar");
      var val = el("span", "bait-val", b.value);
      var dest = el("span", "bait-dest", "→ " + DEST);
      bar.appendChild(el("span", "bait-redact"));
      bar.appendChild(val);
      bar.appendChild(dest);
      li.appendChild(top); li.appendChild(bar);
      ul.appendChild(li);
      return li;
    });
    baitBox.appendChild(ul);

    var tapeBox = el("div", "ch-tape-box");
    var tl = el("div", "ch-label");
    tl.appendChild(el("span", null, "Event tape"));
    tl.appendChild(el("span", "ch-lanes", "file · proc · net · exfil"));
    tapeBox.appendChild(tl);
    var tape = el("ol", "ch-tape");
    tapeBox.appendChild(tape);

    var foot = el("div", "ch-foot");
    var state = el("span", "ch-state"); state.appendChild(el("i")); var stateText = el("span", null, "VM running");
    state.appendChild(stateText);
    var clk = el("span", "ch-clock", clock(0));
    var cost = el("span", "ch-cost", "$0.0000");
    foot.appendChild(state); foot.appendChild(clk); foot.appendChild(cost);

    var stamp = el("div", "ch-stamp");
    stamp.appendChild(el("span", "ch-stamp-word", "VM destroyed"));
    stamp.appendChild(el("span", "ch-stamp-sub", "240 s · $0.0018"));

    inner.appendChild(head); inner.appendChild(baitBox); inner.appendChild(tapeBox); inner.appendChild(foot); inner.appendChild(stamp);
    root.appendChild(inner);
    return { root: root, inner: inner, rows: rows, tape: tape, tally: tally, state: stateText, clk: clk, cost: cost };
  }

  function reset(ui) {
    while (ui.tape.firstChild) ui.tape.removeChild(ui.tape.firstChild);
    ui.rows.forEach(function (r) { r.setAttribute("data-state", "cold"); });
    ui.tally.textContent = "0 / 15 taken";
    ui.state.textContent = "VM running";
    ui.clk.textContent = clock(0);
    ui.cost.textContent = "$0.0000";
    ui.root.classList.remove("is-ended", "is-fading", "is-hit");
  }

  function fire(ui, ev, animate) {
    var li = el("li", "tl tl-" + ev.lane + (animate ? " is-new" : ""));
    li.appendChild(el("span", "tl-t", clock(ev.t)));
    li.appendChild(el("span", "tl-dot"));
    li.appendChild(el("span", "tl-x", ev.text));
    ui.tape.appendChild(li);
    while (ui.tape.children.length > MAX_LINES) ui.tape.removeChild(ui.tape.firstChild);
    ui.clk.textContent = clock(ev.t);
    ui.cost.textContent = "$" + (0.0018 * Math.min(1, ev.t / 240)).toFixed(4);
    if (ev.read != null) ui.rows[ev.read].setAttribute("data-state", "read");
    if (ev.burn) {
      var n = 0;
      BAIT.forEach(function (b, i) { if (b.taken) { n++; ui.rows[i].setAttribute("data-state", "burned"); ui.rows[i].style.setProperty("--k", n); } });
      ui.tally.textContent = n + " / 15 taken";
      ui.root.classList.add("is-hit");
    }
    if (ev.end) {
      ui.state.textContent = "VM destroyed";
      ui.clk.textContent = "240 s";
      ui.cost.textContent = "$0.0018";
      ui.root.classList.add("is-ended");
    }
  }

  function finalFrame(ui) {
    reset(ui);
    TAPE.slice(-MAX_LINES).forEach(function (ev) { fire(ui, ev, false); });
    BAIT.forEach(function (b, i) { if (b.taken) ui.rows[i].setAttribute("data-state", "burned"); });
    ui.tally.textContent = "4 / 15 taken";
  }

  function init() {
    var root = document.getElementById("chamber");
    if (!root) return;
    var ui = build(root);
    st = { ui: ui, t: 0, idx: 0, last: 0, raf: 0, hover: false, visible: true, still: reduced() };
    if (st.still) { finalFrame(ui); return; }
    root.addEventListener("mouseenter", function () { st.hover = true; root.classList.add("is-paused"); });
    root.addEventListener("mouseleave", function () { st.hover = false; root.classList.remove("is-paused"); });
    if ("IntersectionObserver" in window) {
      new IntersectionObserver(function (es) { st.visible = es[0].isIntersecting; }).observe(root);
    }
    reset(ui);
    st.raf = setInterval(function () { frame(performance.now()); }, 50);   // timers, not rAF: steadier, and headless captures advance it
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
      var t = a.t + (b.t - a.t) * f * 0.9;
      ui.clk.textContent = clock(t);
    }
    if (st.t >= LOOP - FADE && !ui.root.classList.contains("is-fading")) ui.root.classList.add("is-fading");
    if (st.t >= LOOP) { st.t = 0; st.idx = 0; reset(ui); }
  }
  function view() { return document.body.dataset.view || "start"; }

  // ---------------------------------------------------------------- nav state + reveals
  function navState() {
    var on = window.scrollY > 8;
    document.documentElement.classList.toggle("is-scrolled", on);
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
    }, { rootMargin: "0px 0px -6% 0px", threshold: 0.08 });
    els.forEach(function (e, i) {
      var sib = e.parentNode ? Array.prototype.indexOf.call(e.parentNode.querySelectorAll(":scope > [data-reveal]"), e) : 0;
      e.style.setProperty("--d", Math.max(0, sib) * 70 + "ms");
      io.observe(e);
    });
  }

  var bootAt = 0;
  function boot() {
    bootAt = performance.now();
    init();
    reveals();
    navState();
    window.addEventListener("scroll", navState, { passive: true });
  }

  window.BurnerHero = {
    refresh: function () {
      if (st) st.last = 0;
      // coming back to the landing from another view: show everything at once (the first load reveals on scroll)
      if (!bootAt || performance.now() - bootAt < 1500) return;
      Array.prototype.forEach.call(document.querySelectorAll("#view-start [data-reveal]"), function (e) { e.classList.add("is-in"); });
    }
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", boot);
  else boot();
})();
