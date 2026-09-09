import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// Lit kraft surfaces: no repeating stripes anywhere — depth comes from the
// flat top-light token wash + shadows, grit from wood fiber. Dotted cut edge
// kept on the setup board, body fiber faint. No raw hex anywhere.
describe('corrugated surfaces', () => {
  it('card grain is wood fiber only, never flute ribs', () => {
    expect(css).toMatch(/\.card::before\{[^}]*background-image:var\(--wood\)/);
    expect(css).not.toMatch(/--flute/);
  });

  it('setup board is a flat token wash with the dotted cut edge', () => {
    expect(css).toMatch(/\.ff-setup\{[^}]*background:var\(--gradients-kraft/);
    expect(css).toMatch(/\.ff-setup::after\{[^}]*radial-gradient\(circle at 8px 10px/);
    expect(css).toMatch(/\.ff-setup::after\{[^}]*background-size:16px 8px/);
  });

  it('body fiber layer stays faint, no raw hex in the new rules', () => {
    expect(css).toMatch(/body::before\{[^}]*opacity:\.06/);
    const after = css.slice(css.indexOf('.ff-setup::after'));
    expect(after.slice(0, 600)).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });

  it('generated token layer carries no ribs, never diagonal weave', () => {
    const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
    const tokens = readFileSync(
      resolve(root, 'web/kodiak-posts-for-todays-frontier/design/styles.css'), 'utf8');
    expect(tokens).not.toMatch(/repeating-linear-gradient/);
    expect(tokens).not.toMatch(/135deg|45deg/);
  });
});
