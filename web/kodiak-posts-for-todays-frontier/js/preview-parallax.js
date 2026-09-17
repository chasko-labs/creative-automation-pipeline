// Resting preview parallax — pointer + scroll depth for the #previewHero
// example tiles ONLY (#previewHero .render-set .render-tile .render-frame img).
// Never touches generated campaign output, recipe cards, or other pages:
// generated renders replace #preview.innerHTML (see js/generate.js
// showRenderSet), which removes #previewHero — the MutationObserver below
// then tears this module down. Static tiles when JS is off (CSS is gated on
// html.pp-ready, added here) or when prefers-reduced-motion is set.
(function () {
  'use strict';

  var HERO_ID = 'previewHero';
  var TILE_SEL = '#' + HERO_ID + ' .render-set .render-tile';
  var POINTER_MAX = 6; // px at full deflection for the deepest tile
  var SCROLL_MAX = 8; // px of scroll drift for the deepest tile
  var SETTLE_MS = 380;

  /** @returns {boolean} */
  function reducedMotion() {
    try {
      return window.matchMedia &&
        window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    } catch (e) { return false; }
  }

  // Query once, narrow once: the const binding below carries the non-null
  // type into the event closures (a var binding would forget it there).
  const heroQuery = document.getElementById(HERO_ID);
  // Static fallback: no hero, no animation support, or motion-sensitive reader.
  if (!heroQuery || reducedMotion()) return;
  const hero = heroQuery;
  if (!('requestAnimationFrame' in window)) return;

  var tiles = Array.prototype.slice.call(document.querySelectorAll(TILE_SEL));
  if (!tiles.length) return;

  // Per-tile depth: slightly different rates so the set reads as layered.
  // Rates cycle 0.4 / 0.6 / 0.8 / 1.0 across the tiles in DOM order. Frames
  // are cast once here so every later use knows they are set, not queried.
  /** @type {{node: Element, frame: HTMLElement, rate: number}[]} */
  var rates = [];
  tiles.forEach(function (tile, i) {
    var frame = /** @type {HTMLElement|null} */ (tile.querySelector('.render-frame'));
    if (frame) rates.push({ node: tile, frame: frame, rate: 0.4 + 0.2 * (i % 4) });
  });
  if (!rates.length) return;

  var rafId = 0;
  var target = { x: 0, y: 0 }; // -1..1 pointer offset from hero center
  var scrollY = 0; // -1..1 hero progress through the viewport
  var active = true;
  var settleTimer = 0;

  /**
   * @param {(r: {node: Element, frame: HTMLElement, rate: number}) => void} fn
   */
  function eachFrame(fn) {
    rates.forEach(fn);
  }

  function paint() {
    rafId = 0;
    if (!active) return;
    eachFrame(function (r) {
      var tx = (target.x * POINTER_MAX * r.rate).toFixed(2) + 'px';
      var ty = (target.y * POINTER_MAX * r.rate).toFixed(2) + 'px';
      var sy = (scrollY * SCROLL_MAX * r.rate).toFixed(2) + 'px';
      r.frame.style.setProperty('--pp-tx', tx);
      r.frame.style.setProperty('--pp-ty', ty);
      r.frame.style.setProperty('--pp-sy', sy);
    });
  }

  function schedule() {
    if (!rafId) rafId = window.requestAnimationFrame(paint);
  }

  /** @param {PointerEvent} ev */
  function onPointerMove(ev) {
    if (!active) return;
    var box = hero.getBoundingClientRect();
    if (!box.width || !box.height) return;
    window.clearTimeout(settleTimer);
    hero.classList.remove('pp-settling');
    target.x = ((ev.clientX - box.left) / box.width - 0.5) * 2;
    target.y = ((ev.clientY - box.top) / box.height - 0.5) * 2;
    // Sheen follows the pointer per frame, in that frame's own coordinates.
    eachFrame(function (r) {
      var fbox = r.frame.getBoundingClientRect();
      if (!fbox.width || !fbox.height) return;
      var sx = ((ev.clientX - fbox.left) / fbox.width) * 100;
      var sy = ((ev.clientY - fbox.top) / fbox.height) * 100;
      r.frame.style.setProperty('--pp-sx', sx.toFixed(1) + '%');
      r.frame.style.setProperty('--pp-sy-pct', sy.toFixed(1) + '%');
      r.frame.style.setProperty('--pp-sheen', '1');
    });
    schedule();
  }

  // Ease back to rest: clear the offsets under a short CSS transition.
  function onPointerLeave() {
    if (!active) return;
    target.x = 0;
    target.y = 0;
    hero.classList.add('pp-settling');
    eachFrame(function (r) {
      r.frame.style.setProperty('--pp-tx', '0px');
      r.frame.style.setProperty('--pp-ty', '0px');
      r.frame.style.setProperty('--pp-sheen', '0');
    });
    window.clearTimeout(settleTimer);
    settleTimer = window.setTimeout(function () {
      hero.classList.remove('pp-settling');
    }, SETTLE_MS);
  }

  function onScroll() {
    if (!active) return;
    var box = hero.getBoundingClientRect();
    var vh = window.innerHeight || document.documentElement.clientHeight || 1;
    // 0 when the hero center sits at viewport center, +/-1 at the edges.
    var center = box.top + box.height / 2;
    scrollY = (center - vh / 2) / (vh / 2);
    if (scrollY > 1) scrollY = 1;
    if (scrollY < -1) scrollY = -1;
    schedule();
  }

  function teardown() {
    active = false;
    if (rafId) window.cancelAnimationFrame(rafId);
    rafId = 0;
    window.clearTimeout(settleTimer);
    try {
      hero.removeEventListener('pointermove', onPointerMove);
      hero.removeEventListener('pointerleave', onPointerLeave);
      // no options object: it was registered without capture, so bare removal
      // matches (the old {passive:true} never narrowed the match anyway).
      window.removeEventListener('scroll', onScroll);
    } catch (e) { /* listener removal is best-effort */ }
    if (observer) { try { observer.disconnect(); } catch (e) { /* never attached */ } }
    try {
      document.documentElement.classList.remove('pp-ready');
      hero.classList.remove('pp-settling');
    } catch (e) { /* DOM already gone */ }
  }

  // Generated campaign output replaces #preview.innerHTML, removing #previewHero.
  // Watch for that and unload the effect layers for generated content.
  /** @type {MutationObserver|null} */
  var observer = null;
  try {
    var preview = document.getElementById('preview');
    if (preview && 'MutationObserver' in window) {
      observer = new MutationObserver(function () {
        if (!document.getElementById(HERO_ID)) teardown();
      });
      observer.observe(preview, { childList: true, subtree: false });
    }
  } catch (e) { observer = null; }

  hero.addEventListener('pointermove', onPointerMove);
  hero.addEventListener('pointerleave', onPointerLeave);
  window.addEventListener('scroll', onScroll, { passive: true });
  document.documentElement.classList.add('pp-ready');
  onScroll();
}());
