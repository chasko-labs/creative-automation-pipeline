// --- Page Lifecycle API: snapshot/restore inputs across Chrome Memory Saver tab discard (freeze/pagehide) ---
// Self-contained. Persists a SMALL text snapshot of the campaign inputs and rehydrates on
// load within a capped lifetime. Does NOT store DOM, blobs, object URLs, or catalogs.
// blob: object URLs for staged uploads do NOT survive a tab discard, so only the upload NAMES are kept
// as a re-derivation note — the user is told to re-add them; no fake assets are fabricated.
//
// 2026-09-08 El Paso fallback fix: persist() fires ONLY after an explicit user change (dirty
// flag); a restore never marks dirty, so an untouched restore can never re-persist itself.
// Snapshots carry an absolute born timestamp — restore is valid 24h from FIRST persist, never
// sliding. And restore never silently overrides the Park City default: a provenance note names
// the active market and its source ("Park City default" vs "saved from last visit") with a
// one-click reset.
(function(){
  var KEY = 'kodiak_ff_state_v1';
  var MAX_AGE_MS = 24 * 60 * 60 * 1000;
  var DEFAULT_MARKET = 'US-MW-PARKCITY-84098';   // mirrors fillSelects hard default
  var dirty = false;      // set only by real user gestures below — never by restore()
  var restoring = false;  // guard: programmatic writes during restore must not set dirty

  function checkedSkus(){
    try{
      return Array.prototype.slice.call(document.querySelectorAll('.sku-check'))
        .filter(function(b){ return b.checked; })
        .map(function(b){ return b.value; });
    }catch(e){ return []; }
  }

  function readSnapshot(){
    var snap = {};
    try{ snap.brief    = document.getElementById('campaignBrief')?.value; }catch(e){}
    try{ snap.locality = document.getElementById('locality')?.value; }catch(e){}
    try{ snap.season   = document.getElementById('seasonalSelect')?.value; }catch(e){}
    try{ snap.skus     = checkedSkus(); }catch(e){}
    try{ snap.userAssetNames = (window.__userAssets || []).map(function(a){ return a && a.name; }).filter(Boolean); }catch(e){}
    return snap;
  }

  function sameSnap(a, b){
    try{ return JSON.stringify(a) === JSON.stringify(b); }catch(e){ return false; }
  }

  function readStored(){
    try{
      var raw = localStorage.getItem(KEY);
      if(!raw) return null;
      var s = JSON.parse(raw);
      if(!s || typeof s.ts !== 'number') return null;
      return s;
    }catch(e){ return null; }
  }

  function persist(){
    // explicit-change only: an untouched restore must never re-persist itself.
    if(!dirty) return;
    try{
      var prev = readStored() || {};
      var snap = readSnapshot();
      // identical state (modulo timestamps) -> skip the write so ts/born never refresh.
      var prevBare = {brief:prev.brief, locality:prev.locality, season:prev.season, skus:prev.skus, userAssetNames:prev.userAssetNames};
      if(sameSnap(prevBare, snap)) return;
      snap.ts = Date.now();
      snap.born = (typeof prev.born === 'number') ? prev.born : snap.ts;  // absolute lifetime: first persist wins
      localStorage.setItem(KEY, JSON.stringify(snap));
    }catch(e){}
  }

  // clear hook — called by the generate success path so a completed campaign does not resurrect on next visit
  window.__kodiakClearFFState = function(){ try{ localStorage.removeItem(KEY); }catch(e){} };

  // explicit user gestures that make the snapshot worth keeping. Restore-time programmatic
  // events are suppressed via the restoring guard.
  function markDirty(){ if(!restoring){ dirty = true; } }
  try{
    document.addEventListener('change', function(e){
      var t = e.target;
      if(!t) return;
      if(t.id === 'locality' || t.id === 'seasonalSelect' || t.id === 'addAssetInput') markDirty();
      else if(t.classList && t.classList.contains('sku-check')) markDirty();
    }, true);
    document.addEventListener('input', function(e){
      if(e.target && e.target.id === 'campaignBrief') markDirty();
    }, true);
  }catch(e){}

  function showAssetReAddNote(names){
    try{
      if(document.getElementById('ffAssetReaddNote')) return;   // idempotent
      var input = document.getElementById('addAssetInput');
      var note = document.createElement('div');
      note.id = 'ffAssetReaddNote';
      note.setAttribute('role', 'status');
      note.style.cssText = 'margin:6px 0 0;font:500 12px/1.4 system-ui,-apple-system,sans-serif;color:#B51E14';
      note.textContent = 'Your previously staged upload' + (names.length > 1 ? 's' : '') + ' (' + names.join(', ') + ') need to be re-added — the browser discarded the tab.';
      var dismiss = document.createElement('button');
      dismiss.type = 'button';
      dismiss.setAttribute('aria-label', 'Dismiss staged-upload notice');
      dismiss.textContent = '\u00d7';
      dismiss.style.cssText = 'margin-left:8px;border:none;background:transparent;color:#B51E14;cursor:pointer;font-size:14px;line-height:1';
      dismiss.addEventListener('click', function(){ if(note.parentNode) note.parentNode.removeChild(note); });
      note.appendChild(dismiss);
      // append after the file input if present, else after the prompt input wrap, else body
      var anchor = input || document.querySelector('.ff-inputwrap') || document.body;
      if(anchor && anchor.parentNode) anchor.parentNode.insertBefore(note, anchor.nextSibling);
      else document.body.appendChild(note);
    }catch(e){}
  }

  // provenance note: which market is active and where it came from, with a one-click reset
  // to the Park City default. Rendered after every restore attempt (idempotent).
  function renderMarketSource(restoredMarket){
    try{
      var host = document.getElementById('marketDisclosure');
      if(!host) return;
      var el = document.getElementById('ffMarketSource');
      if(!el){
        el = document.createElement('div');
        el.id = 'ffMarketSource';
        el.setAttribute('role', 'status');
        el.style.cssText = 'font:500 11px/1.5 system-ui,-apple-system,sans-serif;color:#6B5A53;margin-top:4px';
        host.parentNode.insertBefore(el, host.nextSibling);
      }
      var locEl = document.getElementById('locality');
      var cur = (locEl && locEl.value) || restoredMarket || DEFAULT_MARKET;
      var label = document.getElementById('marketButtonLabel');
      var place = (label && label.textContent.trim()) || cur;
      if(restoredMarket && cur === restoredMarket && cur !== DEFAULT_MARKET){
        el.innerHTML = '';
        el.appendChild(document.createTextNode('Market: ' + place + ' — saved from last visit '));
        var reset = document.createElement('button');
        reset.type = 'button';
        reset.textContent = 'Reset to Park City default';
        reset.style.cssText = 'border:1px solid #8C7A70;background:transparent;color:#3B2316;border-radius:4px;padding:1px 8px;cursor:pointer;font-size:11px';
        reset.addEventListener('click', function(){
          try{
            var l = document.getElementById('locality');
            if(l){ l.value = DEFAULT_MARKET; l.dispatchEvent(new Event('change', {bubbles:true})); }
            window.__kodiakClearFFState();
            dirty = true; persist(); dirty = false;  // persist the default once so the loop dies here
            renderMarketSource(null);
          }catch(e){}
        });
        el.appendChild(reset);
      } else {
        el.textContent = 'Market: ' + place + ' — Park City default';
      }
    }catch(e){}
  }

  function restore(){
    var snap = readStored();
    // absolute lifetime from FIRST persist — a sliding ts can never perpetuate the restore.
    if(!snap || (Date.now() - (typeof snap.born === 'number' ? snap.born : snap.ts)) > MAX_AGE_MS) return null;
    restoring = true;
    try{
      // brief — dispatch input so the autocomplete + auto-grow handlers re-run
      try{
        var briefEl = document.getElementById('campaignBrief');
        if(briefEl && snap.brief && !briefEl.value){ briefEl.value = snap.brief; briefEl.dispatchEvent(new Event('input', {bubbles:true})); }
      }catch(e){}

      // locality — only if the saved option exists; dispatch change so onLocality re-runs.
      // NOTE: this deliberately does NOT mark dirty — an untouched restore must not re-persist.
      try{
        var locEl = document.getElementById('locality');
        if(locEl && snap.locality){
          var hasOpt = Array.prototype.slice.call(locEl.options || []).some(function(o){ return o.value === snap.locality; });
          if(hasOpt && locEl.value !== snap.locality){ locEl.value = snap.locality; locEl.dispatchEvent(new Event('change', {bubbles:true})); }
        }
      }catch(e){}

      // season — restore against #seasonalSelect; dispatch change so dependents re-run.
      try{
        var seasonEl = document.getElementById('seasonalSelect');
        if(seasonEl && snap.season && seasonEl.value !== snap.season){
          var hasSeasonOpt = Array.prototype.slice.call(seasonEl.options || []).some(function(o){ return o.value === snap.season; });
          if(hasSeasonOpt){ seasonEl.value = snap.season; seasonEl.dispatchEvent(new Event('change', {bubbles:true})); }
        }
      }catch(e){}

      // SKUs — re-check matching .sku-check boxes; dispatch change so tray chips reappear.
      try{
        var want = {};
        (snap.skus || []).forEach(function(v){ want[v] = true; });
        Array.prototype.slice.call(document.querySelectorAll('.sku-check')).forEach(function(b){
          if(want[b.value] && !b.checked){ b.checked = true; b.dispatchEvent(new Event('change', {bubbles:true})); }
        });
      }catch(e){}

      // staged uploads — blob URLs are gone after a discard; show a non-blocking re-add note (no fake assets)
      try{
        if(Array.isArray(snap.userAssetNames) && snap.userAssetNames.length){ showAssetReAddNote(snap.userAssetNames); }
      }catch(e){}
    }finally{
      restoring = false;
    }
    return snap.locality || null;
  }

  // persist triggers — hidden visibilitychange + pagehide + freeze (all the discard-adjacent lifecycle events).
  // persist() itself enforces explicit-change-only, so untouched restores never write.
  try{ document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'hidden') persist(); }); }catch(e){}
  try{ window.addEventListener('pagehide', persist); }catch(e){}
  try{ document.addEventListener('freeze', persist); }catch(e){}

  // rehydrate after the selects + SKU checkboxes are populated. fillSelects runs synchronously on load and
  // the SKU catalog paints asynchronously (~900ms), so restore on a short delay and retry once for the SKUs.
  function runRestore(){ try{ var m = restore(); renderMarketSource(m); }catch(e){} }
  if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', function(){ setTimeout(runRestore, 700); }); }
  else { setTimeout(runRestore, 700); }
  setTimeout(function(){ try{ var m2 = restore(); renderMarketSource(m2); }catch(e){} }, 1500);   // second pass — SKU checkboxes may finish painting after the first pass
})();
