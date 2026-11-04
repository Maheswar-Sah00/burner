const crypto = require("crypto");
function shorten(url) { return crypto.createHash("sha256").update(url).digest("base64url").slice(0, 7); }
module.exports = { shorten };
