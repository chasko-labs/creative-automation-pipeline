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

  it('never fires mid-preview: waits on the busy flag, yields detached nodes, speaks human', () => {
    const cards = readFileSync(resolve(APP, 'js/recipe-cards.js'), 'utf8');
    // status text names the work, not the model or provider.
    expect(cards).toMatch(/Painting recipe art/);
    expect(cards).not.toMatch(/generating image using SDXL/);
    // busy gate with a bound, and detached nodes yield to the live one.
    expect(cards).toMatch(/window\.__ffPreviewBusy/);
    expect(cards).toMatch(/waited > 240000/);
    expect(cards).toMatch(/isConnected === false/);
  });

  it('shares the in-flight fetch on re-prime so no skeleton strands, and retries after settle', () => {
    const cards = readFileSync(resolve(APP, 'js/recipe-cards.js'), 'utf8');
    // no silent early return: a re-primed wrap joins the pending promise.
    expect(cards).not.toMatch(/if \(artGenFired\[key\]\) return;/);
    expect(cards).toMatch(/artGenPromise\.then/);
    // settle clears the cell so a later prime retries down the seeded path.
    expect(cards).toMatch(/delete artGenFired\[key\]/);
  });

  it('fires once per completed preview, never on load or scroll, and says so', () => {
    const cards = readFileSync(resolve(APP, 'js/recipe-cards.js'), 'utf8');
    const gen = readFileSync(resolve(APP, 'js/generate.js'), 'utf8');
    // no scroll observer spends model calls; quiet placeholder until primed.
    expect(cards).not.toMatch(/IntersectionObserver/);
    expect(cards).toMatch(/KODIAK_primeReviewArt/);
    // preview-complete kicks it; fresh generations are marked, seeded art stays quiet.
    expect(gen).toMatch(/KODIAK_primeReviewArt/);
    expect(cards).toMatch(/Generated on preview/);
    expect(cards).toMatch(/json\.seeded === true/);
  });
});
