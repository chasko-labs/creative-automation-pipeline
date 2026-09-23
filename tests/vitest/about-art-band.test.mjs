import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// About shares the single forest-divider cap with the Output and Generate
// cards: one component, zero surrounding margins, flush with the card below.
// (A bespoke about svg slice-cropped to the wrong band at divider height and
// floated pale above the card, so it was retired.)
describe('about forest cap', () => {
  it('a forest divider precedes the about disclosure', () => {
    const lastForest = index.lastIndexOf('class="ff-forest"');
    const tool = index.indexOf('id="aboutTool"');
    expect(lastForest).toBeGreaterThan(-1);
    expect(tool).toBeGreaterThan(-1);
    expect(lastForest).toBeLessThan(tool);
  });

  it('no svg remains inside or directly above the about card', () => {
    const fromAbout = index.slice(index.indexOf('id="aboutTool"') - 600);
    expect(fromAbout).not.toMatch(/<svg/);
  });

  it('the forest cap carries zero surrounding margins (flush)', () => {
    expect(css).toMatch(/\.ff-forest\{[^}]*margin:0 var\(--radii-lg\) 0/);
  });
});
