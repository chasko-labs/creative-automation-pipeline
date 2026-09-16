import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const svg = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/assets/recipe-card-board-fallback.svg'),
  'utf8',
);

// Board geometry in SVG units: board 6..419, printer-safe inset 31..394.
// A title line that escapes the safe rect repeats the "sunshine lemon cake
// spills off the margins" defect — estimate width conservatively (0.7 em per
// displayed character for heavy display caps) and require containment.
const SAFE_MIN = 31;
const SAFE_MAX = 394;

function textRuns() {
  const runs = [];
  for (const m of svg.matchAll(/<text\b([^>]*)>([^<]*)<\/text>/g)) {
    const attrs = m[1];
    const body = m[2].trim();
    if (!body) continue;
    const x = parseFloat(/x="([\d.]+)"/.exec(attrs)?.[1] ?? '0');
    const size = parseFloat(/font-size="([\d.]+)"/.exec(attrs)?.[1] ?? '12');
    const anchorMiddle = /text-anchor="middle"/.test(attrs);
    runs.push({ body, x, size, anchorMiddle });
  }
  return runs;
}

describe('recipe-card board fallback margins', () => {
  it('has title text to check', () => {
    expect(textRuns().length).toBeGreaterThan(0);
  });

  it('keeps every text run inside the printer-safe rect', () => {
    for (const r of textRuns()) {
      const half = (r.body.length * r.size * 0.7) / 2;
      const left = r.anchorMiddle ? r.x - half : r.x;
      const right = r.anchorMiddle ? r.x + half : r.x + half * 2;
      expect(left, `"${r.body}" escapes the safe rect left`).toBeGreaterThanOrEqual(SAFE_MIN);
      expect(right, `"${r.body}" escapes the safe rect right`).toBeLessThanOrEqual(SAFE_MAX);
    }
  });
});
