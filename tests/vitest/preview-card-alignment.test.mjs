import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'),
  'utf8',
);

// The preview card is a fixed-width keepsake in a full-width column. When it
// hugs the left edge under the full-width campaign-copy panel, the preview
// region reads misaligned — center it. Scoped to #previewRecipe (index only)
// so the details.html standard specimen is untouched.
function ruleFor(selector) {
  const m = css.match(new RegExp(`${selector}\\{([^}]*)\\}`));
  return m ? m[1] : null;
}

describe('output preview recipe-card alignment', () => {
  it('centers the card inside the preview slot', () => {
    const body = ruleFor('#previewRecipe');
    expect(body, 'missing #previewRecipe rule in components.css').not.toBeNull();
    expect(body).toMatch(/justify-content\s*:\s*center/);
  });

  it('scopes the override to the preview slot, not the card standard', () => {
    expect(css).not.toMatch(/\.rc-card\s*\{[^}]*justify-content/);
  });
});
