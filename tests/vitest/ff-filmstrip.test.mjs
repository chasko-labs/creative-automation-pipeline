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
