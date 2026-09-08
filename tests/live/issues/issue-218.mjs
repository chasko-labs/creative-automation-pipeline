// Issue #218 cluster — scope section is one guided step (#218), chips render into the
// brief with typed text never clobbered (#236), one selection per concept drives brief +
// layers (#237), scope block speaks marketer voice (#223). All against the REAL page,
// local static server (no backend needed — every assertion is client-side state).
import { assert, gotoLive } from "../lib.mjs";

export const issue = 218;
export const title = "scope cluster: guided step, chips into brief, unified layers, marketer copy";

const chipPressed = (page, slug) => page.evaluate((s) => {
  const c = document.querySelector('.ff-chip[data-theme="' + s + '"]');
  return c ? c.getAttribute("aria-pressed") : "NO-CHIP";
}, slug);

const clickChip = (page, slug) => page.evaluate((s) => {
  const c = document.querySelector('.ff-chip[data-theme="' + s + '"]');
  if (!c) return "NO-CHIP";
  c.click();
  return "clicked";
}, slug);

const briefText = (page) => page.evaluate(
  () => document.getElementById("campaignBrief").value);

const layerState = (page) => page.evaluate(() => ({
  product: document.getElementById("layerProduct").checked,
  retailer: document.getElementById("layerRetailer").checked,
  retailerSel: document.getElementById("layerRetailerSelect").value,
  partner: document.getElementById("layerPartner").checked,
  summary: document.getElementById("layersState").textContent,
  partnerMarkHidden: document.getElementById("ussPartnerMark").hidden,
}));

export async function run(page, { baseUrl } = {}) {
  await gotoLive(page, baseUrl);

  // ---- #218: one guided setup step, clear order, same controls reachable ----
  const setup = await page.evaluate(() => {
    const sec = document.querySelector("section.ff-setup");
    if (!sec) return null;
    const steps = Array.from(sec.querySelectorAll("[data-step]")).map((el) => ({
      step: el.getAttribute("data-step"),
      id: el.id || el.className,
    }));
    return {
      heading: document.getElementById("ffSetupHeading")?.textContent || "",
      steps,
      radio: document.querySelectorAll('#campaignScope[role="radiogroup"] [role="radio"]').length,
      listbox: !!document.getElementById("marketListbox"),
      scope: window.__campaignScope,
    };
  });
  assert(setup, "ff-setup section exists");
  assert(/set up your campaign/i.test(setup.heading), `section headed (${setup.heading})`);
  assert(setup.steps.map((s) => s.step).join(",") === "1,2,3,4",
    `four ordered steps (${setup.steps.map((s) => s.step + ":" + s.id).join(" ")})`);
  assert(setup.radio === 3, "same 3 scope radios reachable");
  assert(setup.listbox, "market listbox reachable");
  assert(setup.scope === "local", "default scope local");

  // ---- #223: marketer voice, copy only ----
  const copy = await page.evaluate(() => ({
    summary: document.querySelector(".ff-scope-summary")?.textContent || "",
    aria: document.getElementById("campaignScope")?.getAttribute("aria-label") || "",
    titles: Array.from(document.querySelectorAll(".ff-scope-opt-title")).map((el) => el.textContent.trim()),
    subs: Array.from(document.querySelectorAll(".ff-scope-opt-sub")).map((el) => el.textContent.trim()),
    body: document.querySelector("section.ff-setup")?.textContent || "",
  }));
  assert(/^How far this reaches/.test(copy.summary), `summary leads marketer-voice (${copy.summary})`);
  assert(copy.aria === "How far this reaches", "radiogroup aria-label relabeled, role untouched");
  assert(!/Campaign scope/.test(copy.body), "no developer 'Campaign scope' copy left in the step");
  assert(!/Nationwide \+ localized markets/.test(copy.body), "old redundant title gone");
  assert(copy.titles.includes("Nationwide + local versions"), "deduped title present");
  assert(copy.subs.includes("One core campaign, adapted per market"), "deduped sub present");
  assert(copy.titles.every((t, i) => t !== copy.subs[i]), "no title/sub pair repeats itself");

  // ---- scope invariant: nationwide dims the market row, keyboard moves, readers follow ----
  await page.evaluate(() => document.querySelector('[data-scope="nationwide"]').click());
  await page.waitForTimeout(300);
  let mode = await page.evaluate(() => ({
    mode: document.querySelector(".ff-controlrow").getAttribute("data-scope-mode"),
    note: !document.getElementById("marketScopeNote").hidden,
    scope: window.__campaignScope,
    summary: document.getElementById("scopeSummary").textContent,
  }));
  assert(mode.mode === "nationwide" && mode.note && mode.scope === "nationwide",
    "nationwide dims market row + shows anchor note");
  assert(mode.summary === "Nationwide", "summary follows selection");
  // the reach control rests in a closed disclosure — open it so keyboard focus can land
  await page.evaluate(() => { document.getElementById("scopeWrap").open = true; });
  await page.evaluate(() => document.querySelector('[data-scope="nationwide"]').focus());
  await page.keyboard.press("ArrowRight");
  await page.waitForTimeout(300);
  mode = await page.evaluate(() => window.__campaignScope);
  assert(mode === "nationwide-localized", "arrow key moves radiogroup selection");
  await page.evaluate(() => document.querySelector('[data-scope="local"]').click());
  await page.waitForTimeout(300);

  // ---- #236: chips render into the brief; untoggle removes; typing never clobbered ----
  await page.fill("#campaignBrief", "Fuel mornings");
  await page.waitForTimeout(200);
  assert((await clickChip(page, "bears")) === "clicked", "bears chip clicks");
  await page.waitForTimeout(400);
  let brief = await briefText(page);
  assert(brief.includes("Fuel mornings"), "typed text survives toggle");
  assert(brief.includes("Bears"), `bears renders into brief (${brief})`);
  assert((await clickChip(page, "localized-costco")) === "clicked", "costco chip clicks");
  await page.waitForTimeout(400);
  brief = await briefText(page);
  assert(brief.includes("Bears") && brief.includes("Localized Costco"), `chips stack (${brief})`);
  assert((await clickChip(page, "bears")) === "clicked", "bears untoggles");
  await page.waitForTimeout(400);
  brief = await briefText(page);
  assert(!brief.includes("Bears"), "untoggle removes the clause");
  assert(brief.includes("Localized Costco") && brief.includes("Fuel mornings"),
    `rest untouched (${brief})`);
  // type AFTER the generated tail, then toggle: the typed tail must survive (#236 core)
  await page.evaluate(() => {
    const el = document.getElementById("campaignBrief");
    el.focus();
    el.setSelectionRange(el.value.length, el.value.length);
  });
  await page.keyboard.type(" for winter");
  await page.waitForTimeout(400);
  assert((await clickChip(page, "zac-efron")) === "clicked", "zac chip clicks after typing");
  await page.waitForTimeout(400);
  brief = await briefText(page);
  assert(brief.includes("for winter"), `typed tail survives a later toggle (${brief})`);
  assert(brief.includes("Zac Efron"), "new chip renders");
  assert((await chipPressed(page, "localized-costco")) === "true", "typing never disarms chips");
  assert((await chipPressed(page, "zac-efron")) === "true", "new chip stays armed");
  // type BEFORE the generated tail: caret-safe silent adopt, chips stay armed
  await page.evaluate(() => {
    const el = document.getElementById("campaignBrief");
    el.focus();
    el.setSelectionRange(0, 0);
  });
  await page.keyboard.type("Big ");
  await page.waitForTimeout(400);
  brief = await briefText(page);
  assert(brief.startsWith("Big Fuel mornings"), `head edit adopted (${brief})`);
  assert((await chipPressed(page, "localized-costco")) === "true", "head edit keeps chips armed");

  // ---- #237: one selection per concept drives brief + layers ----
  let layers = await layerState(page);
  assert(layers.retailer && layers.retailerSel === "costco",
    `costco chip drives retailer layer (${JSON.stringify(layers)})`);
  assert(layers.summary !== "all off", "layers summary reflects the mirrored flag");
  // layer -> chip: unchecking the retailer layer untoggles the chip + drops the clause
  await page.evaluate(() => document.getElementById("layerRetailer").click());
  await page.waitForTimeout(400);
  assert((await chipPressed(page, "localized-costco")) === "false", "layer uncheck untoggles chip");
  brief = await briefText(page);
  assert(!brief.includes("Localized Costco"), "layer uncheck drops the brief clause");
  // layer -> chip: checking the partner layer arms the partner chip + mark
  await page.evaluate(() => document.getElementById("layerPartner").click());
  await page.waitForTimeout(400);
  assert((await chipPressed(page, "us-ski-snowboard")) === "true", "partner layer arms chip");
  layers = await layerState(page);
  assert(!layers.partnerMarkHidden, "partner mark shows");
  brief = await briefText(page);
  assert(/Ski/.test(brief), `partner clause renders (${brief})`);
  // select owns non-costco retailers: publix + checked layer leaves the costco chip off
  await page.evaluate(() => {
    const sel = document.getElementById("layerRetailerSelect");
    sel.value = "publix";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForTimeout(400);
  layers = await layerState(page);
  assert(layers.retailer && layers.retailerSel === "publix", "publix layer checks in");
  assert((await chipPressed(page, "localized-costco")) === "false",
    "publix mark does not arm the costco chip");
  // back to costco with the layer on: chip re-arms (single shared concept)
  await page.evaluate(() => {
    const sel = document.getElementById("layerRetailerSelect");
    sel.value = "costco";
    sel.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForTimeout(400);
  assert((await chipPressed(page, "localized-costco")) === "true", "costco layer re-arms chip");
  // product concept: layer flag stays a manual flag, never auto-invented
  layers = await layerState(page);
  assert(layers.product === false, "product layer stays off until the user flags it");
  assert((await page.evaluate(() => window.__selectedLayers())) &&
    (await page.evaluate(() => Object.keys(window.__selectedLayers()).join(","))).includes("retailer"),
    "__selectedLayers still carries the mirrored retailer flag");
}
