import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const timeline = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/ff-timeline.js'), 'utf8');

// #283 — the tracker advances every node with truthful per-stage lines: stage
// transitions derive ONLY from observed status texts, elapsed is measured with
// Date.now() between the real opening and closing lines. No invented theater.
describe('timeline live stages (#283)', () => {
  it('preview open/close lines drive the clock, ready reports measured seconds', () => {
    expect(timeline).toMatch(/function onSampleText/);
    expect(timeline).toMatch(/tPreviewStart = Date\.now\(\)/);
    expect(timeline).toMatch(/Preview ready.*in.*s.*Generate Campaign unlocked, full campaign is next/);
  });

  it('full-campaign start/finish lines drive the generate node with measured seconds', () => {
    expect(timeline).toMatch(/function onGenStatusText/);
    expect(timeline).toMatch(/generating full campaign/i);
    expect(timeline).toMatch(/campaign created/i);
    expect(timeline).toMatch(/is next: review, then download the pack/);
  });

  it('failed runs re-open the gate for retry instead of sticking on done', () => {
    expect(timeline).toMatch(/timed out\|could not generate\|needs the hosted backend/);
  });

  it('done states persist across later syncs; no timer theater of its own', () => {
    expect(timeline).toMatch(/generateDone \? 'done' : 'active'/);
    expect(timeline).not.toMatch(/setInterval|setTimeout/);
  });
});
