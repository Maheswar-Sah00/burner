// The Start screen's backdrop: a dotted "sandbox" (the fake home directory Burner builds inside a throwaway VM) with
// the fake secrets it plants floating over it, and now and then an arc that flies from a secret to the "fake
// internet" sink at the edge, which turns red when it lands. Decorative (aria-hidden): it shows no data.
// Static layer (dots, sandbox outline, glows) is drawn once per size/theme; the arcs are drawn per frame.
// Paused for prefers-reduced-motion, a hidden tab, or when the band is off screen. Theme-aware via CSS tokens.
(function () {
  "use strict";
  var SECRETS = [
    { label: "AWS access key", at: [0.075, 0.17] },
    { label: "SSH private key", at: [0.07, 0.45] },
    { label: "MetaMask vault", at: [0.56, 0.66] },
    { label: ".env (another project)", at: [0.19, 0.31] },
    { label: "Chrome passwords", at: [0.4, 0.57] },
    { label: "Solana wallet", at: [0.45, 0.82] },
    { label: "GitHub token", at: [0.66, 0.62] },
    { label: "Exodus wallet", at: [0.26, 0.66] },
    { label: "npm token", at: [0.73, 0.84] },
    { label: "OpenAI key", at: [0.35, 0.92] },
    { label: "Stripe key", at: [0.6, 0.93] }
  ];
  var DOT = 11;          // px between dots
  var ARC_EVERY = 1500;  // ms between new arcs
  var ARC_MS = 1500;     // flight time

  var st = null;

  function css(el, name, fallback) {
    var v = getComputedStyle(el).getPropertyValue(name).trim();
    return v || fallback;
  }
  function reduced() { return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches; }
  function overlaps(a, b, pad) {
    return a.left < b.right + pad && a.right > b.left - pad && a.top < b.bottom + pad && a.bottom > b.top - pad;
  }

  function init() {
    var band = document.querySelector(".band");
    var canvas = band && band.querySelector(".hero-art");
    if (!band || !canvas || !canvas.getContext) return;
    var pins = band.querySelector(".pins");
    var sink = document.createElement("div");
    sink.className = "sink";
    var b = document.createElement("b"); b.textContent = "Fake internet";
    var s = document.createElement("span"); s.textContent = "answers everything, records it";
    sink.appendChild(b); sink.appendChild(s);
    band.appendChild(sink);
    var chips = SECRETS.map(function (x, i) {
      var el = document.createElement("span");
      el.className = "pin is-new";
      el.style.setProperty("--i", i);
      el.textContent = x.label;
      pins.appendChild(el);
      setTimeout(function () { el.classList.remove("is-new"); }, 1400);
      return { el: el, spec: x, x: 0, y: 0, shown: false };
    });
    st = { band: band, canvas: canvas, ctx: canvas.getContext("2d"), sink: sink, chips: chips, w: 0, h: 0, dpr: 1,
      layer: document.createElement("canvas"), arcs: [], hits: [], last: 0, raf: 0, visible: true, sinkPt: null };
    var ro = new ResizeObserver(function () { layout(); });
    ro.observe(band);
    var card = band.querySelector(".scan-card");
    if (card) ro.observe(card);
    document.addEventListener("burner:theme", function () { paintLayer(); frame(performance.now(), true); });
    document.addEventListener("visibilitychange", loop);
    if (window.IntersectionObserver) {
      new IntersectionObserver(function (es) { st.visible = es[0].isIntersecting; loop(); }).observe(band);
    }
    if (window.matchMedia) {
      var mq = window.matchMedia("(prefers-reduced-motion: reduce)");
      if (mq.addEventListener) mq.addEventListener("change", function () { frame(performance.now(), true); loop(); });
    }
    layout();
  }

  function obstacles() {
    var br = st.band.getBoundingClientRect();
    var out = [];
    [".scan-card", ".evidence-card"].forEach(function (sel) {
      var el = st.band.querySelector(sel);
      if (!el) return;
      var r = el.getBoundingClientRect();
      if (r.width) out.push({ left: r.left - br.left, top: r.top - br.top, right: r.right - br.left, bottom: r.bottom - br.top });
    });
    return out;
  }

  function layout() {
    var br = st.band.getBoundingClientRect();
    if (!br.width || !br.height) return;
    st.w = br.width; st.h = br.height;
    st.dpr = Math.min(window.devicePixelRatio || 1, 2);
    [st.canvas, st.layer].forEach(function (c) { c.width = Math.round(st.w * st.dpr); c.height = Math.round(st.h * st.dpr); });
    var obs = obstacles();
    var narrow = st.w < 1000;
    // the sink: right edge, in the free space
    var card = obs[0];
    var sinkTop = narrow && card ? card.bottom + 26 : st.h * 0.5;
    st.sink.style.right = (narrow ? 10 : 22) + "px";
    st.sink.style.top = Math.round(sinkTop) + "px";
    var sr = st.sink.getBoundingClientRect();
    var sinkBox = { left: sr.left - br.left, top: sr.top - br.top, right: sr.right - br.left, bottom: sr.bottom - br.top };
    st.sinkPt = { x: sinkBox.left + 2, y: (sinkBox.top + sinkBox.bottom) / 2 };
    obs.push(sinkBox);
    // the sandbox: everything left of the sink
    st.box = { x: 14, y: narrow && card ? card.bottom - 40 : 54, r: 18 };
    st.box.w = sinkBox.left - 34 - st.box.x;
    st.box.h = st.h - st.box.y - 14;
    // place the chips: preferred spot, else the first free spot on a coarse grid
    var placed = [];
    var max = st.w < 520 ? 5 : narrow ? 8 : SECRETS.length;
    var candidates = [];
    for (var fy = 0.06; fy < 0.97; fy += 0.055) for (var fx = 0.06; fx < 0.95; fx += 0.09) candidates.push([fx, fy]);
    st.chips.forEach(function (c, i) {
      c.shown = false;
      c.el.style.visibility = "hidden";
      if (i >= max) return;
      var w = c.el.offsetWidth, h = c.el.offsetHeight;
      var tries = [c.spec.at].concat(candidates);
      for (var k = 0; k < tries.length; k++) {
        var x = tries[k][0] * st.w, y = tries[k][1] * st.h;
        var rect = { left: x - w / 2, right: x + w / 2, top: y - h - 10, bottom: y + 6 };
        if (rect.left < 8 || rect.right > st.w - 8 || rect.top < st.box.y + 8 || rect.bottom > st.h - 8) continue;
        if (rect.right > st.box.x + st.box.w - 6) continue;
        if (obs.some(function (o) { return overlaps(rect, o, 10); })) continue;
        if (placed.some(function (o) { return overlaps(rect, o, 8); })) continue;
        placed.push(rect);
        c.x = x; c.y = y; c.shown = true;
        c.el.style.transform = "translate(" + Math.round(x - w / 2) + "px," + Math.round(y - h - 10) + "px)";
        c.el.style.visibility = "visible";
        break;
      }
    });
    paintLayer();
    frame(performance.now(), true);
    loop();
  }

  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }

  function paintLayer() {
    if (!st.w) return;
    var ctx = st.layer.getContext("2d");
    var b = st.band;
    var dot = css(b, "--art-dot", "#b3c3c9"), lit = css(b, "--art-lit", "#ff5a1f"), boxc = css(b, "--art-box", "rgba(0,0,0,.16)");
    var grid = css(b, "--art-grid", "rgba(0,0,0,.05)"), ink3 = css(b, "--ink-3", "#677278");
    ctx.setTransform(st.dpr, 0, 0, st.dpr, 0, 0);
    ctx.clearRect(0, 0, st.w, st.h);
    // faint grid lines (like Babel's graticule)
    ctx.strokeStyle = grid; ctx.lineWidth = 1;
    for (var gx = 0; gx < st.w; gx += DOT * 8) { ctx.beginPath(); ctx.moveTo(gx + 0.5, 0); ctx.lineTo(gx + 0.5, st.h); ctx.stroke(); }
    for (var gy = 0; gy < st.h; gy += DOT * 8) { ctx.beginPath(); ctx.moveTo(0, gy + 0.5); ctx.lineTo(st.w, gy + 0.5); ctx.stroke(); }
    var bx = st.box, shown = st.chips.filter(function (c) { return c.shown; });
    // dots: inside the sandbox full strength, outside faint; near a secret, lit
    for (var y = DOT / 2; y < st.h; y += DOT) {
      for (var x = DOT / 2; x < st.w; x += DOT) {
        var inside = x > bx.x && x < bx.x + bx.w && y > bx.y && y < bx.y + bx.h;
        var heat = 0;
        for (var i = 0; i < shown.length; i++) {
          var dx = x - shown[i].x, dy = y - shown[i].y, d = dx * dx + dy * dy;
          if (d < 1500) heat = Math.max(heat, 1 - d / 1500);
        }
        var n = (Math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1;  // stable noise
        if (!inside && Math.abs(n) < 0.55) continue;
        ctx.globalAlpha = inside ? (heat ? 0.3 + heat * 0.55 : 0.85) : 0.35;
        ctx.fillStyle = heat && inside ? lit : dot;
        ctx.beginPath(); ctx.arc(x, y, heat && inside ? 1.25 + heat * 0.6 : 1.2, 0, Math.PI * 2); ctx.fill();
      }
    }
    ctx.globalAlpha = 1;
    // the sandbox outline + label
    ctx.setLineDash([5, 5]); ctx.strokeStyle = boxc; ctx.lineWidth = 1.5;
    roundRect(ctx, bx.x + 0.5, bx.y + 0.5, bx.w, bx.h, bx.r); ctx.stroke();
    ctx.setLineDash([]);
    ctx.fillStyle = ink3;
    ctx.font = "600 10.5px Figtree, system-ui, sans-serif";
    if ("letterSpacing" in ctx) ctx.letterSpacing = "1.2px";
    var lbl = "GVISOR SANDBOX · FAKE HOME DIRECTORY";
    var tw = ctx.measureText(lbl).width;
    var lx = bx.x + bx.w - tw - 18, ly = bx.y + bx.h - 14;
    if (lx > bx.x + 20) ctx.fillText(lbl, lx, ly);
    if ("letterSpacing" in ctx) ctx.letterSpacing = "0px";
    // markers under the chips
    shown.forEach(function (c) {
      ctx.fillStyle = lit;
      ctx.beginPath(); ctx.arc(c.x, c.y, 3.6, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = css(b, "--surface", "#fff"); ctx.lineWidth = 1.6; ctx.stroke();
    });
  }

  function bez(p0, p1, p2, t) {
    var u = 1 - t;
    return { x: u * u * p0.x + 2 * u * t * p1.x + t * t * p2.x, y: u * u * p0.y + 2 * u * t * p1.y + t * t * p2.y };
  }

  function spawn(now) {
    var shown = st.chips.filter(function (c) { return c.shown && !c.flying; });
    if (!shown.length || !st.sinkPt) return;
    var c = shown[Math.floor(Math.random() * shown.length)];
    c.flying = true;
    var p0 = { x: c.x, y: c.y }, p2 = st.sinkPt;
    var mid = { x: (p0.x + p2.x) / 2, y: Math.min(p0.y, p2.y) - 60 - Math.random() * 90 };
    st.arcs.push({ chip: c, p0: p0, p1: mid, p2: p2, t0: now });
  }

  function frame(now, still) {
    var ctx = st.ctx;
    if (!st.w) return;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.clearRect(0, 0, st.canvas.width, st.canvas.height);
    ctx.drawImage(st.layer, 0, 0);
    ctx.setTransform(st.dpr, 0, 0, st.dpr, 0, 0);
    var arcC = css(st.band, "--art-arc", "#ff5a1f"), sinkC = css(st.band, "--art-sink", "#b3261e");
    if (still) {   // reduced motion / first paint: two faint resting arcs, no movement
      if (reduced()) {
        st.chips.filter(function (c) { return c.shown; }).slice(0, 2).forEach(function (c) {
          var p0 = { x: c.x, y: c.y }, p2 = st.sinkPt, p1 = { x: (p0.x + p2.x) / 2, y: Math.min(p0.y, p2.y) - 90 };
          ctx.strokeStyle = arcC; ctx.globalAlpha = 0.35; ctx.lineWidth = 1.4; ctx.setLineDash([3, 4]);
          ctx.beginPath(); ctx.moveTo(p0.x, p0.y); ctx.quadraticCurveTo(p1.x, p1.y, p2.x, p2.y); ctx.stroke();
          ctx.setLineDash([]); ctx.globalAlpha = 1;
        });
      }
      return;
    }
    st.arcs = st.arcs.filter(function (a) {
      var t = Math.min(1, (now - a.t0) / ARC_MS);
      var e = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;
      var tail = Math.max(0, e - 0.28);
      var steps = 24;
      for (var i = 0; i < steps; i++) {
        var ta = tail + (e - tail) * (i / steps), tb = tail + (e - tail) * ((i + 1) / steps);
        var pa = bez(a.p0, a.p1, a.p2, ta), pb = bez(a.p0, a.p1, a.p2, tb);
        ctx.strokeStyle = arcC; ctx.globalAlpha = (i + 1) / steps * 0.95; ctx.lineWidth = 0.6 + 1.8 * (i / steps);
        ctx.lineCap = "round";
        ctx.beginPath(); ctx.moveTo(pa.x, pa.y); ctx.lineTo(pb.x, pb.y); ctx.stroke();
      }
      var head = bez(a.p0, a.p1, a.p2, e);
      ctx.globalAlpha = 1; ctx.fillStyle = arcC;
      ctx.beginPath(); ctx.arc(head.x, head.y, 3, 0, Math.PI * 2); ctx.fill();
      if (t >= 1) {
        a.chip.flying = false;
        hit(a.chip, now);
        return false;
      }
      return true;
    });
    st.hits = st.hits.filter(function (hh) {
      var k = (now - hh) / 700;
      if (k >= 1) return false;
      ctx.globalAlpha = 1 - k; ctx.strokeStyle = sinkC; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(st.sinkPt.x - 2, st.sinkPt.y, 6 + k * 26, 0, Math.PI * 2); ctx.stroke();
      return true;
    });
    ctx.globalAlpha = 1;
  }

  function hit(chip, now) {
    st.hits.push(now);
    st.sink.classList.add("is-hit");
    chip.el.classList.add("is-taken");
    clearTimeout(st.sinkTimer);
    st.sinkTimer = setTimeout(function () { st.sink.classList.remove("is-hit"); }, 900);
    setTimeout(function () { chip.el.classList.remove("is-taken"); }, 2600);
  }

  function running() { return st && st.visible && !document.hidden && !reduced() && st.w > 0; }

  function loop() {
    if (!st) return;
    if (!running()) { cancelAnimationFrame(st.raf); st.raf = 0; return; }
    if (st.raf) return;
    var tick = function (now) {
      if (!running()) { st.raf = 0; return; }
      if (now - st.last > ARC_EVERY) { st.last = now; spawn(now); }
      frame(now, false);
      st.raf = requestAnimationFrame(tick);
    };
    st.raf = requestAnimationFrame(tick);
  }

  window.BurnerHero = { refresh: function () { if (st) layout(); } };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
