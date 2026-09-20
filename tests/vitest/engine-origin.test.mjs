import { describe, expect, it, beforeAll } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..', '..');
const APP = resolve(root, 'web/kodiak-posts-for-todays-frontier');

function makeEl() {
  return {
    innerHTML: '', textContent: '', value: '', hidden: false, style: {},
    dataset: {}, children: [],
    classList: { add() {}, remove() {}, contains() { return false; } },
    setAttribute() {}, removeAttribute() {}, appendChild() {},
    addEventListener() {}, querySelector() { return null; },
    querySelectorAll() { return []; }, remove() {}, scrollIntoView() {},
  };
}

beforeAll(() => {
  globalThis.document = {
    readyState: 'complete',
    getElementById: () => null,
    createElement: () => makeEl(),
    addEventListener: () => {},
    querySelector: () => null,
    querySelectorAll: () => [],
    head: makeEl(), body: makeEl(),
  };
  globalThis.window = globalThis;
  globalThis.location = { protocol: 'https:', hostname: 'x.example' };
  globalThis.fetch = async () => ({ ok: false });
  globalThis.Image = function () {};
  eval(readFileSync(resolve(APP, 'js/generate.js'), 'utf8'));
});

// Engine-key contract + origin field (owner orin): frontend keys mirror the
// backend ladder — packshot-composite (A), stability-restyle (B),
// pillow-compose (C), brand-floor (D) — plus the legacy alias, and every
// envelope carries origin. The rung badge surfaces rung + engine + origin.
describe('engine-key contract and origin', () => {
  it('ENGINE_LABELS covers all four canonical backend keys', () => {
    const src = readFileSync(resolve(APP, 'js/generate.js'), 'utf8');
    for (const key of ['packshot-composite', 'stability-restyle', 'pillow-compose', 'brand-floor']) {
      expect(src).toMatch(new RegExp(`'${key}':`));
    }
    // legacy alias kept for older cached responses
    expect(src).toMatch(/'stability-control-structure':/);
  });

  it('single-arg heuristics stay four lines with human engine labels', () => {
    expect(window.KODIAK_provenanceHeuristics({
      rung: 'A', engine: 'packshot-composite',
      seed_selection: 'packshot', seed_source: 'catalog', fallthrough_reason: '',
    })).toEqual([
      'Rung: Rung A · packshot verbatim',
      'Engine: Packshot composite (DAM verbatim)',
      'Seed: packshot via catalog',
      'Fallback: none reported',
    ]);
    expect(window.KODIAK_provenanceHeuristics({
      rung: 'B', engine: 'stability-restyle',
      seed_selection: 'theme-photo', seed_source: 'elk-rut', fallthrough_reason: '',
    })[1]).toBe('Engine: Stability restyle (GenAI)');
    expect(window.KODIAK_provenanceHeuristics({
      rung: 'D', engine: 'brand-floor', fallthrough_reason: 'no-seed',
    })[1]).toBe('Engine: Brand floor (offline fallback)');
  });

  it('two-arg heuristics narrate origin without guessing gaps', () => {
    const lines = window.KODIAK_provenanceHeuristics(
      { rung: 'B', engine: 'stability-restyle', origin: 'backend', fallthrough_reason: '' }, {});
    expect(lines).toContain('Origin: backend (API render)');
    const absent = window.KODIAK_provenanceHeuristics({ rung: 'C' }, {});
    expect(absent).toContain('Origin: not reported');
  });

  it('rung badge surfaces rung, engine, and origin', () => {
    const rb = window.KODIAK_rungBadge(
      'bedrock:stability-control-structure',
      { rung: 'B', engine: 'stability-restyle', origin: 'backend', fallthrough_reason: '' });
    expect(rb.fallback).toBe(false);
    expect(rb.text).toMatch(/rung B/i);
    expect(rb.text).toMatch(/Stability restyle/);
    expect(rb.text).toMatch(/backend/);
    const fb = window.KODIAK_rungBadge(
      'brand-floor', { rung: 'D', engine: 'brand-floor', origin: 'backend', fallthrough_reason: 'no-seed' });
    expect(fb.fallback).toBe(true);
    expect(fb.text).toMatch(/rung D/i);
    expect(fb.text).toMatch(/Brand floor/);
    expect(fb.text).toMatch(/no-seed/);
  });
});
