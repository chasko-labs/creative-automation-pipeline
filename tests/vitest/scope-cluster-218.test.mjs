import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const html = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const chips = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/prompt-chips.js'), 'utf8');
const auto = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/autocomplete.js'), 'utf8');
const generate = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');
const disclosure = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/market-disclosure.js'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// #218/#236/#237/#223 scope cluster: one guided setup step, chips render into the brief,
// one selection per concept drives brief + layers, marketer-voice copy.
// Behavioral proof lives in tests/live/issues/issue-218.mjs (real browser).
// These guards pin the source contract so the cluster cannot silently regress.
describe('scope cluster (#218, #236, #237, #223)', () => {
  it('#218: one guided setup section wraps the four blocks in order', () => {
    expect(html).toMatch(/<section class="ff-setup" aria-labelledby="ffSetupHeading">/);
    expect(html).toMatch(/<h2 id="ffSetupHeading"/);
    const steps = [...html.matchAll(/data-step="([1234])"/g)].map((m) => m[1]);
    expect(steps).toEqual(['1', '2', '3', '4']);
    expect(html.indexOf('data-step="1"')).toBeLessThan(html.indexOf('data-step="2"'));
    expect(html.indexOf('data-step="2"')).toBeLessThan(html.indexOf('data-step="3"'));
    expect(html.indexOf('data-step="3"')).toBeLessThan(html.indexOf('data-step="4"'));
  });

  it('step 2 collapses to one summary line at rest, label mirrored by JS', () => {
    // locationSection is a CLOSED disclosure (no open attr); the control row
    // nests inside with bindings intact, dimming hook untouched.
    expect(html).toMatch(/<details class="ff-location" id="locationSection" data-step="2">/);
    expect(html).toMatch(/<span id="locationSectionLabel">Park City, Utah<\/span>/);
    expect(html).toMatch(/<div class="ff-controlrow" role="group"[^>]*data-scope-mode="local">/);
    expect(disclosure).toMatch(/locationSectionLabel/);
  });

  it('#218 invariants: radiogroup/listbox semantics, dimming hook, scope readers', () => {
    expect(html).toMatch(/id="campaignScope" role="radiogroup"/);
    expect(html).toMatch(/role="radio"[^>]*data-scope="nationwide"/);
    expect(html).toMatch(/id="marketListbox" role="listbox"/);
    expect(html).toMatch(/data-scope-mode="local"/);
    expect(chips).toMatch(/window\.__campaignScope/);
    expect(generate).toMatch(/window\.__campaignScope \|\| 'local'/);
    expect(chips).toMatch(/setAttribute\('data-scope-mode'/);
  });

  it('#223: marketer-voice copy, no redundant title/sub, behavior untouched', () => {
    expect(html).toMatch(/How far this reaches/);
    expect(html).toMatch(/aria-label="How far this reaches"/);
    // Full campaign is the hero of step 1: every market, retailer, theme, partner variant
    expect(html).toMatch(/Full campaign/);
    expect(html).toMatch(/Every market localized/);
    expect(html).toMatch(/Wild Grizzly Bears/);
    expect(html).not.toMatch(/Zac Efron/);
    expect(html).toMatch(/id="fullCampaignBanner"/);
    expect(html).not.toMatch(/Campaign scope/);
    expect(html).not.toMatch(/Nationwide \+ localized markets/);
    expect(html).not.toMatch(/National core, localized variants/);
    // behavior/ids/aria untouched: same data-scope values, same roles, same ids
    expect(html).toMatch(/data-scope="nationwide-localized"/);
    expect(html).toMatch(/data-scope="nationwide"/);
    expect(html).toMatch(/data-scope="local"/);
    expect(html).toMatch(/id="scopeWrap"/);
    expect(html).toMatch(/id="scopeSummary"/);
  });

  it('#236: one brief assembly owned by prompt-chips, free text always recoverable', () => {
    expect(chips).toMatch(/window\.__rebuildBrief\s*=\s*rebuildBrief/);
    expect(chips).toMatch(/window\.__briefFreeText\s*=\s*stripFreeText/);
    expect(chips).toMatch(/window\.__briefUserText\s*=\s*base/);
    expect(chips).toMatch(/__briefContextSuffix/);
    // manual typing adopts — the textarea handler never disarms chips
    expect(chips).toMatch(/Manual textarea edit \(#236\): adopt, never clear/);
  });

  it('#236: suggestion picks keep chips armed (no clear on insert)', () => {
    expect(auto).not.toMatch(/__clearActiveTheme/);
    expect(auto).toMatch(/window\.__briefSuffixMarker\s*=\s*SUFFIX_MARKER/);
    expect(auto).toMatch(/window\.__briefContextSuffix\s*=\s*buildSuffix/);
    expect(auto).toMatch(/typeof window\.__rebuildBrief === 'function'/);
  });

  it('#237: retailer/partner chips two-way sync with layer flags, single setter', () => {
    expect(chips).toMatch(/function setChip\(slug, on/);
    expect(chips).toMatch(/function syncLayersFromChips/);
    expect(chips).toMatch(/function syncChipsFromLayers/);
    expect(chips).toMatch(/getElementById\('layerRetailer'\)\?\.addEventListener\('change', syncChipsFromLayers\)/);
    expect(chips).toMatch(/getElementById\('layerPartner'\)\?\.addEventListener\('change', syncChipsFromLayers\)/);
    // layers still read by id in generate.js — the __selectedLayers contract is unchanged
    expect(generate).toMatch(/window\.__selectedLayers\s*=\s*function/);
    expect(generate).toMatch(/getElementById\('layerProduct'\)\?\.checked/);
    // product flag drops when nothing is staged (no stale compose flag)
    expect(chips).toMatch(/function maybeClearProductLayer/);
  });

  it('concept rows: flags ride with their chips, retailer select retired', () => {
    // retailer flag lives inside the retailer cluster; partner flag + mark inside partner's
    expect(html).toMatch(/ff-chipcluster ff-concept" role="group" aria-labelledby="chipClusterRetailer"[\s\S]*?id="layerRetailer"/);
    expect(html).toMatch(/ff-chipcluster ff-concept" role="group" aria-labelledby="chipClusterPartner"[\s\S]*?id="layerPartner"[\s\S]*?id="ussPartnerMark"/);
    // select element gone from markup (retirement comments may name it); retailer comes from the chips
    expect(html).not.toMatch(/id="layerRetailerSelect"/);
    expect(html).not.toMatch(/<select id="layerRetailerSelect"/);
    expect(chips).not.toMatch(/layerRetailerSelect'\)\?\.addEventListener/);
    expect(chips).toMatch(/window\.__activeRetailerValue = activeRetailerValue/);
    expect(generate).toMatch(/window\.__activeRetailerValue\(\)/);
    expect(generate).not.toMatch(/layerPicker/);
    // no Compose subheadings remain; layer checkbox accent reads pine
    expect(html).not.toMatch(/ff-optiongroup-label">Compose</);
    expect(css).toMatch(/\.ff-layer input\{[^}]*accent-color:var\(--colors-brand-frontier-green\)/);
    expect(css).toMatch(/\.ff-concept \.ff-layer\{margin-left:auto/);
  });

  it('product picks still reset directions (documented own-start semantics)', () => {
    expect(chips).toMatch(/window\.__clearActiveTheme\s*=\s*function/);
    expect(chips).toMatch(/contains\('sku-check'\)\)/);
  });
});
