import { describe, expect, it } from 'vitest';
import { readFileSync, existsSync, readdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const web = resolve(root, 'web/kodiak-posts-for-todays-frontier');
const deploy = readFileSync(resolve(root, 'scripts/deploy-frontier.sh'), 'utf8');

// #253/#254: files merged on main 404'd live because scripts/deploy-frontier.sh
// never shipped them — root files need an explicit FILES entry, and the hero
// photo dir was missing from DIRS. This guard fails the suite the moment an
// HTML/JS static reference outruns the deploy include set again.
function deploySet() {
  const files = new Set(
    [...deploy.matchAll(/^\s*"([^"|]+\|[^"|]+\|[^"|]+)"\s*$/gm)].map((m) => m[1].split('|')[0]),
  );
  const dirs = [...deploy.matchAll(/^\s*"([A-Za-z0-9_/-]+)"\s*$/gm)]
    .map((m) => m[1])
    .filter((d) => !d.includes('|') && !d.includes('.'));
  return { files, dirs };
}

// Local static refs from markup: href=/src= minus externals, anchors,
// query strings, above-web-root (..) escapes, and .html page links (all four
// pages ship via FILES; cross-links between them are always deployed).
function htmlRefs() {
  const refs = new Set();
  for (const page of ['index.html', 'details.html', 'pipeline.html', 'infrastructure.html']) {
    const html = readFileSync(resolve(web, page), 'utf8');
    for (const m of html.matchAll(/(?:src|href)="([^"#]+)"/g)) {
      let u = m[1].split('?')[0];
      if (/^(https?:|data:)/.test(u) || u.startsWith('#') || u.startsWith('..')) continue;
      if (u.endsWith('.html')) continue;
      refs.add(`${page}: ${u}`);
    }
  }
  return [...refs];
}

// Quoted relative static paths inside js/ (dynamic fetch/img refs such as the
// DEFAULT_HERO_SRC). Absolute API routes (leading /) are not static assets.
function jsRefs() {
  const refs = new Set();
  for (const f of readdirSync(resolve(web, 'js')).filter((f) => f.endsWith('.js'))) {
    const src = readFileSync(resolve(web, 'js', f), 'utf8');
    for (const m of src.matchAll(/["'`](assets|data|fonts|design|input_assets)\/[^"'`]+["'`]/g)) {
      refs.add(`${f}: ${m[0].slice(1, -1).split('?')[0]}`);
    }
  }
  return [...refs];
}

function covered(ref, { files, dirs }) {
  const u = ref.replace(/^[^:]+: /, '');
  if (files.has(u)) return true;
  return dirs.some((d) => u === d || u.startsWith(d + '/'));
}

describe('deploy asset coverage (#253, #254)', () => {
  it('every static ref in the four pages ships via FILES or DIRS', () => {
    const set = deploySet();
    const missing = htmlRefs().filter((r) => !covered(r, set));
    expect(missing).toEqual([]);
  });

  it('every static ref inside js/ ships via DIRS', () => {
    const set = deploySet();
    const missing = jsRefs().filter((r) => !covered(r, set));
    expect(missing).toEqual([]);
  });

  it('every deployed ref exists in the web source tree (no phantom entries)', () => {
    const { files, dirs } = deploySet();
    const phantom = [...files].filter((f) => !existsSync(resolve(web, f)));
    expect(phantom).toEqual([]);
    const phantomDirs = dirs.filter((d) => !existsSync(resolve(web, d)));
    expect(phantomDirs).toEqual([]);
  });

  it('#254: favicon set + apple-touch-icon ship with image content-types', () => {
    expect(deploy).toMatch(/"favicon\.ico\|favicon\.ico\|image\/x-icon"/);
    expect(deploy).toMatch(/"favicon\.svg\|favicon\.svg\|image\/svg\+xml"/);
    expect(deploy).toMatch(/"apple-touch-icon\.png\|apple-touch-icon\.png\|image\/png"/);
  });

  it('#253: the committed hero photo dir syncs wholesale', () => {
    const { dirs } = deploySet();
    expect(dirs).toContain('input_assets');
    expect(existsSync(resolve(web, 'input_assets/textless/cabin-table.jpg'))).toBe(true);
  });
});
