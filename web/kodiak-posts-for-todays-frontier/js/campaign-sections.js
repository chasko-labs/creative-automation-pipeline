// === Generate Campaign + Campaign Assets (post-create) + product carousel fill — additive, guarded ===
// VANILLA-JS BEHAVIOR track. Mounts two sections at the "generate-campaign section mounts here" placeholder
// (after the .ff-forest treeline), wires the real full-campaign generate, and mirrors selected product images
// into #productCarousel. All guarded; never 500s the UI; prefers-reduced-motion respected for the pulse.
(function(){
  'use strict';

  // ---- one-time attention-pulse style (respects prefers-reduced-motion) ----
  function ensurePulseStyle(){
    if(document.getElementById('ffCampaignPulseCss')) return;
    var st = document.createElement('style');
    st.id = 'ffCampaignPulseCss';
    st.textContent =
      '@keyframes ffCampaignPulse{0%{box-shadow:0 0 0 0 rgba(232,83,14,.45)}70%{box-shadow:0 0 0 14px rgba(232,83,14,0)}100%{box-shadow:0 0 0 0 rgba(232,83,14,0)}}'+
      '.ff-campaign-pulse{animation:ffCampaignPulse 1.2s ease-out 2}'+
      '@media(prefers-reduced-motion:reduce){.ff-campaign-pulse{animation:none}}';
    document.head.appendChild(st);
  }

  // ---- build the two sections into the placeholder location ----
  // Generate Campaign is a COLLAPSED native <details> (same card + summary styling
  // as Output Preview via .preview-card) with a greyed-out marker while GATED:
  // the action button stays hidden until a preview exists to approve. A gated
  // toggle is refused with the message instead of failing silently.
  var GATED_MSG = 'generate campaign to preview and approve, then try again';
  function mountSections(){
    if(document.getElementById('generateCampaignSection')) return true;   // idempotent
    // anchor: the forest treeline divider that precedes the placeholder comment
    var forest = document.querySelector('.ff-forest');
    var wrap = document.createElement('div');
    wrap.innerHTML =
      '<details id="generateCampaignSection" class="ff-output ff-generate-campaign preview-card is-gated" data-gated="true">'+
        '<summary aria-labelledby="generateCampaignHeading"><span class="ff-stepnum" aria-hidden="true">6</span>'+
        '<span id="generateCampaignHeading" class="ff-output-heading">Generate Campaign</span>'+
        ' <span class="badge" id="generateCampaignLock">locked until preview</span></summary>'+
        '<p class="hint" id="generateCampaignHint">The full campaign unlocks after your first preview — every ratio, every platform, localized to your chosen scope.</p>'+
        '<div class="row" id="generateCampaignBtns" style="gap:10px;flex-wrap:wrap">'+
          '<button type="button" class="btn orange ff-campaign-primary" id="genFullCampaign" hidden>Generate full campaign</button>'+
        '</div>'+
        '<div class="hint" id="generateCampaignStatus" role="status" aria-live="polite"></div>'+
      '</details>'+
      '<section id="campaignAssetsSection" class="ff-output ff-campaign-assets" aria-labelledby="campaignAssetsHeading" hidden>'+
        '<h2 id="campaignAssetsHeading" class="ff-output-heading"><span class="ff-stepnum" aria-hidden="true">7</span> Campaign Assets Created</h2>'+
        '<div class="row" style="justify-content:flex-start"><button type="button" class="btn orange" id="downloadCampaignPackTop" data-mcp="download-campaign-pack">Download Campaign Pack</button></div>'+
        '<div class="ff-product-carousel" id="campaignAssetsCarousel" role="group" aria-label="Generated campaign assets" style="margin-top:var(--spacing-sm)"></div>'+
        '<div class="row" style="justify-content:flex-start;margin-top:var(--spacing-sm)"><button type="button" class="btn orange" id="downloadCampaignPackBottom" data-mcp="download-campaign-pack">Download Campaign Pack</button></div>'+
      '</section>';
    // insert right after the forest divider (the placeholder comment sits there); fallback to body append
    if(forest && forest.parentNode){
      var ref = forest.nextSibling;
      while(wrap.firstChild){ forest.parentNode.insertBefore(wrap.firstChild, ref); }
    } else {
      document.body.appendChild(wrap);
    }
    wireButtons();
    wireGate();
    return true;
  }

  // Gated toggles are refused: the disclosure stays collapsed while gated and the
  // lock badge pulses for attention (reduced-motion safe via the shared pulse CSS).
  function wireGate(){
    var sec = document.getElementById('generateCampaignSection');
    if(!sec || sec.__gateWired) return;
    sec.__gateWired = true;
    sec.addEventListener('toggle', function(){
      if(sec.getAttribute('data-gated') !== 'true') return;
      if(sec.open){
        sec.open = false;
        var status = document.getElementById('generateCampaignStatus');
        if(status) status.textContent = GATED_MSG;
        var lock = document.getElementById('generateCampaignLock');
        if(lock){ lock.classList.remove('ff-campaign-pulse'); void lock.offsetWidth; lock.classList.add('ff-campaign-pulse'); }
      }
    });
  }
  try{ window.KODIAK_GATED_MSG = GATED_MSG; }catch(e){}

  // ---- ungate + scroll + pulse when a preview becomes ready ----
  window.__kodiakRevealCampaign = function(){
    try{
      mountSections();
      var sec = document.getElementById('generateCampaignSection');
      if(!sec) return;
      if(sec.hidden){ sec.hidden = false; }
      // ungate: same card, now actionable — disclosure opens, button appears, hint flips to ready.
      try{ sec.open = true; }catch(e){}
      sec.setAttribute('data-gated', 'false');
      sec.classList.remove('is-gated');
      var lock = document.getElementById('generateCampaignLock');
      if(lock) lock.hidden = true;
      var btn = document.getElementById('genFullCampaign');
      if(btn) btn.hidden = false;
      var hint = document.getElementById('generateCampaignHint');
      if(hint) hint.textContent = 'Your preview is ready. Generate the full campaign — every ratio, every platform, localized to your chosen scope.';
      ensurePulseStyle();
      // scroll into center so the user never has to hunt; pulse for attention (reduced-motion => no anim)
      try{ sec.scrollIntoView({behavior:'smooth', block:'center'}); }catch(e){ try{ sec.scrollIntoView(); }catch(e2){} }
      sec.classList.remove('ff-campaign-pulse');
      // reflow so re-adding the class restarts the animation on a repeat preview
      void sec.offsetWidth;
      sec.classList.add('ff-campaign-pulse');
    }catch(e){ /* reveal must never break the generate flow */ }
  };

  // ---- the real full-campaign generate (scope distinction on the same /generate endpoint) ----
  var campaignRenders = [];   // last full-campaign renders[] for the download-pack buttons
  function selectedMarket(){ try{ return document.getElementById('locality')?.value || 'US-MW-PARKCITY-84098'; }catch(e){ return 'US-MW-PARKCITY-84098'; } }
  function selectedProductSlug(){
    // reuse the requested-sku the preview Create recorded; fall back to the flagship mapped handle
    try{ if(window.__requestedSku) return window.__requestedSku; }catch(e){}
    return 'buttermilk-power-cakes-flapjack-waffle-mix';
  }
  function currentBrief(){ try{ return (document.getElementById('campaignBrief')?.value || '').trim() || 'Keep It Wild — Nourishment for Today\u0027s Frontier'; }catch(e){ return 'Keep It Wild'; } }

  function renderCampaignCarousel(renders){
    var car = document.getElementById('campaignAssetsCarousel');
    if(!car) return;
    car.innerHTML = '';
    var date = new Date().toISOString().slice(0,10).replace(/-/g,'');
    var product = selectedProductSlug();
    (renders||[]).forEach(function(r, i){
      if(!r || !r.image_url) return;
      var slot = document.createElement('div');
      slot.className = 'ff-carousel-slot';
      slot.removeAttribute('aria-hidden');
      var img = document.createElement('img');
      img.src = r.image_url;
      img.loading = 'lazy';
      img.alt = 'Campaign asset ' + (r.ratio ? String(r.ratio).replace('x',':') : '');
      slot.appendChild(img);
      // per-asset download link: one real user click per file, so each download
      // carries its own gesture. Browsers block multiple programmatic downloads
      // from a single click (multi-download governor) — the pack button cannot
      // reliably deliver all four, but four individual links always can.
      var dl = document.createElement('a');
      dl.href = r.image_url;
      dl.download = 'KODIAK-CAKES-'+product+'-campaign-'+(r.ratio||(i+1))+'-'+date+'-v01.png';
      dl.className = 'btn ghost ff-asset-download';
      dl.setAttribute('data-mcp', 'download-campaign-asset');
      dl.textContent = 'Download ' + (r.ratio ? String(r.ratio).replace('x',':') : ('asset ' + (i+1)));
      slot.appendChild(dl);
      car.appendChild(slot);
    });
  }

  // Download Campaign Pack (#242) — one click, one ISO zip via the #204 endpoint.
  // POSTs the campaign renders' DAM keys (+ copy sidecars where present) to
  // /assets/pack and saves the single presigned zip. Browsers cap automatic
  // multi-downloads, which is why the old per-file loop saved 1 photo instead
  // of 4. Falls back to the per-file loop only when no DAM keys exist.
  window.downloadCampaignPack = function(){
    var status = document.getElementById('generateCampaignStatus');
    if(!campaignRenders.length){ if(status) status.textContent = 'Generate a campaign first, then download the pack.'; return 0; }
    var product = selectedProductSlug();
    var keyed = campaignRenders.filter(function(r){ return r && r.s3_uri; });
    if(keyed.length){
      var files = keyed.map(function(r){ return {s3_uri: r.s3_uri, ratio: r.ratio || '1x1'}; });
      var extras = [];
      try{
        var sc = window.__lastCampaignSidecar || {};
        if(sc.txt) extras.push({name: 'copy.txt', text: String(sc.txt).slice(0, 65536)});
        if(sc.csv) extras.push({name: 'copy.csv', text: String(sc.csv).slice(0, 65536)});
      }catch(e){}
      if(status) status.textContent = 'Building campaign pack zip…';
      fetch('/assets/pack', {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({files: files, extras: extras, product: product, channel: 'campaign'})})
      .then(function(resp){ if(!resp.ok) throw new Error('pack HTTP '+resp.status); return resp.json(); })
      .then(function(json){
        if(!json || !json.ok || !json.zip_url) throw new Error('pack missing zip_url');
        var a = document.createElement('a'); a.href = json.zip_url; a.download = json.zip_name || 'pack.zip';
        a.rel = 'noopener'; document.body.appendChild(a); a.click(); a.remove();
        if(status) status.textContent = 'Downloaded ' + (json.zip_name || 'campaign pack') + ' (' + (json.count||0) + ' files)';
      })
      .catch(function(){ window.downloadCampaignPackPng(product, status); });
      return 'pack-requested';
    }
    return window.downloadCampaignPackPng(product, status);
  };
  // Per-file fallback (pre-#242 behavior): save each campaign render individually.
  window.downloadCampaignPackPng = function(product, status){
    var date = new Date().toISOString().slice(0,10).replace(/-/g,'');
    var saved = 0;
    campaignRenders.forEach(function(r, i){
      if(!r || !r.image_url) return;
      try{
        var nm = 'KODIAK-CAKES-'+product+'-campaign-'+(r.ratio||(i+1))+'-'+date+'-v01.png';
        var a = document.createElement('a'); a.href = r.image_url; a.download = nm; a.rel='noopener';
        document.body.appendChild(a); a.click(); a.remove(); saved++;
      }catch(e){}
    });
    if(status) status.textContent = 'Downloaded ' + saved + ' campaign asset' + (saved===1?'':'s');
    return saved;
  };

  function setCampaignBtnsDisabled(d){
    var b = document.getElementById('genFullCampaign');
    if(b) b.disabled = d;
  }

  async function runCampaign(){
    // scope is chosen up-front in the scope-first segmented control (window.__campaignScope);
    // default to 'local' if the control has not initialized for any reason.
    var scope = window.__campaignScope || 'local';
    var status = document.getElementById('generateCampaignStatus');
    var isLocal = (location.protocol==='file:') || ['127.0.0.1','localhost'].includes(location.hostname);
    if(isLocal){
      if(status) status.textContent = 'Full campaign generate needs the hosted backend — offline shows the preview only.';
      return;
    }
    setCampaignBtnsDisabled(true);
    if(status) status.textContent = 'Generating full campaign (' + scope + ')\u2026 up to ~90s';
    var controller = new AbortController();
    var timeoutId = setTimeout(function(){ controller.abort(); }, 100000);
    try{
      // staged DAM pick rides as the seed (same contract as the preview path above).
      var stagedKey = null;
      try{ var staged = (window.__userAssets||[]).filter(function(a){ return a && a.source==='dam' && a.key; }); if(staged.length) stagedKey = staged[staged.length-1].key; }catch(e){}
      var body = {
        prompt: currentBrief(),
        market: selectedMarket(),
        product: selectedProductSlug(),
        scope: scope,        // nationwide | nationwide-localized | local
        mode: 'full'         // full 3/4-size + localization + platform-copy path (backend FULL_MODE)
      };
      // retailer / creative direction (#245): the active chip theme rides as a
      // first-class field (same contract as the preview Create path) so the
      // backend can direct image + copy at the retailer. Absent = generic.
      try{ var activeTheme = window.__activeTheme || null; if(activeTheme) body.theme = activeTheme; }catch(e){}
      if(stagedKey) body.seed_key = stagedKey;
      var resp = await fetch('/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body), signal: controller.signal});
      if(!resp.ok) throw new Error('backend returned HTTP ' + resp.status);
      var json;
      try{ json = await resp.json(); }catch(pe){ throw new Error('malformed response from backend'); }
      var renders = Array.isArray(json.renders) && json.renders.length ? json.renders
                    : (json.image_url ? [{image_url: json.image_url, ratio: json.ratio || '1x1', w: json.w, h: json.h}] : []);
      if(!renders.length) throw new Error('response missing renders');
      campaignRenders = renders;
      // pack download (#242) needs the copy sidecars too — record them alongside.
      try{ window.__lastCampaignSidecar = (json.copy_sidecar && typeof json.copy_sidecar==='object') ? json.copy_sidecar : null; }catch(e){}
      // reuse the preview renderer for the on-screen result when available
      try{ if(typeof window.KODIAK_showRenderSet==='function' && Array.isArray(json.renders) && json.renders.length){ window.KODIAK_showRenderSet(json.renders, {source: json.source, provenance: json.provenance}); } }catch(e){}
      renderCampaignCarousel(renders);
      // campaign copy panel (#241): headline + brief + language variants, same
      // rules as the preview captions; downloadable in the pack (#242 zip).
      try{
        var cpHeadline = (json.provenance && json.provenance.copy_headline) || null;
        window.__lastCampaignHeadline = cpHeadline;
        paintCampaignCopy(cpHeadline, currentBrief(), selectedMarket());
      }catch(e){}
      var assets = document.getElementById('campaignAssetsSection');
      if(assets && assets.hidden){ assets.hidden = false; }
      try{ assets.scrollIntoView({behavior:'smooth', block:'start'}); }catch(e){}
      if(status) status.textContent = 'Campaign created — ' + renders.length + ' asset' + (renders.length===1?'':'s') + ' from ' + (json.source || 'Nova Pro') + ' (' + scope + ')';
    }catch(err){
      if(status) status.textContent = (err && err.name==='AbortError')
        ? 'Campaign generate timed out — reconnect and try again.'
        : 'Could not generate the full campaign — ' + (err && err.message ? err.message : 'try again') + '.';
    }finally{
      clearTimeout(timeoutId);
      setCampaignBtnsDisabled(false);
    }
  }

  // Replace-not-append (#243): a new preview generate clears the whole prior
  // campaign (renders, pack keys, sidecar, carousel DOM, assets section, status)
  // BEFORE painting, so stale assets never persist under fresh output. Exposed
  // for the preview Create path; guarded end to end, never throws.
  window.KODIAK_resetCampaign = function(){
    try{ campaignRenders = []; }catch(e){}
    try{ window.__lastCampaignSidecar = null; }catch(e){}
    try{ window.__lastCampaignHeadline = null; }catch(e){}
    try{ var car = document.getElementById('campaignAssetsCarousel'); if(car) car.innerHTML = ''; }catch(e){}
    try{ var cp = document.getElementById('campaignCopyPanel'); if(cp && cp.parentNode) cp.parentNode.removeChild(cp); }catch(e){}
    try{ var assets = document.getElementById('campaignAssetsSection'); if(assets) assets.hidden = true; }catch(e){}
    try{ var st = document.getElementById('generateCampaignStatus'); if(st) st.textContent = ''; }catch(e){}
    return true;
  };

  function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]; }); }

  // Campaign copy (#241): the thing you ship needs words with it. Paints the
  // campaign headline + brief plus the market's top-language variants under the
  // assets, on the SAME rules as the preview tile captions — EN source first,
  // machine langs swap live /localize text in after paint, community-review
  // languages stay EN-source with a badge (never machine-translated), offline
  // shows an honest pending note. Downloadable via the pack (#242 zip).
  // Exposed as KODIAK_paintCampaignCopy for tests; guarded, never throws.
  function paintCampaignCopy(headline, brief, market){
    try{
      var old = document.getElementById('campaignCopyPanel');
      if(old && old.parentNode) old.parentNode.removeChild(old);
      // brand-floor / fallback paths carry no composed headline — the brief is
      // the copy source then, same rule as build_copy_sidecar server-side.
      // copy always ships, even when the image is clean.
      if(!headline) headline = brief;
      if(!headline) return false;
      var assets = document.getElementById('campaignAssetsSection');
      if(!assets) return false;
      var langs = [];
      try{ if(typeof window.KODIAK_marketLangsFor==='function') langs = window.KODIAK_marketLangsFor(market) || []; }catch(e){ langs = []; }
      var rows = ['<div class="loc-line" lang="en" data-provider="source"><span class="loc-langtag">EN</span><span class="loc-text">'+esc(headline)+'</span></div>'];
      if(brief) rows.push('<div class="loc-line loc-brief" data-provider="source"><span class="loc-langtag">brief</span><span class="loc-text">'+esc(brief)+'</span></div>');
      var jobs = [];
      langs.forEach(function(l, i){
        if(!l) return;
        var code = String(l.translate_code || l.lang_code || '').toLowerCase();
        var name = l.lang_name || code;
        if(!code) return;
        var community = false;
        try{ if(typeof window.KODIAK_isCommunityReview==='function') community = !!window.KODIAK_isCommunityReview(l, code); }catch(e){}
        if(community){
          rows.push('<div class="loc-line" lang="'+esc(code)+'" data-provider="community-review"><span class="loc-langtag">'+esc(name)+'</span><span class="loc-text">'+esc(headline)+'</span> <span class="loc-review">community review</span></div>');
        } else if(typeof window.KODIAK_localizeText==='function'){
          var rowId = 'campcopy-'+i+'-'+code;
          rows.push('<div class="loc-line" lang="'+esc(code)+'" data-provider="pending-live" id="'+rowId+'"><span class="loc-langtag">'+esc(name)+'</span><span class="loc-text">'+esc(headline)+'</span></div>');
          jobs.push({rowId: rowId, code: code});
        } else {
          rows.push('<div class="loc-line" lang="'+esc(code)+'" data-provider="pending"><span class="loc-langtag">'+esc(name)+'</span><span class="loc-text">translation pending</span></div>');
        }
      });
      var panel = document.createElement('div');
      panel.id = 'campaignCopyPanel';
      panel.className = 'platform-copy';
      panel.innerHTML = '<div class="pc-head">Campaign copy</div>' + rows.join('');
      var car = document.getElementById('campaignAssetsCarousel');
      if(car && car.parentNode) car.parentNode.insertBefore(panel, car.nextSibling);
      else assets.appendChild(panel);
      jobs.forEach(function(j){
        try{
          window.KODIAK_localizeText(headline, market, j.code).then(function(t){
            if(typeof t!=='string' || !t.trim()) return;
            var el = document.getElementById(j.rowId);
            if(!el) return;
            el.setAttribute('data-provider', 'live');
            var tx = el.querySelector ? el.querySelector('.loc-text') : null;
            if(tx) tx.textContent = t;
          });
        }catch(e){}
      });
      return true;
    }catch(e){ return false; }
  }
  try{ window.KODIAK_paintCampaignCopy = paintCampaignCopy; }catch(e){}

  function wireButtons(){
    var gen = document.getElementById('genFullCampaign');
    if(gen && !gen.__wired){ gen.__wired = true; gen.addEventListener('click', function(){ runCampaign(); }); }
    var dt = document.getElementById('downloadCampaignPackTop');
    if(dt && !dt.__wired){ dt.__wired = true; dt.addEventListener('click', function(){ window.downloadCampaignPack(); }); }
    var db = document.getElementById('downloadCampaignPackBottom');
    if(db && !db.__wired){ db.__wired = true; db.addEventListener('click', function(){ window.downloadCampaignPack(); }); }
  }

  // ---- Item 8: product carousel fill — mirror selected product images into #productCarousel slots ----
  function repaintProductCarousel(){
    try{
      var car = document.getElementById('productCarousel');
      if(!car) return;
      var checked = Array.prototype.slice.call(document.querySelectorAll('#productChooser .sku-check:checked')).map(function(c){ return c.value; });
      var cat = (window.skuCatalog && window.skuCatalog.length) ? window.skuCatalog : [];
      // resolve up to 3 image urls from the selected products (catalog images[0], else hidden host thumb)
      var imgs = [];
      checked.slice(0,3).forEach(function(name){
        var hit = cat.find(function(p){ return p && p.name===name; });
        var src = hit && hit.images && hit.images[0] ? hit.images[0] : '';
        if(!src){
          // fall back to the checkbox row thumb the chooser painted, if present
          try{ var box = Array.prototype.slice.call(document.querySelectorAll('#productChooser .sku-check')).find(function(b){ return b.value===name; });
            var thumb = box && box.parentNode ? box.parentNode.querySelector('img') : null; if(thumb && thumb.src) src = thumb.src; }catch(e){}
        }
        if(src) imgs.push({src:src, name:name});
      });
      // no checked products -> hide the shell entirely (hollow dashed squares help
      // nobody); it reappears with the first checked product. Inline style beats the
      // .ff-product-carousel display:flex rule, which would override [hidden].
      car.style.display = imgs.length ? '' : 'none';
      // repaint exactly 3 slots: filled first, dashed placeholders after (mirror only, no selection change)
      car.innerHTML = '';
      for(var i=0;i<3;i++){
        var slot = document.createElement('div');
        slot.className = 'ff-carousel-slot';
        if(imgs[i]){
          var im = document.createElement('img');
          im.src = imgs[i].src; im.loading = 'lazy'; im.alt = imgs[i].name;
          im.setAttribute('crossorigin','anonymous');
          im.onerror = function(){ this.style.display='none'; };
          slot.appendChild(im);
        } else {
          slot.setAttribute('aria-hidden','true');
        }
        car.appendChild(slot);
      }
    }catch(e){ /* carousel fill is a visual mirror — never break selection logic */ }
  }
  // repaint on any sku-check change (delegation, survives chooser innerHTML swaps + Random 3)
  document.addEventListener('change', function(e){ if(e.target && e.target.classList && e.target.classList.contains('sku-check')) repaintProductCarousel(); });
  document.getElementById('randomProducts')?.addEventListener('click', function(){ setTimeout(repaintProductCarousel, 0); });

  // ---- init ----
  function init(){
    mountSections();
    // catalog paints asynchronously (~900ms) — repaint the carousel after it settles + once more later
    setTimeout(repaintProductCarousel, 950);
    setTimeout(repaintProductCarousel, 1600);
  }
  if(document.readyState==='loading'){ document.addEventListener('DOMContentLoaded', init); }
  else { init(); }
})();
