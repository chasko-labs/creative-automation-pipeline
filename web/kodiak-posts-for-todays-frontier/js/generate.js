// --- New campaign UI: products up to 3 + random, real employees, local flavor derived, single generate ---
(function(){
  let skuCatalog=[]; async function loadCatalog(){ const urls=["data/products/kodiak-full-catalog.json","../../data/products/kodiak-full-catalog.json","./data/products/kodiak-full-catalog.json","/data/products/kodiak-full-catalog.json"]; for(const url of urls){ try{ const r=await fetch(url); if(r.ok){ const d=await r.json(); if(d.products?.length) { console.log('[catalog] loaded',d.products.length,'from',url); return d.products; } }}catch(e){} } console.warn('[catalog] failed all urls'); return []; } loadCatalog().then(products=>{ skuCatalog=products||[]; const chooser=document.getElementById("productChooser"); if(!chooser) return;
    // Single owner of #productChooser. If the catalog JSON loaded, render rich checkboxes (image + price).
    // If it failed/empty, DO NOT leave the chooser blank — fall back to the hardcoded skuList so a checkbox
    // always exists. Selection handlers are bound once by the static block below via delegation on the element,
    // so they keep working no matter which branch paints.
    const preserveChecked=()=>new Set(Array.from(chooser.querySelectorAll('.sku-check:checked')).map(c=>c.value));
    if(skuCatalog.length){ window.skuCatalog=skuCatalog; skuList=skuCatalog.map(p=>p.name);
      const render=(filter="")=>{ const kept=preserveChecked(); const q=(filter||"").toLowerCase(); let filtered=skuCatalog.filter(p=>!q||(p.name||"").toLowerCase().includes(q)||(p.handle||"").toLowerCase().includes(q)||(p.category||"").toLowerCase().includes(q)).slice(0,12);
        // never blank the chooser: a no-match filter (e.g. a brief keyword) falls back to the first 12 SKUs
        if(!filtered.length) filtered=skuCatalog.slice(0,12);
        chooser.innerHTML=filtered.map(p=>`<label class="sku-pick"><input type="checkbox" value="${p.name}" class="sku-check"${kept.has(p.name)?" checked":""}> <img src="${p.images?.[0]||""}" onerror="this.classList.add('is-hidden')" crossorigin="anonymous" loading="lazy"><span>${p.name}<br><span class="sku-sub">${p.category} • $${p.price_usd||""}</span></span></label>`).join(""); const hint2=document.getElementById('skuHint'); if(hint2) hint2.textContent=`${skuCatalog.length} SKUs loaded — ${kept.size} / 3 selected`; if(window.KODIAK_SCORECARDS) window.KODIAK_SCORECARDS.render(); try{ if(typeof window.__syncProductPopover==='function') window.__syncProductPopover(); }catch(e){} };
      render(""); document.getElementById("productSearch")?.addEventListener("input",e=>render(e.target.value)); document.getElementById("campaignBrief")?.addEventListener("input",e=>{ const v=e.target.value.toLowerCase().split(/\s+/).filter(Boolean).pop(); if(v&&v.length>2) render(v); });
    } else { console.warn('[catalog] empty after fetch — falling back to static skuList checkboxes');
      // Guaranteed non-empty fallback. window.skuCatalog is seeded from skuList names so slugify() has a
      // consistent lookup path (no .handle here — slugify's lowercase/hyphenate path yields the real handle,
      // e.g. "Blueberry Muffin Mix" -> "blueberry-muffin-mix").
      window.skuCatalog=skuList.map(n=>({name:n}));
      if(!chooser.querySelector('.sku-check')){ chooser.innerHTML=skuList.slice(0,12).map(n=>`<label class="sku-pick"><input type="checkbox" value="${n}" class="sku-check"> ${n}</label>`).join(''); }
      const hint2=document.getElementById('skuHint'); if(hint2) hint2.textContent=`${skuList.length} SKUs (offline) — 0 / 3 selected`; if(window.KODIAK_SCORECARDS) window.KODIAK_SCORECARDS.render();
    }
  });
let skuList = [
    "Banana Muffin and Quick Bread Mix","Blueberry Muffin Mix","Chocolate Chip Muffin Mix",
    "Buttermilk Power Cakes Flapjack & Waffle Mix","Cinnamon Oat Power Cakes","Dark Chocolate Power Cakes",
    "Oatmeal Chocolate Chip Power Cup","Blueberry Honey Frontier Cakes","Pumpkin Power Cakes",
    "Chocolate Almond Trail Bars","Cinnamon Oat & Apple Breakfast Bars","Protein Oatmeal Packets",
    "Kodiak Cakes Blueberry Lemon Muffin Mix","KODIAK POWER CUPS® Protein Oatmeal Cup","KODIAK CAKES® Cheddar Jalapeno Drop Biscuits",
    "Savory Waffles — Regional","Waffle Ice Cream Sandwiches","Protein Biscuits"
  ];
  const employees = [
    "Aaron Robinson — Senior Director of Brand Management — Park City, Utah (Home Office)",
    "Madison Roberts — Director of Brand Management — Park City, Utah",
    "Rebecka Fitzkee — Director of Brand Management — Park City, Utah",
    "Eli Curtis — Brand Manager — Park City, Utah",
    "Sarah Brooks — Product Marketing Manager — Park City, Utah",
    "Emily Pearson — Associate Brand Manager — Park City, Utah",
    "Elizabeth Hilgemann — Consumer Insights Manager — Park City, Utah",
    "Nina Palazzolo — Senior Category Insights Manager — Salt Lake City Area",
    "Brett Miller — VP of Creative — Park City, Utah",
    "Arnoldo Romo — Design Director — Salt Lake City Area",
    "Sam Featherstone — Associate Creative Director, Content — Park City, Utah",
    "Amber Kirkham — Senior Project Analyst, Marketing Operations — Park City, Utah",
    "Cory Bayers — Chief Marketing Officer — Park City and Remote",
    "Casi Reichardt — Head of Channel Marketing — Park City, Utah",
    "John Oja — Director of eCommerce — Salt Lake City and Remote",
    "Ali Fluke — Associate Director, Shopper Marketing — Chicago, IL",
    "Ashley La Barbera — VP of Sales — Minneapolis Area",
    "Quin Taylor — Field Marketing Specialist — Denver, CO and Austin, TX"
  ];
  const chooser = document.getElementById('productChooser');
  const hint = document.getElementById('skuHint');
  if(chooser){
    // Synchronous baseline: paint skuList checkboxes immediately so #productChooser is never empty before the
    // async catalog resolves. The catalog .then above is the single owner afterward — it upgrades these to rich
    // rows on success or re-affirms skuList on empty. The change/random handlers below bind to the chooser
    // ELEMENT (event delegation), so they keep working across every innerHTML swap regardless of which renderer paints.
    chooser.innerHTML = skuList.slice(0,12).map((n,i)=>`<label class="sku-pick"><input type="checkbox" value="${n}" class="sku-check"> ${n}</label>`).join('');
    const checks = ()=> Array.from(chooser.querySelectorAll('.sku-check:checked'));
    chooser.addEventListener('change', (e)=>{
      if(e.target.classList.contains('sku-check')){
        const c = checks();
        if(c.length > 3){ e.target.checked=false; hint.textContent = 'Max 3 — uncheck one first'; hint.style.color='#B51E14'; return; }
        hint.textContent = c.length + ' / 3 selected — empty = random 3 on generate';
        hint.style.color = '';
        updateLocalFlavor();
      }
    });
    document.getElementById('randomProducts')?.addEventListener('click', ()=>{
      const boxes = Array.from(chooser.querySelectorAll('.sku-check'));
      boxes.forEach(b=>b.checked=false);
      const shuffled = [...boxes].sort(()=>0.5-Math.random()).slice(0,3);
      shuffled.forEach(b=>b.checked=true);
      hint.textContent = '3 / 3 selected (random)';
    });
  }
  const aud = document.getElementById('audienceSelect');
  if(aud){
    aud.innerHTML = employees.map(e=>`<option>${e}</option>`).join('');
  }
  // Local flavor derived by locale (not selectable) — season & source
  const flavorMap = {
    "US-CA-PESCADERO": "Pescadero farm stands — Castroville artichokes <b>Mar–Jun</b> + Marin goat cheese <b>Feb–Jun</b> at Half Moon Bay/Santa Cruz stands",
    "US-WA-NEAHBAY": "Neah Bay harbor — Makah salmon <b>May–Sep</b> + huckleberry <b>Aug</b> at Washburn’s General Store & Makah Days",
    "US-MW-PARKCITY-84098": "Wasatch Back — Jensen Farms peaches + Copper Moose rhubarb compote <b>Jun–Sep</b> at Park City Farmers Market (Canyons Village)",
    "US-SW-LASCRUCES": "Hatch green chile <b>Aug–Sep roast season</b> — roasted by the bushel, Organ Mountains bench, Albertsons Las Cruces",
    "US-UT-KAMASVALLEY": "Kamas Valley — Oakley grass-fed beef + Ballerina Farm butter <b>year-round</b> at Oakley Rodeo Grounds market",
    "_default": "Seasonal frontier flavor — protein that loves the local harvest."
  };
  window.updateLocalFlavor = function(){
    const sel = document.getElementById('useLocationBtn')?.dataset.market || (typeof places!=='undefined' && places[0]?.market) || 'US-MW-PARKCITY-84098';
    // Try to get from location-aware island's selected market (haversine)
    let market = sel;
    try{
      const loc = document.getElementById('locality')?.value || sel;
      if(loc) market = loc;
    }catch(e){}
    // Season-aware engine first (every market x every season resolves a line).
    // Artisanal flavorMap second, places table third, generic only when unknown.
    let txt = null;
    try{
      var season = null;
      try{ season = (typeof window.__activeSeason !== 'undefined') ? window.__activeSeason : document.getElementById('seasonalSelect')?.value || null; }catch(se){ season = null; }
      if(typeof window.seasonFlavorFor === 'function'){
        var r = window.seasonFlavorFor(market, season);
        if(r && r.text) txt = r.text;
      }
    }catch(e){}
    if(!txt) txt = flavorMap[market];
    if(!txt){
      try{
        const p = (typeof places!=='undefined' ? places : []).find(function(x){ return x && x.market === market; });
        if(p && (p.message || p.cue)) txt = (p.place ? p.place + ' — ' : '') + (p.message || p.cue);
      }catch(e){}
    }
    const el = document.getElementById('localFlavorText');
    if(el) el.textContent = txt || flavorMap._default;
  };
  setTimeout(updateLocalFlavor, 800);
  document.addEventListener('change', e=>{ if(e.target?.id==='locality' || e.target?.id==='seasonalSelect') updateLocalFlavor(); });

  // === Platform -> ratio -> dimension matrix ===
  // Authoritative source: data/platforms/platform-matrix.json (offline-tolerant multi-path fetch,
  // same pattern as market-languages.json). Inline fallback below keeps it working file:// offline.
  // module-scoped escape — used by the matrix + platform-copy renderers (the click-handler has its own local one too)
  const escapeHtml = (s)=> String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const PLATFORM_LABELS = {
    facebook:'Facebook', instagram:'Instagram', linkedin:'LinkedIn',
    pinterest:'Pinterest', tiktok:'TikTok', x:'X', youtube:'YouTube', blog:'Blog'
  };
  // Inline fallback — ratio order matches the summary copy (1x1, then portrait, then vertical, then landscape).
  const PLATFORM_MATRIX_FALLBACK = {
    '1x1':  {label:'Square',    w:1080, h:1080, platforms:['facebook','instagram','x','linkedin','pinterest']},
    '4x5':  {label:'Portrait',  w:1080, h:1350, platforms:['instagram','facebook']},
    '9x16': {label:'Vertical',  w:1080, h:1920, platforms:['instagram','facebook','tiktok','youtube','pinterest']},
    '16x9': {label:'Landscape', w:1920, h:1080, platforms:['youtube','linkedin','x','facebook']},
    'blog': {label:'Blog', w:1200, h:630, platforms:['blog']}
  };
  // live matrix — starts as the fallback, upgraded by the fetched JSON when reachable.
  let platformMatrix = PLATFORM_MATRIX_FALLBACK;
  const platformNames = (slugs)=> (slugs||[]).map(s=>PLATFORM_LABELS[s] || s);
  (async ()=>{
    let matrixLoaded = false;
    for(const url of ['data/platforms/platform-matrix.json','../../data/platforms/platform-matrix.json','./data/platforms/platform-matrix.json']){
      try{
        const r = await fetch(url);
        if(r.ok){
          // isolate the parse: a 200 with a malformed body must not abort the loop or throw uncaught
          let d = null;
          try{ d = await r.json(); }catch(pe){ console.warn('[platform-matrix] malformed JSON at', url, pe && pe.message); continue; }
          if(d && d.ratios && Object.keys(d.ratios).length){
            platformMatrix = d.ratios;
            matrixLoaded = true;
            console.log('[platform-matrix] loaded', Object.keys(d.ratios).length, 'ratios from', url);
            // if the matrix explainer is already on-screen, refresh it in place
            try{ renderPlatformMatrix(); }catch(e){}
            break;
          }
        }
      }catch(e){}
    }
    // all sources missed — the working PLATFORM_MATRIX_FALLBACK stays in effect (no blank surface).
    // only surface a note if the matrix explainer is actually on-screen, so an offline file:// open stays quiet.
    if(!matrixLoaded){
      try{
        const mx = document.getElementById('platformMatrix');
        if(mx && !document.getElementById('platformMatrixNote')){
          const n = document.createElement('div');
          n.id = 'platformMatrixNote'; n.className = 'ff-inline-error';
          n.textContent = 'Showing built-in platform sizes (live matrix unavailable)';
          mx.appendChild(n);
        }
      }catch(e){}
    }
  })();
  // clean per-tile platform legend for a ratio slug (e.g. "1x1" -> "Facebook · Instagram · X · LinkedIn · Pinterest")
  function platformsForRatio(ratio){
    const row = platformMatrix[ratio];
    return row ? platformNames(row.platforms) : [];
  }
  // Render the "when you hit Create we generate these sizes for these platforms" explainer into the preview.
  // Idempotent: replaces any existing matrix so re-render never stacks.
  function renderPlatformMatrix(){
    const preview = document.getElementById('preview');
    if(!preview) return;
    const old = document.getElementById('platformMatrix');
    if(old) old.remove();
    // ratio display order — square, portrait, vertical, landscape, then blog/open-graph (whatever the matrix provides)
    const order = ['1x1','4x5','9x16','16x9','blog'];
    const keys = order.filter(k=>platformMatrix[k]).concat(Object.keys(platformMatrix).filter(k=>order.indexOf(k)<0));
    const rows = keys.map(k=>{
      const row = platformMatrix[k];
      const colon = k.replace('x',':');
      const plats = platformNames(row.platforms).map(p=>'<span class="pm-plat">'+escapeHtml(p)+'</span>').join('');
      return '<tr>'+
        '<td class="pm-ratio"><b>'+escapeHtml(colon)+'</b><span class="pm-role">'+escapeHtml(row.label||'')+'</span></td>'+
        '<td class="pm-dims">'+escapeHtml((row.w||'')+'\u00D7'+(row.h||''))+'</td>'+
        '<td class="pm-plats">'+plats+'</td>'+
        '</tr>';
    }).join('');
    const wrap = document.createElement('div');
    wrap.className = 'platform-matrix';
    wrap.id = 'platformMatrix';
    wrap.innerHTML =
      '<div class="pm-head"><b>Asset pack exports:</b></div>'+
      '<table><thead><tr><th scope="col">Ratio</th><th scope="col">Dimensions</th><th scope="col">Platforms</th></tr></thead>'+
      '<tbody>'+rows+'</tbody></table>';
    // matrix leads the preview (explainer sits above the render tiles)
    preview.insertBefore(wrap, preview.firstChild);
  }
  // expose so the offline canvas render() (defined in the earlier script scope) can re-insert
  // the matrix after it clears #preview, keeping the explainer visible on every redraw.
  window.__renderPlatformMatrix = renderPlatformMatrix;
  // show the matrix as the default preview content on load (before any campaign is generated)
  try{ renderPlatformMatrix(); }catch(e){}

  // Compose layers — independently-selectable, ALL OFF by default. Reads the creative-direction
  // checkbox cards into the {product_image, retailer, partner_logo} contract the /generate backend
  // normalizes; an empty object means a clean standalone image. Each card drives its own mark
  // directly — no standalone mark flags. Retailer composes iff a SPECIFIC retailer is checked
  // (window.__activeRetailerValue, most-recent checked wins; All alone -> brief only, no mark).
  window.__selectedLayers = function(){
    const layers = {};
    try{
      if(document.getElementById('layerProduct')?.checked) layers.product_image = true;
      const retailerVal = (typeof window.__activeRetailerValue === 'function' && window.__activeRetailerValue()) || null;
      if(retailerVal) layers.retailer = retailerVal;
      if(document.querySelector('#promptChips .ff-check-card__input[data-theme="us-ski-snowboard"]')?.checked) layers.partner_logo = true;
    }catch(e){}
    return layers;
  };

  // Default photographic hero (#196) — first paint is a real campaign photo, never a
  // generic wordmark block. Same .tile frame as generated results so load and Create
  // read as one surface. onerror removes the tile (offline/missing asset -> matrix only).
  const DEFAULT_HERO_SRC = 'input_assets/textless/cabin-table.jpg';
  try{ const pre = new Image(); pre.src = DEFAULT_HERO_SRC; }catch(e){}
  function renderDefaultHero(){
    const preview = document.getElementById('preview');
    if(!preview || document.getElementById('defaultHeroTile')) return;
    const tile = document.createElement('div');
    tile.className = 'tile tile--default-hero';
    tile.id = 'defaultHeroTile';
    tile.style.cssText = 'grid-column:1/-1;max-width:640px;margin:0 auto';
    const img = document.createElement('img');
    img.src = DEFAULT_HERO_SRC;
    img.alt = 'Kodiak frontier morning — cabin table with a protein stack, natural light';
    img.loading = 'eager';
    img.onerror = ()=>{ tile.remove(); };
    tile.appendChild(img);
    const meta = document.createElement('div');
    meta.className = 'meta';
    meta.innerHTML = '<b>Park City default</b><div class="small">Wasatch Back morning — hit Create for your campaign; copy ships as sidecar text/CSV, never baked in.</div>';
    tile.appendChild(meta);
    preview.appendChild(tile);
  }
  try{ renderDefaultHero(); }catch(e){}
  window.__renderDefaultHero = renderDefaultHero;

  // Open the collapsible Preview card so freshly-generated output is visible immediately.
  function openPreviewCard(){
    const card = document.getElementById('previewCard');
    if(card && !card.open){ card.open = true; }
  }

  // Render per-platform messaging copy — an accordion of native <details>, one per platform.
  // Consumes /generate response `platform_copy` = { platform: {headline|title, body|description, hashtags, source} }.
  // Idempotent + offline-graceful: absent platform_copy simply skips.
  function renderPlatformCopy(platformCopy){
    const preview = document.getElementById('preview');
    if(!preview) return;
    const old = document.getElementById('platformCopyPanel');
    if(old) old.remove();
    if(!platformCopy || typeof platformCopy!=='object') return;
    // stable ordering: known scope first, then any extras the backend adds
    const scope = ['x','linkedin','instagram','tiktok','facebook','pinterest','youtube'];
    const keys = scope.filter(k=>platformCopy[k]).concat(Object.keys(platformCopy).filter(k=>scope.indexOf(k)<0));
    if(!keys.length) return;
    const items = keys.map(k=>{
      const c = platformCopy[k] || {};
      const name = PLATFORM_LABELS[k] || k;
      const title = c.headline!=null ? c.headline : (c.title!=null ? c.title : '');
      const bodyTxt = c.body!=null ? c.body : (c.description!=null ? c.description : '');
      const tags = Array.isArray(c.hashtags) ? c.hashtags.join(' ') : (c.hashtags!=null ? c.hashtags : '');
      const src = String(c.source||'').toLowerCase()==='generated' ? 'generated' : (c.source ? 'fallback' : '');
      const srcPill = src ? '<span class="pc-src '+src+'">source: '+escapeHtml(src)+'</span>' : '';
      return '<details>'+
        '<summary>'+escapeHtml(name)+srcPill+'</summary>'+
        '<div class="pc-body">'+
          (title? '<p class="pc-title">'+escapeHtml(title)+'</p>':'')+
          (bodyTxt? '<p class="pc-text">'+escapeHtml(bodyTxt)+'</p>':'')+
          (tags? '<p class="pc-tags">'+escapeHtml(tags)+'</p>':'')+
        '</div>'+
      '</details>';
    }).join('');
    const panel = document.createElement('div');
    panel.className = 'platform-copy';
    panel.id = 'platformCopyPanel';
    panel.innerHTML = '<div class="pc-head">Per-platform messaging</div>' + items;
    // place after the provenance panel / download row / preview, whichever is last
    const anchor = document.getElementById('provenancePanel') || document.getElementById('previewDownloadRow') || preview;
    anchor.parentNode?.insertBefore(panel, anchor.nextSibling);
  }

  // #281 — copy BEFORE image. The copy-first panel paints at Create time from the
  // REAL request inputs (phase 'driving') and upgrades from the REAL response
  // (phase 'used'). It never invents marketing copy: driving shows only what the
  // user supplied + selected; used shows only what the backend returned, plus
  // request/response divergence flags computed from real echoed fields.
  function paintCopyPanel(arg){
    const preview = document.getElementById('preview');
    if(!preview || !arg) return;
    let panel = document.getElementById('copyFirstPanel');
    if(arg.phase==='driving'){
      try{ window.__lastCopyDriving = {brief:arg.brief, theme:arg.theme||null, themeLabel:arg.themeLabel||null, market:arg.market, place:arg.place||arg.market, products:(arg.products||[]).slice()}; }catch(e){}
      if(panel) panel.remove();
      panel = document.createElement('div');
      panel.className = 'platform-copy';
      panel.id = 'copyFirstPanel';
      panel.innerHTML = '<div class="pc-head">Campaign copy — driving this preview</div>'+
        '<details open><summary>Copy sent with this preview</summary><div class="pc-body">'+
        '<p class="pc-text">'+escapeHtml(arg.brief||'')+'</p>'+
        '<p class="pc-text small">theme: '+escapeHtml(arg.themeLabel||'none — generic')+' · market: '+escapeHtml(arg.place||arg.market)+' · products: '+escapeHtml((arg.products||[]).join(', ')||'—')+'</p>'+
        '</div></details>';
      const anchor = document.getElementById('provenancePanel') || document.getElementById('previewDownloadRow') || preview;
      anchor.parentNode?.insertBefore(panel, anchor.nextSibling);
      return;
    }
    // phase 'used' — upgrade the driving panel; never fabricate one post-hoc.
    if(!panel) return;
    const driving = (arg.driving || window.__lastCopyDriving) || {};
    const json = arg.json || {};
    const prov = (json.provenance && typeof json.provenance==='object') ? json.provenance : {};
    const flags = [];
    const reqTheme = driving.theme || null;
    const gotTheme = json.theme || prov.theme || null;
    if(reqTheme && gotTheme && String(gotTheme)!==String(reqTheme)) flags.push('theme mismatch — requested '+reqTheme+' but the response reports '+gotTheme+'; imagery may not follow the copy');
    if(reqTheme && !gotTheme) flags.push('theme dropped — requested '+reqTheme+' but the response names no theme; imagery may be generic');
    const src = String(json.source||'');
    const isFallback = /^brand-floor/i.test(src);
    if(isFallback) flags.push('render miss — fallback pixels ('+src+'), not the campaign; no copy was used');
    const pc = (json.platform_copy && typeof json.platform_copy==='object') ? json.platform_copy : {};
    const pcKeys = Object.keys(pc);
    const deferred = Array.isArray(prov.deferred) ? prov.deferred : [];
    let usedHtml;
    if(isFallback){
      usedHtml = '<p class="pc-text">No copy was used — the backend returned fallback pixels.</p>';
    } else if(prov.art_headline || pcKeys.length){
      usedHtml = (prov.art_headline ? '<p class="pc-title">'+escapeHtml(prov.art_headline)+'</p>' : '')+
        (pcKeys.length ? '<p class="pc-text">'+pcKeys.map(k=>escapeHtml(k+': '+(((pc[k]||{}).headline||(pc[k]||{}).title)||''))).join('<br>')+'</p>' : '<p class="pc-text">Full platform copy deferred — ships with Generate Campaign.</p>');
    } else if(deferred.indexOf('platform_copy')!==-1){
      // The localized tile captions ARE the preview copy — a second section saying
      // so adds noise. Drop the panel unless mismatch flags need surfacing.
      if(!flags.length){ try{ panel.remove(); }catch(e){} return; }
      usedHtml = '<p class="pc-text">Preview copy lives with each size below — full platform copy ships with Generate Campaign.</p>';
    } else {
      usedHtml = '<p class="pc-text">The backend returned no copy with this preview.</p>';
    }
    panel.innerHTML = '<div class="pc-head">Campaign copy — used in this preview</div>'+usedHtml+
      (flags.length ? '<p class="pc-text flag-err"><b>copy/imagery mismatch:</b> '+escapeHtml(flags.join(' '))+'</p>' : '');
  }

  // Single generate: fans to ALL formats/platforms/locals, returns sample + nearest Frontier + newsletter variant
  // Dev: try GlimmerProxy (127.0.0.1:8181) for brief→SKU intelligence + diagnose, then Nova unlimited (hosted) — go ham on embeddings
  const btn = document.getElementById('generateCampaign');
  if(btn){
    btn.addEventListener('click', async ()=>{
      let brief = document.getElementById('campaignBrief')?.value.trim();
      if(!brief){ brief = 'Keep It Wild — Feeding Epic Days & Wilder Lives • Nourishment for Today\'s Frontier — 100% whole grains, 14g protein — quick-test'; }
      // D. seasonal context — optional. If a season/month/holiday is chosen, fold a hint into the brief
      // that /generate receives (empty selection adds nothing). Matches how activeTheme threads context.
      const activeSeason = window.__activeSeason || null;
      if(activeSeason && !new RegExp('season:\\s*'+activeSeason.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i').test(brief)){
        brief = brief + ' — season: ' + activeSeason;
      }
      // 4. user-supplied assets: staged locally, uploaded to the DAM on hosted origins
      // (market-disclosure uploadAsset POSTs raw bytes to /library/assets and threads
      // the returned asset_id onto the staged rec; file:// + localhost stay
      // staging-only with no fetch). Thread a marker so the generate path is aware
      // a user asset was supplied. (#206 closed: the upload endpoint is real.)
      try{
        const userAssets = window.__userAssets || [];
        if(userAssets.length && !/user assets?:/i.test(brief)){
          brief = brief + ' — user assets: ' + userAssets.map(function(a){return a.name;}).join(', ');
        }
      }catch(e){}
      let selectedProducts = Array.from(document.querySelectorAll('#productChooser .sku-check:checked')).map(c=>c.value);
      const hadExplicitSelection = selectedProducts.length > 0;
      // If local and glimmer up, let it rank SKUs intelligently (not random)
      if(!selectedProducts.length && window.GlimmerProxy?.isLocal){
        try{ const ranked = await window.GlimmerProxy.pickSkus(brief, skuList, 3); if(ranked) selectedProducts = ranked; }catch(e){}
      }
      const products = selectedProducts.length ? selectedProducts : [...skuList].sort(()=>0.5-Math.random()).slice(0,3);
      const audience = 'KODIAK design guide audience — see UX Profiles (23 cards)';
      // Nearest Frontier resolves from the 1:1 market-to-featured-frontier mapping
      // (#257: featuredFrontierFor in data-core.js, canonical — the backend JSON
      // is generated from it) — no hardcoded market checks.
      let selectedLoc = null;
      try{ const locVal=document.getElementById('locality')?.value || 'US-MW-PARKCITY-84098'; selectedLoc = places.find(p=>p.market===locVal) || places.find(p=>p.market==='US-MW-PARKCITY-84098') || places[0]; }catch(e){ selectedLoc = {place:'Park City, Utah 84098', market:'US-MW-PARKCITY-84098'}; }
      const frontierLink = (typeof featuredFrontierFor==='function') ? featuredFrontierFor(selectedLoc.market) : null;
      const frontierHint = frontierLink ? frontierLink.text : 'Nearest Frontier via haversine — same pipeline fans to all 75';
      const status = document.getElementById('sampleStatus');
      const origLabel = 'Create Campaign Preview';
      // slugify a product NAME -> API slug that resolves to a packshot map key.
      // The packshot map key space == catalog product .handle (per sku-packshot-map.json contract:
      // sku_id "matches ... kodiak-full-catalog.json handle"). The catalog carries .handle for every
      // SKU, so the catalog lookup is authoritative and must be the primary path.
      //
      // Prior bug: the string fallback did .replace(/&/g,'and'), producing e.g.
      //   "Buttermilk Power Cakes Flapjack & Waffle Mix" -> "...-flapjack-and-waffle-mix"
      //   "Banana Muffin and Quick Bread Mix"            -> "banana-muffin-and-quick-bread-mix"
      // but the real map keys DROP that connector: "buttermilk-power-cakes-flapjack-waffle-mix",
      // "banana-muffin-quick-bread-mix". The inserted "and" breaks the backend longest-prefix
      // matcher, so a SKU that HAS a real packshot box silently fell to the slow generative path.
      //
      // The map keys are inconsistent about the connector (most DROP "and"/"&"; a few KEEP it, e.g.
      // buttermilk-honey-frontier-cakes-flapjack-and-waffle-mix). Those "keep" SKUs are all present as
      // catalog handles, so the authoritative .handle lookup serves them correctly and the fallback
      // below never has to guess. The fallback mirrors how Kodiak actually mints the dominant handle
      // style — drop the standalone connector — which resolves every flagship baking-mix / flapjack SKU.
      const norm = (s)=>String(s||'').toLowerCase().trim();
      const slugFallback = (name)=>{
        // drop standalone "and" / "&" the way the map keys do, then hyphenate
        const s = norm(name).replace(/&/g,' ').replace(/\band\b/g,' ');
        return s.replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
      };
      const slugify = (name)=>{
        try{
          const cat = (window.skuCatalog || (typeof skuCatalog!=='undefined' ? skuCatalog : [])) || [];
          // 1. exact catalog name match -> authoritative handle
          let hit = cat.find(p=>p && p.name===name);
          // 2. tolerant name match (case/whitespace) for GlimmerProxy-ranked or lightly-varied names
          if(!hit) hit = cat.find(p=>p && norm(p.name)===norm(name));
          if(hit && hit.handle) return hit.handle;
        }catch(e){}
        // 3. no catalog entry (offline / non-catalog name) — mint a connector-dropped slug that
        //    matches the packshot map key style rather than the lossy &->and form.
        return slugFallback(name);
      };
      // Default (no product picked) must target a MAPPED handle so the common Create-without-picking
      // takes the fast ~5s packshot route, not the 30s generative path that 503s to a placeholder.
      // "power-cakes" (the old default) is NOT a packshot map key. The buttermilk power cakes flapjack
      // & waffle mix IS the flagship key (high packshot confidence) and is the sensible default.
      const DEFAULT_MAPPED_SLUG = 'buttermilk-power-cakes-flapjack-waffle-mix';
      const primarySlug = hadExplicitSelection ? slugify(products[0]) : DEFAULT_MAPPED_SLUG;
      // Record the SKU this Create actually requested so a graceful-degrade fallback (canvas render /
      // asset-pack download) names the requested product instead of a hardcoded "savory-waffles".
      try{ window.__requestedSku = primarySlug; }catch(e){}
      // Theme is active only when a card is the starting point (set on window by the prompt-chips IIFE).
      // A manual brief edit or product selection clears window.__activeTheme.
      const activeTheme = window.__activeTheme || null;
      const THEME_LABELS = {
        'recipe-cards':'Recipe cards','localized-costco':'Localized Costco',
        'localized-publix':'Localized Publix','localized-all':'All retailers',
        'kodiak-subscription':'Kodiak subscription',
        'riff-on-past-content':'Riff on past content',
        'wild-grizzly-bears':'Wild Grizzly Bears',
        'us-ski-snowboard':'US Ski & Snowboard'
      };
      const themeLabel = activeTheme ? (THEME_LABELS[activeTheme] || activeTheme) : null;
      // Copy sidecars (#199) — campaign copy as text/CSV downloads, never baked into
      // pixels. Remembers the backend copy_sidecar (or platform_copy) per response.
      const downloadSidecar = (kind)=>{
        const sc = window.__lastSidecar || null;
        const text = (sc && sc[kind]) ? sc[kind] : 'KODIAK campaign copy — hit Create first for this campaign\u2019s sidecar.\n';
        const blob = new Blob([text], {type: kind==='csv' ? 'text/csv' : 'text/plain'});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = kind==='csv' ? 'KODIAK-copy.csv' : 'KODIAK-copy.txt';
        document.body.appendChild(a); a.click();
        setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); }, 500);
      };
      const rememberSidecar = (j)=>{
        try{
          window.__lastSidecar = (j && j.copy_sidecar) || null;
          window.__lastPlatformCopy = (j && j.platform_copy) || {};
          window.__lastLayers = (j && j.layers) || {};
        }catch(e){}
      };
      // Reveal the primary "Download image" action directly under the preview.
      // Idempotent — builds the row once, then just unhides it.
      const revealDownloadActions = ()=>{
        const preview = document.getElementById('preview');
        if(!preview) return;
        let row = document.getElementById('previewDownloadRow');
        if(!row){
          row = document.createElement('div');
          row.id = 'previewDownloadRow';
          row.className = 'row';
          row.style.cssText = 'margin:14px 0 0;gap:10px;flex-direction:column;align-items:stretch;max-width:640px;margin-left:auto;margin-right:auto';
          // PRIMARY — download the shown preview image
          const primary = document.createElement('button');
          primary.type = 'button';
          primary.id = 'downloadImageBtn';
          primary.className = 'btn orange';
          primary.style.cssText = 'justify-content:center;padding:12px 18px;font-size:13px';
          primary.textContent = 'Download image';
          primary.setAttribute('aria-label', 'Download the composed campaign image');
          primary.addEventListener('click', function(){ window.downloadAssetPack(); });
          row.appendChild(primary);
          // SECONDARY — the localized campaign asset pack (all ratios x platform x retailer x localized languages).
          // Real primary action tied to #downloadPack's handler (window.downloadAssetPack). No coming-soon gate.
          const pack = document.createElement('button');
          pack.type = 'button';
          pack.id = 'downloadPackBtn';
          pack.className = 'btn ghost';
          pack.style.cssText = 'justify-content:center;padding:12px 18px;font-size:13px';
          pack.textContent = 'Download asset pack';
          pack.setAttribute('aria-label', 'Download the full localized campaign asset pack — all ratios, platforms, retailers, languages');
          pack.addEventListener('click', function(){ window.downloadAssetPack({pack:true}); });
          row.appendChild(pack);
          // SIDECARS (#199) — campaign copy as text/CSV, never baked into pixels.
          const txtBtn = document.createElement('button');
          txtBtn.type = 'button';
          txtBtn.id = 'downloadCopyTxtBtn';
          txtBtn.className = 'btn ghost';
          txtBtn.style.cssText = 'justify-content:center;padding:12px 18px;font-size:13px';
          txtBtn.textContent = 'Download copy (.txt)';
          txtBtn.setAttribute('aria-label', 'Download the campaign copy as text');
          txtBtn.addEventListener('click', function(){ downloadSidecar('txt'); });
          row.appendChild(txtBtn);
          const csvBtn = document.createElement('button');
          csvBtn.type = 'button';
          csvBtn.id = 'downloadCopyCsvBtn';
          csvBtn.className = 'btn ghost';
          csvBtn.style.cssText = 'justify-content:center;padding:12px 18px;font-size:13px';
          csvBtn.textContent = 'Download copy (.csv)';
          csvBtn.setAttribute('aria-label', 'Download the campaign copy as CSV');
          csvBtn.addEventListener('click', function(){ downloadSidecar('csv'); });
          row.appendChild(csvBtn);
          preview.parentNode?.insertBefore(row, preview.nextSibling);
        }
        row.style.display = 'flex';
      };
      // Show the real generation result(s). For a single image, one prominent hero tile.
      // For multi-product fan-out, a grid of tiles (one per product). window.__lastHeroUrl is
      // the FIRST returned so the "Download image" button targets the hero.
      const showRealImage = (imageUrl, source, opts)=>{
        opts = opts || {};
        // In grid/append mode the caller owns __lastHeroUrl (first-returned wins); single mode records here.
        if(!opts.grid) window.__lastHeroUrl = imageUrl;
        const preview = document.getElementById('preview');
        if(!preview) return;
        if(!opts.append) preview.innerHTML = '';
        const label = (source && String(source).toLowerCase().includes('bedrock')) ? 'Nova Pro' : (source || 'Nova Pro');
        const tile = document.createElement('div');
        tile.className = 'tile';
        // single hero centers wide; grid tiles flow in the auto-fill preview grid
        if(!opts.grid) tile.style.cssText = 'grid-column:1/-1;max-width:640px;margin:0 auto';
        const img = document.createElement('img');
        img.src = imageUrl;
        img.alt = 'Nova Pro composed campaign hero — ' + brief;
        img.style.cssText = 'width:100%;height:auto;max-width:100%;display:block;background:var(--chocolate)';
        tile.appendChild(img);
        const meta = document.createElement('div');
        meta.className = 'meta';
        const themeLine = opts.theme ? ` · theme: ${opts.themeLabel || opts.theme}` : '';
        const prodLine = opts.productName ? `${opts.productName} · ` : '';
        meta.innerHTML = `<b>KODIAK® composed hero</b><div class="small">${prodLine}source: ${label} · ${selectedLoc.market}${themeLine} · ${brief.slice(0,80)}</div>`;
        tile.appendChild(meta);
        preview.appendChild(tile);
        // source badge above the preview — provenance-driven, fallbacks flagged (#173)
        let badge = document.getElementById('genSourceBadge');
        if(!badge){ badge=document.createElement('span'); badge.id='genSourceBadge'; badge.className='badge'; preview.parentNode?.insertBefore(badge, preview); }
        const rb = rungBadge(source, opts.provenance);
        paintRungBadge(badge, rb);
        if(opts.themeLabel || opts.theme) badge.textContent += ' · theme: ' + (opts.themeLabel || opts.theme);
        revealDownloadActions();
        try{ if(typeof window.__kodiakRevealCampaign==='function') window.__kodiakRevealCampaign(); }catch(e){}
      };
      // Human labels for the render ratios and the engine.
      const RATIO_LABELS = {
        '1x1': {name:'Feed', cls:'r-1x1'},
        '4x5': {name:'Portrait', cls:'r-4x5'},
        '9x16': {name:'Vertical', cls:'r-9x16'},
        '16x9': {name:'Landscape', cls:'r-16x9'},
        '2x3': {name:'Story', cls:'r-2x3'}
      };
      const ENGINE_LABELS = {
        'stability-control-structure':'Control-structure restyle (Stability)',
        'pillow-compose':'Pillow compose (brand overlay)'
      };
      // Unit 2 (#173) — honest rung badge. Provenance drives the label; any
      // fallback rung (C/D or a fallthrough_reason) gets flagged, never silently
      // relabeled "Nova Pro". Fallback sightings become counted facts.
      const RUNG_LABELS = {
        'A':'Rung A · packshot verbatim',
        'B':'Rung B · Stability restyle',
        'C':'Rung C · Pillow fallback',
        'D':'Rung D · brand-floor fallback'
      };
      const rungBadge = (source, prov)=>{
        prov = prov || {};
        const rung = prov.rung || '';
        const fallback = !!prov.fallthrough_reason || rung==='C' || rung==='D';
        const base = RUNG_LABELS[rung] || ((source && String(source).toLowerCase().includes('bedrock')) ? 'Nova Pro' : (source || 'Nova Pro'));
        const text = (fallback ? 'Fallback — ' : '') + base + (prov.fallthrough_reason ? ' (' + prov.fallthrough_reason + ')' : '');
        return {text:text, fallback:fallback};
      };
      const paintRungBadge = (badge, rb)=>{
        badge.textContent = rb.text;
        badge.style.cssText = 'display:inline-block;margin:0 0 8px;padding:2px 8px;border-radius:6px;font-size:11px;color:#FFF8F0;background:' + (rb.fallback ? '#B51E14' : '#1A3C34');
      };
      const escapeHtml = (s)=> String(s==null?'':s).replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
      // TASK 1 — render THREE labeled tiles (one per ratio) at real aspect ratio; records the 1x1 as the hero.
      const showRenderSet = (renders, opts)=>{
        opts = opts || {};
        const preview = document.getElementById('preview');
        if(!preview) return;
        preview.innerHTML = '';
        // keep the platform explainer at the top of the preview even after a generate
        try{ renderPlatformMatrix(); }catch(e){}
        const set = document.createElement('div');
        set.className = 'render-set';
        const themeBit = opts.themeLabel ? (', ' + opts.themeLabel + ' theme') : '';
        renders.forEach((r, i)=>{
          const meta = RATIO_LABELS[r.ratio] || {name:r.ratio, cls:'r-'+String(r.ratio||'').replace(/[^0-9x]/g,'')};
          const tile = document.createElement('div');
          tile.className = 'render-tile ' + meta.cls;
          const frame = document.createElement('div');
          frame.className = 'render-frame';
          const img = document.createElement('img');
          img.src = r.image_url;
          img.alt = 'KODIAK campaign hero, ' + r.ratio.replace('x',':') + ' ' + meta.name + themeBit;
          img.loading = i === 0 ? 'eager' : 'lazy';
          frame.appendChild(img);
          tile.appendChild(frame);
          const cap = document.createElement('div');
          cap.className = 'render-cap';
          const ratioColon = r.ratio.replace('x',':');
          // clean caption: "1:1 Feed · 1080×1080" + the platforms this ratio serves (no engineering noise)
          const plats = platformsForRatio(r.ratio);
          const platLine = plats.length ? '<span class="rt-platforms">' + escapeHtml(plats.join(' \u00B7 ')) + '</span>' : '';
          // S12 — localized caption per tile: EN source + this market's top_languages[] (live /localize when on,
          // community-review never machine, offline pending). Driven by the selected market at render time.
          let locCap = '';
          try{
            const _m = document.getElementById('locality')?.value || (selectedLoc && selectedLoc.market);
            if(_m && typeof window.KODIAK_locCaption==='function') locCap = window.KODIAK_locCaption(_m);
          }catch(e){}
          cap.innerHTML = '<b>' + escapeHtml(ratioColon + ' ' + meta.name) + '</b>' +
            '<span class="dims">' + escapeHtml((r.w||'') + '\u00D7' + (r.h||'')) + '</span>' + platLine + locCap;
          tile.appendChild(cap);
          set.appendChild(tile);
        });
        preview.appendChild(set);
        openPreviewCard();
        // hero download targets the 1x1 (primary) render
        const primary = renders.find(r=>r.ratio==='1x1') || renders[0];
        if(primary) window.__lastHeroUrl = primary.image_url;
        // pack download (#204) needs the DAM keys, not the presigned urls — record
        // the set's s3_uris + ratios alongside the hero so downloadAllPreview can
        // POST them to /assets/pack for a real ISO-named zip.
        try{
          const pack = (Array.isArray(renders)?renders:[]).filter(r=>r && r.s3_uri).map(r=>({s3_uri:r.s3_uri, ratio:r.ratio||'1x1'}));
          window.__lastPack = pack.length ? pack : null;
        }catch(e){ try{ window.__lastPack = null; }catch(_){} }
        // source badge above the preview — provenance-driven, fallbacks flagged (#173)
        let badge = document.getElementById('genSourceBadge');
        if(!badge){ badge=document.createElement('span'); badge.id='genSourceBadge'; badge.className='badge'; preview.parentNode?.insertBefore(badge, preview); }
        const rb2 = rungBadge(opts.source, opts.provenance);
        paintRungBadge(badge, rb2);
        if(opts.themeLabel) badge.textContent += ' · theme: ' + opts.themeLabel;
        revealDownloadActions();
        try{ if(typeof window.__kodiakRevealCampaign==='function') window.__kodiakRevealCampaign(); }catch(e){}
      };
      // expose the hosted multi-ratio renderer so the Generate Campaign section can reuse it for full-campaign results
      try{ window.KODIAK_showRenderSet = showRenderSet; }catch(e){}
      // TASK 2 — collapsible provenance panel: what you provided vs what we did.
      const renderProvenancePanel = (prov, ctx)=>{
        ctx = ctx || {};
        const preview = document.getElementById('preview');
        if(!preview || !prov) return;
        // remove a prior panel so re-generate replaces cleanly
        const old = document.getElementById('provenancePanel');
        if(old) old.remove();
        const engineLabel = ENGINE_LABELS[prov.engine] || prov.engine || '—';
        const ratios = prov.ratios || {};
        const ratioPills = Object.keys(ratios).map(k=>{
          const role = ratios[k];
          const cls = /primary/i.test(role) ? 'primary' : 'outpaint';
          return '<span class="prov-pill ' + cls + '">' + escapeHtml(k.replace('x',':')) + ' ' + escapeHtml(role) + '</span>';
        }).join(' ');
        const onoff = (v)=> v ? '<span class="prov-pill on">applied</span>' : '<span class="prov-pill off">not applied</span>';
        const rows = (pairs)=> pairs.filter(p=>p[1]!=null && p[1]!=='').map(p=>'<dt>' + escapeHtml(p[0]) + '</dt><dd>' + p[1] + '</dd>').join('');
        const provided = rows([
          ['Prompt', escapeHtml(prov.incoming_prompt || ctx.brief || '—')],
          ['Headline', escapeHtml(prov.headline)],
          ['Theme', escapeHtml(ctx.themeLabel || ctx.theme)],
          ['Market', escapeHtml(ctx.market)],
          ['Product', escapeHtml(ctx.product)]
        ]);
        const did = rows([
          ['Engine', escapeHtml(engineLabel)],
          ['Model', escapeHtml(prov.model)],
          ['Seed source', escapeHtml(prov.seed_source)],
          ['Seed selection', escapeHtml(prov.seed_selection)],
          ['Art-director scene', escapeHtml(prov.scene_prompt)],
          ['Control strength', prov.control_strength!=null ? escapeHtml(prov.control_strength) : null],
          ['Ratios', ratioPills || null],
          ['Brand overlay', onoff(prov.overlay_applied)],
          ['Paper texture', onoff(prov.paper_overlay)]
        ]);
        const panel = document.createElement('details');
        panel.className = 'provenance';
        panel.id = 'provenancePanel';
        panel.innerHTML =
          '<summary>How this was made</summary>' +
          '<div class="prov-body">' +
            '<div class="prov-group"><h4>You provided</h4><dl>' + provided + '</dl></div>' +
            '<div class="prov-group"><h4>What we did</h4><dl>' + did + '</dl></div>' +
          '</div>';
        // place directly under the preview (after any download row if present)
        const anchor = document.getElementById('previewDownloadRow') || preview;
        anchor.parentNode?.insertBefore(panel, anchor.nextSibling);
      };
      const finishCommon = ()=>{
        // Update local flavor with brief context (runs after either path)
        const lf = document.getElementById('localFlavorText');
        if(lf) lf.innerHTML += `<br><span class="flag-pine"><b>Brief applied:</b> “${brief}” — fans to all formats</span>`;
        console.log('KODIAK generate — sample', {brief, products, primarySlug, audience, selectedLoc: selectedLoc.market, frontierHint});
      };
      // Lock competing controls during generation so nothing changes mid-request; restore after.
      // Class-driven dimming on #promptChips (no inline styles): .is-locked paints it in components.css.
      const lockIds = ['generateCampaign','productSearch','randomProducts','downloadPack','promptUpload'];
      const lockControls = (locked)=>{
        lockIds.forEach(id=>{ const el=document.getElementById(id); if(el) el.disabled=locked; });
        document.querySelectorAll('#promptChips .ff-check-card__input').forEach(c=>{ c.disabled=locked; });
        document.getElementById('promptChips')?.classList.toggle('is-locked', locked);
        document.querySelectorAll('#productChooser .sku-check').forEach(c=>{ c.disabled=locked; });
      };
      // Preserve local/offline behavior: file:// or localhost has no /generate — go straight to canvas.
      const isLocal = (location.protocol==='file:') || ['127.0.0.1','localhost'].includes(location.hostname);
      if(isLocal){
        if(status) status.textContent = 'Campaign preview ready (local canvas)';
        btn.disabled=true; btn.textContent='Generating…';
        // #281 — copy paints before the canvas pixels, from the real request inputs.
        try{ paintCopyPanel({phase:'driving', brief, theme:activeTheme||null, themeLabel:themeLabel||null, market:selectedLoc.market, place:selectedLoc.place||selectedLoc.market, products}); }catch(e){}
        try{ render(); }catch(e){ console.warn('render() failed on generate (local)', e); }
        openPreviewCard();
        finishCommon();
        btn.disabled=false; btn.textContent=origLabel;
        return;
      }
      // Hosted https path: call the real Nova Pro backend, canvas as graceful fallback.
      lockControls(true);
      btn.textContent='Composing…';
      // Skeleton pulse tile + elapsed-seconds counter so the ~90s wait never feels frozen.
      const preview = document.getElementById('preview');
      // leak-teardown: timer holders + controller are declared BEFORE the try so the finally can always
      // clear them; the request-shape helpers are defined before the try because the catch path calls
      // drawNetworkLossNotice (a const defined inside the try would not be visible to the catch).
      let elapsed = 0, tick = null, stageT1 = null, stageT2 = null, timeoutId = null;
      const controller = new AbortController();
      // Multi-product (2+ selected, no theme) shows a skeleton tile per pending product; otherwise one hero skeleton.
      const willFanOut = !activeTheme && hadExplicitSelection && products.length > 1;
      // Decide the request shape:
      //  - themed chip active -> ONE themed request (theme wins; no per-product fan-out)
      //  - 2+ products explicitly selected AND no theme -> one request PER product, render a grid
      //  - otherwise -> one default request (single hero)
      const doThemedOrSingle = activeTheme || !(hadExplicitSelection && products.length > 1);
      const oneGenerate = async (productSlug, wantTheme)=>{
        // scope-first: Create reads the segmented control's selection (window.__campaignScope, default local)
        const scope = window.__campaignScope || 'local';
        // staged DAM pick (Browse past assets) rides as the seed — the backend prefers
        // it over all probed seeds, so the customer's pick drives the pixels. Most
        // recently staged dam asset wins; absent key = today's path untouched.
        let stagedKey = null;
        try{ const staged = (window.__userAssets||[]).filter(function(a){ return a && a.source==='dam' && a.key; }); if(staged.length) stagedKey = staged[staged.length-1].key; }catch(e){}
        // Compose layers (#199/#200): independently-selected, default OFF. An empty
        // object means a clean standalone image + copy sidecars from the backend.
        let reqLayers = {};
        try{ reqLayers = (typeof window.__selectedLayers==='function') ? window.__selectedLayers() : {}; }catch(e){ reqLayers = {}; }
        const body = {prompt: brief, market: selectedLoc.market, product: productSlug, scope, layers: reqLayers, ...(wantTheme ? {theme: wantTheme} : {}), ...(stagedKey ? {seed_key: stagedKey} : {})};
        const resp = await fetch('/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body), signal: controller.signal});
        if(!resp.ok) throw new Error('backend returned HTTP ' + resp.status);
        // isolate the parse so a malformed 200 body surfaces as a clear error (outer catch -> visible status)
        let json;
        try{ json = await resp.json(); }catch(pe){ throw new Error('malformed response from backend'); }
        if(!json || !json.image_url) throw new Error('response missing image_url');
        return json;
      };
      // Total-network-loss defense-in-depth ONLY (no response at all). Composites the REAL
      // requested SKU on a plain canvas and labels it explicitly as an offline stand-in. This
      // is NOT the fake-output path: it does not set window.__lastHeroUrl (so the download
      // button will not treat it as a real generated hero) and carries no "source: Nova Pro"
      // badge — it visibly reads as an offline preview of the requested product, not a result.
      const drawNetworkLossNotice = (requestedSku, briefText)=>{
        const p = document.getElementById('preview');
        if(!p) return;
        p.innerHTML = '';
        // strip any stale real-result source badge so the offline notice is not mislabeled.
        const staleBadge = document.getElementById('genSourceBadge'); if(staleBadge) staleBadge.remove();
        const sku = String(requestedSku || 'power-cakes');
        // resolve a real thumbnail for the requested product from the catalog/products list.
        // only a real http(s) url is loadable; input_assets/*.png stubs do not exist (404 to
        // console). default to no hero -> paint(null) draws the ad without a photo.
        let heroSrc = '';
        try{
          const cat = (window.skuCatalog || (typeof skuCatalog!=='undefined' ? skuCatalog : [])) || [];
          const hit = cat.find(x=>x && (x.handle===sku || x.name===sku));
          if(hit && hit.img) heroSrc = hit.img;
          else if(typeof products!=='undefined'){ const pr = products.find && products.find(x=>x && (x.id===sku)); if(pr && pr.img) heroSrc = pr.img; }
        }catch(e){}
        const isRealHero = typeof heroSrc==='string' && /^https?:\/\//.test(heroSrc) && heroSrc.indexOf('input_assets/')===-1;
        const tile = document.createElement('div');
        tile.className = 'tile';
        tile.style.cssText = 'grid-column:1/-1;max-width:640px;margin:0 auto;border:1px dashed #B51E14';
        const c = document.createElement('canvas'); c.width=1080; c.height=1080; c.style.maxWidth='100%'; c.style.height='auto';
        const ctx = c.getContext('2d');
        const paint = (heroImg)=>{
          try{ drawAd(ctx, 1080, 1080, (briefText||'Keep It Wild'), {id:sku}, heroImg||null); }catch(e){}
          // explicit offline watermark band — makes clear this is NOT the generated result.
          ctx.fillStyle='rgba(181,30,20,0.92)'; ctx.fillRect(0,0,1080,64);
          ctx.fillStyle='#FFF8F0'; ctx.textAlign='center'; ctx.font='700 26px Inter,sans-serif';
          ctx.fillText('OFFLINE PREVIEW — not the generated campaign', 540, 42);
        };
        // leak-teardown: null the handlers after they fire so the closure + Image release.
        let img = new Image(); img.crossOrigin='anonymous';
        img.onload = ()=>{ paint(img); img.onload=img.onerror=null; img=null; };
        img.onerror = ()=>{ paint(null); img.onload=img.onerror=null; img=null; };
        // only fire a network load for a real resolvable url; otherwise paint with no photo
        // (NO Image(), NO 404). offline preview still renders with its OFFLINE watermark.
        if(isRealHero){ img.src = heroSrc; }
        else { paint(null); img.onload=img.onerror=null; img=null; }
        tile.appendChild(c);
        const meta = document.createElement('div'); meta.className='meta';
        meta.innerHTML = `<b>Offline preview — ${sku}</b><div class="small flag-err">No server response. This is a local stand-in of the requested product, not a generated campaign. Reconnect and try Create again.</div>`;
        tile.appendChild(meta);
        p.appendChild(tile);
      };
      // try OPENS before any timer is created so an early throw during skeleton/timer setup still
      // reaches the finally and clears the interval + timeouts (previously the try opened after the
      // timers were created, leaving an unguarded window where a throw would leak the elapsed-tick interval).
      try{
      // a fresh preview generate replaces any prior campaign (#243) — clear it
      // at START (skeleton paint) so stale assets vanish the moment Create runs.
      try{ if(typeof window.KODIAK_resetCampaign==='function') window.KODIAK_resetCampaign(); }catch(e){}
      // #281 — copy paints before the image request, from the real request inputs.
      try{ paintCopyPanel({phase:'driving', brief, theme:activeTheme||null, themeLabel:themeLabel||null, market:selectedLoc.market, place:selectedLoc.place||selectedLoc.market, products}); }catch(e){}
      if(preview){
        if(willFanOut){
          preview.innerHTML = products.map((name,i)=>`<div class="tile genSkeletonTile"><div class="gen-pulse"><span class="gen-pulse-label">Composing…</span></div><div class="meta"><b>${name}</b><div class="small" id="genElapsed${i}">0s elapsed — up to ~90s</div></div></div>`).join('');
        } else {
          preview.innerHTML = `<div class="tile" id="genSkeleton"><div class="gen-pulse"><span class="gen-pulse-label gen-pulse-label--lg">Composing…</span></div><div class="meta"><b>Composing your campaign with Nova Pro${activeTheme ? ' — theme: ' + themeLabel : ''}</b><div class="small" id="genElapsed">0s elapsed — up to ~90s</div></div></div>`;
        }
        if(!document.getElementById('genPulseKeyframes')){ const st=document.createElement('style'); st.id='genPulseKeyframes'; st.textContent='@keyframes genpulse{0%{background-position:200% 0}100%{background-position:-200% 0}}'; document.head.appendChild(st); }
        tick = setInterval(()=>{ elapsed++; document.querySelectorAll('[id^="genElapsed"]').forEach(e=>{ e.textContent = elapsed+'s elapsed — up to ~90s'; }); }, 1000);
      }
      if(status){
        status.textContent = 'Composing your campaign with Nova Pro… (up to ~90s)';
        stageT1 = setTimeout(()=>{ if(status) status.textContent = 'Still composing — Nova Pro is rendering your hero…'; }, 30000);
        stageT2 = setTimeout(()=>{ if(status) status.textContent = 'Almost there — finishing the composition…'; }, 60000);
      }
      timeoutId = setTimeout(()=>controller.abort(), 100000); // Nova Pro composition is slow (~90s); allow headroom
        try{ window.__lastSidecar = null; window.__lastPlatformCopy = {}; }catch(e){}
        if(doThemedOrSingle){
          // Single request (themed if a chip is active, else default product).
          const json = await oneGenerate(primarySlug, activeTheme || undefined);
          rememberSidecar(json);
          const readyThemeLabel = json.theme ? (THEME_LABELS[json.theme] || themeLabel) : (activeTheme ? themeLabel : null);
          const readyTheme = (json.theme || activeTheme) ? (' · theme: ' + readyThemeLabel) : '';
          if(Array.isArray(json.renders) && json.renders.length){
            // NEW backend: three real sizes — render all three labeled tiles.
            showRenderSet(json.renders, {source: json.source, themeLabel: readyThemeLabel, provenance: json.provenance});
            const n = json.renders.length;
            if(status) status.textContent = 'Campaign preview ready — ' + n + ' sizes composed from ' + (json.source || 'Nova Pro') + readyTheme;
          } else {
            // OLDER backend (no renders array): fall back to the single-hero behavior.
            showRealImage(json.image_url, json.source, {theme: json.theme || activeTheme || null, themeLabel: json.theme ? (THEME_LABELS[json.theme] || json.theme) : themeLabel, provenance: json.provenance});
            if(status) status.textContent = 'Campaign preview ready — one real composed hero from ' + (json.source || 'Nova Pro') + readyTheme;
          }
          // provenance transparency panel (renders whenever the backend supplies it)
          if(json.provenance){
            renderProvenancePanel(json.provenance, {brief, theme: json.theme || activeTheme, themeLabel: readyThemeLabel, market: selectedLoc.market, product: primarySlug});
          }
          // per-platform messaging copy panel (renders when the backend supplies platform_copy; skips gracefully otherwise)
          renderPlatformCopy(json.platform_copy);
          // #281 — upgrade the driving panel to the copy actually used + divergence flags.
          try{ paintCopyPanel({phase:'used', json}); }catch(e){}
          // auto-open the collapsed Preview card so the user sees the freshly-composed output
          openPreviewCard();
        } else {
          // Multi-product fan-out: one themed-less request per selected product; render each tile as it returns.
          if(preview) preview.innerHTML = '';
          if(status) status.textContent = 'Composing ' + products.length + ' product variants with Nova Pro…';
          let firstDone = false, okCount = 0;
          await Promise.all(products.map(async (name)=>{
            const slug = slugify(name);
            try{
              const json = await oneGenerate(slug, undefined);
              showRealImage(json.image_url, json.source, {append:true, grid:true, productName:name, provenance: json.provenance});
              okCount++;
              if(!firstDone){ firstDone = true; window.__lastHeroUrl = json.image_url; rememberSidecar(json); try{ window.__lastCopyJson = json; }catch(_){} }
            }catch(e){
              console.warn('generate: product variant failed for', name, e && e.message ? e.message : e);
              // render a small failed-tile so the grid shows what did not compose
              const p = document.getElementById('preview');
              if(p){ const t=document.createElement('div'); t.className='tile'; t.innerHTML=`<div class="meta"><b>${name}</b><div class="small flag-err">variant failed — try again</div></div>`; p.appendChild(t); }
            }
          }));
          if(status) status.textContent = okCount ? ('Campaign preview ready — ' + okCount + ' of ' + products.length + ' product variants composed') : 'Some variants could not reach the server — check your connection and try again';
          // #281 — fan-out upgrade from the first variant's real response.
          try{ if(window.__lastCopyJson) paintCopyPanel({phase:'used', json: window.__lastCopyJson}); }catch(e){}
          openPreviewCard();
        }
        // Successful submit reached (no throw): clear the persisted lifecycle snapshot so a completed
        // campaign does not resurrect stale inputs on the next visit / tab-discard restore.
        try{ if(typeof window.__kodiakClearFFState==='function') window.__kodiakClearFFState(); }catch(e){}
      }catch(err){
        // NEVER-503 CONTRACT: a well-formed POST /generate now returns 200 with real Kodiak
        // pixels 100% of the time (backend degradation ladder A->B->C->D, rung D cannot fail).
        // So a thrown error here means TOTAL network loss — no response at all (fetch rejected
        // or aborted), not a backend generation failure. The old fake-placeholder path (render()
        // -> drawAd with a hardcoded savory-waffles product) is DELETED: it produced fake output
        // that misrepresented a real generated result. Defense-in-depth for total network loss
        // ONLY: composite the REAL requested SKU offline and label it explicitly as an offline
        // stand-in — never styled or badged as the real generated campaign.
        console.warn('generate: no response from backend (total network loss) —', err && err.message ? err.message : err);
        const timedOut = err && (err.name==='AbortError');
        try{
          drawNetworkLossNotice(window.__requestedSku || primarySlug, brief);
        }catch(e){ console.warn('offline notice render failed', e); }
        if(status) status.textContent = timedOut
          ? 'No response from the server (timed out) — offline preview shown; reconnect and try again'
          : 'Could not reach the server — offline preview shown; reconnect and try again';
      }finally{
        clearTimeout(timeoutId);
        if(stageT1) clearTimeout(stageT1);
        if(stageT2) clearTimeout(stageT2);
        if(tick) clearInterval(tick);
        const sk=document.getElementById('genSkeleton'); if(sk) sk.remove();
        document.querySelectorAll('.genSkeletonTile').forEach(t=>t.remove());
        lockControls(false);
        finishCommon();
        btn.disabled=false; btn.textContent=origLabel;
      }
    });
  }

  // Programmatic layers: expose masks/fonts as geometric levers via data-mcp-layer (tooling, not GenAI pixels)
  document.querySelectorAll('[data-mcp-layer]').forEach(el=>{ el.title = 'WebMCP layer: ' + el.getAttribute('data-mcp-layer'); });
  console.log('KODIAK campaign UI — single brief + up to 3 SKUs + real team + local flavor derived + single generate (fans to ALL)');
})();
