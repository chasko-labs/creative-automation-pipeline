import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const timeline = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/ff-timeline.js'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// Progress timeline: slim Setup + 5/6/7 tracker up top with a live line fed
// ONLY by real page events (status mirrors + gate/assets observers). The
// driver invents no events and can never break the page.
describe('progress timeline', () => {
  it('tracker carries Setup + numbered 5/6/7 with honest initial states', () => {
    expect(index).toMatch(/id="progressTimeline"/);
    expect(index).toMatch(/data-node="setup" data-state="active"/);
    expect(index).toMatch(/data-node="preview" data-state="todo"/);
    expect(index).toMatch(/data-node="generate" data-state="locked"/);
    expect(index).toMatch(/id="timelineNote" role="status" aria-live="polite"/);
  });

  it('preview stays greyed until Create is hit, never lights on typing', () => {
    // greyed = todo while sampleStatus is empty (typing only fills the brief);
    // first status text (composing) flips it active, ready flips it done.
    expect(timeline).toMatch(/createHit/);
    expect(timeline).toMatch(/'preview', previewReady \? 'done' : \(createHit \? 'active' : 'todo'\)/);
    expect(timeline).not.toMatch(/briefFull \? 'active' : 'todo'\)/);
  });

  it('driver mirrors real events only and never throws into the page', () => {
    expect(timeline).toMatch(/getElementById\('sampleStatus'\)/);
    expect(timeline).toMatch(/getElementById\('generateCampaignStatus'\)/);
    expect(timeline).toMatch(/MutationObserver/);
    expect(timeline).not.toMatch(/connecting to dynamodb|stable diffusion|dampack/i);
  });

  it('header, timeline, and cards stay equisize at every breakpoint', () => {
    // .wrap baseline is 1100px with no ultrawide growth: header row and
    // timeline ride the same 1100px cap so neither reads wider than the cards.
    expect(css).toMatch(/\.kodiak-header \.header__inner\{[^}]*width:min\(1100px/);
    expect(css).toMatch(/\.ff-timeline\.ff-timeline--under-header\{width:min\(1100px/);
    expect(css).not.toMatch(/\.kodiak-header \.header__inner\{width:min\(1440px/);
    expect(css).not.toMatch(/\.ff-timeline\.ff-timeline--under-header\{width:min\(1440px/);
    expect(css).not.toMatch(/min\(1064px/);
  });

  it('headline plate shares the logo row and shrinks, never its own line', () => {
    // the plate is allowed to be smaller — no full-width wrap under the logo.
    expect(css).not.toMatch(/\.kodiak-header \.kodiak-headline-plate\{flex:1 1 100%\}/);
    expect(css).toMatch(/\.kodiak-header \.kodiak-headline-plate\{flex:1 1 auto;min-width:0/);
  });

  it('tracker styling reuses brand tokens', () => {
    expect(css).toMatch(/\.ff-timeline-steps li\[data-state="active"\][^}]*color:var\(--chocolate\)/);
    expect(css).toMatch(/\.ff-timeline-note:empty::before/);
  });

  it('driver loads after the sections it observes', () => {
    const campaign = index.indexOf('js/campaign-sections.js');
    const driver = index.indexOf('js/ff-timeline.js');
    expect(campaign).toBeGreaterThan(-1);
    expect(driver).toBeGreaterThan(campaign);
  });
});
