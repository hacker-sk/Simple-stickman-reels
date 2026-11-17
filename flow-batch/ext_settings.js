const fs = require("fs");
const path = require("path");

// Turns OFF the ZAPI FLOW extension's serial-number option (the running number it adds to file names).
// Looks at every checkbox / switch in the side panel, matches the nearby label text, and unticks the ones that are ON.
// Best effort: never throws. Writes debug/02d-serial-toggle.json (what it saw and did) so the result is visible in the artifact.
const WANT_RE = /serial|numbering|sequen|counter|number (the )?(file|image|name)|file ?name.*number|prefix.*number|index/i;
const SKIP_RE = /number of|count\b|delay|retry|wait|second|max|limit|prompts?\b/i;

async function scan(ui) {
  return ui.evaluate(({ want, skip }) => {
    const wantRe = new RegExp(want, "i");
    const skipRe = new RegExp(skip, "i");
    document.querySelectorAll("details").forEach((d) => { d.open = true; });
    const els = [...document.querySelectorAll('input[type="checkbox"], [role="switch"]')];
    return els.map((el, i) => {
      const lab = el.closest("label") || (el.id && document.querySelector('label[for="' + el.id + '"]')) || el.parentElement;
      const text = String((lab && lab.innerText) || el.getAttribute("aria-label") || el.id || el.name || "").replace(/\s+/g, " ").trim().slice(0, 120);
      const checked = el.type === "checkbox" ? el.checked : el.getAttribute("aria-checked") === "true";
      return { i, text, id: el.id || "", checked, match: wantRe.test(text + " " + el.id + " " + (el.name || "")) && !skipRe.test(text) };
    });
  }, { want: WANT_RE.source, skip: SKIP_RE.source });
}

async function turnOffSerial(ui, debugDir) {
  const report = { found: [], changed: [], error: null };
  try {
    let list = await scan(ui);
    if (!list.some((c) => c.match)) {
      // the option may sit in a collapsed section: open the settings headers and look again
      for (const re of [/generation settings/i, /auto ?download/i, /settings/i, /file ?name|naming/i]) {
        await ui.getByText(re).first().click({ timeout: 1500 }).catch(() => {});
      }
      await ui.waitForTimeout(600);
      list = await scan(ui);
    }
    report.found = list;
    for (const c of list.filter((x) => x.match && x.checked)) {
      const done = await ui.evaluate((idx) => {
        const els = [...document.querySelectorAll('input[type="checkbox"], [role="switch"]')];
        const el = els[idx];
        if (!el) return false;
        el.click();
        return el.type === "checkbox" ? !el.checked : el.getAttribute("aria-checked") !== "true";
      }, c.i);
      report.changed.push({ text: c.text, nowOff: done });
      console.log("Extension serial number option '" + c.text + "':", done ? "turned OFF" : "click did not change it");
    }
    if (!report.changed.length) {
      const already = list.filter((x) => x.match && !x.checked);
      console.log(already.length ? "Extension serial number option already OFF: " + already.map((x) => x.text).join(" | ")
        : "Extension serial number option NOT found (see debug/02d-serial-toggle.json for every toggle seen)");
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
