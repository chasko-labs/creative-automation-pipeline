import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const sections = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/js/campaign-sections.js'),
  'utf8',
);
const css = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/design/components.css'),
  'utf8',
);
const index = readFileSync(
  resolve(root, 'web/kodiak-posts-for-todays-frontier/index.html'),
  'utf8',
);

// Numbered flow 5/6/7: Generate Campaign is a collapsed native <details> with
// the same card + summary styling as Output Preview (.preview-card), greyed
// while gated, full width like the preview. Assets carry 7; About is unnumbered.
describe('numbered collapse flow 5/6/7', () => {
  it('mounts generate as a collapsed details on the shared output card', () => {
    expect(sections).toMatch(/<details id="generateCampaignSection" class="ff-output ff-generate-campaign preview-card is-gated"/);
    expect(sections).toMatch(/<span class="ff-stepnum" aria-hidden="true">6<\/span>/);
  });

  it('refuses gated toggles: stays collapsed, explains, pulses the lock', () => {
    expect(sections).toMatch(/data-gated="true"/);
    expect(sections).toMatch(/id="genFullCampaign" hidden/);
    expect(sections).toMatch(/generate campaign to preview and approve, then try again/);
    expect(sections).toMatch(/addEventListener\('toggle'/);
    expect(sections).toMatch(/sec\.open = false/);
  });

  it('ungate opens the disclosure and reveals the button', () => {
    expect(sections).toMatch(/sec\.open = true/);
    expect(sections).toMatch(/btn\.hidden = false/);
  });

  it('numbers preview 5 and assets 7', () => {
    expect(index).toMatch(/<span class="ff-stepnum" aria-hidden="true">5<\/span>/);
    expect(sections).toMatch(/<span class="ff-stepnum" aria-hidden="true">7<\/span>/);
  });

  it('shares step-chip + gated-grey styling, generate at preview width', () => {
    expect(css).toMatch(/\.ff-stepnum\{[^}]*border-radius:999px/);
    expect(css).toMatch(/\.ff-generate-campaign\.is-gated>summary\{[^}]*cursor:not-allowed/);
    expect(css).not.toMatch(/\.ff-output\.ff-generate-campaign,\.ff-output\.ff-campaign-assets\{[^}]*max-width:960px/);
    expect(css).toMatch(/\.ff-output\.ff-campaign-assets\{[^}]*max-width:960px/);
  });
});
