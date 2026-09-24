// --- New campaign UI: products up to 3 + random, real employees, local flavor derived, single generate ---
(function(){
  /** @type {SkuEntry[]} */
  let skuCatalog=[]; async function loadCatalog(){ const urls=["data/products/kodiak-full-catalog.json","../../data/products/kodiak-full-catalog.json","./data/products/kodiak-full-catalog.json","/data/products/kodiak-full-catalog.json"]; for(const url of urls){ try{ const r=await fetch(url); if(r.ok){ const d=await r.json(); if(d.products?.length) { console.log('[catalog] loaded',d.products.length,'from',url); return d.products; } }}catch(e){} } console.warn('[catalog] failed all urls'); return []; } loadCatalog().then(products=>{ skuCatalog=products||[]; const chooser=document.getElementById("productChooser"); if(!chooser) return;
    // Single owner of #productChooser. If the catalog JSON loaded, render rich checkboxes (image + price).
    // If it failed/empty, DO NOT leave the chooser blank — fall back to the hardcoded skuList so a checkbox
    // always exists. Selection handlers are bound once by the static block below via delegation on the element,
    // so they keep working no matter which branch paints.
    const preserveChecked=()=>new Set(/** @type {HTMLInputElement[]} */ (Array.from(chooser.querySelectorAll('.sku-check:checked'))).map(c=>c.value));
    if(skuCatalog.length){ window.skuCatalog=skuCatalog; skuList=skuCatalog.map(p=>p.name);
      const render=(filter="")=>{ const kept=preserveChecked(); const q=(filter||"").toLowerCase(); let filtered=skuCatalog.filter(p=>!q||(p.name||"").toLowerCase().includes(q)||(p.handle||"").toLowerCase().includes(q)||(p.category||"").toLowerCase().includes(q)).slice(0,12);
        // never blank the chooser: a no-match filter (e.g. a brief keyword) falls back to the first 12 SKUs
        if(!filtered.length) filtered=skuCatalog.slice(0,12);
        // never erase a selection: checked SKUs outside the filter ride along on top,
        // so typing a second product (or brief word) cannot destroy the first pick
        if(kept.size){ const seen=new Set(filtered.map(p=>p.name)); const missing=skuCatalog.filter(p=>kept.has(p.name)&&!seen.has(p.name)); if(missing.length) filtered=missing.concat(filtered).slice(0,12+missing.length); }
        chooser.innerHTML=filtered.map(p=>`<label class="sku-pick"><input type="checkbox" value="${p.name}" class="sku-check"${kept.has(p.name)?" checked":""}> <img src="${p.images?.[0]||""}" onerror="this.classList.add('is-hidden')" crossorigin="anonymous" loading="lazy"><span>${p.name}<br><span class="sku-sub">${p.category} • $${p.price_usd||""}</span></span></label>`).join(""); const hint2=document.getElementById('skuHint'); if(hint2) hint2.textContent=`${skuCatalog.length} SKUs loaded — ${kept.size} / 3 selected`; if(window.KODIAK_SCORECARDS) window.KODIAK_SCORECARDS.render(); try{ if(typeof window.__syncProductPopover==='function') window.__syncProductPopover(); }catch(e){} };
      render(""); document.getElementById("productSearch")?.addEventListener("input",/** @param {Event} e */(e)=>render((/** @type {HTMLInputElement} */ (e.target)).value)); document.getElementById("campaignBrief")?.addEventListener("input",/** @param {Event} e */(e)=>{ const v=(/** @type {HTMLInputElement} */ (e.target)).value.toLowerCase().split(/\s+/).filter(Boolean).pop(); if(v&&v.length>2) render(v); });
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
    "Kodiak Cakes Blueberry Lemon Muffin Mix","Kodiak Cakes Power Cups Protein Oatmeal Cup","Kodiak Cakes Cheddar Jalapeno Drop Biscuits",
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
  const hint = /** @type {HTMLElement} */ (document.getElementById('skuHint')); // page contract: always in markup
  if(chooser){
    // Synchronous baseline: paint skuList checkboxes immediately so #productChooser is never empty before the
    // async catalog resolves. The catalog .then above is the single owner afterward — it upgrades these to rich
    // rows on success or re-affirms skuList on empty. The change/random handlers below bind to the chooser
    // ELEMENT (event delegation), so they keep working across every innerHTML swap regardless of which renderer paints.
    chooser.innerHTML = skuList.slice(0,12).map((n,i)=>`<label class="sku-pick"><input type="checkbox" value="${n}" class="sku-check"> ${n}</label>`).join('');
    const checks = ()=> /** @type {HTMLInputElement[]} */ (Array.from(chooser.querySelectorAll('.sku-check:checked')));
    chooser.addEventListener('change', /** @param {Event} e */ (e)=>{
      const t = /** @type {HTMLInputElement|null} */ (e.target);
      if(t && t.classList.contains('sku-check')){
        const c = checks();
        if(c.length > 3){ t.checked=false; hint.textContent = 'Max 3 — uncheck one first'; hint.style.color='#B51E14'; return; }
        hint.textContent = c.length + ' / 3 selected — empty = random 3 on generate';
        hint.style.color = '';
        if(typeof window.updateLocalFlavor==='function') window.updateLocalFlavor();
      }
    });
    document.getElementById('randomProducts')?.addEventListener('click', ()=>{
      const boxes = /** @type {HTMLInputElement[]} */ (Array.from(chooser.querySelectorAll('.sku-check')));
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
  /** @type {Object<string, string>} */
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
      const loc = (/** @type {HTMLInputElement|null} */ (document.getElementById('locality')))?.value || sel;
      if(loc) market = loc;
    }catch(e){}
    // Season-aware engine first (every market x every season resolves a line).
    // Artisanal flavorMap second, places table third, generic only when unknown.
    let txt = null;
    try{
      var season = null;
      try{ season = (typeof window.__activeSeason !== 'undefined') ? window.__activeSeason : (/** @type {HTMLInputElement|null} */ (document.getElementById('seasonalSelect')))?.value || null; }catch(se){ season = null; }
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
  setTimeout(function(){ if(typeof window.updateLocalFlavor==='function') window.updateLocalFlavor(); }, 800);
  document.addEventListener('change', /** @param {Event} e */ (e)=>{ const t = e.target instanceof Element ? e.target : null; if(t && (t.id==='locality' || t.id==='seasonalSelect') && typeof window.updateLocalFlavor==='function') window.updateLocalFlavor(); });
  // Resting showcase repaint (top level so tests share it): the static
  // #previewHero ships Park City copy. When another market is selected, the
  // resting words repaint from that market's row + frontier — Utah copy never
  // renders under an Ohio (or any non-Park-City) market. Park City markets
  // keep the shipped example untouched. Pure data half tested in
  // preview-extend.test.mjs via KODIAK_restingCopyFor.
  const RESTING_HOME = ['US-MW-PARKCITY-84098', 'US-MW-WASATCH'];
  const restingRow = (marketId)=>{
    try{
      const rows = (typeof places !== 'undefined' && Array.isArray(places)) ? places : [];
      return rows.find(r=>r && r.market === marketId) || null;
    }catch(e){ return null; }
  };
  const restingCopyFor = (marketId)=>{
    if(!marketId || RESTING_HOME.indexOf(marketId) >= 0) return null;
    const row = restingRow(marketId);
    if(!row || (!row.message && !row.cue)) return null;
    let frontier = '';
    try{ const f = (typeof featuredFrontierFor === 'function') ? featuredFrontierFor(marketId) : null;
      frontier = (f && (f.place || f.frontier_market)) ? String(f.place || f.frontier_market) : '';
    }catch(e){}
    const place = String(row.place || marketId);
    const lede = place + ' — ' + String(row.message || '') +
      (row.cue ? ' ' + String(row.cue) : '') +
      (frontier ? ' Featured frontier: ' + frontier + '.' : '');
    return { place, title: place + ' preview', lede, enLine: String(row.message || row.cue || '') };
  };
  try{ window.KODIAK_restingCopyFor = restingCopyFor; }catch(e){}
  function repaintRestingShowcase(){
    try{
      const sel = document.getElementById('locality');
      const hero = document.getElementById('previewHero');
      if(!sel || !hero) return;
      const copy = restingCopyFor(sel.value);
      if(!copy) return;
      hero.querySelectorAll('.ff-figcap-lede').forEach(n=>{ n.textContent = copy.lede; });
      hero.querySelectorAll('.render-set').forEach(n=>{ n.setAttribute('aria-label', copy.title + ' — five export sizes'); });
      hero.querySelectorAll('.render-tile img').forEach(img=>{
        const alt = img.getAttribute('alt') || '';
        img.setAttribute('alt', alt.replace(/ — Park City example$/, ' — ' + copy.place + ' preview'));
      });
      hero.querySelectorAll('.loc-line').forEach(n=>{
        const lang = n.querySelector('.loc-langtag');
        const txt = n.querySelector('.loc-txt');
        if(lang && txt && /english/i.test(lang.textContent || '')){ txt.textContent = copy.enLine; }
        else if(n.parentNode){ n.parentNode.removeChild(n); }
      });
    }catch(e){}
  }
  try{ window.KODIAK_repaintRestingShowcase = repaintRestingShowcase; }catch(e){}
  // Market-driven resting images: on locality change each hero tile swaps to
  // that market's season-aware pick from the baked campaign-art index
  // (js/campaign-art-index.js, built by scripts/build-campaign-web-art.py) —
  // no fetch('/generate'), so the offline page stays offline. Tile i takes
  // dish i so the five sizes stay distinct; markets without campaign art
  // keep the Park City resting example (null picks = keep). DOM order follows
  // window.KODIAK_TILE_ORDER per the frontier-contracts tile contract.
  const HERO_DISHES = ['waffle', 'muffin', 'oatmeal-cup', 'bars', 'brownie'];
  const SEASON_PRIORITY = ['christmas', 'easter', 'fourth-of-july', 'fall', 'halloween', 'thanksgiving'];
  const seasonKeyForMonth = (idx, month)=>{
    try{
      const months = (idx && idx.season_months) || {};
      for(const key of SEASON_PRIORITY){ if((months[key] || []).indexOf(month) >= 0) return key; }
    }catch(e){}
    return null;
  };
  // Same-origin runtime art gets the page build stamp (?v=) so regenerated
  // campaign-web derivatives do not serve stale from cache. Absolute and
  // already-versioned URLs pass through untouched.
  const withVersion = (url)=>{
    try{
      if(!url || /^(https?:|data:|blob:)/i.test(url) || /(^|[?&])v=/.test(url)) return url;
      const v = (typeof window !== 'undefined' && window.KODIAK_VERSION) || '';
      if(!v) return url;
      return url + (url.indexOf('?') >= 0 ? '&v=' : '?v=') + encodeURIComponent(v);
    }catch(e){ return url; }
  };
  const marketHeroPicks = (marketId, month)=>{
    const out = {};
    try{
      const idx = (typeof window !== 'undefined' && window.KODIAK_CAMPAIGN_ART) || null;
      const entry = (idx && idx.markets && idx.markets[marketId]) || null;
      if(!entry) return out;
      const order = (typeof window !== 'undefined' && Array.isArray(window.KODIAK_TILE_ORDER) && window.KODIAK_TILE_ORDER.length)
        ? window.KODIAK_TILE_ORDER : ['blog', '1x1', '16x9', '4x5', '9x16'];
      const seasons = entry.seasons || {};
      const seasonForMonth = month ? seasonKeyForMonth(idx, month) : null;
      let season = (seasonForMonth && seasons[seasonForMonth]) ? seasonForMonth : null;
      if(!season){
        for(const key of SEASON_PRIORITY){ if(seasons[key]){ season = key; break; } }
      }
      if(!season) return out;
      const dishes = seasons[season] || {};
      order.forEach((size, i)=>{
        const dish = HERO_DISHES[i % HERO_DISHES.length];
        if(dishes[dish]) out[size] = withVersion(dishes[dish]);
      });
    }catch(e){}
    return out;
  };
  try{ window.KODIAK_marketHeroPicks = marketHeroPicks; }catch(e){}
  const currentMonth = ()=>{ try{ return new Date().getMonth() + 1; }catch(e){ return 0; } };
  function repaintRestingImages(){
    try{
      const sel = document.getElementById('locality');
      const hero = document.getElementById('previewHero');
      if(!sel || !hero) return;
      const picks = marketHeroPicks(sel.value, currentMonth());
      const sizes = Object.keys(picks);
      if(!sizes.length) return;
      const copy = restingCopyFor(sel.value);
      const place = copy ? copy.place : sel.value;
      sizes.forEach((size)=>{
        hero.querySelectorAll('.render-tile.r-' + size + ' img').forEach(img=>{
          img.setAttribute('src', picks[size]);
          const alt = img.getAttribute('alt') || '';
          const base = alt.replace(/ — .*?(example|preview)$/, '');
          img.setAttribute('alt', (base || 'Market preview') + ' — ' + place + ' preview');
          img.style.display = '';
        });
      });
    }catch(e){}
  }
  try{ window.KODIAK_repaintRestingImages = repaintRestingImages; }catch(e){}
  document.addEventListener('change', /** @param {Event} e */ (e)=>{ const t = e.target instanceof Element ? e.target : null; if(t && t.id==='locality'){ try{ repaintRestingShowcase(); }catch(_e){} try{ repaintRestingImages(); }catch(_e){} } });
  setTimeout(function(){ try{ repaintRestingShowcase(); }catch(e){} try{ repaintRestingImages(); }catch(e){} }, 900);

  // === Platform -> ratio -> dimension matrix ===
  // Authoritative source: data/platforms/platform-matrix.json (offline-tolerant multi-path fetch,
  // same pattern as market-languages.json). Inline fallback below keeps it working file:// offline.
  // module-scoped escape — used by the matrix + platform-copy renderers (the click-handler has its own local one too)
  /** HTML-escape anything — unknown in, string out. */
  /**
   * @param {unknown} s
   * @returns {string}
   */
  const escapeHtml = (s)=> String(s==null?'':s).replace(/[&<>"']/g, (c)=>ESCAPES[c] || c);
  /** @type {Object<string, string>} */
  const ESCAPES = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
  /** @type {Object<string, string>} */
  const PLATFORM_LABELS = {
    facebook:'Facebook', instagram:'Instagram', linkedin:'LinkedIn',
    pinterest:'Pinterest', tiktok:'TikTok', x:'X', youtube:'YouTube', homepage:'Homepage', blog:'Blog'
  };
  // G — provenance/rung-badge foundation, hoisted to IIFE top-level so the
  // click-handler badge + panel AND the exposed heuristics hook share one
  // source (extended, not reinvented). provenanceHeuristics is pure: prov
  // fields in, honest English lines out — absent fields read as
  // "not reported", never a guess, never an invented translation.
  // Engine-key contract (pinned, mirrors the backend ladder): packshot-composite
  // (rung A), stability-restyle (rung B), pillow-compose (rung C), brand-floor
  // (rung D). stability-control-structure is the legacy alias for rung B —
  // kept so older cached responses still read honestly.
  /** @type {Object<string, string>} */
  const ENGINE_LABELS = {
    'packshot-composite':'Packshot composite (asset store verbatim)',
    'stability-restyle':'Stability restyle (GenAI)',
    'stability-control-structure':'Control-structure restyle (Stability)',
    'pillow-compose':'Pillow compose (brand overlay)',
    'pillow-outpaint-fallback':'Pillow pad (placeholder)',
    'stability-outpaint':'Stability outpaint (GenAI)',
    'bedrock:nova-pro-fallback':'Pillow placeholder (image backend unreachable)',
    'brand-floor':'Brand floor (offline fallback)'
  };
  // Origin contract: "backend" marks an envelope the API rendered;
  // "frontend-preview-fallback" marks one the preview synthesized locally.
  // Unknown values fall through to the raw string — never a guess.
  /** @type {Object<string, string>} */
  const ORIGIN_LABELS = {
    'backend':'backend (API render)',
    'frontend-preview-fallback':'frontend (local preview)'
  };
  /** @type {Object<string, string>} */
  const RUNG_LABELS = {
    'A':'Rung A · packshot verbatim',
    'B':'Rung B · Stability restyle',
    'C':'Rung C · Pillow fallback',
    'D':'Rung D · brand-floor fallback'
  };
  // Human labels for the per-platform slugs the copy narrative names, and for
  // the language codes the backend echoes on prov.languages. Absent codes fall
  // through to the raw value (honest), never a guess.
  /** @type {Object<string, string>} */
  const PLATFORM_COPY_LABELS = {
    x:'X', linkedin:'LinkedIn', instagram:'Instagram', tiktok:'TikTok',
    facebook:'Facebook', pinterest:'Pinterest', youtube:'YouTube',
    homepage:'homepage', home:'homepage', blog:'Blog', web:'homepage'
  };
  /** @type {Object<string, string>} */
  const LANGUAGE_LABELS = {
    en:'English', es:'Spanish', ko:'Korean', 'zh':'Chinese', 'zh-cn':'Chinese',
    fr:'French', de:'German', ja:'Japanese', pt:'Portuguese', it:'Italian',
    vi:'Vietnamese', tl:'Tagalog', hi:'Hindi'
  };
  /**
   * @param {unknown} owner
   * @returns {string|null}
   */
  const humanCopyOwner = (owner)=>{
    var o = String(owner||'').toLowerCase();
    if(!o) return null;
    if(o==='backend-preview-fallback') return 'built by the backend preview path';
    if(o.indexOf('backend-')===0) return 'built by the backend ' + o.slice(8).replace(/-/g,' ') + ' path';
    if(o.indexOf('nova')!==-1) return 'built by a live Nova model call';
    return 'built by ' + o.replace(/-/g,' ');
  };
  // provenanceHeuristics(prov[, platformCopy]) — pure, prov fields in, honest
  // plainspoken English out. Called with ONE arg it returns the original four
  // decision lines (rung/engine/seed/fallback) unchanged — that contract is what
  // the vitest suite pins. Called with the platform_copy map as a second arg it
  // ALSO narrates how the campaign was built (copy path, who built it, platforms,
  // languages, retailer theme, mode) from fields the backend ALREADY returns.
  // Nothing is invented: an absent field reads "not reported" / is simply skipped.
  /**
   * @param {unknown} prov backend provenance envelope
   * @param {unknown} [platformCopy] platform_copy map (narrative path)
   * @returns {string[]}
   */
  const provenanceHeuristics = (prov, platformCopy)=>{
    // fresh const, not reassignment: the narrowed envelope keeps its type
    // through every branch below.
    const env = (prov && typeof prov==='object') ? /** @type {Provenance} */ (prov) : /** @type {Provenance} */ ({});
    var lines = [];
    var rung = env.rung || '';
    lines.push('Rung: ' + (RUNG_LABELS[rung] || 'not reported'));
    var eng = (typeof env.engine === 'string' && (ENGINE_LABELS[env.engine] || env.engine)) || '';
    lines.push('Engine: ' + (eng || 'not reported'));
    if(env.seed_selection || env.seed_source){
      lines.push('Seed: ' + [env.seed_selection, env.seed_source ? 'via ' + env.seed_source : null].filter(Boolean).join(' '));
    } else {
      lines.push('Seed: not reported');
    }
    lines.push('Fallback: ' + (env.fallthrough_reason || 'none reported'));
    // ---- build narrative (only when the panel passes the second arg) ----
    // Single-arg callers (tests, the exposed hook used bare) get exactly the four
    // lines above. The lines below are additive and plainspoken for a marketer.
    // NOTE: dispatch is on platformCopy, not arguments.length — this is an arrow
    // function inside a classic IIFE, so arguments would read the IIFE's (always
    // 0) and the two-arg path would be dead. platformCopy===undefined preserves
    // the pinned single-arg contract exactly.
    if(platformCopy === undefined) return lines;
    // Origin leads the panel path: which side rendered this envelope.
    var origin = (env.origin && ORIGIN_LABELS[env.origin]) || env.origin || '';
    lines.push('Origin: ' + (origin || 'not reported'));
    var pc = (platformCopy && typeof platformCopy==='object') ? /** @type {Object<string, {source?: unknown}>} */ (platformCopy) : /** @type {Object<string, {source?: unknown}>} */ ({});
    var pcKeys = Object.keys(pc);
    // Copy path — did a live model write the copy, or did the on-brand template?
    var anyGenerated = pcKeys.some(function(k){ return String((pc[k]||{}).source||'').toLowerCase()==='generated'; });
    var anyFallback = pcKeys.some(function(k){ return String((pc[k]||{}).source||'').toLowerCase()==='fallback'; });
    if(anyFallback){
      // A mixed response is still a template/fallback result: never claim a full
      // live rewrite when even one returned platform fell back.
      lines.push('Copy: on-brand template — deterministic, no model call (keeps the preview under the time budget; the live rewrite runs on the full campaign)');
    } else if(anyGenerated){
      lines.push('Copy: live Nova Micro rewrite — a model wrote each platform post');
    }
    // Who built it — humanize copy_owner without inventing anything.
    var owner = humanCopyOwner(env.copy_owner);
    if(owner) lines.push('Copy path: ' + owner);
    // Platforms — count + human names, from env.platforms the backend returns.
    if(Array.isArray(env.platforms) && env.platforms.length){
      var pnames = env.platforms.map(function(p){ return PLATFORM_COPY_LABELS[String(p).toLowerCase()] || p; });
      lines.push('Platforms: ' + env.platforms.length + ' — ' + pnames.join(', '));
    }
    // Languages — human names, from env.languages.
    if(Array.isArray(env.languages) && env.languages.length){
      var lnames = env.languages.map(function(l){ return LANGUAGE_LABELS[String(l).toLowerCase()] || l; });
      lines.push('Localized: ' + lnames.join(', '));
    }
    // Retailer theme / recipe / mode — surfaced only when the backend names them.
    if(env.retailer) lines.push('Retailer theme: ' + env.retailer);
    if(env.recipe) lines.push('Recipe: ' + env.recipe);
    // Season pairing — the catalog record the request season resolved to, with
    // the table's reason. Surfaced only when the backend names it.
    if(env.recipe_pairing && typeof env.recipe_pairing==='object'){
      const rp = /** @type {{name?: unknown, recipe_id?: unknown, reason?: unknown}} */ (env.recipe_pairing);
      if(rp.name || rp.recipe_id) lines.push('Season pairing: ' + (rp.name || rp.recipe_id) + (rp.reason ? ' — ' + rp.reason : ''));
    }
    if(env.mode) lines.push('Mode: ' + env.mode);
    return lines;
  };
  try{ window.KODIAK_provenanceHeuristics = provenanceHeuristics; }catch(e){}
  // Preview extend polling (top level so tests share it): which tall/wide
  // tiles upgrade, which render is the 1x1 hero, and the mode=extend body.
  // Pure: renders + fields in, no DOM. Tested in preview-extend.test.mjs.
  const extendTargets = (renders)=>{
    if(!Array.isArray(renders)) return [];
    // blog stays a pad: the portrait + wide tiles with an asset-store uri
    // earn a live outpaint.
    return renders.filter(r=>r && (r.ratio==='4x5' || r.ratio==='9x16' || r.ratio==='16x9') && r.s3_uri);
  };
  const extendHero = (renders)=>{
    if(!Array.isArray(renders)) return null;
    return renders.find(r=>r && r.ratio==='1x1' && r.s3_uri) || null;
  };
  const extendBody = (ratio, hero, fields)=>{
    const f = fields || {};
    return {mode:'extend', ratio, hero_s3_uri: hero.s3_uri,
      subject: f.subject || '', product: f.product || 'power-cakes',
      region: f.region || 'us', theme: f.theme || null};
  };
  try{ window.KODIAK_extendTargets = extendTargets; window.KODIAK_extendHero = extendHero; window.KODIAK_extendBody = extendBody; }catch(e){}
  // Request theme order (top level so tests share it): the primary theme
  // first — backend seed/scene behavior unchanged — then every other checked
  // card in DOM order, deduped. Extras ride as data.themes instead of
  // collapsing silently. Pure: primary + list in, ordered list out.
  // Tested in preview-extend.test.mjs.
  const orderThemes = (primary, list)=>{
    const out = [];
    if(primary) out.push(primary);
    (Array.isArray(list) ? list : []).forEach(t=>{ if(t && t !== primary && out.indexOf(t) < 0) out.push(t); });
    return out;
  };
  try{ window.KODIAK_orderThemes = orderThemes; }catch(e){}
  // Per-tile engine mark (top level so tile render, extend swap, and tests
  // share it): the preview ships per-ratio engines in provenance.ratios, and
  // every tile must show which state it is in — a pillow pad and a live
  // stability outpaint never render identically. Pure: engine in, mark out.
  // Tested in preview-extend.test.mjs.
  /**
   * @param {unknown} engine per-ratio engine slug from provenance.ratios
   * @returns {{text: string, cls: string}}
   */
  const tileEngineMark = (engine)=>{
    if(engine==='stability-outpaint') return {text:' · composed', cls:'rt-live'};
    if(engine==='pillow-outpaint-fallback') return {text:' · cover-pad', cls:'rt-pad'};
    if(engine==='primary') return {text:'', cls:''};
    return {text:'', cls:''};
  };
  try{ window.KODIAK_tileEngineMark = tileEngineMark; }catch(e){}
  // Hoisted to IIFE top-level alongside provenanceHeuristics so the
  // click-handler badge, the render-set badge, and tests share one source.
  // Pure: prov fields in, {text, fallback} out. "Rung X" stays verbatim —
  // pollers match on it.
  /**
   * @param {unknown} source engine label or ''
   * @param {unknown} prov backend provenance envelope
   * @returns {{text: string, fallback: boolean}}
   */
  const rungBadge = (source, prov)=>{
    const p = (prov && typeof prov==='object') ? /** @type {Provenance} */ (prov) : /** @type {Provenance} */ ({});
    const rung = p.rung || '';
    const fallback = !!p.fallthrough_reason || rung==='C' || rung==='D';
    const base = RUNG_LABELS[rung] || ((source && String(source).toLowerCase().includes('bedrock')) ? 'Nova Pro' : String(source || 'Nova Pro'));
    const engLabel = (typeof p.engine === 'string' && (ENGINE_LABELS[p.engine] || p.engine)) || '';
    const originLabel = (typeof p.origin === 'string' && (ORIGIN_LABELS[p.origin] || p.origin)) || '';
    var text = (fallback ? 'Fallback — ' : '') + base;
    if(engLabel) text += ' · ' + engLabel;
    if(originLabel) text += ' · ' + originLabel;
    if(p.fallthrough_reason) text += ' (' + p.fallthrough_reason + ')';
    return {text:text, fallback:fallback};
  };
  try{ window.KODIAK_rungBadge = rungBadge; }catch(e){}
  // Inline fallback — ratio order matches the summary copy (1x1, then portrait, then vertical, then landscape).
  /** @type {PlatformMatrix} */
  const PLATFORM_MATRIX_FALLBACK = {
    '1x1':  {label:'Square',    w:1080, h:1080, platforms:['facebook','instagram','x','linkedin','pinterest']},
    '4x5':  {label:'Portrait',  w:1080, h:1350, platforms:['instagram','facebook']},
    '9x16': {label:'Vertical',  w:1080, h:1920, platforms:['instagram','facebook','tiktok','youtube','pinterest']},
    '16x9': {label:'Landscape', w:1920, h:1080, platforms:['youtube','linkedin','x','facebook']},
    'blog': {label:'Blog', w:1200, h:630, platforms:['blog']}
  };
  // live matrix — starts as the fallback, upgraded by the fetched JSON when reachable.
  /** @type {PlatformMatrix} */
  let platformMatrix = PLATFORM_MATRIX_FALLBACK;
  /**
   * @param {string[]|null|undefined} slugs
   * @returns {string[]}
   */
  const platformNames = (slugs)=> (slugs||[]).map(s=>PLATFORM_LABELS[s] || s);
  (async ()=>{
    let matrixLoaded = false;
    for(const url of ['data/platforms/platform-matrix.json','../../data/platforms/platform-matrix.json','./data/platforms/platform-matrix.json']){
      try{
        const r = await fetch(url);
        if(r.ok){
          // isolate the parse: a 200 with a malformed body must not abort the loop or throw uncaught
          let d = null;
          try{ d = await r.json(); }catch(pe){ console.warn('[platform-matrix] malformed JSON at', url, pe instanceof Error ? pe.message : pe); continue; }
          if(d && d.ratios && Object.keys(d.ratios).length){
            // external code: adopt the fetched matrix only when every key is
            // a known TileSize carrying a platforms array, else keep fallback.
            platformMatrix = (typeof window.KODIAK_adoptPlatformMatrix === 'function')
              ? window.KODIAK_adoptPlatformMatrix(d.ratios, PLATFORM_MATRIX_FALLBACK)
              : d.ratios;
            matrixLoaded = true;
            console.log('[platform-matrix] loaded', Object.keys(d.ratios).length, 'ratios from', url);
            // if the matrix explainer is already on-screen, refresh it in place
            try{ renderPlatformMatrix(); }catch(e){}
            // the live matrix is the single source of truth: re-glue the sizes
            // line + true frame ratios to whatever it carries (drift-proofing
            // the "5 sizes" copy against future matrix growth).
            try{ syncOutputSizes(); }catch(e){}
            try{ ffRefreshFrames(document); }catch(e){}
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
  // clean per-tile platform legend for a ratio slug (e.g. "1x1" -> "Facebook · Instagram · X · LinkedIn · Pinterest").
  // the slug arrives from backend JSON, so it crosses the boundary validator first.
  /**
   * @param {unknown} ratio backend ratio slug
   * @returns {string[]}
   */
  function platformsForRatio(ratio){
    const size = (typeof window.KODIAK_tileSizeFromString === 'function')
      ? window.KODIAK_tileSizeFromString(ratio)
      : (typeof ratio === 'string' ? /** @type {TileSize} */ (ratio) : null);
    if (size === null) return [];
    const row = platformMatrix[size];
    return row ? platformNames(row.platforms) : [];
  }
  // Platforms now live once on the tile caps (each cap carries its ratio's
  // shape, dims, and platform chips), so the side matrix is retired: this
  // keeps the hero grid full-width and removes the duplicated panel.
  // Idempotent: removes any existing matrix so re-render never stacks.
  function renderPlatformMatrix(){
    const old = document.getElementById('platformMatrix');
    if(old) old.remove();
  }
  // expose so the offline canvas render() (defined in the earlier script scope) can
  // clear any matrix after it clears #preview; the explainer panel is retired.
  window.__renderPlatformMatrix = renderPlatformMatrix;
  // no matrix on load: the hero tile grid is the default preview content.
  try{ renderPlatformMatrix(); }catch(e){}

  // === ff-filmstrip + #ffLightbox (top level so the resting strip and every
  // generated set share them). The strip is one horizontal row of true-ratio
  // thumbnails; the lightbox is dependency-free, buttons only.
  /**
   * @returns {boolean}
   */
  function ffReducedMotion(){
    try{ return !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches); }catch(e){ return false; }
  }
  // Reconcile the "5 sizes" copy drift: the heading line is rendered from the
  // live platformMatrix (single source of truth), not a hardcoded count, so a
  // matrix change can never strand the copy. Static fallback in markup matches.
  function syncOutputSizes(){
    const el = document.getElementById('outputSizes');
    if(!el) return;
    try{
      const keys = Object.keys(platformMatrix || {});
      if(keys.length) el.textContent = keys.length + ' sizes \u2014 ' + keys.join(', ');
    }catch(e){}
  }
  // True aspect ratios, matrix-driven: every slot frame takes its ratio's live
  // w/h from platformMatrix (CSS per-ratio fallbacks cover no-JS paint).
  /**
   * @param {ParentNode} root
   * @returns {void}
   */
  function ffRefreshFrames(root){
    try{
      Array.from((root || document).querySelectorAll('.ff-filmstrip__slot[data-ratio]')).forEach((slot)=>{
        const ratio = slot.getAttribute('data-ratio');
        const size = (typeof window.KODIAK_tileSizeFromString === 'function')
          ? window.KODIAK_tileSizeFromString(ratio) : ratio;
        const row = (size && platformMatrix[size]) || null;
        const frame = /** @type {HTMLElement|null} */ (slot.querySelector('.ff-filmstrip__frame'));
        if(row && frame){ try{ frame.style.aspectRatio = row.w + '/' + row.h; }catch(e){} }
      });
    }catch(e){}
  }
  /** @type {Array<{src: string, alt: string, cap: string}>} */
  let ffLightboxItems = [];
  let ffLightboxIndex = 0;
  /** @type {HTMLElement|null} */
  let ffLightboxOpener = null;
  /**
   * @param {number} delta
   * @returns {void}
   */
  function ffLightboxStep(delta){
    if(!ffLightboxItems.length) return;
    ffLightboxIndex = (ffLightboxIndex + delta + ffLightboxItems.length) % ffLightboxItems.length;
    ffLightboxShow();
  }
  function ffLightboxShow(){
    const box = document.getElementById('ffLightbox');
    if(!box) return;
    const item = ffLightboxItems[ffLightboxIndex] || {src:'', alt:'', cap:''};
    const img = box.querySelector('.ff-lightbox__img');
    const cap = box.querySelector('.ff-lightbox__cap');
    if(img){ img.setAttribute('src', item.src || ''); img.setAttribute('alt', item.alt || ''); }
    if(cap){ cap.textContent = item.cap || ''; }
    const multi = ffLightboxItems.length > 1;
    const prev = /** @type {HTMLButtonElement|null} */ (box.querySelector('.ff-lightbox__prev'));
    const next = /** @type {HTMLButtonElement|null} */ (box.querySelector('.ff-lightbox__next'));
    if(prev) prev.disabled = !multi;
    if(next) next.disabled = !multi;
  }
  /**
   * @param {KeyboardEvent} e
   * @returns {void}
   */
  function ffLightboxKeys(e){
    const box = document.getElementById('ffLightbox');
    if(!box || box.hidden) return;
    if(e.key === 'Escape'){ e.preventDefault(); ffLightboxClose(); return; }
    if(e.key === 'ArrowLeft'){ e.preventDefault(); ffLightboxStep(-1); return; }
    if(e.key === 'ArrowRight'){ e.preventDefault(); ffLightboxStep(1); return; }
    if(e.key === 'Tab'){
      // focus trap across the buttons only — the image is never focusable.
      const btns = Array.from(box.querySelectorAll('button')).filter((b)=>!b.disabled);
      if(!btns.length) return;
      const first = btns[0], last = btns[btns.length - 1];
      if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    }
  }
  /**
   * @param {Array<{src: string, alt: string, cap: string}>} items
   * @param {number} index
   * @param {HTMLElement|null} opener
   * @returns {void}
   */
  function ffLightboxOpen(items, index, opener){
    if(!Array.isArray(items) || !items.length) return;
    const box = document.getElementById('ffLightbox');
    if(!box) return;
    ffLightboxItems = items;
    ffLightboxIndex = Math.min(Math.max(index || 0, 0), items.length - 1);
    try{ ffLightboxOpener = opener || /** @type {HTMLElement|null} */ (document.activeElement); }catch(e){ ffLightboxOpener = null; }
    box.hidden = false;
    try{ box.classList.add('is-open'); }catch(e){}
    ffLightboxShow();
    try{ const c = /** @type {HTMLElement|null} */ (box.querySelector('.ff-lightbox__close')); if(c) c.focus(); }catch(e){}
    document.addEventListener('keydown', ffLightboxKeys, true);
  }
  function ffLightboxClose(){
    const box = document.getElementById('ffLightbox');
    if(box){ box.hidden = true; try{ box.classList.remove('is-open'); }catch(e){} }
    document.removeEventListener('keydown', ffLightboxKeys, true);
    try{ if(ffLightboxOpener && ffLightboxOpener.focus) ffLightboxOpener.focus(); }catch(e){}
    ffLightboxOpener = null;
  }
  /**
   * Collect lightbox items from a strip in slot order (caption mirrors the cap).
   * @param {HTMLElement} strip
   * @returns {Array<{src: string, alt: string, cap: string}>}
   */
  function ffStripItems(strip){
    return Array.from(strip.querySelectorAll('.ff-filmstrip__slot')).map((slot)=>{
      const img = slot.querySelector('img');
      const capBits = ['b', '.dims', '.rt-platforms'].map((sel)=>{
        const n = slot.querySelector('.render-cap ' + sel);
        return n ? (n.textContent || '').trim() : '';
      }).filter(Boolean);
      return {src: (img && img.getAttribute('src')) || '', alt: (img && img.getAttribute('alt')) || '', cap: capBits.join(' \u00B7 ')};
    }).filter((it)=>!!it.src);
  }
  /**
   * Wire arrows, dots, track keys, and thumb->lightbox for one strip. Idempotent.
   * @param {HTMLElement} strip
   * @returns {void}
   */
  function wireFilmstrip(strip){
    if(!strip || strip.dataset.ffWired) return;
    strip.dataset.ffWired = '1';
    const track = /** @type {HTMLElement|null} */ (strip.querySelector('.ff-filmstrip__track'));
    const prev = strip.querySelector('.ff-filmstrip__arrow--prev');
    const next = strip.querySelector('.ff-filmstrip__arrow--next');
    const slotsOf = ()=>Array.from(strip.querySelectorAll('.ff-filmstrip__slot'));
    const dotsOf = ()=>Array.from(strip.querySelectorAll('.ff-filmstrip__dot'));
    /**
     * @param {number} i
     * @returns {void}
     */
    const markDot = (i)=>{
      dotsOf().forEach((d, j)=>{ d.setAttribute('aria-current', j === i ? 'true' : 'false'); });
    };
    /**
     * @param {number} i
     * @returns {void}
     */
    const scrollToSlot = (i)=>{
      const s = /** @type {HTMLElement|null} */ (slotsOf()[i] || null);
      if(!s || !track) return;
      markDot(i);
      try{
        track.scrollTo({left: s.offsetLeft - track.offsetLeft - 8, behavior: ffReducedMotion() ? 'auto' : 'smooth'});
      }catch(e){ try{ track.scrollLeft = s.offsetLeft - track.offsetLeft - 8; }catch(_){} }
    };
    /**
     * @param {number} dir
     * @returns {void}
     */
    const stepBy = (dir)=>{
      const first = /** @type {HTMLElement|null} */ (slotsOf()[0] || null);
      const w = first ? (first.offsetWidth + 10) : 200;
      if(!track) return;
      try{ track.scrollBy({left: dir * w, behavior: ffReducedMotion() ? 'auto' : 'smooth'}); }
      catch(e){ try{ track.scrollLeft += dir * w; }catch(_){} }
    };
    if(prev) prev.addEventListener('click', ()=>stepBy(-1));
    if(next) next.addEventListener('click', ()=>stepBy(1));
    dotsOf().forEach((d, i)=>{ d.addEventListener('click', ()=>scrollToSlot(i)); });
    if(track){
      // keep overflow-x:auto keyboard operable: arrows move a slot, Home/End jump.
      track.addEventListener('keydown', (/** @param {KeyboardEvent} e */ e)=>{
        if(e.key === 'ArrowLeft'){ e.preventDefault(); stepBy(-1); }
        else if(e.key === 'ArrowRight'){ e.preventDefault(); stepBy(1); }
        else if(e.key === 'Home'){ e.preventDefault(); scrollToSlot(0); }
        else if(e.key === 'End'){ e.preventDefault(); scrollToSlot(slotsOf().length - 1); }
      });
      // dots follow free scroll (nearest slot wins).
      let ticking = false;
      track.addEventListener('scroll', ()=>{
        if(ticking) return;
        ticking = true;
        try{
          requestAnimationFrame(()=>{
            ticking = false;
            try{
              const x = track.scrollLeft + 8;
              const sl = slotsOf();
              let best = 0;
              sl.forEach((s, i)=>{
                const se = /** @type {HTMLElement} */ (s);
                if(se.offsetLeft - track.offsetLeft <= x + se.offsetWidth / 2) best = i;
              });
              markDot(best);
            }catch(e){}
          });
        }catch(e){ ticking = false; }
      }, {passive: true});
    }
    Array.from(strip.querySelectorAll('.ff-filmstrip__thumb')).forEach((thumb)=>{
      thumb.addEventListener('click', ()=>{
        const slot = thumb.closest('.ff-filmstrip__slot');
        const idx = slot ? slotsOf().indexOf(slot) : 0;
        ffLightboxOpen(ffStripItems(strip), Math.max(idx, 0), /** @type {HTMLElement} */ (thumb));
      });
    });
    ffRefreshFrames(strip);
  }
  try{ window.KODIAK_wireFilmstrip = wireFilmstrip; }catch(e){}
  try{ window.KODIAK_ffLightboxOpen = ffLightboxOpen; }catch(e){}
  // Static lightbox controls (the #ffLightbox node lives outside #preview so
  // re-renders never remove it — wire once here).
  try{
    document.getElementById('ffLightboxPrev')?.addEventListener('click', ()=>ffLightboxStep(-1));
    document.getElementById('ffLightboxNext')?.addEventListener('click', ()=>ffLightboxStep(1));
    document.getElementById('ffLightboxClose')?.addEventListener('click', ffLightboxClose);
    document.getElementById('ffLightbox')?.addEventListener('click', (e)=>{
      const t = /** @type {HTMLElement|null} */ (e.target);
      if(t && t.id === 'ffLightbox') ffLightboxClose();
    });
  }catch(e){}
  // Resting strip + sizes line glue to the live matrix on first paint.
  try{ syncOutputSizes(); }catch(e){}
  try{ ffRefreshFrames(document); }catch(e){}
  try{ Array.from(document.querySelectorAll('.ff-filmstrip')).forEach((s)=>wireFilmstrip(/** @type {HTMLElement} */ (s))); }catch(e){}

  // Compose layers — independently-selectable, ALL OFF by default. Reads the creative-direction
  // checkbox cards into the {product_image, retailer, partner_logo, conservation_badge} contract the /generate backend
  // normalizes; an empty object means a clean standalone image. Each card drives its own mark
  // directly — no standalone mark flags. Retailer composes iff a SPECIFIC retailer is checked
  // (window.__activeRetailerValue, most-recent checked wins; All alone -> brief only, no mark).
  window.__selectedLayers = function(){
    /** @type {Record<string, unknown>} */
    const layers = {};
    try{
      if((/** @type {HTMLInputElement|null} */ (document.getElementById('layerProduct')))?.checked) layers.product_image = true;
      const retailerVal = (typeof window.__activeRetailerValue === 'function' && window.__activeRetailerValue()) || null;
      if(retailerVal) layers.retailer = retailerVal;
      if((/** @type {HTMLInputElement|null} */ (document.querySelector('#promptChips .ff-check-card__input[data-theme="us-ski-snowboard"]')))?.checked) layers.partner_logo = true;
      if((/** @type {HTMLInputElement|null} */ (document.querySelector('#promptChips .ff-check-card__input[data-theme="wild-grizzly-bears"]')))?.checked) layers.conservation_badge = true;
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
    // the resting showcase (#previewHero) owns the first impression — never
    // append a second competing default hero on top of it. Offline/no-hero
    // path below stays intact.
    if(!preview || document.getElementById('defaultHeroTile') || document.getElementById('previewHero')) return;
    const tile = document.createElement('div');
    tile.className = 'tile tile--default-hero';
    tile.id = 'defaultHeroTile';
    tile.style.cssText = 'grid-column:1/-1;max-width:640px;margin:0 auto';
    const img = document.createElement('img');
    img.src = DEFAULT_HERO_SRC;
    img.alt = 'Kodiak Cakes frontier morning — cabin table with a protein stack, natural light';
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
    const card = /** @type {HTMLDetailsElement|null} */ (document.getElementById('previewCard'));
    if(card && !card.open){ card.open = true; }
  }
  // Closed-card fold guard: a closed #previewCard must not lay out its .body
  // (author display rules beat the UA closed-details rule, so the ~1991px body
  // paints clipped under card overflow). Inline display + hidden win over any
  // author rule; the toggle listener re-syncs on every open/close so
  // openPreviewCard() on Create and the resting renderDefaultHero content show
  // correctly when reopened.
  function syncPreviewCardBody(){
    const card = /** @type {HTMLDetailsElement|null} */ (document.getElementById('previewCard'));
    if(!card) return;
    const body = /** @type {HTMLElement|null} */ (card.querySelector(':scope > .body'));
    if(!body) return;
    if(card.open){ body.hidden = false; body.style.display = ''; }
    else { body.hidden = true; body.style.display = 'none'; }
  }
  try{
    const __previewCard = document.getElementById('previewCard');
    if(__previewCard){ __previewCard.addEventListener('toggle', syncPreviewCardBody); }
    syncPreviewCardBody();
  }catch(e){}

  // Render per-platform messaging copy — an accordion of native <details>, one per platform.
  // Consumes /generate and /campaigns/platform-copy response entries without dropping
  // platform-specific fields such as X post or YouTube title/description.
  const PLATFORM_COPY_ORDER = ['homepage','blog','instagram','facebook','tiktok','youtube','pinterest','x','linkedin'];
  let platformCopyGeneration = 0;
  /** @type {Object<string, unknown>} */
  let renderedPlatformCopy = {};
  /**
   * @param {Object<string, unknown>} platformCopy
   * @returns {string[]}
   */
  function orderedPlatformCopyKeys(platformCopy){
    return PLATFORM_COPY_ORDER.filter(k=>platformCopy[k]).concat(
      Object.keys(platformCopy).filter(k=>PLATFORM_COPY_ORDER.indexOf(k)<0)
    );
  }
  /**
   * @param {string} k
   * @param {unknown} entry backend copy entry
   * @returns {string}
   */
  function platformCopyEntryHtml(k, entry){
    const c = (entry && typeof entry==='object') ? /** @type {PlatformCopyEntry} */ (entry) : /** @type {PlatformCopyEntry} */ ({});
    // one signature, not a union: unknown in, unknown out — escapeHtml stringifies downstream.
    const clean = /** @type {(x: unknown) => unknown} */ ((typeof window.KODIAK_brandClean==='function') ? window.KODIAK_brandClean : function(x){ return x; });
    const name = c.label || PLATFORM_LABELS[k] || k;
    const title = clean(c.headline!=null ? c.headline : (c.title!=null ? c.title : ''));
    const bodyTxt = clean(c.body!=null ? c.body : (c.description!=null ? c.description : ''));
    const postTxt = clean(c.post!=null ? c.post : '');
    const tags = clean(Array.isArray(c.hashtags) ? c.hashtags.join(' ') : (c.hashtags!=null ? c.hashtags : ''));
    const src = String(c.source||'').toLowerCase()==='generated' ? 'generated' : 'fallback';
    const srcTitle = src==='generated'
      ? 'Written by a live Nova Micro model call'
      : 'On-brand template (no model call) — deterministic copy retained as the honest fallback';
    const srcNote = src==='fallback'
      ? '<span class="pc-src-note">on-brand template (no model call) — live rewrite may be unavailable</span>'
      : '';
    const srcPill = '<span class="pc-src '+src+'" title="'+escapeHtml(srcTitle)+'">source: '+escapeHtml(src)+'</span>';
    return '<summary>'+escapeHtml(name)+srcPill+'</summary>'+
      '<div class="pc-body">'+srcNote+
      (title? '<p class="pc-title">'+escapeHtml(title)+'</p>':'')+
      (bodyTxt? '<p class="pc-text">'+escapeHtml(bodyTxt)+'</p>':'')+
      (postTxt? '<p class="pc-text pc-post">'+escapeHtml(postTxt)+'</p>':'')+
      (tags? '<p class="pc-tags">'+escapeHtml(tags)+'</p>':'')+
      '</div>';
  }
  /**
   * @param {string} text
   * @param {boolean} visible
   */
  function setPlatformCopyStatus(text, visible){
    const status = document.getElementById('platformCopyStatus');
    if(!status) return;
    status.textContent = text || '';
    status.hidden = !visible;
  }
  /**
   * @param {Object<string, unknown>} nextCopy
   */
  function updatePlatformCopyPanel(nextCopy){
    const panel = document.getElementById('platformCopyPanel');
    if(!panel || !nextCopy || typeof nextCopy!=='object') return false;
    Object.keys(nextCopy).forEach(k=>{
      const entry = (nextCopy[k] && typeof nextCopy[k]==='object' && !Array.isArray(nextCopy[k])) ? nextCopy[k] : {};
      renderedPlatformCopy[k] = Object.assign({}, renderedPlatformCopy[k] || {}, entry);
    });
    orderedPlatformCopyKeys(renderedPlatformCopy).forEach(k=>{
      let details = Array.from(panel.querySelectorAll('details')).find(d=>d.dataset.platform===k);
      if(!details){
        details = document.createElement('details');
        details.dataset.platform = k;
      }
      details.innerHTML = platformCopyEntryHtml(k, renderedPlatformCopy[k]);
      // append moves an existing node without replacing it, preserving open state
      panel.appendChild(details);
    });
    return true;
  }
  /**
   * @param {unknown} platformCopy
   * @returns {number}
   */
  function renderPlatformCopy(platformCopy){
    const preview = document.getElementById('preview');
    if(!preview) return 0;
    platformCopyGeneration++;
    renderedPlatformCopy = {};
    const old = document.getElementById('platformCopyPanel');
    if(old) old.remove();
    if(!platformCopy || typeof platformCopy!=='object') return platformCopyGeneration;
    const keys = orderedPlatformCopyKeys(/** @type {Object<string, unknown>} */ (platformCopy));
    if(!keys.length) return platformCopyGeneration;
    renderedPlatformCopy = /** @type {Object<string, unknown>} */ (Object.assign({}, platformCopy));
    const panel = document.createElement('div');
    panel.className = 'platform-copy';
    panel.id = 'platformCopyPanel';
    panel.innerHTML = '<div class="pc-head">Per-platform messaging <span id="platformCopyStatus" class="pc-status" role="status" aria-live="polite" hidden></span></div>';
    const anchor = document.getElementById('provenancePanel') || document.getElementById('previewDownloadRow') || preview;
    anchor.parentNode?.insertBefore(panel, anchor.nextSibling);
    updatePlatformCopyPanel(/** @type {Object<string, unknown>} */ (platformCopy));
    return platformCopyGeneration;
  }

  /**
   * @param {unknown} market
   * @param {unknown} provenance
   * @returns {string[]}
   */
  function platformCopyLanguages(market, provenance){
    const provLangs = (provenance && typeof provenance === 'object') ? /** @type {{languages?: unknown}} */ (provenance).languages : undefined;
    const raw = Array.isArray(provLangs) && provLangs.length
      ? provLangs
      : (typeof marketLangsFor==='function' ? marketLangsFor(typeof market === 'string' ? market : '') : []);
    const codes = raw.map(l=>{
      if(typeof l==='string') return l;
      return l && (l.translate_code || l.lang_code || l.code);
    }).filter(Boolean).map(code=>String(code).toLowerCase());
    return Array.from(new Set(['en'].concat(codes)));
  }
  /**
   * @param {{baseMessage?: unknown, productName?: unknown, market?: unknown, provenance?: unknown}} [options]
   * @returns {Promise<boolean>}
   */
  async function sharpenPlatformCopy(options){
    options = options || {};
    if((location.protocol==='file:') || ['127.0.0.1','localhost'].includes(location.hostname)) return false;
    const generation = platformCopyGeneration;
    if(!generation || !document.getElementById('platformCopyPanel')) return false;
    const body = {
      base_message: String(options.baseMessage || '').trim(),
      product_name: String(options.productName || '').trim(),
      market: String(options.market || '').trim(),
      languages: platformCopyLanguages(options.market, options.provenance)
    };
    if(!body.base_message || !body.product_name || !body.market) return false;
    setPlatformCopyStatus('sharpening copy...', true);
    const controller = new AbortController();
    const timeoutId = setTimeout(()=>controller.abort(), 20000);
    try{
      const response = await fetch('/campaigns/platform-copy', {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body), signal:controller.signal
      });
      if(!response.ok) throw new Error('platform copy HTTP '+response.status);
      const json = await response.json();
      const returned = json && json.platform_copy;
      if(!returned || typeof returned!=='object' || Array.isArray(returned) || !Object.keys(returned).length ||
          Object.keys(returned).some(k=>!returned[k] || typeof returned[k]!=='object' || Array.isArray(returned[k]))) throw new Error('malformed platform copy response');
      if(generation !== platformCopyGeneration) return false;
      updatePlatformCopyPanel(returned);
      setPlatformCopyStatus('copy sharpened', true);
      try{ if(typeof window.__kodiakUpdateProvenanceCopy==='function') window.__kodiakUpdateProvenanceCopy(renderedPlatformCopy); }catch(e){}
      return true;
    }catch(err){
      if(generation !== platformCopyGeneration) return false;
      /** @type {Object<string, unknown>} */
      const fallback = {};
      Object.keys(renderedPlatformCopy).forEach(k=>{ fallback[k] = Object.assign({}, renderedPlatformCopy[k], {source:'fallback'}); });
      updatePlatformCopyPanel(fallback);
      setPlatformCopyStatus('template copy retained', true);
      try{ if(typeof window.__kodiakUpdateProvenanceCopy==='function') window.__kodiakUpdateProvenanceCopy(renderedPlatformCopy); }catch(e){}
      return false;
    }finally{
      clearTimeout(timeoutId);
    }
  }
  try{ window.KODIAK_sharpenPlatformCopy = sharpenPlatformCopy; }catch(e){}

  // #281 — copy BEFORE image. The copy-first panel paints at Create time from the
  // REAL request inputs (phase 'driving') and upgrades from the REAL response
  // (phase 'used'). It never invents marketing copy: driving shows only what the
  // user supplied + selected; used shows only what the backend returned, plus
  // request/response divergence flags computed from real echoed fields.
  /**
   * @param {CopyPanelArg} arg
   * @returns {void}
   */
  function paintCopyPanel(arg){
    const preview = document.getElementById('preview');
    if(!preview || !arg) return;
    let panel = document.getElementById('copyFirstPanel');
    if(arg.phase==='driving'){
      // KODIAK-forbidden-in-copy law: user/seed briefs predate the law — clean at paint time.
      try{ if(typeof window.KODIAK_brandClean==='function' && arg.brief) arg.brief = window.KODIAK_brandClean(arg.brief); }catch(e){}
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
    const driving = /** @type {{theme?: unknown}} */ ((arg.driving || window.__lastCopyDriving) || {});
    const json = /** @type {{provenance?: unknown, theme?: unknown, source?: unknown, platform_copy?: unknown}} */ (arg.json || {});
    const prov = /** @type {{art_headline?: unknown, deferred?: unknown, theme?: unknown}} */ ((json.provenance && typeof json.provenance==='object') ? json.provenance : {});
    const flags = [];
    const reqTheme = driving.theme || null;
    const gotTheme = json.theme || prov.theme || null;
    if(reqTheme && gotTheme && String(gotTheme)!==String(reqTheme)) flags.push('theme mismatch — requested '+reqTheme+' but the response reports '+gotTheme+'; imagery may not follow the copy');
    if(reqTheme && !gotTheme) flags.push('theme dropped — requested '+reqTheme+' but the response names no theme; imagery may be generic');
    const src = String(json.source||'');
    const isFallback = /^brand-floor/i.test(src);
    if(isFallback) flags.push('render miss — fallback pixels ('+src+'), not the campaign; no copy was used');
    const pc = /** @type {Object<string, {headline?: unknown, title?: unknown}>} */ ((json.platform_copy && typeof json.platform_copy==='object') ? json.platform_copy : {});
    const pcKeys = Object.keys(pc);
    const deferred = Array.isArray(prov.deferred) ? prov.deferred : [];
    let usedHtml;
    if(isFallback){
      usedHtml = '<p class="pc-text">No copy was used — the backend returned fallback pixels.</p>';
    } else if(prov.art_headline || pcKeys.length){
      // KODIAK-forbidden-in-copy law: backend copy predates the law — clean at paint time.
      // one signature, not a union: unknown in, unknown out — escapeHtml stringifies downstream.
      var cleanUsed = /** @type {(x: unknown) => unknown} */ ((typeof window.KODIAK_brandClean==='function') ? window.KODIAK_brandClean : function(x){ return x; });
      usedHtml = (prov.art_headline ? '<p class="pc-title">'+escapeHtml(cleanUsed(prov.art_headline))+'</p>' : '')+
        (pcKeys.length ? '<p class="pc-text">'+pcKeys.map(k=>escapeHtml(k+': '+cleanUsed(((pc[k]||{}).headline||(pc[k]||{}).title)||''))).join('<br>')+'</p>' : '<p class="pc-text">Full platform copy deferred — ships with Generate Campaign.</p>');
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
  // page contract: the generate button always ships with this markup.
  const btn = /** @type {HTMLButtonElement} */ (document.getElementById('generateCampaign'));
  if(btn){
    btn.addEventListener('click', async ()=>{
      let brief = (/** @type {HTMLInputElement|null} */ (document.getElementById('campaignBrief')))?.value.trim();
      if(!brief){ brief = 'Keep It Wild — Feeding Epic Days & Wilder Lives • Nourishment for Today\'s Frontier — 100% whole grains, 14g protein — quick-test'; }
      // D. seasonal context — optional. If a season/month/holiday is chosen, fold a hint into the brief
      // that /generate receives (empty selection adds nothing). Matches how activeTheme threads context.
      const activeSeason = window.__activeSeason || null;
      if(activeSeason && !new RegExp('season:\\s*'+activeSeason.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'),'i').test(brief)){
        brief = brief + ' — season: ' + activeSeason;
      }
      // 4. user-supplied assets: staged locally, uploaded to the asset store on hosted origins
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
      /** @type {string[]} */
      let selectedProducts = /** @type {HTMLInputElement[]} */ (Array.from(document.querySelectorAll('#productChooser .sku-check:checked'))).map(c=>c.value);
      const hadExplicitSelection = selectedProducts.length > 0;
      // If local and glimmer up, let it rank SKUs intelligently (not random)
      if(!selectedProducts.length && window.GlimmerProxy?.isLocal){
        try{ const ranked = window.GlimmerProxy && window.GlimmerProxy.pickSkus ? await window.GlimmerProxy.pickSkus(brief, skuList, 3) : null; if(Array.isArray(ranked)) selectedProducts = /** @type {string[]} */ (ranked); }catch(e){}
      }
      const products = selectedProducts.length ? selectedProducts : [...skuList].sort(()=>0.5-Math.random()).slice(0,3);
      const audience = 'KODIAK design guide audience — see UX Profiles (23 cards)';
      // Nearest Frontier resolves from the 1:1 market-to-featured-frontier mapping
      // (#257: featuredFrontierFor in data-core.js, canonical — the backend JSON
      // is generated from it) — no hardcoded market checks.
      let selectedLoc = null;
      try{ const locVal=(/** @type {HTMLInputElement|null} */ (document.getElementById('locality')))?.value || 'US-MW-PARKCITY-84098'; selectedLoc = places.find(p=>p.market===locVal) || places.find(p=>p.market==='US-MW-PARKCITY-84098') || places[0]; }catch(e){ selectedLoc = {place:'Park City, Utah 84098', market:'US-MW-PARKCITY-84098'}; }
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
      /** @param {unknown} s @returns {string} */
      const norm = (s)=>String(s||'').toLowerCase().trim();
      /** @param {string} name @returns {string} */
      const slugFallback = (name)=>{
        // drop standalone "and" / "&" the way the map keys do, then hyphenate
        const s = norm(name).replace(/&/g,' ').replace(/\band\b/g,' ');
        return s.replace(/[^a-z0-9]+/g,'-').replace(/^-+|-+$/g,'');
      };
      /** @param {string} name @returns {string} */
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
      /** @type {Object<string, string>} */
      const THEME_LABELS = {
        'recipe-cards':'Recipe cards','localized-costco':'Localized Costco',
        'localized-publix':'Localized Publix','localized-target':'Localized Target',
        'localized-all':'All retailers',
        'kodiak-subscription':'Kodiak Cakes subscription',
        'riff-on-past-content':'Riff on past content',
        'wild-grizzly-bears':'Wild Grizzly Bears',
        'us-ski-snowboard':'US Ski & Snowboard'
      };
      const themeLabel = activeTheme ? (THEME_LABELS[activeTheme] || activeTheme) : null;
      // Copy sidecars (#199) — campaign copy as text/CSV downloads, never baked into
      // pixels. Remembers the backend copy_sidecar (or platform_copy) per response.
      /**
       * @param {string} kind
       * @returns {void}
       */
      const downloadSidecar = (kind)=>{
        const sc = /** @type {Object<string, unknown>} */ (window.__lastSidecar || {});
        const text = sc[kind] ? String(sc[kind]) : 'Kodiak Cakes campaign copy — hit Create first for this campaign\u2019s sidecar.\n';
        const blob = new Blob([text], {type: kind==='csv' ? 'text/csv' : 'text/plain'});
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = kind==='csv' ? 'Kodiak-Cakes-copy.csv' : 'Kodiak-Cakes-copy.txt';
        document.body.appendChild(a); a.click();
        setTimeout(()=>{ URL.revokeObjectURL(a.href); a.remove(); }, 500);
      };
      /** @param {unknown} j @returns {void} */
      const rememberSidecar = (j)=>{
        try{
          const jj = /** @type {{copy_sidecar?: unknown, platform_copy?: unknown, layers?: unknown}} */ ((j && typeof j === 'object') ? j : {});
          window.__lastSidecar = jj.copy_sidecar || null;
          window.__lastPlatformCopy = jj.platform_copy || {};
          window.__lastLayers = jj.layers || {};
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
          primary.addEventListener('click', function(){ if(typeof window.downloadAssetPack==='function') window.downloadAssetPack(); });
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
          pack.addEventListener('click', function(){ if(typeof window.downloadAssetPack==='function') window.downloadAssetPack({pack:true}); });
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
      /**
       * @param {string} imageUrl
       * @param {unknown} source engine label or '';
       * @param {ShowOpts} [opts]
       * @returns {void}
       */
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
        meta.innerHTML = `<b>Kodiak Cakes composed hero</b><div class="small">${prodLine}source: ${label} · ${selectedLoc.market}${themeLine} · ${brief.slice(0,80)}</div>`;
        tile.appendChild(meta);
        preview.appendChild(tile);
        // source badge above the preview — provenance-driven, fallbacks flagged (#173)
        let badge = document.getElementById('genSourceBadge');
        if(!badge){ badge=document.createElement('span'); badge.id='genSourceBadge'; badge.className='badge gen-badge'; preview.parentNode?.insertBefore(badge, preview); }
        const rb = rungBadge(source, opts.provenance);
        paintRungBadge(badge, rb);
        if(opts.themeLabel || opts.theme) badge.textContent += ' · theme: ' + (opts.themeLabel || opts.theme);
        revealDownloadActions();
        try{ if(typeof window.__kodiakRevealCampaign==='function') window.__kodiakRevealCampaign(); }catch(e){}
      };
      // Human labels for the render ratios and the engine.
      // teaching note (frontier totality: keyed by the whole TileSize union — add a
      // size and the checker lists every table you must extend; exhaustiveness by keys).
      // decision: Object<TileSize,...>, not Object<string,...> — string keys would
      // silently accept a missing size.
      /** @type {Object<TileSize, {name: string, cls: string}>} */
      const RATIO_LABELS = {
        '1x1': {name:'Feed', cls:'r-1x1'},
        '4x5': {name:'Portrait', cls:'r-4x5'},
        '9x16': {name:'Vertical', cls:'r-9x16'},
        '16x9': {name:'Landscape', cls:'r-16x9'},
        '2x3': {name:'Story', cls:'r-2x3'},
        'blog': {name:'Blog', cls:'r-blog'}
      };
      // Unit 2 (#173) — honest rung badge. Provenance drives the label; any
      // fallback rung (C/D or a fallthrough_reason) gets flagged, never silently
      // relabeled "Nova Pro". Fallback sightings become counted facts.
      /**
       * @param {unknown} source
       * @param {unknown} prov backend provenance envelope
       * @returns {{text: string, fallback: boolean}}
       */
      /**
       * @param {HTMLElement} badge
       * @param {{text: string, fallback: boolean}} rb
       * @returns {void}
       */
      const paintRungBadge = (badge, rb)=>{
        badge.textContent = rb.text;
        badge.classList.remove('is-live', 'is-fallback');
        badge.classList.add(rb.fallback ? 'is-fallback' : 'is-live');
      };
      /** @param {unknown} s @returns {string} */
      const escapeHtml = (s)=> String(s==null?'':s).replace(/[&<>"']/g, (c)=>ESCAPES[c] || c);
      // render one labeled tile per ratio at real aspect ratio; records the 1x1 as the hero.
      /**
       * @param {RenderItem[]} renders
       * @param {ShowOpts} [opts]
       * @returns {void}
       */
      const showRenderSet = (renders, opts)=>{
        opts = opts || {};
        const preview = document.getElementById('preview');
        if(!preview) return;
        preview.innerHTML = '';
        // keep the platform explainer at the top of the preview even after a generate
        try{ renderPlatformMatrix(); }catch(e){}
        // Live results ride the same ff-filmstrip pattern as the resting hero:
        // one horizontal track of true-ratio thumbnails (click opens the full-size
        // lightbox) instead of the old vertically-stacked grid. render-set /
        // render-tile / render-frame / render-cap aliases are kept so the extend
        // swap, parallax, and TILE_ORDER contracts keep working.
        const strip = document.createElement('div');
        strip.className = 'ff-filmstrip';
        strip.dataset.ffLive = '1';
        const track = document.createElement('div');
        track.className = 'ff-filmstrip__track render-set';
        track.id = 'ffLiveTrack';
        track.tabIndex = 0;
        track.setAttribute('role', 'region');
        track.setAttribute('aria-label', 'Generated campaign — ' + renders.length + ' export sizes');
        const themeBit = opts.themeLabel ? (', ' + opts.themeLabel + ' theme') : '';
        renders.forEach((r, i)=>{
          // backend slug validated to TileSize; unknown slugs keep their name and a derived class.
          const size = (typeof window.KODIAK_tileSizeFromString==='function') ? window.KODIAK_tileSizeFromString(r.ratio) : null;
          const meta = (size && RATIO_LABELS[size]) || {name:r.ratio, cls:'r-'+String(r.ratio||'').replace(/[^0-9x]/g,'')};
          const ratioColon = r.ratio.replace('x',':');
          const tile = document.createElement('div');
          tile.className = 'ff-filmstrip__slot render-tile ' + meta.cls;
          tile.dataset.ratio = size || String(r.ratio || '');
          const thumb = document.createElement('button');
          thumb.type = 'button';
          thumb.className = 'ff-filmstrip__thumb';
          thumb.setAttribute('aria-label', 'Open ' + ratioColon + ' ' + meta.name + ' preview');
          const frame = document.createElement('span');
          frame.className = 'ff-filmstrip__frame render-frame';
          // true frame ratio from the delivered pixels; CSS per-ratio + matrix
          // refresh cover the cases where w/h are missing.
          try{ if(r.w && r.h) frame.style.aspectRatio = r.w + '/' + r.h; }catch(e){}
          const img = document.createElement('img');
          img.src = r.image_url;
          img.alt = 'Kodiak Cakes campaign hero, ' + ratioColon + ' ' + meta.name + themeBit;
          img.loading = i === 0 ? 'eager' : 'lazy';
          frame.appendChild(img);
          thumb.appendChild(frame);
          tile.appendChild(thumb);
          const cap = document.createElement('div');
          cap.className = 'render-cap ff-filmstrip__cap';
          // clean caption: "1:1 Feed · 1080×1080" + the platforms this ratio serves (no engineering noise)
          const plats = platformsForRatio(r.ratio);
          const platLine = plats.length ? '<span class="rt-platforms">' + escapeHtml(plats.join(' \u00B7 ')) + '</span>' : '';
          // S12 — localized caption per tile: EN source + this market's top_languages[] (live /localize when on,
          // community-review never machine, offline pending). Driven by the selected market at render time.
          let locCap = '';
          try{
            const _m = (/** @type {HTMLInputElement|null} */ (document.getElementById('locality')))?.value || (selectedLoc && selectedLoc.market);
            if(_m && typeof window.KODIAK_locCaption==='function') locCap = window.KODIAK_locCaption(_m);
          }catch(e){}
          // Per-tile engine mark: provenance.ratios names each tile's engine, so a
          // pillow pad never renders identically to a live outpaint. The 1x1
          // primary carries no mark — it is the real hero, not a derived tile.
          let engMark = '';
          try{
            const _penv = (opts.provenance && typeof opts.provenance==='object') ? opts.provenance : {};
            const _engines = (_penv.ratios && typeof _penv.ratios==='object') ? _penv.ratios : {};
            const _mark = tileEngineMark(_engines[r.ratio]);
            if(_mark.text) engMark = '<span class="rt-eng ' + _mark.cls + '">' + escapeHtml(_mark.text) + '</span>';
          }catch(e){}
          cap.innerHTML = '<b>' + escapeHtml(ratioColon + ' ' + meta.name) + '</b>' +
            '<span class="dims">' + escapeHtml((r.w||'') + '\u00D7' + (r.h||'')) + '</span>' + platLine + locCap + engMark;
          // per-ratio download survives the filmstrip move (same action as the resting strip)
          const dl = document.createElement('a');
          dl.className = 'ff-filmstrip__dl';
          dl.href = r.image_url;
          dl.textContent = 'Download';
          try{ dl.download = 'Kodiak-Cakes-' + String(r.ratio || 'render').replace(/[^0-9a-z]/gi, '') + '-' + (r.w || '') + 'x' + (r.h || '') + '.png'; }catch(e){}
          cap.appendChild(dl);
          tile.appendChild(cap);
          track.appendChild(tile);
        });
        /**
         * @param {string} dir
         * @returns {HTMLButtonElement}
         */
        const mkArrow = (dir)=>{
          const b = document.createElement('button');
          b.type = 'button';
          b.className = 'ff-filmstrip__arrow ff-filmstrip__arrow--' + dir;
          b.setAttribute('aria-label', dir === 'prev' ? 'Scroll sizes backward' : 'Scroll sizes forward');
          b.setAttribute('aria-controls', 'ffLiveTrack');
          b.textContent = dir === 'prev' ? '\u2039' : '\u203A';
          return b;
        };
        strip.appendChild(mkArrow('prev'));
        strip.appendChild(track);
        strip.appendChild(mkArrow('next'));
        const dots = document.createElement('div');
        dots.className = 'ff-filmstrip__dots';
        dots.setAttribute('role', 'group');
        dots.setAttribute('aria-label', 'Choose size');
        renders.forEach((r, i)=>{
          const size = (typeof window.KODIAK_tileSizeFromString==='function') ? window.KODIAK_tileSizeFromString(r.ratio) : null;
          const meta = (size && RATIO_LABELS[size]) || {name:r.ratio};
          const d = document.createElement('button');
          d.type = 'button';
          d.className = 'ff-filmstrip__dot';
          d.setAttribute('aria-label', 'Show ' + r.ratio.replace('x',':') + ' ' + meta.name);
          d.setAttribute('aria-current', i === 0 ? 'true' : 'false');
          dots.appendChild(d);
        });
        strip.appendChild(dots);
        preview.appendChild(strip);
        // true frame ratios + arrows/dots/lightbox wiring for the fresh strip
        try{ if(typeof ffRefreshFrames === 'function') ffRefreshFrames(strip); }catch(e){}
        try{ const w = (typeof wireFilmstrip === 'function') ? wireFilmstrip : window.KODIAK_wireFilmstrip; if(typeof w === 'function') w(strip); }catch(e){}
        openPreviewCard();
        // hero download targets the 1x1 (primary) render
        const primary = renders.find(r=>r.ratio==='1x1') || renders[0];
        if(primary) window.__lastHeroUrl = primary.image_url;
        // pack download (#204) needs the asset keys, not the presigned urls — record
        // the set's s3_uris + ratios alongside the hero so downloadAllPreview can
        // POST them to /assets/pack for a real ISO-named zip.
        try{
          const pack = (Array.isArray(renders)?renders:[]).filter(r=>r && r.s3_uri).map(r=>({s3_uri:r.s3_uri, ratio:r.ratio||'1x1'}));
          window.__lastPack = pack.length ? pack : null;
        }catch(e){ try{ window.__lastPack = null; }catch(_){} }
        // source badge above the preview — provenance-driven, fallbacks flagged (#173)
        let badge = document.getElementById('genSourceBadge');
        if(!badge){ badge=document.createElement('span'); badge.id='genSourceBadge'; badge.className='badge gen-badge'; preview.parentNode?.insertBefore(badge, preview); }
        const rb2 = rungBadge(opts.source, opts.provenance);
        paintRungBadge(badge, rb2);
        if(opts.themeLabel) badge.textContent += ' · theme: ' + opts.themeLabel;
        revealDownloadActions();
        try{ if(typeof window.__kodiakRevealCampaign==='function') window.__kodiakRevealCampaign(); }catch(e){}
      };
      // expose the hosted multi-ratio renderer so the Generate Campaign section can reuse it for full-campaign results
      try{ window.KODIAK_showRenderSet = showRenderSet; }catch(e){}
      // Tall/wide tiles start as server-side pads. Each one then attempts a
      // live extend (mode=extend fits the wall alone) and swaps to composed
      // pixels when they land. Pads are the loading state, never the final
      // state while an extend is still possible.
      // extendTargets/extendHero/extendBody live at IIFE top level (shared
      // with tests); used directly here.
      const extendTallTiles = async (renders, fields)=>{
        try{
          const hero = extendHero(renders);
          if(!hero) return;
          const targets = extendTargets(renders);
          if(!targets.length) return;
          /**
           * @param {string} ratio
           * @param {boolean} on
           * @returns {void}
           */
          const markComposing = (ratio, on)=>{
            try{
              document.querySelectorAll('#preview .render-tile').forEach(t=>{
                const b = t.querySelector('b');
                if(b && b.textContent.indexOf(ratio.replace('x',':'))===0){
                  let s = t.querySelector('.rt-extend');
                  if(on && !s){ s=document.createElement('span'); s.className='rt-extend'; s.textContent=' · composing'; t.querySelector('.render-cap')?.appendChild(s); }
                  if(!on && s) s.remove();
                }
              });
            }catch(e){}
          };
          // Every delivered state gets a mark: a live outpaint says composed, a
          // server-side pad says cover-pad (distinct crop), and a failed extend
          // (the server-side pad stays in place) says cover-pad too — a pad is
          // never left bare. Supersedes the initial rt-eng mark, never dupes it.
          /**
           * @param {string} ratio
           * @param {string} text
           * @param {string} cls
           * @returns {void}
           */
          const setTileMark = (ratio, text, cls)=>{
            try{
              document.querySelectorAll('#preview .render-tile').forEach(t=>{
                const b = t.querySelector('b');
                if(b && b.textContent.indexOf(ratio.replace('x',':'))===0){
                  markComposing(ratio, false);
                  const cap = t.querySelector('.render-cap');
                  const old = cap && cap.querySelector('.rt-eng');
                  if(old) old.remove();
                  if(!cap) return;
                  let s = cap.querySelector('.rt-extend');
                  if(!s){ s=document.createElement('span'); s.className='rt-extend'; cap.appendChild(s); }
                  s.textContent = text;
                  s.classList.remove('rt-live', 'rt-pad');
                  if(cls) s.classList.add(cls);
                }
              });
            }catch(e){}
          };
          /**
           * @param {string} ratio
           * @param {string} url
           * @param {unknown} engine
           * @returns {void}
           */
          const swapTile = (ratio, url, engine)=>{
            try{
              document.querySelectorAll('#preview .render-tile').forEach(t=>{
                const b = t.querySelector('b');
                if(b && b.textContent.indexOf(ratio.replace('x',':'))===0){
                  const img = t.querySelector('img');
                  if(img && url) img.src = url;
                }
              });
            }catch(e){}
            const mark = tileEngineMark(engine);
            setTileMark(ratio, mark.text || ' · cover-pad', mark.cls || 'rt-pad');
          };
          await Promise.all(targets.map(async (r)=>{
            const ratio = r.ratio;
            markComposing(ratio, true);
            for(let attempt=0; attempt<2; attempt++){
              try{
                const resp = await fetch('/generate', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(extendBody(ratio, hero, fields))});
                if(!resp.ok) break;
                const tile = await resp.json();
                if(tile && tile.ok && tile.image_url){ swapTile(ratio, tile.image_url, tile.engine); return; }
                break;
              }catch(e){}
            }
            // Retries exhausted or a bad response: the server-side pad is the
            // delivered tile — label it instead of leaving it bare or stuck
            // on "composing".
            setTileMark(ratio, ' · cover-pad', 'rt-pad');
          }));
        }catch(e){}
      };
      try{ window.KODIAK_extendTallTiles = extendTallTiles; }catch(e){}
      // TASK 2 — collapsible provenance panel: what you provided vs what we did.
      /**
       * @param {unknown} prov backend response envelope
       * @param {ProvCtx} [ctx] request inputs
       * @returns {void}
       */
      const renderProvenancePanel = (prov, ctx)=>{
        // fresh consts, not reassignment: narrowed shapes keep their types below.
        const penv = /** @type {Provenance} */ ((prov && typeof prov==='object') ? prov : {});
        const cctx = /** @type {ProvCtx} */ (ctx || {});
        const preview = document.getElementById('preview');
        if(!preview) return;
        // build-tracing is ALWAYS shown: an absent/empty provenance still renders
        // the panel, with the honest "not reported" lines — never a blank surface.
        prov = (prov && typeof prov==='object') ? prov : {};
        // remove a prior panel so re-generate replaces cleanly
        const old = document.getElementById('provenancePanel');
        if(old) old.remove();
        const engineLabel = String((typeof penv.engine === 'string' && ENGINE_LABELS[penv.engine]) || penv.engine || '—');
        const ratios = /** @type {Object<string, unknown>} */ (penv.ratios || {});
        // Pill class names the engine state: a pillow pad never shares a pill
        // with a live stability outpaint.
        const ratioPills = Object.keys(ratios).map(k=>{
          const role = String(ratios[k]);
          const cls = /primary/i.test(role) ? 'primary'
            : role === 'stability-outpaint' ? 'live'
            : role === 'pillow-outpaint-fallback' ? 'pad' : 'outpaint';
          return '<span class="prov-pill ' + cls + '">' + escapeHtml(k.replace('x',':')) + ' ' + escapeHtml(role) + '</span>';
        }).join(' ');
        /** @param {unknown} v @returns {string} */
        const onoff = (v)=> v ? '<span class="prov-pill on">applied</span>' : '<span class="prov-pill off">not applied</span>';
        /** @param {Array<[string, (string|null)]>} pairs @returns {string} */
        const rows = (pairs)=> pairs.filter(p=>p[1]!=null && p[1]!=='').map(p=>'<dt>' + escapeHtml(p[0]) + '</dt><dd>' + String(p[1]) + '</dd>').join('');
        const provided = rows([
          ['Prompt', escapeHtml(penv.incoming_prompt || cctx.brief || '—')],
          ['Headline', escapeHtml(penv.headline)],
          ['Theme', escapeHtml(cctx.themeLabel || cctx.theme)],
          ['Market', escapeHtml(cctx.market)],
          ['Product', escapeHtml(cctx.product)]
        ]);
        const originLabel = (typeof penv.origin === 'string' && (ORIGIN_LABELS[penv.origin] || penv.origin)) || null;
        const did = rows([
          ['Engine', escapeHtml(engineLabel)],
          ['Origin', originLabel ? escapeHtml(originLabel) : null],
          ['Model', escapeHtml(penv.model)],
          ['Seed source', escapeHtml(penv.seed_source)],
          ['Seed selection', escapeHtml(penv.seed_selection)],
          ['Art-director scene', escapeHtml(penv.scene_prompt)],
          ['Control strength', penv.control_strength!=null ? escapeHtml(penv.control_strength) : null],
          ['Ratios', ratioPills || null],
          ['Brand overlay', onoff(penv.overlay_applied)],
          ['Paper texture', onoff(penv.paper_overlay)]
        ]);
        const panel = document.createElement('details');
        panel.className = 'provenance';
        panel.id = 'provenancePanel';
        // G — heuristics readout rides the same panel: how it was decided,
        // from the same prov object (no new data source, nothing invented).
        // The single-arg call keeps the pinned four decision lines
        // (rung/engine/seed/fallback); the panel then re-runs with the
        // platform_copy map to append the plainspoken build narrative so a
        // marketer reads WHAT the machine did, not just decision labels.
        var decisionLines = /** @type {string[]} */ ([]), buildLines = /** @type {string[]} */ ([]);
        try{
          decisionLines = provenanceHeuristics(prov);
          var allLines = provenanceHeuristics(prov, cctx.platformCopy || {});
          buildLines = allLines.slice(decisionLines.length);
        }catch(e){ decisionLines = []; buildLines = []; }
        var heurHtml = decisionLines.map(function(h){
          return '<p class="prov-heur">' + escapeHtml(h) + '</p>';
        }).join('');
        var buildHtml = buildLines.map(function(h){
          return '<p class="prov-heur prov-heur--build">' + escapeHtml(h) + '</p>';
        }).join('');
        // build narrative is the always-on plainspoken "how the campaign was built"
        // group — reuses the same model-call-stats real estate + the .prov-heur token styling.
        var buildGroup = buildHtml
          ? '<div class="prov-group prov-heuristics prov-build"><h4>How this campaign was built</h4>' + buildHtml + '</div>'
          : '';
        panel.innerHTML =
          '<summary>How this was made</summary>' +
          '<div class="prov-body">' +
            '<div class="prov-group"><h4>You provided</h4><dl>' + provided + '</dl></div>' +
            '<div class="prov-group"><h4>What we did</h4><dl>' + did + '</dl></div>' +
            buildGroup +
            '<div class="prov-group prov-heuristics"><h4>How it was decided</h4>' + heurHtml + '</div>' +
          '</div>';
        // Mount the panel: it was previously built but never inserted, so the
        // transparency section never appeared. Open by default — it is the
        // honest record of what the machine did, not fine print.
        try{
          panel.open = true;
          const provAnchor = document.getElementById('previewDownloadRow') || preview;
          provAnchor.parentNode?.insertBefore(panel, provAnchor.nextSibling);
        }catch(e){}
        // Keep provenance updates on the same renderer/state path when the separate
        // platform-copy request completes or falls back.
        try{
          window.__kodiakUpdateProvenanceCopy = function(platformCopy){
            renderProvenancePanel(prov, Object.assign({}, ctx, {platformCopy: platformCopy || {}}));
          };
        }catch(e){}
      };
      const finishCommon = ()=>{
        // Update local flavor with brief context (runs after either path)
        const lf = document.getElementById('localFlavorText');
        if(lf) lf.innerHTML += `<br><span class="flag-pine"><b>Brief applied:</b> “${brief}” — fans to all formats</span>`;
        console.log('KODIAK generate — sample', {brief, products, primarySlug, audience, selectedLoc: selectedLoc.market, frontierHint});
        try{ if(window.ffLog) window.ffLog('create', {brief: brief, products: products, theme: primarySlug, market: selectedLoc.market}); }catch(e){}
      };
      // Lock competing controls during generation so nothing changes mid-request; restore after.
      // Class-driven dimming on #promptChips (no inline styles): .is-locked paints it in components.css.
      const lockIds = ['generateCampaign','productSearch','randomProducts','downloadPack','promptUpload'];
      /**
       * @param {boolean} locked
       * @returns {void}
       */
      const lockControls = (locked)=>{
        lockIds.forEach(id=>{ const el=document.getElementById(id); if(el) /** @type {HTMLButtonElement|HTMLInputElement} */ (el).disabled=locked; });
        /** @type {NodeListOf<HTMLInputElement>} */ (document.querySelectorAll('#promptChips .ff-check-card__input')).forEach(c=>{ c.disabled=locked; });
        document.getElementById('promptChips')?.classList.toggle('is-locked', locked);
        /** @type {NodeListOf<HTMLInputElement>} */ (document.querySelectorAll('#productChooser .sku-check')).forEach(c=>{ c.disabled=locked; });
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
      let elapsed = 0, tick = null, timeoutId = null;
      /** @type {Array<ReturnType<typeof setTimeout>>} */
      const stageTimers = [];
      const controller = new AbortController();
      // Multi-product (2+ selected, no theme) shows a skeleton tile per pending product; otherwise one hero skeleton.
      const willFanOut = !activeTheme && hadExplicitSelection && products.length > 1;
      // Decide the request shape:
      //  - themed chip active -> ONE themed request (theme wins; no per-product fan-out)
      //  - 2+ products explicitly selected AND no theme -> one request PER product, render a grid
      //  - otherwise -> one default request (single hero)
      const doThemedOrSingle = activeTheme || !(hadExplicitSelection && products.length > 1);
      /**
       * @param {string} productSlug
       * @param {unknown} wantTheme
       * @returns {Promise<void>}
       */
      /**
       * @param {string} productSlug
       * @param {unknown} wantTheme
       * @returns {Promise<BackendResponse>}
       */
      const oneGenerate = async (productSlug, wantTheme)=>{
        // scope-first: Create reads the segmented control's selection (window.__campaignScope, default local)
        const scope = window.__campaignScope || 'local';
        // staged staged asset pick (Browse past assets) rides as the seed — the backend prefers
        // it over all probed seeds, so the customer's pick drives the pixels. Most
        // recently staged dam asset wins; absent key = today's path untouched.
        let stagedKey = null;
        try{ const staged = (window.__userAssets||[]).filter(function(a){ return a && a.source==='asset-library' && a.key; }); if(staged.length) stagedKey = staged[staged.length-1].key; }catch(e){}
        // Compose layers (#199/#200): independently-selected, default OFF. An empty
        // object means a clean standalone image + copy sidecars from the backend.
        let reqLayers = {};
        try{ reqLayers = (typeof window.__selectedLayers==='function') ? window.__selectedLayers() : {}; }catch(e){ reqLayers = {}; }
        // Every checked theme card rides along (primary first): the backend
        // drives seed/scene from the first known slug and folds extras into
        // overlay/copy lines. Season rides as its own field so the preview
        // recipe pairing reads it structurally, not from brief-text parsing.
        let themeList = wantTheme ? [wantTheme] : [];
        try{ themeList = orderThemes(wantTheme || null, (typeof window.__activeThemes==='function') ? window.__activeThemes() : []); }catch(e){}
        const body = {prompt: brief, market: selectedLoc.market, product: productSlug, scope, layers: reqLayers, ...(wantTheme ? {theme: wantTheme} : {}), ...(themeList.length ? {themes: themeList} : {}), ...(activeSeason ? {season: activeSeason} : {}), ...(stagedKey ? {seed_key: stagedKey} : {})};
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
      /**
       * @param {string} requestedSku
       * @param {string} briefText
       * @returns {void}
       */
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
          // historical shape: the local products here is string[], so this lookup always
        // misses (the id/img list lives in data-core). flagged, not changed — see README.
        else if(typeof products!=='undefined'){ const assetList = /** @type {Array<{id?: string, img?: string}>} */ (/** @type {unknown} */ (products)); const pr = assetList.find && assetList.find(x=>x && (x.id===sku)); if(pr && pr.img) heroSrc = pr.img; }
        }catch(e){}
        const isRealHero = typeof heroSrc==='string' && /^https?:\/\//.test(heroSrc) && heroSrc.indexOf('input_assets/')===-1;
        const tile = document.createElement('div');
        tile.className = 'tile';
        tile.style.cssText = 'grid-column:1/-1;max-width:640px;margin:0 auto;border:1px dashed #B51E14';
        const c = document.createElement('canvas'); c.width=1080; c.height=1080; c.style.maxWidth='100%'; c.style.height='auto';
        // page contract: 2d contexts are universally available — null only for unknown ids.
        const ctx = /** @type {CanvasRenderingContext2D} */ (c.getContext('2d'));
        /** @param {HTMLImageElement|null} heroImg @returns {void} */
        const paint = (heroImg)=>{
          try{ drawAd(ctx, 1080, 1080, (briefText||'Keep It Wild'), {id:sku}, heroImg||null); }catch(e){}
          // explicit offline watermark band — makes clear this is NOT the generated result.
          ctx.fillStyle='rgba(181,30,20,0.92)'; ctx.fillRect(0,0,1080,64);
          ctx.fillStyle='#FFF8F0'; ctx.textAlign='center'; ctx.font='700 26px Inter,sans-serif';
          ctx.fillText('OFFLINE PREVIEW — not the generated campaign', 540, 42);
        };
        // leak-teardown: detach the handlers after they fire so the closure + Image release.
        let img = new Image(); img.crossOrigin='anonymous';
        const release = ()=>{ img.onload=null; img.onerror=null; };
        img.onload = ()=>{ paint(img); release(); };
        img.onerror = ()=>{ paint(null); release(); };
        // only fire a network load for a real resolvable url; otherwise paint with no photo
        // (NO Image(), NO 404). offline preview still renders with its OFFLINE watermark.
        if(isRealHero){ img.src = heroSrc; }
        else { paint(null); release(); }
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
      // stale fallback retry never survives into a fresh run (either path)
      try{ document.getElementById('genRetry')?.remove(); }catch(e){}
      if(preview){
        if(willFanOut){
          preview.innerHTML = products.map((name,i)=>`<div class="tile genSkeletonTile"><div class="gen-pulse"><span class="gen-pulse-label">Composing…</span></div><div class="meta"><b>${name}</b><div class="small" id="genElapsed${i}">0s elapsed — up to ~90s</div></div></div>`).join('');
        } else {
          preview.innerHTML = `<div class="tile" id="genSkeleton"><div class="gen-pulse"><span class="gen-pulse-label gen-pulse-label--lg">Composing…</span></div><div class="meta"><b>Composing your campaign with Nova Pro${activeTheme ? ' — theme: ' + themeLabel : ''}</b><div class="small" id="genElapsed">0s elapsed — up to ~90s</div></div></div>`;
        }
        tick = setInterval(()=>{ elapsed++; document.querySelectorAll('[id^="genElapsed"]').forEach(e=>{ e.textContent = elapsed+'s elapsed — up to ~90s'; }); }, 1000);
      }
      // Rolling behind-the-scenes statuses: each line names a REAL phase of the
      // preview pipeline in typical order (brief in, Nova Micro copy review
      // runs concurrently first, Nova Pro hero composition is the bulk of the
      // wall, ratio fan-out + extends land last). Timed narration, not live
      // mapping — the single POST exposes no per-stage callbacks.
      const composeStages = [
        {at: 0, text: 'Sending your brief + market to the campaign backend…'},
        {at: 8000, text: 'Nova Micro reviewing campaign copy…'},
        {at: 15000, text: 'Nova Pro composing the hero…'},
        {at: 30000, text: 'Still composing — Nova Pro is rendering your hero…'},
        {at: 60000, text: 'Almost there — finishing the composition…'}
      ];
      if(status){
        composeStages.forEach((s)=>{
          if(s.at === 0){ status.textContent = s.text + ' (up to ~90s)'; return; }
          stageTimers.push(setTimeout(()=>{ if(status) status.textContent = s.text; }, s.at));
        });
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
            // backend renders[] carries all five sizes (1x1 + pillow pads) — render every labeled tile.
            showRenderSet(json.renders, {source: json.source, themeLabel: readyThemeLabel, provenance: json.provenance});
            // tall/wide tiles upgrade from pads to composed pixels as extends land.
            try{ (window.KODIAK_extendTallTiles || extendTallTiles)(json.renders, {subject: brief, product: primarySlug, region: selectedLoc.market, theme: json.theme || activeTheme || null}); }catch(e){}
            const n = json.renders.length;
            if(status) status.textContent = 'Campaign preview ready — ' + n + ' sizes composed from ' + (json.source || 'Nova Pro') + readyTheme;
          } else {
            // OLDER backend (no renders array): fall back to the single-hero behavior.
            showRealImage(json.image_url, json.source, {theme: json.theme || activeTheme || null, themeLabel: json.theme ? (THEME_LABELS[json.theme] || json.theme) : themeLabel, provenance: json.provenance});
            if(status) status.textContent = 'Campaign preview ready — one real composed hero from ' + (json.source || 'Nova Pro') + readyTheme;
          }
          // provenance transparency panel — ALWAYS renders so every preview
          // narrates how it was built, in the same model-call-stats real estate.
          // Passing platform_copy lets the build narrative say whether the copy
          // came from a live model or the on-brand template.
          renderProvenancePanel(json.provenance || {}, {brief, theme: json.theme || activeTheme, themeLabel: readyThemeLabel, market: selectedLoc.market, product: primarySlug, platformCopy: json.platform_copy || {}});
          // per-platform messaging copy paints the deterministic fallback first, then
          // sharpens it through the separate bounded endpoint without hiding it.
          renderPlatformCopy(json.platform_copy);
          try{
            const previewProv = /** @type {{copy_headline?: unknown, incoming_prompt?: unknown}} */ ((json.provenance && typeof json.provenance==='object') ? json.provenance : {});
            const previewBaseMessage = previewProv.copy_headline || previewProv.incoming_prompt || json.headline || json.message || brief;
            void sharpenPlatformCopy({
              baseMessage: previewBaseMessage,
              productName: products[0] || primarySlug,
              market: selectedLoc.market,
              provenance: previewProv
            });
          }catch(e){}
          // #281 — upgrade the driving panel to the copy actually used + divergence flags.
          try{ paintCopyPanel({phase:'used', json}); }catch(e){}
          // Honest fallback gets a retry affordance: the wall fires on cold
          // models, so a second Create often lands real pixels. Idempotent —
          // a passing run removes any stale button.
          try{
            let retry = document.getElementById('genRetry');
            if(retry) retry.remove();
            if(/^brand-floor/i.test(String((json && json.source) || ''))){
              if(status) status.textContent = 'Render miss (wall timeout) — fallback pixels shown, not the campaign.';
              retry = document.createElement('button');
              retry.type = 'button';
              retry.id = 'genRetry';
              retry.className = 'ff-retry';
              retry.textContent = 'Try again — models are warm now';
              retry.addEventListener('click', ()=>{ const g = document.getElementById('generateCampaign'); if(g) g.click(); });
              const anchor = document.getElementById('previewDownloadRow') || document.getElementById('preview');
              if(anchor && anchor.parentNode) anchor.parentNode.insertBefore(retry, anchor.nextSibling);
            }
          }catch(e){}
          // auto-open the collapsed Preview card so the user sees the freshly-composed output
          openPreviewCard();
        } else {
          // Multi-product fan-out: one themed-less request per selected product, run
          // SERIALLY and render each tile as it returns. Parallel full preview
          // ladders contend for shared model quota inside the backend 22s wall
          // and all fall through to rung D together; serial keeps each request
          // inside its own budget (first tile still paints fast).
          if(preview) preview.innerHTML = '';
          if(status) status.textContent = 'Composing ' + products.length + ' product variants with Nova Pro…';
          let firstDone = false, okCount = 0;
          for(const name of products){
            const slug = slugify(name);
            try{
              const json = await oneGenerate(slug, undefined);
              showRealImage(json.image_url, json.source, {append:true, grid:true, productName:name, provenance: json.provenance});
              okCount++;
              if(!firstDone){ firstDone = true; window.__lastHeroUrl = json.image_url; rememberSidecar(json); try{ window.__lastCopyJson = json; }catch(_){} }
            }catch(e){
              console.warn('generate: product variant failed for', name, e instanceof Error ? e.message : e);
              // render a small failed-tile so the grid shows what did not compose
              const p = document.getElementById('preview');
              if(p){ const t=document.createElement('div'); t.className='tile'; t.innerHTML=`<div class="meta"><b>${name}</b><div class="small flag-err">variant failed — try again</div></div>`; p.appendChild(t); }
            }
          }
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
        console.warn('generate: no response from backend (total network loss) —', err instanceof Error ? err.message : err);
        const timedOut = err instanceof Error && err.name==='AbortError';
        try{
          drawNetworkLossNotice(String(window.__requestedSku || primarySlug), brief);
        }catch(e){ console.warn('offline notice render failed', e); }
        if(status) status.textContent = timedOut
          ? 'No response from the server (timed out) — offline preview shown; reconnect and try again'
          : 'Could not reach the server — offline preview shown; reconnect and try again';
      }finally{
        if(timeoutId) clearTimeout(timeoutId);
        stageTimers.forEach((t)=>{ try{ clearTimeout(t); }catch(e){} });
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
  /** @type {NodeListOf<HTMLElement>} */ (document.querySelectorAll('[data-mcp-layer]')).forEach(el=>{ el.title = 'WebMCP layer: ' + el.getAttribute('data-mcp-layer'); });
  console.log('KODIAK campaign UI — single brief + up to 3 SKUs + real team + local flavor derived + single generate (fans to ALL)');
})();
