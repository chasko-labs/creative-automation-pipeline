import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const chips = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/prompt-chips.js'), 'utf8');

// Preview pack coverage: the preview records the backend copy_sidecar per
// response (recipe + platform copy as txt/csv), but downloadAllPreview used to
// POST images only — an images-only zip drops the recipe. The pack POST must
// carry the sidecar as extras, same as the campaign pack path.
describe('preview pack extras (recipe + copy ride the zip)', () => {
  it('posts copy.txt/copy.csv extras built from __lastSidecar', () => {
    expect(chips).toMatch(/window\.__lastSidecar/);
    expect(chips).toMatch(/name: 'copy\.txt'/);
    expect(chips).toMatch(/name: 'copy\.csv'/);
    expect(chips).toMatch(/extras: extras/);
  });

  it('caps extra text at the backend 64KB limit', () => {
    expect(chips).toMatch(/slice\(0, 65536\)/);
  });

  it('matches the campaign pack extras contract', () => {
    const sections = readFileSync(
      resolve(root, 'web/kodiak-posts-for-todays-frontier/js/campaign-sections.js'), 'utf8');
    for (const src of [chips, sections]) {
      expect(src).toMatch(/__last\w*Sidecar \|\| \{\}/);
      expect(src).toMatch(/\/assets\/pack/);
    }
  });
});
