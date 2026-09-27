#!/usr/bin/env node
// Reusable layout measurement for the frontier page: header row sharing,
// column widths across breakpoints, timeline grid shape, section gaps, and
// empty blocks between two landmarks. Replaces ad-hoc one-off probes —
// every visual-layout investigation runs through here so the method stays
// consistent and re-runnable.
// Usage:
//   node scripts/frontier-measure-layout.mjs [--url URL] [--widths 1400,900,400]
//     [--market US-NE-BROOKLYN] [--season October] [--preview]
//     [--checks header,widths,timeline,gaps,empties] [--between #a,#b]
import { chromium } from "playwright";

const raw = process.argv.slice(2);
const args = {};
for (let i = 0; i < raw.length; i++) {
  const m = raw[i].match(/^--([^=]+)(?:=(.*))?$/);
  if (m && m[2] !== undefined) args[m[1]] = m[2];
  else if (m && raw[i + 1] && !raw[i + 1].startsWith("--")) args[m[1]] = raw[++i];
  else if (m) args[m[1]] = true;
}

const url = args.url || "https://kodiak-dev.bryanchasko.com/";
const widths = String(args.widths || "1366").split(",").map(Number);
const checks = String(args.checks || "header,widths,timeline").split(",");
const between = String(args.between || "").split(",").filter(Boolean);

const BOX_FN = `(selector) => {
  const el = document.querySelector(selector);
  if (!el) return null;
  const rect = el.getBoundingClientRect();
  return { top: Math.round(rect.top), bottom: Math.round(rect.bottom),
    left: Math.round(rect.left), right: Math.round(rect.right),
    w: Math.round(rect.width), h: Math.round(rect.height) };
}`;

const report = {};
const browser = await chromium.launch();
for (const width of widths) {
  const page = await browser.newPage({ viewport: { width, height: 900 } });
  await page.goto(url, { waitUntil: "load", timeout: 60000 });
  try {
    await page.fill("#kodiak-gate input", "cakes", { timeout: 5000 });
    await page.click("#kodiak-gate button", { timeout: 5000 });
  } catch (_) {}
  await page.waitForTimeout(1500);
  if (args.market || args.season) {
    await page.evaluate(
      ([market, season]) => {
        const loc = document.getElementById("locality");
        if (market && loc) {
          loc.value = market;
          loc.dispatchEvent(new Event("change", { bubbles: true }));
        }
        const sea = document.getElementById("seasonalSelect");
        if (season && sea) {
          sea.value = season;
          sea.dispatchEvent(new Event("change", { bubbles: true }));
          window.__activeSeason = season;
        }
      },
      [args.market || null, args.season || null],
    );
    await page.waitForTimeout(1000);
  }
  if (args.preview) {
    await page.click("#generateCampaign");
    let ready = false;
    for (let i = 0; i < 40 && !ready; i++) {
      await page.waitForTimeout(15000);
      ready = await page.evaluate(() => !!document.getElementById("ffLiveTrack"));
    }
    if (!ready) {
      report[width] = { error: "preview never landed" };
      await page.close();
      continue;
    }
    await page.waitForTimeout(8000);
  }
  const row = {};
  if (checks.includes("widths")) {
    row.widths = await page.evaluate((boxSrc) => {
      const measure = new Function(`return (${boxSrc})`)();
      const out = {};
      for (const sel of [
        ".kodiak-header .header__inner",
        ".kodiak-header .kodiak-headline-plate",
        "#progressTimeline",
        ".wrap",
        ".wrap > .card",
      ]) out[sel] = measure(sel)?.w ?? null;
      return out;
    }, BOX_FN);
  }
  if (checks.includes("header")) {
    row.header = await page.evaluate((boxSrc) => {
      const measure = new Function(`return (${boxSrc})`)();
      const logos = measure(".kodiak-header__logos");
      const plate = measure(".kodiak-header .kodiak-headline-plate");
      const sharesRow =
        !!logos && !!plate
          ? plate.top < logos.bottom - 2 &&
            plate.bottom > logos.top + 2 &&
            plate.left >= logos.right - 1
          : false;
      return { logos, plate, sharesRow };
    }, BOX_FN);
  }
  if (checks.includes("timeline")) {
    row.timeline = await page.evaluate(() => {
      const strip = document.querySelector("#progressTimeline");
      const tops = [...document.querySelectorAll("#progressTimeline .ff-timeline-steps > li")].map(
        (step) => Math.round(step.getBoundingClientRect().top),
      );
      return { h: strip ? Math.round(strip.getBoundingClientRect().height) : null, stepTops: tops };
    });
  }
  if (checks.includes("gaps")) {
    row.gaps = await page.evaluate(() => {
      const kids = [...document.querySelectorAll(".wrap > *, #progressTimeline")]
        .filter((el) => el.getBoundingClientRect().height > 0)
        .sort((a, b) => a.getBoundingClientRect().top - b.getBoundingClientRect().top);
      return kids.map((el) => {
        const b = el.getBoundingClientRect();
        const style = getComputedStyle(el);
        return `${el.id ? `#${el.id}` : el.tagName.toLowerCase()}.${String(el.className).split(" ")[0]} top=${Math.round(b.top)} h=${Math.round(b.height)} mt=${style.marginTop} mb=${style.marginBottom} pt=${style.paddingTop}`;
      });
    });
  }
  if (checks.includes("empties") && between.length === 2) {
    row.empties = await page.evaluate(([fromSel, toSel]) => {
      const from = document.querySelector(fromSel);
      const to = document.querySelector(toSel);
      if (!from || !to) return { error: "landmarks missing" };
      const fb = from.getBoundingClientRect();
      const tb = to.getBoundingClientRect();
      const found = [];
      const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_ELEMENT);
      let node;
      while ((node = walker.nextNode())) {
        const b = node.getBoundingClientRect();
        if (!(b.top >= fb.bottom - 1 && b.bottom <= tb.top + 1 && b.height > 0)) continue;
        const style = getComputedStyle(node);
        if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") continue;
        if (node.closest("[hidden], details:not([open])")) continue;
        const text = (node.textContent || "").trim().replace(/\s+/g, " ");
        found.push(`${node.tagName}#${node.id || ""}.${String(node.className).split(" ")[0]} h=${Math.round(b.height)} kids=${node.children.length} text=${text.slice(0, 60) || "(empty)"}`);
        if (found.length >= 40) break;
      }
      return { gap: Math.round(tb.top - fb.bottom), found };
    }, between);
  }
  report[width] = row;
  await page.close();
}
await browser.close();
console.log(JSON.stringify(report, null, 1));
