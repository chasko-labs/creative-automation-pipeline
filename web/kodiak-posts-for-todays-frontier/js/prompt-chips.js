// --- Simplified Park City demo wiring: prompt chips, upload affordance, textarea auto-grow ---
(function(){
  // Creative-direction chips — ADDITIVE MULTI-SELECT toggles (aria-pressed on/off). Redesign change:
  // chips no longer OVERWRITE the brief with canned copy. Instead we maintain window.__activeDirections
  // (a Set of theme slugs) and rebuild a MANAGED REGION at the end of the brief on every toggle. The
  // user's own typed text lives ABOVE the managed region and is never clobbered — toggling only rewrites
  // the block between two sentinels. window.__activeTheme is kept for backward compat (generate.js reads
  // it): it holds the MOST-RECENTLY-toggled-on direction (or null when none remain active).
  var briefEl = document.getElementById('campaignBrief');
  var chipWrap = document.getElementById('promptChips');

  // Sentinel-delimited managed region. Everything between BEGIN and END is owned by the chip logic;
  // everything before BEGIN is the user's free text. Using an HTML-comment-style sentinel keeps it
  // visually unobtrusive if it ever surfaces, and unlikely to collide with real brief prose.
  var DIR_BEGIN = '\u2014 directions: ';   // "— directions: " reads as natural brief prose
  var activeDirections = window.__activeDirections instanceof Set ? window.__activeDirections : new Set();
  window.__activeDirections = activeDirections;
  // theme slug -> short human-readable clause (kept concise; the richer data-brief text would bloat the
  // managed region when several chips stack, so we use short labels here for the accumulated line).
  var DIRECTION_CLAUSES = {};

  // partner mark visibility — only when the US Ski & Snowboard direction is ACTIVE within the
  // multi-select set (not tied to a single active theme any more). Tasteful, not overused.
  function togglePartnerMark(){
    var mark = document.getElementById('ussPartnerMark');
    if(!mark) return;
    var on = activeDirections.has('us-ski-snowboard');
    mark.hidden = !on;
    mark.style.display = on ? 'flex' : 'none';
  }

  // split the brief into { userText, hasManaged } — the managed region is the tail from DIR_BEGIN on.
  function splitBrief(){
    var v = briefEl ? briefEl.value : '';
    var idx = v.lastIndexOf(DIR_BEGIN);
    if(idx === -1) return { userText: v, hasManaged: false };
    return { userText: v.slice(0, idx).replace(/\s+$/,''), hasManaged: true };
  }

  // rebuild the brief = user's free text + a freshly-assembled managed directions line (or nothing
  // when no chips are active). Never touches the user's portion. Guarded so the input handler this
  // triggers does not treat the programmatic write as a manual edit.
  function rebuildBrief(){
    if(!briefEl) return;
    var parts = splitBrief();
    var clauses = [];
    chipWrap.querySelectorAll('.ff-chip').forEach(function(c){
      var slug = c.getAttribute('data-theme');
      if(slug && activeDirections.has(slug)){
        clauses.push(DIRECTION_CLAUSES[slug] || (c.getAttribute('data-label') || slug));
      }
    });
    var next = parts.userText;
    if(clauses.length){
      next = (next ? next + ' ' : '') + DIR_BEGIN + clauses.join(', ');
    }
    window.__chipSettingBrief = true;
    briefEl.value = next;
    briefEl.dispatchEvent(new Event('input', {bubbles:true}));
    window.__chipSettingBrief = false;
  }

  // clear every active direction (called on manual edit of the USER portion, or product change).
  window.__clearActiveTheme = function(){
    if(!activeDirections.size){ window.__activeTheme = null; return; }
    activeDirections.clear();
    window.__activeTheme = null;
    if(chipWrap) chipWrap.querySelectorAll('.ff-chip').forEach(function(c){ c.setAttribute('aria-pressed','false'); });
    togglePartnerMark();
    rebuildBrief();
  };

  if(chipWrap && briefEl){
    chipWrap.querySelectorAll('.ff-chip[data-theme]').forEach(function(chip){
      var slug = chip.getAttribute('data-theme');
      // seed the short clause from data-label (falls back to the visible chip text)
      DIRECTION_CLAUSES[slug] = chip.getAttribute('data-label') || chip.textContent.trim();
      chip.addEventListener('click', function(){
        var nowActive = !activeDirections.has(slug);
        if(nowActive){ activeDirections.add(slug); window.__activeTheme = slug; }
        else {
          activeDirections.delete(slug);
          // most-recently-toggled-on remaining direction becomes __activeTheme (back-compat single-theme)
          if(window.__activeTheme === slug){
            var remaining = Array.prototype.slice.call(chipWrap.querySelectorAll('.ff-chip'))
              .filter(function(c){ return activeDirections.has(c.getAttribute('data-theme')); });
            window.__activeTheme = remaining.length ? remaining[remaining.length-1].getAttribute('data-theme') : null;
          }
        }
        chip.setAttribute('aria-pressed', nowActive ? 'true' : 'false');
        togglePartnerMark();
        rebuildBrief();
        // honest riff: the chip directs a STAGED pick, it is not retrieval. Tell the
        // customer what to do instead of letting the default masquerade as a remix.
        // Non-blocking — Create still generates normally with no pick staged.
        if(nowActive && slug === 'riff-on-past-content'){
          try{
            var hasStaged = (window.__userAssets||[]).some(function(a){ return a && a.source==='dam' && a.key; });
            // NOTE: flash() lives in the DAM-browse IIFE below — not visible here.
            // Write the status node directly (it is static markup, always present).
            if(!hasStaged){ var cueEl = document.getElementById('damFlash'); if(cueEl) cueEl.textContent = 'Riff on past content riffs on your staged pick — Browse past assets and stage one, or Create generates fresh.'; }
          }catch(e){}
        }
        briefEl.focus();
      });
    });
    // Manual textarea edit of the USER portion clears directions. Guarded against the chip's own
    // programmatic input event. Only clears when the user actually typed into their free-text region
    // (i.e. an edit happened while directions were active and it was not a chip-driven write).
    briefEl.addEventListener('input', function(){
      if(window.__chipSettingBrief) return;
      if(activeDirections.size) window.__clearActiveTheme();
    });
  }
  // Selecting/deselecting a product clears the active directions too (a product pick is its own start).
  document.getElementById('productChooser')?.addEventListener('change', function(e){
    if(e.target && e.target.classList && e.target.classList.contains('sku-check')) window.__clearActiveTheme();
  });

  // ---- STEP 1: campaign scope segmented control (WAI-ARIA radiogroup) ----
  // The first + most important decision. Stores the selection on window.__campaignScope (read by
  // Create in generate.js and by the full-campaign generate in campaign-sections.js). Keyboard: arrow
  // keys move + activate the selection per the radiogroup pattern; roving tabindex keeps one radio
  // tabbable. scope="nationwide" flips the control row into a de-emphasized localization-anchor mode.
  (function(){
    var group = document.getElementById('campaignScope');
    if(!group) return;
    var opts = Array.prototype.slice.call(group.querySelectorAll('.ff-scope-opt'));
    if(!opts.length) return;
    var controlRow = document.querySelector('.ff-controlrow');
    var scopeNote = document.getElementById('marketScopeNote');

    // default from the pre-checked radio in markup (data-scope="local"); fall back to first option.
    var initial = opts.find(function(o){ return o.getAttribute('aria-checked') === 'true'; }) || opts[0];
    window.__campaignScope = initial.getAttribute('data-scope') || 'local';

    function applyScopeMode(scope){
      if(controlRow){ controlRow.setAttribute('data-scope-mode', scope); }
      if(scopeNote){ scopeNote.hidden = (scope !== 'nationwide'); }
    }

    function select(opt, focus){
      opts.forEach(function(o){
        var on = (o === opt);
        o.setAttribute('aria-checked', on ? 'true' : 'false');
        o.tabIndex = on ? 0 : -1;
      });
      window.__campaignScope = opt.getAttribute('data-scope') || 'local';
      applyScopeMode(window.__campaignScope);
      // fold-density: keep the collapsed disclosure summary showing the active scope
      try{
        var sumEl = document.getElementById('scopeSummary');
        var titleEl = opt.querySelector('.ff-scope-opt-title');
        if(sumEl && titleEl && titleEl.textContent) sumEl.textContent = titleEl.textContent.trim();
      }catch(e){}
      if(focus){ try{ opt.focus(); }catch(e){} }
    }

    opts.forEach(function(opt){
      opt.addEventListener('click', function(){ select(opt, false); });
      opt.addEventListener('keydown', function(e){
        var i = opts.indexOf(opt);
        var next = -1;
        if(e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i + 1) % opts.length;
        else if(e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i - 1 + opts.length) % opts.length;
        else if(e.key === 'Home') next = 0;
        else if(e.key === 'End') next = opts.length - 1;
        else if(e.key === ' ' || e.key === 'Enter'){ e.preventDefault(); select(opt, true); return; }
        else return;
        e.preventDefault();
        select(opts[next], true);
      });
    });

    // set the initial roving tabindex + scope-mode from the pre-checked default
    select(initial, false);
  })();

  // Upload affordance — the + icon triggers the real staging file input (#addAssetInput),
  // whose change handler stages a removable chip in the shared selection tray + threads window.__userAssets.
  document.getElementById('promptUpload')?.addEventListener('click', function(){
    var input = document.getElementById('addAssetInput');
    if(input){ try{ input.click(); }catch(e){} }
  });

  // ---- Browse past assets (DAM) — ADDITIVE second staging path into the SAME #selectionTray ----
  // Reads GET /assets/library and stages a chosen asset via the shared KODIAK_buildChip so a DAM asset
  // behaves like a local upload downstream (window.__userAssets threads name/label into the brief).
  // Fully guarded: enabled:false, HTTP 500, malformed JSON, timeout, or offline all show the friendly
  // "unavailable" message and never throw. Does NOT touch the local-file upload path or Track 6 routing.
  (function(){
    var trigger  = document.getElementById('damBrowseTrigger');
    var backdrop = document.getElementById('damBackdrop');
    var panel    = document.getElementById('damPanel');
    var closeBtn = document.getElementById('damPanelClose');
    var body     = document.getElementById('damBody');
    var flashEl  = document.getElementById('damFlash');
    if(!trigger || !panel || !backdrop || !body) return;  // markup missing — degrade to no-op

    // resolve the library endpoint the same way localizeText resolves /localize: hosted origin only.
    // offline (file://) or localhost -> no endpoint -> honest "unavailable offline" without a fetch.
    var _isLocal = (location.protocol==='file:') || ['127.0.0.1','localhost'].includes(location.hostname);
    var LIB_ENDPOINT = window.KODIAK_LIBRARY_ENDPOINT || (_isLocal ? null : '/assets/library');
    // 6-tab marketer taxonomy — Products default-active (the shelf a marketer reaches for first).
    var CAT_LABELS = { 'products':'Products', 'recipes':'Recipes', 'lifestyle':'Lifestyle', 'ideas':'Ideas', 'themes':'Themes', 'brand':'Brand' };
    var TAB_ORDER = ['products','recipes','lifestyle','ideas','themes','brand'];

    // marketer-voice copy — every user-facing string lives here so tone stays in one place.
    var COPY_SEARCH_PLACEHOLDER = 'Search this stack\u2026';
    var COPY_FOOTER_SELECTED    = '{n} selected \u2014 ready to stack into your campaign idea';
    var COPY_FOOTER_NONE        = 'Pick an asset to add it to your campaign idea';
    var COPY_SPARSE             = 'A small, hand-picked set \u2014 this stack is meant to run lean.';
    var COPY_EMPTY              = 'Nothing on this shelf yet. Try another tab.';
    var COPY_LOADING            = 'Loading past assets\u2026';
    var COPY_OFFLINE            = 'Past assets unavailable offline.';
    var COPY_LOAD_MORE          = 'Load more';
    var COPY_END                = 'That\u2019s the whole stack.';
    var SPARSE_THRESHOLD        = 20;   // total <= this (but > 0) shows the "run lean" note
    var PAGE_LIMIT = 24;   // #171: 60-item presign fan-out measured 6.4s > 6s abort; 24 keeps p95 under timeout
    var DAM_TIMEOUT_MS = 12000;
    var COPY_TIMEOUT = 'Past assets timed out. Try again.';
    var COPY_ERROR = 'Past assets unavailable right now. Try again.';
    function damLog(outcome, failureClass, latencyMs, extra){
      try{ console.info('[dam] outcome=' + outcome + ' latency_ms=' + latencyMs + ' class=' + failureClass + (extra ? ' ' + extra : '')); }catch(e){}
    }
    function damClassify(err, json){
      if(!navigator.onLine) return 'offline';
      if(err && (err.name === 'AbortError' || /abort/i.test(String((err && err.message) || '')))) return 'abort';
      if(err && /HTTP\s+\d+/.test(String((err && err.message) || ''))) return 'http';
      if(json && json.enabled !== true) return 'empty';
      return 'empty';
    } // #171: must exceed 6.4s endpoint; abort race lost at 6s

    // client-side Type facets, scoped per active tab. A one-entry ['All'] list auto-hides (noise).
    var TYPE_FACETS = {
      'products':  ['All','Flapjack & Waffle','Cups','Oatmeal','Bars','Granola','Frozen','Baking','Protein Balls'],
      'recipes':   ['All'],
      'lifestyle': ['All','People','Outdoors','Kitchen'],
      'ideas':     ['All'],
      'themes':    ['All'],
      'brand':     ['All','Heroes','Logos','Zac Efron','References']
    };
    // multi-token chips (matched as OR against the tile haystack); everything else is its lowercased token.
    var TYPE_KEYWORDS = { 'flapjack & waffle': ['flapjack','waffle'] };
    // Ratio facets are AND-combined with Type + search; the whole row auto-hides when no loaded tile carries a ratio.
    var RATIO_FACETS = ['All','1x1','4x5','9x16','16x9'];

    var loaded = false;      // fetch once per session; re-open reuses cached model
    var lastFocus = null;    // element to restore focus to on close

    // --- session-scoped state (rebuilt per load; torn down on close) ---
    var model = {};          // cat -> { items:[...], total:number }
    var activeCat = null;    // currently shown tab
    var selectedKey = null;  // key of the staged/selected tile (persists across tab switches)
    var io = null;           // IntersectionObserver for lazy image load + far-scroll cleanup
    var tablist = null;      // the tab bar element (for arrow-key nav + roving tabindex)
    var filterInput = null;  // the search box
    var gridEl = null;       // the active listbox grid
    var footerEl = null;     // selection footer line (COPY_FOOTER_*)
    var sparseEl = null;     // "run lean" note under the tab bar
    var typeRowEl = null;    // Type facet chip row
    var ratioRowEl = null;   // Ratio facet chip row
    var moreEl = null;       // load-more button / end-of-stack line wrapper
    var activeType = 'All';  // active Type facet (per tab; reset on tab switch)
    var activeRatio = 'All'; // active Ratio facet (per tab; reset on tab switch)

    function flash(msg){ try{ if(flashEl) flashEl.textContent = String(msg||''); }catch(e){} }

    // status line lives inside #damBody but MUST NOT wipe the shell (tabs+filter) once built.
    function setStatus(msg){
      try{
        clearGrid();
        if(!gridEl){ body.innerHTML=''; var p=document.createElement('p'); p.className='ff-dam-status'; p.textContent=String(msg||''); body.appendChild(p); return; }
        var s=document.createElement('p'); s.className='ff-dam-status'; s.textContent=String(msg||''); gridEl.appendChild(s);
      }catch(e){}
    }

    function openPanel(){
      lastFocus = document.activeElement;
      backdrop.hidden = false; panel.hidden = false;
      backdrop.classList.add('is-open'); panel.classList.add('is-open');
      trigger.setAttribute('aria-expanded','true');
      document.addEventListener('keydown', onDocKeydown, true);
      if(!loaded) loadLibrary();
      else focusFirstControl();
    }

    // teardown matters — this app has a leak-audit history. Disconnect the observer, drop image
    // src refs, clear grid nodes, and remove the document-level keydown trap on every close.
    function closePanel(){
      backdrop.classList.remove('is-open'); panel.classList.remove('is-open');
      backdrop.hidden = true; panel.hidden = true;
      trigger.setAttribute('aria-expanded','false');
      flash('');
      document.removeEventListener('keydown', onDocKeydown, true);
      teardownGrid();
      // return focus to the trigger (or the "+" if the trigger is gone)
      var back = (lastFocus && lastFocus.isConnected) ? lastFocus : trigger;
      try{ (back || trigger).focus(); }catch(e){}
    }

    // document-level keydown trap, added with capture on open / removed on close (symmetry matters
    // for the leak-audit history). Only job: Escape closes the modal DAM panel. Everything else
    // passes through untouched — tab/tile arrow nav is owned by onTabKeydown/onTileKeydown on their
    // own elements, so this handler must not preventDefault or interfere with other keys.
    function onDocKeydown(e){
      if(e.key === 'Escape'){ e.preventDefault(); closePanel(); }
    }

    // release the IntersectionObserver + null every img.src so presigned bitmaps can be GC'd.
    function teardownGrid(){
      if(io){ try{ io.disconnect(); }catch(e){} io = null; }
      if(gridEl){
        gridEl.querySelectorAll('img').forEach(function(img){ img.src=''; });
      }
    }
    function clearGrid(){
      if(io){ try{ io.disconnect(); }catch(e){} io = null; }
      if(gridEl){ gridEl.innerHTML=''; }
    }

    // GET /assets/library (no category param -> all groups). 6s AbortController timeout, mirrors localizeText.
    function loadLibrary(){
      if(!LIB_ENDPOINT){ buildShell(); renderUnavailable(COPY_OFFLINE); loaded = true; return; }
      body.innerHTML = ''; var p=document.createElement('p'); p.className='ff-dam-status'; p.textContent=COPY_LOADING; body.appendChild(p);
      var t0 = Date.now();
      var controller = new AbortController();
      var timer = setTimeout(function(){ controller.abort(); }, DAM_TIMEOUT_MS || 12000);
      fetch(LIB_ENDPOINT + '?limit=' + PAGE_LIMIT, {signal: controller.signal})
        .then(function(r){ if(!r.ok) throw new Error('library HTTP '+r.status); return r.json(); })
        .then(function(j){
          if(!j || j.enabled !== true){ buildShell(); renderUnavailable(COPY_OFFLINE); }
          if(!j || j.enabled !== true){ buildShell(); renderUnavailable(COPY_OFFLINE); damLog('unavailable','empty', Date.now()-t0, 'enabled!=true'); }
          else { ingest(j); buildShell(); renderActiveTab(); focusFirstControl(); damLog('ok','none', Date.now()-t0, 'limit='+PAGE_LIMIT); }
          loaded = true;
        })
        .catch(function(err){ var lat = Date.now()-t0; var cls = damClassify(err); var msg = (cls==='offline') ? COPY_OFFLINE : (cls==='abort') ? COPY_TIMEOUT : (cls==='http') ? COPY_ERROR : COPY_OFFLINE; damLog('error', cls, lat, String((err && err.message)||err)); buildShell(); renderUnavailable(msg); loaded = true; })
        .finally(function(){ clearTimeout(timer); });
    }

    // normalize server payload into `model`; pick the default active tab.
    // model[cat] carries items + total + pagination cursors (offset/count/has_more/next_offset).
    function ingest(j){
      var cats = (j && j.categories) || {};
      var order = TAB_ORDER.slice();
      Object.keys(cats).forEach(function(k){ if(order.indexOf(k)===-1) order.push(k); });
      model = {}; activeCat = null;
      order.forEach(function(cat){
        var entry = cats[cat];
        if(!entry) return;
        var items = (entry && entry.items) || [];
        var total = (typeof entry.total === 'number') ? entry.total : items.length;
        model[cat] = {
          items: items,
          total: total,
          has_more: (entry.has_more === true),
          next_offset: (typeof entry.next_offset === 'number') ? entry.next_offset : null
        };
      });
      // Products is the default shelf; fall back to first known tab, then first non-empty.
      if(model[TAB_ORDER[0]]) activeCat = TAB_ORDER[0];
      if(activeCat === null){ var ks = Object.keys(model); activeCat = ks.length ? ks[0] : null; }
    }

    function renderUnavailable(msg){
      setStatus(msg || COPY_OFFLINE);
    }

    // build the persistent shell inside #damBody: tab bar + filter input + empty grid listbox.
    // Rebuilt fresh each load; child of #damBody only (index.html untouched).
    function buildShell(){
      body.innerHTML = '';
      var cats = Object.keys(model);
      if(!cats.length){ return; }  // nothing to tab over — caller shows status

      var controls = document.createElement('div');
      controls.className = 'ff-dam-controls';

      tablist = document.createElement('div');
      tablist.className = 'ff-dam-tabs';
      tablist.setAttribute('role','tablist');
      tablist.setAttribute('aria-label','Asset categories');
      cats.forEach(function(cat){
        var tab = document.createElement('button');
        tab.type = 'button';
        tab.className = 'ff-dam-tab';
        tab.setAttribute('role','tab');
        tab.id = 'dam-tab-' + cat;
        tab.dataset.cat = cat;
        var isActive = (cat === activeCat);
        tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
        tab.tabIndex = isActive ? 0 : -1;   // roving tabindex across the tablist
        var count = model[cat].total;
        tab.textContent = (CAT_LABELS[cat] || cat) + (count ? ' (' + count + ')' : '');
        tab.addEventListener('click', function(){ selectTab(cat); });
        tab.addEventListener('keydown', onTabKeydown);
        tablist.appendChild(tab);
      });
      controls.appendChild(tablist);

      var filterWrap = document.createElement('div');
      filterWrap.className = 'ff-dam-filter';
      filterInput = document.createElement('input');
      filterInput.type = 'search';
      filterInput.className = 'ff-dam-filter-input';
      filterInput.setAttribute('placeholder', COPY_SEARCH_PLACEHOLDER);
      filterInput.setAttribute('aria-label','Filter assets in this category');
      filterInput.addEventListener('input', applyFilter);
      filterWrap.appendChild(filterInput);
      controls.appendChild(filterWrap);

      body.appendChild(controls);

      // "run lean" note under the tab bar — shown only when the active category is a small set.
      sparseEl = document.createElement('p');
      sparseEl.className = 'ff-dam-sparse';
      sparseEl.hidden = true;
      body.appendChild(sparseEl);

      // two client-side facet rows (Type, Ratio) between tab bar and grid. Populated per tab.
      typeRowEl = document.createElement('div');
      typeRowEl.className = 'ff-dam-facets ff-dam-facets-type';
      typeRowEl.setAttribute('role','group');
      typeRowEl.setAttribute('aria-label','Filter by type');
      body.appendChild(typeRowEl);

      ratioRowEl = document.createElement('div');
      ratioRowEl.className = 'ff-dam-facets ff-dam-facets-ratio';
      ratioRowEl.setAttribute('role','group');
      ratioRowEl.setAttribute('aria-label','Filter by ratio');
      body.appendChild(ratioRowEl);

      gridEl = document.createElement('div');
      gridEl.className = 'ff-dam-grid';
      gridEl.setAttribute('role','listbox');
      gridEl.setAttribute('aria-label','Past assets');
      body.appendChild(gridEl);

      // load-more / end-of-stack line lives after the grid.
      moreEl = document.createElement('div');
      moreEl.className = 'ff-dam-more';
      body.appendChild(moreEl);

      // selection footer — reflects selectedKey; persists across tab switches.
      footerEl = document.createElement('p');
      footerEl.className = 'ff-dam-footer';
      footerEl.setAttribute('role','status');
      footerEl.setAttribute('aria-live','polite');
      body.appendChild(footerEl);
      renderFooter();
    }

    // footer line: count of DAM-staged selection, or the "pick one" prompt when nothing selected.
    function renderFooter(){
      if(!footerEl) return;
      if(selectedKey){ footerEl.textContent = COPY_FOOTER_SELECTED.replace('{n}', '1'); }
      else { footerEl.textContent = COPY_FOOTER_NONE; }
    }

    // sparse note visibility for the active category (total <= threshold but > 0).
    function renderSparse(){
      if(!sparseEl) return;
      var entry = model[activeCat];
      var total = (entry && typeof entry.total === 'number') ? entry.total : 0;
      var show = (total > 0 && total <= SPARSE_THRESHOLD);
      sparseEl.hidden = !show;
      sparseEl.textContent = show ? COPY_SPARSE : '';
    }

    // build/refresh the Type + Ratio facet rows for the active tab.
    // Type row auto-hides when the tab's list is ['All'] only. Ratio row auto-hides when no loaded
    // tile in the active tab carries a ratio. Reset active facets to 'All' on tab switch.
    function renderFacets(){
      activeType = 'All';
      activeRatio = 'All';
      var entry = model[activeCat];
      var items = (entry && entry.items) || [];

      // --- Type row --- only chips whose keyword tokens match >=1 loaded tile; hide row if none do.
      // Mirrors the Ratio row + applyFilter's matcher: build each item's haystack exactly as
      // buildTile sets tile.dataset.search ((label + ratio + basename(key)).toLowerCase()), then keep
      // a chip only if SOME loaded item's haystack contains SOME of the chip's tokens. 'All' always
      // leads; a lone 'All' (no type matches the loaded window) is noise, so hide the whole row.
      if(typeRowEl){
        typeRowEl.innerHTML = '';
        var types = TYPE_FACETS[activeCat] || ['All'];
        var hays = items.map(function(it){
          return ((it && it.label || '') + ' ' + (it && it.ratio || '') + ' ' + basename(it && it.key || '')).toLowerCase();
        });
        var keptTypes = types.filter(function(t){
          if(t === 'All') return false;   // 'All' is added unconditionally below, never keyword-matched
          var toks = TYPE_KEYWORDS[t.toLowerCase()] || [t.toLowerCase()];
          return hays.some(function(hay){
            return toks.some(function(tok){ return hay.indexOf(tok) !== -1; });
          });
        });
        var showType = keptTypes.length > 0;   // only 'All' would remain -> row is noise
        typeRowEl.hidden = !showType;
        if(showType){
          ['All'].concat(keptTypes).forEach(function(t){
            typeRowEl.appendChild(makeFacetChip(t, (t === activeType), function(){ onFacetPick('type', t); }));
          });
        }
      }

      // --- Ratio row --- only chips that match >=1 loaded tile; hide row if none carry a ratio.
      if(ratioRowEl){
        ratioRowEl.innerHTML = '';
        var present = {};
        items.forEach(function(it){ if(it && it.ratio){ present[String(it.ratio)] = true; } });
        var anyRatio = Object.keys(present).length > 0;
        ratioRowEl.hidden = !anyRatio;
        if(anyRatio){
          RATIO_FACETS.forEach(function(r){
            if(r === 'All' || present[r]){   // never render a chip matching zero tiles
              ratioRowEl.appendChild(makeFacetChip(r, (r === activeRatio), function(){ onFacetPick('ratio', r); }));
            }
          });
        }
      }
    }

    function makeFacetChip(label, isActive, onClick){
      var chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'ff-dam-facet-chip';
      chip.textContent = label;
      chip.dataset.facet = label;
      chip.setAttribute('aria-pressed', isActive ? 'true' : 'false');
      chip.addEventListener('click', onClick);
      return chip;
    }

    function onFacetPick(which, label){
      if(which === 'type') activeType = label; else activeRatio = label;
      var row = (which === 'type') ? typeRowEl : ratioRowEl;
      if(row){
        row.querySelectorAll('.ff-dam-facet-chip').forEach(function(c){
          c.setAttribute('aria-pressed', (c.dataset.facet === label) ? 'true' : 'false');
        });
      }
      applyFilter();
    }

    // arrow-key navigation across the tab bar (WAI-ARIA tablist pattern) + roving tabindex.
    function onTabKeydown(e){
      var tabs = Array.prototype.slice.call(tablist.querySelectorAll('.ff-dam-tab'));
      var i = tabs.indexOf(e.currentTarget);
      if(i === -1) return;
      var next = -1;
      if(e.key === 'ArrowRight' || e.key === 'ArrowDown') next = (i+1) % tabs.length;
      else if(e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = (i-1+tabs.length) % tabs.length;
      else if(e.key === 'Home') next = 0;
      else if(e.key === 'End') next = tabs.length-1;
      else return;
      e.preventDefault();
      var cat = tabs[next].dataset.cat;
      selectTab(cat);
      try{ tabs[next].focus(); }catch(err){}
    }

    function selectTab(cat){
      if(!model[cat] || cat === activeCat){ if(cat===activeCat) return; }
      activeCat = cat;
      if(tablist){
        tablist.querySelectorAll('.ff-dam-tab').forEach(function(t){
          var on = (t.dataset.cat === cat);
          t.setAttribute('aria-selected', on ? 'true' : 'false');
          t.tabIndex = on ? 0 : -1;
        });
      }
      if(filterInput) filterInput.value = '';
      renderActiveTab();
    }

    // render tiles for the active tab into the grid, wired for lazy IntersectionObserver loading.
    function renderActiveTab(){
      if(!gridEl){ return; }
      clearGrid();
      renderSparse();
      renderFacets();
      var entry = model[activeCat];
      var items = (entry && entry.items) || [];
      if(!items.length){ var s=document.createElement('p'); s.className='ff-dam-status'; s.textContent=COPY_EMPTY; gridEl.appendChild(s); renderMore(); return; }

      io = makeObserver();
      var firstOption = true;
      items.forEach(function(it){
        var tile = buildTile(activeCat, it, firstOption);
        if(tile){ gridEl.appendChild(tile); if(io) io.observe(tile); firstOption = false; }
      });
      applyFilter();  // respect any residual filter value + active facets (usually reset after tab switch)
      renderMore();
    }

    // load-more affordance under the grid: a button when has_more, else the end-of-stack line.
    // Appended items re-run applyFilter + io.observe so lazy-load + facet/search state stay correct.
    function renderMore(){
      if(!moreEl) return;
      moreEl.innerHTML = '';
      var entry = model[activeCat];
      if(!entry){ return; }
      if(entry.has_more && typeof entry.next_offset === 'number'){
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'ff-dam-load-more';
        btn.textContent = COPY_LOAD_MORE;
        btn.addEventListener('click', function(){ loadMore(btn); });
        moreEl.appendChild(btn);
      } else if(entry.total > 0){
        var end = document.createElement('p');
        end.className = 'ff-dam-end';
        end.textContent = COPY_END;
        moreEl.appendChild(end);
      }
    }

    // fetch the next page for the active category, append items, and re-render the more line.
    function loadMore(btn){
      var cat = activeCat;
      var entry = model[cat];
      if(!LIB_ENDPOINT || !entry || !entry.has_more || typeof entry.next_offset !== 'number'){ return; }
      if(btn){ btn.disabled = true; btn.textContent = COPY_LOADING; }
      var controller = new AbortController();
      var timer = setTimeout(function(){ controller.abort(); }, DAM_TIMEOUT_MS || 12000);
      var url = LIB_ENDPOINT + '?category=' + encodeURIComponent(cat) + '&limit=' + PAGE_LIMIT + '&offset=' + entry.next_offset;
      fetch(url, {signal: controller.signal})
        .then(function(r){ if(!r.ok) throw new Error('library HTTP '+r.status); return r.json(); })
        .then(function(j){
          var cats = (j && j.categories) || {};
          var page = cats[cat] || {};
          var newItems = (page.items) || [];
          // tab may have changed while the fetch was in flight — only mutate the category we fetched.
          var target = model[cat];
          if(!target){ return; }
          target.items = target.items.concat(newItems);
          target.has_more = (page.has_more === true);
          target.next_offset = (typeof page.next_offset === 'number') ? page.next_offset : null;
          if(cat !== activeCat){ return; }   // user switched tabs; don't paint into the wrong grid
          // preserve the user's facet picks across the append (renderFacets resets them to 'All')
          var keepType = activeType;
          var keepRatio = activeRatio;
          // append only the new tiles (keep existing ones + their loaded state)
          newItems.forEach(function(it){
            var tile = buildTile(cat, it, false);
            if(tile){ gridEl.appendChild(tile); if(io) io.observe(tile); }
          });
          renderSparse();
          renderFacets();   // newly appended tiles may introduce ratios -> Ratio row can appear
          activeType = keepType; activeRatio = keepRatio;
          reassertActiveFacets();
          applyFilter();
          renderMore();
        })
        .catch(function(){ if(btn){ btn.disabled = false; btn.textContent = COPY_LOAD_MORE; } })
        .finally(function(){ clearTimeout(timer); });
    }

    // renderFacets resets active facets to 'All'; after a load-more we want the user's picks kept.
    // Re-apply the aria-pressed state to match the retained activeType/activeRatio.
    function reassertActiveFacets(){
      if(typeRowEl){ typeRowEl.querySelectorAll('.ff-dam-facet-chip').forEach(function(c){ c.setAttribute('aria-pressed', (c.dataset.facet === activeType) ? 'true' : 'false'); }); }
      if(ratioRowEl){ ratioRowEl.querySelectorAll('.ff-dam-facet-chip').forEach(function(c){ c.setAttribute('aria-pressed', (c.dataset.facet === activeRatio) ? 'true' : 'false'); }); }
    }

    // IntersectionObserver drives BOTH directions: load src on enter, drop src when far out of view.
    // rootMargin gives a generous pre-load band; a tile that leaves the band releases its bitmap.
    function makeObserver(){
      if(typeof IntersectionObserver === 'undefined') return null;
      return new IntersectionObserver(function(entries){
        entries.forEach(function(ent){
          var img = ent.target.querySelector('.ff-dam-thumb-img');
          if(!img) return;
          if(ent.isIntersecting){
            if(!img.getAttribute('src') && img.dataset.src){ img.src = img.dataset.src; }
          } else if(img.getAttribute('src')){
            img.src = '';  // scrolled far out — release memory; re-enter reloads from data-src
          }
        });
      }, { root: gridEl, rootMargin: '300px 0px', threshold: 0.01 });
    }

    // one grid tile: role=option, fixed-aspect frame, lazy <img> (data-src), ratio badge, label.
    // On img error we DO NOT hide — we reveal a branded kraft placeholder so a failed presign
    // still leaves a findable, labeled tile instead of collapsing into text-only "word salad".
    function buildTile(cat, it, isFirstOption){
      if(!it || !it.url) return null;
      var kind = (it.kind === 'video') ? 'video' : 'image';
      var label = it.label || basename(it.key) || 'asset';
      var ratio = it.ratio ? String(it.ratio) : '';
      var key = it.key || it.url;

      var tile = document.createElement('div');
      tile.className = 'ff-dam-tile';
      tile.setAttribute('role','option');
      tile.dataset.cat = cat;
      tile.dataset.key = key;
      // searchable haystack for the client filter (filename/label + ratio)
      tile.dataset.search = (label + ' ' + ratio + ' ' + basename(it.key)).toLowerCase();
      tile.dataset.ratio = ratio;   // exact ratio for the Ratio facet (empty when unknown)
      var selected = (selectedKey !== null && key === selectedKey);
      tile.setAttribute('aria-selected', selected ? 'true' : 'false');
      if(selected) tile.classList.add('is-selected');
      // roving tabindex across the listbox: exactly one option is tabbable
      tile.tabIndex = (isFirstOption && !selectedKey) || selected ? 0 : -1;
      // descriptive alt/label: "render, 9x16, <label>"
      var desc = (CAT_LABELS[cat] || cat) + (ratio ? ', ' + ratio : '') + ', ' + label;
      tile.setAttribute('aria-label', desc);

      var frame = document.createElement('span');
      frame.className = 'ff-dam-tile-frame';

      if(kind === 'video'){
        var vbox = document.createElement('span');
        vbox.className = 'ff-dam-thumb-video';
        vbox.textContent = 'VIDEO';
        frame.appendChild(vbox);
      } else {
        var img = document.createElement('img');
        img.className = 'ff-dam-thumb-img';
        img.alt = '';                      // decorative; the tile carries the aria-label
        img.decoding = 'async';
        img.width = 150; img.height = 150; // sized decode hint — kills layout shift
        img.dataset.src = it.url;          // IntersectionObserver assigns real src on enter
        img.addEventListener('error', function(){ showPlaceholder(frame, label); });
        frame.appendChild(img);
      }

      if(ratio){
        var badge = document.createElement('span');
        badge.className = 'ff-dam-ratio-badge';
        badge.textContent = ratio;
        frame.appendChild(badge);
      }

      var check = document.createElement('span');
      check.className = 'ff-dam-tile-check';
      check.setAttribute('aria-hidden','true');
      check.textContent = '\u2713';
      frame.appendChild(check);

      tile.appendChild(frame);

      var lab = document.createElement('span');
      lab.className = 'ff-dam-thumb-label';
      lab.textContent = label;
      tile.appendChild(lab);

      tile.addEventListener('click', function(){ chooseTile(tile, cat, it, kind, label); });
      tile.addEventListener('keydown', function(e){ onTileKeydown(e, tile, cat, it, kind, label); });
      return tile;
    }

    // branded fallback: replace the broken <img> with a kraft-tone block carrying the label.
    // Idempotent — only injects once even if error fires repeatedly.
    function showPlaceholder(frame, label){
      var img = frame.querySelector('.ff-dam-thumb-img');
      if(img){ img.remove(); }
      if(frame.querySelector('.ff-dam-thumb-ph')) return;
      var ph = document.createElement('span');
      ph.className = 'ff-dam-thumb-ph';
      ph.textContent = label || 'asset';
      // keep the badge/check overlays on top — insert placeholder as the first child
      frame.insertBefore(ph, frame.firstChild);
    }

    // keyboard on a tile: arrows move roving focus, Enter/Space selects+stages.
    function onTileKeydown(e, tile, cat, it, kind, label){
      if(e.key === 'Enter' || e.key === ' '){
        e.preventDefault();
        chooseTile(tile, cat, it, kind, label);
        return;
      }
      var visible = Array.prototype.slice.call(gridEl.querySelectorAll('.ff-dam-tile')).filter(function(t){ return !t.hidden; });
      var i = visible.indexOf(tile);
      if(i === -1) return;
      var next = -1;
      if(e.key === 'ArrowRight') next = Math.min(i+1, visible.length-1);
      else if(e.key === 'ArrowLeft') next = Math.max(i-1, 0);
      else if(e.key === 'ArrowDown') next = Math.min(i + gridColumns(), visible.length-1);
      else if(e.key === 'ArrowUp') next = Math.max(i - gridColumns(), 0);
      else if(e.key === 'Home') next = 0;
      else if(e.key === 'End') next = visible.length-1;
      else return;
      e.preventDefault();
      var target = visible[next];
      if(!target) return;
      visible.forEach(function(t){ t.tabIndex = -1; });
      target.tabIndex = 0;
      try{ target.focus(); }catch(err){}
    }

    // estimate columns from rendered tile widths so ArrowUp/Down move a visual row.
    function gridColumns(){
      if(!gridEl) return 1;
      var first = gridEl.querySelector('.ff-dam-tile');
      if(!first) return 1;
      var gw = gridEl.clientWidth || 1;
      var tw = first.offsetWidth || gw;
      return Math.max(1, Math.round(gw / tw));
    }

    // stage + mark selected (ring + checkmark + aria-selected). Reuses the existing stageDamAsset path.
    function chooseTile(tile, cat, it, kind, label){
      selectedKey = tile.dataset.key;
      if(gridEl){
        gridEl.querySelectorAll('.ff-dam-tile').forEach(function(t){
          var on = (t.dataset.key === selectedKey);
          t.classList.toggle('is-selected', on);
          t.setAttribute('aria-selected', on ? 'true' : 'false');
        });
      }
      stageDamAsset(cat, it, kind, label);
      renderFooter();
    }

    // client-side filter over the active tab's tiles: search box AND Type facet AND Ratio facet. No fetch.
    function applyFilter(){
      if(!gridEl) return;
      var q = (filterInput && filterInput.value ? filterInput.value : '').trim().toLowerCase();
      // Type facet -> list of lowercased keyword tokens (OR within a multi-token chip).
      var typeTokens = null;   // null means "All" (no type constraint)
      if(activeType && activeType !== 'All'){
        var key = activeType.toLowerCase();
        typeTokens = TYPE_KEYWORDS[key] || [key];
      }
      var ratioWant = (activeRatio && activeRatio !== 'All') ? activeRatio : null;
      var tiles = gridEl.querySelectorAll('.ff-dam-tile');
      var firstVisible = null;
      tiles.forEach(function(t){
        var hay = t.dataset.search || '';
        var show = true;
        if(q && hay.indexOf(q) === -1) show = false;
        if(show && typeTokens){
          var hit = typeTokens.some(function(tok){ return hay.indexOf(tok) !== -1; });
          if(!hit) show = false;
        }
        if(show && ratioWant){
          if((t.dataset.ratio || '') !== ratioWant) show = false;
        }
        // toggle the `hidden` attribute (not inline style.display): the grid used to carry
        // content-visibility:auto, which size/paint-contained the subtree so inline display:none
        // mutations never reflowed. `hidden` + `.ff-dam-tile[hidden]{display:none!important}` in CSS
        // makes the collapse robust regardless of any containment/flex interplay.
        t.hidden = !show;
        if(show && !firstVisible) firstVisible = t;
      });
      // keep roving tabindex valid: ensure one visible tile is tabbable
      var current = gridEl.querySelector('.ff-dam-tile[tabindex="0"]');
      if(!current || current.hidden){
        tiles.forEach(function(t){ t.tabIndex = -1; });
        if(firstVisible) firstVisible.tabIndex = 0;
      }
    }

    function focusFirstControl(){
      try{
        if(tablist){ var active = tablist.querySelector('.ff-dam-tab[aria-selected="true"]') || tablist.querySelector('.ff-dam-tab'); if(active){ active.focus(); return; } }
        if(closeBtn) closeBtn.focus();
      }catch(e){}
    }

    function basename(key){
      if(!key) return '';
      var s = String(key);
      var slash = s.lastIndexOf('/');
      return slash !== -1 ? s.slice(slash+1) : s;
    }

    // STAGE into the shared tray exactly like a local upload — reuse KODIAK_buildChip so the chip is identical.
    // De-dupe on source:'dam' && key. Presigned url used directly as the thumb <img> src (no blob: to revoke).
    function stageDamAsset(cat, it, kind, label){
      window.__userAssets = window.__userAssets || [];
      var key = it.key || it.url;
      // de-dupe: same DAM key already staged -> flash a note, do not stage twice
      var dup = window.__userAssets.some(function(a){ return a && a.source==='dam' && a.key===key; });
      if(dup){ flash('already added: ' + label); return; }

      var buildChip = window.KODIAK_buildChip;
      var docLabel  = window.KODIAK_docLabel;
      if(typeof buildChip !== 'function'){ flash('could not add: staging unavailable'); return; }

      var id = 'dam-asset-' + (window.__damSeq = (window.__damSeq||0) + 1);
      var rec = { id:id, name:label, kind:kind, source:'dam', key:key, url:it.url, category:cat };
      window.__userAssets.push(rec);
      try{ if(typeof window.__kodiakMarkDirty === 'function') window.__kodiakMarkDirty(); }catch(e){}

      var thumbNode;
      if(kind === 'image'){
        thumbNode = document.createElement('img');
        thumbNode.className = 'ff-pending-thumb';
        thumbNode.alt = '';
        thumbNode.onerror = function(){ this.style.display='none'; };
        thumbNode.src = it.url;                 // presigned GET, not a blob: — remove handler's revoke guard skips it
      } else {
        thumbNode = (typeof docLabel === 'function') ? docLabel('VIDEO') : null;
      }
      try{ buildChip(rec, thumbNode); }
      catch(e){
        // never leave a half-staged record if the chip build throws — roll back the push
        window.__userAssets = window.__userAssets.filter(function(a){ return a.id !== id; });
        flash('could not add: ' + label);
        return;
      }
      closePanel();
    }

    // wire triggers + keyboard/click-outside close
    trigger.addEventListener('click', openPanel);
    trigger.addEventListener('keydown', function(e){ if(e.key==='Enter'||e.key===' '){ e.preventDefault(); openPanel(); } });
    if(closeBtn) closeBtn.addEventListener('click', closePanel);
    backdrop.addEventListener('click', closePanel);
    document.addEventListener('keydown', function(e){
      if(e.key==='Escape' && !panel.hidden){ e.preventDefault(); closePanel(); }
    });
  })();

  // auto-grow the prompt textarea (google/firefly feel)
  if(briefEl){
    var grow = function(){ briefEl.style.height='auto'; briefEl.style.height=Math.min(briefEl.scrollHeight,160)+'px'; };
    briefEl.addEventListener('input', grow); setTimeout(grow, 100);
  }

  // Download asset pack — download the last generated hero as an ISO-labeled PNG.
  window.downloadAssetPack = function(opts){
    opts = opts || {};
    var status = document.getElementById('sampleStatus');
    // Real download requires a generated hero. showRealImage records it on window.__lastHeroUrl.
    if(!window.__lastHeroUrl){
      if(status) status.textContent = 'Generate a campaign first, then download.';
      return null;
    }
    var date = new Date().toISOString().slice(0,10).replace(/-/g,'');
    // Park City demo defaults — real selection state can override via opts.
    // Prefer the SKU the last Create actually requested so a fallback filename is honest about the
    // product, rather than always claiming the hardcoded "savory-waffles" demo stand-in.
    var product = opts.product || window.__requestedSku || 'savory-waffles';
    var region = opts.region || 'US-UT';
    var locality = opts.locality || 'park-city-84098';
    var channel = opts.channel || 'retailers';
    // Single composed hero image, so .png (not a multi-ratio .zip pack).
    var name = 'KODIAK-CAKES-' + product + '-' + region + '-' + locality + '-' + channel + '-' + date + '-v01.png';
    var url = window.__lastHeroUrl;
    // Direct anchor[download] against the presigned S3 URL — NO fetch()/blob().
    // fetch->blob tripped S3 CORS (no Access-Control-Allow-Origin on the presigned GET),
    // which failed the download entirely. A plain anchor click bypasses the CORS preflight/read path.
    // The browser saves rather than navigates when the presigned URL carries
    // Content-Disposition:attachment (set at signing time via ResponseContentDisposition).
    // Cross-origin note: the download="" filename attribute is ignored for cross-origin hrefs,
    // so the saved filename comes from Content-Disposition; download="" stays as the same-origin hint.
    var a = document.createElement('a');
    a.href = url;
    a.download = name;
    a.rel = 'noopener';
    document.body.appendChild(a); a.click(); a.remove();
    if(status) status.textContent = 'Downloaded ' + name;
    return name;
  };

  // Download Preview Pack — save ALL current preview images, not one. Offline: iterate canvases[]
  // (populated by the offline render(); {canvas,ratio,product}) via toDataURL. Hosted: iterate the
  // <img> tiles the hosted renderer (showRenderSet / showRealImage) painted into #preview and save
  // each presigned url. Falls back to the single-hero downloadAssetPack when neither source exists.
  // Guarded end to end; never throws into the click handler.
  window.downloadAllPreview = function(){
    var status = document.getElementById('sampleStatus');
    var date = new Date().toISOString().slice(0,10).replace(/-/g,'');
    var product = window.__requestedSku || 'savory-waffles';
    var region = 'US-UT', locality = 'park-city-84098', channel = 'retailers';
    // #204: the real ISO asset-pack zip. When a hosted set was rendered, its DAM
    // keys are on window.__lastPack — POST them to /assets/pack and save the
    // presigned zip (the button's data-mcp-description promise, kept). Any
    // failure falls through to the per-PNG flow below, so the button never dies.
    try{
      if(Array.isArray(window.__lastPack) && window.__lastPack.length){
        if(status) status.textContent = 'Building ISO asset-pack zip…';
        fetch('/assets/pack', {method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({files: window.__lastPack, product: product, region: region, locality: locality, channel: channel})})
        .then(function(resp){ if(!resp.ok) throw new Error('pack HTTP '+resp.status); return resp.json(); })
        .then(function(json){
          if(!json || !json.ok || !json.zip_url) throw new Error('pack missing zip_url');
          var a = document.createElement('a'); a.href = json.zip_url; a.download = json.zip_name || 'pack.zip';
          a.rel = 'noopener'; document.body.appendChild(a); a.click(); a.remove();
          if(status) status.textContent = 'Downloaded ' + (json.zip_name || 'asset pack') + ' (' + (json.count||0) + ' files)';
        })
        .catch(function(){ window.downloadAllPreviewPng(product, region, locality, channel, date, status); });
        return 'pack-requested';
      }
    }catch(e){}
    return window.downloadAllPreviewPng(product, region, locality, channel, date, status);
  };
  // Per-PNG fallback for downloadAllPreview (pre-#204 behavior, unchanged): save
  // each preview image individually with ISO per-file names.
  window.downloadAllPreviewPng = function(product, region, locality, channel, date, status){
    var saved = 0;
    var clickDL = function(href, dl){
      try{ var a=document.createElement('a'); a.href=href; if(dl) a.download=dl; a.rel='noopener'; document.body.appendChild(a); a.click(); a.remove(); saved++; }catch(e){}
    };
    // 1. offline canvases[] — real client-side pixels, name per ratio
    try{
      if(typeof canvases!=='undefined' && canvases && canvases.length){
        canvases.forEach(function(c){
          if(!c || !c.canvas) return;
          var nm = 'KODIAK-CAKES-'+(c.product||product)+'-'+region+'-'+locality+'-'+channel+'-'+(c.ratio||'1x1')+'-'+date+'-v01.png';
          try{ clickDL(c.canvas.toDataURL('image/png'), nm); }catch(e){}
        });
      }
    }catch(e){}
    // 2. hosted preview <img> tiles — presigned urls (cross-origin download attr ignored; Content-Disposition wins)
    if(!saved){
      try{
        var preview = document.getElementById('preview');
        var imgs = preview ? Array.prototype.slice.call(preview.querySelectorAll('img')) : [];
        imgs.forEach(function(img, i){
          var src = img && img.getAttribute('src'); if(!src) return;
          var nm = 'KODIAK-CAKES-'+product+'-'+region+'-'+locality+'-'+channel+'-'+(i+1)+'-'+date+'-v01.png';
          clickDL(src, nm);
        });
      }catch(e){}
    }
    // 3. nothing on screen — fall back to the single recorded hero, else prompt to generate
    if(!saved){
      if(window.__lastHeroUrl){ return window.downloadAssetPack(); }
      if(status) status.textContent = 'Generate a preview first, then download.';
      return 0;
    }
    if(status) status.textContent = 'Downloaded ' + saved + ' preview image' + (saved===1?'':'s');
    return saved;
  };
  // Download Preview Pack downloads ALL current preview images (was mis-bound to #downloadAll which is not in the DOM).
  document.getElementById('downloadPack')?.addEventListener('click', function(){ window.downloadAllPreview(); });
})();
