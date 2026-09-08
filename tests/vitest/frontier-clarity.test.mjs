import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const core = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'), 'utf8');
const disclosure = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/market-disclosure.js'), 'utf8');

// Frontier framing names the RURAL COUNTERPART to the urban market — a data
// pairing, never the viewer's location. Language readouts list only the
// generated others; English (the source) is inferred.
describe('frontier clarity', () => {
  it('explains the featured frontier as the rural counterpart', () => {
    expect(core).toMatch(/rural counterpart to this market/);
    expect(disclosure).toMatch(/featured frontier \(rural counterpart\)/);
    expect(core).not.toMatch(/hinterland frontier/);
    expect(disclosure).not.toMatch(/hinterland frontier/);
  });

  it('never prepends inferred English to the generated languages', () => {
    expect(core).not.toMatch(/\['English'\]\.concat\(names\)/);
    expect(core).toMatch(/names\.length \? names\.join\(', '\) : 'English'/);
    expect(index).toMatch(/localized in languages: <b>Spanish, Portuguese<\/b>/);
  });
});
