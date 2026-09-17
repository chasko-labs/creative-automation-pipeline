import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const dataCore = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'), 'utf8');
const pairsSrc = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/recipes-frontier-pairs.js'), 'utf8');

// Eval the marked frontier-season slice with a stubbed pairs book.
function loadSeasonLine(stubPairs) {
  const start = dataCore.indexOf('// #frontier-season start');
  const end = dataCore.indexOf('// #frontier-season end');
  expect(start, 'season start marker').toBeGreaterThan(-1);
  expect(end, 'season end marker').toBeGreaterThan(start);
  const window = { KODIAK_FRONTIER_PAIRS: stubPairs };
  const fn = new Function('window', dataCore.slice(start, end));
  fn(window);
  expect(typeof window.frontierSeasonLine, 'helper exposed').toBe('function');
  return window.frontierSeasonLine;
}

const STUB = [
  { market: 'US-MW-BOISE',
    frontier: { place: 'Kuna, ID', market: 'US-ID-KUNA' },
    monthly: { '2026-10': 'winter squash', '2026-09': 'peppers' },
    moments: [
      { moment: 'Sweet corn + harvest fair (Sep)', status: 'confirmed', months: [9] },
      { moment: 'Thanksgiving / winter holidays', status: 'proposed', months: [1, 3, 10, 11] },
    ] },
];

describe('frontier season line', () => {
  it('composes place + ingredient + month-matching moment', () => {
    const line = loadSeasonLine(STUB);
    const r = line('US-MW-BOISE', 'October');
    expect(r.place).toBe('Kuna, ID');
    expect(r.ingredient).toBe('winter squash');
    expect(r.moment).toBe('Thanksgiving / winter holidays');
    expect(r.text).toContain('Kuna, ID');
    expect(r.text).toContain('winter squash in season');
  });

  it('accepts YYYY-MM keys and prefers confirmed moments', () => {
    const line = loadSeasonLine(STUB);
    const r = line('US-MW-BOISE', '2026-09');
    expect(r.ingredient).toBe('peppers');
    expect(r.moment).toBe('Sweet corn + harvest fair (Sep)');
    expect(r.momentStatus).toBe('confirmed');
  });

  it('returns null for unknown markets, seasons, and missing pairs', () => {
    const line = loadSeasonLine(STUB);
    expect(line('US-XX-NOWHERE', 'October')).toBeNull();
    expect(line('US-MW-BOISE', 'Fall')).toBeNull();
    expect(line('US-MW-BOISE', '')).toBeNull();
    expect(loadSeasonLine(null)('US-MW-BOISE', 'October')).toBeNull();
    expect(loadSeasonLine([])('US-MW-BOISE', 'October')).toBeNull();
  });

  it('never names a moment outside its months', () => {
    const line = loadSeasonLine(STUB);
    const r = line('US-MW-BOISE', '2026-10');
    expect(r.text).not.toContain('harvest fair');
  });
});
