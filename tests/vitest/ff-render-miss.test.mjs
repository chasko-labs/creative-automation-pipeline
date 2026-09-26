import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const web = (...parts) =>
  resolve(root, 'web/kodiak-posts-for-todays-frontier', ...parts);

const css = readFileSync(web('design/components.css'), 'utf8');
const gen = readFileSync(web('js/generate.js'), 'utf8');

// Double-miss contract: a wall-timeout fallthrough auto-retries once on warm
// models; only a second miss shows the honest error card (never fallback
// pixels presented as the campaign) with an unmissable pulsing retry.
describe('render-miss auto-retry and honest error', () => {
  it('auto-retries exactly once on a brand-floor fallthrough', () => {
    expect(gen).toMatch(/AUTO-RETRY ONCE/);
    expect(gen).toMatch(/Bounded to exactly one retry/i);
    // the retry re-issues oneGenerate; the old passive status copy is gone.
    expect(gen).not.toMatch(
      /fallback pixels shown, not the campaign/,
    );
  });

  it('double miss swaps the grid for a role=alert error card', () => {
    expect(gen).toMatch(/ff-render-miss/);
    expect(gen).toMatch(/role['"],\s*['"]alert/);
    expect(gen).toMatch(/Render miss — nothing generated/);
  });

  it('retry button pulses and stays motion-safe', () => {
    expect(gen).toMatch(/ff-retry ff-retry--pulse/);
    expect(css).toMatch(/@keyframes ff-retry-pulse/);
    expect(css).toMatch(/\.ff-retry--pulse\{[^}]*animation:ff-retry-pulse/);
    // a reduced-motion rule kills the pulse later in source order.
    const pulseIdx = css.indexOf('.ff-retry--pulse{animation:');
    const killIdx = css.indexOf('.ff-retry--pulse{animation:none}');
    expect(pulseIdx).toBeGreaterThanOrEqual(0);
    expect(killIdx).toBeGreaterThan(pulseIdx);
  });

  it('miss card has its own honest styling, no fake-pixel presentation', () => {
    expect(css).toMatch(/\.ff-render-miss\{[^}]*grid-column:1\/-1/);
  });
});
