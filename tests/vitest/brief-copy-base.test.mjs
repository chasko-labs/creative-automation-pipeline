import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const gen = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');

// Extract the self-contained briefCopyBase + its marker table and eval it.
function loadBase() {
  const start = gen.indexOf('var BRIEF_COPY_MARKERS');
  const end = gen.indexOf('try{ window.KODIAK_briefCopyBase');
  expect(start).toBeGreaterThan(-1);
  expect(end).toBeGreaterThan(start);
  const fn = new Function(`${gen.slice(start, end)}; return briefCopyBase;`);
  return fn();
}

const NYC_BRIEF = '— market: New York City · season: September · ecology: Bodega coffee, oatmeal cup on subway platform · frontier: Warwick, NY (Hudson Valley, apples/onions/black dirt) — Black-dirt onion season (Jul-Sep) · in-season: apples (savory onion cheddar bakes, sweet corn)';

describe('briefCopyBase (generate.js)', () => {
  it('humanizes pure scaffolding to ecology + ingredient', () => {
    const base = loadBase()(NYC_BRIEF);
    expect(base).not.toMatch(/market:|frontier:/);
    expect(base).not.toContain('Black-dirt onion season');
    expect(base).toContain('Bodega coffee');
    expect(base).toContain('apples');
  });

  it('passes human copy through and keeps user ideas', () => {
    const base = loadBase();
    expect(base('Bodega mornings fuel the hustle')).toBe('Bodega mornings fuel the hustle');
    expect(base('sea otters · market: Cincinnati')).toContain('sea otters');
    expect(base('sea otters · market: Cincinnati')).not.toMatch(/market:/);
  });

  it('returns empty when nothing human is available', () => {
    const base = loadBase();
    expect(base('market: X · season: Fall')).toBe('');
    expect(base('')).toBe('');
    expect(base(null)).toBe('');
  });
});
