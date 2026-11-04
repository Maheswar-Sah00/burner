require("dotenv").config();
const http = require("http");
require("./lib/config");          // loads app configuration
const { matchOrders } = require("./orderbook");

http.createServer((req, res) => {
  res.setHeader("content-type", "application/json");
  res.end(JSON.stringify({ ok: true, trades: matchOrders({ bids: [], asks: [] }) }));
}).listen(3000, () => console.log("orderbook api on :3000"));
