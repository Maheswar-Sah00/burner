/* Static GitHub Pages build of Burner: stands in for the FastAPI control VM (now switched off).
   Serves recorded real scans from static/data/ and replays their event stream at the recorded pace.
   Live scans need a throwaway Vultr VM per repo, so they are not available here. */
(function () {
  var BASE = window.__BASE = "/burner";
  var REC = ["clean-takehome", "npm-start-stealer"];
  var NO_LIVE = "This is the static demo on GitHub Pages. Live scans ran on a throwaway Vultr VM per repo during the " +
    "hackathon, and that server is now off. Press \"Watch a recorded scan\" to replay a real scan.";

  window.__bpath = function () {
    var p = location.pathname;
    if (p.indexOf(BASE) === 0) p = p.slice(BASE.length);
    return p || "/";
  };
  function pref(u) {
    return typeof u === "string" && u.charAt(0) === "/" && u.charAt(1) !== "/" && u.indexOf(BASE + "/") !== 0 && u !== BASE ? BASE + u : u;
  }
  ["pushState", "replaceState"].forEach(function (k) {
    var orig = history[k].bind(history);
    history[k] = function (s, t, u) { return orig(s, t, u == null ? u : pref(u)); };
  });

  var origFetch = window.fetch.bind(window);
  var cache = {}, started = {};
  function load(name) {
    if (!cache[name]) cache[name] = origFetch(BASE + "/static/data/" + name + ".json").then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
    return cache[name];
  }
  function reply(obj, status) {
    return new Response(JSON.stringify(obj), { status: status || 200, headers: { "Content-Type": "application/json" } });
  }
  function lastT(d) { return d.events.length ? d.events[d.events.length - 1].t : 0; }

  window.fetch = function (input, init) {
    var url = typeof input === "string" ? input : input.url;
    var method = ((init && init.method) || "GET").toUpperCase();
    if (url.indexOf("/api/") !== 0) return origFetch(pref(url), init);
    if (url === "/api/recorded") return Promise.resolve(reply({ samples: REC }));
    if (url === "/api/benchmark") return load("benchmark").then(reply);
    if (url === "/api/scan" && method === "POST") {
      var b = {};
      try { b = JSON.parse(init.body); } catch (e) { /* empty body */ }
      if (b.sample && REC.indexOf(b.sample) >= 0) {
        started[b.sample] = Date.now();
        return Promise.resolve(reply({ id: b.sample }));
      }
      return Promise.resolve(reply({ detail: NO_LIVE }, 400));
    }
    var m = /^\/api\/scan\/([^/?]+)(\/[a-z-]+)?/.exec(url);
    if (m) {
      var id = decodeURIComponent(m[1]);
      if (method === "DELETE") return Promise.resolve(reply({ status: "done", cancelled: false }));
      if (m[2] || REC.indexOf(id) < 0) return Promise.resolve(reply({ detail: "Not available in the static demo." }, 404));
      return load(id).then(function (d) {
        var t0 = started[id];
        if (t0 && (Date.now() - t0) / 1000 < lastT(d)) {
          var el = (Date.now() - t0) / 1000;
          return reply({ status: "running", events: d.events.filter(function (e) { return e.t <= el; }), report: null });
        }
        return reply({ status: "done", events: d.events, report: d.report });
      });
    }
    return Promise.resolve(reply({ detail: "Not available in the static demo." }, 404));
  };

  function FakeEventSource(url) {
    var self = this, timers = [], ends = [];
    self.readyState = 1;
    self.onmessage = null;
    self.onerror = null;
    self.addEventListener = function (type, fn) { if (type === "end") ends.push(fn); };
    self.close = function () { self.readyState = 2; timers.forEach(clearTimeout); };
    var m = /^\/api\/scan\/([^/?]+)\/events/.exec(url), id = m ? decodeURIComponent(m[1]) : "";
    load(id).then(function (d) {
      var t0 = started[id] || Date.now(), off = (Date.now() - t0) / 1000;
      d.events.forEach(function (ev) {
        timers.push(setTimeout(function () {
          if (self.readyState !== 2 && self.onmessage) self.onmessage({ data: JSON.stringify(ev) });
        }, Math.max(0, (ev.t - off) * 1000)));
      });
      timers.push(setTimeout(function () {
        if (self.readyState === 2) return;
        ends.forEach(function (fn) { fn({ data: JSON.stringify({ status: "done" }) }); });
      }, Math.max(0, (lastT(d) - off) * 1000) + 300));
    }).catch(function () { self.readyState = 2; if (self.onerror) self.onerror({}); });
  }
  FakeEventSource.CLOSED = 2;
  window.EventSource = FakeEventSource;
})();
