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
    // staged DAM picks rehydrate by KEY (small strings, re-fetchable server-side) —
    // presigned urls and blob object urls never survive a discard, so only the key
    // travels. Local file uploads have no key and keep the names-only re-add note.
    try{
      snap.userDamAssets = (window.__userAssets || [])
        .filter(function(a){ return a && a.source === 'dam' && a.key; })
        .map(function(a){ return {name: a.name, key: a.key, category: a.category, kind: a.kind}; });
    }catch(e){}
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
    // Reset keeps this guard set through pagehide while the old document unloads.
    if(restoring || !dirty) return;
    try{
      var prev = readStored() || {};
      var snap = readSnapshot();
      // identical state (modulo timestamps) -> skip the write so ts/born never refresh.
      var prevBare = {brief:prev.brief, locality:prev.locality, season:prev.season, skus:prev.skus, userAssetNames:prev.userAssetNames, userDamAssets:prev.userDamAssets};
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
  // staging lives in prompt-chips.js (another IIFE) — chips and removals must mark
  // dirty or the snapshot never captures them. Guarded read at call time.
  window.__kodiakMarkDirty = function(){ markDirty(); };
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

  // restored-picks note: DAM picks came back by key and work at the next Create.
  function showRestoredNote(names){
    try{
      if(document.getElementById('ffAssetRestoredNote')) return;   // idempotent
      var note = document.createElement('div');
      note.id = 'ffAssetRestoredNote';
      note.setAttribute('role', 'status');
      note.style.cssText = 'margin:6px 0 0;font:500 12px/1.4 system-ui,-apple-system,sans-serif;color:#1A3C34';
      note.textContent = 'Restored ' + names.length + ' staged pick' + (names.length > 1 ? 's' : '') + ' (' + names.join(', ') + ') — ready at Create, no need to re-add.';
      var dismiss = document.createElement('button');
      dismiss.type = 'button';
      dismiss.setAttribute('aria-label', 'Dismiss restored picks notice');
      dismiss.textContent = '\u00d7';
      dismiss.style.cssText = 'margin-left:8px;border:none;background:transparent;color:#1A3C34;cursor:pointer;font-size:14px;line-height:1';
      dismiss.addEventListener('click', function(){ if(note.parentNode) note.parentNode.removeChild(note); });
      note.appendChild(dismiss);
      var anchor = document.querySelector('.ff-inputwrap') || document.body;
      if(anchor && anchor.parentNode) anchor.parentNode.insertBefore(note, anchor.nextSibling);
      else document.body.appendChild(note);
    }catch(e){}
  }

  // Restore Defaults returns the page to its canonical initial-load state. Clear the saved
  // snapshot before reloading; keep restoring set through pagehide so lifecycle persistence
  // cannot write the pre-reset state back during the reset event.
  function resetToDefaults(){
    restoring = true;
    // #250: uncheck the live product boxes and re-sync the tray from them before
    // the reload, so stale chips whose boxes a host re-filter destroyed are voided
    // rather than surviving the clear. The sync hook is idempotent and safe pre-reload.
    try{
      Array.prototype.slice.call(document.querySelectorAll('.sku-check:checked')).forEach(function(b){
        try{ b.checked = false; b.dispatchEvent(new Event('change', {bubbles:true})); }catch(e){}
      });
    }catch(e){}
    try{ if(typeof window.__kodiakSyncSkuChips === 'function') window.__kodiakSyncSkuChips(); }catch(e){}
    try{ window.__kodiakClearFFState(); }catch(e){}
    try{ window.location.reload(); }catch(e){ restoring = false; }
  }
  // Step-0 reset stays greyed until any mutable state differs from the initial load state.
  function currentCalendarMonth(){
    return ['January','February','March','April','May','June','July','August','September','October','November','December'][new Date().getMonth()];
  }
  function generatedOutputIsDirty(){
    try{
      var status = document.getElementById('sampleStatus');
      if(status && status.textContent.trim()) return true;
      var files = document.getElementById('fileNames');
      if(files && files.textContent.trim()) return true;
      // The initial page owns the static hero and platform matrix; generated preview paths replace the hero.
      if(!document.getElementById('previewHero') || !document.getElementById('platformMatrix')) return true;
      if(document.querySelector('#previewDownloadRow, #genSourceBadge, #provenancePanel, #copyFirstPanel, #platformCopyPanel, #campaignCopyPanel')) return true;
      var gate = document.getElementById('generateCampaignSection');
      if(gate && gate.getAttribute('data-gated') === 'false') return true;
      var assets = document.getElementById('campaignAssetsSection');
      if(assets && !assets.hidden) return true;
      var carousel = document.getElementById('campaignAssetsCarousel');
      if(carousel && carousel.children.length) return true;
    }catch(e){ return true; }
    return false;
  }
  function resetIsDirty(){
    try{
      var brief = document.getElementById('campaignBrief');
      if(brief && brief.value.trim()) return true;
      var l = document.getElementById('locality');
      if(l && l.value && l.value !== DEFAULT_MARKET) return true;
      var season = document.getElementById('seasonalSelect');
      if(season && season.value !== currentCalendarMonth()) return true;
      if(typeof window.__activeSeason === 'string' && window.__activeSeason !== currentCalendarMonth()) return true;
      var selectedScope = document.querySelector('#campaignScope .ff-scope-opt[aria-checked="true"]');
      if(typeof window.__campaignScope === 'string' && window.__campaignScope !== 'local') return true;
      if(selectedScope && selectedScope.getAttribute('data-scope') !== 'local') return true;
      if(document.querySelector('#promptChips .ff-check-card__input[data-theme]:checked')) return true;
      if(document.querySelector('.sku-check:checked')) return true;
      if(document.querySelector('.layer-check:checked')) return true;
      if((window.__userAssets || []).length || document.querySelector('.ff-pending-remove')) return true;
      if(generatedOutputIsDirty()) return true;
    }catch(e){ return true; }
    return false;
  }
  function refreshResetBtn(){
    try{
      var b = document.getElementById('resetDefaults');
      if(b) b.disabled = !resetIsDirty();
    }catch(e){}
  }
  try{
    var resetBtn = document.getElementById('resetDefaults');
    if(resetBtn) resetBtn.addEventListener('click', resetToDefaults);
    document.addEventListener('change', function(){ refreshResetBtn(); });
    document.addEventListener('click', function(){ setTimeout(refreshResetBtn, 0); });
    refreshResetBtn();
    setTimeout(refreshResetBtn, 900);
    // re-render the source line on live market changes (#213) — without this it names
    // the load-time market forever while the rest of the UI moves on.
    document.addEventListener('change', function(e){
      if(e.target && e.target.id === 'locality'){ try{ renderMarketSource(null); }catch(_){} }
    });
  }catch(e){}

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
      if(place.indexOf('Market: ') === 0) place = place.slice('Market: '.length);
      else if(place.indexOf('Location: ') === 0) place = place.slice('Location: '.length);
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
      } else if(cur === DEFAULT_MARKET){
        el.textContent = 'Market: ' + place + ' — Park City default';
      } else {
        el.textContent = 'Market: ' + place;
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

      // staged DAM picks — rehydrate by key: the request path re-fetches server-side
      // (fetch_dam_key), so no presigned url is needed. Chips rebuild without thumbs;
      // the pick is fully functional at the next Create.
      try{
        var damList = Array.isArray(snap.userDamAssets) ? snap.userDamAssets : [];
        var buildChip = window.KODIAK_buildChip;
        var rehydrated = [];
        damList.forEach(function(d){
          if(!d || !d.key) return;
          try{
            var exists = (window.__userAssets || []).some(function(a){ return a && a.source === 'dam' && a.key === d.key; });
            if(exists) return;
            window.__userAssets = window.__userAssets || [];
            var rec = {id: 'dam-asset-restore-' + rehydrated.length, name: d.name || d.key, kind: d.kind, source: 'dam', key: d.key, url: null, category: d.category};
            window.__userAssets.push(rec);
            if(typeof buildChip === 'function'){ buildChip(rec, null); }
            rehydrated.push(rec.name);
          }catch(e){}
        });
        if(rehydrated.length){ showRestoredNote(rehydrated); }
      }catch(e){}

      // staged uploads — blob URLs are gone after a discard; show a non-blocking re-add note (no fake assets).
      // DAM picks restored above are excluded: their keys (not names) identify them.
      try{
        var restoredKeys = {};
        (Array.isArray(snap.userDamAssets) ? snap.userDamAssets : []).forEach(function(d){ if(d && d.name) restoredKeys[d.name] = true; });
        var missing = (Array.isArray(snap.userAssetNames) ? snap.userAssetNames : []).filter(function(n){ return !restoredKeys[n]; });
        if(missing.length){ showAssetReAddNote(missing); }
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
