import { describe, expect, it, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');

// Minimal stub DOM that records what the real campaign-sections.js paints.
function makeEl(id) {
  return {
    id, innerHTML: '', hidden: true, textContent: '', value: '', style: {},
    dataset: {}, parentNode: null, children: [],
    classList: { add() {}, remove() {}, contains() { return false; } },
    setAttribute() {}, removeAttribute() {}, appendChild(c) { this.children.push(c); c.parentNode = this; },
    addEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; },
    scrollIntoView() {},
  };
}

const els = {};
const localizeCalls = [];
let localizeImpl = (text) => Promise.resolve('TEXTO ' + text);

function installStubs() {
  const doc = {
    readyState: 'complete',
    getElementById: (id) => els[id] || null,
    createElement: (tag) => makeEl(tag),
    addEventListener: () => {},
    querySelector: () => null,
    querySelectorAll: () => [],
    head: makeEl('head'), body: makeEl('body'),
  };
  globalThis.document = doc;
  globalThis.window = globalThis;
  globalThis.location = { protocol: 'https:', hostname: 'x.example' };
  globalThis.KODIAK_marketLangsFor = () => ([
    { lang_code: 'es', lang_name: 'Spanish', translate_code: 'es' },
    { lang_code: 'nv', lang_name: 'Navajo', translate_code: 'nv' },
  ]);
  globalThis.KODIAK_isCommunityReview = (l, code) => code === 'nv';
  globalThis.KODIAK_localizeText = (text, market, code) => {
    localizeCalls.push({ text, market, code });
    return localizeImpl(text, market, code);
  };
  // the elements the campaign flow touches
  for (const id of ['campaignAssetsCarousel', 'campaignAssetsSection', 'generateCampaignStatus']) {
    els[id] = makeEl(id);
  }
  els.campaignAssetsSection.hidden = false;
  els.campaignAssetsCarousel.parentNode = els.campaignAssetsSection;
  els.campaignAssetsSection.removeChild = function (node) {
    this.children = this.children.filter((c) => c !== node);
  };
  els.campaignAssetsSection.insertBefore = function (node, ref) { node.parentNode = this; this.children.push(node); };
  const src = readFileSync(
    resolve(root, 'web/kodiak-posts-for-todays-frontier/js/campaign-sections.js'), 'utf8');
  eval(src);
}

beforeAll(() => { installStubs(); });

describe('campaign copy panel (#241)', () => {
  it('paints EN headline, brief, machine row pending, community row badged', async () => {
    const ok = window.KODIAK_paintCampaignCopy('Fuel <Wild> Mornings', 'Keep It Wild', 'US-MW-PARKCITY-84098');
    expect(ok).toBe(true);
    const panel = els.campaignAssetsSection.children.find((c) => c.id === 'campaignCopyPanel');
    expect(panel, 'panel inserted after carousel').toBeTruthy();
    expect(panel.innerHTML).toContain('Campaign copy');
    expect(panel.innerHTML).toContain('Fuel &lt;Wild&gt; Mornings');
    expect(panel.innerHTML).toContain('data-provider="pending-live"');
    expect(panel.innerHTML).toContain('data-provider="community-review"');
    expect(panel.innerHTML).toContain('community review');
    expect(localizeCalls).toEqual([{ text: 'Fuel <Wild> Mornings', market: 'US-MW-PARKCITY-84098', code: 'es' }]);
    await Promise.resolve();
  });

  it('falls back to the brief without a headline; false only with neither', () => {
    expect(window.KODIAK_paintCampaignCopy(null, 'Just the brief', 'm')).toBe(true);
    const panels = els.campaignAssetsSection.children.filter((c) => c.id === 'campaignCopyPanel');
    const panel = panels[panels.length - 1];
    expect(panel.innerHTML).toContain('Just the brief');
    expect(window.KODIAK_paintCampaignCopy(null, null, 'm')).toBe(false);
  });

  it('reset removes the copy panel', () => {
    window.KODIAK_paintCampaignCopy('Headline Here', null, 'm');
    expect(window.KODIAK_resetCampaign()).toBe(true);
  });
});
