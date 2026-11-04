// Light or dark theme. A classic script in <head>, so it runs before the page paints (no flash of the wrong theme).
// It always sets <html data-theme="light|dark">: the saved choice, else the system setting (followed live while
// nothing is saved). Stylesheets key their dark colours on :root[data-theme="dark"] inside @media screen, so
// printing stays light. window.burnerTheme: get(), set("light" | "dark"), toggle(x, y); every change fires
// "burner:theme" on document (charts.js and hero.js listen to it).
(function () {
  var KEY = "burner-theme";
  var REVEAL_MS = 480;
  var media = window.matchMedia ? window.matchMedia("(prefers-color-scheme: dark)") : null;

  function saved() {
    try {
      var v = localStorage.getItem(KEY);
      return v === "light" || v === "dark" ? v : null;
    } catch (e) { return null; }
  }
  function system() { return media && media.matches ? "dark" : "light"; }

  function apply(theme) {
    var root = document.documentElement;
    if (root.dataset.theme === theme) return;
    root.dataset.theme = theme;
    document.dispatchEvent(new CustomEvent("burner:theme", { detail: { theme: theme } }));
  }

  function set(theme) {
    try { localStorage.setItem(KEY, theme); } catch (e) { /* private window: lasts until the tab closes */ }
    apply(theme);
  }

  // The new theme grows over the old one in a circle from (x, y) (a view transition; app.css turns off the default
  // cross-fade). Without view transitions, a point, or with reduced motion, it switches at once.
  function reveal(theme, x, y) {
    var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (!document.startViewTransition || still || typeof x !== "number" || typeof y !== "number") return set(theme);
    var radius = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y));
    var at = " at " + Math.round(x) + "px " + Math.round(y) + "px)";
    var tr = document.startViewTransition(function () { set(theme); });
    tr.ready.then(function () {
      document.documentElement.animate(
        { clipPath: ["circle(0px" + at, "circle(" + Math.ceil(radius) + "px" + at] },
        { duration: REVEAL_MS, easing: "cubic-bezier(.4, 0, .2, 1)", pseudoElement: "::view-transition-new(root)" });
    }).catch(function () { /* skipped (hidden page): the theme is already set */ });
  }

  window.burnerTheme = {
    get: function () { return document.documentElement.dataset.theme === "dark" ? "dark" : "light"; },
    set: set,
    toggle: function (x, y) { reveal(window.burnerTheme.get() === "dark" ? "light" : "dark", x, y); }
  };
  // ?theme=dark|light forces a theme for this page load without saving it (screenshots, demos, links).
  var forced = null;
  try { forced = new URLSearchParams(location.search).get("theme"); } catch (e) { forced = null; }
  if (forced !== "dark" && forced !== "light") forced = null;
  apply(forced || saved() || system());
  if (media && media.addEventListener) {
    media.addEventListener("change", function () { if (!saved() && !forced) apply(system()); });
  }
})();
