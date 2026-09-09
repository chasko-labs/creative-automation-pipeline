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

// Numbered flow 6/7/8 (season is step 3, the group is step 4): Generate Campaign
// is a collapsed native <details> with the same card + summary styling as Output
// Preview (.preview-card), greyed while gated, full width like the preview.
// Assets carry 8; About is unnumbered.
describe('numbered collapse flow 6/7/8', () => {
  it('mounts generate as a collapsed details on the shared output card', () => {
    expect(sections).toMatch(/<details id="generateCampaignSection" class="ff-output ff-generate-campaign preview-card is-gated"/);
    expect(sections).toMatch(/<span class="ff-stepnum" aria-hidden="true">7<\/span>/);
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

  it('numbers preview 6 and assets 8', () => {
    expect(index).toMatch(/<span class="ff-stepnum" aria-hidden="true">6<\/span>/);
    expect(sections).toMatch(/<span class="ff-stepnum" aria-hidden="true">8<\/span>/);
  });

  it('shares step-chip + gated-grey styling, generate at preview width', () => {
    expect(css).toMatch(/\.ff-stepnum\{[^}]*border-radius:999px/);
    expect(css).toMatch(/\.ff-generate-campaign\.is-gated>summary\{[^}]*cursor:not-allowed/);
    expect(css).not.toMatch(/\.ff-output\.ff-generate-campaign,\.ff-output\.ff-campaign-assets\{[^}]*max-width:960px/);
    expect(css).toMatch(/\.ff-output\.ff-campaign-assets\{[^}]*max-width:960px/);
  });
});

describe('de-reddened decorative UI', () => {
  it('chevrons read pine, never signal red', () => {
    for (const sel of ['\\.preview-card>summary::before', '\\.platform-copy summary::before',
        '\\.provenance>summary::before', '\\.ff-season-details>summary::before',
        '#locationSection>summary::before', '\\.ff-products>summary::before',
        '\\.ff-layers>summary::before', '\\.ff-scope-summary::before']) {
      expect(css).toMatch(new RegExp(sel + '\\{[^}]*color:var\\(--colors-brand-frontier-green\\)'));
    }
    expect(css).not.toMatch(/summary::before\{[^}]*signal-red/);
  });

  it('timeline badges carry four earth states, active is pine', () => {
    expect(css).toMatch(/\.ff-timeline-steps li\[data-state="active"\] \.ff-stepnum\{background:var\(--colors-brand-frontier-green\)/);
    expect(css).toMatch(/\.ff-timeline-steps li\[data-state="done"\] \.ff-stepnum\{background:var\(--colors-brand-bear-brown\)/);
    expect(css).toMatch(/\.ff-timeline-steps \.ff-stepnum\{[^}]*background:transparent/);
    expect(css).not.toMatch(/\.ff-timeline-steps[^}]*signal-red/);
  });

  it('secondary action buttons ride bear-brown, not red', () => {
    expect(css).toMatch(/\.btn\.orange\{background:var\(--colors-brand-bear-brown\);border-color:var\(--colors-brand-bear-brown\)/);
  });

  it('focus rings read pine; red stays on links, alerts, and removal', () => {
    expect(css).toMatch(/a:focus-visible,button:focus-visible,[^}]*outline:2px solid var\(--colors-brand-frontier-green\)/);
    expect(css).toMatch(/a\{color:var\(--red\)/);
    expect(css).toMatch(/\.ff-pending-remove:hover\{background:var\(--colors-brand-signal-red\)/);
  });

  it('asset actions have one solid primary and outline secondaries', () => {
    expect(css).toMatch(/#promptUpload\{background:var\(--colors-brand-bear-brown\);border-color:var\(--colors-brand-bear-brown\)/);
    expect(css).toMatch(/#promptUpload::before\{content:"\+"[^}]*\}/);
    expect(css).toMatch(/\.ff-dam-trigger\{[^}]*border:1px solid var\(--colors-border-strong\)/);
    expect(css).toMatch(/\.ff-products \.ff-products-random\{[^}]*border:1px solid var\(--colors-border-strong\)/);
  });
});

// Layout law — campaign assets ride the main page scroll: no inner scrollbar,
// download actions in normal flow, nothing clipped at 1600px or 390px.
describe('layout law (no inner scroll on assets)', () => {
  it('assets sections refuse inner scroll; carousel shell never scrolls', () => {
    expect(css).toMatch(/\.ff-output\.ff-campaign-assets,\.ff-output\.ff-generate-campaign\{[^}]*overflow:visible[^}]*max-height:none/);
    expect(css).toMatch(/\.ff-campaign-assets \.ff-product-carousel\{[^}]*overflow-x:visible/);
  });

  it('narrow slots share the row instead of scrolling', () => {
    expect(css).toMatch(/\.ff-carousel-slot\{flex:1 1 0;min-width:0/);
  });

  it('platform matrix stacks instead of scrolling sideways', () => {
    expect(css).not.toMatch(/\.platform-matrix\{overflow-x:auto/);
    expect(css).toMatch(/\.platform-matrix\{overflow-x:visible/);
  });

  it('download pack actions stay in normal flow, top and bottom', () => {
    expect(sections).toMatch(/id="downloadCampaignPackTop"/);
    expect(sections).toMatch(/id="downloadCampaignPackBottom"/);
    expect(sections).not.toMatch(/downloadCampaignPackTop[^]*position:(fixed|absolute)/);
  });
});
