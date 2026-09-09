/* Guided arrow tour — hand-drawn cardboard cut-out arrow (inline SVG, kraft
   fill, rough/torn edge, sharpie stroke + short sharpie label). Stops in order:
   Create button -> steps 1-5 -> preview. Vanilla, no dependencies; binds by id,
   touches nothing else. Dismissal persists in localStorage; a dismissed tour
   removes its node so it can never block input. Under prefers-reduced-motion
   the arrow is fully static (no float, no shimmer, instant scroll). */
(function(){
  'use strict';
  var KEY = 'kodiak_tour';
  function isDismissed(){ try{ return localStorage.getItem(KEY) === 'dismissed'; }catch(e){ return false; } }
  function setDismissed(){ try{ localStorage.setItem(KEY, 'dismissed'); }catch(e){} }
  if(isDismissed()) return;

  var reduced = false;
  try{ reduced = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }catch(e){}

  // Tour order = job order: Create first, then steps 1-5, then the preview.
  var STOPS = [
    { sel: '#generateCampaign',                       label: 'start here',      hint: 'Create your preview' },
    { sel: '#scopeWrap > summary.ff-scope-summary',   label: 'step 1 · reach',  hint: 'How far this reaches' },
    { sel: '#locationSection > summary',               label: 'step 2 · market', hint: 'Pick the market' },
    { sel: '.ff-season-details[data-step="3"] > summary', label: 'step 3 · season', hint: 'Seasonal context' },
    { sel: '#creativeDirection > summary',            label: 'step 4 · direction', hint: 'Creative direction' },
    { sel: '.ff-inputwrap[data-step="5"] label.ff-brief-label', label: 'step 5 · brief', hint: 'Your campaign idea' },
    { sel: '#outputHeading',                           label: 'preview',         hint: 'Your four sizes' }
  ];
  var idx = 0;
  var el = null, labelEl = null, stepEl = null, backBtn = null, nextBtn = null;

  // Jittered down-arrow polygon: shaft + head with slightly uneven vertices so
  // the cut edge reads hand-torn, not machined. Kraft fill + sharpie stroke
  // come from the .ff-tour-arrow-shape CSS class (token var() only).
  var ARROW_D = 'M74,30 L86,31 L85,58 L87,90 L97,89 L80,118 L63,92 L75,91 Z';

  function target(sel){
    try{ return document.querySelector(sel); }catch(e){ return null; }
  }

  function build(){
    el = document.createElement('div');
    el.className = 'ff-tour' + (reduced ? ' is-still' : '');
    el.id = 'ffTour';
    el.setAttribute('role', 'dialog');
    el.setAttribute('aria-label', 'Guided tour of the campaign setup');
    el.innerHTML =
      '<div class="ff-tour-svgwrap" aria-hidden="true">' +
      '<svg class="ff-tour-svg" viewBox="0 0 160 132" focusable="false">' +
      '<path class="ff-tour-arrow-shape" d="' + ARROW_D + '"/>' +
      '<text class="ff-tour-label" id="ffTourLabel" x="80" y="20" text-anchor="middle">start here</text>' +
      '</svg>' +
      '<div class="ff-tour-sheen"></div>' +
      '</div>' +
      '<div class="ff-tour-bar">' +
      '<span class="ff-tour-step" id="ffTourStep"></span>' +
      '<button type="button" class="ff-tour-btn ff-tour-btn--quiet" id="ffTourBack">Back</button>' +
      '<button type="button" class="ff-tour-btn" id="ffTourNext">Next</button>' +
      '<button type="button" class="ff-tour-btn ff-tour-btn--quiet" id="ffTourDismiss">Dismiss</button>' +
      '</div>';
    document.body.appendChild(el);
    labelEl = document.getElementById('ffTourLabel');
    stepEl = document.getElementById('ffTourStep');
    backBtn = document.getElementById('ffTourBack');
    nextBtn = document.getElementById('ffTourNext');
    document.getElementById('ffTourDismiss').addEventListener('click', teardown);
    backBtn.addEventListener('click', function(){ go(idx - 1); });
    nextBtn.addEventListener('click', function(){
      if(idx >= STOPS.length - 1){ teardown(); return; }
      go(idx + 1);
    });
    document.addEventListener('keydown', function onKey(e){
      if(e && e.key === 'Escape'){ teardown(); }
    });
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, { passive: true });
    // Late layout shifts (webfonts, header images) move the anchor after first
    // paint — re-center + re-track once they settle so neither the viewport
    // nor the arrow strands on stale pre-shift geometry. Instant (no glide).
    function recenter(){
      var t = target(STOPS[idx].sel);
      if(t){ try{ t.scrollIntoView({ block: 'center', behavior: 'auto' }); }catch(e){} }
      place();
    }
    try{
      if(document.fonts && document.fonts.ready) document.fonts.ready.then(recenter);
      window.addEventListener('load', recenter);
    }catch(e){}
  }

  // First paint places instantly (no scroll animation on load, so the resting
  // viewport is deterministic); user-driven Back/Next glides, except under
  // reduced motion where every move is instant.
  function go(i, instant){
    if(i < 0 || i >= STOPS.length) return;
    idx = i;
    var stop = STOPS[idx];
    var t = target(stop.sel);
    if(!t) return;
    // Open the stop's own disclosure so the arrow points at visible content.
    var host = (t.tagName && t.tagName.toLowerCase() === 'summary') ? t.parentNode : t;
    if(host && host.tagName && host.tagName.toLowerCase() === 'details' && !host.open){
      try{ host.open = true; }catch(e){}
    }
    try{ t.scrollIntoView({ block: 'center', behavior: (reduced || instant) ? 'auto' : 'smooth' }); }catch(e){
      try{ t.scrollIntoView(); }catch(e2){}
    }
    if(labelEl) labelEl.textContent = stop.label;
    if(stepEl) stepEl.textContent = (idx + 1) + ' / ' + STOPS.length + ' · ' + stop.hint;
    if(backBtn) backBtn.style.display = idx === 0 ? 'none' : '';
    if(nextBtn) nextBtn.textContent = idx >= STOPS.length - 1 ? 'Done' : 'Next';
    // Layout settles after scroll/open; place on the next frame.
    try{ requestAnimationFrame(place); }catch(e){ place(); }
  }

  function place(){
    if(!el) return;
    var t = target(STOPS[idx].sel);
    if(!t) return;
    var r = t.getBoundingClientRect();
    var w = 170;
    var h = 185;
    var left = Math.round(r.left + r.width / 2 - w / 2);
    left = Math.max(8, Math.min(window.innerWidth - w - 8, left));
    var top = Math.round(r.top - h);
    if(top < 8) top = 8;
    el.style.left = left + 'px';
    el.style.top = top + 'px';
  }

  function teardown(){
    setDismissed();
    window.removeEventListener('resize', place);
    window.removeEventListener('scroll', place);
    if(el && el.parentNode) el.parentNode.removeChild(el);
    el = null;
  }
  window.__ffTourTeardown = teardown;

  function start(){
    if(isDismissed()) return;
    build();
    // Defer one frame so first paint + fonts settle before measuring.
    try{ requestAnimationFrame(function(){ go(0, true); }); }catch(e){ go(0, true); }
  }
  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', start);
  }else{
    start();
  }
})();
