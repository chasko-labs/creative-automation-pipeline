import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const web = (...parts) =>
  resolve(root, 'web/kodiak-posts-for-todays-frontier', ...parts);

// frontier-contracts.js is a classic browser script (IIFE, no exports), so
// eval it with a fake window and read the validators back off that object.
// Fast, no browser: guards the contract source itself.
const src = readFileSync(web('js/frontier-contracts.js'), 'utf8');
const fakeWindow = {};
new Function('window', src)(fakeWindow);
const {
  KODIAK_tileSizeFromClass: tileSizeFromClass,
  KODIAK_tileSizeFromString: tileSizeFromString,
  KODIAK_adoptPlatformMatrix: adoptPlatformMatrix,
  KODIAK_localeFromLang: localeFromLang,
  KODIAK_parseBuildId: parseBuildId,
  KODIAK_TILE_ORDER: TILE_ORDER,
} = fakeWindow;

describe('frontier contracts surface', () => {
  it('exposes every validator the renderers consume', () => {
    for (const [name, fn] of Object.entries({
      tileSizeFromClass,
      tileSizeFromString,
      adoptPlatformMatrix,
      localeFromLang,
      parseBuildId,
    })) {
      expect(fn, `${name} missing off window`).toEqual(expect.any(Function));
    }
    expect(Array.isArray(TILE_ORDER)).toBe(true);
  });

  it('TILE_ORDER runs shortest to tallest', () => {
    expect(TILE_ORDER).toEqual(['blog', '1x1', '16x9', '4x5', '9x16']);
  });
});

describe('tileSizeFromClass', () => {
  it.each([
    ['r-blog', 'blog'],
    ['r-1x1', '1x1'],
    ['r-16x9', '16x9'],
    ['r-4x5', '4x5'],
    ['r-9x16', '9x16'],
    ['r-2x3', '2x3'],
    ['tile render-tile r-4x5', '4x5'],
  ])('%s -> %s', (cls, size) => {
    expect(tileSizeFromClass(cls)).toBe(size);
  });

  it.each([['r-3x4'], ['r-'], [''], [null], [undefined], [[42]]])(
    '%s is a stranger -> null',
    (cls) => {
      expect(tileSizeFromClass(cls)).toBeNull();
    },
  );
});

describe('tileSizeFromString', () => {
  it.each([['blog'], ['1x1'], ['16x9'], ['4x5'], ['9x16'], ['2x3']])(
    '%s validates',
    (ratio) => {
      expect(tileSizeFromString(ratio)).toBe(ratio);
    },
  );

  it.each([['3x4'], ['1X1'], [''], [null], [undefined]])(
    '%s is rejected',
    (ratio) => {
      expect(tileSizeFromString(ratio)).toBeNull();
    },
  );
});

describe('#previewHero tile order', () => {
  it('markup blocks follow TILE_ORDER (reorder the array, not the markup)', () => {
    const html = readFileSync(web('index.html'), 'utf8');
    const classes = [...html.matchAll(/render-tile\s+(r-[0-9a-z]+)/g)].map(
      (m) => m[1],
    );
    expect(classes.length).toBeGreaterThan(0);
    expect(classes.map((c) => tileSizeFromClass(c))).toEqual(TILE_ORDER);
  });
});

describe('build-id pins', () => {
  it('every version-shaped token parses and agrees', () => {
    const files = [web('index.html'), web('webmcp.json'), web('llms.txt')];
    const ids = [];
    for (const f of files) {
      const text = readFileSync(f, 'utf8');
      const tokens = text.match(/0\.\d+\.\d+-[0-9a-f]{7}-\d{8}/g) || [];
      for (const t of tokens) {
        expect(parseBuildId(t), `${t} in ${f} fails validation`).toBe(t);
        ids.push(t);
      }
    }
    expect(ids.length).toBeGreaterThan(0);
    expect(
      new Set(ids).size,
      `drifted pins: ${[...new Set(ids)].join(', ')}`,
    ).toBe(1);
  });

  it('rejects malformed ids', () => {
    for (const bad of ['0.1.012', 'v0.1.012-f618fd8-20260917', '', null]) {
      expect(parseBuildId(bad)).toBeNull();
    }
  });
});

describe('adoptPlatformMatrix', () => {
  const fallback = {
    '1x1': { platforms: ['instagram-feed'] },
  };

  it('adopts a fully valid fetched table', () => {
    const table = {
      '1x1': { platforms: ['instagram-feed'] },
      '9x16': { platforms: ['reels'] },
    };
    expect(adoptPlatformMatrix(table, fallback)).toBe(table);
  });

  it.each([[{}], [[]], [null], [undefined], ['nope']])(
    'keeps the fallback for %s',
    (ratios) => {
      expect(adoptPlatformMatrix(ratios, fallback)).toBe(fallback);
    },
  );

  it('keeps the fallback when any key or row is off', () => {
    expect(
      adoptPlatformMatrix({ '3x4': { platforms: ['x'] } }, fallback),
    ).toBe(fallback);
    expect(adoptPlatformMatrix({ '1x1': {} }, fallback)).toBe(fallback);
    expect(
      adoptPlatformMatrix({ '1x1': { platforms: 'nope' } }, fallback),
    ).toBe(fallback);
  });
});

describe('localeFromLang', () => {
  it.each([['en'], ['es'], ['pt']])('%s is a caption locale', (lang) => {
    expect(localeFromLang(lang)).toBe(lang);
  });

  it.each([['fr'], ['EN'], [''], [null]])('%s is a stranger', (lang) => {
    expect(localeFromLang(lang)).toBeNull();
  });
});
