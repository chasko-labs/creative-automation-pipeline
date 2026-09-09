import { describe, expect, it, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const APP = resolve(root, 'web/kodiak-posts-for-todays-frontier');

function loadGuard() {
  globalThis.window = globalThis;
  const src = readFileSync(resolve(APP, 'js/brand-guard.js'), 'utf8');
  eval(src);
}

beforeAll(() => { loadGuard(); });

// KODIAK-forbidden-in-copy law: bare KODIAK never ships in customer-visible
// copy. Allowed: "Kodiak Cakes", "Kodiak Park City", #kodiakcakes-style
// hashtags. Offending examples below are real strings that shipped in the
// frontend before the fix (Atlanta's frontier sister Sandersville, Pescadero,
// Neah Bay, Tularosa, Seattle cue, SKU list, caption fallback).
describe('KODIAK-forbidden-in-copy law', () => {
  it('flags the real Atlanta-sister offending example', () => {
    expect(window.KODIAK_hasBareKodiak(
      'KODIAK® Sandersville frontier — Georgia pecans over Buttermilk Power Cakes, kaolin-belt farm stand to your griddle, 14g protein'
    )).toBe(true);
  });

  it('flags the other real offending examples', () => {
    const offenders = [
      'KODIAK® frontier for Bay Area urban folks to see their hinterland — protein-packed whole grains for your Pescadero coast. Nourishment for Today\'s Frontier',
      'KODIAK® Neah Bay frontier — huckleberry compote over Buttermilk Power Cakes, Makah water meets Wasatch grain',
      'KODIAK® Keep It Wild — protein-packed whole grains for your Tularosa frontier. Nourishment for Today\'s Frontier',
      'Coffee beside KODIAK® flapjacks, evergreen, rain-morning griddle, bulk Costco Family Size',
      'KODIAK POWER CUPS® Protein Oatmeal Cup',
      'KODIAK® — Nourishment for Today\'s Frontier',
      'KODIAK campaign copy — hit Create first',
      'KODIAK® composed hero',
    ];
    for (const s of offenders) expect(window.KODIAK_hasBareKodiak(s), s).toBe(true);
  });

  it('passes the allowed forms', () => {
    const allowed = [
      'Kodiak Cakes frontier for your Pescadero coast',
      'Kodiak Park City example — Power Cakes flapjacks for a Wasatch Back morning',
      '#kodiakcakes #keepitwild protein mornings',
      'Georgia pecan frontier — 14 grams to start your day',
    ];
    for (const s of allowed) expect(window.KODIAK_hasBareKodiak(s), s).toBe(false);
  });

  it('cleans the mark without inventing translations', () => {
    expect(window.KODIAK_brandClean(
      'KODIAK® Sandersville frontier — Georgia pecans over Buttermilk Power Cakes, kaolin-belt farm stand to your griddle, 14g protein'
    )).toBe(
      'Kodiak Cakes Sandersville frontier — Georgia pecans over Buttermilk Power Cakes, kaolin-belt farm stand to your griddle, 14g protein'
    );
    // the cleaner rewrites only the brand mark — surrounding words (even
    // all-caps leftovers from a legacy string) are never reworded.
    expect(window.KODIAK_brandClean('KODIAK POWER CUPS® Protein Oatmeal Cup'))
      .toBe('Kodiak Cakes POWER CUPS® Protein Oatmeal Cup');
    expect(window.KODIAK_brandClean('#kodiakcakes mornings')).toBe('#kodiakcakes mornings');
    expect(window.KODIAK_brandClean('Keep It Wild — Kodiak Cakes campaign')).toBe('Keep It Wild — Kodiak Cakes campaign');
  });

  it('no bare KODIAK remains in frontend copy string literals', () => {
    const files = [
      'js/data-core.js',
      'js/generate.js',
      'js/campaign-sections.js',
      'index.html',
      'data/localization/store-finder-markets.json',
    ];
    // Scan quoted string literals (the only thing that can paint customer
    // copy). Not copy, so explicitly allowlisted with reasons:
    // - window.KODIAK_* identifiers and __kodiak hooks: code, never painted.
    // - KODIAK-CAKES-… ISO filenames / download names: file names, not copy.
    // - canvas fillText('KODIAK®…') lockups in drawAd: baked logo lockups,
    //   the one standing-law exception (copy ships as sidecar, never baked).
    // - brief.yaml brand:/file fields: machine-readable export metadata.
    // - <title>/<meta>/manifest/logo-alt lines: chrome lockups, not copy.
    // - .includes('KODIAK') brand-hint check: code predicate, never painted.
    const ALLOW = /KODIAK_[A-Z_]+|__kodiak|__requestedSku|__last[A-Za-z]+|__active[A-Za-z]+|__sync[A-Za-z]+|KODIAK-CAKES-|Kodiak-Cakes-copy|fillText\(|^['"]KODIAK®['"]$|KODIAK® — Nourishment|KODIAK® • kodiakcakes|design guide audience|KODIAK (generate|campaign UI)|brand:\s*|campaign_name:|headline\.includes|['"]KODIAK['"]|<title>|kodiak-version|kodiak-coach-url|kodiak-gate|kodiak_sans|kodiak-header|kodiak-topstrip|application\/ld\+json|webmcp|KODIAK Posts|KODIAK® Posts for Today|100% WHOLE GRAINS|Bear silhouette lockup|wordmark beside bear|assets\/kodiak-|Kodiak Cakes — Park City|data\/products\/kodiak-|kodiak-full-catalog|kodiak-posts-for-todays-frontier|web\/kodiak|brands\/kodiak/;
    for (const f of files) {
      const s = readFileSync(resolve(APP, f), 'utf8');
      const lits = s.match(/('(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`)/g) || [];
      for (const lit of lits) {
        if (ALLOW.test(lit)) continue;
        // Slugs, keys, paths and single tokens are code, never prose copy.
        if (!/\s/.test(lit.slice(1, -1))) continue;
        expect(window.KODIAK_hasBareKodiak(lit), `${f}: bare KODIAK in copy literal: ${lit.slice(0, 120)}`).toBe(false);
      }
    }
  });

  it('copy renderers enforce the law at paint time', () => {
    for (const f of ['js/campaign-sections.js', 'js/generate.js', 'js/data-core.js']) {
      const s = readFileSync(resolve(APP, f), 'utf8');
      expect(s, f).toMatch(/KODIAK_brandClean/);
    }
    expect(readFileSync(resolve(APP, 'index.html'), 'utf8')).toMatch(/js\/brand-guard\.js/);
  });
});
