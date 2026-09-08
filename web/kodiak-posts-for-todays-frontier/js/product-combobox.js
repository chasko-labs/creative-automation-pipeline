// --- Product combobox + shared selection tray ---
// The product grid is folded into a closed <details>; #productChooser is now a HIDDEN checkbox host that
// stays the source of truth (the generate path + Random 3 + change-delegation all read it unchanged).
// This wiring: (1) mirrors the hidden checkboxes into #productResults as combobox options, (2) reflects
// checked SKUs as removable chips in the shared #selectionTray, (3) toggles checkboxes from the popover/chips.
(function(){
  var search  = document.getElementById('productSearch');
  var results = document.getElementById('productResults');
  var chooser = document.getElementById('productChooser');
  var tray    = document.getElementById('selectionTray');
  var details = document.getElementById('existingAssets');
  if(!search || !results || !chooser || !tray) return;

  function boxes(){ return Array.prototype.slice.call(chooser.querySelectorAll('.sku-check')); }
  function checkedBoxes(){ return boxes().filter(function(b){ return b.checked; }); }
  function boxFor(value){ return boxes().find(function(b){ return b.value===value; }) || null; }
  function removeSkuChip(value){
    // Drop the tray chip(s) for a value regardless of host state. A chip whose
    // box was destroyed by a host re-filter is a stale claim — leaving it makes
    // the X a silent no-op (#250). Truth lives in the live boxes; the chip is void.
    try{
      Array.prototype.slice.call(tray.querySelectorAll('.ff-pending-chip[data-sku]')).forEach(function(c){
        if(c.dataset && c.dataset.sku===value && typeof c.remove==='function') c.remove();
      });
    }catch(e){}
  }

  // reflect the combobox expanded state for assistive tech
  function setExpanded(open){ search.setAttribute('aria-expanded', open ? 'true' : 'false'); results.hidden = !open; }

  // mirror the hidden host's staged rows into the popover (thumb reused from the host).
  // Deliberately NO independent filter here: the host (generate.js render) owns the single
  // name+handle+category filter, so the popover can never disagree with it, blank on a
  // category word like "power", or lag a keystroke behind. The host never blanks (no-match
  // falls back to the first 12), so neither does the popover.
  function renderResults(){
    var matched = boxes().slice(0, 12);
    if(!matched.length){ setExpanded(false); results.innerHTML = ''; return; }
    results.innerHTML = '';
    matched.forEach(function(b){
      var opt = document.createElement('button');
      opt.type = 'button';
      opt.setAttribute('role', 'option');
      opt.setAttribute('aria-selected', b.checked ? 'true' : 'false');
      opt.dataset.value = b.value;
      // reuse the thumbnail painted into the hidden host, if any
      var hostImg = b.parentNode ? b.parentNode.querySelector('img') : null;
      var thumbHtml = (hostImg && hostImg.src) ? '<img class="ff-opt-thumb" src="' + hostImg.src + '" alt="" onerror="this.style.display=\'none\'">' : '';
      opt.innerHTML = thumbHtml + '<span>' + b.value + '</span>';
      opt.addEventListener('click', function(){ toggleSku(b.value); search.focus(); });
      results.appendChild(opt);
    });
    setExpanded(true);
  }

  // toggle a SKU via its hidden checkbox so the existing change-delegation (3-cap, hint) runs unchanged
  function toggleSku(value){
    var b = boxFor(value);
    if(!b){
      // #250: the box is gone from the host (a re-filter destroyed it) but the
      // stale chip remains — the X voids that one claim only. No tray re-sync
      // here: sibling stale chips record surviving intent (their boxes may come
      // back via another filter); reset owns the bulk truth-sync instead.
      removeSkuChip(value);
      return;
    }
    if(!b.checked && checkedBoxes().length >= 3){
      var hint = document.getElementById('skuHint');
      if(hint){ hint.textContent = 'Max 3 — remove one first'; }
      return;
    }
    b.checked = !b.checked;
    b.dispatchEvent(new Event('change', {bubbles:true}));
    removeSkuChip(value);
    syncSkuChips();
    renderResults();
  }
  // #250: let resetToDefaults re-sync the tray after unchecking — a repaint from
  // live boxes is the only honest chip state (stale chips must not survive reset).
  try{ window.__kodiakSyncSkuChips = syncSkuChips; }catch(e){}

  // render one removable chip per selected SKU into the SHARED tray (same treatment as staged uploads)
  function syncSkuChips(){
    // clear only SKU chips; upload chips (.ff-pending-chip with an id starting pending-asset-) stay put
    Array.prototype.slice.call(tray.querySelectorAll('.ff-pending-chip[data-sku]')).forEach(function(c){ c.remove(); });
    checkedBoxes().forEach(function(b){
      var chip = document.createElement('div');
      chip.className = 'ff-pending-chip';
      chip.dataset.sku = b.value;
      var nm = document.createElement('span');
      nm.className = 'ff-pending-name';
      nm.textContent = b.value;
      var rm = document.createElement('button');
      rm.type = 'button';
      rm.className = 'ff-pending-remove';
      rm.setAttribute('aria-label', 'Remove product ' + b.value);
      rm.textContent = '\u00d7';
      rm.addEventListener('click', function(){ toggleSku(b.value); });
      chip.appendChild(nm); chip.appendChild(rm);
      tray.appendChild(chip);
    });
  }

  // the host repaint (generate.js render) calls window.__syncProductPopover after every
  // repaint, so the popover tracks the staged rows with no keystroke lag; expose the sync
  // for that cross-file hook. The input listener stays as a backstop.
  window.__syncProductPopover = function(){ renderResults(); };
  // combobox interactions
  search.addEventListener('input', renderResults);
  search.addEventListener('focus', renderResults);
  search.addEventListener('keydown', function(e){
    var opts = Array.prototype.slice.call(results.querySelectorAll('[role="option"]'));
    if(e.key === 'Escape'){ setExpanded(false); return; }
    if(!opts.length) return;
    var idx = opts.findIndex(function(o){ return o.classList.contains('is-active'); });
    if(e.key === 'ArrowDown'){ e.preventDefault(); var n = opts[Math.min(opts.length-1, idx+1)] || opts[0]; opts.forEach(function(o){ o.classList.remove('is-active'); }); n.classList.add('is-active'); n.focus(); }
    else if(e.key === 'ArrowUp'){ e.preventDefault(); var p = opts[Math.max(0, idx-1)] || opts[0]; opts.forEach(function(o){ o.classList.remove('is-active'); }); p.classList.add('is-active'); p.focus(); }
    else if(e.key === 'Enter'){ if(idx >= 0){ e.preventDefault(); toggleSku(opts[idx].dataset.value); } }
  });
  // click outside the disclosure closes the popover
  document.addEventListener('click', function(e){ if(details && !details.contains(e.target)) setExpanded(false); });

  // keep tray chips in sync whenever the hidden host changes (Random 3, catalog re-render, clear-theme, etc.)
  chooser.addEventListener('change', function(e){ if(e.target && e.target.classList && e.target.classList.contains('sku-check')) syncSkuChips(); });
  document.getElementById('randomProducts')?.addEventListener('click', function(){ setTimeout(syncSkuChips, 0); });
  // catalog fetch re-paints the hidden host asynchronously — resync chips shortly after load
  setTimeout(syncSkuChips, 900);
})();
