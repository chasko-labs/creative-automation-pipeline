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
});
