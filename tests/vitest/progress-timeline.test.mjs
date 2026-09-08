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
    expect(index).toMatch(/data-node="generate" data-state="locked"/);
    expect(index).toMatch(/id="timelineNote" role="status" aria-live="polite"/);
  });

  it('driver mirrors real events only and never throws into the page', () => {
    expect(timeline).toMatch(/getElementById\('sampleStatus'\)/);
    expect(timeline).toMatch(/getElementById\('generateCampaignStatus'\)/);
    expect(timeline).toMatch(/MutationObserver/);
    expect(timeline).not.toMatch(/connecting to dynamodb|stable diffusion|dampack/i);
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
