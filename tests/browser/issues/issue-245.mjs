// Issue #245 — retailer direction never reaches the output.
// Acceptance: the retailer choice visibly changes the render brief and the
// copy. Proof chain (all against the REAL page + hosted backend):
//   1. tapping the Localized Costco chip writes the direction into the brief;
//   2. Generate full campaign sends theme=localized-costco on /generate
//      (the field the campaign path never sent before this fix);
//   3. the returned copy sidecar carries the retailer framing line, so the
//      same brief with and without the retailer yields different copy
//      (python tests/test_retailer_direction.py pins the sidecar diff +
//      the scene-prompt fold offline).
// Run with:
//   npm run test:browser -- --issue 245
import { assert, gotoLocal } from "../lib.mjs";

export const issue = 245;
export const title = "retailer direction reaches image brief and copy";

const PANEL_TIMEOUT_MS = 120000;

export async function run(page, { baseUrl } = {}) {
  const isLocal = /127\.0\.0\.1|localhost/.test(baseUrl || "");
  await gotoLocal(page, baseUrl);

  // 1. Chip tap directs the brief.
  await page.evaluate(() =>
    document.querySelector('#promptChips .ff-chip[data-theme="localized-costco"]')?.click());
  await page.waitForTimeout(800);
  const brief = await page.evaluate(() => document.getElementById("campaignBrief")?.value || "");
  assert(/localized costco/i.test(brief), `brief carries retailer direction (${brief.slice(0, 120)})`);
  const pressed = await page.evaluate(() =>
    document.querySelector('#promptChips .ff-chip[data-theme="localized-costco"]')?.getAttribute("aria-pressed"));
  assert(pressed === "true", "chip shows active");

  // Hold the directed brief on screen for the receipt.
  await page.evaluate(() => document.getElementById("campaignBrief")?.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(1200);

  // 2. The campaign request carries the theme.
  let genBody = null;
  await page.route("**/generate", async (route) => {
    try { genBody = route.request().postDataJSON(); } catch (_) { genBody = null; }
    await route.continue();
  });
  await page.evaluate(() => document.getElementById("genFullCampaign")?.click());

  if (isLocal) {
    await page.waitForTimeout(2000);
    await page.unroute("**/generate");
    assert(genBody && genBody.theme === "localized-costco", "local request carries theme");
    return;
  }

  // 3. Copy comes back retailer-framed and visible.
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200)); });
  page.on("pageerror", (e) => consoleErrors.push(String(e).slice(0, 200)));
  try {
    await page.waitForFunction(
      () => {
        const p = document.getElementById("campaignCopyPanel");
        return p && p.querySelectorAll(".loc-line").length >= 2;
      },
      null,
      { timeout: PANEL_TIMEOUT_MS },
    );
  } catch (e) {
    const diag = await page.evaluate(() => ({
      status: document.getElementById("generateCampaignStatus")?.textContent || null,
      assetsHidden: document.getElementById("campaignAssetsSection")?.hidden ?? null,
      genBtn: !!document.getElementById("genFullCampaign"),
      headline: window.__lastCampaignHeadline ?? null,
      sidecar: !!window.__lastCampaignSidecar,
      version: document.querySelector('meta[name="kodiak-version"]')?.content || null,
    }));
    throw new Error(`no copy panel; diag=${JSON.stringify(diag)} console=${JSON.stringify(consoleErrors.slice(0, 5))}`);
  }
  await page.unroute("**/generate").catch(() => {});
  assert(genBody && genBody.theme === "localized-costco",
    `campaign request carries retailer theme (${JSON.stringify(genBody && Object.keys(genBody))})`);
  const sidecar = await page.evaluate(() => window.__lastCampaignSidecar || null);
  assert(sidecar && /retailer framing/i.test(sidecar.txt || ""),
    "sidecar txt carries the retailer framing line");
  assert(sidecar && /retailer_framing/.test(sidecar.csv || ""),
    "sidecar csv carries the retailer framing row");
  await page.evaluate(() => document.getElementById("campaignCopyPanel")
    ?.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(1500);
}
