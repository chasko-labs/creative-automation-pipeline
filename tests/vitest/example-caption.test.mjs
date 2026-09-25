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

  it('the figcaption tail IS the click — same star CTA, wired to generate', () => {
    const cap = html.match(/<figcaption class="ff-figcap">([\s\S]*?)<\/figcaption>/);
    expect(cap, 'missing .ff-figcap').not.toBeNull();
    expect(cap[1]).toMatch(/<button class="ff-go ff-figcap-cta"[^>]*>/);
    expect(cap[1]).toMatch(/>Create Campaign Preview</);
    expect(cap[1]).toMatch(/getElementById\('generateCampaign'\)\.click\(\)/);
    expect(cap[1]).toMatch(/Click the button to generate these five sizes/);
    // caption + CTA share a 2-column figcaption: lede left, control cell right.
    expect(css).toMatch(/\.ff-figcap\{[^}]*grid-template-columns:minmax\(0,1fr\) 300px/);
    expect(cap[1]).toMatch(/<div class="ff-figcap-side">/);
    expect(html).toMatch(/id="generateCampaign"/);
  });
});
