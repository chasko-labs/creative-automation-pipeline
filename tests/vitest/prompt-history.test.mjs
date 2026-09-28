import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const src = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/prompt-history.js'), 'utf8');

// Eval the ledger module with stub globals (it reads bare window/localStorage).
function loadLedger(storage) {
  const window = {};
  const fn = new Function('window', 'localStorage', 'module', `${src}; return window.KODIAK_promptHistory;`);
  return fn(window, storage, { exports: {} });
}

function memStore() {
  const data = {};
  return {
    getItem: (k) => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v); },
    removeItem: (k) => { delete data[k]; },
  };
}

const ENTRY = {
  market: 'US-NE-NYC',
  season: 'September',
  product: 'buttermilk-power-cakes-flapjack-waffle-mix',
  dish: 'Apple Cinnamon Compote',
  base: 'Bodega coffee, oatmeal cup on subway platform — apples in season',
  scene_prompt: 'A serving of Apple Cinnamon Compote. Buttermilk Power Cakes product photo restyled for Warwick apples in season',
  headline: 'Bodega Mornings, Warwick Apples',
  recipe: 'Apple Cinnamon Compote',
  source: 'bedrock:stability-control-structure',
  image_url: 'https://example.com/hero.png',
};

describe('prompt-history ledger', () => {
  it('records what was sent and what came back', () => {
    const api = loadLedger(memStore());
    const stored = api.record(ENTRY);
    expect(stored).not.toBeNull();
    expect(stored.ts).toBeTruthy();
    const entries = api.read();
    expect(entries).toHaveLength(1);
    expect(entries[0].scene_prompt).toContain('A serving of Apple Cinnamon Compote');
    expect(entries[0].dish).toBe('Apple Cinnamon Compote');
    expect(entries[0].base).toContain('apples in season');
  });

  it('skips empty records and caps at 100, newest first', () => {
    const api = loadLedger(memStore());
    expect(api.record({})).toBeNull();
    expect(api.record({ market: 'x' })).toBeNull();
    expect(api.read()).toHaveLength(0);
    for (let i = 0; i < 105; i++) api.record({ ...ENTRY, headline: `h${i}` });
    const entries = api.read();
    expect(entries).toHaveLength(100);
    expect(entries[0].headline).toBe('h104');
  });

  it('persists across loads under the versioned key and clears', () => {
    const storage = memStore();
    loadLedger(storage).record(ENTRY);
    expect(loadLedger(storage).read()).toHaveLength(1);
    expect(storage.getItem('kodiak.promptHistory.v1')).toContain('Apple Cinnamon Compote');
    loadLedger(storage).clear();
    expect(loadLedger(storage).read()).toHaveLength(0);
  });

  it('degrades to memory-only when storage throws', () => {
    const broken = {
      getItem: () => { throw new Error('denied'); },
      setItem: () => { throw new Error('denied'); },
      removeItem: () => { throw new Error('denied'); },
    };
    const api = loadLedger(broken);
    expect(api.record(ENTRY)).not.toBeNull();
    expect(api.read()).toHaveLength(1);
  });
});
