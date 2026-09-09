import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const about = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/coach-about.js'), 'utf8');

// Coach Q&A (Unit 4): ask box inside collapsed #aboutTool, answers plus
// confirm-to-apply edits. Nothing applies without a click; nothing fetches
// until asked; dark without a coach URL.
describe('coach about Q&A', () => {
  it('script loads and mounts only inside #aboutTool when a coach URL exists', () => {
    expect(index).toMatch(/js\/coach-about\.js/);
    expect(about).toMatch(/querySelector\('#aboutTool \.body'\)/);
    expect(about).toMatch(/if\(document\.getElementById\('coachAsk'\) \|\| !coachUrl\(\)\) return/);
  });

  it('edits render as confirm chips; dispatch needs the click', () => {
    expect(about).toMatch(/coach-confirm/);
    expect(about).toMatch(/addEventListener\('click', function\(\)\{ applyEdit/);
    // all three ops reuse the page's own controls — no shadow state
    expect(about).toMatch(/\.ff-check-card__input\[data-theme="/);
    expect(about).toMatch(/dispatchEvent\(new Event\('input'/);
    expect(about).toMatch(/#marketListbox/);
  });

  it('unknown or missing targets fail honestly, never silently', () => {
    expect(about).toMatch(/Could not find that direction/);
    expect(about).toMatch(/Could not find that market/);
    expect(about).toMatch(/Unknown edit — nothing applied/);
    expect(about).toMatch(/The coach is busy — try again\./);
  });

  it('about copy is the exact brainstorm line; coach button carries the exact label', () => {
    expect(index).toContain(
      '<p class="ff-about__copy">Here to brainstorm with you through creation of a Kodiak Cakes campaign. Here&#39;s how things work behind the scenes:</p>'
    );
    // reference links survive the copy swap
    expect(index).toMatch(/ff-doclinks/);
    expect(index).toMatch(/pipeline\.html/);
    expect(about).toContain('id="coachGo">ask about this automation tool</button>');
  });

  it('coach ask box is styled with token var()s only', () => {
    const css = readFileSync(
      resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');
    const block = css.slice(css.indexOf('#coachAsk{'));
    expect(block.length).toBeGreaterThan(100);
    const rules = block.slice(0, block.indexOf('/* About-this-tool'));
    expect(rules).toMatch(/#coachAsk/);
    // no raw hex / rgb slop outside var() fallbacks (fallbacks mirror the
    // repo's own var(--colors-brand-box-parchment,#F5EAD3) pattern)
    const bare = rules.replace(/var\([^)]*\)/g, 'var()');
    expect(bare).not.toMatch(/#[0-9a-fA-F]{3,8}\b/);
    expect(bare).not.toMatch(/rgba?\(/);
  });

  it('sends page state, never secrets', () => {
    expect(about).toMatch(/pageState/);
    expect(about).toMatch(/briefLength/);
    expect(about).not.toMatch(/localStorage|sessionStorage|cookie/i);
  });
});
