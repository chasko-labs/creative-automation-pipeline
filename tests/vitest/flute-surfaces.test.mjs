import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// Corrugated surfaces: ribs lead on cards + setup, exposed arch edge on the
// setup board, thread-like body grain dialed back. No raw hex anywhere.
describe('corrugated surfaces', () => {
  it('card grain leads with flute ribs over wood', () => {
    expect(css).toMatch(/\.card::before\{[^}]*background-image:var\(--flute\),var\(--wood\)/);
  });

  it('setup board tiles flute over kraft and shows the arch edge', () => {
    expect(css).toMatch(/\.ff-setup\{[^}]*background-image:var\(--flute\),var\(--gradients-kraft/);
    expect(css).toMatch(/\.ff-setup::after\{[^}]*radial-gradient\(circle at 8px 10px/);
    expect(css).toMatch(/\.ff-setup::after\{[^}]*background-size:16px 8px/);
  });

  it('body thread layer stays faint, no raw hex in the new rules', () => {
    expect(css).toMatch(/body::before\{[^}]*opacity:\.12/);
    const after = css.slice(css.indexOf('.ff-setup::after'));
    expect(after.slice(0, 600)).not.toMatch(/#[0-9a-fA-F]{3,6}/);
  });

  it('generated token layer carries ribs, never diagonal weave', () => {
    const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
    const tokens = readFileSync(
      resolve(root, 'web/kodiak-posts-for-todays-frontier/design/styles.css'), 'utf8');
    expect(tokens).toMatch(/repeating-linear-gradient\(90deg/);
    expect(tokens).not.toMatch(/135deg|45deg/);
  });
});
