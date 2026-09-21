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
    createElementNS: () => makeEl(),
    addEventListener: () => {},
    querySelector: () => null,
    querySelectorAll: () => [],
    head: makeEl(), body: makeEl(),
  };
  globalThis.window = globalThis;
  globalThis.location = { protocol: 'https:', hostname: 'x.example' };
  globalThis.fetch = async () => ({ ok: false, json: async () => ({}) });
  eval(readFileSync(resolve(APP, 'js/recipe-cards.js'), 'utf8'));
});

describe('recipe art lazy-generate', () => {
  it('builds a mode=recipe-art body, null without an id', () => {
    expect(window.KODIAK_recipeArtBody('roasted-grape-flapjack-topper-draft', 'raw_ingredient')).toEqual({
      mode: 'recipe-art', recipe_id: 'roasted-grape-flapjack-topper-draft', zone: 'raw_ingredient',
    });
    expect(window.KODIAK_recipeArtBody(null, 'technique')).toBe(null);
    expect(window.KODIAK_recipeArtBody('  ', 'finished_plate')).toBe(null);
  });
});
