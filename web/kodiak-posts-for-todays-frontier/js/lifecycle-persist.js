// --- Page Lifecycle API: snapshot/restore inputs across Chrome Memory Saver tab discard (freeze/pagehide) ---
// Self-contained. Persists a SMALL text snapshot of the campaign inputs on hide/pagehide/freeze and
// rehydrates on load if the snapshot is < 24h old. Does NOT store DOM, blobs, object URLs, or catalogs.
// blob: object URLs for staged uploads do NOT survive a tab discard, so only the upload NAMES are kept
// as a re-derivation note — the user is told to re-add them; no fake assets are fabricated.
(function(){
  var KEY = 'kodiak_ff_state_v1';
  var MAX_AGE_MS = 24 * 60 * 60 * 1000;

  function checkedSkus(){
    try{
      return Array.prototype.slice.call(document.querySelectorAll('.sku-check'))
        .filter(function(b){ return b.checked; })
        .map(function(b){ return b.value; });
    }catch(e){ return []; }
  }

  function persist(){
    try{
      var snap = {};
      try{ snap.brief    = document.getElementById('campaignBrief')?.value; }catch(e){}
      try{ snap.locality = document.getElementById('locality')?.value; }catch(e){}
      try{ snap.season   = document.getElementById('seasonalSelect')?.value; }catch(e){}   // real id is #seasonalSelect (a legacy #season lookup silently persisted nothing)
      try{ snap.skus     = checkedSkus(); }catch(e){}
      try{ snap.userAssetNames = (window.__userAssets || []).map(function(a){ return a && a.name; }).filter(Boolean); }catch(e){}
      snap.ts = Date.now();
      localStorage.setItem(KEY, JSON.stringify(snap));
    }catch(e){}
  }

  // clear hook — called by the generate success path so a completed campaign does not resurrect on next visit
  window.__kodiakClearFFState = function(){ try{ localStorage.removeItem(KEY); }catch(e){} };

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

  function restore(){
    var snap = null;
    try{ snap = JSON.parse(localStorage.getItem(KEY) || 'null'); }catch(e){ snap = null; }
    if(!snap || typeof snap.ts !== 'number' || (Date.now() - snap.ts) > MAX_AGE_MS) return;

    // brief — dispatch input so the autocomplete + auto-grow handlers re-run
    try{
      var briefEl = document.getElementById('campaignBrief');
      if(briefEl && snap.brief && !briefEl.value){ briefEl.value = snap.brief; briefEl.dispatchEvent(new Event('input', {bubbles:true})); }
    }catch(e){}

    // locality — only if the saved option exists; dispatch change so onLocality/renderLangChips re-run
    try{
      var locEl = document.getElementById('locality');
      if(locEl && snap.locality){
        var hasOpt = Array.prototype.slice.call(locEl.options || []).some(function(o){ return o.value === snap.locality; });
        if(hasOpt && locEl.value !== snap.locality){ locEl.value = snap.locality; locEl.dispatchEvent(new Event('change', {bubbles:true})); }
      }
    }catch(e){}

    // season — restore against #seasonalSelect; dispatch change so market-disclosure's handler
    // re-derives window.__activeSeason and the autocomplete suffix (reflect) rebuilds from it.
    try{
      var seasonEl = document.getElementById('seasonalSelect');
      if(seasonEl && snap.season && seasonEl.value !== snap.season){
        var hasSeasonOpt = Array.prototype.slice.call(seasonEl.options || []).some(function(o){ return o.value === snap.season; });
        if(hasSeasonOpt){ seasonEl.value = snap.season; seasonEl.dispatchEvent(new Event('change', {bubbles:true})); }
      }
    }catch(e){}

    // SKUs — re-check matching .sku-check boxes; dispatch change (bubbles) so the combobox syncSkuChips
    // delegation + the clear-theme delegation on #productChooser both re-run and the tray chips reappear.
    try{
      var want = {};
      (snap.skus || []).forEach(function(v){ want[v] = true; });
      var restored = 0;
      Array.prototype.slice.call(document.querySelectorAll('.sku-check')).forEach(function(b){
        if(want[b.value] && !b.checked){ b.checked = true; b.dispatchEvent(new Event('change', {bubbles:true})); restored++; }
      });
    }catch(e){}

    // staged uploads — blob URLs are gone after a discard; show a non-blocking re-add note (no fake assets)
    try{
      if(Array.isArray(snap.userAssetNames) && snap.userAssetNames.length){ showAssetReAddNote(snap.userAssetNames); }
    }catch(e){}
  }

  // persist triggers — hidden visibilitychange + pagehide + freeze (all the discard-adjacent lifecycle events)
  try{ document.addEventListener('visibilitychange', function(){ if(document.visibilityState === 'hidden') persist(); }); }catch(e){}
  try{ window.addEventListener('pagehide', persist); }catch(e){}
  try{ document.addEventListener('freeze', persist); }catch(e){}

  // rehydrate after the selects + SKU checkboxes are populated. fillSelects runs synchronously on load and
  // the SKU catalog paints asynchronously (~900ms), so restore on a short delay and retry once for the SKUs.
  function runRestore(){ try{ restore(); }catch(e){} }
  if(document.readyState === 'loading'){ document.addEventListener('DOMContentLoaded', function(){ setTimeout(runRestore, 700); }); }
  else { setTimeout(runRestore, 700); }
  setTimeout(runRestore, 1500);   // second pass — SKU checkboxes may finish painting after the first pass
})();
