// Burner charts: window.BurnerCharts.{timeline, flow, baitBoard, benchMatrix, scoreBars, scanTimes, donut}.
// Drawn with D3 v7 (vendored as window.d3, ISC) in SVG/HTML. A classic script, so it works from <script src> on any page.
// Each chart renders into a container it owns, redraws on resize (ResizeObserver) and on the document "burner:theme"
// event, takes its colours from CSS classes on the tokens in charts.css, has keyboard-focusable marks with tooltips,
// honours prefers-reduced-motion, and returns {update(data), destroy()}.
// Every label can be attacker-controlled (file names, hosts, process names from the scanned repo), so text only ever
// goes through textContent / d3 .text(); nothing here builds HTML from data.
(function () {
  "use strict";
  var d3 = window.d3;
  var SVGNS = "http://www.w3.org/2000/svg";

  // ---------------------------------------------------------------- shared helpers
  function reducedMotion() {
    return !!(window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }
  function str(v) { return v == null ? "" : String(v); }
  function num(v, dflt) { var n = Number(v); return isFinite(n) ? n : (dflt === undefined ? 0 : dflt); }
  function plural(n, one, many) { return n + " " + (n === 1 ? one : (many || one + "s")); }
  function fmtSecs(t, span) {
    var dp = span < 3 ? 2 : span < 20 ? 1 : 0;
    return num(t).toFixed(dp) + " s";
  }
  function fmtBytes(b) {
    b = num(b);
    if (b >= 1048576) return (b / 1048576).toFixed(1) + " MB";
    if (b >= 1024) return (b / 1024).toFixed(1) + " KB";
    return b + " B";
  }
  function pct(x) { return Math.round(x * 100) + "%"; }

  /** document.createElement with attrs; {text} sets textContent, {class} the class; children are nodes or strings. */
  function h(tag, attrs) {
    var n = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (k) {
      var v = attrs[k];
      if (v == null || v === false) return;
      if (k === "text") n.textContent = str(v);
      else if (k === "class") n.className = v;
      else n.setAttribute(k, v === true ? "" : v);
    });
    for (var i = 2; i < arguments.length; i++) {
      var c = arguments[i];
      if (c == null) continue;
      if (Array.isArray(c)) c.forEach(function (x) { if (x != null) n.append(x); });
      else n.append(c);
    }
    return n;
  }
  function svgEl(tag, attrs) {
    var n = document.createElementNS(SVGNS, tag);
    Object.keys(attrs || {}).forEach(function (k) { n.setAttribute(k, attrs[k]); });
    return n;
  }

  /** Shorten an SVG <text> (already in the DOM) with an ellipsis until it fits maxW px. */
  function fit(node, maxW) {
    if (!node || maxW <= 0) { if (node) node.textContent = ""; return; }
    var full = node.textContent;
    if (node.getComputedTextLength() <= maxW) return;
    var lo = 0, hi = full.length;
    while (lo < hi) {
      var mid = (lo + hi + 1) >> 1;
      node.textContent = full.slice(0, mid) + "\u2026";
      if (node.getComputedTextLength() <= maxW) lo = mid; else hi = mid - 1;
    }
    node.textContent = lo > 0 ? full.slice(0, lo) + "\u2026" : "";
  }
  function fitAll(sel, maxW) { sel.each(function (d, i) { fit(this, typeof maxW === "function" ? maxW(d, i) : maxW); }); }

  /** A tooltip box inside root. show(lines, anchor): lines = [text] or [[text, cls]]; anchor = MouseEvent or element. */
  function tooltip(root) {
    var box = h("div", { class: "bc-tip", role: "tooltip", hidden: true });
    root.append(box);
    function place(x, y, below) {
      var r = root.getBoundingClientRect();
      var w = box.offsetWidth, ht = box.offsetHeight;
      var left = x - r.left + 14;
      if (left + w > r.width - 4) left = x - r.left - w - 14;
      left = Math.max(4, Math.min(left, r.width - w - 4));
      var top = below ? y - r.top + 10 : y - r.top + 14;
      if (top + ht > r.height + 40 && y - r.top - ht - 10 > -40) top = y - r.top - ht - 10;
      box.style.left = left + "px";
      box.style.top = top + "px";
    }
    return {
      show: function (lines, anchor) {
        box.replaceChildren.apply(box, lines.filter(Boolean).map(function (l, i) {
          var text = Array.isArray(l) ? l[0] : l;
          var cls = Array.isArray(l) ? l[1] : (i ? "m" : "h");
          return h("span", { class: cls, text: text });
        }));
        box.hidden = false;
        if (anchor && anchor.clientX != null) place(anchor.clientX, anchor.clientY);
        else if (anchor && anchor.getBoundingClientRect) {
          var b = anchor.getBoundingClientRect();
          place(b.left + Math.min(b.width, 240) / 2, b.bottom, true);
        }
      },
      move: function (e) { if (!box.hidden) place(e.clientX, e.clientY); },
      hide: function () { box.hidden = true; },
    };
  }

  /** Legend chips that filter: items [{id, label, n, sw}] (sw = extra swatch classes); on(id) -> pressed. */
  function chips(items, isOn, onToggle, label) {
    var ul = h("ul", { class: "bc-legend", "aria-label": label || "Filter" });
    items.forEach(function (it) {
      var b = h("button", { type: "button", class: "bc-chip", "aria-pressed": String(!!isOn(it.id)) },
        it.sw === null ? null : h("span", { class: "bc-sw " + (it.sw || ""), "aria-hidden": "true" }),
        h("span", { text: it.label }),
        it.n != null ? h("span", { class: "n", text: String(it.n) }) : null);
      b.addEventListener("click", function () { onToggle(it.id); });
      ul.append(h("li", {}, b));
    });
    return ul;
  }

  /** Keyboard + pointer behaviour for a focusable mark selection. tip(d) -> lines; act(d) on click/Enter/Space. */
  function interactive(sel, tt, tip, act) {
    sel.attr("tabindex", 0).attr("role", act ? "button" : "img")
      .attr("aria-label", function (d) { return tip(d).filter(Boolean).map(function (l) { return Array.isArray(l) ? l[0] : l; }).join(". "); })
      .on("mouseenter", function (e, d) { d3.select(this).classed("is-hot", true); tt.show(tip(d), e); })
      .on("focus", function (e, d) { d3.select(this).classed("is-hot", true); tt.show(tip(d), this); })
      .on("mousemove", function (e) { tt.move(e); })
      .on("mouseleave blur", function () { d3.select(this).classed("is-hot", false); tt.hide(); });
    if (act) {
      sel.style("cursor", "pointer")
        .on("click", function (e, d) { act(d, this); })
        .on("keydown", function (e, d) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); act(d, this); }
        });
    }
  }

  /** The chart lifecycle shared by every chart: owns host, redraws on resize and theme, entrance once. */
  function mount(host, kind, data, opts, draw) {
    if (!host) throw new Error("BurnerCharts." + kind + ": no container element");
    var root = h("div", { class: "bc bc-" + kind });
    if (opts && opts.fixedWidth) root.style.width = opts.fixedWidth + "px";
    host.replaceChildren(root);
    var st = { root: root, data: data, opts: opts || {}, ui: {}, drawn: false, width: 0 };
    var lastW = -1, raf = 0, dead = false;
    st.redraw = function (animate) {
      if (dead) return;
      if (!d3) { root.replaceChildren(h("p", { class: "bc-empty", text: "Charts need d3 (static/vendor/d3.min.js)." })); return; }
      var w = Math.floor(root.clientWidth);
      if (w < 40) return;            // hidden (display:none tab): draw when it gets a size
      lastW = w;
      st.width = w;
      st.narrow = w < 560;
      var anim = (animate || !st.drawn) && !reducedMotion();
      root.classList.toggle("bc-anim", anim);
      draw(st);
      st.drawn = true;
      if (anim) setTimeout(function () { root.classList.remove("bc-anim"); }, 1400);
    };
    var ro = "ResizeObserver" in window ? new ResizeObserver(function () {
      if (Math.abs(Math.floor(root.clientWidth) - lastW) < 2) return;
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () { st.redraw(false); });
    }) : null;
    if (ro) ro.observe(root);
    function onTheme() { st.redraw(false); }
    document.addEventListener("burner:theme", onTheme);
    st.redraw(true);
    return {
      update: function (next) { st.data = next; st.redraw(false); },
      destroy: function () {
        dead = true;
        if (ro) ro.disconnect();
        cancelAnimationFrame(raf);
        document.removeEventListener("burner:theme", onTheme);
        root.remove();
      },
    };
  }

  function svgFor(parent, width, height, label) {
    return d3.select(parent).append("svg").attr("width", width).attr("height", height)
      .attr("viewBox", "0 0 " + width + " " + height).attr("role", "group").attr("aria-label", label);
  }

  /** A horizontal bar from x0 with a rounded data end. */
  function barPath(x0, x1, y, hgt, r) {
    r = r == null ? 4 : r;
    var w = x1 - x0;
    if (w < 0.5) return "";
    var rr = Math.min(r, w, hgt / 2);
    return "M" + x0 + "," + y + "H" + (x1 - rr) + "A" + rr + "," + rr + " 0 0 1 " + x1 + "," + (y + rr)
      + "V" + (y + hgt - rr) + "A" + rr + "," + rr + " 0 0 1 " + (x1 - rr) + "," + (y + hgt) + "H" + x0 + "Z";
  }

  var SEV_RANK = { critical: 4, high: 3, medium: 2, low: 1, info: 0 };
  var SEV_LABEL = { critical: "Critical", high: "High", medium: "Medium", low: "Low", info: "Info" };
  function sevOf(s) { s = str(s).toLowerCase(); return SEV_RANK[s] != null ? s : "info"; }

  /** Severity is double-encoded: shape + size (see charts.css). */
  function shapePath(sev, big) {
    var k = big ? 1.3 : 1;
    if (sev === "critical") { var r = 7.5 * k; return "M0," + (-r) + "L" + r + ",0L0," + r + "L" + (-r) + ",0Z"; }
    var rad = (sev === "high" ? 5.5 : sev === "medium" ? 4.4 : sev === "low" ? 4 : 3.2) * k;
    return d3.arc()({ innerRadius: 0, outerRadius: rad, startAngle: 0, endAngle: 2 * Math.PI });
  }
  function sevKeys() {
    return h("div", { class: "bc-foot", "aria-hidden": "true" },
      ["critical", "high", "medium", "low", "info"].map(function (s) {
        return h("span", { class: "bc-key" },
          h("span", { class: "bc-sw k-" + s + (s === "critical" ? " dia" : s === "low" ? " ring" : "") }),
          h("span", { text: SEV_LABEL[s] }));
      }));
  }

  // ---------------------------------------------------------------- 1. timeline
  var LANES = [
    { id: "secrets", name: "Secrets read", short: "Secrets" },
    { id: "files", name: "Files written", short: "Files" },
    { id: "processes", name: "Programs run", short: "Programs" },
    { id: "dns", name: "DNS lookups", short: "DNS" },
    { id: "network", name: "Connections", short: "Network" },
    { id: "exfil", name: "Secrets sent", short: "Sent" },
  ];

  function cleanTrace(trace) {
    trace = trace || {};
    var events = (Array.isArray(trace.events) ? trace.events : []).filter(function (e) { return e && isFinite(Number(e.t)); })
      .map(function (e, i) {
        return { t: Number(e.t), lane: str(e.lane) || "processes", label: str(e.label), detail: str(e.detail),
          severity: sevOf(e.severity), step: str(e.step), _i: i, raw: e };
      });
    var steps = (Array.isArray(trace.steps) ? trace.steps : []).filter(function (s) { return s && isFinite(Number(s.t0)); })
      .map(function (s) { return { name: str(s.name), t0: Number(s.t0), t1: num(s.t1, Number(s.t0)), rc: s.rc, sandbox_died: !!s.sandbox_died }; });
    var end = Math.max(num(trace.duration), d3.max(events, function (e) { return e.t; }) || 0,
      d3.max(steps, function (s) { return s.t1; }) || 0, 1);
    return { duration: end, steps: steps, events: events };
  }

  function drawTimeline(st) {
    var root = st.root, ui = st.ui, opts = st.opts;
    var tr = cleanTrace(st.data);
    var narrow = st.narrow;
    var lanes = LANES.slice();
    tr.events.forEach(function (e) {
      if (!lanes.some(function (l) { return l.id === e.lane; })) lanes.push({ id: e.lane, name: e.lane, short: e.lane });
    });
    if (!ui.hidden) ui.hidden = {};
    var counts = {};
    tr.events.forEach(function (e) { counts[e.lane] = (counts[e.lane] || 0) + 1; });
    var shown = lanes.filter(function (l) { return !ui.hidden[l.id]; });
    var full = [0, tr.duration];
    var dom = ui.domain || full;

    // header: lane chips + zoom reset
    var reset = h("button", { type: "button", class: "bc-btn", hidden: !ui.domain, text: "Reset zoom" });
    var firstEx = tr.events.filter(function (e) { return e.lane === "exfil"; }).sort(function (a, b) { return a.t - b.t; })[0];
    var theft = h("button", { type: "button", class: "bc-btn", hidden: !!ui.domain || !firstEx, text: "Zoom to the theft" });
    theft.addEventListener("click", function () {
      // the run-up to the first theft: what happened in the second before it, and just after
      var near = tr.events.filter(function (e) { return e.t >= firstEx.t - 1 && e.t <= firstEx.t + 0.25 && (e.severity !== "low" || e.lane === "exfil"); });
      var a = Math.min.apply(null, near.map(function (e) { return e.t; })), b = Math.max.apply(null, near.map(function (e) { return e.t; }));
      var pad = Math.max(0.05, (b - a) * 0.25);
      ui.domain = [Math.max(0, a - pad), Math.min(tr.duration, b + pad)];
      ui.zoomed = true;
      st.redraw(false);
    });
    reset.addEventListener("click", function () { ui.domain = null; ui.zoomed = true; st.redraw(false); });
    var legend = chips(lanes.map(function (l) {
      return { id: l.id, label: narrow ? l.short : l.name, n: counts[l.id] || 0,
        sw: l.id === "exfil" ? "dia k-critical" : null };
    }), function (id) { return !ui.hidden[id]; }, function (id) {
      var vis = lanes.filter(function (l) { return !ui.hidden[l.id]; });
      if (!ui.hidden[id] && vis.length === 1) return;     // keep one lane
      ui.hidden[id] = !ui.hidden[id];
      st.redraw(false);
    }, "Show or hide lanes");
    var hint = h("p", { class: "bc-hint", text: ui.domain ? "Zoomed to " + fmtSecs(dom[0], dom[1] - dom[0]) + " \u2013 "
      + fmtSecs(dom[1], dom[1] - dom[0]) : (narrow ? "Drag to zoom" : "Drag across the lanes to zoom in") });
    var plot = h("div", { class: "bc-plot" });
    root.replaceChildren(h("div", { class: "bc-head" }, legend, h("div", { class: "bc-legend" }, hint, theft, reset)), plot);
    if (ui.zoomed) { root.classList.add("bc-zoomed"); setTimeout(function () { root.classList.remove("bc-zoomed"); }, 260); ui.zoomed = false; }
    var tt = tooltip(root);

    var W = st.width;
    var M = { l: narrow ? 6 : 128, r: narrow ? 8 : 18, t: 50, b: 30 };
    var LH = narrow ? 46 : 40;
    var markY = narrow ? 30 : LH / 2;
    var lanesTop = M.t, lanesH = shown.length * LH, H = M.t + lanesH + M.b;
    var x = d3.scaleLinear().domain(dom).range([M.l, W - M.r]);
    var span = dom[1] - dom[0];
    var exfilCount = (counts.exfil || 0);
    var svg = svgFor(plot, W, H, "Timeline of what the take-home did in the sandbox, " + fmtSecs(tr.duration, tr.duration)
      + ": " + shown.map(function (l) { return plural(counts[l.id] || 0, l.name.toLowerCase().replace(/s$/, ""), l.name.toLowerCase()); }).join(", ")
      + (exfilCount ? ". Fake secrets left the sandbox." : "."));
    var clipId = "bc-clip-" + Math.random().toString(36).slice(2, 9);
    svg.append("clipPath").attr("id", clipId).append("rect")
      .attr("x", M.l - 10).attr("y", 0).attr("width", W - M.l - M.r + 20).attr("height", H);

    // step bands
    var bands = svg.append("g").attr("clip-path", "url(#" + clipId + ")");
    var stepSel = bands.selectAll("g.step").data(tr.steps).join("g").attr("class", "step");
    stepSel.append("rect").attr("class", function (d, i) { return "band" + (i % 2 ? " alt" : ""); })
      .attr("x", function (d) { return x(d.t0); }).attr("width", function (d) { return Math.max(0, x(d.t1) - x(d.t0)); })
      .attr("y", 0).attr("height", lanesTop + lanesH);
    stepSel.append("line").attr("class", "band-edge").attr("x1", function (d) { return x(d.t0); }).attr("x2", function (d) { return x(d.t0); })
      .attr("y1", 0).attr("y2", lanesTop + lanesH);
    stepSel.append("text").attr("class", "t-strong t-small step-name").attr("x", function (d) { return Math.max(x(d.t0), M.l) + 7; }).attr("y", 11)
      .text(function (d) { return d.name; });
    stepSel.append("text").attr("class", "t-muted t-small").attr("x", function (d) { return Math.max(x(d.t0), M.l) + 7; }).attr("y", 26)
      .text(function (d) {
        var rc = d.sandbox_died ? "sandbox died" : d.rc === 137 ? "stopped at time limit" : d.rc != null ? "exit " + d.rc : "";
        return fmtSecs(d.t1 - d.t0, 99) + (rc ? " \u00b7 " + rc : "");
      });
    stepSel.each(function (d) {
      var w = Math.min(x(d.t1), W - M.r) - Math.max(x(d.t0), M.l) - 12;
      d3.select(this).selectAll("text").each(function () { fit(this, w < 26 ? 0 : w); });
    });
    var stepHit = stepSel.append("rect").attr("class", "band-hit").attr("x", function (d) { return Math.max(x(d.t0), M.l); })
      .attr("width", function (d) { return Math.max(0, Math.min(x(d.t1), W - M.r) - Math.max(x(d.t0), M.l)); })
      .attr("y", 0).attr("height", 32);
    interactive(stepHit, tt, function (d) {
      return ["Step: " + d.name, fmtSecs(d.t0, 99) + " to " + fmtSecs(d.t1, 99) + " (" + fmtSecs(d.t1 - d.t0, 99) + ")",
        d.sandbox_died ? ["The sandbox died during this step", "bad"] : d.rc === 137 ? "Stopped when its time ran out (exit 137)" : d.rc != null ? "Exit code " + d.rc : null];
    });

    // lanes
    var laneG = svg.append("g");
    shown.forEach(function (l, i) {
      var y0 = lanesTop + i * LH;
      laneG.append("line").attr("class", "lane-line").attr("x1", narrow ? 0 : 8).attr("x2", W).attr("y1", y0 + LH).attr("y2", y0 + LH);
      var name = laneG.append("text").attr("class", "lane-name").attr("x", narrow ? 6 : 8).attr("y", narrow ? y0 + 11 : y0 + LH / 2 - 7).text(l.name);
      fit(name.node(), narrow ? W * 0.6 : M.l - 16);
      laneG.append("text").attr("class", "t-muted t-small t-num").attr("x", narrow ? W - M.r : 8).attr("text-anchor", narrow ? "end" : "start")
        .attr("y", narrow ? y0 + 11 : y0 + LH / 2 + 9).text(plural(counts[l.id] || 0, "event"));
      if (!counts[l.id]) {
        laneG.append("text").attr("class", "lane-none").attr("x", M.l + 10).attr("y", y0 + markY).text("nothing seen");
      }
    });
    svg.append("line").attr("class", "lane-line").attr("x1", narrow ? 0 : 8).attr("x2", W).attr("y1", lanesTop).attr("y2", lanesTop);

    // axis
    var axisY = lanesTop + lanesH;
    var ticks = x.ticks(narrow ? 4 : Math.max(4, Math.min(10, Math.floor((W - M.l) / 90))));
    var ax = svg.append("g").attr("class", "axis");
    var tk = ax.selectAll("g.tick").data(ticks).join("g").attr("class", "tick").attr("transform", function (t) { return "translate(" + x(t) + ",0)"; });
    tk.append("line").attr("y1", axisY).attr("y2", axisY + 5);
    tk.append("text").attr("y", axisY + 16).attr("text-anchor", "middle").text(function (t) { return fmtSecs(t, span); });
    if (!narrow) ax.append("text").attr("class", "t-muted t-small").attr("x", 8).attr("y", axisY + 16).text("seconds");

    // brush (beneath the marks, so marks stay hoverable)
    if (d3.brushX) {
      var brush = d3.brushX().extent([[M.l, lanesTop], [W - M.r, axisY]]).on("end", function (ev) {
        if (!ev.selection || !ev.sourceEvent) return;
        var a = x.invert(ev.selection[0]), b = x.invert(ev.selection[1]);
        if (b - a < Math.max(0.01, span / 400)) return;
        ui.domain = [Math.max(full[0], a), Math.min(full[1], b)];
        ui.zoomed = true;
        st.redraw(false);
      });
      svg.append("g").attr("class", "brush").call(brush);
      svg.on("dblclick", function () { if (ui.domain) { ui.domain = null; ui.zoomed = true; st.redraw(false); } });
    }

    // events -> clusters per lane (marks closer than CL px merge; zoom in to split them)
    var CL = narrow ? 14 : 12;
    var clusters = [];
    shown.forEach(function (l, li) {
      var evs = tr.events.filter(function (e) { return e.lane === l.id && e.t >= dom[0] - span * 0.002 && e.t <= dom[1] + span * 0.002; })
        .sort(function (a, b) { return a.t - b.t; });
      var cur = null;
      evs.forEach(function (e) {
        var px = x(e.t);
        if (cur && px - cur.x0 < CL) { cur.events.push(e); cur.x1 = px; }
        else { cur = { lane: l.id, li: li, x0: px, x1: px, events: [e] }; clusters.push(cur); }
      });
    });
    clusters.forEach(function (c) {
      c.x = (c.x0 + c.x1) / 2;
      c.y = lanesTop + c.li * LH + markY;
      c.top = c.events.slice().sort(function (a, b) { return SEV_RANK[b.severity] - SEV_RANK[a.severity] || a.t - b.t; })[0];
      c.sev = c.top.severity;
      c.key = c.lane + "@" + c.events[0]._i;
    });

    // exfil: a red rule through every lane, a glow column, and the "fake keys leave" label
    var ex = clusters.filter(function (c) { return c.lane === "exfil"; });
    var exG = svg.append("g").attr("clip-path", "url(#" + clipId + ")").attr("class", "bc-fadein");
    var lastRight = -1e9;
    ex.forEach(function (c, i) {
      exG.append("rect").attr("class", "exfil-glow").attr("x", c.x - 7).attr("width", 14).attr("y", 34).attr("height", axisY - 34);
      exG.append("line").attr("class", "exfil-rule").attr("x1", c.x).attr("x2", c.x).attr("y1", 34).attr("y2", axisY);
      var lbl = (i === 0 || narrow ? "fake keys leave" : "fake keys leave again") + (narrow ? "" : " \u00b7 " + fmtSecs(c.events[0].t, span));
      var tg = exG.append("g");
      var tx = tg.append("text").attr("class", "exfil-text").attr("y", 41).text(lbl);
      var tw = tx.node().getComputedTextLength() + 16;
      var left = c.x - tw / 2;
      left = Math.max(M.l - 4, Math.min(left, W - M.r - tw + 4));
      if (left < lastRight + 6) { tg.remove(); }
      else {
        lastRight = left + tw;
        tx.attr("x", left + 8);
        tg.insert("rect", "text").attr("class", "exfil-pill").attr("x", left).attr("y", 33).attr("width", tw).attr("height", 17).attr("rx", 8.5);
      }
    });

    // marks
    var mg = svg.append("g").attr("class", "bc-marks").attr("clip-path", "url(#" + clipId + ")");
    var maxX = d3.max(clusters, function (c) { return c.x; }) || 1;
    var m = mg.selectAll("g.bc-mark").data(clusters, function (c) { return c.key; }).join("g")
      .attr("class", function (c) { return "bc-mark" + (ui.selected === c.key ? " is-selected" : ""); })
      .attr("transform", function (c) { return "translate(" + c.x + "," + c.y + ")"; });
    m.append("rect").attr("class", "hit").attr("x", function (c) { return -Math.max(9, (c.x1 - c.x0) / 2 + 8); })
      .attr("width", function (c) { return Math.max(18, c.x1 - c.x0 + 16); }).attr("y", -LH / 2 + 3).attr("height", LH - 6);
    m.filter(function (c) { return c.lane === "exfil"; }).append("path").attr("class", "ripple").attr("d", shapePath("critical", true));
    var inner = m.append("g").attr("class", "bc-in").each(function (c) {
      this.style.setProperty("--d", Math.round(60 + (c.x / maxX) * 260) + "ms");
    });
    inner.append("path").attr("class", function (c) { return "shape m-" + c.sev; })
      .attr("d", function (c) { return shapePath(c.sev, c.lane === "exfil"); });
    inner.append("circle").attr("class", "sel").attr("r", function (c) { return c.lane === "exfil" ? 13 : 9; }).attr("fill", "none");
    m.append("circle").attr("class", "bc-focus-ring").attr("r", 12);
    clusters.forEach(function (c, i) {
      var next = clusters.filter(function (o) { return o.lane === c.lane && o.x > c.x; })[0];
      c.room = next ? next.x - c.x : 1e9;
    });
    // "\u00d7n" right of a mark, or above it when the next mark is close
    m.filter(function (c) { return c.events.length > 1; }).append("text").attr("class", "count")
      .attr("x", function (c) { return c.room > 30 ? (c.lane === "exfil" ? 13 : 9) : 0; })
      .attr("y", function (c) { return c.room > 30 ? 0 : -12; })
      .attr("text-anchor", function (c) { return c.room > 30 ? "start" : "middle"; })
      .text(function (c) { return "\u00d7" + c.events.length; });

    interactive(m, tt, function (c) {
      var lines = [];
      var lane = (lanes.filter(function (l) { return l.id === c.lane; })[0] || {}).name || c.lane;
      if (c.events.length === 1) {
        var e = c.events[0];
        lines.push(c.lane === "exfil" ? ["Fake secrets sent to " + e.label, "bad"] : e.label || lane);
        if (e.detail) lines.push(e.detail);
        lines.push([lane + " \u00b7 " + SEV_LABEL[e.severity] + " \u00b7 " + fmtSecs(e.t, span) + (e.step ? " \u00b7 " + e.step : ""), "s"]);
      } else {
        lines.push(c.lane === "exfil" ? ["Fake secrets sent " + c.events.length + " times", "bad"] : plural(c.events.length, lane.toLowerCase().replace(/s$/, ""), lane.toLowerCase()) + " within " + fmtSecs(c.events[c.events.length - 1].t - c.events[0].t, 1));
        c.events.slice(0, 6).forEach(function (e) { lines.push(fmtSecs(e.t, span) + "  " + (e.label || e.detail)); });
        if (c.events.length > 6) lines.push(["and " + (c.events.length - 6) + " more \u00b7 drag to zoom in", "s"]);
        lines.push([(c.top.step || "") + (c.top.step ? " \u00b7 " : "") + "highest: " + SEV_LABEL[c.sev], "s"]);
      }
      return lines;
    }, function (c) {
      ui.selected = c.key;
      m.classed("is-selected", function (o) { return o.key === c.key; });
      if (opts.onSelect) opts.onSelect(c.top.raw, c.events.map(function (e) { return e.raw; }));
    });

    if (!tr.events.length) {
      svg.append("text").attr("class", "t-muted").attr("x", (M.l + W) / 2).attr("y", lanesTop + lanesH / 2).attr("text-anchor", "middle")
        .text("No activity was recorded");
    }
    root.append(sevKeys());
  }

  // ---------------------------------------------------------------- 2. flow (secrets -> process -> destination)
  function drawFlow(st) {
    var root = st.root, narrow = st.narrow, W = st.width;
    var data = st.data || {};
    var nodes = (Array.isArray(data.nodes) ? data.nodes : []).filter(function (n) { return n && n.id != null; }).map(function (n) {
      return { id: str(n.id), label: str(n.label || n.id), kind: str(n.kind), taken: n.taken !== false, raw_ip: !!n.raw_ip,
        ins: [], outs: [] };
    });
    var byId = {};
    nodes.forEach(function (n) { byId[n.id] = n; });
    var links = (Array.isArray(data.links) ? data.links : []).filter(function (l) { return l && byId[l.source] && byId[l.target]; })
      .map(function (l, i) {
        var secrets = Array.isArray(l.secrets) ? l.secrets.map(str) : [];
        return { i: i, s: byId[l.source], t: byId[l.target], kind: str(l.kind), secrets: secrets, bytes: num(l.bytes),
          w: l.kind === "sent" ? Math.max(1, secrets.length) : 1 };
      });
    links.forEach(function (l) { l.s.outs.push(l); l.t.ins.push(l); });
    var secrets = nodes.filter(function (n) { return n.kind === "secret"; });
    var procs = nodes.filter(function (n) { return n.kind === "process"; });
    var dests = nodes.filter(function (n) { return n.kind === "destination"; });
    // a secret counts as taken only if it was sent (the node flag, cross-checked against the sent links)
    var sentNames = {};
    links.forEach(function (l) { if (l.kind === "sent") l.secrets.forEach(function (s) { sentNames[s] = true; }); });
    var anySent = Object.keys(sentNames).length > 0;
    secrets.forEach(function (n) { n.taken = anySent ? !!sentNames[n.label] : n.taken; });
    procs.forEach(function (n) { n.taken = n.outs.some(function (l) { return l.kind === "sent"; }); });
    dests.forEach(function (n) { n.taken = n.ins.length > 0; n.bytes = d3.sum(n.ins, function (l) { return l.bytes; }); });

    var tt;
    root.replaceChildren();
    if (!secrets.length && !links.length) {
      root.append(h("p", { class: "bc-empty", text: "No secrets were planted or moved in this scan." }));
      return;
    }
    var takenN = secrets.filter(function (n) { return n.taken; }).length;
    secrets.sort(function (a, b) { return (b.taken - a.taken) || (b.outs.length - a.outs.length) || a.label.localeCompare(b.label); });
    procs.sort(function (a, b) { return (b.taken - a.taken) || (d3.sum(b.ins, function (l) { return l.w; }) - d3.sum(a.ins, function (l) { return l.w; })); });
    dests.sort(function (a, b) { return d3.sum(b.ins, function (l) { return l.w; }) - d3.sum(a.ins, function (l) { return l.w; }); });

    var U = narrow ? 11 : 13;            // px per secret
    var GAP = narrow ? 5 : 7;
    var leftW = narrow ? Math.min(100, W * 0.3) : Math.min(190, W * 0.24);
    var rightW = narrow ? Math.min(128, W * 0.36) : Math.min(210, W * 0.26);
    var BAR = 8;
    var xL = leftW, xR = W - rightW - BAR, xM = Math.round((xL + xR) / 2 - BAR / 2);
    var top = 50;
    function weight(n) {
      var i = d3.sum(n.ins, function (l) { return l.w; }), o = d3.sum(n.outs, function (l) { return l.w; });
      return Math.max(1, i, o);
    }
    function stack(col, x, gap) {
      var y = 0;
      col.forEach(function (n) { n.x = x; n.h = weight(n) * U; n.y = y; y += n.h + gap; });
      return y - gap;
    }
    var hL = stack(secrets, xL, GAP), hM = stack(procs, xM, 34), hR = stack(dests, xR, 40);
    var Hc = Math.max(hL - 22, hM, hR);
    [[secrets, hL], [procs, hM], [dests, hR]].forEach(function (p) {
      var off = (p[0] === secrets ? 28 : top) + Math.max(0, (Hc - p[1]) / 2) * (p[0] === secrets ? 0 : 1);
      p[0].forEach(function (n) { n.y += off; });
    });
    var H = Math.max(top + Hc, 28 + hL) + 14;
    // link end positions, stacked along node edges in the order of the opposite node
    nodes.forEach(function (n) {
      var outs = n.outs.slice().sort(function (a, b) { return a.t.y - b.t.y; });
      var ins = n.ins.slice().sort(function (a, b) { return a.s.y - b.s.y; });
      var so = d3.sum(outs, function (l) { return l.w; }) * U, si = d3.sum(ins, function (l) { return l.w; }) * U;
      var yo = n.y + (n.h - so) / 2, yi = n.y + (n.h - si) / 2;
      outs.forEach(function (l) { l.y0 = yo + l.w * U / 2; yo += l.w * U; });
      ins.forEach(function (l) { l.y1 = yi + l.w * U / 2; yi += l.w * U; });
    });

    var svg = svgFor(root, W, H, "Where the fake secrets went: " + takenN + " of " + secrets.length + " planted secrets were sent to "
      + plural(dests.length, "destination") + ".");
    root.classList.toggle("is-focus", false);
    tt = tooltip(root);
    var heads = [["Fake secret", xL, "end"], ["Read by", xM + BAR / 2, "middle"], ["Sent to", xR + BAR + 2, "start"]];
    if (narrow) heads[0] = ["Secret", xL + BAR, "end"];
    svg.selectAll("text.col-head").data(heads).join("text").attr("class", "col-head")
      .attr("x", function (d) { return d[2] === "end" ? d[1] - 8 : d[2] === "start" ? d[1] + 6 : d[1]; }).attr("y", 10)
      .attr("text-anchor", function (d) { return d[2]; }).text(function (d) { return d[0]; });

    // "stolen" links burn with the heat gradient (in user space, so straight links still paint)
    var gid = "bc-heat-" + (++HEAT_SEQ);
    var lg = svg.append("defs").append("linearGradient").attr("id", gid).attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", xM).attr("x2", xR + BAR).attr("y1", 0).attr("y2", 0);
    [0, 0.42, 0.78, 1].forEach(function (o, i) { lg.append("stop").attr("offset", o).attr("class", "heat-" + i); });
    var linkG = svg.append("g").attr("class", "bc-fadein");
    var path = function (l) {
      var x0 = l.s.x + BAR, x1 = l.t.x, xm = (x0 + x1) / 2;
      return "M" + x0 + "," + l.y0 + "C" + xm + "," + l.y0 + " " + xm + "," + l.y1 + " " + x1 + "," + l.y1;
    };
    var lk = linkG.selectAll("path.link").data(links).join("path")
      .attr("class", function (l) { return "link" + (l.kind === "read" && !l.s.taken ? " read-only" : "") + (l.kind === "sent" ? " sent" : ""); })
      .each(function (l) { if (l.kind === "sent") this.style.stroke = "url(#" + gid + ")"; })
      .attr("d", path).attr("stroke-width", function (l) { return Math.max(1.5, l.w * U - (l.kind === "read" && !l.s.taken ? U * 0.6 : 1)); });
    var lh = linkG.selectAll("path.link-hit").data(links).join("path").attr("class", "link-hit").attr("d", path)
      .attr("stroke-width", function (l) { return Math.max(10, l.w * U); });

    var ng = svg.append("g").selectAll("g.node").data(nodes.filter(function (n) { return n.h != null; })).join("g")
      .attr("class", function (n) { return "node " + n.kind + (n.taken ? " taken" : " idle"); });
    ng.append("rect").attr("class", "hit").attr("x", function (n) { return n.kind === "secret" ? n.x - leftW : n.kind === "destination" ? n.x : n.x - 50; })
      .attr("width", function (n) { return n.kind === "process" ? BAR + 100 : n.kind === "secret" ? leftW + BAR : rightW + BAR; })
      .attr("y", function (n) { return n.kind === "process" ? n.y - 22 : n.y - 1; })
      .attr("height", function (n) { return n.kind === "process" ? n.h + 23 : Math.max(n.h + 2, 16); });
    ng.append("rect").attr("class", "bar bc-in").attr("x", function (n) { return n.x; }).attr("y", function (n) { return n.y; })
      .attr("width", BAR).attr("height", function (n) { return Math.max(2, n.h); }).attr("rx", 3);
    ng.append("rect").attr("class", "bc-focus-ring").attr("x", function (n) { return n.x - 3; }).attr("y", function (n) { return n.y - 3; })
      .attr("width", BAR + 6).attr("height", function (n) { return n.h + 6; }).attr("rx", 5);
    // secrets: label left of the bar; "not taken" on the right for untaken
    var sn = ng.filter(function (n) { return n.kind === "secret"; });
    sn.append("text").attr("class", "lbl").attr("x", function (n) { return n.x - 8; }).attr("y", function (n) { return n.y + n.h / 2; })
      .attr("text-anchor", "end").text(function (n) { return n.label; });
    fitAll(sn.select("text.lbl"), leftW - 12);
    sn.filter(function (n) { return !n.taken && !narrow; }).append("text").attr("class", "tag").attr("x", function (n) { return n.x + BAR + 6; })
      .attr("y", function (n) { return n.y + n.h / 2; }).text(function (n) { return n.outs.length ? "read, not sent" : "not taken"; });
    // processes: label above the bar
    var pn = ng.filter(function (n) { return n.kind === "process"; });
    pn.append("text").attr("class", "lbl halo").attr("x", function (n) { return n.x + BAR / 2; }).attr("y", function (n) { return n.y - 10; })
      .attr("text-anchor", "middle").text(function (n) { return n.label; });
    fitAll(pn.select("text.lbl"), Math.max(60, (xR - xL) * (narrow ? 0.95 : 0.45)));
    // destinations: label right of the bar, raw-IP badge + totals under it
    var dn = ng.filter(function (n) { return n.kind === "destination"; });
    dn.append("text").attr("class", "lbl t-strong").attr("x", function (n) { return n.x + BAR + 8; })
      .attr("y", function (n) { return n.y + n.h / 2 - (narrow ? 8 : 9); }).text(function (n) { return n.label; });
    fitAll(dn.select("text.lbl"), rightW - 10);
    dn.append("text").attr("class", "sub t-num").attr("x", function (n) { return n.x + BAR + 8; })
      .attr("y", function (n) { return n.y + n.h / 2 + (narrow ? 8 : 9); })
      .text(function (n) {
        var k = {};
        n.ins.forEach(function (l) { l.secrets.forEach(function (s) { k[s] = 1; }); });
        var c = Object.keys(k).length;
        return (narrow ? c + " secrets" : plural(c, "secret")) + (n.bytes ? " \u00b7 " + fmtBytes(n.bytes) : "");
      });
    dn.each(function (n) {
      if (!n.raw_ip) return;
      var g = d3.select(this);
      var sub = g.select("text.sub").node();
      var sx = n.x + BAR + 8 + sub.getComputedTextLength() + 8;
      var bx = sx + 46 > W ? n.x + BAR + 8 : sx;
      var by = sx + 46 > W ? n.y + n.h / 2 + 18 : n.y + n.h / 2 + (narrow ? 1 : 2);
      var b = g.append("g").attr("class", "badge");
      b.append("rect").attr("x", bx).attr("y", by).attr("width", 44).attr("height", 15).attr("rx", 7.5);
      b.append("text").attr("x", bx + 22).attr("y", by + 7.5).attr("text-anchor", "middle").text("RAW IP");
    });

    // highlight: the paths through a node or a link
    function relatedTo(n) {
      var on = { nodes: {}, links: {} };
      function addLink(l) { on.links[l.i] = 1; on.nodes[l.s.id] = 1; on.nodes[l.t.id] = 1; }
      on.nodes[n.id] = 1;
      if (n.kind === "secret") {
        n.outs.forEach(function (l) {
          addLink(l);
          l.t.outs.forEach(function (o) { if (o.secrets.indexOf(n.label) >= 0) addLink(o); });
        });
      } else if (n.kind === "process") {
        n.ins.forEach(addLink); n.outs.forEach(addLink);
      } else {
        n.ins.forEach(function (l) {
          addLink(l);
          l.s.ins.forEach(function (r) { if (l.secrets.indexOf(r.s.label) >= 0) addLink(r); });
        });
      }
      return on;
    }
    function focus(on) {
      root.classList.toggle("is-focus", !!on);
      lk.classed("on", function (l) { return !!(on && on.links[l.i]); });
      ng.classed("on", function (n) { return !!(on && on.nodes[n.id]); });
    }
    interactive(ng, tt, function (n) {
      if (n.kind === "secret") {
        var to = [];
        n.outs.forEach(function (l) { l.t.outs.forEach(function (o) { if (o.secrets.indexOf(n.label) >= 0) to.push(o.t.label); }); });
        return [n.label, n.taken ? ["Sent to " + to.join(", "), "bad"] : n.outs.length ? "Read by " + n.outs.map(function (l) { return l.t.label; }).join(", ") + ", never sent" : "Not taken: nothing touched it",
          n.outs.length ? ["Read by " + n.outs.map(function (l) { return l.t.label; }).join(", "), "s"] : null];
      }
      if (n.kind === "process") {
        return ["Process: " + n.label, "Read " + plural(n.ins.length, "fake secret"), n.outs.length ? ["Sent to " + n.outs.map(function (l) { return l.t.label; }).join(", "), "bad"] : "Sent nothing out"];
      }
      var k = {};
      n.ins.forEach(function (l) { l.secrets.forEach(function (s) { k[s] = 1; }); });
      return [n.label, ["Received " + plural(Object.keys(k).length, "fake secret") + (n.bytes ? " in " + fmtBytes(n.bytes) : ""), "bad"],
        n.raw_ip ? "A raw IP address: no domain name, typical of malware" : null, Object.keys(k).length ? ["" + Object.keys(k).join(", "), "s"] : null];
    });
    ng.on("mouseenter.hl focus.hl", function (e, n) { focus(relatedTo(n)); })
      .on("mouseleave.hl blur.hl", function () { focus(null); });
    lh.on("mouseenter", function (e, l) {
      var on = { nodes: {}, links: {} };
      on.links[l.i] = 1; on.nodes[l.s.id] = 1; on.nodes[l.t.id] = 1;
      focus(on);
      tt.show(l.kind === "sent" ? [l.s.label + " \u2192 " + l.t.label, [plural(l.secrets.length, "fake secret") + (l.bytes ? " \u00b7 " + fmtBytes(l.bytes) : ""), "bad"], [l.secrets.join(", "), "s"]]
        : [l.s.label + " read by " + l.t.label, l.s.taken ? "then sent out" : "never sent"], e);
    }).on("mousemove", function (e) { tt.move(e); }).on("mouseleave", function () { focus(null); tt.hide(); });
  }

  var HEAT_SEQ = 0;

  // ---------------------------------------------------------------- 3. bait board
  var GLYPHS = {   // simple 24px line icons (static strings, never data)
    cloud: "M7 18h10a4 4 0 0 0 .6-7.95A6 6 0 0 0 6.2 9.6 4.2 4.2 0 0 0 7 18z",
    key: "M14.5 9.5a4 4 0 1 1-1.2-2.8M13.3 6.7 20 13.4M17 10.4l2-2M15 8.4l1.5-1.5",
    wallet: "M4 7h14a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zM4 7l11-3v3M16 13h.01",
    lock: "M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3",
    term: "M4 5h16v14H4zM8 10l3 2-3 2M13 15h3",
    file: "M7 3h7l4 4v14H7zM14 3v4h4M10 13h5M10 17h5",
    seed: "M5 5h14v14H5zM8 9h8M8 12h8M8 15h5",
  };
  function glyphFor(kind) {
    var k = kind.toLowerCase();
    if (/aws|cloud|gcp|azure/.test(k)) return "cloud";
    if (/seed|phrase|mnemonic/.test(k)) return "seed";
    if (/wallet|solana|exodus|metamask|vault|crypto/.test(k)) return "wallet";
    if (/password|login|cookie/.test(k)) return "lock";
    if (/history|shell/.test(k)) return "term";
    if (/\.env|stripe|openai|database|config/.test(k)) return "file";
    return "key";
  }
  function glyph(name) {
    var s = svgEl("svg", { viewBox: "0 0 24 24", "aria-hidden": "true" });
    s.append(svgEl("path", { d: GLYPHS[name] || GLYPHS.key }));
    return s;
  }

  function drawBoard(st) {
    var root = st.root, ui = st.ui;
    var bait = Array.isArray(st.data.bait) ? st.data.bait : [];
    var stolen = Array.isArray(st.data.stolen) ? st.data.stolen : [];
    var by = {};
    stolen.forEach(function (s) {
      if (!s) return;
      var k = str(s.secret);
      (by[k] = by[k] || []).push(s);
    });
    var tiles = bait.map(function (b, i) {
      var kind = str(b && (b.kind || b.secret || b.name));
      var file = str(b && (b.file || b.path));
      var got = by[kind] || [];
      var dests = [], steps = [];
      got.forEach(function (s) {
        var d = str(s.sent_to || s.dst);
        if (d && dests.indexOf(d) < 0) dests.push(d);
        if (s.step && steps.indexOf(str(s.step)) < 0) steps.push(str(s.step));
      });
      return { i: i, kind: kind, file: file || str(got[0] && got[0].from_file), stolen: got.length > 0, dests: dests, steps: steps };
    });
    // stolen entries for secrets that were not in the bait list still deserve a tile
    Object.keys(by).forEach(function (k) {
      if (!tiles.some(function (t) { return t.kind === k; })) {
        var s = by[k][0];
        tiles.push({ i: tiles.length, kind: k, file: str(s.from_file), stolen: true, dests: [str(s.sent_to || s.dst)], steps: [str(s.step)] });
      }
    });
    tiles.sort(function (a, b) { return (b.stolen - a.stolen) || a.i - b.i; });
    var nStolen = tiles.filter(function (t) { return t.stolen; }).length;
    ui.filter = ui.filter || "all";
    root.replaceChildren();
    if (!tiles.length) { root.append(h("p", { class: "bc-empty", text: "No fake secrets were planted." })); return; }
    var tt = null;
    var legend = chips([
      { id: "all", label: "All", n: tiles.length, sw: null },
      { id: "stolen", label: "Stolen", n: nStolen, sw: "sq k-stolen" },
      { id: "untouched", label: "Not taken", n: tiles.length - nStolen, sw: "sq k-untouched" },
    ], function (id) { return ui.filter === id; }, function (id) { ui.filter = id; st.redraw(false); }, "Filter the fake secrets");
    legend.classList.add("is-radio");
    var grid = h("ul", { class: "bc-board-grid", "aria-label": nStolen + " of " + tiles.length + " fake secrets stolen" });
    tiles.forEach(function (t, i) {
      var dim = ui.filter === "stolen" ? !t.stolen : ui.filter === "untouched" ? t.stolen : false;
      var li = h("li", { class: "bc-tile" + (t.stolen ? " stolen" : "") + (dim ? " is-dim" : ""), tabindex: "0",
        "aria-label": t.kind + ": " + (t.stolen ? "stolen, sent to " + t.dests.join(", ") : "not taken") + (t.file ? ". Planted at " + t.file : "") },
        h("span", { class: "k", text: t.kind }),
        h("span", { class: "rx", "aria-hidden": "true" }, h("span", { class: "rx-t", text: t.stolen ? "→ " + t.dests.join(", ") : "██████" })),
        h("span", { class: "st", text: t.stolen ? "Stolen" + (t.steps.length ? " · during " + t.steps.join(", ") : "") : "Not taken" }),
        t.file ? h("span", { class: "p", text: t.file }) : null);
      li.style.setProperty("--d", Math.min(i * 22, 300) + "ms");
      li.addEventListener("mouseenter", function (e) { tt.show(tipFor(t), e); });
      li.addEventListener("mousemove", function (e) { tt.move(e); });
      li.addEventListener("mouseleave", function () { tt.hide(); });
      li.addEventListener("focus", function () { tt.show(tipFor(t), li); });
      li.addEventListener("blur", function () { tt.hide(); });
      grid.append(li);
    });
    function tipFor(t) {
      return [t.kind, t.stolen ? ["Stolen: sent to " + t.dests.join(", "), "bad"] : "Not taken: the take-home never sent it",
        t.steps.length ? "During " + t.steps.join(", ") : null, t.file ? ["Planted at " + t.file, "s"] : null];
    }
    root.append(h("div", { class: "bc-head" }, legend), grid);
    tt = tooltip(root);
  }

  // ---------------------------------------------------------------- bench helpers
  function sampleRows(samples) {
    return (Array.isArray(samples) ? samples : []).filter(Boolean).map(function (s) {
      var mal = str(s.expected).toLowerCase() === "malicious";
      var gd = s.guarddog || {};
      var burner = !!s.detected, guard = !!gd.flagged;
      var name = str(s.name);
      var m = /^([a-z]\d+)-(.*)$/i.exec(name);
      return { name: name, id: m ? m[1] : "", short: m ? m[2] : name, mal: mal, technique: str(s.technique), headline: str(s.headline),
        verdict: str(s.verdict), secs: num(s.secs, NaN), gdRules: (gd.threat_rules || []).map(str), gdSecs: num(gd.secs, NaN),
        cells: [
          { det: "burner", outcome: mal ? (burner ? "caught" : "missed") : (burner ? "false" : "quiet") },
          { det: "guarddog", outcome: mal ? (guard ? "caught" : "missed") : (guard ? "false" : "quiet") },
        ] };
    });
  }
  var OUTCOME = { caught: "\u2713 caught", missed: "\u2717 missed", false: "! false alarm", quiet: "\u2713 quiet" };
  var OUTCOME_LONG = { caught: "caught it", missed: "missed it", false: "false alarm on a clean repo", quiet: "correctly quiet" };
  var DET = { burner: "Burner", guarddog: "GuardDog" };

  // ---------------------------------------------------------------- 4. bench matrix
  function drawMatrix(st) {
    var root = st.root, ui = st.ui, narrow = st.narrow, W = st.width;
    var rows = sampleRows(st.data);
    root.replaceChildren();
    if (!rows.length) { root.append(h("p", { class: "bc-empty", text: "No benchmark samples." })); return; }
    ui.on = ui.on || { caught: true, missed: true, false: true, quiet: true };
    var count = { caught: 0, missed: 0, false: 0, quiet: 0 };
    rows.forEach(function (r) { r.cells.forEach(function (c) { count[c.outcome]++; }); });
    var legend = chips(["caught", "missed", "false", "quiet"].map(function (k) {
      return { id: k, label: { caught: "Caught", missed: "Missed", false: "False alarm", quiet: "Correctly quiet" }[k], n: count[k], sw: "sq k-" + k };
    }), function (id) { return ui.on[id]; }, function (id) {
      var n = Object.keys(ui.on).filter(function (k) { return ui.on[k]; }).length;
      var allOn = n === 4;
      if (allOn) { Object.keys(ui.on).forEach(function (k) { ui.on[k] = k === id; }); }   // first click isolates
      else { ui.on[id] = !ui.on[id]; if (!Object.keys(ui.on).some(function (k) { return ui.on[k]; })) Object.keys(ui.on).forEach(function (k) { ui.on[k] = true; }); }
      st.redraw(false);
    }, "Highlight outcomes");
    root.append(h("div", { class: "bc-head" }, legend));
    var tt = tooltip(root);

    var groups = [
      { title: "Malicious take-homes", rows: rows.filter(function (r) { return r.mal; }) },
      { title: "Clean take-homes", rows: rows.filter(function (r) { return !r.mal; }) },
    ].filter(function (g) { return g.rows.length; });
    var RH = 28, GH = 34, HEAD = 46;
    var cellW = narrow ? Math.min(84, (W - 120) / 2) : Math.min(150, Math.max(110, (W - 320) / 2));
    var labelW = W - cellW * 2 - 16;
    var nameW = narrow ? labelW - 46 : Math.min(250, labelW * 0.4);
    var H = HEAD + groups.length * GH + rows.length * RH + 6;
    var svg = svgFor(root, W, H, "Benchmark: each sample, and whether Burner and GuardDog flagged it.");
    var cx = [labelW + 8, labelW + 8 + cellW + 8];
    ["burner", "guarddog"].forEach(function (det, j) {
      var mal = rows.filter(function (r) { return r.mal; }), ben = rows.filter(function (r) { return !r.mal; });
      var caught = mal.filter(function (r) { return r.cells[j].outcome === "caught"; }).length;
      var fa = ben.filter(function (r) { return r.cells[j].outcome === "false"; }).length;
      svg.append("text").attr("class", "col-head").attr("x", cx[j] + cellW / 2 - 4).attr("y", 12).attr("text-anchor", "middle").text(DET[det]);
      svg.append("text").attr("class", "col-sub t-num").attr("x", cx[j] + cellW / 2 - 4).attr("y", 30).attr("text-anchor", "middle")
        .text(narrow ? caught + "/" + mal.length + " · " + fa + " FA" : caught + "/" + mal.length + " · " + fa + "/" + ben.length + " FA");
    });
    var y = HEAD;
    var allRows = [];
    groups.forEach(function (g) {
      svg.append("text").attr("class", "group-head").attr("x", 4).attr("y", y + GH / 2 + 4).text(g.title + " \u00b7 " + g.rows.length);
      svg.append("line").attr("class", "rule").attr("x1", 0).attr("x2", W).attr("y1", y + GH - 3).attr("y2", y + GH - 3);
      y += GH;
      g.rows.forEach(function (r) { r.y = y; y += RH; allRows.push(r); });
    });
    var rg = svg.append("g").selectAll("g.bc-row").data(allRows).join("g").attr("class", "bc-row bc-fadein")
      .attr("transform", function (r) { return "translate(0," + r.y + ")"; })
      .each(function (r, i) { this.style.setProperty("--d", Math.min(i * 14, 320) + "ms"); });
    rg.append("rect").attr("class", "hit").attr("x", 0).attr("width", W).attr("height", RH).attr("rx", 6);
    rg.append("rect").attr("class", "bc-focus-ring").attr("x", 1).attr("y", 1).attr("width", W - 2).attr("height", RH - 2).attr("rx", 6);
    rg.append("text").attr("class", "id").attr("x", 6).attr("y", RH / 2).text(function (r) { return r.id; });
    var nm = rg.append("text").attr("class", "name").attr("x", 42).attr("y", RH / 2).text(function (r) { return r.short; });
    fitAll(nm, nameW);
    if (!narrow && labelW - nameW - 70 > 120) {
      var tq = rg.append("text").attr("class", "t-muted").attr("x", 42 + nameW + 18).attr("y", RH / 2).text(function (r) { return r.technique; });
      fitAll(tq, labelW - nameW - 70);
    }
    var cell = rg.selectAll("g.cell").data(function (r) { return r.cells; }).join("g")
      .attr("class", function (c) { return "cell c-" + c.outcome + (ui.on[c.outcome] ? "" : " is-dim"); })
      .attr("transform", function (c, j) { return "translate(" + cx[j] + ",3)"; });
    cell.append("rect").attr("width", cellW - 8).attr("height", RH - 6).attr("rx", 6);
    cell.append("text").attr("x", (cellW - 8) / 2).attr("y", (RH - 6) / 2).text(function (c) { return narrow && c.outcome === "false" ? "! false" : OUTCOME[c.outcome]; });
    interactive(rg, tt, function (r) {
      return [r.name + (r.mal ? " (malicious)" : " (clean)"), r.technique || null,
        ["Burner: " + OUTCOME_LONG[r.cells[0].outcome] + (r.verdict ? " \u00b7 " + r.verdict.toLowerCase() : "") + (isFinite(r.secs) ? " \u00b7 " + r.secs.toFixed(1) + " s" : ""), r.cells[0].outcome === "missed" || r.cells[0].outcome === "false" ? "bad" : "m"],
        ["GuardDog: " + OUTCOME_LONG[r.cells[1].outcome] + (r.gdRules.length ? " \u00b7 " + r.gdRules.join(", ") : ""), "m"],
        r.headline ? [r.headline, "s"] : null];
    });
  }

  // ---------------------------------------------------------------- 5. score bars
  function drawScore(st) {
    var root = st.root, ui = st.ui, narrow = st.narrow, W = st.width;
    var s = st.data || {};
    var mal = num(s.malicious), ben = num(s.benign);
    var metrics = [
      { id: "det", title: "Malicious repos caught", sub: "of " + mal + " \u00b7 higher is better", of: mal,
        v: { burner: num(s.burner_detected), guarddog: num(s.guarddog_detected) } },
      { id: "fa", title: "False alarms on clean repos", sub: "of " + ben + " \u00b7 lower is better", of: ben,
        v: { burner: num(s.burner_false_alarms), guarddog: num(s.guarddog_false_alarms) } },
    ];
    ui.on = ui.on || { burner: true, guarddog: true };
    var legend = chips([{ id: "burner", label: "Burner", sw: "sq k-burner" }, { id: "guarddog", label: "GuardDog", sw: "sq k-guarddog" }],
      function (id) { return ui.on[id]; }, function (id) {
        if (ui.on[id] && Object.keys(ui.on).filter(function (k) { return ui.on[k]; }).length === 1) return;
        ui.on[id] = !ui.on[id]; st.redraw(false);
      }, "Detectors");
    root.replaceChildren(h("div", { class: "bc-head" }, legend));
    var tt = tooltip(root);
    var dets = ["burner", "guarddog"].filter(function (d) { return ui.on[d]; });
    var labelW = narrow ? 74 : 96, valW = narrow ? 112 : 150, BH = 16, RG = 26, MH = 40, GAPM = 18;
    var H = metrics.length * (MH + dets.length * RG + GAPM);
    var svg = svgFor(root, W, H, metrics.map(function (m) {
      return m.title + ": Burner " + m.v.burner + " of " + m.of + ", GuardDog " + m.v.guarddog + " of " + m.of;
    }).join(". "));
    var x = d3.scaleLinear().domain([0, 1]).range([labelW, W - valW]);
    var y = 0, k = 0;
    metrics.forEach(function (m) {
      svg.append("text").attr("class", "metric").attr("x", 0).attr("y", y + 12).text(m.title);
      var sub = svg.append("text").attr("class", "metric-sub").attr("x", 0).attr("y", y + 29).text(m.sub);
      fit(sub.node(), W);
      y += MH;
      dets.forEach(function (d) {
        var v = m.v[d], frac = m.of ? v / m.of : 0;
        var g = svg.append("g").attr("class", "bc-row").datum({ m: m, d: d, v: v, frac: frac }).attr("transform", "translate(0," + y + ")");
        g.append("text").attr("class", "t-ink").attr("x", 0).attr("y", BH / 2 + 2).text(DET[d]);
        g.append("rect").attr("class", "bar-track").attr("x", labelW).attr("y", 2).attr("width", x(1) - labelW).attr("height", BH).attr("rx", 4);
        var p = g.append("path").attr("class", "bc-bar b-" + d).attr("d", barPath(labelW, x(frac), 2, BH));
        p.node().style.setProperty("--d", (k++ * 70) + "ms");
        if (frac === 0) g.append("rect").attr("class", "b-" + d).attr("x", labelW).attr("y", 2).attr("width", 2).attr("height", BH);
        g.append("text").attr("class", "val").attr("x", x(1) + 10).attr("y", BH / 2 + 2)
          .text(v + " of " + m.of + " \u00b7 " + pct(frac));
        g.append("rect").attr("class", "bc-focus-ring").attr("x", -2).attr("y", -2).attr("width", W + 2).attr("height", BH + 8).attr("rx", 6);
        interactive(g, tt, function (o) {
          return [DET[o.d] + ": " + o.v + " of " + o.m.of + " (" + pct(o.frac) + ")", o.m.title.toLowerCase(),
            o.m.id === "det" ? ["Missed " + (o.m.of - o.v), "s"] : ["Clean repos called out by mistake", "s"]];
        });
        y += RG;
      });
      y += GAPM;
    });
  }

  // ---------------------------------------------------------------- 6. scan times (strip / beeswarm)
  function drawTimes(st) {
    var root = st.root, narrow = st.narrow, W = st.width;
    var rows = sampleRows(st.data).filter(function (r) { return isFinite(r.secs); });
    root.replaceChildren();
    if (!rows.length) { root.append(h("p", { class: "bc-empty", text: "No scan times." })); return; }
    var tt = tooltip(root);
    var R = narrow ? 5 : 6;
    var groups = [
      { title: "Malicious", rows: rows.filter(function (r) { return r.mal; }) },
      { title: "Clean", rows: rows.filter(function (r) { return !r.mal; }) },
    ].filter(function (g) { return g.rows.length; });
    var labelW = narrow ? 70 : 92, M = { r: 14, t: 26, b: 30 };
    var max = d3.max(rows, function (r) { return r.secs; });
    var x = d3.scaleLinear().domain([0, Math.max(10, max * 1.05)]).range([labelW, W - M.r]).nice();
    // deterministic swarm: each dot takes the nearest free slot above/below its row line
    groups.forEach(function (g) {
      var placed = [];
      g.rows.slice().sort(function (a, b) { return a.secs - b.secs; }).forEach(function (r) {
        var cx = x(r.secs), dy = 0;
        for (var k = 0; k < 60; k++) {
          dy = (k % 2 ? 1 : -1) * Math.ceil(k / 2) * (R * 2 + 1);
          var ok = placed.every(function (p) { return Math.hypot(p.cx - cx, p.dy - dy) >= R * 2 + 1; });
          if (ok) break;
        }
        r.cx = cx; r.dy = dy; placed.push(r);
      });
      var ext = d3.extent(placed, function (p) { return p.dy; });
      g.span = [ext[0] - R - 6, ext[1] + R + 6];
    });
    var y = M.t;
    groups.forEach(function (g) { g.y = y - g.span[0]; y += g.span[1] - g.span[0] + 10; });
    var H = y + M.b;
    var med = d3.median(rows, function (r) { return r.secs; });
    var gdMed = d3.median(rows.filter(function (r) { return isFinite(r.gdSecs); }), function (r) { return r.gdSecs; });
    var svg = svgFor(root, W, H, "Scan time per sample; median " + med.toFixed(1) + " seconds.");
    var ticks = x.ticks(narrow ? 4 : 8);
    var tk = svg.append("g").selectAll("g.tick").data(ticks).join("g").attr("class", "tick").attr("transform", function (t) { return "translate(" + x(t) + ",0)"; });
    tk.append("line").attr("y1", M.t - 4).attr("y2", H - M.b);
    tk.append("text").attr("y", H - M.b + 14).attr("text-anchor", "middle").text(function (t) { return t + " s"; });
    groups.forEach(function (g) {
      svg.append("text").attr("class", "row-name").attr("x", 0).attr("y", g.y).text(g.title);
      svg.append("text").attr("class", "t-muted t-small").attr("x", 0).attr("y", g.y + 15).text(plural(g.rows.length, "repo"));
    });
    svg.append("line").attr("class", "median").attr("x1", x(med)).attr("x2", x(med)).attr("y1", M.t - 8).attr("y2", H - M.b);
    var ml = svg.append("text").attr("class", "median-label halo").attr("y", M.t - 16).attr("text-anchor", "end").attr("x", x(med) + 4)
      .text("median " + med.toFixed(1) + " s");
    if (x(med) - ml.node().getComputedTextLength() < labelW) ml.attr("text-anchor", "start").attr("x", x(med) - 4);
    var all = [];
    groups.forEach(function (g) { g.rows.forEach(function (r) { r.cy = g.y + r.dy; all.push(r); }); });
    var mk = svg.append("g").selectAll("g.bc-mark").data(all).join("g").attr("class", "bc-mark")
      .attr("transform", function (r) { return "translate(" + r.cx + "," + r.cy + ")"; });
    mk.append("circle").attr("class", function (r) {
      var v = r.verdict.toUpperCase();
      return "dot bc-in " + (v.indexOf("MALICIOUS BEHAVIOUR") >= 0 || v.indexOf("NO ") === 0 ? "v-clean" : v === "MALICIOUS" ? "v-malicious" : v === "SUSPICIOUS" ? "v-suspicious" : "v-clean");
    }).attr("r", R).each(function (r) { this.style.setProperty("--d", Math.round((r.cx / W) * 300) + "ms"); });
    mk.append("circle").attr("class", "bc-focus-ring").attr("r", R + 3);
    interactive(mk, tt, function (r) {
      return [r.name, r.secs.toFixed(1) + " s to scan \u00b7 " + (r.verdict || "").toLowerCase(), r.technique ? [r.technique, "s"] : null];
    });
    root.append(h("div", { class: "bc-foot" },
      h("span", { class: "bc-key" }, h("span", { class: "bc-sw k-malicious" }), h("span", { text: "Verdict: malicious" })),
      h("span", { class: "bc-key" }, h("span", { class: "bc-sw k-suspicious" }), h("span", { text: "suspicious" })),
      h("span", { class: "bc-key" }, h("span", { class: "bc-sw k-clean" }), h("span", { text: "nothing malicious" })),
      isFinite(gdMed) ? h("span", { text: "GuardDog reads the code without running it: median " + gdMed.toFixed(2) + " s." }) : null));
  }

  // ---------------------------------------------------------------- 7. donut
  var SAFE_COLOR = /^(#[0-9a-f]{3,8}|var\(--[\w-]+\)|[a-z]{3,20}|rgba?\([\d\s.,%]+\)|hsla?\([\d\s.,%deg]+\))$/i;
  function drawDonut(st) {
    var root = st.root;
    var items = (Array.isArray(st.data) ? st.data : []).filter(Boolean).map(function (d, i) {
      return { label: str(d.label), value: Math.max(0, num(d.value)), color: SAFE_COLOR.test(str(d.color)) ? str(d.color) : null, i: i };
    });
    var total = d3.sum(items, function (d) { return d.value; });
    var size = Math.max(56, Math.min(num(st.opts.size, 120), st.width));
    root.replaceChildren();
    var tt = tooltip(root);
    var svg = svgFor(root, size, size, items.map(function (d) { return d.label + " " + d.value; }).join(", ") + " (total " + total + ")");
    var g = svg.append("g").attr("transform", "translate(" + size / 2 + "," + size / 2 + ")");
    var r = size / 2 - 2;
    var arc = d3.arc().innerRadius(r * 0.7).outerRadius(r).cornerRadius(2);
    var pie = d3.pie().sort(null).value(function (d) { return d.value; }).padAngle(total ? 0.02 : 0);
    if (!total) {
      g.append("path").attr("class", "arc d-1").attr("d", arc({ startAngle: 0, endAngle: 2 * Math.PI }));
    } else {
      var arcs = g.selectAll("path.arc").data(pie(items)).join("path")
        .attr("class", function (d) { return "arc d-" + Math.min(3, d.data.i); }).attr("d", arc)
        .each(function (d) { if (d.data.color) this.style.setProperty("fill", d.data.color); });
      if (st.root.classList.contains("bc-anim")) {
        arcs.transition().duration(380).ease(d3.easeCubicOut).attrTween("d", function (d) {
          var i = d3.interpolate({ startAngle: d.startAngle, endAngle: d.startAngle }, d);
          return function (t) { return arc(i(t)); };
        });
      }
      interactive(arcs, tt, function (d) { return [d.data.label + ": " + d.data.value, (total ? pct(d.data.value / total) : "") + " of " + total]; });
    }
    var first = items[0];
    g.append("text").attr("class", "big").attr("y", st.opts.caption === false ? 0 : -5).text(first ? String(first.value) : "0");
    if (st.opts.caption !== false) g.append("text").attr("class", "of").attr("y", size * 0.14).text(st.opts.caption || "of " + total);
  }

  // ---------------------------------------------------------------- public API
  window.BurnerCharts = {
    timeline: function (el, trace, opts) { return mount(el, "timeline", trace, opts, drawTimeline); },
    flow: function (el, flows, opts) { return mount(el, "flow", flows, opts, drawFlow); },
    baitBoard: function (el, bait, stolen, opts) {
      var api = mount(el, "board", { bait: bait, stolen: stolen }, opts, drawBoard);
      return { update: function (b, s) { api.update(b && b.bait !== undefined && s === undefined ? b : { bait: b, stolen: s }); }, destroy: api.destroy };
    },
    benchMatrix: function (el, samples, opts) { return mount(el, "matrix", samples, opts, drawMatrix); },
    scoreBars: function (el, summary, opts) { return mount(el, "bars", summary, opts, drawScore); },
    scanTimes: function (el, samples, opts) { return mount(el, "strip", samples, opts, drawTimes); },
    donut: function (el, items, opts) {
      opts = Object.assign({ size: 120 }, opts || {});
      opts.fixedWidth = opts.size;
      return mount(el, "donut", items, opts, drawDonut);
    },
  };
})();
