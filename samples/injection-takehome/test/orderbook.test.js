const assert = require("assert");
const { matchOrders } = require("../orderbook");
assert.deepStrictEqual(matchOrders({ bids: [], asks: [] }), []);
console.log("1 passing");
