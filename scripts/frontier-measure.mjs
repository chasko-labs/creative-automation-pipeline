// frontier-measure.mjs — reusable live-page geometry probe for the frontier UI.
//
// Past the share gate, measures the load contract and header/art alignment,
// saves a screenshot for the record. No throwaway /tmp scripts: this lives
// in scripts/ and writes evidence under output/qa-shots/.
//
// Usage:
//   node scripts/frontier-measure.mjs [--url URL] [--w 1440] [--h 900]
//     [--label desk] [--scroll 0] [--out output/qa-shots]
//   Defaults target local dev: https://kodiak-dev.bryanchasko.com/index.html
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { resolve } from "node:path";

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const m = a.match(/^--([^=]+)=(.*)$/) || a.match(/^--(.+)$/);
    return m ? [m[1], m[2] ?? "1"] : [];
  }),
);
const url = args.url || "https://kodiak-dev.bryanchasko.com/index.html";
const w = Number(args.w || 1440);
const h = Number(args.h || 900);
const label = args.label || `${w}x${h}`;
const scrollY = Number(args.scroll || 0);
const outDir = resolve(args.out || "output/qa-shots");
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: w, height: h } });
const errors = [];
page.on("pageerror", (e) => errors.push(String(e).slice(0, 160)));
await page.goto(url, { waitUntil: "networkidle" });
const gate = page.getByPlaceholder(/shared word/i);
if (await gate.count()) {
  await gate.fill("cakes");
  await page.locator("button:has-text('Enter')").click();
  await page.waitForTimeout(2000);
}
if (scrollY) {
  await page.evaluate((s) => window.scrollTo(0, s), scrollY);
  await page.waitForTimeout(800);
}
await page.waitForTimeout(1000);
await page.screenshot({ path: `${outDir}/measure-${label}.png` });

const rect = (el) => {
  if (!el) return null;
  const b = el.getBoundingClientRect();
  const r = (n) => Math.round(n);
  return { x: r(b.x), y: r(b.y), w: r(b.width), h: r(b.height), bottom: r(b.bottom) };
};
const result = await page.evaluate(() => {
  const q = (s) => document.querySelector(s);
  const h1 = q(".kodiak-headline-plate h1");
  const html = document.body.innerHTML;
  const aboutIdx = html.indexOf('id="aboutTool"');
  // the band is a single ~1.6KB line: compare positions, not a char window.
  const bandIdx = html.lastIndexOf("ff-about-art", aboutIdx);
  const beforeAbout = bandIdx > -1 ? html.slice(bandIdx, aboutIdx) : "";
  return {
    docH: document.documentElement.scrollHeight,
    winH: window.innerHeight,
    headerH: q("header.kodiak-header")?.getBoundingClientRect().height ?? null,
    titleFont: h1 ? getComputedStyle(h1).fontSize : null,
    logoOverlapsTimeline: (() => {
      const logo = q(".kodiak-header__logos")?.getBoundingClientRect();
      const tl = document.getElementById("progressTimeline")?.getBoundingClientRect();
      if (!logo || !tl) return null;
      const xOverlap = logo.left < tl.right && logo.right > tl.left;
      return logo.bottom > tl.top && xOverlap;
    })(),
    aboutBand: beforeAbout.includes("ff-about-art"),
    aboutSvg: beforeAbout.includes("<svg"),
    aboutFlush: (() => {
      const art = q(".ff-about-art")?.getBoundingClientRect();
      const tool = document.getElementById("aboutTool")?.getBoundingClientRect();
      if (!art || !tool) return null;
      return Math.round(art.bottom) === Math.round(tool.top);
    })(),
  };
});
result.pageErrors = errors;
console.log(JSON.stringify({ label, url, ...result }));
await browser.close();
