#!/usr/bin/env node
// Drive a REAL end-to-end campaign preview the way the user does: fill the
// brief, hit Create Campaign Preview, wait for the tiles, screenshot the
// result. Evidence lands in docs/qa-evidence/shots/.
// Usage: node scripts/frontier-drive-preview.mjs [--url https://kodiak.bryanchasko.com] [--prompt "..."]
import { mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const raw = process.argv.slice(2);
const args = {};
for (let i = 0; i < raw.length; i++) {
  const m = raw[i].match(/^--([^=]+)(?:=(.*))?$/);
  if (m && m[2] !== undefined) args[m[1]] = m[2];
  else if (m && raw[i + 1] && !raw[i + 1].startsWith("--")) args[m[1]] = raw[++i];
  else if (m) args[m[1]] = true;
}
const url = args.url || "https://kodiak.bryanchasko.com/";
const prompt =
  args.prompt ||
  "the box on top of a surf board with a sunset and christmas lights and santa's sleigh in the distance";

const browser = await chromium.launch();
const pg = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
pg.on("pageerror", (e) => errors.push(String(e).split("\n")[0]));
await pg.goto(url, { waitUntil: "networkidle", timeout: 60000 });
const gate = pg.getByPlaceholder(/shared word/i);
if (await gate.count()) {
  await gate.fill("cakes");
  await pg.locator("button:has-text('Enter')").click();
  await pg.waitForTimeout(2000);
}
// fill the campaign brief.
const brief = pg.locator("#campaignBrief");
await brief.fill(prompt);
await pg.waitForTimeout(500);
// fire the preview.
await pg.locator("#generateCampaign").click();
// wait for tiles OR the honest miss card (two warm passes worst case).
await pg.waitForFunction(
  () =>
    document.querySelectorAll("#preview .render-tile img").length > 0 ||
    document.querySelector("#preview .ff-render-miss") !== null,
  null,
  { timeout: 180000 }
);
await pg.waitForTimeout(2500);
// measure AFTER scrolling into view: #preview carries content-visibility:auto,
// so geometry taken while it is below the fold reflects size containment,
// not the real layout.
await pg.evaluate(() => {
  const p = document.getElementById("preview");
  if (p) p.scrollIntoView({ block: "start" });
});
await pg.waitForTimeout(3000);
const state = await pg.evaluate(() => {
  const rect = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    const n = (v) => Math.round(v);
    return { x: n(b.x), w: n(b.width), h: n(b.height) };
  };
  return {
  tiles: document.querySelectorAll("#preview .render-tile img").length,
  liveStrip: rect(document.querySelector("#preview .ff-filmstrip")),
  liveTrack: rect(document.getElementById("ffLiveTrack")),
  liveSlot0: rect(document.querySelector("#ffLiveTrack .ff-filmstrip__slot")),
  liveFrame0: rect(document.querySelector("#ffLiveTrack .ff-filmstrip__frame")),
  previewBox: rect(document.getElementById("preview")),
  stripParent: (() => {
    const s = document.querySelector("#preview .ff-filmstrip");
    const p = s && s.parentElement;
    if (!p) return null;
    const b = p.getBoundingClientRect();
    const cs = getComputedStyle(s);
    return { tag: p.tagName + "#" + (p.id || "-") + "." + (p.className || "-"),
      x: Math.round(b.x), w: Math.round(b.width),
      stripDisplay: cs.display, stripWidth: cs.width, stripMaxWidth: cs.maxWidth,
      stripCols: cs.gridTemplateColumns, stripAreas: cs.gridTemplateAreas,
      trackMinWidth: getComputedStyle(document.getElementById("ffLiveTrack")).minWidth,
      trackDisplay: getComputedStyle(document.getElementById("ffLiveTrack")).display };
  })(),
  miss: document.querySelector("#preview .ff-render-miss") !== null,
  status: document.getElementById("generateCampaignStatus")?.textContent || null,
  badge: document.getElementById("genSourceBadge")?.textContent || null,
  copyPanel: (document.getElementById("campaignCopyPanel")?.textContent || "").slice(0, 120),
  };
});
if (args.cssprobe) {
  // bisect the narrow-live-strip: toggle containment suspects live, re-measure.
  const probe = await pg.evaluate(() => {
    const out = {};
    const measure = () => {
      const s = document.querySelector("#preview .ff-filmstrip");
      const t = document.getElementById("ffLiveTrack");
      return {
        stripW: s ? Math.round(s.getBoundingClientRect().width) : null,
        trackW: t ? Math.round(t.getBoundingClientRect().width) : null,
      };
    };
    out.base = measure();
    const pv = document.getElementById("preview");
    const cs = getComputedStyle(pv);
    out.preview = {
      rectW: Math.round(pv.getBoundingClientRect().width),
      clientW: pv.clientWidth,
      scrollW: pv.scrollWidth,
      padL: cs.paddingLeft,
      padR: cs.paddingRight,
      box: cs.boxSizing,
      display: cs.display,
    };
    return out;
  });
  console.log("CSSPROBE " + JSON.stringify(probe));
}
const dir = resolve(root, "docs/qa-evidence/shots");
mkdirSync(dir, { recursive: true });
const shot = resolve(dir, "drive-preview-prod.png");
await pg.screenshot({ path: shot, fullPage: false });
state.shot = shot;
state.pageErrors = errors;
console.log(JSON.stringify(state, null, 1));
await browser.close();
