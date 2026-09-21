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
    expect(line('US-MW-BOISE', '')).toBeNull();
    expect(line('US-MW-BOISE', 'Froctober')).toBeNull();
    expect(loadSeasonLine(null)('US-MW-BOISE', 'October')).toBeNull();
    expect(loadSeasonLine([])('US-MW-BOISE', 'October')).toBeNull();
  });

  it('resolves seasons and holidays to their representative month', () => {
    const line = loadSeasonLine(STUB);
    const fall = line('US-MW-BOISE', 'Fall');
    expect(fall.ingredient).toBe('winter squash');
    expect(fall.moment).toBe('Thanksgiving / winter holidays');
    // Halloween is October's seat: same October ingredient + moment.
    const halloween = line('US-MW-BOISE', 'Halloween');
    expect(halloween.ingredient).toBe('winter squash');
    expect(halloween.moment).toBe('Thanksgiving / winter holidays');
    expect(line('US-MW-BOISE', 'Spring').ingredient).toBeNull();
  });

  it('never names a moment outside its months', () => {
    const line = loadSeasonLine(STUB);
    const r = line('US-MW-BOISE', '2026-10');
    expect(r.text).not.toContain('harvest fair');
  });

  it('grounds Dayton/Cincinnati in the shared Lebanon calendar', () => {
    const m = pairsSrc.match(/window\.KODIAK_FRONTIER_PAIRS\s*=\s*(\[[\s\S]*\]);/);
    expect(m, 'web pairs book parses').not.toBeNull();
    const line = loadSeasonLine(JSON.parse(m[1]));
    for (const market of ['US-OH-DAYTON', 'US-OH-CINCINNATI']) {
      const sept = line(market, 'September');
      expect(sept.text).toContain('Lebanon');
      const tween = line(market, 'Halloween');
      expect(tween.ingredient).toBe('apples');
      expect(tween.moment).toContain('Halloween');
      expect(tween.text).not.toMatch(/15-hour/);
    }
  });
});
