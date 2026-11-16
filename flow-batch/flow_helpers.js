const fs = require("fs");
const path = require("path");

const ROLES = ["button", "menuitem", "option", "tab", "radio", "menuitemradio", "switch", "checkbox"];
const LAYER_SEL = '[role="dialog"],[role="menu"],[role="listbox"],[popover],[data-radix-popper-content-wrapper],.mdc-menu-surface';

function esc(s) { return String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&"); }

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

async function composerChip(pg) {
  const b = pg.getByRole("button", { name: /nano banana|imagen|banana|veo|omni/i });
  if ((await b.count().catch(() => 0)) > 0) return b.last();
  const t = pg.getByText(/nano banana|imagen|veo/i);
  if ((await t.count().catch(() => 0)) > 0) return t.last();
  return null;
}

// Best-effort: Agent off, model, aspect, count. Never throws. Reports what it could and could not verify.
async function applyFlowSettings(pg, want, debugDir) {
  const res = { want, steps: [], verified: false };
  const note = (s) => { res.steps.push(s); console.log("Settings:", s); };
  try {
    const chip = await composerChip(pg);
    if (!chip) { note("composer settings chip not found (is the Flow project open?)"); return res; }
    res.chipBefore = (await chip.innerText().catch(() => "")).replace(/\s+/g, " ").trim();
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

    await chip.click({ timeout: 3000 });
    await pg.waitForTimeout(900);
    fs.writeFileSync(path.join(debugDir, "02b-settings-popover-text.txt"), await layerText(pg));
    await pg.screenshot({ path: path.join(debugDir, "02b-settings-open.png") }).catch(() => {});
    const scope = () => pg.locator(LAYER_SEL).last();
    const sc = async () => ((await pg.locator(LAYER_SEL).count().catch(() => 0)) > 0 ? scope() : pg);

    const modelRe = new RegExp(esc(want.model), "i");
    if (!modelRe.test(res.chipBefore)) {
      let r = await tryClick(await sc(), modelRe);
      if (!r) { await tryClick(await sc(), /model/i); await pg.waitForTimeout(700); r = await tryClick(await sc(), modelRe); }
      note("model click: " + r);
    } else note("model already " + want.model);
    if (want.aspect === "portrait") note("portrait click: " + (await tryClick(await sc(), /9\s*:\s*16|portrait/i)));
    note("count click: " + (await tryClick(await sc(), new RegExp("^\\s*x?" + want.count + "\\s*$", "i"))));

    await pg.keyboard.press("Escape").catch(() => {});
    await pg.waitForTimeout(700);
    const chip2 = await composerChip(pg);
    res.chipAfter = chip2 ? (await chip2.innerText().catch(() => "")).replace(/\s+/g, " ").trim() : "";
    note("chip after: " + res.chipAfter);
    res.verified = modelRe.test(res.chipAfter) && new RegExp("x\\s*" + want.count + "\\b", "i").test(res.chipAfter);
    await pg.screenshot({ path: path.join(debugDir, "02b-settings-after.png") }).catch(() => {});
  } catch (e) {
    note("settings error: " + String(e && e.message).slice(0, 200));
  }
  return res;
}

module.exports = { applyFlowSettings };
