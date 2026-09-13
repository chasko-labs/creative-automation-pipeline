// Issue #244 — brand-term translation policy: Keep It Wild untranslated in ES/PT.
// Policy (decided, documented in localize_service): slogans/marks never
// translate — BRAND_TERMS ship verbatim, everything else translates.
// Proof chain against the REAL page + hosted backend:
//   (a) POST /localize directly: ES + PT of a term-carrying headline keep
//       "Keep It Wild" verbatim while the surrounding text translates;
//   (b) visible compliance: after Generate full campaign with a term-carrying
//       brief, the ES row flips provider=live and still carries the term
//       verbatim (vacuous only when the composed headline carries no term,
//       in which case the test records the headline for the receipt).
// Run with:
//   npm run test:browser -- --issue 244
import { assert, gotoLocal } from "../lib.mjs";

export const issue = 244;
export const title = "brand terms survive ES/PT localization";

const TEXT = "Keep It Wild mornings fuel the frontier";
const PANEL_TIMEOUT_MS = 120000;

async function localize(page, text, code) {
  return page.evaluate(async ({ text, code }) => {
    const resp = await fetch("/localize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, market: "US-MW-PARKCITY-84098", target_lang: code }),
    });
    if (!resp.ok) return { status: resp.status, json: null };
    return { status: resp.status, json: await resp.json().catch(() => null) };
  }, { text, code });
}

export async function run(page, { baseUrl } = {}) {
  await gotoLocal(page, baseUrl);

  // (a) policy seam, both languages.
  for (const code of ["es", "pt"]) {
    const { status, json } = await localize(page, TEXT, code);
    assert(status === 200 && json && typeof json.text === "string", `/${code} 200 with text`);
    assert(json.text.includes("Keep It Wild"), `${code} keeps slogan verbatim (${json.text})`);
    assert(json.text !== TEXT, `${code} translates around the slogan (${json.text})`);
  }

  // (b) visible compliance on a real campaign.
  await page.evaluate(() => {
    const b = document.getElementById("campaignBrief");
    if (b) { b.value = "Keep It Wild frontier mornings"; b.dispatchEvent(new Event("input", { bubbles: true })); }
  });
  await page.waitForTimeout(800);
  await page.evaluate(() => document.getElementById("genFullCampaign")?.click());
  const isLocal = /127\.0\.0\.1|localhost/.test(baseUrl || "");
  if (isLocal) return;
  await page.waitForFunction(
    () => {
      const p = document.getElementById("campaignCopyPanel");
      return p && p.querySelectorAll(".loc-line").length >= 2;
    },
    null,
    { timeout: PANEL_TIMEOUT_MS },
  );
  // Rows paint pending-live first; the /localize swaps land async after.
  await page.waitForFunction(
    () => Array.from(document.querySelectorAll("#campaignCopyPanel .loc-line"))
      .some((r) => r.getAttribute("lang") !== "en" && r.getAttribute("data-provider") === "live"),
    null,
    { timeout: 60000 },
  );
  const rows = await page.evaluate(() => {
    const p = document.getElementById("campaignCopyPanel");
    return Array.from(p.querySelectorAll(".loc-line")).map((r) => ({
      lang: r.getAttribute("lang"),
      provider: r.getAttribute("data-provider"),
      text: r.querySelector(".loc-text")?.textContent || "",
    }));
  });
  const en = (rows.find((r) => r.lang === "en") || {}).text || "";
  const live = rows.filter((r) => r.lang !== "en" && r.provider === "live");
  assert(live.length >= 1, `live localized rows present (${rows.map((r) => r.lang + ":" + r.provider).join(",")})`);
  const enTerms = ["Keep It Wild", "KODIAK"].filter((t) => en.includes(t));
  console.log(`      headline carries terms: ${JSON.stringify(enTerms)} (${en.slice(0, 80)})`);
  for (const t of enTerms) {
    assert(live.every((r) => r.text.includes(t)), `every live row keeps ${t} verbatim`);
  }
  await page.evaluate(() => document.getElementById("campaignCopyPanel")
    ?.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(1500);
}
