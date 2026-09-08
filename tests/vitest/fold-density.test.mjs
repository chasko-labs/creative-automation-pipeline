import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const disclosure = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/market-disclosure.js'), 'utf8');
const core = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/data-core.js'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// Fold density: creative-direction clusters collapse by default so Your
// campaign idea stays the star; the market control reads as a closed
// "Location: <place>" row defaulting to Park City.
describe('fold density', () => {
  it('creative direction rides a closed disclosure', () => {
    expect(index).toMatch(/<details class="ff-products ff-directions" id="creativeDirection">/);
    expect(index).not.toMatch(/<details class="ff-products ff-directions" id="creativeDirection" open/);
    expect(index).toMatch(/<summary aria-label="Creative direction/);
    expect(index).toMatch(/id="promptChips"/);
  });

  it('market control reads as Location defaulting to Park City', () => {
    expect(index).toMatch(/id="marketButtonLabel">Location: Park City, Utah</);
    expect(disclosure).toMatch(/label\.textContent = 'Location: ' \+ \(p\.place \|\| market\)/);
    expect(core).toMatch(/aria-label','Location — currently '/);
  });

  it('directions disclosure keeps flush optiongroup rules', () => {
    expect(css).toMatch(/\.ff-directions>\.ff-optiongroup\{[^}]*border-top:none/);
  });
});
