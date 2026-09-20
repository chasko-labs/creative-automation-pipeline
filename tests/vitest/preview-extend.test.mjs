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

  it('builds a mode=extend body with sane defaults', () => {
    const b = window.KODIAK_extendBody('9x16', hero, { subject: 's', product: 'p', region: 'r', theme: 't' });
    expect(b).toEqual({ mode: 'extend', ratio: '9x16', hero_s3_uri: 's3://b/hero.png', subject: 's', product: 'p', region: 'r', theme: 't' });
    const d = window.KODIAK_extendBody('16x9', hero, {});
    expect(d.product).toBe('power-cakes');
    expect(d.theme).toBe(null);
  });
});
