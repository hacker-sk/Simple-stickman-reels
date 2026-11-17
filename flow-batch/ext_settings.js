const fs = require("fs");
const path = require("path");

// Sets ONLY the ZAPI FLOW rows "Include serial number in filename" (-> OFF) and "Auto download generated images" (-> ON).
// Character Consistency, Agent mode and everything else are never touched.
// The checkbox sits outside the visible area, so Playwright's click (even with force) cannot reach it.
// Instead the change is made inside the page, trying 3 ways in turn, and the state is re-read after each one.
// Best effort: never throws. Writes debug/02d-serial-toggle.json and a screenshot.
async function rowState(ui, pattern, attr) {
  return ui.evaluate(({ pattern, attr }) => {
    const re = new RegExp(pattern, "i");
    const state = (el) => (el.type === "checkbox" ? el.checked : el.getAttribute("aria-checked") === "true");
    const cands = [...document.querySelectorAll("body *")].filter((e) => re.test(e.textContent || "") && (e.textContent || "").length < 80);
    if (!cands.length) return { found: false };
    const label = cands.sort((a, b) => a.textContent.length - b.textContent.length)[0];
    let row = label;
    for (let k = 0; k < 6 && row; k++, row = row.parentElement) {
      const t = [...row.querySelectorAll('input[type="checkbox"], [role="switch"], [aria-checked]')];
      if (t.length === 1) {
        const el = t[0];
        el.setAttribute(attr, "1");
        return { found: true, text: label.textContent.trim(), checked: state(el), tag: el.tagName.toLowerCase(), type: el.type || "" };
      }
      if (t.length > 1) break;
    }
    row = label.parentElement && label.parentElement.parentElement ? label.parentElement.parentElement : label.parentElement;
    const sw = row && row.querySelector('[class*="toggle"], [class*="switch"], [class*="slider"]');
    if (sw) { sw.setAttribute(attr, "1"); return { found: true, text: label.textContent.trim(), checked: null, tag: "custom", type: "" }; }
    return { found: false, text: label.textContent.trim() };
  }, { pattern, attr });
}

async function flip(ui, attr, method, want) {
  return ui.evaluate(({ attr, method, want }) => {
    const el = document.querySelector("[" + attr + '="1"]');
    if (!el) return false;
    if (method === 0) { el.scrollIntoView({ block: "center" }); el.click(); return true; }
    if (method === 1) {
      const l = el.closest("label") || (el.id && document.querySelector('label[for="' + el.id + '"]'));
      if (!l) return false;
      l.click();
      return true;
    }
    if (el.type !== "checkbox") return false;
    el.checked = want;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.dispatchEvent(new Event("change", { bubbles: true }));
    return true;
  }, { attr, method, want });
}

async function ensure(ui, pattern, attr, want) {
  const r = { before: null, after: null, method: null, ok: false };
  r.before = await rowState(ui, pattern, attr);
  if (!r.before.found) return r;
  if (r.before.checked === want) { r.ok = true; r.after = r.before; return r; }
  for (let m = 0; m < 3; m++) {
    const did = await flip(ui, attr, m, want).catch(() => false);
    if (!did) continue;
    await ui.waitForTimeout(500);
    r.after = await rowState(ui, pattern, attr);
    r.method = m;
    if (r.after.checked === want) { r.ok = true; break; }
    if (r.before.checked === null) break; // custom switch without readable state: never toggle twice
  }
  return r;
}

async function turnOffSerial(ui, debugDir) {
  const report = { serial: null, autoDownload: null, error: null };
  try {
    report.serial = await ensure(ui, "include serial number in filename", "data-serial-toggle", false);
    const s = report.serial;
    if (!s.before.found) console.log("Serial number option NOT found in the extension panel");
    else console.log("Serial number option:", s.ok ? "OFF (verified" + (s.method === null ? ", was already off)" : ", method " + s.method + ")") : "STILL ON after 3 methods");
    report.autoDownload = await ensure(ui, "auto download generated images", "data-autodl-toggle", true);
    const a = report.autoDownload;
    if (!a.before.found) console.log("Auto download option NOT found in the extension panel");
    else console.log("Auto download option:", a.ok ? "ON (verified)" : "could not be set ON");
  } catch (e) {
    report.error = String(e && e.message).slice(0, 200);
    console.log("Serial number toggle skipped:", report.error);
  }
  try { fs.writeFileSync(path.join(debugDir, "02d-serial-toggle.json"), JSON.stringify(report, null, 2)); } catch (e) {}
  try { await ui.screenshot({ path: path.join(debugDir, "02d-serial-toggle.png") }); } catch (e) {}
  return report;
}

module.exports = { turnOffSerial };
