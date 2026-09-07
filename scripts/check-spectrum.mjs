// spectrum-a11y gate: resolved computed values for contrast, focus rings,
// touch targets, light/dark, forced colors, and large scale.
//
// Chromium-only by design: uses the repo-local ms-playwright Chromium binary
// via executablePath (no browser download, no network install). Firefox/WebKit
// binaries are intentionally absent — Chromium is the gate; other engines are
// out of scope until a failure proves otherwise.
//
// Serves the worktree over a local static server (so webfonts + relative
// asset paths resolve exactly as deployed) and asserts numeric verdicts.
// Exit 0 pass, 1 fail.
import { createServer } from 'node:http';
import { readFile } from 'node:fs/promises';
import { extname, join, normalize, resolve } from 'node:path';
import { homedir } from 'node:os';
import { existsSync, readdirSync } from 'node:fs';
import { chromium } from 'playwright';

const REPO = resolve(new URL('.', import.meta.url).pathname, '..');
const APP = join(REPO, 'web', 'kodiak-posts-for-todays-frontier');

const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2', '.txt': 'text/plain' };

function findChrome() {
  const dir = join(homedir(), '.cache', 'ms-playwright');
  if (!existsSync(dir)) return null;
  const builds = readdirSync(dir).filter((d) => d.startsWith('chromium-')).sort().reverse();
  for (const b of builds) {
    const p = join(dir, b, 'chrome-linux', 'chrome');
    const p64 = join(dir, b, 'chrome-linux64', 'chrome');
    if (existsSync(p64)) return p64;
    if (existsSync(p)) return p;
  }
  return null;
}

function serve() {
  return new Promise((done) => {
    const srv = createServer(async (req, res) => {
      try {
        const urlPath = decodeURIComponent(new URL(req.url, 'http://x').pathname);
        const file = normalize(join(APP, urlPath === '/' ? '/index.html' : urlPath));
        if (!file.startsWith(APP)) { res.writeHead(403); res.end(); return; }
        const body = await readFile(file);
        res.writeHead(200, { 'Content-Type': MIME[extname(file)] || 'application/octet-stream' });
        res.end(body);
      } catch { res.writeHead(404); res.end(); }
    });
    srv.listen(0, '127.0.0.1', () => done(srv));
  });
}

function luminance([r, g, b]) {
  const f = (c) => { c /= 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}
function ratio(fg, bg) {
  const a = luminance(fg), b = luminance(bg);
  return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
}
function parseRgb(s) {
  const m = s.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/);
  return m ? [ +m[1], +m[2], +m[3] ] : null;
}

const results = [];
function check(name, ok, detail) {
  results.push({ name, ok: !!ok, detail });
  console.log(`${ok ? 'ok' : 'FAIL'} ${name}${detail ? ` — ${detail}` : ''}`);
}

const exe = findChrome();
if (!exe) { console.log('FAIL chromium binary: no ms-playwright chromium found'); process.exit(1); }

const srv = await serve();
const base = `http://127.0.0.1:${srv.address().port}/index.html?cakes=1`;
const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox'] });
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page.goto(base, { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(2500);

  // disclosures that hide their controls at rest must be opened before sampling —
  // a collapsed control has no box and no focus ring by design, not by defect.
  for (const det of ['#scopeWrap', '#existingAssets']) {
    await page.evaluate((s) => { const d = document.querySelector(s); if (d && !d.open) d.open = true; }, det);
  }
  await page.waitForTimeout(300);

  // 1. contrast — resolved computed colors, WCAG ratios.
  // bgOf climbs to the nearest opaque ancestor: transparent layers parse as
  // black and would manufacture a failing ratio out of thin air.
  const pairs = await page.evaluate(() => {
    const cs = (sel, prop) => { const el = document.querySelector(sel); return el ? getComputedStyle(el)[prop] : null; };
    const opaque = (el) => {
      let n = el;
      while (n && n !== document.documentElement) {
        const bg = getComputedStyle(n).backgroundColor;
        const m = bg.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/);
        if (m && (m[4] === undefined || parseFloat(m[4]) >= 1)) return bg;
        n = n.parentElement;
      }
      return getComputedStyle(document.body).backgroundColor;
    };
    const bgOf = (sel) => { const el = document.querySelector(sel); return el ? opaque(el) : null; };
    return [
      { name: 'body-copy', fg: cs('.ff-about__copy', 'color'), bg: bgOf('.ff-about') || cs('body', 'backgroundColor') },
      { name: 'create-cta', fg: cs('#generateCampaign', 'color'), bg: bgOf('#generateCampaign') },
      { name: 'scope-selected', fg: cs('.ff-scope-opt[aria-checked="true"] .ff-scope-opt-title', 'color'), bg: bgOf('.ff-scope-opt[aria-checked="true"]') },
      { name: 'chip-idle', fg: cs('.ff-chip', 'color'), bg: bgOf('.ff-chip') },
    ];
  });
  for (const p of pairs) {
    const fg = parseRgb(p.fg || ''), bg = parseRgb(p.bg || '');
    if (!fg || !bg) { check(`contrast/${p.name}`, false, 'unresolvable colors'); continue; }
    const r = ratio(fg, bg);
    check(`contrast/${p.name}`, r >= 4.5, `${r.toFixed(2)}:1 (floor 4.5)`);
  }

  // 2. focus rings — focus each control, read resolved outline
  const focusSels = ['#generateCampaign', '.ff-scope-opt[data-scope="local"]', '.ff-chip',
    '#marketDisclosure summary', '#productSearch', '#campaignBrief', '#damBrowseTrigger'];
  for (const sel of focusSels) {
    const o = await page.evaluate((s) => {
      const el = document.querySelector(s);
      if (!el) return null;
      el.focus();
      const cs = getComputedStyle(el);
      return { style: cs.outlineStyle, width: cs.outlineWidth };
    }, sel);
    if (!o) { check(`focus/${sel}`, false, 'missing element'); continue; }
    const w = parseFloat(o.width) || 0;
    check(`focus/${sel}`, o.style !== 'none' && w >= 2, `${o.style} ${o.width}`);
  }

  // 3. touch targets — primary CTA 44px floor, everything sampled 24px (WCAG 2.5.8)
  const sizes = await page.evaluate((sels) => sels.map((s) => {
    const el = document.querySelector(s);
    if (!el) return { sel: s, missing: true };
    const r = el.getBoundingClientRect();
    return { sel: s, h: Math.round(r.height), w: Math.round(r.width) };
  }), ['#generateCampaign', ...focusSels.slice(1)]);
  for (const s of sizes) {
    if (s.missing) { check(`touch/${s.sel}`, false, 'missing'); continue; }
    const floor = s.sel === '#generateCampaign' ? 44 : 24;
    check(`touch/${s.sel}`, s.h >= floor, `${s.w}x${s.h}px (floor ${floor})`);
  }

  // 4. dark scheme + forced colors smoke — key controls stay visible
  for (const mode of [{ colorScheme: 'dark' }, { forcedColors: 'active' }]) {
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, ...mode });
    const pg = await ctx.newPage();
    await pg.goto(base, { waitUntil: 'networkidle', timeout: 45000 });
    await pg.waitForTimeout(1500);
    const vis = await pg.evaluate(() => ['header.kodiak-header', '#generateCampaign', '#campaignBrief']
      .every((s) => { const el = document.querySelector(s); if (!el) return false;
        const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0; }));
    check(`smoke/${Object.keys(mode)[0]}`, vis, vis ? 'controls visible' : 'controls missing');
    await ctx.close();
  }

  // 5. small-scale robustness — a 320px viewport must not scroll horizontally.
  // (Body-level CSS zoom is NOT used: it scales layout without shrinking the
  // layout viewport, manufacturing overflow no real browser zoom produces.)
  const narrow = await browser.newPage({ viewport: { width: 320, height: 700 } });
  await narrow.goto(base, { waitUntil: 'networkidle', timeout: 45000 });
  await narrow.waitForTimeout(1500);
  const overflow = await narrow.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  check('scale/narrow-320', overflow <= 1, `overflow ${overflow}px`);
  await narrow.close();
} finally {
  await browser.close();
  srv.close();
}

const failed = results.filter((r) => !r.ok);
console.log(`spectrum-a11y ${failed.length ? 'FAIL' : 'PASS'} (${results.length - failed.length}/${results.length})`);
process.exit(failed.length ? 1 : 0);
