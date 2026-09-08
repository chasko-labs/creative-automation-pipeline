import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'), 'utf8');
const ac = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/autocomplete.js'), 'utf8');
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'), 'utf8');

// briefSuggest is an inline pill strip INSIDE the prompt — never a floating
// overlay duplicating the market/season context line. Listbox semantics and
// the keyboard model are untouched.
describe('inline suggest pills', () => {
  it('suggest box is in-flow, not absolutely positioned', () => {
    expect(css).toMatch(/\.ff-briefsuggest\{[^}]*position:static/);
    expect(css).not.toMatch(/\.ff-briefsuggest\{[^}]*position:absolute/);
    expect(css).toMatch(/\.ff-briefsuggest\[hidden\]\{display:none\}/);
  });

  it('options render as pills reusing the tag styles', () => {
    expect(css).toMatch(/\.ff-briefsuggest \.ff-suggest-opt\{[^}]*border-radius:999px/);
    expect(css).toMatch(/\.ff-briefsuggest \.ff-suggest-tag\{/);
  });

  it('selection model is unchanged', () => {
    expect(index).toMatch(/id="briefSuggest"[^>]*role="listbox"/);
    expect(ac).toMatch(/aria-activedescendant/);
    expect(ac).toMatch(/briefSuggestOpt'/);
  });
});
