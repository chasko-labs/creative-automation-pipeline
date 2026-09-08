import { describe, expect, it } from 'vitest';
import { readFileSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const web = resolve(root, 'web/kodiak-posts-for-todays-frontier');
const jsDir = resolve(web, 'js');

const read = (p) => readFileSync(p, 'utf8');
const jsFiles = readdirSync(jsDir).filter((f) => f.endsWith('.js'));
const sources = Object.fromEntries(jsFiles.map((f) => [f, read(resolve(jsDir, f))]));
const allJs = jsFiles.map((f) => sources[f]).join('\n---\n');
const html = read(resolve(web, 'index.html'));

// #197 — geolocation consent: no location resolution of any kind until the user
// explicitly taps "My location". The market dropdown (Park City default) is the
// default path. Fast, no browser: guards the shipped source itself.

describe('#197 geolocation consent — zero calls on clean load', () => {
  it('getCurrentPosition appears exactly once, inside the My-location tap handler', () => {
    const hits = [];
    for (const [f, src] of Object.entries(sources)) {
      let i = src.indexOf('getCurrentPosition');
      while (i !== -1) {
        hits.push({ file: f, index: i });
        i = src.indexOf('getCurrentPosition', i + 1);
      }
    }
    expect(hits, 'expected exactly one getCurrentPosition call site').toHaveLength(1);
    expect(hits[0].file).toBe('market-disclosure.js');
    const before = sources['market-disclosure.js'].slice(
      Math.max(0, hits[0].index - 2000),
      hits[0].index,
    );
    expect(before).toMatch(/getElementById\('useMyLocation'\)/);
    expect(before).toMatch(/addEventListener\('click'/);
  });

  it('no watchPosition / GPS tracking anywhere in the frontend', () => {
    expect(allJs).not.toMatch(/watchPosition/);
    expect(allJs).not.toMatch(/clearWatch/);
  });

  it('no IP-inference / edge-geo fetch anywhere in the frontend', () => {
    expect(allJs).not.toMatch(/ipinfo|ip-api|ipapi\.co|geoip|maxmind/i);
    expect(allJs).not.toMatch(/CloudFront-Viewer|cf-ipcountry/i);
  });
});

describe('#197 mock coords are tap-gated, never auto-applied', () => {
  it('data-core stashes ?mockLat&mockLon without touching #locality on load', () => {
    const src = sources['data-core.js'];
    expect(src).toMatch(/window\.__mockGeo\s*=\s*\{lat,\s*lon\}/);
    const blockStart = src.indexOf('Consent-gated mock coordinates');
    expect(blockStart, 'consent-gated mock block missing').toBeGreaterThan(-1);
    // The on-load block ends at the next section header; it must not mutate selection.
    const sectionEnd = src.indexOf('// === AXIS 2', blockStart);
    const block = src.slice(blockStart, sectionEnd === -1 ? undefined : sectionEnd);
    expect(block).not.toMatch(/\.value\s*=/);
    expect(block).not.toMatch(/dispatchEvent/);
    expect(block).not.toMatch(/nearestMarketForCoords\(/);
  });

  it('tap handler consumes the staged mock coords', () => {
    expect(sources['market-disclosure.js']).toMatch(/window\.__mockGeo/);
  });
});

describe('#197 market dropdown remains the default path', () => {
  it('My-location button and market disclosure exist in index.html', () => {
    expect(html).toMatch(/id="useMyLocation"/);
    expect(html).toMatch(/id="marketDisclosure"/);
  });

  it('#locality select is owned by JS (the value generate() reads)', () => {
    expect(sources['data-core.js']).toMatch(/getElementById\('locality'\)/);
  });

  it('Park City 84098 is the seeded default', () => {
    expect(allJs).toMatch(/US-MW-PARKCITY-84098/);
    expect(sources['data-core.js']).toMatch(
      /localitySel\.value\s*=\s*"US-MW-PARKCITY-84098"|value="US-MW-PARKCITY-84098"|DEFAULT_MARKET = 'US-MW-PARKCITY-84098'/,
    );
  });
});
