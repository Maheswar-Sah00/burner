// Burner Verified page: who owns the repo (GitHub's own data) + what Burner saw for this exact commit, with the
// Ed25519 signature checked in the browser. Every string from GitHub or a repo is written with textContent.
(function () {
  "use strict";
  var m = location.pathname.match(/^\/v\/github\.com\/([^/]+)\/([^/]+?)\/?$/);
  if (!m) return;
  var owner = decodeURIComponent(m[1]), name = decodeURIComponent(m[2]);
  var wanted = new URLSearchParams(location.search).get("commit");
  var ORIGIN = location.origin;
  var $ = function (id) { return document.getElementById(id); };

  function text(id, s, cls) {
    var el = $(id);
    el.textContent = s == null ? "" : String(s);
    if (cls) el.className = el.className.replace(/\bis-\w+\b/g, "").trim() + " " + cls;
  }
  function fact(dl, k, v, cls) {
    if (v == null || v === "") return;
    var dt = document.createElement("dt"), dd = document.createElement("dd");
    dt.textContent = k; dd.textContent = String(v);
    if (cls) dd.className = cls;
    dl.appendChild(dt); dl.appendChild(dd);
  }
  function short(sha) { return (sha || "").slice(0, 7); }
  function day(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    return isNaN(d) ? String(iso) : d.toLocaleString(undefined, { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }
  function ago(days) {
    if (days == null) return null;
    if (days < 60) return days + " days ago";
    if (days < 730) return Math.round(days / 30) + " months ago";
    return Math.round(days / 365) + " years ago";
  }
  function domain(site) { return (site || "").replace(/^https?:\/\/(www\.)?/, "").replace(/\/.*$/, ""); }
  function link(label, href, solid) {
    var a = document.createElement("a");
    a.className = "vf-btn" + (solid ? " solid" : "");
    a.textContent = label; a.href = href; a.rel = "noopener noreferrer";
    return a;
  }

  // The exact bytes Python signs: json.dumps(sort_keys=True, separators=(",", ":"), ensure_ascii=False)
  function canon(v) {
    if (Array.isArray(v)) return "[" + v.map(canon).join(",") + "]";
    if (v && typeof v === "object") {
      return "{" + Object.keys(v).sort().map(function (k) { return JSON.stringify(k) + ":" + canon(v[k]); }).join(",") + "}";
    }
    return JSON.stringify(v);
  }
  function b64(s) { var b = atob(s), u = new Uint8Array(b.length); for (var i = 0; i < b.length; i++) u[i] = b.charCodeAt(i); return u; }
  function checkSig(env, pub) {
    if (!(window.crypto && crypto.subtle)) return Promise.resolve(null);
    return crypto.subtle.importKey("raw", b64(pub), { name: "Ed25519" }, false, ["verify"])
      .then(function (key) { return crypto.subtle.verify({ name: "Ed25519" }, key, b64(env.signature), new TextEncoder().encode(canon(env.statement))); })
      .catch(function () { return null; });
  }

  var repoUrl = "https://github.com/" + owner + "/" + name;
  $("repo-link").href = repoUrl;
  $("repo-link").textContent = "github.com/" + owner + "/" + name;
  text("who-h", owner);
  document.title = "Burner Verified · " + owner + "/" + name;

  var badgeMd = "[![Burner Verified](" + ORIGIN + "/badge/github.com/" + owner + "/" + name + ".svg)](" + ORIGIN + "/v/github.com/" + owner + "/" + name + ")";
  $("snip-badge").textContent = badgeMd;
  $("snip-action").textContent = [
    "name: Burner",
    "on:",
    "  push:",
    "    branches: [main]",
    "  pull_request:",
    "permissions:",
    "  contents: read",
    "  issues: write",
    "  pull-requests: write",
    "jobs:",
    "  burn:",
    "    runs-on: ubuntu-latest",
    "    steps:",
    "      - uses: Maheswar-Sah00/burner@main",
  ].join("\n");
  document.querySelectorAll("[data-copy]").forEach(function (b) {
    b.addEventListener("click", function () {
      var t = $(b.getAttribute("data-copy")).textContent;
      (navigator.clipboard ? navigator.clipboard.writeText(t) : Promise.reject()).then(function () {
        b.textContent = "Copied"; setTimeout(function () { b.textContent = "Copy"; }, 1400);
      }).catch(function () { b.textContent = "Select and copy"; });
    });
  });

  function renderOwner(o, summary) {
    var dl = $("owner-facts");
    var nm = o.name || o.login;
    text("who-h", nm);
    if (o.kind === "organisation" && o.verified) {
      text("owner-state", "✓ Verified organisation", "is-ok");
      text("owner-line", nm + " owns this repo on GitHub, and GitHub has verified that it controls " + (domain(o.site) || "its website") + ".");
    } else if (o.kind === "organisation") {
      text("owner-state", "Organisation, not verified", "is-warn");
      text("owner-line", "GitHub hasn't verified this organisation's domain. Check that the recruiter's email matches " + (domain(o.site) || "the company's real website") + ".");
    } else if (o.kind === "personal account") {
      text("owner-state", "Personal account", "is-bad");
      text("owner-line", "This repo belongs to a personal GitHub account (" + o.login + "), not a company organisation. Ask the recruiter why their company's take-home isn't under the company.");
    } else {
      text("owner-state", "Unknown owner", "is-dim");
      text("owner-line", o.error || "Couldn't ask GitHub right now.");
    }
    fact(dl, "Owner", o.login);
    fact(dl, "Type", summary);
    fact(dl, "Website", o.site ? domain(o.site) : null);
    fact(dl, "Account", ago(o.age_days) ? "created " + ago(o.age_days) : null, o.age_days != null && o.age_days < 180 ? "is-bad" : "");
    fact(dl, "Public repos", o.public_repos);
  }

  var STATES = {
    clean: ["BURNED CLEAN", "is-ok"], malicious: ["MALICIOUS", "is-bad"], suspicious: ["SUSPICIOUS", "is-warn"],
    inconclusive: ["INCONCLUSIVE", "is-dim"], changed: ["CHANGED SINCE BURN", "is-warn"],
    none: ["NOT BURNED YET", "is-dim"], gone: ["UNREACHABLE", "is-dim"],
  };

  function renderBurn(d) {
    var st = d.state || {}, env = d.envelope, s = env && env.statement;
    var key = wanted && s ? s.result : st.state;
    var look = STATES[key] || STATES.none;
    text("burn-state", look[0], look[1]);
    var acts = $("burn-actions"), dl = $("burn-facts");
    if (s) {
      var b = s.burn || {}, vm = b.vm || {};
      var line = {
        clean: "Burner ran this exact commit the way a candidate would, in a throwaway Vultr VM holding " + b.fake_secrets_planted + " fake secrets. Nothing malicious happened, and the VM was deleted.",
        malicious: "Don't run it. When Burner ran this commit, " + b.fake_secrets_sent + " fake secrets were sent out. " + (s.headline || "").replace(/^Don't run this\.\s*/, ""),
        suspicious: "Burner saw risky behaviour in this commit. " + (s.headline || ""),
        inconclusive: "Burner couldn't run enough of this commit to say. " + (s.headline || ""),
      }[s.result] || "";
      if (!wanted && st.state === "changed") {
        line = "The default branch is now at " + short(st.head) + ", which Burner hasn't burned. The last burn covered " + short(s.subject.commit) + " (" + s.result + "). Burn the new commit before you run it.";
      } else if (wanted && st.head && st.head !== s.subject.commit) {
        line += " Note: the default branch has moved on since (now " + short(st.head) + ").";
      }
      text("burn-line", line);
      fact(dl, "Commit", short(s.subject.commit) + (s.subject.branch ? " on " + s.subject.branch : ""));
      fact(dl, "Burned", day(s.issued_at));
      fact(dl, "Ran", (b.ran || []).map(function (r) { return r.name; }).join(" → "));
      fact(dl, "App started", b.app_started ? "yes" : "no");
      fact(dl, "Fake secrets", b.fake_secrets_planted + " planted · " + b.fake_secrets_sent + " sent out", b.fake_secrets_sent ? "is-bad" : "is-ok");
      fact(dl, "Vultr VM", [vm.plan, vm.region, vm.alive_secs != null ? "alive " + vm.alive_secs + " s" : null].filter(Boolean).join(" · "));
      fact(dl, "Deleted", vm.deleted ? "yes · Vultr API 404 at " + day(vm.deleted_confirmed_at) : "not confirmed", vm.deleted ? "is-ok" : "is-warn");
      if (b.report) acts.appendChild(link("Full report", b.report.replace(/^https?:\/\/[^/]+/, ""), true));
    } else {
      text("burn-line", st.state === "gone" ? "The repo can't be reached: it may have been deleted or made private."
        : "Burner has no statement for this repo yet. Burn it before you run it: it takes about two minutes.");
    }
    acts.appendChild(link(s && st.state !== "changed" ? "Burn it again" : "Burn it now", "/github.com/" + owner + "/" + name, !s));
  }

  function renderSig(d) {
    var env = d.envelope;
    if (!env) {
      $("sig-dot").className = "vf-dot";
      text("sig-title", "No signed statement to check yet");
      text("sig-sub", "Burner's public key: " + ORIGIN + "/.well-known/burner-attest.pub (key " + d.key_id + ")");
      $("raw").textContent = "—";
      return;
    }
    $("raw").textContent = JSON.stringify(env, null, 2);
    checkSig(env, d.public_key).then(function (ok) {
      var good = ok === true || (ok === null && d.signature_ok);
      $("sig-dot").className = "vf-dot " + (good ? "ok" : "bad");
      text("sig-title", ok === true ? "Valid Ed25519 signature, checked in your browser"
        : ok === null && d.signature_ok ? "Valid Ed25519 signature (checked by Burner's server; this browser can't check Ed25519 itself)"
        : "Signature does not match: don't trust this statement");
      text("sig-sub", "Signed by Burner key " + env.key_id + " · public key at " + ORIGIN + "/.well-known/burner-attest.pub");
    });
  }

  function renderHist(h) {
    var ol = $("hist");
    ol.textContent = "";
    if (!h.length) { var li = document.createElement("li"); li.className = "vf-muted"; li.textContent = "No burns yet."; ol.appendChild(li); return; }
    h.slice(0, 12).forEach(function (x) {
      var li = document.createElement("li");
      var chip = document.createElement("span"); chip.className = "chip " + x.result; chip.textContent = x.result;
      var c = document.createElement("a"); c.className = "mono"; c.textContent = short(x.commit) + (x.branch ? " · " + x.branch : "");
      c.href = "/v/github.com/" + owner + "/" + name + "?commit=" + x.commit;
      var when = document.createElement("span"); when.className = "when vf-muted"; when.textContent = day(x.issued_at);
      var rep = document.createElement("a"); rep.className = "rep"; rep.textContent = "report"; rep.href = "/r/" + x.scan_id;
      li.appendChild(chip); li.appendChild(c); li.appendChild(when); li.appendChild(rep);
      ol.appendChild(li);
    });
  }

  fetch("/api/attest/github.com/" + encodeURIComponent(owner) + "/" + encodeURIComponent(name) + (wanted ? "?commit=" + encodeURIComponent(wanted) : ""))
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (d) { renderOwner(d.owner || {}, d.owner_summary); renderBurn(d); renderSig(d); renderHist(d.history || []); })
    .catch(function (e) {
      text("owner-state", "Couldn't load", "is-dim"); text("burn-state", "—", "is-dim");
      text("burn-line", "Burner couldn't load this check (" + e.message + "). Try again in a minute.");
    });
})();
