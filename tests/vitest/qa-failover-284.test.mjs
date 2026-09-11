import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const sections = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/campaign-sections.js'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// #284 — QA-failed runs render an honest fail state (Try again + run summary)
// instead of weak results; fallback pixels are labeled on the tile.
describe('qa failover (#284)', () => {
  it('fail box offers retry plus a copyable factual run summary', () => {
    expect(sections).toMatch(/function paintFailBox/);
    expect(sections).toMatch(/Try again/);
    expect(sections).toMatch(/Copy run summary/);
    expect(sections).toMatch(/Kodiak Cakes campaign run summary/);
  });

  it('wall-timeout fallback is named a render miss, passing runs clear the box', () => {
    expect(sections).toMatch(/Render miss \(wall timeout\) — fallback shown below, not the campaign/);
    expect(sections).toMatch(/paintFailBox\(null\)/);
    expect(sections).toMatch(/kind:'fallback'/);
    expect(sections).toMatch(/kind:'error'/);
  });

  it('carousel labels fallback tiles with their real source', () => {
    expect(sections).toMatch(/renderCampaignCarousel\(renders, source\)/);
    expect(sections).toMatch(/ff-fallback-flag/);
    expect(sections).toMatch(/render miss — fallback pixels, not the campaign/);
  });

  it('fail styling is sharp-bordered, never success-styled', () => {
    expect(css).toMatch(/\.ff-failbox\{[^}]*border:1px solid var\(--colors-brand-signal-red\)/);
    expect(css).toMatch(/\.ff-fallback-flag\{/);
  });
});
