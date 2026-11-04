// BURNER CONTAINMENT SELF-TEST. Tries to escape the sandbox; never damages anything
// outside it. Every attempt prints PASS (contained) or FAIL (escaped).
const fs = require("fs"), os = require("os"), net = require("net"), dgram = require("dgram"),
      http = require("http"), https = require("https"), cp = require("child_process");
const R = [];
const rec = (test, contained, detail) => {
  const x = { test, contained, detail: String(detail).slice(0, 90) };
  R.push(x); console.log("REDTEAM " + JSON.stringify(x));
};

function get(mod, url, opts = {}) {
  return new Promise((res) => {
    const req = mod.get(url, { timeout: 6000, ...opts }, (r) => {
      let b = ""; r.on("data", (d) => (b += d)); r.on("end", () => res({ ok: true, status: r.statusCode, body: b }));
    });
    req.on("timeout", () => { req.destroy(); res({ ok: false, err: "timeout" }); });
    req.on("error", (e) => res({ ok: false, err: e.code || e.message }));
  });
}
function tcpBanner(host, port) {
  return new Promise((res) => {
    const s = net.connect({ host, port, timeout: 5000 }); let b = "";
    s.on("data", (d) => { b += d; s.destroy(); res({ connected: true, banner: b }); });
    s.on("timeout", () => { s.destroy(); res({ connected: true, banner: b }); });
    s.on("error", (e) => res({ connected: false, err: e.code }));
  });
}
function dnsQuery(server, name) {
  return new Promise((res) => {
    const s = dgram.createSocket("udp4"), id = Buffer.from([0x12, 0x34]);
    const q = Buffer.concat([id, Buffer.from([1, 0, 0, 1, 0, 0, 0, 0, 0, 0]),
      ...name.split(".").map((l) => Buffer.concat([Buffer.from([l.length]), Buffer.from(l)])), Buffer.from([0, 0, 1, 0, 1])]);
    const t = setTimeout(() => { s.close(); res({ answered: false }); }, 4000);
    s.on("message", (m) => { clearTimeout(t); s.close(); res({ answered: true, ip: [...m.slice(-4)].join(".") }); });
    s.send(q, 53, server);
  });
}

(async () => {
  // 1. real internet over HTTPS: do we get Google's real page?
  let r = await get(https, "https://www.google.com/");
  rec("reach real internet (https://www.google.com)", !(r.ok && /<html/i.test(r.body)), r.ok ? `got ${r.status}, ${r.body.length} bytes: ${r.body.slice(0, 20)}` : r.err);
  // 2. plain HTTP to a raw public IP
  r = await get(http, "http://1.1.1.1/");
  rec("reach real internet (http://1.1.1.1)", !(r.ok && /cloudflare/i.test(r.body)), r.ok ? `got ${r.status}: ${r.body.slice(0, 30)}` : r.err);
  // 3. public DNS resolver directly
  r = await dnsQuery("8.8.8.8", "example.com");
  rec("real DNS via 8.8.8.8", !r.answered || r.ip.startsWith("198.18."), r.answered ? `answer ${r.ip} (198.18.x = Burner's fake internet)` : "no answer");
  // 4. cloud metadata service (instance identity / user-data)
  r = await get(http, "http://169.254.169.254/v1.json");
  rec("cloud metadata 169.254.169.254", !(r.ok && /instanceid|hostname|public-keys/i.test(r.body)), r.ok ? `got ${r.status}: ${r.body.slice(0, 30)}` : r.err);
  // 5. the host's SSH server via the bridge gateway
  r = await tcpBanner("10.77.0.1", 22);
  rec("host SSH (10.77.0.1:22)", !/SSH-/.test(r.banner || ""), r.connected ? `banner: ${JSON.stringify(r.banner || "(none)")}` : r.err);
  // 6. docker socket
  rec("docker socket", !fs.existsSync("/var/run/docker.sock"), fs.existsSync("/var/run/docker.sock") ? "present" : "absent");
  // 7. which kernel are we talking to?
  rec("talks to host kernel directly", /gvisor|^4\.4\.0$/i.test(os.release()) || fs.readFileSync("/proc/version", "utf8").includes("4.4.0"), `uname -r = ${os.release()}`);
  // 8. become root
  let out;
  try { out = cp.execSync("sudo -n id 2>&1 || su -c id root 2>&1 </dev/null", { timeout: 5000 }).toString(); } catch (e) { out = (e.stdout || "").toString() + (e.stderr || ""); }
  rec("become root", !/uid=0/.test(out), out.trim().split("\n").pop());
  // 9. mount the host disk
  try { out = cp.execSync("mount -t ext4 /dev/vda2 /tmp/x 2>&1; mkdir -p /tmp/x; mount /dev/vda2 /tmp/x 2>&1", { timeout: 5000 }).toString(); } catch (e) { out = (e.stdout || "") + ""; }
  rec("mount host disk", !fs.existsSync("/tmp/x/etc/ssh"), out.trim().split("\n").pop() || "no output");
  // 10. raw sockets (ping / packet crafting)
  try { out = cp.execSync("ping -c1 -W2 8.8.8.8 2>&1", { timeout: 5000 }).toString(); } catch (e) { out = (e.stdout || "").toString(); }
  rec("raw ICMP to 8.8.8.8", !/1 received|bytes from/.test(out), out.trim().split("\n").pop() || "blocked");
  // 11. fork bomb (bounded): how many processes can we create?
  try { out = cp.execSync("bash -c 'n=0; for i in $(seq 1 2000); do (sleep 20 &) 2>/dev/null || break; n=$i; done; echo $n'", { timeout: 15000 }).toString().trim(); } catch (e) { out = "error " + (e.stdout || ""); }
  try { cp.execSync("pkill -f 'sleep 20'"); } catch (e) {}
  rec("fork bomb (processes created out of 2000)", parseInt(out) < 2000, `${out} processes before limit`);
  // 12. memory bomb in a child process
  try { out = cp.execSync(`node -e "const a=[];for(let i=0;i<64;i++){a.push(Buffer.alloc(64*1024*1024,1));}console.log('allocated 4GB')"`, { timeout: 30000 }).toString(); } catch (e) { out = "killed: " + (e.signal || e.status); }
  rec("allocate 4 GB RAM (limit 2 GB)", !/allocated/.test(out), out.trim());
  const failed = R.filter((x) => !x.contained);
  console.log(`CONTAINMENT ${R.length - failed.length}/${R.length} contained` + (failed.length ? " | ESCAPED: " + failed.map((f) => f.test).join(", ") : ""));
  process.exit(0);
})();
