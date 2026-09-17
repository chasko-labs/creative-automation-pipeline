import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'),
  'utf8',
);

// The preview card is a fixed 8.5x11in canvas that only transform-scales, so
// a static scale caps it at 816px and it sits left in a wider column. The
// slot is a size container and the shell scale divides the slot width by 816,
// so the card paints edge to edge at any column width. Scoped to
// #previewRecipe (index only) so the details.html standard specimen is
// untouched.
function ruleFor(selector) {
  const m = css.match(new RegExp(`${selector}\\{([^}]*)\\}`));
  return m ? m[1] : null;
}

describe('output preview recipe-card alignment', () => {
  it('makes the slot a block size-container so the card can fill it', () => {
    const body = ruleFor('#previewRecipe');
    expect(body, 'missing #previewRecipe rule in components.css').not.toBeNull();
    expect(body).toMatch(/display\s*:\s*block/);
    expect(body).toMatch(/container-type\s*:\s*inline-size/);
  });

  it('scales the shell from the slot width, not a static cap', () => {
    const body = ruleFor('#previewRecipe \\.rc-card-shell');
    expect(body, 'missing #previewRecipe .rc-card-shell rule').not.toBeNull();
    expect(body).toMatch(/calc\(100cqw\s*\/\s*816px\)/);
  });

  it('scopes the override to the preview slot, not the card standard', () => {
    expect(css).not.toMatch(/\.rc-card\s*\{[^}]*justify-content/);
  });
});
