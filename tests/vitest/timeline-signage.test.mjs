import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const ember = readFileSync(resolve(root, 'src/kodiak-ember.js'), 'utf8');

// Timeline signage boot pin: the area-light layer mounts ONLY behind the
// ?ember3d=1 lab flag (same gate as the paperboard boot) and ONLY for
// #progressTimeline — never the cards.
describe('timeline signage boot', () => {
  it('mountTimelineSignage is flag-gated and scoped to #progressTimeline', () => {
    // source exposes the mount following the sheen lazy/gated/capped pattern
    expect(ember).toMatch(/function mountTimelineSignage\(selector = "#progressTimeline"\)/);
    expect(ember).toMatch(/gateReason\(host\)/);
    expect(ember).toMatch(/IntersectionObserver/);
    expect(ember).toMatch(/RectAreaLight/);
    // boot lives inside the existing ember3d=1 lab-flag guard…
    const bootBlock = index.match(
      /get\('ember3d'\) === '1'\) \{[\s\S]*?\n  \}\n<\/script>/);
    expect(bootBlock, 'ember3d=1 boot block missing').not.toBeNull();
    expect(bootBlock[0]).toMatch(/mountTimelineSignage\('#progressTimeline'\)/);
    // …and the signage mount targets the timeline only, never .card
    expect(bootBlock[0]).not.toMatch(/mountTimelineSignage\([^)]*\.card/);
    expect(index).toMatch(/id="progressTimeline"/);
  });
});
