const fs = require("fs");
const os = require("os");
const path = require("path");
const zlib = require("zlib");
const crypto = require("crypto");
const { chromium } = require("playwright");

const cfg = JSON.parse(fs.readFileSync(path.join(__dirname, "config.json"), "utf8"));
const FLOW_URL = process.env.FLOW_URL || cfg.flowUrl;
const EXT_DIR = path.resolve(__dirname, "extension", "zapi-flow");
const DL_DIR = path.resolve(__dirname, "downloads");
const RAW_DIR = path.join(DL_DIR, "raw");
const FINAL_DIR = path.join(DL_DIR, "final");
const DEBUG_DIR = path.resolve(__dirname, "debug");
const PROMPTS_FILE = path.resolve(__dirname, process.env.PROMPTS_FILE || "prompts/batch.json");
fs.mkdirSync(RAW_DIR, { recursive: true });
fs.mkdirSync(FINAL_DIR, { recursive: true });
fs.mkdirSync(DEBUG_DIR, { recursive: true });

const NL = String.fromCharCode(10);

// .json: array of strings or {prompt}. .txt: prompts separated by a blank line.
// Each prompt is flattened to ONE line because ZAPI FLOW queues one prompt per line.
function loadPrompts() {
  const text = fs.readFileSync(PROMPTS_FILE, "utf8").replace(/\r/g, "");
  let list;
  if (PROMPTS_FILE.endsWith(".txt")) list = text.split(/\n[ \t]*\n/);
  else list = JSON.parse(text).map((p) => (typeof p === "string" ? p : p.prompt));
  return list.filter(Boolean).map((p) => p.replace(/\s*\n\s*/g, " ").trim()).filter(Boolean);
}

// Accepts: Playwright storageState ({cookies:[...]}) or array, Cookie-Editor / EditThisCookie export (array).
// Base64 of plain JSON or of gzipped JSON. Never logs cookie values.
function loadCookies() {
  const b64 = (process.env.FLOW_COOKIES_B64 || "").trim();
  if (!b64) throw new Error("FLOW_COOKIES_B64 secret is missing");
  let buf = Buffer.from(b64, "base64");
  if (buf[0] === 0x1f && buf[1] === 0x8b) buf = zlib.gunzipSync(buf);
  let data;
  try { data = JSON.parse(buf.toString("utf8")); }
  catch (e) { throw new Error("FLOW_COOKIES_B64 is not valid base64 JSON (plain or gzipped)"); }
  const list = Array.isArray(data) ? data : data.cookies;
  if (!Array.isArray(list) || !list.length) throw new Error("FLOW_COOKIES_B64 contains no cookies");
  const ss = { no_restriction: "None", none: "None", lax: "Lax", strict: "Strict" };
  const out = [];
  for (const c of list) {
    if (!c || !c.name || !c.domain) continue;
    const host = String(c.domain).replace(/^\./, "");
    const secure = !!c.secure;
    let sameSite = ss[String(c.sameSite || "").toLowerCase()];
    if (sameSite === "None" && !secure) sameSite = "Lax";
    const exp = c.expires !== undefined ? c.expires : c.expirationDate;
    const cookie = { name: c.name, value: c.value === undefined ? "" : String(c.value), httpOnly: !!c.httpOnly, secure };
    if (sameSite) cookie.sameSite = sameSite;
    cookie.expires = (typeof exp === "number" && exp > 0 && !c.session) ? Math.floor(exp) : -1;
    if (c.hostOnly === true || /^__Host-/.test(c.name)) {
      cookie.url = "https://" + host + "/";
    } else {
      cookie.domain = String(c.domain);
      cookie.path = c.path || "/";
    }
    out.push(cookie);
  }
  if (!out.length) throw new Error("No usable cookies found in FLOW_COOKIES_B64");
  const names = new Set(out.map((c) => c.name));
  console.log("Cookies loaded:", out.length, "| has SID:", names.has("SID") || names.has("__Secure-1PSID"));
  return out;
}

function imgType(buf) {
  if (buf.length > 8 && buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4e && buf[3] === 0x47) return ".png";
  if (buf.length > 3 && buf[0] === 0xff && buf[1] === 0xd8 && buf[2] === 0xff) return ".jpg";
  if (buf.length > 12 && buf.toString("ascii", 0, 4) === "RIFF" && buf.toString("ascii", 8, 12) === "WEBP") return ".webp";
  return null;
}

function listFiles(dir, out) {
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) { if (full !== FINAL_DIR) listFiles(full, out); }
    else out.push(full);
  }
  return out;
}

// Collect only complete, valid images from every place Chrome may have written them (subfolders included).
function collectImages() {
  const files = [];
  listFiles(DL_DIR, files);
  listFiles(path.join(os.homedir(), "Downloads"), files);
  const seen = new Set();
  const manifest = [];
  const skipped = [];
  let n = 0;
  for (const full of files) {
    const f = path.basename(full);
    if (/\.(crdownload|tmp|part)$/i.test(f)) { skipped.push(f + " (incomplete)"); continue; }
    const buf = fs.readFileSync(full);
    const ext = imgType(buf);
    if (!ext || buf.length < 10000) { skipped.push(f + " (not a valid image / too small)"); continue; }
    const hash = crypto.createHash("sha256").update(buf).digest("hex");
    if (seen.has(hash)) continue;
    seen.add(hash);
    n += 1;
    const name = "img-" + String(n).padStart(3, "0") + ext;
    fs.copyFileSync(full, path.join(FINAL_DIR, name));
    manifest.push({ file: name, bytes: buf.length, source: full.replace(os.homedir(), "~") });
  }
  fs.writeFileSync(path.join(DEBUG_DIR, "downloads-listing.json"), JSON.stringify({ valid: manifest, skipped }, null, 2));
  console.log("Valid images:", manifest.length, "| skipped:", skipped.length);
  return manifest.length;
}

async function dumpUiText(ui, name) {
  const t = await ui.locator("body").innerText().catch(() => "");
  fs.writeFileSync(path.join(DEBUG_DIR, name), t);
  return t;
}

(async () => {
  if (!fs.existsSync(path.join(EXT_DIR, "manifest.json"))) throw new Error("ZAPI Flow extension not found in " + EXT_DIR);
  const prompts = loadPrompts();
  if (!prompts.length) throw new Error("No prompts found in " + PROMPTS_FILE);
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
    await d.saveAs(target).catch((e) => console.log("download save failed:", e.message));
    console.log("Saved", path.basename(target));
  });
  context.pages().forEach(hook);
  context.on("page", hook);

  // The ZAPI Flow side panel looks for the active tab in the current window.
  // Opened as a normal tab it would find itself, so point it at the Flow tab instead.
  await context.addInitScript(() => {
    if (!(window.chrome && chrome.tabs && chrome.tabs.query)) return;
    const orig = chrome.tabs.query.bind(chrome.tabs);
    chrome.tabs.query = function (q, cb) {
      const wantActive = q && q.active && q.currentWindow;
      const query = wantActive ? { url: ["https://labs.google/fx/*", "https://flow.google.com/*"] } : q;
      const p = orig(query).then((r) => (wantActive ? r.slice(0, 1) : r));
      if (typeof cb === "function") { p.then(cb); return; }
      return p;
    };
  });

  await context.addCookies(loadCookies());

  let extId = process.env.EXT_ID || "";
  if (!extId) {
    try {
      let sw = context.serviceWorkers()[0];
      if (!sw) sw = await context.waitForEvent("serviceworker", { timeout: 20000 });
      extId = sw.url().split("/")[2];
    } catch (e) {
      console.log("Service worker not found");
    }
  }
  if (!extId) throw new Error("Could not detect the ZAPI Flow extension id - did the extension load?");
  console.log("Extension id:", extId);

  const flow = await context.newPage();
  await flow.goto(FLOW_URL, { waitUntil: "domcontentloaded" });
  await flow.waitForTimeout(12000);
  await flow.screenshot({ path: path.join(DEBUG_DIR, "01-flow.png") });
  const fu = new URL(flow.url());
  console.log("Flow page host/path:", fu.host + fu.pathname);
  const signedOut = flow.url().includes("accounts.google.com") ||
    (await flow.getByRole("button", { name: /^sign in$/i }).count().catch(() => 0)) > 0 ||
    (await flow.getByRole("link", { name: /^sign in$/i }).count().catch(() => 0)) > 0;
  if (signedOut) throw new Error("AUTH FAILED: Google rejected or expired the restored session (new device/IP or expired cookies) - re-export cookies and update FLOW_COOKIES_B64");

  const ui = await context.newPage();
  await ui.goto("chrome-extension://" + extId + "/" + cfg.extensionPage);
  await ui.waitForTimeout(4000);
  await ui.screenshot({ path: path.join(DEBUG_DIR, "02-ui.png") });
  await dumpUiText(ui, "02-ui-text.txt");

  // ZAPI FLOW: one prompt per line
  const block = prompts.join(NL);
  await ui.locator(cfg.selectors.promptInput).fill(block);
  const echoed = await ui.locator(cfg.selectors.promptInput).inputValue();
  console.log("Prompt box lines:", echoed.split(NL).filter((s) => s.trim()).length, "of", prompts.length);
  try {
    await ui.waitForFunction((sel) => { const b = document.querySelector(sel); return b && !b.disabled; }, cfg.selectors.startButton, { timeout: 90000 });
  } catch (e) {
    await ui.screenshot({ path: path.join(DEBUG_DIR, "03-disabled.png") });
    await dumpUiText(ui, "03-disabled-text.txt");
    await flow.screenshot({ path: path.join(DEBUG_DIR, "03-flow-state.png") });
    throw new Error("Start button stayed disabled - the Flow tab must be inside an open Flow project (check repo variable FLOW_PROJECT_URL) and Agent mode must be off");
  }
  await ui.screenshot({ path: path.join(DEBUG_DIR, "03-filled.png") });
  await ui.locator(cfg.selectors.startButton).click();
  await flow.bringToFront();
  console.log("Start clicked");
  await flow.waitForTimeout(8000);
  const early = await ui.locator(cfg.selectors.status).innerText().catch(() => "");
  console.log("Status 8s after start:", early.slice(0, 200));
  await ui.screenshot({ path: path.join(DEBUG_DIR, "03b-started.png") });
  await dumpUiText(ui, "03b-started-text.txt");
  await flow.screenshot({ path: path.join(DEBUG_DIR, "03c-flow-started.png") });

  const deadline = Date.now() + cfg.timeoutMinutes * 60000;
  const doneRe = new RegExp(cfg.doneText, "i");
  const failRe = /error|failed|sign in|not logged|quota|limit/i;
  let done = false;
  let last = "";
  let tick = 0;
  while (Date.now() < deadline) {
    const txt = await ui.locator(cfg.selectors.status).innerText().catch(() => "");
    if (txt !== last) { console.log("Status:", txt.slice(0, 300)); last = txt; }
    if (doneRe.test(txt)) { done = true; break; }
    if (failRe.test(txt)) { console.log("Extension reported a problem - stopping wait"); break; }
    tick += 1;
    if (tick % 8 === 0) await flow.screenshot({ path: path.join(DEBUG_DIR, "progress-" + tick + ".png") });
    await flow.waitForTimeout(15000);
  }
  console.log("Extension finished:", done);
  await flow.screenshot({ path: path.join(DEBUG_DIR, "04-end.png") });
  await ui.screenshot({ path: path.join(DEBUG_DIR, "04-ui-end.png") });
  await dumpUiText(ui, "04-ui-end-text.txt");
  await flow.waitForTimeout(cfg.settleSeconds * 1000);
  await context.close();

  const valid = collectImages();
  console.log("RESULT expected=" + prompts.length + " valid_images=" + valid + " extension_done=" + done);
  if (!done || valid < prompts.length) process.exit(1);
})().catch((e) => { console.error(e.message || e); process.exit(1); });
