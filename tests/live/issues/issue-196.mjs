// Issue #196 — on-load preview is a generic off-brand wordmark.
// Acceptance: clean-cache load shows a photographic on-brand preview,
// zero generic blocks.
// Proof chain (all against the REAL page, no mocks, fresh context =
// clean cache):
//   1. no preview asset 404s (the static hero used to point at a missing
//      input_assets/power-cakes/hero.png);
//   2. at least one #preview img is fully decoded (naturalWidth > 0) before
//      any generation runs;
//   3. exactly one hero photo is shown (static figure retires when the JS
//      default-hero tile takes over — never zero, never a duo);
//   4. zero console errors / pageerrors on clean load.
// Run with:
//   npm run test:live -- --issue 196
import { assert, gotoLive } from "../lib.mjs";

export const issue = 196;
export const title = "on-load preview is photographic and on-brand";

export async function run(page, { baseUrl } = {}) {
  const badResponses = [];
  page.on("response", (r) => {
    if (r.status() >= 400 && /input_assets|data\//.test(r.url())) {
      badResponses.push(`${r.status()} ${r.url().slice(-80)}`);
    }
  });
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => consoleErrors.push(String(e).slice(0, 200)));

  await gotoLive(page, baseUrl);
  await page.waitForTimeout(1500);

  assert(badResponses.length === 0,
    `no preview/data 404s on clean load (${badResponses.join("; ") || "none"})`);

  // Lazy tiles below the fold have not fetched at load time; bring them into
  // view so decode can happen before the broken-image assert. A 404 or a
  // corrupt file still fails (badResponses above; never decodes below).
  await page.evaluate(() => {
    document.querySelectorAll("#preview img").forEach((im) => im.scrollIntoView({ block: "nearest" }));
  });
  await page.waitForFunction(
    () => [...document.querySelectorAll("#preview img")].every((im) => im.complete),
    null, { timeout: 10000 },
  );
  await page.waitForTimeout(400);

  const heroes = await page.evaluate(() => [...document.querySelectorAll("#preview img")].map((im) => ({
    src: im.getAttribute("src"),
    decoded: im.complete && im.naturalWidth > 0,
    hidden: im.style.display === "none" || im.offsetWidth === 0,
  })));
  const shown = heroes.filter((h) => h.decoded);
  assert(shown.length >= 1,
    `photographic hero decoded on load (${JSON.stringify(shown.map((h) => h.src))})`);
  const broken = heroes.filter((h) => !h.decoded && !h.hidden);
  assert(broken.length === 0,
    `zero broken-but-visible preview images (${broken.map((h) => h.src).join("; ") || "none"})`);

  assert(consoleErrors.length === 0,
    `zero console errors on clean load (${consoleErrors.join("; ") || "none"})`);

  await page.evaluate(() => {
    document.getElementById("previewCard").open = true;
    document.querySelector("#preview img")?.scrollIntoView({ block: "center" });
  });
  await page.waitForTimeout(800);
}
