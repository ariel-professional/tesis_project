const fs = require("node:fs");
const path = require("node:path");

const html = fs.readFileSync(path.join(__dirname, "../src/renderer/index.html"), "utf8");
const policy = html.match(/http-equiv="Content-Security-Policy"\s+content="([^"]+)"/);
if (!policy) throw new Error("Missing renderer Content-Security-Policy");
module.exports = policy[1];
