import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const sections = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/campaign-sections.js'),
  'utf8',
);
const chips = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/prompt-chips.js'),
  'utf8',
);
const generate = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'),
  'utf8',
);
const market = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/market-disclosure.js'),
  'utf8',
);
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'),
  'utf8',
);
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'),
  'utf8',
);

// Carousel: the campaign-assets carousel container exists only when renders exist.
describe('campaign carousel mounts only with renders', () => {
  it('mounts no static carousel shell in the assets section', () => {
    expect(sections).not.toMatch(/id="campaignAssetsCarousel" role="group"/);
  });

  it('creates the container on demand and removes it when nothing is renderable', () => {
    expect(sections).toMatch(/function renderCampaignCarousel\(renders, source\)/);
    expect(sections).toMatch(/\.filter\(function\(r\)\{ return r && r\.image_url; \}\)/);
    expect(sections).toMatch(/car\.id = 'campaignAssetsCarousel'/);
    expect(sections).toMatch(/if\(car && car\.parentNode\) car\.parentNode\.removeChild\(car\); return;/);
  });

  it('reset removes the container instead of leaving an emptied shell', () => {
    expect(sections).toMatch(
      /var car = document\.getElementById\('campaignAssetsCarousel'\); if\(car && car\.parentNode\) car\.parentNode\.removeChild\(car\);/,
    );
  });

  it('product carousel rests empty and hidden; slots fill only from resolved images', () => {
    expect(index).toMatch(/id="productCarousel"[^>]*style="display:none"/);
    expect(index).not.toMatch(/<div class="ff-carousel-slot" aria-hidden="true"><\/div>/);
  });
});

// Riff cue: riff-without-asset is a visible non-blocking cue; generate proceeds normally.
describe('riff-without-asset visible cue', () => {
  it('cue markup lives beside the cards, hidden at rest, announced politely', () => {
    expect(index).toMatch(/<p class="ff-riff-cue" id="riffCue" role="status" aria-live="polite" hidden><\/p>/);
    // inside the creative-direction disclosure, not inside the DAM dialog panel
    const dirAt = index.indexOf('id="creativeDirection"');
    const cueAt = index.indexOf('id="riffCue"');
    const damAt = index.indexOf('id="damPanel"');
    expect(dirAt).toBeGreaterThan(-1);
    expect(cueAt).toBeGreaterThan(dirAt);
    expect(cueAt).toBeLessThan(damAt);
  });

  it('checking the riff card refreshes the visible cue; the cue never hides in the dialog', () => {
    expect(chips).toMatch(/function refreshRiffCue\(\)/);
    expect(chips).toMatch(/getElementById\('riffCue'\)/);
    expect(chips).toMatch(/Riff on past content riffs on your staged pick/);
    expect(chips).not.toMatch(/getElementById\('damFlash'\)[^]*riffs on your staged pick/);
  });

  it('cue clears on uncheck, on clear-all, and once a DAM pick is staged', () => {
    expect(chips).toMatch(/if\(slug === 'riff-on-past-content'\)/);
    expect(chips).toMatch(/__clearActiveTheme[^]*refreshRiffCue\(\)/);
    expect(chips).toMatch(/__kodiakRefreshRiffCue/);
  });

  it('removing the staged pick re-shows the cue when riff is still checked', () => {
    // the shared tray-chip remove handler (market-disclosure buildChip, used by DAM
    // staging too) refreshes the cue right after filtering __userAssets.
    expect(market).toMatch(/window\.__userAssets = window\.__userAssets\.filter\(function\(a\)\{ return a\.id!==rec\.id; \}\)/);
    const rmAt = market.indexOf('window.__userAssets = window.__userAssets.filter(function(a){ return a.id!==rec.id; })');
    expect(rmAt).toBeGreaterThan(-1);
    const rmBlock = market.slice(rmAt, rmAt + 600);
    expect(rmBlock).toMatch(/__kodiakRefreshRiffCue/);
    // staging a DAM pick still clears the cue via the same hook.
    expect(chips).toMatch(/__kodiakRefreshRiffCue/);
  });

  it('cue styling is guidance, not an error flag', () => {
    expect(css).toMatch(/\.ff-riff-cue\{[^}]*background:var\(--colors-brand-box-parchment\)/);
    expect(css).toMatch(/\.ff-riff-cue\[hidden\]\{display:none\}/);
    expect(css).not.toMatch(/\.ff-riff-cue\{[^}]*signal-red/);
  });

  it('riff-without-asset never gates generation: the request proceeds, seed_key rides only when staged', () => {
    expect(generate).toMatch(/\.\.\.\(stagedKey \? \{seed_key: stagedKey\} : \{\}\)/);
    const riffAt = chips.indexOf("if(slug === 'riff-on-past-content')");
    expect(riffAt).toBeGreaterThan(-1);
    const riffBlock = chips.slice(riffAt, riffAt + 300);
    expect(riffBlock).toMatch(/refreshRiffCue/);
    expect(riffBlock).not.toMatch(/preventDefault|return false|disabled/);
  });
});
