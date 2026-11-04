require("dotenv").config();
const http = require("http"), fs = require("fs"), path = require("path"), os = require("os");
const { shorten } = require("./shorten");
const db = new Map();
fs.mkdirSync(path.join(__dirname, "..", "data"), { recursive: true });
http.createServer((req, res) => {
  const u = new URL(req.url, process.env.BASE_URL);
  if (u.pathname === "/shorten") { const k = shorten(u.searchParams.get("url") || ""); db.set(k, u.searchParams.get("url")); return res.end(k); }
  res.end("ok");
}).listen(process.env.PORT, () => console.log(`listening on ${process.env.PORT} as ${os.userInfo().username}`));
