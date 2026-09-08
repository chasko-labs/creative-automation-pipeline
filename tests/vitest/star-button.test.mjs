import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');
const generate = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');

// The star button: full "Create Campaign Preview" label (restored after every
// generate), lit ember gradient where every stop clears WCAG AA vs white,
// hover light-sweep with a reduced-motion off-ramp, and corrugated flute over
// the kraft on hero surfaces — lit cardboard, never stripes.
describe('star button + lit cardboard', () => {
  it('button reads Create Campaign Preview and restores it', () => {
    expect(index).toMatch(/id="generateCampaign"[^>]*>Create Campaign Preview</);
    expect(generate).toMatch(/const origLabel = 'Create Campaign Preview'/);
  });

  it('ember gradient keeps every stop AA-safe vs white', () => {
    expect(css).toMatch(/\.ff-go\{[^}]*background:linear-gradient\(180deg,#C9460C 0%,#C7440B 48%,#A93B07 100%\)/);
  });

  it('hover light-sweep exists with a reduced-motion off-ramp', () => {
    expect(css).toMatch(/\.ff-go::after\{[^}]*skewX\(-18deg\)/);
    expect(css).toMatch(/\.ff-go:hover::after,\.ff-go:focus-visible::after\{left:135%/);
    expect(css).toMatch(/prefers-reduced-motion.*\.ff-go::after\{display:none\}/s);
  });

  it('corrugated flute tiles over kraft on hero surfaces', () => {
    expect(css).toMatch(/--flute:url\("data:image\/svg\+xml/);
    expect(css).toMatch(/\.ff-prompt\{background-image:var\(--flute\),var\(--gradients-kraft\\\.surface\)\}/);
    expect(css).toMatch(/\.ff-timeline\{[^}]*background-image:var\(--flute\)/);
  });
});
