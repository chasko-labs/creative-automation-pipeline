import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'),
  'utf8',
);
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'),
  'utf8',
);
const generate = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'),
  'utf8',
);

// UI simplification: sections 1–4.3 fold into one Brainstorm disclosure that is
// CLOSED on load, so the load view is Brainstorm + Your campaign idea + Create.
describe('one-screen load: brainstorm collapse', () => {
  it('wraps steps 1-4.3 in a closed Brainstorm disclosure', () => {
    const open = index.indexOf('id="brainstormAll"');
    expect(open).toBeGreaterThan(-1);
    const tag = index.slice(index.lastIndexOf('<details', open), open);
    expect(tag).not.toMatch(/\bopen\b/);
    const summary = index.slice(open, index.indexOf('</summary>', open));
    expect(summary).toMatch(/Brainstorm — let's cook up something wild/);
  });

  it('opens the brainstorm stack as one consistent boxed rhythm', () => {
    expect(css).toMatch(/#brainstormAll\[open\] \.ff-scope-wrap>\.ff-scope-summary/);
    expect(css).toMatch(/#brainstormAll\[open\] #locationSection>summary/);
    expect(css).toMatch(/#brainstormAll\[open\] \.ff-season-details>summary/);
    expect(css).toMatch(/#brainstormAll\[open\] \.ff-brainstorm \.ff-products>summary/);
    expect(css).toMatch(/#brainstormAll\[open\] \.ff-assetrow\{[^}]*display:flex/);
  });

  it('keeps the preview closed until Create opens it', () => {
    const tag = index.slice(index.lastIndexOf('<details', index.indexOf('id="previewCard"')), index.indexOf('id="previewCard"'));
    expect(tag).not.toMatch(/\bopen\b/);
    expect(generate).toMatch(/function openPreviewCard\(\)/);
    // fold guard: a closed card must not lay out its ~2000px body (author
    // display rules beat the UA closed-details rule, so the guard hides it
    // and re-syncs on every toggle).
    expect(generate).toMatch(/function syncPreviewCardBody\(\)/);
    expect(generate).toMatch(/addEventListener\('toggle', syncPreviewCardBody\)/);
  });

  it('nests reach, market, season, direction, products, and staged assets inside', () => {
    const wrap = index.slice(
      index.indexOf('id="brainstormAll"'),
      index.indexOf('/Brainstorm (steps 1-4, closed on load)'),
    );
    for (const id of ['id="scopeWrap"', 'id="locationSection"', 'class="ff-season-details"',
      'id="creativeDirection"', 'id="existingAssets"', 'id="promptUpload"',
      'id="assetBrowseTrigger"', 'id="selectionTray"']) {
      expect(wrap).toContain(id);
    }
  });

  it('keeps every inner binding id intact', () => {
    for (const id of ['campaignScope', 'scopeSummary', 'marketDisclosure', 'marketListbox',
      'locality', 'seasonalSelect', 'promptChips', 'productSearch', 'productChooser']) {
      expect(index).toContain(`id="${id}"`);
    }
  });

  it('campaign idea copy points at upload, past campaigns, and brainstorm', () => {
    expect(index).toMatch(/placeholder="Describe your social campaign idea — or upload files, browse past campaigns, and brainstorm by tapping above\."/);
    expect(index).not.toMatch(/tap options above/);
  });
});

// Backlog: the wallpaper tore at exactly one viewport of scroll (100dvh-clipped
// wash layers); every layer must complete inside its own box at any depth.
describe('infinite wallpaper', () => {
  it('sizes washes to the full page, never the viewport', () => {
    expect(css).not.toMatch(/background-size:[^;]*100dvh/);
    expect(css).toMatch(/background-size:100% 100%,100% 100%,auto,100% 100%,auto/);
  });
});

// The header navbar is out of scope for the simplification: no sign host in
// the header, headline plate untouched. The ambient engine boots ONLY behind
// the three feature stages (paperboard spot-gloss); the retired navbar sign
// stays out.
describe('header untouched', () => {
  it('carries no sign wiring', () => {
    expect(index).not.toMatch(/frontierSign/);
    expect(index).not.toMatch(/#kodiak-sheen-rim/);
  });
  it('engine boot is scoped to the three feature stages', () => {
    expect(index).toMatch(/mountPaperboardCards\(\s*'[^']*#generateCampaignSection[^']*#aboutTool/);
    expect(index).not.toMatch(/mountSheenRim/);
  });
  it('engine boot stays behind the lab flag (demo path is CSS-only)', () => {
    expect(index).toMatch(/ember3d/);
  });
});

// Backlog: the shared forest cap must sit flush on the About tool card, no gap.
describe('flush about cap', () => {
  it('the forest divider carries zero surrounding margins', () => {
    expect(css).toMatch(/\.ff-forest\{[^}]*margin:0 var\(--radii-lg\) 0/);
  });
});
