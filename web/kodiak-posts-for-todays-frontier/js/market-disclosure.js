// --- Wave2 (C/D/E/F): rizzy market disclosure + seasonal menu + inline featured-frontier & language line ---
(function(){
  var details = document.getElementById('marketDisclosure');
  var summary = details ? details.querySelector('summary') : null;
  var label   = document.getElementById('marketButtonLabel');
  var listbox = document.getElementById('marketListbox');
  var featuredEl = document.getElementById('featuredFrontier');
  var langLine   = document.getElementById('marketLangLine');
  if(!details || !summary || !listbox){ return; }

  // top-3 languages for a market, default EN/ES/PT when a market lists fewer non-English langs.
  // marketLangsOffline holds top-2 non-English; English is always first.
  function topThreeLangsFor(market){
    var extra = (typeof marketLangsFor==='function') ? marketLangsFor(market) : [];
    var names = ['English'];
    (extra||[]).forEach(function(l){ if(l && l.lang_name && names.indexOf(l.lang_name)===-1) names.push(l.lang_name); });
    var defaults = ['English','Spanish','Portuguese'];
    for(var i=0; names.length<3 && i<defaults.length; i++){ if(names.indexOf(defaults[i])===-1) names.push(defaults[i]); }
    return names.slice(0,3);
  }

  function placeFor(market){
    try{
      if(typeof places!=='undefined'){ var hit = places.find(function(p){return p.market===market;}); if(hit) return hit; }
    }catch(e){}
    // custom user-added markets are not in places[] — resolve them here so the label/featured lines reflect
    try{ return customMarkets.find(function(p){return p.market===market;}) || null; }catch(e){ return null; }
  }

  // two-bucket location_class (pipeline #124). derived read only, no schema change.
  // "market" = the place has a home/primary chain-grocer retailer (real non-empty string);
  // "featured-frontier" = retailer is "—" or empty (frontier spot with no commercial retail).
  function classifyLocation(place){
    var r = place && typeof place.retailer==='string' ? place.retailer.trim() : '';
    return (r && r !== '—') ? 'market' : 'featured-frontier';
  }

  // language-names summary (2026-09-08 cleanup order): the per-language translated rows are
  // retired — translated copy lives only in the preview tile captions. This keeps
  // #marketLangLine live and truthful (names, never translated copy) with no second surface.
  function renderLocalizedCopy(market){
    if(!langLine) return;
    var langs = (typeof marketLangsFor==='function') ? marketLangsFor(market) : [];
    var names = ['English'];
    (langs||[]).forEach(function(l){ if(l && l.lang_name && names.indexOf(l.lang_name)===-1) names.push(l.lang_name); });
    function esc(s){ return String(s).replace(/[&<>"]/g, function(c){ return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]; }); }
    langLine.innerHTML = 'localized in languages: <b>' + esc(names.join(', ')) + '</b>';
    return;
  }

  // 3. user-added markets (client-side only). No curated cue/language data — degrade gracefully.
  var customMarkets = [];

  // update the three derived lines (button label, featured frontier, language line) for a market
  function reflectMarket(market){
    var p = placeFor(market);
    if(label && p) label.textContent = (p.place || market);
    if(summary && p) summary.setAttribute('aria-label', 'Choose market — currently ' + (p.place || market));
    if(featuredEl){
      var cue = p && p.cue ? p.cue : '';
      featuredEl.textContent = cue ? ('Featured frontier: ' + cue) : '';
    }
    if(langLine){
      try{ renderLocalizedCopy(market); }
      catch(e){ /* never break reflectMarket on a render fault */ }
    }
  }

  // keep the hidden #locality select (the value generate() reads) in sync, firing change so
  // onLocality + updateLocalFlavor + any listeners run exactly as before.
  function selectMarket(market, opts){
    opts = opts || {};
    var sel = document.getElementById('locality');
    if(sel){
      if(!Array.prototype.some.call(sel.options, function(o){return o.value===market;})){
        // ensure the option exists (fillSelects builds them from places[])
        var o=document.createElement('option'); o.value=market; o.textContent=market; sel.appendChild(o);
      }
      sel.value = market;
      sel.dispatchEvent(new Event('change', {bubbles:true}));
    }
    reflectMarket(market);
    // mark aria-selected in the listbox
    Array.prototype.forEach.call(listbox.querySelectorAll('[role="option"]'), function(el){
      el.setAttribute('aria-selected', el.dataset.market===market ? 'true':'false');
    });
    if(!opts.keepOpen){ closePanel(); summary.focus(); }
  }

  function buildOptions(){
    if(typeof places==='undefined' || !places.length) return;
    listbox.innerHTML = '';
    function addOption(p, isCustom){
      var opt = document.createElement('button');
      opt.type='button';
      opt.setAttribute('role','option');
      opt.dataset.market = p.market;
      opt.setAttribute('aria-selected','false');
      var badge = isCustom ? '<span class="ff-opt-badge">custom</span>' : '';
      opt.innerHTML = '<span>'+ (p.place||p.market) + badge +'</span><span class="ff-opt-sub">'+ p.market +'</span>';
      opt.addEventListener('click', function(){ selectMarket(p.market); });
      listbox.appendChild(opt);
    }
    places.forEach(function(p){ addOption(p, false); });
    customMarkets.forEach(function(p){ addOption(p, true); });
  }

  // ---- disclosure open/close + aria-expanded ----
  function openPanel(){ if(!details.open){ details.open = true; } summary.setAttribute('aria-expanded','true'); }
  function closePanel(){ if(details.open){ details.open = false; } summary.setAttribute('aria-expanded','false'); }
  // native <details> toggles on summary click; mirror the state into aria-expanded
  details.addEventListener('toggle', function(){
    summary.setAttribute('aria-expanded', details.open ? 'true':'false');
    if(details.open){ focusActiveOption(); }
  });

  function optionEls(){ return Array.prototype.slice.call(listbox.querySelectorAll('[role="option"]')); }
  function focusActiveOption(){
    var opts = optionEls(); if(!opts.length) return;
    var active = opts.find(function(o){return o.getAttribute('aria-selected')==='true';}) || opts[0];
    setActive(active);
    active.focus();
  }
  function setActive(el){
    optionEls().forEach(function(o){ o.classList.toggle('is-active', o===el); });
  }

  // keyboard: Enter/Space/Down opens; Arrow keys move; Enter selects; Esc closes.
  summary.addEventListener('keydown', function(e){
    if(e.key==='ArrowDown' || e.key==='Enter' || e.key===' '){
      // let Space/Enter also do the native toggle, but ensure open + focus
      if(!details.open){ e.preventDefault(); openPanel(); setTimeout(focusActiveOption, 0); }
    } else if(e.key==='Escape'){ closePanel(); }
  });
  listbox.addEventListener('keydown', function(e){
    var opts = optionEls(); if(!opts.length) return;
    var idx = opts.findIndex(function(o){return o.classList.contains('is-active');});
    if(idx<0) idx = opts.findIndex(function(o){return o===document.activeElement;});
    if(e.key==='ArrowDown'){ e.preventDefault(); var n=opts[Math.min(opts.length-1, idx+1)]||opts[0]; setActive(n); n.focus(); }
    else if(e.key==='ArrowUp'){ e.preventDefault(); var pr=opts[Math.max(0, idx-1)]||opts[0]; setActive(pr); pr.focus(); }
    else if(e.key==='Home'){ e.preventDefault(); setActive(opts[0]); opts[0].focus(); }
    else if(e.key==='End'){ e.preventDefault(); setActive(opts[opts.length-1]); opts[opts.length-1].focus(); }
    else if(e.key==='Enter' || e.key===' '){ e.preventDefault(); var cur=opts[idx>=0?idx:0]; if(cur) selectMarket(cur.dataset.market); }
    else if(e.key==='Escape'){ e.preventDefault(); closePanel(); summary.focus(); }
  });
  // click outside closes the panel
  document.addEventListener('click', function(e){ if(details.open && !details.contains(e.target)) closePanel(); });

  // if #locality changes elsewhere (haversine/mockLat, Kamas dual-preview, fillSelects default),
  // reflect it into the button + derived lines so the UI never drifts from the real value.
  document.addEventListener('change', function(e){
    if(e.target && e.target.id==='locality'){ reflectMarket(e.target.value); }
  });

  // ---- D. seasonal menu ----
  var seasonSel = document.getElementById('seasonalSelect');
  if(seasonSel){
    var months = ['January','February','March','April','May','June','July','August','September','October','November','December'];
    var seasons = ['Spring','Summer','Fall','Winter'];
    var holidays = ['New Year','Valentine\u2019s Day','Easter','Memorial Day','Fourth of July','Labor Day','Halloween','Thanksgiving','Christmas','Holiday season'];
    function optGroup(labelTxt, items){
      var g=document.createElement('optgroup'); g.label=labelTxt;
      items.forEach(function(v){ var o=document.createElement('option'); o.value=v; o.textContent=v; g.appendChild(o); });
      return g;
    }
    seasonSel.appendChild(optGroup('Months', months));
    seasonSel.appendChild(optGroup('Seasons', seasons));
    seasonSel.appendChild(optGroup('Holidays', holidays));
    // thread selection into the campaign context. window.__activeSeason is read by generate();
    // empty selection = no seasonal hint (optional).
    window.__activeSeason = null;
    seasonSel.addEventListener('change', function(){
      window.__activeSeason = seasonSel.value || null;
    });
    // 1. default to the CURRENT calendar month by name (not "any"). "Season: any" stays selectable.
    // seed activeSeason so the brief carries "season: <month>" by default.
    try{
      var cm = months[new Date().getMonth()];
      seasonSel.value = cm;
      window.__activeSeason = seasonSel.value || null;
    }catch(e){}
  }

  // ---- 2. "use my location" — snap to nearest curated market by haversine ----
  // places[] carries no coordinates; store-finder-markets.json (keyed by `market`) does — but only
  // ~12 of 74 rows there carry `coordinates`, and the file is not served alongside this page on
  // CloudFront / file://. so the button must NOT depend on that fetch to function.
  // offline-first design: seed marketCoords from a built-in per-market table (factual US city
  // lat/lon, geographic constants — not fabricated market data). the JSON fetch stays a best-effort
  // ENRICHMENT pass that overwrites entries with richer coords when it happens to load. the button
  // works fully offline because marketCoords is never empty.
  var GEO_FALLBACK = {
    'US-MW-PARKCITY-84098':{lat:40.6461,lon:-111.4980}, 'US-UT-KAMASVALLEY':{lat:40.6902,lon:-111.2799},
    'US-SW-ALBQ':{lat:35.0844,lon:-106.6504}, 'US-SC-AUSTIN':{lat:30.2672,lon:-97.7431},
    'US-SE-FL':{lat:25.7617,lon:-80.1918}, 'US-SE-COAST':{lat:32.0809,lon:-81.0912},
    'US-SE-ATL':{lat:33.7490,lon:-84.3880}, 'US-MW-CHI':{lat:41.8781,lon:-87.6298},
    'US-MW-TC':{lat:44.9778,lon:-93.2650}, 'US-MW-DEN':{lat:39.7392,lon:-104.9903},
    'US-W-SEA':{lat:47.6062,lon:-122.3321}, 'US-W-PDX':{lat:45.5152,lon:-122.6784},
    'US-W-LA':{lat:34.0522,lon:-118.2437}, 'US-SE-NASH':{lat:36.1627,lon:-86.7816},
    'US-SE-LOU':{lat:38.2527,lon:-85.7585}, 'US-NE-BOS':{lat:42.3601,lon:-71.0589},
    'US-SW-PHX':{lat:33.4484,lon:-112.0740}, 'US-NE-NYC':{lat:40.6782,lon:-73.9442},
    'US-SW-TIMBERON':{lat:32.6376,lon:-105.6947}, 'US-MW-WASATCH-SLC':{lat:40.7608,lon:-111.8910},
    'US-W-SF':{lat:37.7749,lon:-122.4194}, 'US-W-SD':{lat:32.7157,lon:-117.1611},
    'US-W-VEGAS':{lat:36.1699,lon:-115.1398}, 'US-MW-PHX2':{lat:32.2226,lon:-110.9747},
    'US-SW-EL PASO':{lat:31.7619,lon:-106.4850}, 'US-SC-DALLAS':{lat:32.7767,lon:-96.7970},
    'US-SC-HOUSTON':{lat:29.7604,lon:-95.3698}, 'US-SC-SANANTONIO':{lat:29.4241,lon:-98.4936},
    'US-MW-KC':{lat:39.0997,lon:-94.5786}, 'US-MW-STL':{lat:38.6270,lon:-90.1994},
    'US-MW-OMAHA':{lat:41.2565,lon:-95.9345}, 'US-MW-DESMOINES':{lat:41.5868,lon:-93.6250},
    'US-MW-MILWAUKEE':{lat:43.0389,lon:-87.9065}, 'US-MW-DETROIT':{lat:42.3314,lon:-83.0458},
    'US-MW-CLEVELAND':{lat:41.4993,lon:-81.6944}, 'US-MW-INDY':{lat:39.7684,lon:-86.1581},
    'US-NE-PHILLY':{lat:39.9526,lon:-75.1652}, 'US-NE-DC':{lat:38.9072,lon:-77.0369},
    'US-NE-BALTIMORE':{lat:39.2904,lon:-76.6122}, 'US-NE-RALEIGH':{lat:35.7796,lon:-78.6382},
    'US-SE-CHARLOTTE':{lat:35.2271,lon:-80.8431}, 'US-SE-JAX':{lat:30.3322,lon:-81.6557},
    'US-SE-TAMPA':{lat:27.9506,lon:-82.4572}, 'US-SE-NOLA':{lat:29.9511,lon:-90.0715},
    'US-SE-MEMPHIS':{lat:35.1495,lon:-90.0490}, 'US-SE-BIRMINGHAM':{lat:33.5186,lon:-86.8104},
    'US-SE-JACKSON':{lat:32.2988,lon:-90.1848}, 'US-SW-OKC':{lat:35.4676,lon:-97.5164},
    'US-MW-BOISE':{lat:43.6150,lon:-116.2023}, 'US-W-YAKIMA':{lat:46.6021,lon:-120.5059},
    'US-W-SPOKANE':{lat:47.6588,lon:-117.4260}, 'US-MW-MISSOULA':{lat:46.8721,lon:-113.9940},
    'US-W-RENO':{lat:39.5296,lon:-119.8138}, 'US-W-SACRAMENTO':{lat:38.5816,lon:-121.4944},
    'US-MW-MINNEAPOLIS2':{lat:46.7867,lon:-92.1005}, 'US-MW-FARGO':{lat:46.8772,lon:-96.7898},
    'US-NE-BURLINGTON':{lat:44.4759,lon:-73.2121}, 'US-NE-HARTFORD':{lat:41.7658,lon:-72.6734},
    'US-NE-PROVIDENCE':{lat:41.8240,lon:-71.4128}, 'US-SW-SANTA FE':{lat:35.6870,lon:-105.9378},
    'US-SW-CLOUDCROFT':{lat:32.8995,lon:-105.7458}, 'US-SW-ROSWELL':{lat:33.3943,lon:-104.5230},
    'US-W-ANCHORAGE':{lat:61.2181,lon:-149.9003}, 'US-W-HONOLULU':{lat:21.3069,lon:-157.8583},
    'US-SE-ASHEVILLE':{lat:35.5951,lon:-82.5515}, 'US-MW-JACKSONHOLE':{lat:43.4799,lon:-110.7624},
    'US-W-BEND':{lat:44.0582,lon:-121.3153}, 'US-W-BOULDER':{lat:40.0150,lon:-105.2705},
    'US-CA-PESCADERO':{lat:37.2547,lon:-122.3833}, 'US-WA-NEAHBAY':{lat:48.3686,lon:-124.6244},
    'US-SW-TULAROSA':{lat:33.0742,lon:-106.0192}
  };
  var marketCoords = {}; // market code -> {lat, lon}; seeded offline-first, enriched by JSON if present
  Object.keys(GEO_FALLBACK).forEach(function(mk){ marketCoords[mk] = {lat:GEO_FALLBACK[mk].lat, lon:GEO_FALLBACK[mk].lon}; });
  (async function loadMarketCoords(){
    for(const url of ['data/localization/store-finder-markets.json','../../data/localization/store-finder-markets.json','./data/localization/store-finder-markets.json']){
      try{
        const r = await fetch(url);
        if(r && r.ok){
          // isolate the parse: a 200 with a malformed body must not abort the loop or throw uncaught
          let d = null;
          try{ d = await r.json(); }catch(pe){ console.warn('[geo] malformed JSON at', url, pe && pe.message); continue; }
          const list = (d && d.markets) ? d.markets : [];
          var added = 0;
          list.forEach(function(m){
            if(m && m.market && m.coordinates && typeof m.coordinates.lat==='number' && typeof m.coordinates.lon==='number'){
              marketCoords[m.market] = {lat:m.coordinates.lat, lon:m.coordinates.lon}; // JSON wins over built-in
              added += 1;
            }
          });
          if(added){ console.log('[geo] enriched', added, 'market coordinates from', url, '— total', Object.keys(marketCoords).length); break; }
        }
      }catch(e){ /* file:// or offline — built-in GEO_FALLBACK already seeded marketCoords */ }
    }
  })();

  function haversineMi(lat1, lon1, lat2, lon2){
    var R = 3958.8, toRad = function(d){ return d*Math.PI/180; };
    var dLat = toRad(lat2-lat1), dLon = toRad(lon2-lon1);
    var a = Math.sin(dLat/2)*Math.sin(dLat/2) + Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)*Math.sin(dLon/2);
    return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
  }
  function nearestMarket(lat, lon){
    var best=null, bestD=Infinity;
    Object.keys(marketCoords).forEach(function(mk){
      var c = marketCoords[mk];
      var d = haversineMi(lat, lon, c.lat, c.lon);
      if(d < bestD){ bestD = d; best = mk; }
    });
    return best ? {market:best, miles:bestD} : null;
  }

  var geoBtn = document.getElementById('useMyLocation');
  var geoStatus = document.getElementById('geoStatus');
  function setGeoStatus(msg){ if(geoStatus) geoStatus.textContent = msg || ''; }
  if(geoBtn){
    // #197 consent gate: this tap is the ONLY entry point to any location resolution
    // (GPS, staged mock coords, IP inference). Nothing here runs on page load — the market
    // dropdown (Park City default) is the default path.
    geoBtn.addEventListener('click', function(){
      // Headless/QA path: ?mockLat&mockLon coords staged on window.__mockGeo by data-core.js.
      // Consumed here on tap only — never on load.
      try{
        var mock = window.__mockGeo;
        if(mock && isFinite(mock.lat) && isFinite(mock.lon)){
          var hit0 = nearestMarket(mock.lat, mock.lon);
          if(hit0){
            selectMarket(hit0.market);
            var p0 = placeFor(hit0.market);
            setGeoStatus('Nearest market: ' + ((p0 && p0.place) || hit0.market) + ' (' + Math.round(hit0.miles) + ' mi)');
          } else {
            setGeoStatus('No nearby market — keeping Park City');
          }
          return;
        }
      }catch(e){}
      if(!('geolocation' in navigator)){ setGeoStatus('Location unavailable — keeping Park City'); return; }
      // marketCoords is seeded offline-first from GEO_FALLBACK, so it is never empty in practice;
      // the guard remains only as a defensive no-op if the table were ever cleared.
      if(!Object.keys(marketCoords).length){ setGeoStatus('Location data unavailable — keeping Park City'); return; }
      setGeoStatus('Locating\u2026');
      navigator.geolocation.getCurrentPosition(
        function(pos){
          try{
            var hit = nearestMarket(pos.coords.latitude, pos.coords.longitude);
            if(hit){
              selectMarket(hit.market);
              var p = placeFor(hit.market);
              setGeoStatus('Nearest market: ' + ((p && p.place) || hit.market) + ' (' + Math.round(hit.miles) + ' mi)');
            } else {
              setGeoStatus('No nearby market — keeping Park City');
            }
          }catch(e){ setGeoStatus('Location unavailable — keeping Park City'); }
        },
        function(){ setGeoStatus('Location unavailable — keeping Park City'); },
        {enableHighAccuracy:false, timeout:8000, maximumAge:600000}
      );
    });
  }

  // ---- 3. add a location not in the curated list (client-side custom market) ----
  var addLocInput = document.getElementById('addLocInput');
  var addLocBtn = document.getElementById('addLocBtn');
  var customSeq = 0;
  function addCustomLocation(){
    if(!addLocInput) return;
    var raw = (addLocInput.value || '').trim();
    if(!raw) return;
    customSeq += 1;
    var code = 'CUSTOM-' + customSeq;
    // custom entry has no curated cue -> featured line blanks; no langs -> falls back to EN/ES/PT.
    customMarkets.push({market:code, place:raw, cue:'', custom:true});
    buildOptions();
    selectMarket(code, {keepOpen:true});
    addLocInput.value = '';
    addLocInput.focus();
  }
  if(addLocBtn){ addLocBtn.addEventListener('click', addCustomLocation); }
  if(addLocInput){
    addLocInput.addEventListener('keydown', function(e){
      if(e.key==='Enter'){ e.preventDefault(); addCustomLocation(); }
    });
  }

  // ---- 4. add-your-own-asset (frontend staging only, no DAM upload) ----
  // stages a pending asset chip and threads a marker into the brief so the generate path can read it.
  var addAssetInput = document.getElementById('addAssetInput');
  var pendingWrap = document.getElementById('selectionTray');
  var pendingSeq = 0;
  window.__userAssets = window.__userAssets || [];

  // DAM upload gate (T2). Same "hosted origin only" guard prompt-chips/data-core use: file:// +
  // localhost have no backend, so ASSET_ENDPOINT stays null and the upload path is skipped entirely
  // (staging-only, no fetch, no throw). A dev/server context can set window.KODIAK_LIBRARY_UPLOAD_ENDPOINT
  // to re-enable. Mirrors prompt-chips LIB_ENDPOINT resolution exactly.
  var _isLocal = (location.protocol==='file:') || ['127.0.0.1','localhost'].includes(location.hostname);
  var ASSET_ENDPOINT = window.KODIAK_LIBRARY_UPLOAD_ENDPOINT || (_isLocal ? null : '/library/assets');

  // POST the raw file bytes to /library/assets (T2 backend contract). ADDITIVE to client-side staging:
  // on 201 it records the returned asset_id on the staged rec so the generate path can reference a real
  // DAM asset later. 415 -> assetError with backend detail. network/offline/local -> silent honest degrade
  // (the chip already staged locally). NEVER throws into stagePendingAsset. rec is already in window.__userAssets.
  function uploadAsset(file, rec){
    if(!ASSET_ENDPOINT || !file || !rec) return;   // offline/local -> staging-only, no fetch
    // DAM-sourced recs never re-upload (they already live in the library); only local files reach here.
    if(rec.source === 'dam') return;
    var qs = '?filename=' + encodeURIComponent(rec.name || file.name || 'asset') +
             '&added_by=' + encodeURIComponent('frontier-ui');
    // tag with the detected kind so the DAM carries useful metadata; skip when unknown.
    if(rec.kind && rec.kind !== 'unknown'){ qs += '&tags=' + encodeURIComponent(rec.kind); }
    try{
      var ctrl = (typeof AbortController!=='undefined') ? new AbortController() : null;
      var timer = ctrl ? setTimeout(function(){ ctrl.abort(); }, 15000) : null;
      fetch(ASSET_ENDPOINT + qs, {
        method:'POST',
        headers:{'Content-Type':'application/octet-stream'},
        body: file,
        signal: ctrl ? ctrl.signal : undefined
      }).then(function(r){
        if(timer){ clearTimeout(timer); timer = null; }
        return r.text().then(function(body){
          var data = null;
          try{ data = body ? JSON.parse(body) : null; }catch(pe){ data = null; }   // guarded parse
          if(r.status === 415){
            // unsupported type per backend — surface its detail (the chip stays staged locally).
            var detail415 = (data && data.detail) ? String(data.detail) : ('unsupported file type: ' + rec.name);
            assetError(detail415);
            return;
          }
          if(!r.ok || !data){ return; }   // any other non-2xx or unparseable body -> silent staging-only degrade
          if(data.asset_id){ rec.asset_id = data.asset_id; }   // thread the real DAM id onto the staged rec
          if(data.embed_status){ rec.embed_status = data.embed_status; }
          // soft, non-blocking note for the pending-index case; not an error.
          if(data.embed_status === 'embed_pending'){ assetError('uploaded \u2014 indexing shortly'); }
        });
      }).catch(function(){
        if(timer){ clearTimeout(timer); timer = null; }
        // network failure / abort / offline -> keep staging-only silently, never throw.
      });
    }catch(e){ /* fetch construction fault -> staging-only, silent honest degrade */ }
  }

  function refreshUserAssetMarker(){
    // expose count for the generate path; also mark the create card so downstream can read it.
    try{
      var card = document.querySelector('[data-mcp="campaign-brief"]');
      if(card){ card.setAttribute('data-user-assets', String(window.__userAssets.length)); }
    }catch(e){}
  }
  // surface a short user-facing error near the upload tray (idempotent element, auto-clears on next action)
  function assetError(msg){
    try{
      if(!pendingWrap) return;
      var el = document.getElementById('ffAssetError');
      if(!el){
        el = document.createElement('span');
        el.id = 'ffAssetError';
        el.className = 'ff-inline-error';
        el.setAttribute('role','alert');
        el.setAttribute('aria-live','polite');
        pendingWrap.parentNode ? pendingWrap.parentNode.insertBefore(el, pendingWrap.nextSibling) : pendingWrap.appendChild(el);
      }
      el.textContent = String(msg || '');
    }catch(e){}
  }
  function clearAssetError(){ try{ var el = document.getElementById('ffAssetError'); if(el) el.textContent=''; }catch(e){} }

  // classify by mime type first, filename extension second (mime is empty for some OS/type combos)
  function detectKind(file){
    var t = (file && file.type || '').toLowerCase();
    var n = (file && file.name || '').toLowerCase();
    var ext = n.indexOf('.') !== -1 ? n.slice(n.lastIndexOf('.')+1) : '';
    if(t.indexOf('image/') === 0) return 'image';
    if(t === 'application/pdf' || ext === 'pdf') return 'pdf';
    if(ext === 'docx' || t.indexOf('wordprocessingml') !== -1) return 'docx';
    if(ext === 'json' || t === 'application/json') return 'brief-json';
    if(ext === 'yaml' || ext === 'yml' || t.indexOf('yaml') !== -1) return 'brief-yaml';
    return 'unknown';
  }

  // shared chip builder — thumbNode is either a blob <img> (image) or a styled label box (pdf/doc/brief)
  function buildChip(rec, thumbNode){
    var chip = document.createElement('div');
    chip.className = 'ff-pending-chip';
    chip.id = rec.id;
    var nm = document.createElement('span');
    nm.className = 'ff-pending-name';
    nm.textContent = rec.name;
    var rm = document.createElement('button');
    rm.type = 'button';
    rm.className = 'ff-pending-remove';
    rm.setAttribute('aria-label', 'Remove staged asset ' + rec.name);
    rm.textContent = '\u00d7';
    rm.addEventListener('click', function(){
      try{ if(thumbNode && thumbNode.tagName === 'IMG' && thumbNode.src && thumbNode.src.indexOf('blob:')===0) URL.revokeObjectURL(thumbNode.src); }catch(e){}
      window.__userAssets = window.__userAssets.filter(function(a){ return a.id!==rec.id; });
      if(chip.parentNode) chip.parentNode.removeChild(chip);
      refreshUserAssetMarker();
      try{ if(typeof window.__kodiakMarkDirty === 'function') window.__kodiakMarkDirty(); }catch(e){}
    });
    if(thumbNode) chip.appendChild(thumbNode);
    chip.appendChild(nm); chip.appendChild(rm);
    pendingWrap.appendChild(chip);
    refreshUserAssetMarker();
  }
  // labelled box for non-image staged files (ascii label only — no emoji, no blob <img> that cannot render)
  function docLabel(text){
    var box = document.createElement('span');
    box.className = 'ff-pending-doc';
    box.setAttribute('aria-hidden','true');
    box.textContent = text;
    return box;
  }
  // expose the shared stagers so the DAM browse path stages identically into the same tray (buildChip == same chip look)
  window.KODIAK_buildChip = buildChip;
  window.KODIAK_docLabel = docLabel;
  window.KODIAK_refreshUserAssetMarker = refreshUserAssetMarker;

  function stagePendingAsset(file){
    if(!file || !pendingWrap) return;
    clearAssetError();
    var kind;
    try{ kind = detectKind(file); }catch(e){ kind = 'unknown'; }
    pendingSeq += 1;
    var id = 'pending-asset-' + pendingSeq;
    var rec = {id:id, name:file.name || 'asset', type:file.type || '', kind:kind};

    if(kind === 'unknown'){
      // do NOT stage — surface a user-facing error, keep the tray usable
      assetError('unsupported file type: ' + rec.name);
      return;
    }

    if(kind === 'image'){
      window.__userAssets.push(rec);
      var thumb = document.createElement('img');
      thumb.className = 'ff-pending-thumb';
      thumb.alt = '';
      try{ thumb.src = URL.createObjectURL(file); }
      catch(e){ /* blob url unavailable — chip still stages with an empty thumb, never throws */ }
      buildChip(rec, thumb);
      uploadAsset(file, rec);
      return;
    }

    if(kind === 'pdf' || kind === 'docx'){
      window.__userAssets.push(rec);
      buildChip(rec, docLabel(kind === 'pdf' ? 'PDF' : 'DOC'));
      uploadAsset(file, rec);
      return;
    }

    // brief files (.json / .yaml / .yml): read as text, guarded. JSON is parse-checked; yaml stays raw.
    if(kind === 'brief-json' || kind === 'brief-yaml'){
      rec.assetType = 'brief';
      rec.format = (kind === 'brief-json') ? 'json' : 'yaml-raw';
      // stage immediately with a label so the chip appears even before the async read resolves
      window.__userAssets.push(rec);
      buildChip(rec, docLabel(kind === 'brief-json' ? 'JSON' : 'YAML'));
      uploadAsset(file, rec);
      try{
        var reader = new FileReader();
        reader.onload = function(){
          var text = '';
          try{ text = String(reader.result || ''); }catch(e){ text = ''; }
          rec.text = text;
          if(kind === 'brief-json'){
            try{ rec.parsed = JSON.parse(text); clearAssetError(); }
            catch(err){
              // guarded: never throw — surface an inline parse error, keep the raw text staged
              rec.parsed = null; rec.parseError = true;
              assetError('could not parse ' + rec.name + ' as JSON');
            }
          } else {
            // no yaml parser available in this static build — raw text is fine, note it as raw
            rec.parsed = null;
          }
        };
        reader.onerror = function(){ assetError('could not read ' + rec.name); };
        reader.readAsText(file);
      }catch(e){ assetError('could not read ' + rec.name); }
      return;
    }
  }
  if(addAssetInput){
    addAssetInput.addEventListener('change', function(e){
      var files = e.target && e.target.files ? e.target.files : [];
      for(var i=0;i<files.length;i++){ try{ stagePendingAsset(files[i]); }catch(err){ assetError('could not add ' + ((files[i]&&files[i].name)||'file')); } }
      // clear so re-selecting the same file re-fires change
      try{ addAssetInput.value = ''; }catch(err){}
    });
  }

  // ---- init ----
  function init(){
    buildOptions();
    var current = (document.getElementById('locality') && document.getElementById('locality').value) || 'US-MW-PARKCITY-84098';
    reflectMarket(current);
    Array.prototype.forEach.call(listbox.querySelectorAll('[role="option"]'), function(el){
      el.setAttribute('aria-selected', el.dataset.market===current ? 'true':'false');
    });
    summary.setAttribute('aria-expanded','false');
  }
  // places[] + #locality exist by the time DOM is parsed (scripts above are inline, synchronous).
  // rebuild once the async 73-market file may have upgraded marketLangsOffline (language line only reads it live).
  init();
  // rebuild options again shortly in case fillSelects/default ran after us
  setTimeout(function(){ if(!listbox.querySelector('[role="option"]')) buildOptions(); reflectMarket((document.getElementById('locality')||{}).value || 'US-MW-PARKCITY-84098'); }, 500);
})();
