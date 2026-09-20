import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const core = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'),
  'utf8',
);
const contracts = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/frontier-contracts.js'),
  'utf8',
);
const generate = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'),
  'utf8',
);
const globals = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/globals.d.ts'),
  'utf8',
);

// The three type specimens cited on slides: each asserts the teaching marker
// sits next to the construct it documents, so a cleanup cannot silently
// remove the lesson without breaking the suite.
describe('type specimens', () => {
  it('intersection: MarketCoord rows are identifiable AND located', () => {
    expect(core).toMatch(/teaching note \(frontier coords/);
    expect(core).toMatch(
      /@typedef \{Pick<PlaceEntry,'market'> & \{lat: number, lon: number\}\} MarketCoord/,
    );
    expect(core).toMatch(/@type \{MarketCoord\[\]\}/);
  });

  it('overloads: onLocality answers the DOM and direct callers', () => {
    expect(core).toMatch(/teaching note \(frontier calling conventions/);
    expect(core).toMatch(/@overload/);
    expect(core).toMatch(/function onLocality\(_ev\)/);
  });

  it('typed this: the keydown handler reads its own element', () => {
    expect(core).toMatch(/teaching note \(frontier handlers/);
    expect(core).toMatch(/@this \{HTMLInputElement\}/);
    expect(core).toMatch(/this\.value=''/);
  });

  it('truthiness first: adoptPlatformMatrix rejects empties up front', () => {
    expect(contracts).toMatch(/teaching note \(frontier truthiness/);
    expect(contracts).toMatch(/!ratios \|\| typeof ratios/);
  });

  it('typeof isolated: tileSizeFromClass narrows unknown to string', () => {
    expect(contracts).toMatch(/teaching note \(frontier typeof/);
    expect(contracts).toMatch(/typeof cls === 'string' &&/);
  });

  it('closed union: CaptionProvider names every render state', () => {
    expect(contracts).toMatch(/teaching note \(frontier closed unions/);
    expect(contracts).toMatch(/'community-review'\|'pending-live'\|'pending'/);
    expect(core).toMatch(/@type \{CaptionProvider\}/);
  });

  it('intersection: MarketCoord rows are identifiable AND located', () => {
    expect(core).toMatch(/teaching note \(frontier coords/);
    expect(core).toMatch(/Pick<PlaceEntry,'market'> & \{lat: number/);
    expect(core).toMatch(/@type \{MarketCoord\[\]\}/);
  });

  it('assignments widen reads: pick is null until the loop assigns it', () => {
    expect(core).toMatch(/teaching note \(frontier assignments/);
    expect(core).toMatch(/pick = mo/);
  });

  it('control flow: the early return is the narrowing', () => {
    expect(core).toMatch(/teaching note \(frontier control flow/);
    expect(core).toMatch(/if\(!p\) return/);
  });

  it('instanceof replaces the cast on the mouseover target', () => {
    expect(core).toMatch(/teaching note \(frontier instanceof/);
    expect(core).toMatch(/e\.target instanceof Element/);
  });

  it('never: empty literals infer never until annotated', () => {
    expect(core).toMatch(/teaching note \(frontier never/);
    expect(core).toMatch(/'market':\[\], 'featured-frontier':\[\]/);
  });

  it('totality: RATIO_LABELS is keyed by the whole TileSize union', () => {
    expect(generate).toMatch(/teaching note \(frontier totality/);
    expect(generate).toMatch(/Object<TileSize,/);
  });

  it('totality: RATIO_LABELS carries every TileSize incl blog (5-tile preview)', () => {
    const m = generate.match(/const RATIO_LABELS = \{([\s\S]*?)\};/);
    expect(m, 'missing RATIO_LABELS literal').not.toBeNull();
    for (const size of ['1x1', '4x5', '9x16', '16x9', '2x3', 'blog']) {
      expect(m[1]).toContain(`'${size}':`);
    }
    expect(m[1]).toMatch(/'blog':\s*\{name:'Blog',\s*cls:'r-blog'\}/);
  });

  it('generics: the localize cache instantiates both Map slots', () => {
    expect(core).toMatch(/teaching note \(frontier generics/);
    expect(core).toMatch(/@type \{Map<string,string>\}/);
    expect(core).toMatch(/_locCache\.get\(key\) \?\? null/);
  });

  it('signatures: parameter names are positional, never nominal', () => {
    expect(core).toMatch(/teaching note \(frontier signatures/);
    expect(core).toMatch(/callers pass o and opts\[i\]/);
  });

  it('every-path returns: the fallthrough is the missing else', () => {
    expect(core).toMatch(/teaching note \(frontier every-path returns/);
    expect(core).toMatch(/fallthrough return ''/);
  });

  it('aliases: PlaceEntry names the shape once for many signatures', () => {
    expect(globals).toMatch(/teaching note \(frontier aliases/);
    expect(globals).toMatch(/six\n\/\/ signatures reuse it/);
  });
});
