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

// #239: the Generate Campaign section must read as the primary next step —
// same output card surface as the preview, full-width primary action.
describe('campaign section prominence (#239)', () => {
  it('mounts the generate section on the shared output card', () => {
    expect(sections).toMatch(/id="generateCampaignSection" class="ff-output ff-generate-campaign/);
  });

  it('gates the generate section on load: visible, button hidden, click explains the unlock', () => {
    expect(sections).toMatch(/data-gated="true"/);
    expect(sections).toMatch(/id="genFullCampaign" hidden/);
    expect(sections).toMatch(/generate campaign to preview and approve, then try again/);
    // ungate path: preview-ready reveals the button
    expect(sections).toMatch(/btn\.hidden = false/);
  });

  it('mounts the assets section on the shared output card', () => {
    expect(sections).toMatch(/id="campaignAssetsSection" class="ff-output ff-campaign-assets"/);
  });

  it('marks the full-campaign action as the primary button', () => {
    expect(sections).toMatch(/class="btn orange ff-campaign-primary" id="genFullCampaign"/);
    expect(css).toMatch(/#generateCampaignBtns \.ff-campaign-primary\{[^}]*width:100%/);
  });

  it('centers campaign cards like the preview', () => {
    expect(css).toMatch(/\.ff-output\.ff-generate-campaign,\.ff-output\.ff-campaign-assets\{[^}]*max-width:960px/);
  });
});
