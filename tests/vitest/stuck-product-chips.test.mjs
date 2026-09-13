import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const combo = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/product-combobox.js'), 'utf8');
const persist = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/lifecycle-persist.js'), 'utf8');

// #250: a host re-filter destroys checked checkbox nodes without events, leaving
// stale tray chips. The toggle must void the chip even when the box is gone,
// and reset must re-sync the tray from the live boxes.
// Behavioral proof lives in tests/browser/issues/issue-250.mjs (local browser).
// FAILS pre-fix at "A chip gone after X", PASSES post-fix on all three steps).
// These guards pin the source contract so the fix cannot silently regress.
describe('stuck product chips (#250)', () => {
  it('toggleSku voids the chip when the box is absent', () => {
    expect(combo).toMatch(/if\s*\(!b\)\s*\{[^}]*removeSkuChip\(value\)/s);
  });

  it('removeSkuChip drops chips by dataset.sku regardless of host state', () => {
    expect(combo).toMatch(/function removeSkuChip\(value\)/);
    expect(combo).toMatch(/\.ff-pending-chip\[data-sku\]/);
    expect(combo).toMatch(/c\.dataset\s*&&\s*c\.dataset\.sku\s*===\s*value/);
  });

  it('the tray sync is exposed for reset', () => {
    expect(combo).toMatch(/window\.__kodiakSyncSkuChips\s*=\s*syncSkuChips/);
  });

  it('resetToDefaults re-syncs the tray after unchecking', () => {
    expect(persist).toMatch(/typeof window\.__kodiakSyncSkuChips/);
  });
});
