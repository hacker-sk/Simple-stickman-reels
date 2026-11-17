const fs = require("fs");
const path = require("path");

// Turns OFF ONLY the ZAPI FLOW row "Include serial number in filename". Nothing else is touched
// (Auto download generated images, Character Consistency, Agent mode all stay as they are).
// How: find the row by its text, take the single toggle inside that row, click it only if it is ON, then re-read it.
// Best effort: never throws. Writes debug/02d-serial-toggle.json and a screenshot so the result is visible in the artifact.
async function rowState(ui) {
  return ui.evaluate(() => {
    const isToggle = (e) => e.matches('input[type="checkbox"], [role="switch"], [aria-checked]');
    const state = (el) => (el.type === "checkbox" ? el.checked : el.getAttribute("aria-checked") === "true");
    // smallest element whose own text is the serial number label
    const cands = [...document.querySelectorAll("body *")].filter((e) => /include serial number in filename/i.test(e.textContent || "") && (e.textContent || "").length < 80);
    if (!cands.length) return { found: false };
    const label = cands.sort((a, b) => a.textContent.length - b.textContent.length)[0];
    // walk up until the ancestor holds exactly one toggle: that is this row's switch
    let row = label;
    for (let k = 0; k < 6 && row; k++, row = row.parentElement) {
      const t = [...row.querySelectorAll('input[type="checkbox"], [role="switch"], [aria-checked]')];
      if (t.length === 1) {
        const el = t[0];
        el.setAttribute("data-serial-toggle", "1");
        return { found: true, text: label.textContent.trim(), checked: state(el), tag: el.tagName.toLowerCase(), type: el.type || "" };
      }
      if (t.length > 1) break;
    }
    // custom switch without input/aria: take the last styled child of the row
    row = label.parentElement && label.parentElement.parentElement ? label.parentElement.parentElement : label.parentElement;
    const sw = row && row.querySelector('[class*="toggle"], [class*="switch"], [class*="slider"]');
    if (sw) { sw.setAttribute("data-serial-toggle", "1"); return { found: true, text: label.textContent.trim(), checked: null, tag: "custom", type: "" }; }
    return { found: false, text: label.textContent.trim() };
  });
}

async function turnOffSerial(ui, debugDir) {
  const report = { before: null, after: null, clicked: false, error: null };
  try {
    report.before = await rowState(ui);
    if (!report.before.found) {
      console.log("Serial number option NOT found in the extension panel (see debug/02d-serial-toggle.png)");
    } else if (report.before.checked === false) {
      console.log("Serial number option already OFF");
    } else {
      // checked === true, or unknown for a custom switch (screenshot decides): click once
      await ui.locator('[data-serial-toggle="1"]').first().click({ timeout: 3000, force: true });
      report.clicked = true;
      await ui.waitForTimeout(500);
      report.after = await rowState(ui);
      const off = report.after.found && report.after.checked === false;
      console.log("Serial number option:", off ? "turned OFF" : "clicked, state now " + JSON.stringify(report.after.checked));
      // a custom switch that reports no state must not be toggled twice: leave it as clicked
    }
  } catch (e) {
    report.error = String(e && e.message).slice(0, 200);
    console.log("Serial number toggle skipped:", report.error);
  }
  try { fs.writeFileSync(path.join(debugDir, "02d-serial-toggle.json"), JSON.stringify(report, null, 2)); } catch (e) {}
  try { await ui.screenshot({ path: path.join(debugDir, "02d-serial-toggle.png") }); } catch (e) {}
  return report;
}

module.exports = { turnOffSerial };
