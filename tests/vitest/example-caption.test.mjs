import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const web = (...parts) =>
  resolve(root, 'web/kodiak-posts-for-todays-frontier', ...parts);
const css = readFileSync(web('design/components.css'), 'utf8');
const html = readFileSync(web('index.html'), 'utf8');

function ruleFor(selector) {
  const m = css.match(new RegExp(`${selector}\\{([^}]*)\\}`));
  return m ? m[1] : null;
}

describe('example tile captions', () => {
  it('caption rows are fixed: title ellipsis line plus one unbreakable spec line', () => {
    // title owns its own ellipsis line so ragged wraps cannot stagger cards
    expect(ruleFor('.render-tile .render-cap b')).toMatch(/display\s*:\s*block/);
    expect(ruleFor('.render-tile .render-cap b')).toMatch(/text-overflow\s*:\s*ellipsis/);
    // shape + dims ride one shared nowrap ellipsis row in CSS and in markup
    expect(ruleFor('.render-tile .render-cap .rt-spec')).toMatch(
      /white-space\s*:\s*nowrap/,
    );
    expect(ruleFor('.render-tile .render-cap .rt-spec')).toMatch(
      /text-overflow\s*:\s*ellipsis/,
    );
    expect(html).toMatch(/rt-spec"><span class="dims">/);
    expect(html).toMatch(/rt-spec"><span class="rt-shape">/);
  });

  it('shape descriptor folds into the same line, not a duplicate', () => {
    expect(ruleFor('.render-tile .render-cap .rt-shape')).toMatch(
      /display\s*:\s*inline/,
    );
    expect(html).not.toMatch(/rt-shape">Vertical \/ Full-Screen</);
  });

  it('the figcaption is disclosure only — one Create lives on the page', () => {
    // the duplicate figcaption CTA was deliberately removed (d0ce03f): the
    // caption carries the Market context disclosure, and exactly one Create
    // Campaign Preview button exists, at #generateCampaign.
    const cap = html.match(/<figcaption class="ff-figcap">([\s\S]*?)<\/figcaption>/);
    expect(cap, 'missing .ff-figcap').not.toBeNull();
    expect(cap[1]).toMatch(/<summary>Market context<\/summary>/);
    expect(cap[1]).toMatch(/ff-figcap-lede/);
    expect(cap[1]).not.toMatch(/ff-figcap-cta/);
    expect(cap[1]).not.toMatch(/ff-figcap-side/);
    expect(css).not.toMatch(/ff-figcap-cta/);
    const creates = html.match(/>Create Campaign Preview</g) || [];
    expect(creates).toHaveLength(1);
    expect(html).toMatch(/id="generateCampaign"/);
  });
});
