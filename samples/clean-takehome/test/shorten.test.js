const assert = require("assert"); const { shorten } = require("../src/shorten");
assert.strictEqual(shorten("https://example.com").length, 7); console.log("1 passing");
