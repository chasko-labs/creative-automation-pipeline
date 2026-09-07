import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/styles.css'),
  'utf8',
);

// Brand custom properties the Panda generator must emit with exact values.
// Fast, no browser: guards the generated artifact itself.
const EXPECTED_PROPS = {
  '--colors-brand-bear-brown': '#3B2316',
  '--colors-brand-blaze-orange': '#E8530E',
  '--colors-brand-frontier-green': '#1A3C34',
  '--colors-brand-signal-red': '#B51E14',
};

describe('kodiak brand custom properties', () => {
  for (const [prop, value] of Object.entries(EXPECTED_PROPS)) {
    it(`${prop} is ${value}`, () => {
      const re = new RegExp(`${prop}:\\s*${value};`, 'i');
      expect(css, `${prop} missing or drifted in generated styles.css`).toMatch(re);
    });
  }

  it('semantic aliases resolve through brand tokens, not raw hex', () => {
    expect(css).toMatch(/--colors-background-nature:\s*var\(--colors-brand-frontier-green\)/);
    expect(css).toMatch(/--colors-foreground-default:\s*var\(--colors-brand-bear-brown\)/);
  });
});
