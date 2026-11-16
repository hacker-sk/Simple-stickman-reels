"use strict";

// Pure helpers for the Flow batch. No browser and no file system in here.

// ZAPI FLOW finishing message, e.g. "Done — 3 succeeded, 2 failed" (dash may be em/en/hyphen/colon).
const DONE_RE = /done\s*[\u2014\u2013:-]*\s*(\d+)\s*succeeded(?:\s*[,;]?\s*(\d+)\s*failed)?/i;

function parseDoneMessage(text) {
  const m = DONE_RE.exec(String(text || ""));
  if (!m) return null;
  const succeeded = parseInt(m[1], 10);
  const failed = m[2] === undefined ? 0 : parseInt(m[2], 10);
  return { succeeded, failed, total: succeeded + failed };
}

const TERMINAL = ["GENERATION_COMPLETED", "GENERATION_FAILED"];

// True when every queue row has reached a final state and the row count equals the number of prompts submitted.
function queueFinished(rows, expected) {
  return Array.isArray(rows) && rows.length === expected && rows.length > 0 && rows.every((r) => TERMINAL.indexOf(r.state) !== -1);
}

// The queue is complete only when ALL submitted prompts are accounted for.
// One failed prompt (or a message that counts fewer prompts than were submitted) never ends the wait.
function isQueueComplete(i) {
  if (i.doneMsg && i.doneMsg.total === i.expected) return { complete: true, via: "done-message" };
  if (queueFinished(i.rows, i.expected)) return { complete: true, via: "queue-rows" };
  return { complete: false, via: "" };
}

// More images than prompts * images-per-prompt means Flow (or the extension) generated extras.
function detectOverGeneration(i) {
  const extra = Math.max(0, (i.found || 0) - (i.expected || 0));
  return { over: extra > 0, extra };
}

// SUCCESS: everything verified, nothing failed, exact image count.
// PARTIAL_SUCCESS: at least one usable image but something was off (reasons say what).
// FAILED: no usable image.
function computeBatchStatus(i) {
  if (!(i.imagesAccepted > 0)) return { status: "FAILED", reasons: ["no usable images were produced"] };
  const reasons = [];
  if (i.failedPrompts > 0) reasons.push(i.failedPrompts + " prompt(s) failed");
  if (i.unfinishedPrompts > 0) reasons.push(i.unfinishedPrompts + " prompt(s) did not finish");
  if (i.imagesAccepted < i.expectedImages) reasons.push("only " + i.imagesAccepted + " of " + i.expectedImages + " expected images kept");
  if (i.imagesWrongRatio > 0) reasons.push(i.imagesWrongRatio + " image(s) had the wrong ratio");
  if (i.overGenerated) reasons.push(i.extraImages + " extra image(s) beyond what was requested");
  if (!i.extensionDone) reasons.push("queue completion was not confirmed");
  if (!i.settingsVerified) reasons.push("Flow settings were not verified");
  return { status: reasons.length ? "PARTIAL_SUCCESS" : "SUCCESS", reasons };
}

function normModel(s) { return String(s || "").trim().toLowerCase().replace(/\s+/g, " "); }

// Loose match: every word of `want` appears in order inside `name`, so "Nano Banana Lite" matches "Nano Banana 2 Lite".
function modelMatches(want, name) {
  const toks = normModel(want).split(" ").filter(Boolean);
  if (!toks.length) return false;
  const hay = normModel(name);
  let pos = 0;
  for (const t of toks) {
    const j = hay.indexOf(t, pos);
    if (j < 0) return false;
    pos = j + t.length;
  }
  return true;
}

function validateModel(want, allowed) {
  if (!normModel(want)) return { ok: false, reason: "model name is empty" };
  if (!Array.isArray(allowed) || !allowed.length) return { ok: true, skipped: true };
  const hit = allowed.find((a) => modelMatches(want, a));
  if (hit) return { ok: true, matched: hit };
  return { ok: false, reason: "'" + want + "' is not a known model. Allowed: " + allowed.join(", ") + " (edit allowedModels in config.json if Flow added a new one)" };
}

// Keeps the descriptive name ZAPI FLOW gave the file. Strips the capture timestamp prefix, removes characters that are
// unsafe in file names, keeps the real image extension, and adds -2, -3 ... only when two files would collide.
function uniqueName(raw, ext, used) {
  let base = String(raw || "").replace(/^\d{10,}-/, "");
  base = base.replace(/[\\/:*?"<>|\u0000-\u001f]/g, "_").replace(/\s+/g, " ").trim();
  base = base.replace(/\.(png|jpe?g|webp|gif)$/i, "");
  let stem = base.slice(0, 120).replace(/[. ]+$/, "");
  if (!stem) stem = "image";
  let name = stem + ext;
  let n = 1;
  while (used.has(name.toLowerCase())) { n += 1; name = stem + "-" + n + ext; }
  used.add(name.toLowerCase());
  return name;
}

module.exports = { parseDoneMessage, queueFinished, isQueueComplete, detectOverGeneration, computeBatchStatus, modelMatches, validateModel, uniqueName };
