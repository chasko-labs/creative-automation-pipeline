import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const dataCore = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'), 'utf8');
const generateJs = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');

// The #257 mapping block is dependency-free: eval just the marked slice.
function loadMapping() {
  const start = dataCore.indexOf('// #257 mapping start');
  const end = dataCore.indexOf('// #257 mapping end');
  expect(start, 'mapping start marker').toBeGreaterThan(-1);
  expect(end, 'mapping end marker').toBeGreaterThan(start);
  const window = {};
  const fn = new Function('window', dataCore.slice(start, end));
  fn(window);
  expect(typeof window.featuredFrontierFor, 'helper exposed').toBe('function');
  return window.featuredFrontierFor;
}

describe('market-to-featured-frontier mapping (#257)', () => {
  it('every evaluated market resolves one frontier; unknown returns null', () => {
    const for_ = loadMapping();
    const sf = for_('US-W-SF');
    expect(sf.frontier).toBe('US-CA-BOLINAS');
    expect(sf.items).toContain('Marin goat cheese');
    expect(sf.text).toContain('Bolinas');
    expect(for_('US-W-SEA').frontier).toBe('US-WA-CARNATION');
    expect(for_('US-W-SD').frontier).toBe('US-CA-JULIAN');
    expect(for_('US-W-SD').place).toContain('Julian');
    expect(for_('US-SE-ATL').frontier).toBe('US-GA-SENOIA');
    expect(for_('US-CA-PESCADERO').frontier).toBe('US-CA-PESCADERO');
    expect(for_('US-XX-NOWHERE')).toBeNull();
  });

  it('only the declared Lebanon and Warwick shares are shared', () => {
    const pairs = [...dataCore.matchAll(/"(US-[A-Z0-9\- ]+)": "(US-[A-Z0-9\-]+)"/g)]
      .map((m) => [m[1], m[2]]);
    expect(pairs.length).toBeGreaterThan(70);
    const served = {};
    for (const [k, v] of pairs) {
      if (k !== v) served[v] = (served[v] || []).concat(k);
    }
    const shared = Object.entries(served).filter(([, ks]) => ks.length > 1);
    // two declared shares: Cincinnati+Dayton on Lebanon, and the NYC metro
    // (rollup + three boroughs) on Warwick — one Hudson Valley foodshed.
    expect(shared.length).toBe(2);
    expect(shared[0][0]).toBe('US-OH-LEBANON');
    expect([...shared[0][1]].sort()).toEqual(['US-OH-CINCINNATI', 'US-OH-DAYTON']);
    expect(shared[1][0]).toBe('US-NY-WARWICK');
    expect([...shared[1][1]].sort()).toEqual([
      'US-NE-BRONX',
      'US-NE-BROOKLYN',
      'US-NE-MANHATTAN',
      'US-NE-NYC',
    ]);
    for (const [k, v] of pairs) {
      expect(dataCore).toMatch(new RegExp('"' + v + '": \\{place:'));
    }
  });

  it('Wasatch markets resolve their own close frontiers — no sharing', () => {
    const for_ = loadMapping();
    expect(for_('US-MW-PARKCITY-84098').frontier).toBe('US-UT-OAKLEY');
    expect(for_('US-MW-PARKCITY-84098').place).toContain('Oakley, Utah 84055');
    // #305 replaced the Splendor Valley placeholder with the researched calendar
    expect(for_('US-MW-PARKCITY-84098').text).toContain('tart cherries');
    expect(for_('US-MW-WASATCH').frontier).toBe('US-UT-MIDWAY');
    expect(for_('US-MW-WASATCH-SLC').frontier).toBe('US-UT-GRANTSVILLE');
    expect(for_('US-UT-KAMASVALLEY').frontier).toBe('US-UT-KAMASVALLEY');
  });

  it('generate.js resolves its hint from the mapping, not hardcoded markets', () => {
    for (const code of ['US-W-SF', 'US-W-SEA', 'US-WA-NEAHBAY', 'US-CA-PESCADERO']) {
      expect(generateJs.includes(`.includes('${code}')`), `hardcode ${code}`).toBe(false);
    }
    expect(generateJs.includes('featuredFrontierFor')).toBe(true);
  });
});
