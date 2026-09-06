// --- Simplified Park City demo wiring: prompt chips, upload affordance, textarea auto-grow ---
(function(){
  // Firefly-style suggestion chips — populate the prompt, mark active, set theme
  var briefEl = document.getElementById('campaignBrief');
  var chipWrap = document.getElementById('promptChips');
  // Manual brief edit or product select clears the active theme (a chip is the only theme source).
  window.__clearActiveTheme = function(){
    window.__activeTheme = null;
    if(chipWrap) chipWrap.querySelectorAll('.ff-chip').forEach(function(c){ c.setAttribute('aria-pressed','false'); });
    togglePartnerMark(null);
  };
  // partner mark visibility — only for the US Ski & Snowboard chip; tasteful, not overused.
  function togglePartnerMark(theme){
    var mark = document.getElementById('ussPartnerMark');
    if(!mark) return;
    var on = theme === 'us-ski-snowboard';
    mark.hidden = !on;
    mark.style.display = on ? 'flex' : 'none';
  }
  if(chipWrap && briefEl){
    chipWrap.querySelectorAll('.ff-chip[data-brief]').forEach(function(chip){
      chip.addEventListener('click', function(){
        briefEl.value = chip.getAttribute('data-brief');
        // Chip is the active starting point: expose its theme slug for the generate IIFE.
        window.__activeTheme = chip.getAttribute('data-theme') || null;
        togglePartnerMark(window.__activeTheme);
        // dispatch input AFTER setting theme, and guard the input handler so the chip's own
        // programmatic input event does not immediately clear the theme it just set.
        window.__chipSettingBrief = true;
        briefEl.dispatchEvent(new Event('input', {bubbles:true}));
        window.__chipSettingBrief = false;
        chipWrap.querySelectorAll('.ff-chip').forEach(function(c){ c.setAttribute('aria-pressed', c===chip ? 'true':'false'); });
        briefEl.focus();
      });
    });
    // Manual textarea edit (not driven by a chip) clears the theme.
    briefEl.addEventListener('input', function(){
      if(window.__chipSettingBrief) return;
      window.__clearActiveTheme();
    });
  }
  // Selecting/deselecting a product overrides the theme too.
  document.getElementById('productChooser')?.addEventListener('change', function(e){
    if(e.target && e.target.classList && e.target.classList.contains('sku-check')) window.__clearActiveTheme();
  });

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
    var CAT_LABELS = { 'zac-efron':'Zac Efron', 'renders':'Renders', 'heroes':'Heroes', 'logos':'Logos' };
    var loaded = false;      // fetch once per session; re-open reuses rendered groups
    var lastFocus = null;    // element to restore focus to on close

    function flash(msg){ try{ if(flashEl) flashEl.textContent = String(msg||''); }catch(e){} }
    function setStatus(msg){
      try{ body.innerHTML = ''; var p=document.createElement('p'); p.className='ff-dam-status'; p.textContent=String(msg||''); body.appendChild(p); }catch(e){}
    }

    function openPanel(){
      lastFocus = document.activeElement;
      backdrop.hidden = false; panel.hidden = false;
      backdrop.classList.add('is-open'); panel.classList.add('is-open');
      trigger.setAttribute('aria-expanded','true');
      try{ closeBtn.focus(); }catch(e){}
      if(!loaded) loadLibrary();
    }
    function closePanel(){
      backdrop.classList.remove('is-open'); panel.classList.remove('is-open');
      backdrop.hidden = true; panel.hidden = true;
      trigger.setAttribute('aria-expanded','false');
      flash('');
      // return focus to the trigger (or the "+" if the trigger is gone)
      var back = (lastFocus && lastFocus.isConnected) ? lastFocus : trigger;
      try{ (back || trigger).focus(); }catch(e){}
    }

    // GET /assets/library (no category param -> all four groups). 6s AbortController timeout, mirrors localizeText.
    function loadLibrary(){
      if(!LIB_ENDPOINT){ renderUnavailable('Past assets unavailable offline.'); loaded = true; return; }
      setStatus('Loading past assets\u2026');
      var controller = new AbortController();
      var timer = setTimeout(function(){ controller.abort(); }, 6000);
      fetch(LIB_ENDPOINT + '?limit=60', {signal: controller.signal})
        .then(function(r){ if(!r.ok) throw new Error('library HTTP '+r.status); return r.json(); })
        .then(function(j){
          if(!j || j.enabled !== true){ renderUnavailable('Past assets unavailable offline.'); }
          else { renderLibrary(j); }
          loaded = true;
        })
        .catch(function(){ renderUnavailable('Past assets unavailable offline.'); loaded = true; })
        .finally(function(){ clearTimeout(timer); });
    }

    function renderUnavailable(msg){
      setStatus(msg || 'Past assets unavailable offline.');
    }

    // render four labeled groups from j.categories; each group is a content-visibility grid of thumbs.
    function renderLibrary(j){
      var cats = (j && j.categories) || {};
      var order = ['zac-efron','renders','heroes','logos'];
      // include any server-returned category not in the fixed order, defensively
      Object.keys(cats).forEach(function(k){ if(order.indexOf(k)===-1) order.push(k); });
      body.innerHTML = '';
      var rendered = 0;
      order.forEach(function(cat){
        var entry = cats[cat];
        if(!entry) return;
        var items = (entry && entry.items) || [];
        var total = (typeof entry.total === 'number') ? entry.total : items.length;
        var group = document.createElement('div');
        group.className = 'ff-dam-group';

        var head = document.createElement('div');
        head.className = 'ff-dam-group-head';
        var label = document.createElement('span');
        label.className = 'ff-dam-group-label';
        label.textContent = CAT_LABELS[cat] || cat;
        head.appendChild(label);
        if(total > items.length){
          var count = document.createElement('span');
          count.className = 'ff-dam-group-count';
          count.textContent = 'showing ' + items.length + ' of ' + total;
          head.appendChild(count);
        }
        group.appendChild(head);

        var grid = document.createElement('div');
        grid.className = 'ff-dam-grid';
        items.forEach(function(it){ var node = buildThumb(cat, it); if(node) grid.appendChild(node); });
        group.appendChild(grid);
        body.appendChild(group);
        rendered += 1;
      });
      if(rendered === 0){ renderUnavailable('No past assets found.'); }
    }

    // one thumbnail button: image -> lazy <img> (onerror hides broken thumb); video -> labeled placeholder box.
    function buildThumb(cat, it){
      if(!it || !it.url) return null;
      var kind = (it.kind === 'video') ? 'video' : 'image';
      var label = it.label || basename(it.key) || 'asset';
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'ff-dam-thumb';
      btn.setAttribute('aria-label', 'Add ' + label + ' to campaign');

      if(kind === 'video'){
        var vbox = document.createElement('span');
        vbox.className = 'ff-dam-thumb-video';
        vbox.textContent = 'VIDEO';
        btn.appendChild(vbox);
      } else {
        var img = document.createElement('img');
        img.className = 'ff-dam-thumb-img';
        img.loading = 'lazy';
        img.alt = '';
        img.onerror = function(){ this.style.display='none'; };
        img.src = it.url;
        btn.appendChild(img);
      }
      var lab = document.createElement('span');
      lab.className = 'ff-dam-thumb-label';
      lab.textContent = label;
      btn.appendChild(lab);

      btn.addEventListener('click', function(){ stageDamAsset(cat, it, kind, label); });
      return btn;
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
