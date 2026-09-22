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
    expect(auto).toMatch(/#promptChips \.ff-check-card\[data-brief\]/);
    expect(auto).toMatch(/window\.__briefSuffixMarker\s*=\s*SUFFIX_MARKER/);
    expect(auto).toMatch(/window\.__briefContextSuffix\s*=\s*buildSuffix/);
    expect(auto).toMatch(/typeof window\.__rebuildBrief === 'function'/);
  });

  it('checkbox cards: one shared setter, no layer sync, no standalone mark flags', () => {
    expect(chips).toMatch(/function setChip\(slug, on/);
    expect(chips).toMatch(/\.ff-check-card__input\[data-theme\]/);
    // the two-way sync is retired — each card drives its own mark directly
    expect(chips).not.toMatch(/function syncLayersFromChips/);
    expect(chips).not.toMatch(/function syncChipsFromLayers/);
    expect(chips).not.toMatch(/getElementById\('layerRetailer'\)/);
    expect(chips).not.toMatch(/getElementById\('layerPartner'\)/);
    expect(html).not.toMatch(/id="layerRetailer"/);
    expect(html).not.toMatch(/id="layerPartner"/);
    // layers still read by id in generate.js — the __selectedLayers contract is unchanged
    expect(generate).toMatch(/window\.__selectedLayers\s*=\s*function/);
    expect(generate).toMatch(/getElementById\('layerProduct'\)+\)\?\.checked/);
    expect(generate).not.toMatch(/getElementById\('layerRetailer'\)/);
    expect(generate).not.toMatch(/getElementById\('layerPartner'\)/);
    // product flag drops when nothing is staged (no stale compose flag)
    expect(chips).toMatch(/function maybeClearProductLayer/);
  });

  it('concept rows: cards carry data-theme + data-brief, retailer mark iff specific', () => {
    // retailer cards: three specifics (Costco/Publix/Target, #198) + All (brief only);
    // Walmart is never a chooser card — it stays in market data strings only.
    expect(html).toMatch(/ff-check-card__input" data-theme="localized-costco"/);
    expect(html).toMatch(/ff-check-card__input" data-theme="localized-publix"/);
    expect(html).toMatch(/ff-check-card__input" data-theme="localized-target"/);
    expect(html).toMatch(/ff-check-card__input" data-theme="localized-all"/);
    expect(html).not.toMatch(/localized-walmart/);
    expect(chips).toMatch(/'localized-target':'target'/);
    // partner: ONE card carries data-theme + data-brief, mark preview inline in the same cluster
    expect(html).toMatch(/ff-chipcluster ff-concept" role="group" aria-labelledby="chipClusterPartner"[\s\S]*?ff-check-card" data-theme="us-ski-snowboard"[\s\S]*?id="ussPartnerMark"/);
    // every card keeps its slug + brief contract
    for (const slug of ['recipe-cards', 'kodiak-subscription', 'localized-target', 'wild-grizzly-bears', 'riff-on-past-content', 'us-ski-snowboard']) {
      expect(html).toMatch(new RegExp('ff-check-card" data-theme="' + slug + '"[^>]*data-brief="[^"]+'));
    }
    // retailer mark composes iff a SPECIFIC retailer is checked, most-recent wins
    expect(chips).toMatch(/RETAILER_CARD_VALUES/);
    expect(chips).toMatch(/__retailerCheckOrder/);
    expect(chips).toMatch(/window\.__activeRetailerValue = activeRetailerValue/);
    expect(generate).toMatch(/window\.__activeRetailerValue\(\)/);
    expect(generate).toMatch(/ff-check-card__input\[data-theme="us-ski-snowboard"\]/);
    expect(generate).not.toMatch(/layerPicker/);
    // no Compose subheadings remain; layer checkbox accent reads pine; card checked state is class-free :has()
    expect(html).not.toMatch(/ff-optiongroup-label">Compose</);
    expect(css).toMatch(/\.ff-layer input\{[^}]*accent-color:var\(--colors-brand-frontier-green\)/);
    expect(css).toMatch(/\.ff-check-card:has\(\.ff-check-card__input:checked\)/);
    expect(css).toMatch(/\.ff-partner-mark\.is-on\{display:flex\}/);
    expect(css).not.toMatch(/\.ff-concept \.ff-layer/);
  });

  it('unified style: house-token background wash, flush about art, spacing-token caps', () => {
    // layered page wash from house tokens at low alpha — token refs only, never raw hex
    expect(css).toMatch(/color-mix\(in srgb,var\(--colors-brand-frontier-green\)/);
    expect(css).toMatch(/color-mix\(in srgb,var\(--colors-brand-bear-brown\)/);
    // about art flush with its section (no stacked top margin)
    expect(css).toMatch(/\.ff-about-art\{margin:0/);
    // inter-section caps shrink via shared spacing tokens
    expect(css).toMatch(/\.ff-ridge\{height:var\(--spacing-xl/);
    expect(css).toMatch(/\.ff-forest\{height:var\(--spacing-xl/);
    expect(css).toMatch(/\.ff-about-art \.ff-about-range\{[^}]*height:var\(--spacing-xl/);
  });

  it('product picks still reset directions (documented own-start semantics)', () => {
    expect(chips).toMatch(/window\.__clearActiveTheme\s*=\s*function/);
    expect(chips).toMatch(/contains\('sku-check'\)\)/);
  });
});
