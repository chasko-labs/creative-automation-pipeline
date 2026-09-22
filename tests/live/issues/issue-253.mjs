// Issue #253 — preload hero 404: cabin-table.jpg missing, first paint broken.
// Acceptance: the #196 photographic preload resolves 200 and decodes to a
// real photo on first paint.
// Root cause was scripts/deploy-frontier.sh, not the markup: the photo is
// committed (force-added under the gitignored input_assets/ DAM dir) and
// preloaded in <head>, but the deploy DIRS set never synced input_assets/.
// This test guards the served result; the deploy include set is pinned by
// tests/vitest/deploy-asset-coverage.test.mjs.
import { assert, gotoLive } from "../lib.mjs";

const HERO = "input_assets/textless/cabin-table.jpg";

export const issue = 253;
export const title = "preload hero serves 200 and paints photographic";

export async function run(page, { baseUrl } = {}) {
  const bad = [];
  page.on("response", (r) => {
    if (r.url().includes("cabin-table.jpg") && r.status() >= 400) {
      bad.push(`${r.status()} ${r.url()}`);
    }
  });
  await gotoLive(page, baseUrl);
  await page.waitForTimeout(1500);

  const preloadHref = await page.evaluate(() => {
    const l = document.querySelector('link[rel="preload"][as="image"]');
    return l ? l.getAttribute("href") : null;
  });
  assert(preloadHref && preloadHref.split("?")[0] === HERO,
    `head preloads the committed hero (got: ${preloadHref})`);
  assert(bad.length === 0, `no hero 404s in network log (got: ${bad.join(", ") || "none"})`);

  const size = await page.evaluate((src) => new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
    img.onerror = () => resolve({ w: 0, h: 0 });
    img.src = src;
  }), HERO);
  assert(size.w > 0 && size.h > 0, `hero decodes to a photo (${size.w}x${size.h})`);
}
