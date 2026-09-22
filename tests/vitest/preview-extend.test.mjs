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

// Preview extend polling: tall/wide pads upgrade to composed pixels.
describe('preview extend helpers', () => {
  const hero = { ratio: '1x1', s3_uri: 's3://b/hero.png' };
  const renders = [
    hero,
    { ratio: '9x16', s3_uri: 's3://b/a.png' },
    { ratio: '16x9', s3_uri: 's3://b/b.png' },
    { ratio: '4x5', s3_uri: 's3://b/c.png' },
    { ratio: 'blog' },
  ];

  it('targets only 9x16/16x9 tiles that carry an s3 uri', () => {
    const t = window.KODIAK_extendTargets(renders);
    expect(t.map(r => r.ratio).sort()).toEqual(['16x9', '9x16']);
    expect(window.KODIAK_extendTargets(null)).toEqual([]);
  });

  it('finds the 1x1 hero or null', () => {
    expect(window.KODIAK_extendHero(renders)).toBe(hero);
    expect(window.KODIAK_extendHero([{ ratio: '9x16' }])).toBe(null);
  });

  it('marks pad vs live engines so tiles never render identically', () => {
    expect(window.KODIAK_tileEngineMark('stability-outpaint')).toEqual({ text: ' · composed', cls: 'rt-live' });
    expect(window.KODIAK_tileEngineMark('pillow-outpaint-fallback')).toEqual({ text: ' · cover-pad', cls: 'rt-pad' });
    expect(window.KODIAK_tileEngineMark('primary')).toEqual({ text: '', cls: '' });
    expect(window.KODIAK_tileEngineMark('unknown-engine')).toEqual({ text: '', cls: '' });
    expect(window.KODIAK_tileEngineMark(null)).toEqual({ text: '', cls: '' });
  });

  it('orders request themes primary-first, extras never dropped silently', () => {
    expect(window.KODIAK_orderThemes('b', ['a', 'b', 'c'])).toEqual(['b', 'a', 'c']);
    expect(window.KODIAK_orderThemes(null, ['a', 'b'])).toEqual(['a', 'b']);
    expect(window.KODIAK_orderThemes('b', ['b', 'b'])).toEqual(['b']);
    expect(window.KODIAK_orderThemes(null, null)).toEqual([]);
  });

  it('builds a mode=extend body with sane defaults', () => {
    const b = window.KODIAK_extendBody('9x16', hero, { subject: 's', product: 'p', region: 'r', theme: 't' });
    expect(b).toEqual({ mode: 'extend', ratio: '9x16', hero_s3_uri: 's3://b/hero.png', subject: 's', product: 'p', region: 'r', theme: 't' });
    const d = window.KODIAK_extendBody('16x9', hero, {});
    expect(d.product).toBe('power-cakes');
    expect(d.theme).toBe(null);
  });

  it('picks season-aware market hero images offline, distinct per tile', () => {
    globalThis.KODIAK_TILE_ORDER = ['blog', '1x1', '16x9', '4x5', '9x16'];
    globalThis.KODIAK_CAMPAIGN_ART = {
      season_months: { christmas: [12, 1, 2], fall: [9, 10, 11] },
      markets: {
        'US-OH-LEBANON': {
          seasons: {
            fall: { waffle: 'input_assets/campaign-web/US-OH-LEBANON/fall-waffle.jpg', muffin: 'input_assets/campaign-web/US-OH-LEBANON/fall-muffin.jpg', 'oatmeal-cup': 'input_assets/campaign-web/US-OH-LEBANON/fall-oatmeal-cup.jpg', bars: 'input_assets/campaign-web/US-OH-LEBANON/fall-bars.jpg', brownie: 'input_assets/campaign-web/US-OH-LEBANON/fall-brownie.jpg' },
            christmas: { waffle: 'input_assets/campaign-web/US-OH-LEBANON/christmas-waffle.jpg', muffin: 'input_assets/campaign-web/US-OH-LEBANON/christmas-muffin.jpg', 'oatmeal-cup': 'input_assets/campaign-web/US-OH-LEBANON/christmas-oatmeal-cup.jpg', bars: 'input_assets/campaign-web/US-OH-LEBANON/christmas-bars.jpg', brownie: 'input_assets/campaign-web/US-OH-LEBANON/christmas-brownie.jpg' },
          },
          extras: {},
        },
      },
    };
    const oct = window.KODIAK_marketHeroPicks('US-OH-LEBANON', 10);
    expect(Object.keys(oct).sort()).toEqual(['16x9', '1x1', '4x5', '9x16', 'blog']);
    expect(new Set(Object.values(oct)).size).toBe(5);
    expect(oct.blog).toContain('fall-waffle.jpg');
    expect(window.KODIAK_marketHeroPicks('US-OH-LEBANON', 1).blog).toContain('christmas-waffle.jpg');
    expect(window.KODIAK_marketHeroPicks('US-XX-NOWHERE', 10)).toEqual({});
    expect(window.KODIAK_marketHeroPicks(null, 10)).toEqual({});
  });

  it('stamps runtime hero picks with the page build version', () => {
    globalThis.KODIAK_TILE_ORDER = ['blog'];
    globalThis.KODIAK_CAMPAIGN_ART = {
      season_months: { fall: [9, 10, 11] },
      markets: { 'US-OH-LEBANON': { seasons: { fall: { waffle: 'input_assets/campaign-web/US-OH-LEBANON/fall-waffle.jpg' } }, extras: {} } },
    };
    globalThis.KODIAK_VERSION = '0.1.012-test';
    const stamped = window.KODIAK_marketHeroPicks('US-OH-LEBANON', 10);
    expect(stamped.blog).toBe('input_assets/campaign-web/US-OH-LEBANON/fall-waffle.jpg?v=0.1.012-test');
    delete globalThis.KODIAK_VERSION;
    const plain = window.KODIAK_marketHeroPicks('US-OH-LEBANON', 10);
    expect(plain.blog).toBe('input_assets/campaign-web/US-OH-LEBANON/fall-waffle.jpg');
  });

  it('repaints resting copy from the market row, never Utah under Ohio', () => {
    globalThis.places = [
      { market: 'US-OH-LEBANON', place: 'Lebanon, Ohio 45036', message: 'Orchard belt frontier', cue: 'Hidden Valley peaches' },
    ];
    globalThis.featuredFrontierFor = () => ({ place: 'Lebanon, Ohio 45036' });
    const copy = window.KODIAK_restingCopyFor('US-OH-LEBANON');
    expect(copy.title).toBe('Lebanon, Ohio 45036 preview');
    expect(copy.lede).toContain('Orchard belt frontier');
    expect(copy.lede).not.toContain('Wasatch');
    expect(copy.lede).not.toContain('Oakley');
    expect(window.KODIAK_restingCopyFor('US-MW-PARKCITY-84098')).toBe(null);
    expect(window.KODIAK_restingCopyFor('US-XX-NOWHERE')).toBe(null);
  });
});
