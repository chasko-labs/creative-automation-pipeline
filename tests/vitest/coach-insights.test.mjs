import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const counsel = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/coach-counsel.js'), 'utf8');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');

// Campaign counsel (replaces passive "Why this works"): adversarial
// recommendations with per-item Apply that writes through real controls via
// real events and reruns Create — approval only, never auto.
describe('campaign counsel', () => {
  it('script is wired into the page, old insights retired', () => {
    expect(index).toMatch(/js\/coach-counsel\.js/);
    expect(index).not.toMatch(/js\/coach-insights\.js/);
  });

  it('renders recommendations with per-item Apply plus apply-all', () => {
    expect(counsel).toMatch(/ff-counsel-apply/);
    expect(counsel).toMatch(/data-counsel-all/);
    expect(counsel).toMatch(/Apply all/);
  });

  it('applies through real controls and real events, then reruns Create', () => {
    // brief: set value + input event
    expect(counsel).toMatch(/getElementById\('campaignBrief'\)/);
    expect(counsel).toMatch(/dispatchEvent\(new Event\('input', \{ bubbles: true \}\)\)/);
    // market: select + change event
    expect(counsel).toMatch(/getElementById\('locality'\)/);
    expect(counsel).toMatch(/dispatchEvent\(new Event\('change', \{ bubbles: true \}\)\)/);
    // theme + products via native clicks (all delegated handlers run)
    expect(counsel).toMatch(/getElementById\('randomProducts'\)/);
    expect(counsel).toMatch(/function checkTheme\(dataTheme\)/);
    expect(counsel).toMatch(/\.ff-check-card__input\[data-theme=/);
    // rerun is a real Create click
    expect(counsel).toMatch(/getElementById\('generateCampaign'\)/);
  });

  it('counsel rules are local, deterministic, and grounded in live state', () => {
    expect(counsel).toMatch(/ruleThinBrief/);
    expect(counsel).toMatch(/ruleNoProducts/);
    expect(counsel).toMatch(/ruleRetailer/);
    expect(counsel).toMatch(/store-finder-markets\.json/);
  });

  it('KODIAK copy law holds on applied briefs (refuse, never launder)', () => {
    expect(counsel).toMatch(/KODIAK/);
    expect(counsel).toMatch(/return ok/);
  });

  it('no auto-apply, no auto-fetch; counsel-token CSS only', () => {
    // counsel runs only from its button; reruns only from Apply handlers
    expect(counsel).toMatch(/addEventListener\('click', counsel\)/);
    expect((counsel.match(/rerunPreview\(\);/g) || []).length).toBe(2);
    expect(counsel).not.toMatch(/setTimeout\(counsel|setInterval\(/);
    const start = css.indexOf('/* === Campaign counsel');
    expect(start, 'counsel CSS marker').toBeGreaterThan(-1);
    const block = css.slice(start);
    expect(block).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
  });
});
