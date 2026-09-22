import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// About art lives in a full-bleed band ABOVE #aboutTool (mirroring the
// ff-ridge / ff-forest dividers), never buried in .body padding — and carries
// pine sections between the peaks, a mix of the other two motifs.
describe('about art band', () => {
  it('art band precedes the about disclosure', () => {
    const art = index.indexOf('class="ff-about-art"');
    const tool = index.indexOf('id="aboutTool"');
    expect(art).toBeGreaterThan(-1);
    expect(tool).toBeGreaterThan(-1);
    expect(art).toBeLessThan(tool);
  });

  it('no svg remains inside the about body', () => {
    const body = index.slice(index.indexOf('id="aboutTool"'));
    expect(body).not.toMatch(/<svg/);
  });

  it('sawtooth treeline carries a full tooth row (bottom-anchored, flush)', () => {
    const band = index.slice(index.indexOf('class="ff-about-art"'), index.indexOf('id="aboutTool"'));
    const teeth = band.match(/<path d="M\d+ 32 L\d+ \d+ L\d+ 32 Z"/g) || [];
    expect(teeth.length).toBeGreaterThanOrEqual(8);
    expect(band).toMatch(/viewBox="0 0 640 32"/);
    expect(band).toMatch(/preserveAspectRatio="xMidYMax slice"/);
  });

  it('band is full-bleed with a spacing-token cap height', () => {
    expect(css).toMatch(/\.ff-about-art\{[^}]*line-height:0/);
    expect(css).toMatch(/\.ff-about-art \.ff-about-range\{[^}]*width:100%;height:var\(--spacing-xl/);
  });
});
