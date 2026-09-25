import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const web = (...parts) =>
  resolve(root, 'web/kodiak-posts-for-todays-frontier', ...parts);

const css = readFileSync(web('design/components.css'), 'utf8');
const html = readFileSync(web('index.html'), 'utf8');
const gen = readFileSync(web('js/generate.js'), 'utf8');
const dts = readFileSync(web('js/globals.d.ts'), 'utf8');

// One horizontal language: the product carousel and Output Preview share the
// ff-filmstrip pattern — hidden native scrollbar, scroll-snap, keyboard focus,
// reduced-motion guard, dependency-free lightbox.
describe('ff-filmstrip shared pattern', () => {
  it('product carousel hides its native scrollbar but keeps overflow scroll', () => {
    expect(css).toMatch(/\.ff-product-carousel\{[^}]*overflow-x:auto/);
    expect(css).toMatch(/\.ff-product-carousel\{[^}]*scrollbar-width:none/);
    expect(css).toMatch(
      /\.ff-product-carousel::-webkit-scrollbar\{display:none\}/,
    );
  });

  it('product carousel keeps scroll-snap and drops the parchment fill', () => {
    expect(css).toMatch(
      /\.ff-product-carousel\{[^}]*scroll-snap-type:x proximity/,
    );
    const rule =
      css.match(/\.ff-product-carousel\{[^}]*\}/)?.[0] || '';
    expect(rule).not.toMatch(/#F5EAD3/i);
    expect(rule).toMatch(/kraft/i);
  });

  it('filmstrip track hides its scrollbar, snaps, and stays focusable', () => {
    expect(css).toMatch(/\.ff-filmstrip__track\{[^}]*overflow-x:auto/);
    expect(css).toMatch(/\.ff-filmstrip__track\{[^}]*scroll-snap-type:x/);
    expect(css).toMatch(/\.ff-filmstrip__track\{[^}]*scrollbar-width:none/);
    expect(css).toMatch(
      /\.ff-filmstrip__track::-webkit-scrollbar\{display:none\}/,
    );
    expect(css).toMatch(/\.ff-filmstrip__track:focus-visible\{/);
  });

  it('filmstrip styles live in components.css, not an inline style block', () => {
    expect(html).not.toMatch(/id="ff-filmstrip-styles"/);
    expect(css).toMatch(/\.ff-filmstrip__slot\[data-ratio="1x1"\]/);
    expect(css).toMatch(/\.ff-filmstrip__slot\[data-ratio="blog"\]/);
  });

  it('reduced-motion guard covers track snap and button transitions', () => {
    expect(css).toMatch(
      /@media\(prefers-reduced-motion:reduce\)\{[^}]*\.ff-filmstrip__track\{[^}]*scroll-snap-type:none/,
    );
  });

  it('lightbox show/hide rides the hidden attribute (zero-JS-scroll untouched)', () => {
    expect(css).toMatch(/#ffLightbox\[hidden\]\{display:none!important\}/);
    expect(html).toMatch(/id="ffLightbox"[^>]*hidden/);
    expect(gen).toMatch(/box\.hidden = false/);
    expect(gen).toMatch(/box\.hidden = true/);
  });

  it('lightbox has buttons-only chrome with keyboard + focus-trap wiring', () => {
    for (const id of ['ffLightboxPrev', 'ffLightboxNext', 'ffLightboxClose']) {
      expect(html).toContain(`id="${id}"`);
    }
    expect(gen).toMatch(/ffLightboxKeys/);
    expect(gen).toMatch(/Escape/);
    expect(gen).toMatch(/focus trap/);
  });

  it('resting strip keeps the render aliases and TILE_ORDER the contracts read', () => {
    const classes = [...html.matchAll(/render-tile\s+(r-[0-9a-z]+)/g)].map(
      (m) => m[1],
    );
    expect(classes).toEqual(['r-blog', 'r-1x1', 'r-16x9', 'r-4x5', 'r-9x16']);
    expect(html).toMatch(/ff-filmstrip__slot render-tile/);
    expect(html).toMatch(/ff-filmstrip__frame render-frame/);
    expect(html).toMatch(/render-cap ff-filmstrip__cap/);
  });

  it('live renders build the same strip (no vertical stack, downloads kept)', () => {
    expect(gen).toMatch(/ff-filmstrip__slot render-tile/);
    expect(gen).toMatch(/ff-filmstrip__track render-set/);
    expect(gen).toMatch(/ff-filmstrip__dl/);
    expect(gen).toMatch(/tile\.dataset\.ratio/);
    expect(gen).toMatch(/KODIAK_wireFilmstrip/);
  });

  it('no gesture or carousel library sneaks in', () => {
    expect(gen.toLowerCase()).not.toMatch(/hammer|swiper|flickity|glide/);
    expect(html.toLowerCase()).not.toMatch(/swiper|flickity/);
  });
});

// Logo blend + composing/timeout tokens: the cardboard board sheets blend with
// the header (no opaque fill, no edge) and vanish on scroll; the composing
// pulse keyframes and rung-badge colors live in components.css, never in JS.
describe('kodiak logo blend + composing tokens', () => {
  it('logo board sheets blend — no border, no flat fill, multiply wash', () => {
    const rule =
      css.match(/\.kodiak-header__logos::before,\.kodiak-header__logos::after\{[^}]*\}/)?.[0] || '';
    expect(rule).not.toMatch(/border:1px solid/);
    expect(rule).toMatch(/mix-blend-mode:multiply/);
    expect(rule).toMatch(/opacity:\.85/);
    expect(rule).toMatch(/linear-gradient\(180deg,transparent/);
    expect(rule).not.toMatch(/background-color:/);
  });

  it('no cardboard on scroll — sticky fades the sheets, header stays sticky', () => {
    expect(css).toMatch(
      /\.kodiak-header\.is-sticky \.kodiak-header__logos::before,\.kodiak-header\.is-sticky \.kodiak-header__logos::after\{opacity:0\}/,
    );
    expect(css).toMatch(/header\.kodiak-header\{[^}]*position:sticky[^}]*top:0/);
  });

  it('composing pulse keyframes live in CSS, not a JS-injected style tag', () => {
    expect(css).toMatch(
      /@keyframes genpulse\{0%\{background-position:200% 0\}100%\{background-position:-200% 0\}\}/,
    );
    expect(gen).not.toMatch(/genPulseKeyframes/);
  });

  it('rung badge resolves through token classes, never inline hex', () => {
    expect(css).toMatch(
      /\.gen-badge\.is-live\{[^}]*var\(--colors-brand-frontier-green\)/,
    );
    expect(css).toMatch(
      /\.gen-badge\.is-fallback\{[^}]*var\(--colors-brand-signal-red\)/,
    );
    expect(gen).toMatch(/badge\.className='badge gen-badge'/);
    expect(gen).toMatch(/classList\.add\(rb\.fallback \? 'is-fallback' : 'is-live'\)/);
    const paint =
      gen.match(/const paintRungBadge = \(badge, rb\)=>\{[^}]*\}/)?.[0] || '';
    expect(paint).not.toMatch(/#/);
  });

  it('composing helpers carry JSDoc types and the extend entry is declared', () => {
    const params = gen.match(/@param \{string\} ratio/g) || [];
    expect(params.length).toBeGreaterThanOrEqual(3);
    expect(gen).toMatch(/@param \{boolean\} on/);
    expect(gen).toMatch(/@param \{unknown\} engine/);
    expect(dts).toMatch(/KODIAK_extendTallTiles\?:/);
  });

  it('composing and honest fallback marks keep their copy', () => {
    expect(gen).toMatch(/· composing/);
    expect(gen).toMatch(/· cover-pad/);
    expect(gen).toMatch(/· composed/);
  });
});

// Second pass: behind-the-scenes composing statuses, fallback retry, chips on
// brand, complementing captions, arrows off the thumbnails.
describe('frontier polish pass', () => {
  it('composing roller names real pipeline phases and cleans up', () => {
    expect(gen).toMatch(/Nova Micro reviewing campaign copy/);
    expect(gen).toMatch(/Nova Pro composing the hero/);
    expect(gen).toMatch(/Sending your brief \+ market/);
    expect(gen).toMatch(/stageTimers\.forEach\(\(t\)=>\{ try\{ clearTimeout\(t\); \}catch\(e\)\{\} \}\)/);
    expect(gen).not.toMatch(/stageT1 = setTimeout/);
  });

  it('wall-timeout fallthrough auto-retries, double miss is honest', () => {
    expect(gen).toMatch(/id = 'genRetry'/);
    expect(gen).toMatch(/Try again — models are warm now/);
    expect(gen).toMatch(/AUTO-RETRY ONCE/);
    // fallback pixels are never presented as the campaign on a double miss.
    expect(gen).toMatch(/Render miss — nothing generated/);
    expect(gen).not.toMatch(/fallback pixels shown, not the campaign/);
    expect(css).toMatch(/\.ff-retry\{[^}]*var\(--colors-brand-frontier-green\)/);
  });

  it('live strip spans the preview tile grid full width', () => {
    // #preview.preview is an auto-fill tile grid: without 1/-1 the live
    // strip squeezes into one 240px column and tiles render as slivers.
    expect(css).toMatch(/#preview > \.ff-filmstrip\{grid-column:1\/-1\}/);
  });

  it('filmstrip arrows live in flanking grid gutters, never overlaid', () => {
    const rule =
      css.match(/\.ff-filmstrip__arrow\{[^}]*\}/)?.[0] || '';
    expect(rule).not.toMatch(/position:absolute/);
    expect(css).not.toMatch(/\.ff-filmstrip__arrow--prev\{left:/);
    expect(css).toMatch(/\.ff-filmstrip__arrow--prev\{grid-area:prev\}/);
    expect(css).toMatch(/\.ff-filmstrip__arrow--next\{grid-area:next\}/);
    // 64px senior-friendly targets with explicit verbal labels.
    expect(rule).toMatch(/min-width:64px/);
    expect(rule).toMatch(/min-height:64px/);
    expect(css).toMatch(/\.ff-filmstrip__arrow \.ff-tlabel/);
    expect(html).toMatch(/Prev assets/);
    expect(html).toMatch(/Next assets/);
    expect(gen).toMatch(/Prev assets/);
  });

  it('pills and control chips ride parchment, not near-white', () => {
    const pill =
      css.match(/\.ff-publish-targets \.ff-publish-pill\{[^}]*\}/)?.[0] || '';
    expect(pill).toMatch(/var\(--colors-brand-box-parchment\)/);
    expect(pill).not.toMatch(/neutral-50/);
    expect(css).toMatch(
      /\.ff-season select\{[^}]*var\(--colors-brand-badge-parchment\)/,
    );
  });

  it('resting caps complement instead of repeating (live captions untouched)', () => {
    const strip = html.slice(
      html.indexOf('id="ffRestTrack"'),
      html.indexOf('id="ffLightbox"'),
    );
    expect(strip).not.toMatch(/loc-line/);
    expect(strip).toMatch(/rt-platforms/);
    expect(gen).toMatch(/KODIAK_locCaption/);
  });
});
