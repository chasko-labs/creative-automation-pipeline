import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');
const sections = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/campaign-sections.js'), 'utf8');

// #282 — the "locked until preview" badge persisted after reveal because
// .badge sets display:inline-block, which beats the UA [hidden] rule — the
// same trap already patched for the button. Badge and button now hide/unhide
// on the single __kodiakRevealCampaign path.
describe('unlock badge (#282)', () => {
  it('badge hidden attribute is enforced over .badge display', () => {
    expect(css).toMatch(/#generateCampaignLock\[hidden\]\{display:none\}/);
  });

  it('reveal hides the badge and ungates the button in one path', () => {
    const fn = sections.slice(sections.indexOf('__kodiakRevealCampaign'));
    expect(fn).toMatch(/lock\.hidden = true/);
    expect(fn).toMatch(/btn\.hidden = false/);
    expect(fn).toMatch(/data-gated', 'false'/);
  });

  it('gated-toggle guard null-checks the badge (safe post-reveal)', () => {
    expect(sections).toMatch(/var lock = document\.getElementById\('generateCampaignLock'\);\s*\n\s*if\(lock\)/);
  });
});
