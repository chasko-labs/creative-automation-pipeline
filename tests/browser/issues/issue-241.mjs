// Issue #241 — full campaign output shows no accompanying copy.
// Acceptance: every generated campaign asset ships with its post copy and
// language variants VISIBLE (campaign copy panel under the assets) and
// DOWNLOADABLE (copy.txt/copy.csv inside the campaign pack zip).
// Needs the hosted backend (runCampaign shows an honest offline note on a
// local static server), so run with:
//   npm run test:browser -- --issue 241
import { assert, gotoLocal } from "../lib.mjs";

export const issue = 241;
export const title = "campaign copy visible and downloadable";

const PANEL_TIMEOUT_MS = 120000;

export async function run(page, { baseUrl } = {}) {
  const isLocal = /127\.0\.0\.1|localhost/.test(baseUrl || "");
  await gotoLocal(page, baseUrl);

  await page.evaluate(() => document.getElementById("genFullCampaign")?.click());
  await page.waitForTimeout(1500);

  if (isLocal) {
    const note = await page.evaluate(() =>
      document.getElementById("generateCampaignStatus")?.textContent || "");
    assert(/hosted backend/i.test(note), `offline shows honest note (got: ${note})`);
    return;
  }

  // VISIBLE: wait for the copy panel with the EN source row + variants.
  await page.waitForFunction(
    () => {
      const p = document.getElementById("campaignCopyPanel");
      return p && p.querySelectorAll(".loc-line").length >= 2;
    },
    null,
    { timeout: PANEL_TIMEOUT_MS },
  );
  const panel = await page.evaluate(() => {
    const p = document.getElementById("campaignCopyPanel");
    const rows = Array.from(p.querySelectorAll(".loc-line")).map((r) => ({
      lang: r.getAttribute("lang"),
      provider: r.getAttribute("data-provider"),
      text: (r.querySelector(".loc-text")?.textContent || "").slice(0, 120),
    }));
    const head = p.querySelector(".pc-head")?.textContent || "";
    return { head, rows };
  });
  assert(/campaign copy/i.test(panel.head), "panel headed 'Campaign copy'");
  const en = panel.rows.find((r) => r.lang === "en");
  assert(en && en.text.length > 10, "EN source headline row has copy");
  assert(en.provider === "source", "EN row tagged data-provider=source");
  const variants = panel.rows.filter((r) => r.lang !== "en");
  assert(variants.length >= 1, `language variant rows present (${variants.length})`);
  assert(
    variants.every((r) => r.text.length > 3),
    "no empty variant rows",
  );
  // Hold the panel on screen so the recorded receipt shows the copy.
  await page.evaluate(() => document.getElementById("campaignCopyPanel")
    ?.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(1500);

  // DOWNLOADABLE: the sidecar the pack ships must carry txt+csv with the headline.
  const sidecar = await page.evaluate(() => window.__lastCampaignSidecar || null);
  assert(sidecar && typeof sidecar.txt === "string" && sidecar.txt.length > 20, "sidecar txt present");
  assert(sidecar && typeof sidecar.csv === "string" && /headline/.test(sidecar.csv), "sidecar csv present");
  assert(
    sidecar.txt.includes(en.text.slice(0, 40)),
    "sidecar txt carries the panel headline",
  );

  // End to end: click the REAL Download Campaign Pack button, capture the
  // /assets/pack request the page builds (renders + sidecar extras) and prove
  // the returned zip contains copy.txt and copy.csv.
  let packBody = null;
  let packJson = null;
  await page.route("**/assets/pack", async (route) => {
    try { packBody = route.request().postDataJSON(); } catch (_) { packBody = null; }
    const resp = await route.fetch();
    try { packJson = await resp.json(); } catch (_) { packJson = null; }
    await route.fulfill({ response: resp });
  });
  await page.evaluate(() => document.getElementById("downloadCampaignPackTop")?.click());
  await page.waitForFunction(() => window.__packDone === true || /Downloaded|Could not|failed/i.test(
    document.getElementById("generateCampaignStatus")?.textContent || ""), null, { timeout: 60000 }).catch(() => {});
  await page.waitForTimeout(3000);
  await page.unroute("**/assets/pack");
  assert(packBody && Array.isArray(packBody.files) && packBody.files.length >= 1,
    `pack request carries DAM files (${packBody?.files?.length ?? 0})`);
  const extraNames = (packBody.extras || []).map((e) => e.name);
  assert(extraNames.includes("copy.txt"), `pack request carries copy.txt (${extraNames})`);
  assert(extraNames.includes("copy.csv"), `pack request carries copy.csv (${extraNames})`);
  assert(packJson && packJson.ok && packJson.zip_url, "pack 200 ok with zip_url");
  // Fetch the zip from node (the page is CORS-blocked from the presigned
  // S3 URL) and scan local file headers for member names (PK\x03\x04 + name).
  const zipRes = await fetch(packJson.zip_url);
  assert(zipRes.ok, `zip downloads (got ${zipRes.status})`);
  const buf = await zipRes.arrayBuffer();
  const bytes = new Uint8Array(buf);
  const dec = new TextDecoder();
  const names = [];
  const dv = new DataView(buf);
  for (let i = 0; i + 30 < bytes.length; i++) {
    if (dv.getUint32(i, true) === 0x04034b50) {
      const nlen = dv.getUint16(i + 26, true);
      const elen = dv.getUint16(i + 28, true);
      names.push(dec.decode(bytes.slice(i + 30, i + 30 + nlen)));
      i += 30 + nlen + elen;
    }
  }
  assert(names.some((n) => n.endsWith("copy.txt")), `zip holds copy.txt (${names.join(",")})`);
  assert(names.some((n) => n.endsWith("copy.csv")), `zip holds copy.csv (${names.join(",")})`);
}
