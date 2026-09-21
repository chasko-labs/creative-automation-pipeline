import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const core = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'), 'utf8');
const disclosure = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/market-disclosure.js'), 'utf8');
const langs = JSON.parse(readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/data/localization/market-languages.json'), 'utf8'));
const finder = JSON.parse(readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/data/localization/store-finder-markets.json'), 'utf8'));

// #279 — Bay Area normalization: SF + San Jose urban markets, Pescadero +
// Castroville rural featured frontiers. 73 -> 75 places with full companions.
// Ohio (Cincinnati/Dayton/Lebanon) + Oceanside adds took it to 79; Lebanon
// then left the picker (shared Cincinnati+Dayton frontier, not a market):
// 79 -> 78 places.
describe('bay area markets (#279)', () => {
  it('places holds 78 unique markets including the Bay Area adds', () => {
    const ids = core.match(/\{market:"([^"]*)"/g).map(s => s.slice(9, -1));
    expect(ids.length).toBe(78);
    expect(new Set(ids).size).toBe(ids.length);
    expect(core).toMatch(/market:"US-W-SF"/);
    expect(core).toMatch(/market:"US-W-SANJOSE"/);
    expect(core).toMatch(/market:"US-CA-CASTROVILLE"/);
    expect(core).toMatch(/market:"US-OH-CINCINNATI"/);
    expect(core).toMatch(/market:"US-OH-DAYTON"/);
    expect(core).not.toMatch(/\{market:"US-OH-LEBANON"/);
  });

  it('urban markets pair to their own nearby rural featured frontiers', () => {
    expect(core).toMatch(/"US-W-SF": "US-CA-BOLINAS"/);
    expect(core).toMatch(/"US-W-SANJOSE": "US-CA-BRENTWOOD"/);
    expect(core).toMatch(/"US-CA-CASTROVILLE": "US-CA-CASTROVILLE"/);
    expect(core).toMatch(/"US-CA-CASTROVILLE": \{place:"Castroville/);
    expect(core).toMatch(/"US-CA-BOLINAS": \{place:"Bolinas/);
    expect(core).toMatch(/"US-CA-BRENTWOOD": \{place:"Brentwood/);
  });

  it('new markets carry coords in both tables', () => {
    expect(core).toMatch(/SANJOSE.*37\.3382/);
    expect(core).toMatch(/CASTROVILLE.*36\.7656/);
    expect(disclosure).toMatch(/'US-W-SANJOSE':\{lat:37\.3382,lon:-121\.8863\}/);
    expect(disclosure).toMatch(/'US-CA-CASTROVILLE':\{lat:36\.7656,lon:-121\.7588\}/);
  });

  it('language + store-finder companions cover all 76', () => {
    expect(langs.markets.length).toBe(76);
    expect(langs.metadata.total_markets).toBe(76);
    expect(finder.markets.length).toBe(76);
    for (const m of ['US-W-SF', 'US-W-SANJOSE', 'US-CA-CASTROVILLE']) {
      expect(langs.markets.map(x => x.market)).toContain(m);
    }
  });
});
