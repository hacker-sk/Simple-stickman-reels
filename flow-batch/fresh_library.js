// One-time step per Flow run: create a brand-new Library (the + next to "Library" in Flow's sidebar) right after the
// project loads, before anything else. Returns false when the sidebar is not there yet (not logged in), so the caller
// can try again after the next page load; true once the step has been handled (even if it could not be confirmed).
const fs = require("fs");
const path = require("path");

const DEBUG_DIR = path.join(__dirname, "debug");

async function ensureFreshLibrary(page, h) {
  fs.mkdirSync(DEBUG_DIR, { recursive: true });
  const label = page.getByText("Library", { exact: true }).locator("visible=true").first();
  try { await label.waitFor({ state: "visible", timeout: 25000 }); }
  catch (e) { console.log("Fresh library: sidebar not visible yet, skipped for now"); return false; }

  await h.pause(1500, 3500);
  await h.wander(page);

  // The + is the right-most clickable element on the same row as the "Library" label.
  const lb = await label.boundingBox();
  const pt = lb && await page.evaluate((r) => {
    let best = null;
    for (const el of document.querySelectorAll('button,[role="button"],a')) {
      const b = el.getBoundingClientRect();
      if (!b.width || !b.height) continue;
      if (Math.abs(b.y + b.height / 2 - (r.y + r.height / 2)) > r.height) continue;
      if (b.x < r.x + r.width || b.x > r.x + 300) continue;
      if (!best || b.x > best.x) best = { x: b.x + b.width / 2, y: b.y + b.height / 2 };
    }
    return best;
  }, lb);

  if (pt) {
    await h.moveTo(page, pt.x + h.rand(-3, 3), pt.y + h.rand(-3, 3));
    await h.pause(80, 250);
    await page.mouse.down();
    await h.pause(40, 110);
    await page.mouse.up();
  } else {
    const alt = page.locator('button[aria-label*="ibrary" i]').first();
    if (!(await alt.count())) { console.log("::warning::Fresh library: + button not found, using the existing library"); return true; }
    await alt.click();
  }
  await h.pause(900, 1800);

  const name = "run-" + new Date().toISOString().replace(/[-:T]/g, "").slice(0, 12) + "-" + String(process.env.GITHUB_RUN_ID || "local").slice(-5);
  const dialog = page.locator('[role="dialog"]').locator("visible=true").first();
  const input = dialog.locator('input, textarea, [contenteditable="true"]').locator("visible=true").first();
  let named = false;
  try {
    await input.waitFor({ state: "visible", timeout: 6000 });
    await input.click();
    await h.pause(250, 600);
    await page.keyboard.press("Control+A");
    await h.type(page, name);
    await h.pause(400, 900);
    await page.keyboard.press("Enter");
    named = true;
  } catch (e) {
    console.log("Fresh library: no name field appeared, trying the dialog's confirm button / default name");
  }
  await h.pause(1200, 2200);
  // Fallback: a dialog that is still open needs its confirm button.
  if (await dialog.count()) {
    const ok = dialog.getByRole("button", { name: /create|save|done|add|ok|confirm/i }).first();
    if (await ok.count()) await ok.click().catch(() => {});
    await h.pause(1000, 2000);
  }

  let confirmed = false;
  if (named) confirmed = await page.getByText(name).first().waitFor({ state: "visible", timeout: 12000 }).then(() => true, () => false);
  await page.screenshot({ path: path.join(DEBUG_DIR, "fresh-library.png") }).catch(() => {});
  console.log("Fresh library step done | name: " + (named ? name : "default") + " | confirmed on page: " + confirmed);
  if (named && !confirmed) console.log("::warning::Fresh library name not seen on the page - check debug/fresh-library.png");
  return true;
}

module.exports = { ensureFreshLibrary };
