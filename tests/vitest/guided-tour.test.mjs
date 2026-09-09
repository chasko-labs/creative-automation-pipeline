import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const app = resolve(root, 'web/kodiak-posts-for-todays-frontier');
const index = readFileSync(resolve(app, 'index.html'), 'utf8');
const tour = readFileSync(resolve(app, 'js/tour.js'), 'utf8');
const css = readFileSync(resolve(app, 'design/components.css'), 'utf8');

// Guided arrow tour: cardboard cut-out arrow, Create -> steps 1-5 -> preview,
// start/dismiss persisted, never blocks input, static under reduced motion.
describe('guided arrow tour', () => {
  it('is wired into the page', () => {
    expect(index).toMatch(/js\/tour\.js/);
  });

  it('visits Create, steps 1-5, then preview in order', () => {
    const order = [
      '#generateCampaign',
      '#scopeWrap',
      '#locationSection',
      '.ff-season-details',
      '#creativeDirection',
      '.ff-inputwrap',
      '#outputHeading',
    ];
    let last = -1;
    for (const sel of order) {
      const at = tour.indexOf(sel);
      expect(at, `stop selector ${sel}`).toBeGreaterThan(-1);
      expect(at, `${sel} out of order`).toBeGreaterThan(last);
      last = at;
    }
  });

  it('persists dismissal and removes its node when dismissed', () => {
    expect(tour).toMatch(/kodiak_tour/);
    expect(tour).toMatch(/localStorage/);
    expect(tour).toMatch(/removeChild/);
  });

  it('advances on arrow click/Enter, dismisses on x/Escape — no panel buttons', () => {
    expect(tour).toMatch(/ffTourWrap/);
    expect(tour).toMatch(/ffTourX/);
    expect(tour).toMatch(/function advance/);
    expect(tour).toMatch(/'Enter'/);
  });

  it('handles reduced motion (static arrow, no float/shimmer)', () => {
    expect(tour).toMatch(/prefers-reduced-motion/);
    expect(tour).toMatch(/is-still/);
    expect(css).toMatch(/prefers-reduced-motion/);
  });

  it('never blocks input: wrapper is pointer-events none', () => {
    expect(css).toMatch(/\.ff-tour\{[^}]*pointer-events:none/);
  });

  it('arrow SVG uses kraft fill, sharpie stroke, pine label — token var() only, no floating panel', () => {
    expect(tour).toMatch(/<svg/);
    expect(tour).toMatch(/<text/);
    expect(tour).not.toMatch(/ff-tour-bar/);
    expect(tour).not.toMatch(/ffTourNext/);
    expect(css).toMatch(/\.ff-tour-arrow-shape\{[^}]*fill:var\(--colors-brand-box-parchment\)/);
    expect(css).toMatch(/\.ff-tour-label\{[^}]*fill:var\(--colors-brand-frontier-green\)/);
    expect(css).not.toMatch(/\.ff-tour-btn\{/);
    const start = css.indexOf('/* === Guided arrow tour');
    expect(start, 'tour CSS marker').toBeGreaterThan(-1);
    const block = css.slice(start);
    expect(block, 'raw color literal in tour CSS').not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(block, 'raw rgb() in tour CSS').not.toMatch(/rgba?\(/);
  });

  it('floats gently (4s+ bob, tiny amplitude) with a slow sheen sweep', () => {
    expect(css).toMatch(/ff-tour-bob 4\.6s/);
    expect(css).toMatch(/translateY\(-3px\)/);
    expect(css).toMatch(/ff-tour-sheen 5\.6s/);
  });
});
