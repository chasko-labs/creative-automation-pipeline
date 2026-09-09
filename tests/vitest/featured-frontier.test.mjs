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
    expect(sf.frontier).toBe('US-CA-PESCADERO');
    expect(sf.items).toContain('Castroville artichokes');
    expect(sf.seasons).toContain('Mar-Jun');
    expect(sf.text).toContain('Castroville artichokes');
    expect(for_('US-W-SEA').frontier).toBe('US-WA-NEAHBAY');
    expect(for_('US-W-SD').frontier).toBe('US-CA-JULIAN');
    expect(for_('US-W-SD').place).toContain('Julian');
    expect(for_('US-SE-ATL').frontier).toBe('US-SE-SANDERSVILLE');
    expect(for_('US-CA-PESCADERO').frontier).toBe('US-CA-PESCADERO');
    expect(for_('US-XX-NOWHERE')).toBeNull();
  });

  it('generate.js resolves its hint from the mapping, not hardcoded markets', () => {
    for (const code of ['US-W-SF', 'US-W-SEA', 'US-WA-NEAHBAY', 'US-CA-PESCADERO']) {
      expect(generateJs.includes(`.includes('${code}')`), `hardcode ${code}`).toBe(false);
    }
    expect(generateJs.includes('featuredFrontierFor')).toBe(true);
  });
});
