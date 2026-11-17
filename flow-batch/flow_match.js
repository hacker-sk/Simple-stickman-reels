const fs = require("fs");
const path = require("path");

// Maps each submitted prompt (scene) to the Flow media UUIDs that came back for it.
// Flow names downloaded files by media UUID, so UUID-in-filename -> scene is deterministic.
// Every POST made by the browser is checked: if its payload contains one prompt's text, the UUIDs in its response belong to that prompt.
const UUID = /[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi;

function strings(v, out) {
  if (typeof v === "string") out.push(v);
  else if (Array.isArray(v)) v.forEach((x) => strings(x, out));
  else if (v && typeof v === "object") Object.values(v).forEach((x) => strings(x, out));
  return out;
}
function short(u) { try { const x = new URL(u); return x.host + x.pathname; } catch (e) { return String(u).slice(0, 80); } }

function createMediaTracker(prompts, debugDir) {
  const sets = prompts.map(() => new Set());
  const calls = [];
  const samples = [];
  let map = null;

  async function onResponse(r) {
    try {
      const req = r.request();
      if (req.method() !== "POST") return;
      const post = req.postData() || "";
      if (post.length < 20) return;
      let hay = [post];
      try { hay.push(decodeURIComponent(post.replace(/\+/g, " "))); } catch (e) {}
      try { hay = hay.concat(strings(JSON.parse(post), [])); } catch (e) {}
      let hit = [];
      prompts.forEach((p, i) => { if (p && hay.some((s) => s.indexOf(p) !== -1)) hit.push(i); });
      if (!hit.length) {
        // the extension may trim or wrap the text: fall back to the last 80 characters
        prompts.forEach((p, i) => { const t = p.slice(-80); if (t.length > 20 && hay.some((s) => s.indexOf(t) !== -1)) hit.push(i); });
      }
      if (!hit.length) return;
      const body = await r.text().catch(() => "");
      const ids = [...new Set((body.match(UUID) || []).map((x) => x.toLowerCase()))];
      if (hit.length === 1) ids.forEach((id) => sets[hit[0]].add(id));
      map = null;
      if (calls.length < 200) calls.push({ t: new Date().toISOString(), url: short(r.url()), status: r.status(), scenes: hit.map((i) => i + 1), uuids: ids.length, ambiguous: hit.length > 1 });
      if (samples.length < 4) samples.push({ url: short(r.url()), request: post.slice(0, 1500), response: body.slice(0, 2500) });
    } catch (e) {}
  }

  function build() {
    if (map) return map;
    const count = new Map();
    sets.forEach((s) => s.forEach((id) => count.set(id, (count.get(id) || 0) + 1)));
    map = new Map();
    sets.forEach((s, i) => s.forEach((id) => { if (count.get(id) === 1) map.set(id, i + 1); })); // a UUID seen under 2 prompts is ambiguous: ignore
    return map;
  }
  function hasMapping() { return build().size > 0; }
  function matchFile(name) {
    const m = build();
    const ids = (String(name).match(UUID) || []).map((x) => x.toLowerCase());
    for (const id of ids) if (m.has(id)) return { index: m.get(id), uuid: id };
    return null;
  }
  function writeDebug() {
    try {
      fs.writeFileSync(path.join(debugDir, "media-map.json"), JSON.stringify({ calls, scenes: sets.map((s, i) => ({ scene: i + 1, uuids: [...s] })) }, null, 2));
      fs.writeFileSync(path.join(debugDir, "media-samples.json"), JSON.stringify(samples, null, 2));
    } catch (e) {}
  }
  return { onResponse, hasMapping, matchFile, writeDebug, count: prompts.length };
}

module.exports = { createMediaTracker };
