import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const insights = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/coach-insights.js'), 'utf8');

// Coach insights (Unit 3): on-demand "Why this works" on the preview card.
// Never auto-fetches, never blocks Create/Download, dark without a coach URL.
describe('coach insights', () => {
  it('script loads after the preview it observes, coach URL meta-gated', () => {
    expect(index).toMatch(/js\/coach-insights\.js/);
    expect(index).toMatch(/meta name="kodiak-coach-url"/);
    expect(insights).toMatch(/function coachUrl/);
    expect(insights).toMatch(/if\(!prov \|\| !coachUrl\(\)\) return/);
  });

  it('button mounts only after the provenance panel, one fetch max per preview', () => {
    expect(insights).toMatch(/getElementById\('provenancePanel'\)/);
    expect(insights).toMatch(/id = 'insightsBtn'/);
    expect(insights).toMatch(/one fetch max per preview/);
    expect(insights).toMatch(/lastKey/);
  });

  it('fetches only on button click and fails honestly', () => {
    // exactly one fetch call site in the file, inside the click-driven fetchInsights
    expect(insights.match(/[^.]fetch\(/g).length).toBe(1);
    expect(insights).toMatch(/addEventListener\('click', fetchInsights\)/);
    expect(insights).toMatch(/Insights are busy — try again\./);
  });

  it('never throws into the page', () => {
    expect(insights).toMatch(/never break the page/);
  });
});
