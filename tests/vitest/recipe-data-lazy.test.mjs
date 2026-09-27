import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const APP = resolve(root, 'web/kodiak-posts-for-todays-frontier');
const indexHtml = readFileSync(resolve(APP, 'index.html'), 'utf8');
const cardsSrc = readFileSync(resolve(APP, 'js/recipe-cards.js'), 'utf8');

function makeEl(tag) {
  return {
    tagName: String(tag || '').toUpperCase(), className: '', textContent: '',
    innerHTML: '', children: [], style: {}, dataset: {}, offsetParent: {},
    setAttribute() {}, appendChild(c) { this.children.push(c); return c; },
    querySelector() { return null; }, querySelectorAll() { return []; },
    addEventListener() {}, remove() {},
    classList: { add() {}, remove() {}, contains() { return false; } },
  };
}

// Installs a stub DOM, evals the renderer, and returns the injection log.
// cardOpen mirrors the preview <details>: closed at boot, open on generate.
function boot(cardOpen) {
  const injected = [];
  const scripts = [];
  const slot = makeEl('div');
  const card = { tagName: 'DETAILS', open: cardOpen };
  const head = makeEl('head');
  head.appendChild = (c) => { injected.push(c); return c; };
  globalThis.document = {
    readyState: 'complete',
    head, documentElement: makeEl('html'),
    getElementById: (id) => {
      if (id === 'previewRecipe') return slot;
      if (id === 'previewCard') return card;
      if (id === 'locality') return { value: 'MKT' };
      if (id === 'seasonalSelect') return { value: 'October' };
      return null;
    },
    createElement: (tag) => {
      const s = makeEl(tag);
      if (String(tag).toLowerCase() === 'script') scripts.push(s);
      return s;
    },
    createElementNS: () => makeEl('x'),
    addEventListener() {}, querySelector: () => null, querySelectorAll: () => [],
  };
  globalThis.window = globalThis;
  globalThis.KODIAK_VERSION = 'test-v9';
  delete globalThis.KODIAK_RECIPE_CARDS;
  delete globalThis.KODIAK_RECIPE_I18N;
  eval(cardsSrc);
  return { injected, scripts, slot, card };
}

const tick = () => new Promise((r) => setTimeout(r, 10));

describe('recipe data lazy-load', () => {
  it('index boots without the 20MB data scripts; recipes.html keeps its own', () => {
    expect(indexHtml).not.toMatch(/<script[^>]*recipe-cards-data\.js/);
    expect(indexHtml).not.toMatch(/<script[^>]*recipe-i18n-data\.js/);
    expect(indexHtml).toMatch(/<script[^>]*js\/recipe-cards\.js/);
    const recipes = readFileSync(resolve(APP, 'recipes.html'), 'utf8');
    expect(recipes).toMatch(/<script[^>]*recipe-cards-data\.js/);
  });

  it('boot with a closed card fetches nothing and keeps the honest empty state', () => {
    const { injected, slot } = boot(false);
    // bootstrap render ran at eval: empty state painted, zero script tags.
    expect(injected).toEqual([]);
    expect(slot.children[0].className).toBe('rc-gallery-empty');
    expect(slot.children[0].textContent).toMatch(/once generated/);
  });

  it('first open injects both data scripts with the build stamp', () => {
    const { injected, card } = boot(false);
    card.open = true;
    window.KODIAK_renderPreviewCard();
    const srcs = injected.map((s) => s.src);
    expect(srcs).toHaveLength(2);
    expect(srcs[0]).toMatch(/js\/recipe-cards-data\.js\?v=test-v9/);
    expect(srcs[1]).toMatch(/js\/recipe-i18n-data\.js\?v=test-v9/);
    // a second render while loading reuses the one in-flight promise.
    window.KODIAK_renderPreviewCard();
    expect(injected).toHaveLength(2);
  });

  it('paints the card on arrival and loads nothing more after', async () => {
    const { injected, scripts, slot, card } = boot(false);
    card.open = true;
    window.KODIAK_renderPreviewCard();
    window.KODIAK_RECIPE_CARDS = {
      MKT: { '2026-10': { title: 'T', ingredient: 'X', meta: {}, ingredients: [], art: {} } },
    };
    scripts.forEach((s) => s.onload && s.onload());
    await tick();
    const wrap = slot.children.find((c) => c.className === 'rc-preview-wrap');
    expect(wrap).toBeTruthy();
    const n = injected.length;
    delete window.KODIAK_RECIPE_CARDS;
    window.KODIAK_renderPreviewCard();
    await tick();
    expect(injected).toHaveLength(n);
  });

  it('a failed load keeps the empty state and never throws', async () => {
    const { scripts, slot, card } = boot(false);
    card.open = true;
    window.KODIAK_renderPreviewCard();
    expect(scripts).toHaveLength(2);
    scripts.forEach((s) => s.onerror && s.onerror());
    await tick();
    expect(slot.children[0].className).toBe('rc-gallery-empty');
  });
});
