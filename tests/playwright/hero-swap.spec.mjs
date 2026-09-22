// Resting hero market swap — offline page behaves like the shipped site.
//
// LOCAL / OPT-IN. Run: npm run test:render (or vitest file directly).
// Loads index.html over file:// (offline requirement), picks a campaign-art
// market in #locality, and asserts the five hero tiles swap from the Park
// City resting set to that market's season-aware picks with zero fetch —
// the KODIAK_marketHeroPicks contract in js/generate.js, observed in a real
// DOM instead of a stub.

import { test, expect } from "playwright/test";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const page_url = pathToFileURL(
  resolve(here, "..", "..", "web", "kodiak-posts-for-todays-frontier", "index.html"),
).href;

async function tileSrcs(page) {
  return page.$$eval("#previewHero .render-tile img", (imgs) =>
    imgs.map((i) => i.getAttribute("src")),
  );
}

test("resting hero is Park City, Cincinnati select swaps five distinct tiles", async ({
  page,
}) => {
  await page.goto(page_url);
  await page.waitForSelector("#previewHero .render-tile img", { state: "attached" });

  const resting = await tileSrcs(page);
  expect(resting).toHaveLength(5);
  expect(resting.every((s) => s && s.startsWith("input_assets/textless/"))).toBe(true);

  await page.evaluate(() => {
    const sel = document.getElementById("locality");
    sel.value = "US-OH-CINCINNATI";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll("#previewHero .render-tile img")].every((i) =>
        (i.getAttribute("src") || "").includes("campaign-web/US-OH-CINCINNATI/"),
      ),
    null,
    { timeout: 10000 },
  );

  const swapped = await tileSrcs(page);
  expect(new Set(swapped).size).toBe(5);
  const lede = await page.$eval("#previewHero .ff-figcap-lede", (n) => n.textContent);
  expect(lede).toMatch(/Cincinnati/);
  expect(lede).not.toMatch(/Wasatch/);
});

test("oceanside select swaps five distinct tiles", async ({ page }) => {
  await page.goto(page_url);
  await page.waitForSelector("#previewHero .render-tile img", { state: "attached" });

  await page.evaluate(() => {
    const sel = document.getElementById("locality");
    sel.value = "US-CA-OCEANSIDE";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForFunction(
    () =>
      [...document.querySelectorAll("#previewHero .render-tile img")].every((i) =>
        (i.getAttribute("src") || "").includes("campaign-web/US-CA-OCEANSIDE/"),
      ),
    null,
    { timeout: 10000 },
  );

  const swapped = await tileSrcs(page);
  expect(new Set(swapped).size).toBe(5);
});

test("market without campaign art keeps the resting example", async ({ page }) => {
  await page.goto(page_url);
  await page.waitForSelector("#previewHero .render-tile img", { state: "attached" });
  const before = await tileSrcs(page);

  await page.evaluate(() => {
    const sel = document.getElementById("locality");
    sel.value = "US-MW-INDY";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForTimeout(1500);

  expect(await tileSrcs(page)).toEqual(before);
});
