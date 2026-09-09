import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const dataCore = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'), 'utf8');
const engine = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/season-flavors.js'), 'utf8');
const generateJs = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');

const SEASONS = ['January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
  'Spring', 'Summer', 'Fall', 'Winter', 'New Year', 'Valentine\u2019s Day',
  'Easter', 'Memorial Day', 'Fourth of July', 'Labor Day', 'Halloween',
  'Thanksgiving', 'Christmas', 'Holiday season', ''];

function loadEngine() {
  const start = dataCore.indexOf('// #257 mapping start');
  const end = dataCore.indexOf('// #257 mapping end');
  expect(start, 'mapping start marker').toBeGreaterThan(-1);
  const win = {};
  new Function('window', dataCore.slice(start, end))(win);
  const places = [...dataCore.matchAll(/\{market:"([^"]+)", place:"([^"]+)"/g)]
    .map((m) => ({ market: m[1], place: m[2] }));
  expect(places.length, 'places parsed').toBeGreaterThan(70);
  const scope = { window: win, places, featuredFrontierFor: win.featuredFrontierFor };
  const fn = new Function('window', 'places', 'featuredFrontierFor',
    `${engine}\nreturn window.seasonFlavorFor;`);
  // engine file sets window.seasonFlavorFor on the passed window
  const flavorFor = fn.call(scope, win, places, win.featuredFrontierFor);
  return { flavorFor, places };
}

describe('season flavors — 100% market x season coverage', () => {
  it('every market x every season resolves a non-empty line with a tier', () => {
    const { flavorFor, places } = loadEngine();
    let curated = 0, frontier = 0, archetype = 0;
    for (const p of places) {
      for (const s of SEASONS) {
        const r = flavorFor(p.market, s);
        expect(r && typeof r.text, `${p.market} x ${s || 'year-round'}`).toBe('string');
        expect(r.text.length, `${p.market} x ${s || 'year-round'}`).toBeGreaterThan(20);
        expect(['curated', 'frontier', 'archetype']).toContain(r.source);
        if (r.source === 'curated') curated++;
        else if (r.source === 'frontier') frontier++;
        else archetype++;
      }
    }
    // curated = researched calendars (7 frontiers + market bases); frontier =
    // the 1:1 close-frontier tier that replaced sharing — the bulk of the matrix
    expect(curated, 'curated lines').toBeGreaterThan(100);
    expect(frontier, 'frontier lines').toBeGreaterThan(1000);
    // unknown markets fall to the archetype tier, never empty
    const unknown = flavorFor('US-XX-NOWHERE', 'March');
    expect(unknown.source).toBe('archetype');
    expect(unknown.text.length).toBeGreaterThan(20);
  });

  it('spot checks: Park City September peaches, Neah Bay August huckleberry', () => {
    const { flavorFor } = loadEngine();
    const pc = flavorFor('US-MW-PARKCITY-84098', 'September');
    expect(pc.text).toMatch(/peach/i);
    expect(pc.frontier).toBe('US-UT-OAKLEY');
    const nb = flavorFor('US-WA-NEAHBAY', 'August');
    expect(nb.text).toMatch(/huckleberry/i);
    expect(nb.source).toBe('curated');
    const sd = flavorFor('US-W-SD', 'September');
    expect(sd.frontier).toBe('US-CA-JULIAN');
    expect(sd.text).toMatch(/apple/i);
    // 1:1 frontiers surface in the readout: Burlington names Shelburne, not Georgia
    const burl = flavorFor('US-NE-BURLINGTON', 'October');
    expect(burl.frontier).toBe('US-VT-SHELBURNE');
    expect(burl.text).toMatch(/Shelburne/);
    expect(burl.text).not.toMatch(/Georgia|Sandersville/);
    const atl = flavorFor('US-SE-ATL', 'July');
    expect(atl.frontier).toBe('US-GA-SENOIA');
    expect(atl.text).toMatch(/Senoia/);
  });

  it('readout is season-reactive and the engine ships with the page', () => {
    expect(generateJs).toMatch(/window\.seasonFlavorFor\(market, season\)/);
    expect(generateJs).toMatch(/id==='seasonalSelect'\) updateLocalFlavor/);
    expect(index).toMatch(/js\/season-flavors\.js\?v=/);
  });
});
