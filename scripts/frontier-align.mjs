#!/usr/bin/env node
// Geometry probe for the frontier header/timeline alignment contract.
// Usage: node scripts/frontier-align.mjs --page prod --viewport-width 1440
// Prints JSON rects for the brown bar, headline plate, logo cluster,
// sticky alt logo, and progress timeline so edge alignment is checkable.
import { chromium } from "playwright";

const args = Object.fromEntries(
  process.argv.slice(2).flatMap((a, i, arr) => {
    if (!a.startsWith("--")) return [];
    const key = a.slice(2);
    const next = arr[i + 1];
    return [[key, next && !next.startsWith("--") ? next : "true"]];
  })
);

const page = args.page ?? "dev";
const vw = Number(args["viewport-width"] ?? 1440);
const url =
  args.url ??
  (page === "prod"
    ? "https://kodiak.bryanchasko.com/"
    : "https://kodiak-dev.bryanchasko.com/");

const browser = await chromium.launch();
const pg = await browser.newPage({ viewport: { width: vw, height: 900 } });
const errors = [];
pg.on("pageerror", (e) => errors.push(String(e).split("\n")[0]));
await pg.goto(url, { waitUntil: "networkidle", timeout: 60000 });
const gate = pg.getByPlaceholder(/shared word/i);
if (await gate.count()) {
  await gate.fill("cakes");
  await pg.locator("button:has-text('Enter')").click();
  await pg.waitForTimeout(2000);
}
await pg.waitForTimeout(1500);
// scrolled state: sticky secondary logo visible
if (args.expand) {
  await pg.evaluate(() => {
    document.querySelectorAll("details:not([open])").forEach((d) => {
      d.open = true;
    });
  });
  await pg.waitForTimeout(800);
}
await pg.evaluate(() => window.scrollTo(0, 1200));
await pg.waitForTimeout(800);

const r = (el) => {
  if (!el) return null;
  const b = el.getBoundingClientRect();
  const n = (v) => Math.round(v);
  return { x: n(b.x), y: n(b.y), w: n(b.width), h: n(b.height) };
};
const out = await pg.evaluate(() => {
  const q = (s) => document.querySelector(s);
  const rect = (el) => {
    if (!el) return null;
    const b = el.getBoundingClientRect();
    const n = (v) => Math.round(v);
    return { x: n(b.x), y: n(b.y), w: n(b.width), h: n(b.height) };
  };
  return {
    bar: rect(q("header.kodiak-header")),
    inner: rect(q(".kodiak-header .header__inner")),
    plate: rect(q(".kodiak-headline-plate")),
    logos: rect(q(".kodiak-header__logos")),
    stickyAlt: rect(q(".kodiak-header__logo--secondary")),
    timeline: rect(document.getElementById("progressTimeline")),
    scrolled: window.scrollY,
  };
});
out.pageErrors = errors;
out.viewport = vw;
try {
  const { mkdirSync } = await import("node:fs");
  const { resolve, dirname } = await import("node:path");
  const { fileURLToPath } = await import("node:url");
  const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
  const dir = resolve(root, "docs/qa-evidence/shots");
  mkdirSync(dir, { recursive: true });
  const shot = resolve(dir, `align-${vw}-${args.expand ? "sticky" : "load"}.png`);
  await pg.screenshot({ path: shot });
  out.shot = shot;
} catch (e) {
  out.shotError = String(e).split("\n")[0];
}
console.log(JSON.stringify(out, null, 1));
await browser.close();
