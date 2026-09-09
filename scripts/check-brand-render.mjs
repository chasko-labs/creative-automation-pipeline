// render-baseline gate: screenshot/pixel-diff brand render baselines.
//
// Captures the worktree app (local static server, real webfonts) at desktop
// 1440x900 + mobile 390x844 and diffs against committed baselines in
// tests/fixtures/brand-baseline/. Nondeterministic sample-content regions
// (#preview, sample status, filenames) are masked before capture — the gate
// guards brand chrome + layout, not generated pixels.
//
// Chromium-only (repo-local ms-playwright binary, same as check-spectrum).
// Animations + caret are frozen for determinism. Webfonts need network;
// without it, regenerate baselines when back online instead of loosening
// the threshold to excuse font fallback.
//
// Usage: node scripts/check-brand-render.mjs [--update-baselines]
// Exit 0 pass, 1 fail.
import { createServer } from 'node:http';
import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { extname, join, normalize, resolve, dirname } from 'node:path';
import { homedir } from 'node:os';
import { existsSync, readdirSync } from 'node:fs';
import { inflateSync } from 'node:zlib';
import { chromium } from 'playwright';

const REPO = resolve(new URL('.', import.meta.url).pathname, '..');
const APP = join(REPO, 'web', 'kodiak-posts-for-todays-frontier');
const BASE_DIR = join(REPO, 'tests', 'fixtures', 'brand-baseline');
const VIEWPORTS = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const DIFF_FRACTION = 0.003; // at most 0.3% of pixels may differ
const TOLERANCE = 16; // per-channel absolute difference ignored (antialiasing)

const MIME = { '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml',
  '.woff2': 'font/woff2', '.txt': 'text/plain' };

const MASK_JS = `(sels) => {
  document.querySelectorAll(sels.join(',')).forEach((el) => {
    const r = el.getBoundingClientRect();
    const m = document.createElement('div');
    m.setAttribute('data-baseline-mask', '1');
    m.style.cssText = 'position:absolute;left:' + (r.left + scrollX) + 'px;top:' + (r.top + scrollY) +
      'px;width:' + r.width + 'px;height:' + r.height + 'px;background:#E8DDD3;z-index:5;';
    document.body.appendChild(m);
  });
  document.querySelectorAll('*').forEach((el) => {
    el.style.animation = 'none'; el.style.transition = 'none'; el.style.caretColor = 'transparent';
  });
  // inline animation:none does not reach ::before/::after (e.g. the tour sheen
  // sweep) — kill those too so captures are deterministic.
  const freeze = document.createElement('style');
  freeze.textContent = '*,*::before,*::after{animation:none!important;transition:none!important}';
  document.head.appendChild(freeze);
}`;

function findChrome() {
  const dir = join(homedir(), '.cache', 'ms-playwright');
  if (!existsSync(dir)) return null;
  const builds = readdirSync(dir).filter((d) => d.startsWith('chromium-')).sort().reverse();
  for (const b of builds) {
    const p64 = join(dir, b, 'chrome-linux64', 'chrome');
    if (existsSync(p64)) return p64;
    const p = join(dir, b, 'chrome-linux', 'chrome');
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

// Minimal PNG decoder: 8-bit, non-interlaced, truecolor(+alpha). Chromium
// screenshots always take this shape; anything else is a loud failure.
function decodePng(buf) {
  const magic = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
  if (!buf.subarray(0, 8).equals(magic)) throw new Error('not a PNG');
  let pos = 8, width = 0, height = 0, bitDepth = 0, colorType = 0, interlace = 1;
  const idat = [];
  while (pos < buf.length) {
    const len = buf.readUInt32BE(pos);
    const type = buf.toString('ascii', pos + 4, pos + 8);
    const data = buf.subarray(pos + 8, pos + 8 + len);
    if (type === 'IHDR') {
      width = data.readUInt32BE(0); height = data.readUInt32BE(4);
      bitDepth = data[8]; colorType = data[9]; interlace = data[12];
    } else if (type === 'IDAT') idat.push(data);
    else if (type === 'IEND') break;
    pos += 12 + len;
  }
  if (bitDepth !== 8 || interlace !== 0 || ![2, 6].includes(colorType))
    throw new Error(`unsupported PNG shape depth=${bitDepth} color=${colorType} interlace=${interlace}`);
  const ch = colorType === 6 ? 4 : 3;
  const raw = inflateSync(Buffer.concat(idat));
  const stride = width * ch;
  const px = Buffer.alloc(height * stride);
  let p = 0;
  const paeth = (a, b, c) => { const q = a + b - c, pa = Math.abs(q - a), pb = Math.abs(q - b), pc = Math.abs(q - c);
    return pa <= pb && pa <= pc ? a : pb <= pc ? b : c; };
  for (let y = 0; y < height; y++) {
    const f = raw[p++];
    for (let x = 0; x < stride; x++) {
      const v = raw[p++];
      const a = x >= ch ? px[y * stride + x - ch] : 0;
      const b = y > 0 ? px[(y - 1) * stride + x] : 0;
      const c = x >= ch && y > 0 ? px[(y - 1) * stride + x - ch] : 0;
      px[y * stride + x] = (v + (f === 1 ? a : f === 2 ? b : f === 3 ? ((a + b) >> 1) : f === 4 ? paeth(a, b, c) : 0)) & 255;
    }
  }
  return { width, height, ch, px };
}

function diffFraction(a, b) {
  if (a.width !== b.width || a.height !== b.height || a.ch !== b.ch)
    return { frac: 1, note: `dimension mismatch ${a.width}x${a.height}c${a.ch} vs ${b.width}x${b.height}c${b.ch}` };
  let diff = 0;
  const n = a.width * a.height;
  for (let i = 0; i < n; i++) {
    for (let c = 0; c < a.ch; c++) {
      if (Math.abs(a.px[i * a.ch + c] - b.px[i * b.ch + c]) > TOLERANCE) { diff++; break; }
    }
  }
  return { frac: diff / n, note: `${diff}/${n} pixels differ` };
}

const update = process.argv.includes('--update-baselines');
const exe = findChrome();
if (!exe) { console.log('FAIL chromium binary: no ms-playwright chromium found'); process.exit(1); }

const srv = await serve();
const base = `http://127.0.0.1:${srv.address().port}/index.html`;
const browser = await chromium.launch({ executablePath: exe, args: ['--no-sandbox'] });
let failed = 0;
try {
  for (const [name, vp] of Object.entries(VIEWPORTS)) {
    const page = await browser.newPage({ viewport: vp });
    // Dismiss the guided tour before load: it is a dismissible animated guide
    // (covered by vitest + screenshots), and its stop-0 auto-scroll would move
    // the resting viewport run to run. Dismissed, the page rests at top —
    // the same resting state this gate has always guarded.
    await page.addInitScript(() => { try{ localStorage.setItem('kodiak_tour', 'dismissed'); }catch(e){} });
    await page.goto(base, { waitUntil: 'domcontentloaded', timeout: 45000 });
    // Step through the share-gate (courtesy screen): fill the word field
    // with 'cakes', submit, and wait for the app to mount. There is
    // deliberately no query-param bypass, so baselines must exercise this
    // path to guard the real campaign UI.
    try {
      await page.waitForSelector('#kodiak-gate-pw', { timeout: 10000 });
      await page.fill('#kodiak-gate-pw', 'cakes');
      await page.click('#kodiak-gate-form button[type="submit"]');
      await page.waitForSelector('#kodiak-gate', { state: 'detached', timeout: 10000 });
      // submit triggers location.reload(); wait for the reloaded app to settle
      try { await page.waitForLoadState('networkidle', { timeout: 30000 }); } catch (e) {}
      await page.waitForSelector('#generateCampaign', { timeout: 15000 });
    } catch (e) {
      // No gate present (already stepped through) — continue to capture.
    }
    await page.waitForTimeout(2500);
    // settle webfonts before capture — a late Typekit swap re-rasterizes text
    // (and shifts composited edges) nondeterministically between runs.
    try{ await page.evaluate(() => Promise.race([document.fonts.ready, new Promise((r)=>setTimeout(r,8000))])); }catch(e){}
    // pin scroll: the tour's smooth scrollIntoView may still be mid-flight at
    // capture time, shifting every pixel nondeterministically between runs.
    try{ await page.evaluate(() => window.scrollTo(0, 0)); }catch(e){}
    await page.waitForTimeout(400);
    // settle lazy images: a tile decoding between mask and capture shifts
    // ~1k pixels nondeterministically (mobile is the canary).
    try{
      await page.evaluate(() => Promise.race([
        Promise.all([...document.images].map((img) => img.complete || new Promise((res) => {
          img.addEventListener('load', res, { once: true });
          img.addEventListener('error', res, { once: true });
        }))),
        new Promise((r) => setTimeout(r, 8000)),
      ]));
    }catch(e){}
    await page.waitForTimeout(400);
    // #ffTour masked: it is a dismissible animated guide whose live position
    // tracks layout — brand chrome around it stays guarded, and the tour
    // itself is covered by vitest structural tests + screenshots.
    await page.evaluate(MASK_JS, ['#preview', '#sampleStatus', '#fileNames', '#featuredFrontier', '#ffTour']);
    const shot = await page.screenshot();
    await page.close();
    const basePath = join(BASE_DIR, `${name}.png`);
    if (update || !existsSync(basePath)) {
      await mkdir(dirname(basePath), { recursive: true });
      await writeFile(basePath, shot);
      console.log(`ok baseline/${name} — wrote ${basePath}`);
      continue;
    }
    const d = diffFraction(decodePng(await readFile(basePath)), decodePng(shot));
    const ok = d.frac <= DIFF_FRACTION;
    if (!ok) failed++;
    console.log(`${ok ? 'ok' : 'FAIL'} baseline/${name} — ${d.note} (threshold ${DIFF_FRACTION * 100}%)`);
  }
} finally {
  await browser.close();
  srv.close();
}
console.log(`render-baseline ${failed ? 'FAIL' : 'PASS'}`);
process.exit(failed ? 1 : 0);
