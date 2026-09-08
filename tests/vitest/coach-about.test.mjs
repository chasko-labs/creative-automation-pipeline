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
    expect(about).toMatch(/\.ff-chip\[data-theme="/);
    expect(about).toMatch(/dispatchEvent\(new Event\('input'/);
    expect(about).toMatch(/#marketListbox/);
  });

  it('unknown or missing targets fail honestly, never silently', () => {
    expect(about).toMatch(/Could not find that direction/);
    expect(about).toMatch(/Could not find that market/);
    expect(about).toMatch(/Unknown edit — nothing applied/);
    expect(about).toMatch(/The coach is busy — try again\./);
  });

  it('sends page state, never secrets', () => {
    expect(about).toMatch(/pageState/);
    expect(about).toMatch(/briefLength/);
    expect(about).not.toMatch(/localStorage|sessionStorage|cookie/i);
  });
});
