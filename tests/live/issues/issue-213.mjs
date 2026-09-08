// Issue #213 — market selection syncs all derived state.
// Symptom was two half-fixes for one bug: the dropdown relabeled itself while
// derived state stayed on Park City. Acceptance: picking SF Bay syncs the
// button label, the market source line, and the hidden #locality select with
// zero pageerrors; Restore defaults re-renders all three back.
// NOTE: fix/input-side-217-213 extends this same file with the declared-control
// assertions (present/populated/warnings) — keep both halves on union.
import { assert, clickResetDefaults, gotoLive } from "../lib.mjs";

export const issue = 213;
export const title = "market pick syncs button, source line, select";

export async function run(page, { baseUrl } = {}) {
  const pageerrors = [];
  page.on("pageerror", (err) => pageerrors.push(String(err).slice(0, 200)));
  await gotoLive(page, baseUrl);

  // Pick SF Bay through the listbox (the Axis-2 path that starved derived state).
  const picked = await page.evaluate(() => {
    const opts = Array.from(document.querySelectorAll('#marketListbox [role="option"]'));
    const sf = opts.find((o) => (o.dataset.market || "").includes("US-W-SF"));
    if (!sf) return null;
    sf.click();
    return sf.dataset.market;
  });
  assert(picked && picked.includes("US-W-SF"), `SF Bay option picked (${picked})`);
  await page.waitForTimeout(800);

  const synced = await page.evaluate(() => ({
    select: document.getElementById("locality")?.value || null,
    label: document.getElementById("marketButtonLabel")?.textContent?.trim() || null,
    source: document.getElementById("ffMarketSource")?.textContent?.trim() || null,
  }));
  assert(synced.select === picked, `hidden select synced (${synced.select})`);
  assert(synced.label && !/park city/i.test(synced.label), `button relabeled off Park City (${synced.label})`);
  assert(synced.source && !/park city default/i.test(synced.source), `source line moved on (${synced.source?.slice(0, 80)})`);
  assert(/san francisco|sf bay/i.test((synced.label || "") + " " + (synced.source || "")), "SF names somewhere visible");

  // Restore defaults re-renders all three back.
  assert((await clickResetDefaults(page)) === "clicked", "Restore defaults clicks");
  await page.waitForTimeout(800);
  const restored = await page.evaluate(() => ({
    select: document.getElementById("locality")?.value || null,
    label: document.getElementById("marketButtonLabel")?.textContent?.trim() || null,
    source: document.getElementById("ffMarketSource")?.textContent?.trim() || null,
  }));
  assert(restored.select === "US-MW-PARKCITY-84098", `select back to default (${restored.select})`);
  assert(/park city/i.test(restored.label || ""), `button back to Park City (${restored.label})`);
  assert(/park city default/i.test(restored.source || ""), `source line back to default (${restored.source?.slice(0, 80)})`);

  assert(pageerrors.length === 0, `zero pageerrors (got: ${pageerrors.join(" | ").slice(0, 300)})`);
}
