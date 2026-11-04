// Burner halftone / dither art — window.BurnerDither (no dependencies).
//
//   BurnerDither.field(canvas, opts)        full-bleed animated halftone field (smoke rising, ember hot-spots, sparks)
//   BurnerDither.icon(canvas, name, opts)   isometric dot illustration; names in BurnerDither.names
//   BurnerDither.text(canvas, string, opts) text rasterised and redrawn as dots (the giant statement)
//   BurnerDither.auto(root)                 mounts every <canvas data-dither="field|icon|text"> under root (once each)
//   BurnerDither.refresh()                  re-reads the theme colours and redraws everything
//
// Each call returns a handle { redraw(), set(opts), destroy(), canvas }. Calling again on the same canvas replaces it.
// Common opts: pitch (CSS px between dots), dot (dot size as a share of the pitch), alpha, animate (bool), ember (bool).
// How it draws: values are computed on a coarse cell grid (one cell per dot) into an ImageData, scaled up crisply to
// device pixels and masked by a one-dot pattern tile, so every dot lands on whole device pixels (sharp on hi-dpi, dpr
// capped at 2). Colours come from --dot and --ember and are re-read on the document "burner:theme" event.
// Animation runs on one shared timer at <= 30 fps, only for canvases that are on screen, in a visible tab and not under
// prefers-reduced-motion (which always gets a single still frame).
(function () {
  "use strict";
  if (window.BurnerDither) return;

  var DPR_CAP = 2, FPS = 30;
  var B8 = [0, 32, 8, 40, 2, 34, 10, 42, 48, 16, 56, 24, 50, 18, 58, 26, 12, 44, 4, 36, 14, 46, 6, 38, 60, 28, 52, 20, 62, 30, 54, 22,
    3, 35, 11, 43, 1, 33, 9, 41, 51, 19, 59, 27, 49, 17, 57, 25, 15, 47, 7, 39, 13, 45, 5, 37, 63, 31, 55, 23, 61, 29, 53, 21];
  var BAYER = new Float32Array(64);
  for (var b = 0; b < 64; b++) BAYER[b] = (B8[b] + 0.5) / 64;
  function bayer(i, j) { return BAYER[((j & 7) << 3) | (i & 7)]; }
  function clamp01(x) { return x < 0 ? 0 : x > 1 ? 1 : x; }
  function smooth(a, c, x) { x = clamp01((x - a) / (c - a)); return x * x * (3 - 2 * x); }
  function fract(x) { return x - Math.floor(x); }
  function hash(a, c) {
    var h = Math.imul(a | 0, 374761393) + Math.imul(c | 0, 668265263);
    h = Math.imul(h ^ (h >>> 13), 1274126177);
    h ^= h >>> 16;
    return (h >>> 0) / 4294967296;
  }
  function reduced() { return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches); }
  function dprNow() { return Math.min(DPR_CAP, window.devicePixelRatio || 1); }

  // ---------------------------------------------------------------- colours
  var probe = null, COL = { dot: [237, 237, 237, 1], ember: [255, 106, 43, 1], dark: true };
  function rgba(str, fallback) {
    if (!probe) { var pc = document.createElement("canvas"); pc.width = pc.height = 1; probe = pc.getContext("2d", { willReadFrequently: true }); }
    probe.clearRect(0, 0, 1, 1);
    probe.fillStyle = fallback; probe.fillStyle = str || fallback;
    probe.fillRect(0, 0, 1, 1);
    var d = probe.getImageData(0, 0, 1, 1).data;
    return [d[0], d[1], d[2], d[3] / 255];
  }
  function readColors() {
    var cs = getComputedStyle(document.documentElement);
    COL.dot = rgba(cs.getPropertyValue("--dot").trim(), "#ededed");
    COL.ember = rgba(cs.getPropertyValue("--ember").trim(), "#ff6a2b");
    COL.dark = document.documentElement.getAttribute("data-theme") !== "light";
  }

  // ---------------------------------------------------------------- tileable value-noise fBm (256 x 256, wraps)
  var NT = null;
  function noiseTile() {
    if (NT) return NT;
    NT = new Float32Array(65536);
    var oct = [[64, 0.55, 11], [32, 0.3, 23], [16, 0.15, 37]];
    for (var y = 0; y < 256; y++) for (var x = 0; x < 256; x++) {
      var v = 0;
      for (var o = 0; o < oct.length; o++) {
        var P = oct[o][0], n = 256 / P, s = oct[o][2];
        var gx = x / P, gy = y / P, x0 = Math.floor(gx), y0 = Math.floor(gy), fx = gx - x0, fy = gy - y0;
        fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy);
        var x1 = (x0 + 1) % n, y1 = (y0 + 1) % n;
        var a = hash(x0 + s * 97, y0 + s), c = hash(x1 + s * 97, y0 + s), d = hash(x0 + s * 97, y1 + s), e = hash(x1 + s * 97, y1 + s);
        v += oct[o][1] * (a + (c - a) * fx + (d - a) * fy + (a - c - d + e) * fx * fy);
      }
      NT[(y << 8) | x] = v;
    }
    return NT;
  }
  function nz(x, y) {
    var xi = Math.floor(x), yi = Math.floor(y), fx = x - xi, fy = y - yi;
    var x0 = xi & 255, y0 = yi & 255, x1 = (x0 + 1) & 255, y1 = (y0 + 1) & 255;
    var a = NT[(y0 << 8) | x0], c = NT[(y0 << 8) | x1], d = NT[(y1 << 8) | x0], e = NT[(y1 << 8) | x1];
    return a + (c - a) * fx + (d - a) * fy + (a - c - d + e) * fx * fy;
  }

  // ---------------------------------------------------------------- instances + the shared loop
  var all = [], timer = 0, last = 0;
  function ensureLoop() { if (!timer) { last = performance.now(); timer = setInterval(step, 1000 / FPS); } }
  function step() {
    var now = performance.now(), dt = Math.min(0.1, (now - last) / 1000), live = false;
    last = now;
    for (var k = 0; k < all.length; k++) {
      var x = all[k];
      if (!x.anim) continue;
      live = true;
      if (document.hidden || !x.vis) continue;
      x.t += dt * (x.o.speed || 1);
      if (x.o.until != null && x.t >= x.o.until) { x.t = x.o.until; x.anim = false; }
      x.draw();
    }
    if (!live) { clearInterval(timer); timer = 0; }
  }

  function Inst(canvas, kind, opts, paint) {
    var self = this;
    this.c = canvas; this.kind = kind; this.o = opts; this.paint = paint;
    this.ctx = canvas.getContext("2d");
    this.cell = document.createElement("canvas");
    this.cctx = this.cell.getContext("2d");
    this.W = this.H = this.dp = this.cols = this.rows = 0;
    this.t = opts.t != null ? opts.t : 0;
    this.vis = !("IntersectionObserver" in window);
    this.dirty = true;
    this.anim = !!opts.animate && !reduced();
    if (reduced() && opts.still != null) this.t = opts.still;
    if (!this.vis) {
      this.io = new IntersectionObserver(function (es) {
        self.vis = es[es.length - 1].isIntersecting;
        if (self.vis && self.dirty) self.draw();
      }, { rootMargin: "160px" });
      this.io.observe(canvas);
    }
    if ("ResizeObserver" in window) {
      this.ro = new ResizeObserver(function () { self.dirty = true; if (self.vis) self.draw(); });
      this.ro.observe(canvas);
    }
    all.push(this);
    if (this.anim) ensureLoop();
    this.draw();
  }
  Inst.prototype.layout = function () {
    var w = this.c.clientWidth, h = this.c.clientHeight;
    if (!w || !h) return false;
    var dpr = dprNow();
    var W = Math.round(w * dpr), H = Math.round(h * dpr);
    var pitch = this.o.pitchSm && w < 600 ? this.o.pitchSm : (this.o.pitch || 4);
    var dp = Math.max(2, Math.round(pitch * dpr));
    var ds = Math.max(1, Math.min(dp - 1, Math.round(dp * (this.o.dot || 0.55))));
    if (W !== this.W || H !== this.H || dp !== this.dp || ds !== this.ds) {
      this.W = W; this.H = H; this.dp = dp; this.ds = ds; this.dpr = dpr;
      this.c.width = W; this.c.height = H;
      this.cols = Math.max(1, Math.floor(W / dp)); this.rows = Math.max(1, Math.floor(H / dp));
      this.ox = Math.floor((W - this.cols * dp) / 2); this.oy = Math.floor((H - this.rows * dp) / 2);
      this.cell.width = this.cols; this.cell.height = this.rows;
      this.img = this.cctx.createImageData(this.cols, this.rows);
      var tile = document.createElement("canvas");
      tile.width = tile.height = dp;
      var tc = tile.getContext("2d"), off = (dp - ds) >> 1;
      tc.fillStyle = "#000"; tc.fillRect(off, off, ds, ds);
      this.pattern = this.ctx.createPattern(tile, "repeat");
      this.fresh = true;
    }
    return true;
  };
  Inst.prototype.draw = function () {
    if (this.dead || !this.layout()) return;
    this.dirty = false;
    var d = this.img.data;
    d.fill(0);
    this.paint(this, d, this.t);
    this.fresh = false;
    this.cctx.putImageData(this.img, 0, 0);
    var ctx = this.ctx, gw = this.cols * this.dp, gh = this.rows * this.dp;
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = "source-over";
    ctx.clearRect(0, 0, this.W, this.H);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.cell, this.ox, this.oy, gw, gh);
    ctx.globalCompositeOperation = "destination-in";
    ctx.translate(this.ox, this.oy);
    ctx.fillStyle = this.pattern;
    ctx.fillRect(0, 0, gw, gh);
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.globalCompositeOperation = "source-over";
  };
  Inst.prototype.destroy = function () {
    this.dead = true; this.anim = false;
    if (this.io) this.io.disconnect();
    if (this.ro) this.ro.disconnect();
    var i = all.indexOf(this);
    if (i >= 0) all.splice(i, 1);
    if (this.c.__dither === this) this.c.__dither = null;
  };
  function handle(inst) {
    return {
      canvas: inst.c,
      redraw: function () { inst.dirty = true; inst.draw(); },
      set: function (o) {
        for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) inst.o[k] = o[k];
        if ("animate" in o || "until" in o) { inst.anim = !!inst.o.animate && !reduced(); if (inst.anim) ensureLoop(); }
        if ("t" in o) inst.t = o.t;
        inst.W = 0; inst.dirty = true; inst.draw();
      },
      destroy: function () { inst.destroy(); }
    };
  }
  function mount(canvas, kind, opts, paint) {
    if (!canvas || !canvas.getContext) return null;
    if (canvas.__dither) canvas.__dither.destroy();
    if (!COL.read) { readColors(); COL.read = true; }
    var inst = new Inst(canvas, kind, opts || {}, paint);
    canvas.__dither = inst;
    return handle(inst);
  }
  function put(d, p, col, a) {
    d[p] = col[0]; d[p + 1] = col[1]; d[p + 2] = col[2];
    d[p + 3] = Math.round(255 * clamp01(a * col[3]));
  }

  // ---------------------------------------------------------------- field
  function paintField(I, d, t) {
    noiseTile();
    var o = I.o, cols = I.cols, rows = I.rows, px = I.dp / I.dpr;
    var mask = o.mask || "hero", dens = o.density == null ? 1 : o.density;
    var alpha = (o.alpha == null ? 0.7 : o.alpha) * (COL.dark ? 1 : 0.78);
    var useEmber = o.ember !== false, asp = cols / rows;
    var lo = o.lo == null ? 0.4 : o.lo, hi = o.hi == null ? 0.66 : o.hi;
    var rise = o.rise == null ? 1 : o.rise, seed = o.seed || 0;
    var sx = seed * 53.1, sy = seed * 31.7;
    // ember hot-spots: slow blobs along the bottom edge
    var blobs = [];
    var nb = o.blobs == null ? 3 : o.blobs;
    for (var k = 0; k < nb; k++) {
      blobs.push([0.16 + 0.34 * k + 0.05 * Math.sin(t * 0.21 + k * 2.1 + seed), 1.0 - 0.05 * Math.sin(t * 0.33 + k * 1.3), 0.13 + 0.03 * Math.sin(t * 0.27 + k)]);
    }
    for (var j = 0; j < rows; j++) {
      var w = (j + 0.5) / rows, Y = j * px;
      var mv = 1;
      if (mask === "hero") mv = 0.22 + 0.78 * smooth(0.08, 0.92, w);
      else if (mask === "panel") mv = 0.55 + 0.45 * smooth(0, 1, w);
      else if (mask === "top") mv = 0.3 + 0.7 * smooth(0.6, 0.0, w);
      for (var i = 0; i < cols; i++) {
        var u = (i + 0.5) / cols, X = i * px;
        var n1 = nz(X / 2.1 + t * 1.1 + sx, Y / 2.1 + t * 6.5 * rise + sy);
        var n2 = nz(X / 5.4 - t * 0.7 + 97 + sx, Y / 5.4 + t * 3.2 * rise + 31 + sy);
        var smoke = 0.58 * n2 + 0.42 * n1;
        var v = smooth(lo, hi, smoke);
        if (v <= 0) continue;
        var m = mv;
        if (mask === "hero") {
          var cx = (u - 0.5) / 0.3, cy = (w - 0.44) / 0.27;
          m *= 1 - 0.72 * Math.exp(-(cx * cx + cy * cy));
          m *= smooth(0, 0.05, u) * smooth(1, 0.95, u);
        }
        v *= m * dens;
        if (v <= bayer(i, j)) continue;
        var p = (j * cols + i) * 4, hot = 0;
        if (useEmber) {
          for (var q = 0; q < blobs.length; q++) {
            var dx = (u - blobs[q][0]) * asp, dy = w - blobs[q][1], r = blobs[q][2];
            hot += Math.exp(-(dx * dx + dy * dy) / (r * r));
          }
          hot *= smoke;
        }
        if (hot > 0.34 && hash(i, j + seed) < smooth(0.34, 0.75, hot)) put(d, p, COL.ember, (0.55 + 0.45 * v) * (COL.dark ? 1 : 0.9));
        else put(d, p, COL.dot, alpha * (0.3 + 0.7 * v));
      }
    }
    // sparks: single ember dots drifting up out of the hot-spots
    var ns = useEmber ? (o.sparks == null ? 28 : o.sparks) : 0;
    for (var s = 0; s < ns; s++) {
      var h1 = hash(s, 7 + seed), h2 = hash(s, 13 + seed), h3 = hash(s, 29 + seed);
      var life = 5 + 6 * h2, ph = fract(t / life + h3);
      var bx = blobs.length ? blobs[s % blobs.length][0] : h1;
      var su = bx + (h1 - 0.5) * 0.3 + 0.015 * Math.sin(t * (0.8 + h2) + s);
      var sw = 1.0 - ph * (0.35 + 0.45 * h2);
      var ci = Math.round(su * cols), cj = Math.round(sw * rows);
      if (ci < 0 || ci >= cols || cj < 0 || cj >= rows) continue;
      put(d, (cj * cols + ci) * 4, COL.ember, (1 - ph) * (1 - ph) * 0.95);
    }
  }

  // ---------------------------------------------------------------- the pen: draws icons in design units into a raster
  // Channels: R = shade (dot density), G = ember flag, B = hard edge (a line that must stay solid). Alpha = coverage.
  var C30 = 0.8660254, S30 = 0.5;
  function Pen(ctx, k, ox, oy) {
    this.x = ctx; this.k = k; this.ox = ox; this.oy = oy;
    this.minX = Infinity; this.minY = Infinity; this.maxX = -Infinity; this.maxY = -Infinity;
    this.sparks = [];
    if (ctx) ctx.setTransform(k, 0, 0, k, ox, oy);
  }
  function colr(shade, ember, edge, a) {
    return "rgba(" + Math.round(clamp01(shade) * 255) + "," + (ember ? 255 : 0) + "," + (edge ? 255 : 0) + "," + (a == null ? 1 : a) + ")";
  }
  Pen.prototype.iso = function (x, y, z) { return [(x - y) * C30, (x + y) * S30 - (z || 0)]; };
  Pen.prototype.m = function (pts) {
    for (var i = 0; i < pts.length; i++) {
      var p = pts[i];
      if (p[0] < this.minX) this.minX = p[0]; if (p[0] > this.maxX) this.maxX = p[0];
      if (p[1] < this.minY) this.minY = p[1]; if (p[1] > this.maxY) this.maxY = p[1];
    }
  };
  Pen.prototype.path = function (pts, closed) {
    var c = this.x;
    c.beginPath(); c.moveTo(pts[0][0], pts[0][1]);
    for (var i = 1; i < pts.length; i++) c.lineTo(pts[i][0], pts[i][1]);
    if (closed) c.closePath();
  };
  Pen.prototype.poly = function (pts, shade, o) {
    o = o || {};
    this.m(pts);
    if (!this.x) return;
    this.path(pts, true);
    this.x.fillStyle = colr(shade, o.ember, false, o.a);
    this.x.fill();
  };
  // a line in design units; w is in cells; edge (default) = solid; edge:false = dithered by its shade
  Pen.prototype.line = function (pts, o) {
    o = o || {};
    this.m(pts);
    if (!this.x) return;
    var c = this.x;
    this.path(pts, !!o.closed);
    c.lineWidth = (o.w || 1) / this.k;
    c.lineJoin = "round"; c.lineCap = o.cap || "round";
    c.setLineDash(o.dash ? o.dash.map(function (v) { return v / this.k; }, this) : []);
    c.strokeStyle = colr(o.shade == null ? 1 : o.shade, o.ember, o.edge !== false);
    c.stroke();
    c.setLineDash([]);
  };
  Pen.prototype.ellipse = function (cx, cy, rx, ry, o) {
    o = o || {};
    this.m([[cx - rx, cy - ry], [cx + rx, cy + ry]]);
    if (!this.x) return;
    var c = this.x;
    c.beginPath(); c.ellipse(cx, cy, Math.max(0.01, rx), Math.max(0.01, ry), o.rot || 0, o.a0 || 0, o.a1 == null ? Math.PI * 2 : o.a1);
    if (o.fill != null) { c.fillStyle = colr(o.fill, o.ember, false); c.fill(); }
    if (o.stroke !== false && o.fill == null || o.stroke) {
      c.lineWidth = (o.w || 1) / this.k;
      c.setLineDash(o.dash ? o.dash.map(function (v) { return v / this.k; }, this) : []);
      c.strokeStyle = colr(o.shade == null ? 1 : o.shade, o.ember, o.edge !== false);
      c.stroke(); c.setLineDash([]);
    }
  };
  // union of shapes (Path2D builders in design units): outlined together, filled with one shade
  Pen.prototype.shape = function (builders, shade, o) {
    o = o || {};
    var self = this;
    builders.forEach(function (bd) { self.m(bd.bounds); });
    if (!this.x) return;
    var c = this.x;
    c.lineWidth = (o.w || 2) / this.k; c.lineJoin = "round";
    c.strokeStyle = colr(o.edgeShade == null ? 1 : o.edgeShade, o.ember, true);
    builders.forEach(function (bd) { c.stroke(bd.path); });
    c.fillStyle = colr(shade, o.ember, false);
    builders.forEach(function (bd) { c.fill(bd.path); });
  };
  Pen.prototype.box = function (x, y, z, w, d, h, o) {
    o = o || {};
    var P = this.iso, T = [P(x, y, z + h), P(x + w, y, z + h), P(x + w, y + d, z + h), P(x, y + d, z + h)];
    var L = [P(x, y + d, z), P(x + w, y + d, z), P(x + w, y + d, z + h), P(x, y + d, z + h)];
    var R = [P(x + w, y, z), P(x + w, y + d, z), P(x + w, y + d, z + h), P(x + w, y, z + h)];
    var em = o.ember;
    if (o.faces !== false) {
      this.poly(T, o.top == null ? 0.97 : o.top, { ember: em });
      this.poly(L, o.left == null ? 0.5 : o.left, { ember: em });
      this.poly(R, o.right == null ? 0.22 : o.right, { ember: em });
    } else this.m(T.concat(L, R));
    if (o.edge === false) return;
    var es = { shade: o.edge == null ? 1 : o.edge, w: o.w || 1, dash: o.dash, ember: o.edgeEmber };
    var near = P(x + w, y + d, z + h);
    this.line([P(x, y, z + h), P(x + w, y, z + h), P(x + w, y, z), P(x + w, y + d, z), P(x, y + d, z), P(x, y + d, z + h)], Object.assign({ closed: true }, es));
    this.line([near, P(x, y + d, z + h)], es);
    this.line([near, P(x + w, y, z + h)], es);
    this.line([near, P(x + w, y + d, z)], es);
    if (o.hidden) {   // wireframe: the three hidden edges too
      var far = P(x, y, z);
      this.line([far, P(x + w, y, z)], es); this.line([far, P(x, y + d, z)], es); this.line([far, P(x, y, z + h)], es);
    }
  };
  // a single dot at a design point (not measured; drawn on top after decoding)
  Pen.prototype.spark = function (pt, a, ember) { this.sparks.push([pt[0], pt[1], a, ember]); };
  Pen.prototype.text = function (str, x, y, size, o) {
    o = o || {};
    this.m([[x - size * str.length * 0.32, y - size * 0.5], [x + size * str.length * 0.32, y + size * 0.5]]);
    if (!this.x) return;
    var c = this.x;
    c.font = (o.weight || 600) + " " + size + "px " + (o.family || "Geist, ui-sans-serif, system-ui, sans-serif");
    c.textAlign = "center"; c.textBaseline = "middle";
    c.fillStyle = colr(o.shade == null ? 1 : o.shade, o.ember, o.edge !== false);
    c.fillText(str, x, y);
  };
  function rect(x0, y0, x1, y1) { return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]; }
  function p2d(fn, bounds) { var p = new Path2D(); fn(p); return { path: p, bounds: bounds }; }

  // ---------------------------------------------------------------- the icons (design units; auto-fitted to the canvas)
  function cube(pen, o) {
    o = o || {};
    var s = o.s || 44, z = o.z || 0, x = (o.x || 0) - s / 2, y = (o.y || 0) - s / 2;
    pen.box(x, y, z, s, s, o.h || s * 0.95, o);
    if (o.prompt !== false) {   // a ">_" on the front-left face
      var fy = y + s, P = pen.iso, zt = z + (o.h || s * 0.95);
      var u = s / 44;
      pen.line([P(x + 8 * u, fy, zt - 12 * u), P(x + 15 * u, fy, zt - 18 * u), P(x + 8 * u, fy, zt - 24 * u)], { w: 1, ember: o.promptEmber });
      pen.line([P(x + 20 * u, fy, zt - 25 * u), P(x + 31 * u, fy, zt - 25 * u)], { w: 1, ember: o.promptEmber });
    }
  }
  function plate(pen, s, o) {
    o = o || {};
    pen.box(-s / 2, -s / 2, 0, s, s, 4, { top: 0.3, left: 0.18, right: 0.1, edge: 0.6, ember: o.ember });
  }
  function rising(pen, t, n, x0, x1, y0, y1, zTop, height, seed) {
    for (var k = 0; k < n; k++) {
      var h1 = hash(k, seed), h2 = hash(k, seed + 5), h3 = hash(k, seed + 9);
      var life = 1.8 + 2.2 * h2, ph = fract(t / life + h3);
      var px = x0 + (x1 - x0) * h1, py = y0 + (y1 - y0) * hash(k, seed + 3);
      var z = zTop + ph * height * (0.6 + 0.6 * h2);
      var sway = Math.sin(t * 2 + k) * 3 * ph;
      pen.spark(pen.iso(px + sway, py - sway, z), (1 - ph) * (1 - ph * 0.5), h2 > 0.18);
    }
  }

  var ICONS = {
    vm: { draw: function (pen) { plate(pen, 78); cube(pen, { z: 4 }); } },
    "vm-burning": {
      draw: function (pen, t) {
        plate(pen, 78);
        cube(pen, { z: 4, promptEmber: true });
        var P = pen.iso, zt = 4 + 44 * 0.95;
        pen.line([P(-12, -22, zt), P(-4, -8, zt), P(6, -12, zt), P(14, 4, zt)], { w: 1, ember: true });
        pen.line([P(-22, 6, zt), P(-10, 10, zt), P(-6, 22, zt)], { w: 1, ember: true });
        rising(pen, t, 26, -20, 20, -20, 20, zt + 2, 46, 41);
      }
    },
    ash: {   // the cube dissolving from the top into falling dots and a heap of ash
      draw: function (pen, t, o) {
        var p = ashP(t, o);
        pen.ellipse(0, 40, 50 + 8 * p, 6 + 5 * p, { fill: 0.3 + 0.35 * p });
        pen.ellipse(0, 38, 18 + 22 * p, 2 + 4 * p, { fill: 0.7 + 0.3 * p, ember: p > 0.2 && p < 0.9 });
        cube(pen, { s: 46, prompt: true });
        pen.m([[-62, -72], [62, 50]]);
      },
      post: function (I, cls, al, t, o) {
        var p = ashP(t, o), cols = I.cols, rows = I.rows, b = I.bounds;
        if (!b || p <= 0) return;
        var top = b.top, bot = b.cubeBot, span = Math.max(1, bot - top);
        var out = I.scratch || (I.scratch = { cls: new Uint8Array(cols * rows), al: new Float32Array(cols * rows) });
        if (out.cls.length !== cols * rows) { out.cls = new Uint8Array(cols * rows); out.al = new Float32Array(cols * rows); }
        out.cls.set(cls); out.al.set(al);
        for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
          var q = j * cols + i;
          if (!cls[q] || j > bot) continue;
          var h = hash(i * 3 + 1, j * 7 + 2), h2 = hash(i + 11, j + 5);
          var th = clamp01((j - top) / span) * 0.82 + h * 0.18;
          if (th >= p) continue;
          out.cls[q] = 0; out.al[q] = 0;
          var age = (p - th) * 3.2;
          if (age > 1.3 || h2 < 0.2) continue;   // some of it is simply gone
          var nj = Math.round(j + age * age * span * 0.9), ni = Math.round(i + (h2 - 0.5) * age * 8);
          if (nj >= rows || ni < 0 || ni >= cols || nj > bot + span * 0.22) continue;
          var nq = nj * cols + ni;
          out.cls[nq] = h2 > 0.82 ? 2 : 1;
          out.al[nq] = Math.max(out.al[nq], (1 - age / 1.3) * 0.95);
        }
        cls.set(out.cls); al.set(out.al);
      }
    },
    key: {
      draw: function (pen) {
        pen.shape([
          p2d(function (p) { p.arc(-38, 0, 17, 0, Math.PI * 2); }, [[-55, -17], [-21, 17]]),
          p2d(function (p) { p.rect(-24, -4.5, 58, 9); }, [[-24, -5], [34, 5]]),
          p2d(function (p) { p.rect(18, 2, 5.5, 11); p.rect(27, 2, 5.5, 8); }, [[18, 2], [33, 13]])
        ], 0.66, { w: 2 });
        if (pen.x) {   // the ring's hole
          var c = pen.x;
          c.save(); c.globalCompositeOperation = "destination-out"; c.beginPath(); c.arc(-38, 0, 7, 0, Math.PI * 2); c.fill(); c.restore();
        }
        pen.ellipse(-38, 0, 7, 7, { w: 1 });
        pen.line([[-31, -1.2], [-20, -1.2]], { w: 1, shade: 0.3, edge: false });
        // 15 planted secrets, 4 taken
        var taken = { 0: 1, 3: 1, 7: 1, 11: 1 };
        for (var n = 0; n < 15; n++) {
          var cx = 50 + (n % 5) * 12, cy = -17 + Math.floor(n / 5) * 12;
          if (taken[n]) { pen.poly(rect(cx, cy, cx + 8, cy + 8), 1, { ember: true }); pen.line(rect(cx, cy, cx + 8, cy + 8), { closed: true, w: 1, ember: true }); }
          else { pen.poly(rect(cx, cy, cx + 8, cy + 8), 0.2); pen.line(rect(cx, cy, cx + 8, cy + 8), { closed: true, w: 1, shade: 0.55 }); }
        }
      }
    },
    globe: {
      draw: function (pen, t) {
        var P = pen.iso;
        pen.box(-33.5 - 9, 33.5 - 9, -2, 18, 18, 17, { });
        var gx = 34, r = 31;
        // the connection: dotted, ember (what it tried to send), stopped at the fake internet's edge
        pen.line([[-44, -6], [gx - r - 6, -6]], { w: 1, ember: true, dash: [1, 2.2], cap: "butt" });
        pen.poly([[gx - r - 7, -9.5], [gx - r - 1.5, -6], [gx - r - 7, -2.5]], 1, { ember: true });
        pen.ellipse(gx, -6, r, r, { fill: 0.1, stroke: true, w: 1 });
        var spin = t * 0.5;
        for (var k = 0; k < 3; k++) {
          var a = spin + k * Math.PI / 3, rx = Math.abs(Math.cos(a)) * r;
          pen.ellipse(gx, -6, Math.max(0.6, rx), r, { w: 1, shade: 0.75, edge: rx > 3 });
        }
        pen.line([[gx - r, -6], [gx + r, -6]], { w: 1, shade: 0.8 });
        [-0.5, 0.5].forEach(function (f) {
          var yy = -6 + f * r * 1.1, hw = Math.sqrt(Math.max(0, r * r - (f * r * 1.1) * (f * r * 1.1)));
          pen.line([[gx - hw, yy], [gx + hw, yy]], { w: 1, shade: 0.7 });
        });
        void P;
      }
    },
    nested: {   // the gVisor sandbox inside the VM
      draw: function (pen) {
        var s = 74, hgt = 62;
        pen.box(-s / 2, -s / 2, 0, s, s, hgt, { top: 0.09, left: 0.06, right: 0.04, edge: 0.7, dash: [1, 1.6], hidden: true });
        cube(pen, { s: 30, h: 28, prompt: false });
        var P = pen.iso, x = s / 2, y = s / 2;
        var es = { w: 1, shade: 0.9, dash: [1, 1.6] };
        pen.line([P(x, y, hgt), P(-x, y, hgt)], es); pen.line([P(x, y, hgt), P(x, -y, hgt)], es);
        pen.line([P(x, y, hgt), P(x, y, 0)], es); pen.line([P(-x, y, 0), P(x, y, 0), P(x, -y, 0)], es);
      }
    },
    laptop: {
      draw: function (pen) {
        pen.poly(rect(-62, -48, 62, 26), 0.06);
        pen.line(rect(-62, -48, 62, 26), { closed: true, w: 1 });
        pen.line(rect(-55, -41, 55, 19), { closed: true, w: 1, shade: 0.45, edge: false });
        var L = [26, 64, 48, 80, 36, 58, 70, 22], X = -48;
        for (var n = 0; n < L.length; n++) {
          var y = -35 + n * 6.6, em = n === 4;
          pen.poly(rect(X + (n === 2 || n === 3 || n === 5 ? 8 : 0), y, X + L[n], y + 3), em ? 1 : 0.66, { ember: em });
        }
        pen.poly(rect(X, -35 + 8 * 6.6, X + 4, -35 + 8 * 6.6 + 4), 1);
        pen.shape([p2d(function (p) { p.moveTo(-74, 30); p.lineTo(74, 30); p.lineTo(66, 39); p.lineTo(-66, 39); p.closePath(); }, [[-74, 30], [74, 39]])], 0.72, { w: 1.6 });
        pen.line([[-12, 33], [12, 33]], { w: 1, shade: 0.4, edge: false });
      }
    },
    stamp: {
      draw: function (pen) {
        pen.shape([
          p2d(function (p) { p.arc(0, -44, 11, 0, Math.PI * 2); }, [[-11, -55], [11, -33]]),
          p2d(function (p) { p.rect(-6, -36, 12, 20); }, [[-6, -36], [6, -16]]),
          p2d(function (p) { p.rect(-30, -17, 60, 17); }, [[-30, -17], [30, 0]]),
          p2d(function (p) { p.rect(-35, 0, 70, 6); }, [[-35, 0], [35, 6]])
        ], 0.62, { w: 1.6 });
        pen.poly(rect(-29, -16, 29, -12), 0.95);
        // the imprint it leaves
        pen.poly(rect(-62, 16, 62, 48), 0.1, { ember: true });
        pen.line(rect(-62, 16, 62, 48), { closed: true, w: 1.4, ember: true });
        for (var g = 0; g < 7; g++) pen.poly(rect(-49 + g * 14.5, 25, -49 + g * 14.5 + 10, 39), 0.92, { ember: true });   // the stamped word
      }
    },
    shield: {
      draw: function (pen) {
        pen.shape([p2d(function (p) {
          p.moveTo(0, -46); p.lineTo(38, -33); p.bezierCurveTo(38, 4, 26, 30, 0, 46); p.bezierCurveTo(-26, 30, -38, 4, -38, -33); p.closePath();
        }, [[-38, -46], [38, 46]])], 0.42, { w: 1.6 });
        pen.shape([p2d(function (p) {
          p.moveTo(0, -46); p.lineTo(0, 46); p.bezierCurveTo(26, 30, 38, 4, 38, -33); p.closePath();
        }, [[0, -46], [38, 46]])], 0.66, { w: 0.01 });
        pen.line([[-15, 1], [-4, 12], [17, -12]], { w: 2.2 });
      }
    },
    clock: {
      draw: function (pen, t) {
        var r = 36;
        pen.poly(rect(-7, -52, 7, -45), 0.9);
        pen.line(rect(-7, -52, 7, -45), { closed: true, w: 1 });
        pen.poly(rect(-2.5, -45, 2.5, -38), 0.7);
        pen.ellipse(0, 0, r, r, { fill: 0.06, stroke: false });
        for (var k = 0; k < 60; k++) {
          var a = k / 60 * Math.PI * 2, big = k % 5 === 0;
          var r0 = big ? r - 6 : r - 0.5, r1 = r;
          if (big) pen.line([[Math.sin(a) * r0, -Math.cos(a) * r0], [Math.sin(a) * r1, -Math.cos(a) * r1]], { w: 1 });
          else pen.spark([Math.sin(a) * r, -Math.cos(a) * r], 0.85, false);
        }
        pen.m([[-r, -r], [r, r]]);
        var ang = 2.2 + t * 0.9;   // ~91 s: the sweep hand
        pen.line([[0, 0], [Math.sin(ang) * (r - 9), -Math.cos(ang) * (r - 9)]], { w: 1.3, ember: true });
        pen.line([[0, 0], [Math.sin(0.6) * 16, -Math.cos(0.6) * 16]], { w: 1.6 });
        pen.ellipse(0, 0, 2.6, 2.6, { fill: 1 });
      }
    },
    bars: {
      draw: function (pen) {
        var L = [70, 104, 52, 86], E = 1;
        for (var n = 0; n < 4; n++) {
          var y = -32 + n * 18;
          pen.poly(rect(-66, y, -58, y + 8), n === E ? 1 : 0.9, { ember: n === E });
          pen.poly(rect(-52, y, -52 + L[n] * 0.86, y + 8), n === E ? 1 : 0.62, { ember: n === E });
          for (var x = -52 + L[n] * 0.86 + 5; x < 66; x += 4) pen.spark([x, y + 4], 0.5, false);
        }
        pen.line([[-66, 42], [66, 42]], { w: 1, shade: 0.5, dash: [1, 1.5], cap: "butt" });
        pen.m([[-66, -34], [66, 44]]);
      }
    }
  };
  function ashP(t, o) {
    if (o.progress != null) return o.progress;
    if (o.until != null) return clamp01(t / Math.max(0.01, o.until)) * (o.end == null ? 0.92 : o.end);
    var cyc = fract(t / 6.5);
    return cyc < 0.75 ? cyc / 0.75 : 1;
  }

  // raster + decode: shared by icons and text
  function ensureRaster(I) {
    if (!I.rc) { I.rc = document.createElement("canvas"); I.rctx = I.rc.getContext("2d", { willReadFrequently: true }); }
    if (I.rc.width !== I.cols || I.rc.height !== I.rows) { I.rc.width = I.cols; I.rc.height = I.rows; }
    var n = I.cols * I.rows;
    if (!I.cls || I.cls.length !== n) { I.cls = new Uint8Array(n); I.al = new Float32Array(n); }
    var c = I.rctx;
    c.setTransform(1, 0, 0, 1, 0, 0);
    c.globalCompositeOperation = "source-over";
    c.clearRect(0, 0, I.cols, I.rows);
    return c;
  }
  function decode(I, o) {
    var cols = I.cols, rows = I.rows, src = I.rctx.getImageData(0, 0, cols, rows).data, cls = I.cls, al = I.al;
    var useEmber = o.ember !== false, gamma = o.gain || 1;
    for (var j = 0; j < rows; j++) for (var i = 0; i < cols; i++) {
      var q = j * cols + i, p = q * 4, a = src[p + 3] / 255;
      cls[q] = 0; al[q] = 0;
      if (a < 0.05) continue;
      var sh = clamp01(src[p] / 255 * a * gamma), em = src[p + 1] > 110 && useEmber, ed = src[p + 2] / 255 * a > 0.42;
      if (ed) { cls[q] = em ? 2 : 1; al[q] = Math.max(0.5, src[p] / 255); continue; }
      if (sh <= bayer(i, j) * 0.985 + 0.008) continue;
      cls[q] = em ? 2 : 1;
      al[q] = 0.4 + 0.6 * sh;
    }
  }
  function emit(I, d, o, pen) {
    var cols = I.cols, rows = I.rows, cls = I.cls, al = I.al;
    var alpha = (o.alpha == null ? 1 : o.alpha) * (COL.dark ? 0.92 : 0.9);
    if (pen) pen.sparks.forEach(function (s) {
      var ci = Math.round(pen.ox + s[0] * pen.k - 0.5), cj = Math.round(pen.oy + s[1] * pen.k - 0.5);
      if (ci < 0 || cj < 0 || ci >= cols || cj >= rows) return;
      var q = cj * cols + ci;
      if (s[3] && o.ember !== false) { cls[q] = 2; al[q] = Math.max(al[q], s[2]); }
      else if (!cls[q]) { cls[q] = 1; al[q] = s[2]; }
    });
    for (var q = 0; q < cols * rows; q++) {
      if (!cls[q]) continue;
      put(d, q * 4, cls[q] === 2 ? COL.ember : COL.dot, cls[q] === 2 ? (COL.dark ? al[q] : Math.sqrt(al[q])) : al[q] * alpha);
    }
  }

  function paintIcon(I, d, t) {
    var def = ICONS[I.name] || ICONS.vm, o = I.o;
    if (I.fresh || !I.fit) {   // measure once per size (at t = 0 so animation never changes the scale)
      var mp = new Pen(null, 1, 0, 0);
      def.draw(mp, 0, o);
      var bw = Math.max(1, mp.maxX - mp.minX), bh = Math.max(1, mp.maxY - mp.minY), fill = o.fill || 0.84;
      var k = Math.min(I.cols * fill / bw, I.rows * fill / bh);
      if (o.maxScale) k = Math.min(k, o.maxScale * I.dpr / I.dp);
      var ax = o.align === "left" ? 0 : o.align === "right" ? 1 : 0.5;
      I.fit = { k: k, ox: (I.cols - bw * k) * ax - mp.minX * k, oy: (I.rows - bh * k) / 2 - mp.minY * k, mp: mp };
    }
    var c = ensureRaster(I), f = I.fit;
    var pen = new Pen(c, f.k, f.ox, f.oy);
    def.draw(pen, t, o);
    decode(I, o);
    if (def.post) {
      var cb = pen.iso(0, 0, 0);
      I.bounds = { top: Math.round(f.oy + f.mp.minY * f.k), cubeBot: Math.round(f.oy + (cb[1] + 23) * f.k) };
      def.post(I, I.cls, I.al, t, o);
    }
    emit(I, d, o, pen);
  }

  // ---------------------------------------------------------------- text
  function textLines(I) {
    var o = I.o, cssW = I.c.clientWidth;
    var s = o.narrow && cssW < (o.narrowBelow || 760) ? o.narrow : I.str;
    return String(s).split("\n");
  }
  function fontStr(o, px) { return (o.weight || 600) + " " + px + "px " + (o.family || '"Geist", ui-sans-serif, system-ui, sans-serif'); }
  function sizeText(I) {   // sets the canvas's CSS height from its width so the text fills it
    var o = I.o, cssW = I.c.clientWidth;
    if (!cssW) return;
    var lines = textLines(I), c = document.createElement("canvas").getContext("2d");
    c.font = fontStr(o, 100);
    var mw = 1;
    lines.forEach(function (l) { mw = Math.max(mw, c.measureText(l).width + (o.tracking || 0) * 100 * l.length); });
    var px = cssW * (o.fillW || 1) / (mw / 100);
    if (o.maxSize) px = Math.min(px, o.maxSize);
    I.tx = { px: px, lines: lines, lh: px * (o.leading || 1.0) };
    var h = Math.ceil(I.tx.lh * lines.length + px * (o.padTop == null ? 0.32 : o.padTop) + px * 0.2);
    if (Math.abs((parseFloat(I.c.style.height) || 0) - h) > 1) I.c.style.height = h + "px";
  }
  function paintText(I, d, t) {
    var o = I.o;
    if (!I.tx || I.fresh) sizeText(I);
    if (!I.tx) return;
    var c = ensureRaster(I), sc = I.dpr / I.dp;   // CSS px -> cells
    var px = I.tx.px * sc, lh = I.tx.lh * sc, top = I.tx.px * (o.padTop == null ? 0.32 : o.padTop) * sc;
    c.font = fontStr(o, px);
    c.textBaseline = "alphabetic"; c.textAlign = "left";
    if ("letterSpacing" in c) c.letterSpacing = ((o.tracking || 0) * px) + "px";
    var from = o.emberFrom == null ? -1 : o.emberFrom, idx = 0, pen = new Pen(null, 1, 0, 0);
    var hot = [];
    I.tx.lines.forEach(function (line, n) {
      var base = top + lh * n + px * 0.8, y0 = base - px * 0.74;
      var g = c.createLinearGradient(0, y0, 0, base);
      var g2 = c.createLinearGradient(0, y0, 0, base);
      g.addColorStop(0, colr(0.6, false, false)); g.addColorStop(1, colr(1, false, false));
      g2.addColorStop(0, colr(0.62, true, false)); g2.addColorStop(1, colr(1, true, false));
      var cut = from < 0 ? line.length : Math.max(0, Math.min(line.length, from - idx));
      var head = line.slice(0, cut), tail = line.slice(cut);
      c.fillStyle = g; c.fillText(head, 0, base);
      if (tail) {
        var x = c.measureText(head).width;
        c.fillStyle = g2; c.fillText(tail, x, base);
        hot.push([x, c.measureText(tail).width, y0]);
      }
      idx += line.length + 1;
    });
    decode(I, o);
    // embers lifting off the hot words
    if (o.sparks !== 0 && hot.length) {
      var ns = o.sparks || 22;
      for (var s = 0; s < ns; s++) {
        var hz = hot[s % hot.length], h1 = hash(s, 3), h2 = hash(s, 8), h3 = hash(s, 17);
        var life = 2.4 + 2.6 * h2, ph = fract(t / life + h3);
        var sx = hz[0] + hz[1] * h1 + Math.sin(t * 1.7 + s) * 2 * ph, sy = hz[2] + px * 0.2 - ph * (top + px * 0.25);
        pen.spark([sx, sy], (1 - ph) * 0.95, true);
      }
    }
    emit(I, d, o, pen);
  }

  // ---------------------------------------------------------------- public API
  function onFonts(fn) { if (document.fonts && document.fonts.ready) document.fonts.ready.then(fn, function () {}); }
  var API = {
    names: Object.keys(ICONS),
    field: function (canvas, opts) {
      opts = Object.assign({ pitch: 4, dot: 0.5, animate: true }, opts || {});
      if (opts.still == null) opts.still = 4;
      return mount(canvas, "field", opts, paintField);
    },
    icon: function (canvas, name, opts) {
      opts = Object.assign({ pitch: 3, dot: 0.62 }, opts || {});
      if (opts.still == null) opts.still = name === "ash" ? (opts.until != null ? opts.until : 3) : 1.2;
      var h = mount(canvas, "icon", opts, function (I, d, t) { I.name = name; paintIcon(I, d, t); });
      return h;
    },
    text: function (canvas, str, opts) {
      opts = Object.assign({ pitch: 3, dot: 0.62 }, opts || {});
      if (opts.still == null) opts.still = 1.5;
      var h = mount(canvas, "text", opts, function (I, d, t) { I.str = str; paintText(I, d, t); });
      if (h) {
        if (document.fonts && document.fonts.load) document.fonts.load(fontStr(opts, 100)).then(function () { h.set({}); }, function () {});
        onFonts(function () { h.set({}); });
      }
      return h;
    },
    auto: function (root) {
      var list = (root || document).querySelectorAll("canvas[data-dither]"), out = [];
      Array.prototype.forEach.call(list, function (cv) {
        if (cv.__dither) return;
        var ds = cv.dataset, o = {};
        ["pitch", "pitchSm", "dot", "alpha", "density", "lo", "hi", "fill", "seed", "sparks", "blobs", "speed", "emberFrom", "maxSize", "rise", "t"].forEach(function (k) {
          if (ds[k] != null && ds[k] !== "") o[k] = parseFloat(ds[k]);
        });
        if (ds.animate) o.animate = ds.animate !== "false";
        if (ds.mask) o.mask = ds.mask;
        if (ds.align) o.align = ds.align;
        if (ds.ember === "false") o.ember = false;
        if (ds.narrow) o.narrow = ds.narrow.replace(/\\n/g, "\n");
        if (ds.family) o.family = ds.family;
        if (ds.weight) o.weight = ds.weight;
        var kind = ds.dither, h;
        if (kind === "field") h = API.field(cv, o);
        else if (kind === "text") h = API.text(cv, ds.text || cv.getAttribute("aria-label") || "", o);
        else h = API.icon(cv, ds.icon || "vm", o);
        out.push(h);
      });
      return out;
    },
    refresh: function () {
      readColors();
      all.forEach(function (x) { x.dirty = true; x.draw(); });
    }
  };
  document.addEventListener("burner:theme", function () { API.refresh(); });
  document.addEventListener("visibilitychange", function () { if (!document.hidden) last = performance.now(); });
  window.BurnerDither = API;
})();
