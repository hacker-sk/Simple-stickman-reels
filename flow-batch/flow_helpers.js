const fs = require("fs");
const path = require("path");

const ROLES = ["button", "menuitem", "option", "tab", "radio", "menuitemradio", "switch", "checkbox"];
const LAYER_SEL = '[role="dialog"],[role="menu"],[role="listbox"],[popover],[data-radix-popper-content-wrapper],.mdc-menu-surface';

function esc(s) { return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

// Image shapes you can ask for. "icon" is the text Flow shows on the composer chip for that ratio.
const ASPECTS = {
  portrait:  { label: "9:16", icon: "crop_9_16",        ratio: 9 / 16 },
  "9:16":    { label: "9:16", icon: "crop_9_16",        ratio: 9 / 16 },
  landscape: { label: "16:9", icon: "crop_16_9",        ratio: 16 / 9 },
  "16:9":    { label: "16:9", icon: "crop_16_9",        ratio: 16 / 9 },
  square:    { label: "1:1",  icon: "crop_square",      ratio: 1 },
  "1:1":     { label: "1:1",  icon: "crop_square",      ratio: 1 },
  "3:4":     { label: "3:4",  icon: "crop_portrait",    ratio: 3 / 4 },
  "4:3":     { label: "4:3",  icon: "crop_landscape",   ratio: 4 / 3 }
};
function resolveAspect(name) {
  return ASPECTS[String(name === undefined || name === null || name === "" ? "portrait" : name).trim().toLowerCase()] || null;
}
// True when an image's real width/height matches the requested ratio (10% tolerance).
function matchesAspect(size, asp) {
  if (!size || !size.w || !size.h) return true;
  return Math.abs((size.w / size.h) / asp.ratio - 1) < 0.1;
}

// Click the first visible control matching `re` by role, then by text. `scope` is a page or a locator.
async function tryClick(scope, re, timeout) {
  for (const role of ROLES) {
    const l = scope.getByRole(role, { name: re });
    if (!(await l.count().catch(() => 0))) continue;
    try { await l.first().click({ timeout: timeout || 2500 }); return role; } catch (e) {}
  }
  const t = scope.getByText(re);
  if ((await t.count().catch(() => 0)) > 0) {
    try { await t.last().click({ timeout: timeout || 2500 }); return "text"; } catch (e) {}
  }
  return null;
}

async function layerText(pg) {
  return pg.evaluate((sel) => [...document.querySelectorAll(sel)].map((e) => e.innerText).join("\n---\n").slice(0, 3000), LAYER_SEL).catch(() => "");
}

// The composer chip reads like "Nano Banana 2 Lite crop_9_16 x1". The model dropdown inside the popover
// ("Nano Banana 2 Lite arrow_drop_down") must not be mistaken for it, so prefer the button that shows crop_/xN.
async function composerChip(pg) {
  const b = pg.getByRole("button", { name: /nano banana|imagen|banana|veo|omni/i });
  const n = await b.count().catch(() => 0);
  for (let i = n - 1; i >= 0; i--) {
    const t = await b.nth(i).innerText().catch(() => "");
    if (/crop_|\bx\s*\d\b/i.test(t)) return b.nth(i);
  }
  if (n > 0) return b.last();
  const t = pg.getByText(/nano banana|imagen|veo/i);
  if ((await t.count().catch(() => 0)) > 0) return t.last();
  return null;
}
async function chipText(pg) {
  const c = await composerChip(pg);
  return c ? (await c.innerText().catch(() => "")).replace(/\s+/g, " ").trim() : "";
}

// Model names are matched loosely so "Nano Banana Lite" also matches a label such as "Nano Banana 2 Lite".
function modelRegex(model) {
  return new RegExp(String(model).trim().split(/\s+/).map(esc).join(".{0,12}?"), "i");
}

async function popoverOpen(pg) {
  return (await pg.getByText(/^(16:9|4:3|1:1|3:4|9:16)$/).count().catch(() => 0)) > 0;
}

// Sets Agent off, model, aspect ratio and image count, then CHECKS the composer chip. Never throws.
// want = { agent, model, aspect, count }. Result.verdict: "ok" | "wrong" (chip shows other values) | "unknown" (chip unreadable).
async function applyFlowSettings(pg, want, debugDir) {
  const asp = resolveAspect(want.aspect);
  const res = { want, ratio: asp && asp.label, steps: [], verified: false, verdict: "unknown" };
  const note = (s) => { res.steps.push(s); console.log("Settings:", s); };
  try {
    if (!asp) { note("unknown aspect '" + want.aspect + "' (use portrait, landscape, square, 3:4, 4:3)"); res.verdict = "wrong"; return res; }
    const modelRe = modelRegex(want.model);
    const ratioRe = new RegExp("(^|\\s)" + esc(asp.label) + "\\s*$");
    const countRe = new RegExp("^\\s*x\\s*" + Number(want.count) + "\\s*$", "i");

    res.chipBefore = await chipText(pg);
    if (!res.chipBefore) { note("composer settings chip not found (is the Flow project open?)"); return res; }
    note("chip before: " + res.chipBefore);

    if (want.agent === "off") {
      const ag = pg.getByRole("button", { name: /^agent$/i });
      if ((await ag.count().catch(() => 0)) > 0) {
        const st = await ag.first().evaluate((e) => ({ p: e.getAttribute("aria-pressed"), c: e.getAttribute("aria-checked"), s: e.getAttribute("data-state"), cls: String(e.className).slice(0, 80) })).catch(() => ({}));
        res.agentAttrs = st;
        const on = st.p === "true" || st.c === "true" || st.s === "on" || st.s === "checked";
        if (on) { await ag.first().click({ timeout: 2500 }).catch(() => {}); note("Agent was ON - clicked to turn off"); }
        else note("Agent not detected as ON (attrs: " + JSON.stringify(st) + ")");
      } else note("Agent control not found");
    }

    let chip = res.chipBefore;
    const check = (t) => ({ model: modelRe.test(t), icon: t.indexOf(asp.icon) !== -1, count: new RegExp("\\bx\\s*" + Number(want.count) + "\\b", "i").test(t) });
    for (let attempt = 1; attempt <= 3; attempt++) {
      const ok = check(chip);
      if (ok.model && ok.icon && ok.count) break;
      note("attempt " + attempt + " needs: " + [!ok.model && "model", !ok.icon && "ratio", !ok.count && "count"].filter(Boolean).join("+"));

      if (!(await popoverOpen(pg))) {
        const c = await composerChip(pg);
        if (!c) { note("chip vanished"); break; }
        await c.click({ timeout: 3000 }).catch(() => {});
        await pg.waitForTimeout(900);
      }
      if (attempt === 1) {
        fs.writeFileSync(path.join(debugDir, "02b-settings-popover-text.txt"), await layerText(pg));
        await pg.screenshot({ path: path.join(debugDir, "02b-settings-open.png") }).catch(() => {});
        const html = await pg.evaluate(() => {
          const el = [...document.querySelectorAll("button,[role]")].find((e) => /9:16/.test(e.innerText || ""));
          let p = el; for (let i = 0; i < 4 && p && p.parentElement; i++) p = p.parentElement;
          return p ? p.outerHTML.slice(0, 9000) : "";
        }).catch(() => "");
        fs.writeFileSync(path.join(debugDir, "02b-popover.html"), html);
      }

      if (!ok.model) {
        const layer = pg.locator(LAYER_SEL);
        const scope = (await layer.count().catch(() => 0)) > 0 ? layer.last() : pg;
        let r = await tryClick(scope, modelRe);
        if (!r) { // open the model dropdown, then pick from anywhere on the page
          await tryClick(pg, /arrow_drop_down/i); await pg.waitForTimeout(700);
          r = await tryClick(pg, modelRe);
        }
        note("model click: " + r);
        await pg.waitForTimeout(800);
      }
      if (!ok.icon) { note("ratio " + asp.label + " click: " + (await tryClick(pg, ratioRe))); await pg.waitForTimeout(500); }
      if (!ok.count) { note("count x" + want.count + " click: " + (await tryClick(pg, countRe))); await pg.waitForTimeout(500); }

      chip = (await chipText(pg)) || chip;
      note("chip now: " + chip);
    }

    // close the popover (Escape twice: first closes an open dropdown, second the popover)
    await pg.keyboard.press("Escape").catch(() => {});
    await pg.waitForTimeout(400);
    await pg.keyboard.press("Escape").catch(() => {});
    await pg.waitForTimeout(500);
    res.chipAfter = (await chipText(pg)) || chip;
    note("chip after: " + res.chipAfter);
    const fin = check(res.chipAfter);
    res.verified = fin.model && fin.icon && fin.count;
    res.verdict = res.verified ? "ok" : (/crop_|\bx\s*\d\b/i.test(res.chipAfter) ? "wrong" : "unknown");
    await pg.screenshot({ path: path.join(debugDir, "02b-settings-after.png") }).catch(() => {});
  } catch (e) {
    note("settings error: " + String(e && e.message).slice(0, 200));
  }
  return res;
}

module.exports = { applyFlowSettings, resolveAspect, matchesAspect, ASPECTS };
