// Issue #213 — market selection syncs all derived state.
// Union of two halves: the declared-control half (fillSelects must not build a
// hidden #locality fallback; zero console warnings on load) and the sync half
// (#256: picking SF Bay syncs button label, market source line, and the hidden
// #locality select; Restore defaults re-renders all three back).
// Local-safe: no backend calls.
import { assert, clickResetDefaults, gotoLive } from "../lib.mjs";

export const issue = 213;
export const title = "market control declared, pick syncs all derived state";

export async function run(page, { baseUrl } = {}) {
  // console WARNINGS are the declared-control acceptance (the fallback warn fired
  // on every load). Resource 404s from the local static server (deploy-only
  // input_assets) are collected separately and reported, never failed.
  const warnings = [];
  const pageerrors = [];
  const resourceErrors = [];
  page.on("console", (msg) => {
    const text = msg.text();
    if (msg.type() === "warning") warnings.push(text.slice(0, 200));
    else if (msg.type() === "error" && /failed to load resource/i.test(text)) resourceErrors.push(text.slice(0, 120));
    else if (msg.type() === "error") warnings.push(`error: ${text.slice(0, 200)}`);
  });
  page.on("pageerror", (err) => pageerrors.push(String(err).slice(0, 200)));
  await gotoLive(page, baseUrl);

  // the control is declared in markup and populated by fillSelects — never a fallback
  const loc = await page.evaluate(() => {
    const el = document.getElementById("locality");
    if (!el) return null;
    return {
      tag: el.tagName,
      displayNone: el.style.display === "none",
      count: el.options ? el.options.length : 0,
      value: el.value,
    };
  });
  assert(loc && loc.tag === "SELECT", "declared #locality select present");
  assert(!loc.displayNone, "real control, not a display:none fallback");
  assert(loc.count > 10, `#locality populated (${loc.count} options)`);
  assert(loc.value === "US-MW-PARKCITY-84098", `Park City default (${loc.value})`);

  // picking SF Bay through the listbox syncs every derived surface (#256 symptom:
  // the dropdown relabeled itself while state stayed Park City).
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

  // Restore defaults re-renders all three back. The source line trails
  // select+label through a slower persist round-trip (~30% of runs read
  // it before it lands), so poll it bounded instead of single-shot.
  assert((await clickResetDefaults(page)) === "clicked", "Restore defaults clicks");
  await page.waitForTimeout(800);
  await page.waitForFunction(
    () => /park city default/i.test(document.getElementById("ffMarketSource")?.textContent || ""),
    null,
    { timeout: 5000 },
  );
  const restored = await page.evaluate(() => ({
    select: document.getElementById("locality")?.value || null,
    label: document.getElementById("marketButtonLabel")?.textContent?.trim() || null,
    source: document.getElementById("ffMarketSource")?.textContent?.trim() || null,
  }));
  assert(restored.select === "US-MW-PARKCITY-84098", `select back to default (${restored.select})`);
  assert(/park city/i.test(restored.label || ""), `button back to Park City (${restored.label})`);
  assert(/park city default/i.test(restored.source || ""), "source line back to default");

  await page.waitForTimeout(500);
  assert(warnings.length === 0, `zero console warnings (got: ${warnings.join(" | ").slice(0, 300)})`);
  assert(pageerrors.length === 0, `zero page errors (got: ${pageerrors.join(" | ").slice(0, 200)})`);
  if (resourceErrors.length) console.log(`  note: ${resourceErrors.length} local-only resource 404(s), pre-existing on main`);
}
