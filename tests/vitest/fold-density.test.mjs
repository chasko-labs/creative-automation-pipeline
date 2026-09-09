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
// "Market: <place>" row defaulting to Park City, paired with its featured
// frontier on the step-2 summary line.
describe('fold density', () => {
  it('creative direction rides a closed disclosure', () => {
    expect(index).toMatch(/<details class="ff-products ff-directions" id="creativeDirection">/);
    expect(index).not.toMatch(/<details class="ff-products ff-directions" id="creativeDirection" open/);
    expect(index).toMatch(/<summary aria-label="Creative direction/);
    expect(index).toMatch(/id="promptChips"/);
  });

  it('market control reads as Market defaulting to Park City + frontier', () => {
    expect(index).toMatch(/id="marketButtonLabel">Market: Park City, Utah</);
    expect(disclosure).toMatch(/label\.textContent = 'Market: ' \+ \(p\.place \|\| market\)/);
    expect(disclosure).toMatch(/featuredFrontierFor\(market\)/);
    expect(disclosure).toMatch(/' · Featured Frontier: ' \+ ffShort/);
    expect(core).toMatch(/aria-label','Market — currently '/);
  });

  it('directions disclosure keeps flush optiongroup rules', () => {
    expect(css).toMatch(/\.ff-directions>\.ff-optiongroup\{[^}]*border-top:none/);
  });
});
