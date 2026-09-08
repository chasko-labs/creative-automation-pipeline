import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const core = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'), 'utf8');

// #278 — market picker type-ahead: typing filters the 73-option listbox by
// city/state/zip substring, keyboard navigable, selection still flows through
// the existing select() path (snapshot/persist/brief untouched).
describe('market filter (#278)', () => {
  it('filter input lives in the panel, wired to the listbox', () => {
    expect(index).toMatch(/id="marketFilter"/);
    expect(index).toMatch(/aria-controls="marketListbox"/);
    expect(index).toMatch(/placeholder="Filter by city, state, or zip"/);
  });

  it('filter matches substrings across name, place, market id, zip, state', () => {
    expect(core).toMatch(/function matchesFilter/);
    expect(core).toMatch(/shortName\(p\)\+' '\+\(p\.place\|\|''\)\+' '\+p\.market\+' '\+\(p\.zip\|\|''\)\+' '\+stateOf\(p\)/);
    expect(core).toMatch(/split\(\/\\s\+\/\)\.every/);
  });

  it('keyboard nav: arrows move, enter selects, escape clears and closes', () => {
    expect(core).toMatch(/ArrowDown/);
    expect(core).toMatch(/ArrowUp/);
    expect(core).toMatch(/key==='Enter'/);
    expect(core).toMatch(/key==='Escape'/);
    expect(core).toMatch(/aria-activedescendant/);
  });

  it('selection still flows through select() into #locality with bubbles', () => {
    expect(core).toMatch(/loc\.dispatchEvent\(new Event\('change', \{bubbles:true\}\)\)/);
  });

  it('empty filter result is honest, selection stays put', () => {
    expect(core).toMatch(/ff-market-empty/);
    expect(core).toMatch(/No markets match/);
  });
});
