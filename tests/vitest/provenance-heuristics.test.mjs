import { describe, expect, it, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const APP = resolve(root, 'web/kodiak-posts-for-todays-frontier');

function makeEl() {
  return {
    innerHTML: '', textContent: '', value: '', hidden: false, style: {},
    dataset: {}, children: [],
    classList: { add() {}, remove() {}, contains() { return false; } },
    setAttribute() {}, removeAttribute() {}, appendChild() {},
    addEventListener() {}, querySelector() { return null; },
    querySelectorAll() { return []; }, remove() {}, scrollIntoView() {},
  };
}

beforeAll(() => {
  globalThis.document = {
    readyState: 'complete',
    getElementById: () => null,
    createElement: () => makeEl(),
    addEventListener: () => {},
    querySelector: () => null,
    querySelectorAll: () => [],
    head: makeEl(), body: makeEl(),
  };
  globalThis.window = globalThis;
  globalThis.location = { protocol: 'https:', hostname: 'x.example' };
  globalThis.fetch = async () => ({ ok: false });
  globalThis.Image = function () {};
  eval(readFileSync(resolve(APP, 'js/generate.js'), 'utf8'));
});

// G — heuristics how-it-was-done readout on the provenance/rung-badge
// foundation: extended, not reinvented. Same label tables, same prov object,
// honest lines only (absent fields read as "not reported").
describe('provenance heuristics readout', () => {
  it('exposes a pure hook on the shared foundation', () => {
    expect(typeof window.KODIAK_provenanceHeuristics).toBe('function');
    const src = readFileSync(resolve(APP, 'js/generate.js'), 'utf8');
    // single source: exactly one copy of each label table
    expect(src.match(/const RUNG_LABELS = \{/g)).toHaveLength(1);
    expect(src.match(/const ENGINE_LABELS = \{/g)).toHaveLength(1);
    // the panel renders the readout group from the same prov object
    expect(src).toMatch(/prov-heuristics/);
    expect(src).toMatch(/How it was decided/);
    expect(src).toMatch(/provenanceHeuristics\(prov\)/);
  });

  it('reads real prov fields; nothing invented', () => {
    expect(window.KODIAK_provenanceHeuristics({
      rung: 'B',
      engine: 'stability-control-structure',
      seed_selection: 'packshot match',
      seed_source: 'catalog',
      fallthrough_reason: '',
    })).toEqual([
      'Rung: Rung B · Stability restyle',
      'Engine: Control-structure restyle (Stability)',
      'Seed: packshot match via catalog',
      'Fallback: none reported',
    ]);
  });

  it('flags fallback rungs honestly and never guesses gaps', () => {
    expect(window.KODIAK_provenanceHeuristics({
      rung: 'D', fallthrough_reason: 'no packshot; canvas fallback',
    })).toEqual([
      'Rung: Rung D · brand-floor fallback',
      'Engine: not reported',
      'Seed: not reported',
      'Fallback: no packshot; canvas fallback',
    ]);
    expect(window.KODIAK_provenanceHeuristics({})).toEqual([
      'Rung: not reported',
      'Engine: not reported',
      'Seed: not reported',
      'Fallback: none reported',
    ]);
    expect(window.KODIAK_provenanceHeuristics(null)).toEqual(
      window.KODIAK_provenanceHeuristics({}));
  });

  it('surfaces the season pairing only when the backend names it', () => {
    const withPairing = window.KODIAK_provenanceHeuristics({
      recipe: 'Pumpkin Oat Muffins',
      recipe_pairing: { name: 'Pumpkin Oat Muffins', recipe_id: 'pumpkin-oat-muffins', reason: 'fall harvest' },
    }, {});
    expect(withPairing).toContain('Recipe: Pumpkin Oat Muffins');
    expect(withPairing).toContain('Season pairing: Pumpkin Oat Muffins — fall harvest');
    const without = window.KODIAK_provenanceHeuristics({ recipe: 'Trail Stack' }, {});
    expect(without).toContain('Recipe: Trail Stack');
    expect(without.some((l) => l.indexOf('Season pairing') === 0)).toBe(false);
  });

  it('readout styling is token var()s only', () => {
    const css = readFileSync(resolve(APP, 'design/components.css'), 'utf8');
    expect(css).toMatch(/\.provenance \.prov-heur\{[^}]*border-left:3px solid var\(--colors-brand-frontier-green\)/);
  });
});
