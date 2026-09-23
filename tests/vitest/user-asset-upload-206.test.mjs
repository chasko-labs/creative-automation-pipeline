import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const disclosure = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/market-disclosure.js'), 'utf8');
const generate = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');

// #206: staged uploads persist to the asset store via POST /library/assets (201 +
// asset_id threaded onto the staged rec) on hosted origins; file:// +
// localhost stay staging-only by design. The backend half is pinned by
// tests/test_library_mount.py (201 + asset ref). These guards pin the
// frontend half so the wiring cannot silently regress to staging-only.
describe('user asset asset store upload (#206)', () => {
  it('staging POSTs raw bytes to /library/assets', () => {
    expect(disclosure).toMatch(/\/library\/assets/);
    expect(disclosure).toMatch(/function uploadAsset\(file,\s*rec\)/);
    expect(disclosure).toMatch(/method:\s*['"]POST['"]/);
  });

  it('a 201 threads the real asset store asset_id onto the staged rec', () => {
    expect(disclosure).toMatch(/rec\.asset_id\s*=\s*data\.asset_id/);
  });

  it('offline/local degrades to staging-only without throwing', () => {
    expect(disclosure).toMatch(/if\(!ASSET_ENDPOINT[^)]*\)\s*return/);
  });

  it('generate.js no longer claims staging is frontend-only', () => {
    expect(generate).not.toMatch(/TODO:\s*server asset store-upload endpoint/);
    expect(generate).not.toMatch(/staged frontend-only \(no asset store upload\)/);
  });
});
