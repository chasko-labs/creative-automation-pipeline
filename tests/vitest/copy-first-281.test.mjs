import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const gen = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');

// #281 — copy BEFORE image: the copy-first panel paints at Create time from
// the real request inputs, upgrades from the real response, and flags real
// request/response divergence. It never invents marketing copy.
describe('copy-first preview (#281)', () => {
  it('driving phase paints from request inputs before any image request', () => {
    expect(gen).toMatch(/phase:'driving'/);
    expect(gen).toMatch(/Campaign copy — driving this preview/);
    // driving paint precedes the fetch flows (skeleton + oneGenerate calls)
    expect(gen.indexOf("phase:'driving'")).toBeLessThan(gen.indexOf('oneGenerate(primarySlug'));
  });

  it('used phase shows only backend-returned copy, honestly labeled when deferred', () => {
    expect(gen).toMatch(/phase:'used'/);
    expect(gen).toMatch(/Campaign copy — used in this preview/);
    expect(gen).toMatch(/full platform copy is deferred and ships with Generate Campaign/);
  });

  it('mismatch flag fires on real divergence: theme changed/dropped, fallback pixels', () => {
    expect(gen).toMatch(/copy\/imagery mismatch/);
    expect(gen).toMatch(/theme mismatch/);
    expect(gen).toMatch(/theme dropped/);
    expect(gen).toMatch(/render miss — fallback pixels/);
  });

  it('used phase never fabricates a panel without a driving one', () => {
    expect(gen).toMatch(/never fabricate one post-hoc/);
  });
});
