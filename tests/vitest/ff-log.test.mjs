import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');
const fflog = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/ff-log.js'), 'utf8');
const counsel = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/coach-counsel.js'), 'utf8');
const generate = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/generate.js'), 'utf8');
const chips = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/prompt-chips.js'), 'utf8');
const sections = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/campaign-sections.js'), 'utf8');

// ff-log: structured client event bus. Console spew alone is not shareable —
// every meaningful action lands one JSON line in the console AND in a capped
// ring buffer downloadable as ff-log.json, so a session pastes as data.
describe('ff-log console bus', () => {
  it('loads first, before the scripts it instruments', () => {
    const log = index.indexOf('js/ff-log.js');
    expect(log).toBeGreaterThan(-1);
    for (const other of ['js/generate.js', 'js/prompt-chips.js', 'js/coach-counsel.js']) {
      expect(index.indexOf(other)).toBeGreaterThan(log);
    }
  });

  it('keeps a capped ring buffer with export and error capture', () => {
    expect(fflog).toMatch(/window\.__FF_LOG__/);
    expect(fflog).toMatch(/window\.ffLog\s*=/);
    expect(fflog).toMatch(/window\.ffLogExport/);
    expect(fflog).toMatch(/CAP = 300/);
    expect(fflog).toMatch(/unhandledrejection/);
    expect(fflog).toMatch(/ffLogExport/);
    expect(fflog).toMatch(/Export log/);
    // at rest there is no provenancePanel — the button docks at the
    // campaign status line instead, and retries on document mutations.
    expect(fflog).toMatch(/generateCampaignStatus/);
    expect(fflog).toMatch(/document\.documentElement \|\| document\.body/);
  });

  it('create emits brief, products, theme, market', () => {
    expect(generate).toMatch(/window\.ffLog\('create', \{brief: brief, products: products, theme: primarySlug, market: selectedLoc\.market\}\)/);
  });

  it('counsel emits render mode with rag flag and apply with patch keys', () => {
    expect(counsel).toMatch(/window\.ffLog\('counsel', \{\s*mode:/);
    expect(counsel).toMatch(/rag: !!\(meta && meta\.rag\)/);
    expect(counsel).toMatch(/renderRecs\(patched, \{ mode: 'server', rag: !!j\.rag \}\)/);
    expect(counsel).toMatch(/window\.ffLog\('counsel-apply', \{label: r\.label, keys: r\.keys/);
    expect(counsel).toMatch(/keys: Object\.keys\(r\.patch/);
  });

  it('dam outcomes flow into the buffer', () => {
    expect(chips).toMatch(/window\.ffLog\('asset-library', \{outcome: outcome, latency_ms: latencyMs/);
  });

  it('full-campaign runs emit start/done/fail with wall-timing', () => {
    expect(sections).toMatch(/window\.ffLog\('campaign-start', \{scope: scope/);
    expect(sections).toMatch(/window\.ffLog\('campaign-done', \{scope: scope, source: runSource, ms: runMs/);
    expect(sections).toMatch(/fallthrough_reason/);
    expect(sections).toMatch(/window\.ffLog\('campaign-fail', \{kind: 'fallback'/);
    expect(sections).toMatch(/window\.ffLog\('campaign-fail', \{kind: 'error'/);
    expect(sections).toMatch(/fallthrough: ' \+ \(info\.fallthrough/);
    expect(sections).toMatch(/client_ms: ' \+ \(info\.ms/);
  });
});
