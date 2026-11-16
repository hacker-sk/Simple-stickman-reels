const fs = require("fs");
const path = require("path");
const zlib = require("zlib");
const { chromium } = require("playwright");

const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, "config.json"), "utf8"));
const FLOW_URL = process.env.FLOW_URL || cfg.flowUrl;
const EXT_DIR = path.resolve(__dirname, "extension", "zapi-flow");
const DL_DIR = path.resolve(__dirname, "downloads");
const RAW_DIR = path.join(DL_DIR, "raw");
const DEBUG_DIR = path.resolve(__dirname, "debug");
const PROMPTS_FILE = path.resolve(__dirname, process.env.PROMPTS_FILE || "prompts/batch.json");
fs.mkdirSync(RAW_DIR, { recursive: true });
fs.mkdirSync(DEBUG_DIR, { recursive: true });

function loadPrompts() {
  const raw = JSON.parse(fs.readFileSync(PROMPTS_FILE, "utf8"));
  return raw.map((p) => (typeof p === "string" ? p : p.prompt)).filter(Boolean);
}

function loadCookies() {
  const b64 = process.env.FLOW_COOKIES_B64;
  if (!b64) throw new Error("FLOW_COOKIES_B64 secret is missing");
  const state = JSON.parse(zlib.gunzipSync(Buffer.from(b64, "base64")).toString("utf8"));
  return state.cookies || state;
}

function fixExtensions(dir) {
  if (!fs.existsSync(dir)) return;
  for (const f of fs.readdirSync(dir)) {
    if (path.extname(f)) continue;
    const full = path.join(dir, f);
    const head = fs.readFileSync(full).subarray(0, 12);
    let ext = ".bin";
    if (head[0] === 0x89 && head[1] === 0x50) ext = ".png";
    else if (head[0] === 0xff && head[1] === 0xd8) ext = ".jpg";
    else if (head.toString("ascii", 0, 4) === "RIFF") ext = ".webp";
    fs.renameSync(full, full + ext);
  }
}

(async () => {
  if (!fs.existsSync(path.join(EXT_DIR, "manifest.json"))) throw new Error("ZAPI Flow extension not found in " + EXT_DIR);
  const prompts = loadPrompts();
  console.log("Prompts loaded:", prompts.length);

  const context = await chromium.launchPersistentContext(path.join(__dirname, "profile"), {
    headless: false,
    viewport: { width: 1440, height: 900 },
    acceptDownloads: true,
    downloadsPath: RAW_DIR,
    args: ["--no-sandbox", "--disable-extensions-except=" + EXT_DIR, "--load-extension=" + EXT_DIR]
  });

  const hook = (pg) => pg.on("download", async (d) => {
    const target = path.join(DL_DIR, Date.now() + "-" + d.suggestedFilename());
    await d.saveAs(target);
    console.log("Saved", target);
  });
  context.pages().forEach(hook);
  context.on("page", hook);
  await context.addCookies(loadCookies());

  let extId = process.env.EXT_ID || "";
  if (!extId) {
    try {
      let sw = context.serviceWorkers()[0];
      if (!sw) sw = await context.waitForEvent("serviceworker", { timeout: 20000 });
      extId = sw.url().split("/")[2];
    } catch (e) {
      console.log("Could not detect extension id (set EXT_ID if the UI is a popup page)");
    }
  }
  console.log("Extension id:", extId || "unknown");

  const flow = await context.newPage();
  await flow.goto(FLOW_URL, { waitUntil: "domcontentloaded" });
  await flow.waitForTimeout(10000);
  await flow.screenshot({ path: path.join(DEBUG_DIR, "01-flow.png") });
  if (flow.url().includes("accounts.google.com")) throw new Error("Google session expired - regenerate FLOW_COOKIES_B64");

  let ui = flow;
  const visible = await flow.locator(cfg.selectors.promptInput).first().isVisible().catch(() => false);
  if (!visible && extId) {
    ui = await context.newPage();
    await ui.goto("chrome-extension://" + extId + "/" + cfg.extensionPage);
    await ui.waitForTimeout(3000);
  }
  await ui.screenshot({ path: path.join(DEBUG_DIR, "02-ui.png") });

  await ui.locator(cfg.selectors.promptInput).first().fill(prompts.join(String.fromCharCode(10)));
  await ui.screenshot({ path: path.join(DEBUG_DIR, "03-filled.png") });
  await ui.locator(cfg.selectors.startButton).first().click();
  console.log("Job started");

  const deadline = Date.now() + cfg.timeoutMinutes * 60000;
  const doneRe = new RegExp(cfg.doneText, "i");
  let done = false;
  while (Date.now() < deadline) {
    const txt = await ui.locator("body").innerText().catch(() => "");
    if (doneRe.test(txt)) { done = true; break; }
    await ui.waitForTimeout(15000);
  }
  console.log("Job finished:", done);
  await ui.screenshot({ path: path.join(DEBUG_DIR, "04-end.png") });
  await ui.waitForTimeout(cfg.settleSeconds * 1000);
  await context.close();

  fixExtensions(RAW_DIR);
  const files = fs.readdirSync(DL_DIR).length + fs.readdirSync(RAW_DIR).length;
  console.log("Files in downloads:", files);
  if (!done) process.exit(1);
})().catch((e) => { console.error(e); process.exit(1); });
