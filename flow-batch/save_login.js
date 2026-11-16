const { chromium } = require("playwright");
const fs = require("fs");
const zlib = require("zlib");

(async () => {
  const browser = await chromium.launch({ headless: false, channel: "chrome", ignoreDefaultArgs: ["--enable-automation"], args: ["--disable-blink-features=AutomationControlled"] });
  const context = await browser.newContext();
  const page = await context.newPage();
  await page.goto("https://labs.google/fx/tools/flow");
  console.log("Log in to Google in the opened window, wait until Flow loads, then press Enter here.");
  await new Promise((r) => process.stdin.once("data", r));
  const state = await context.storageState();
  const b64 = zlib.gzipSync(Buffer.from(JSON.stringify(state))).toString("base64");
  fs.writeFileSync("flow_cookies_b64.txt", b64);
  console.log("Saved flow_cookies_b64.txt (" + b64.length + " chars). Add its content as repo secret FLOW_COOKIES_B64.");
  await browser.close();
  process.exit(0);
})();
