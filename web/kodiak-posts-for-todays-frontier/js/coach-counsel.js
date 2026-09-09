// === Campaign counsel — adversarial recommendations with Apply ===
// Replaces the passive "Why this works" bullets with counsel that critiques
// the CURRENT brief/market/products and offers discrete recommendations.
// Each Apply writes through the real controls via real events (never behind
// the UI's back) and reruns Create so the preview visibly changes — only on
// explicit approval per item (or Apply all). No auto-apply, no auto-fetch.
// Counsel rules are local + deterministic (no model spend): thin brief, no
// products, missing retailer angle. Server recommendations[] are rendered
// too when the endpoint returns them (forward-compatible, preferred).
(function(){
  'use strict';
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  function coachUrl(){
    try{
      var m = document.querySelector('meta[name="kodiak-coach-url"]');
      var u = m && m.getAttribute('content');
      return (u && u.trim()) ? u.trim().replace(/\/$/, '') : null;
    }catch(e){ return null; }
  }
  var lastKey = null;

  function liveState(){
    var s = { brief: '', products: [], market: '', marketLabel: '', seasonText: '', theme: 'none' };
    try{
      var b = document.getElementById('campaignBrief');
      s.brief = b ? b.value : '';
      var ch = document.getElementById('productChooser');
      if(ch) s.products = Array.prototype.map.call(
        ch.querySelectorAll('.sku-check:checked'), function(x){ return x.value; });
      var loc = document.getElementById('locality');
      s.market = loc ? loc.value : '';
      var lab = document.getElementById('locationSectionLabel');
      s.marketLabel = lab ? lab.textContent.trim() : s.market;
      var fl = document.getElementById('localFlavorText');
      s.seasonText = fl ? fl.textContent.trim() : '';
      var th = document.querySelector('#promptChips .ff-check-card__input[data-theme]:checked');
      s.theme = th ? th.getAttribute('data-theme') : 'none';
    }catch(e){}
    return s;
  }

  // Market retailer data, same file the disclosure island already loads.
  var retailerCache = null;
  function marketRetailer(market, cb){
    try{
      if(retailerCache){ cb(retailerCache[market] || null); return; }
      var urls = ['data/localization/store-finder-markets.json',
        '../../data/localization/store-finder-markets.json',
        './data/localization/store-finder-markets.json'];
      (function next(i){
        if(i >= urls.length){ cb(null); return; }
        fetch(urls[i]).then(function(r){ if(!r.ok) throw 0; return r.json(); }).then(function(d){
          try{
            var map = {};
            (d.markets || []).forEach(function(m){
              if(m && m.market) map[m.market] = m.retailer || null;
            });
            retailerCache = map;
          }catch(e){ retailerCache = {}; }
          cb(retailerCache[market] || null);
        }).catch(function(){ next(i + 1); });
      })(0);
    }catch(e){ cb(null); }
  }

  // --- Apply primitives: real controls, real events, then rerun Create ---
  function setBrief(text){
    var b = document.getElementById('campaignBrief');
    if(!b || !text) return false;
    b.value = text;
    b.dispatchEvent(new Event('input', { bubbles: true }));
    return true;
  }
  function pickRandom3(){
    var r = document.getElementById('randomProducts');
    if(!r) return false;
    r.click();
    return true;
  }
  function checkTheme(dataTheme){
    var inp = document.querySelector(
      '#promptChips .ff-check-card__input[data-theme="' + dataTheme + '"]');
    if(!inp || inp.checked) return !!inp;
    inp.click();
    return true;
  }
  function rerunPreview(){
    var go = document.getElementById('generateCampaign');
    if(go) go.click();
  }

  // --- Local adversarial rules (deterministic, grounded in live state) ---
  // Each returns {label, reason, apply} or null.
  function ruleThinBrief(st){
    if(st.brief && st.brief.trim().length >= 12) return null;
    var bits = [];
    if(st.marketLabel) bits.push(st.marketLabel);
    if(st.seasonText) bits.push(st.seasonText.split('.')[0]);
    if(st.products.length) bits.push('featuring ' + st.products[0]);
    if(!bits.length) return null;
    return {
      label: 'Sharpen the brief',
      reason: 'Your brief is empty — the preview is running on defaults. Counsel drafts one from your live market, season, and picks.',
      apply: function(){
        return setBrief('Camp morning ' + bits.join(' · '));
      }
    };
  }
  function ruleNoProducts(st){
    if(st.products.length) return null;
    return {
      label: 'Pick 3 products',
      reason: 'Nothing is selected, so generate rolls Random 3. Counsel rolls it now so you see exactly what ships.',
      apply: pickRandom3
    };
  }
  function ruleRetailer(st, retailer){
    if(st.theme !== 'none' || !retailer) return null;
    var want = null;
    var low = String(retailer).toLowerCase();
    if(low.indexOf('publix') !== -1) want = 'localized-publix';
    else if(low.indexOf('costco') !== -1) want = 'localized-costco';
    if(!want) return null;
    if(!document.querySelector('#promptChips .ff-check-card__input[data-theme="' + want + '"]')) return null;
    var first = String(retailer).split(',')[0].trim();
    return {
      label: 'Angle it for ' + first,
      reason: st.marketLabel + ' shops at ' + retailer + ' — but no retailer angle is checked. Counsel checks the ' + first + ' card.',
      apply: function(){ return checkTheme(want); }
    };
  }

  function renderRecs(list){
    var p = panel();
    if(!p) return;
    var html = '<summary>Campaign counsel</summary><div class="prov-body">';
    if(!list.length){
      html += '<p>Nothing to counter — brief, picks, and angle read coherent. Create when ready.</p>';
    }else{
      html += '<ul class="ff-counsel-list">' + list.map(function(r, i){
        return '<li class="ff-counsel-item"><div><b>' + esc(r.label) + '</b><span>' +
          esc(r.reason) + '</span></div>' +
          '<button type="button" class="ff-counsel-apply" data-counsel="' + i + '">Apply</button></li>';
      }).join('') + '</ul>';
      if(list.length > 1) html += '<button type="button" class="ff-counsel-apply-all" data-counsel-all="1">Apply all &amp; preview</button>';
    }
    html += '</div>';
    p.innerHTML = html;
    if(!p.open) p.open = true;
    Array.prototype.forEach.call(p.querySelectorAll('[data-counsel]'), function(btn){
      btn.addEventListener('click', function(){
        var r = list[Number(btn.getAttribute('data-counsel'))];
        if(r && typeof r.apply === 'function' && r.apply() !== false) rerunPreview();
      });
    });
    var all = p.querySelector('[data-counsel-all]');
    if(all) all.addEventListener('click', function(){
      var ok = false;
      list.forEach(function(r){ if(typeof r.apply === 'function' && r.apply() !== false) ok = true; });
      if(ok) rerunPreview();
    });
  }

  function counsel(){
    var st = liveState();
    marketRetailer(st.market, function(retailer){
      var list = [];
      [ruleThinBrief(st), ruleNoProducts(st), ruleRetailer(st, retailer)]
        .forEach(function(r){ if(r) list.push(r); });
      // Server recommendations (future endpoint shape) preferred when present.
      // Local rules render IMMEDIATELY so the click never hangs on network;
      // a live server response upgrades the panel when it arrives.
      var url = coachUrl();
      renderRecs(list);
      if(!url) return;
      var timeout = new Promise(function(_, rej){
        setTimeout(function(){ rej(new Error('coach timeout')); }, 6000);
      });
      Promise.race([
        fetch(url + '/insights', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            brief: st.brief, theme: st.theme, market: st.market,
            products: st.products, want: 'recommendations'
          }),
        }),
        timeout
      ]).then(function(r){ if(!r.ok) throw 0; return r.json(); }).then(function(j){
        var remote = (j && j.recommendations) || [];
        var patched = remote.filter(function(r){
          return r && r.label && r.patch;
        }).map(function(r){
          return { label: r.label, reason: r.reason || 'Coach recommendation.',
            apply: function(){ return applyPatch(r.patch); } };
        });
        if(patched.length) renderRecs(patched);
      }).catch(function(){ /* local list already rendered */ });
    });
  }

  // Server patch shape {brief?, market?, theme?, products?} applied through
  // the same real-control paths as user input. KODIAK copy law holds: a
  // patched brief carrying bare KODIAK is refused, not laundered.
  function applyPatch(patch){
    var ok = false;
    try{
      if(patch.market){
        var l = document.getElementById('locality');
        if(l){ l.value = patch.market; l.dispatchEvent(new Event('change', { bubbles: true })); ok = true; }
      }
      if(patch.theme && checkTheme(patch.theme)) ok = true;
      if(patch.brief){
        if(/(^|[^a-zA-Z#])KODIAK([^a-zA-Z]|$)/.test(patch.brief)) return ok;
        if(setBrief(patch.brief)) ok = true;
      }
      if(patch.products && patch.products.length && pickRandom3()) ok = true;
    }catch(e){}
    return ok;
  }

  function panel(){
    var p = document.getElementById('insightsPanel');
    if(p) return p;
    var d = document.createElement('div');
    d.id = 'insightsPanel';
    d.className = 'provenance';
    d.setAttribute('role', 'status');
    d.setAttribute('aria-live', 'polite');
    var btn = document.getElementById('insightsBtn');
    if(btn && btn.parentNode){ btn.parentNode.insertBefore(d, btn.nextSibling); return d; }
    var prov = document.getElementById('provenancePanel');
    if(prov && prov.parentNode){ prov.parentNode.insertBefore(d, prov.nextSibling); return d; }
    return null;
  }

  function mountButton(){
    try{
      if(document.getElementById('insightsPanel') || document.getElementById('insightsBtn')) return;
      var prov = document.getElementById('provenancePanel');
      if(!prov) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.id = 'insightsBtn';
      btn.className = 'btn ghost';
      btn.textContent = 'Coach check';
      btn.addEventListener('click', counsel);
      prov.parentNode.insertBefore(btn, prov.nextSibling);
    }catch(e){}
  }

  try{
    var grid = document.getElementById('preview');
    if(grid && typeof MutationObserver !== 'undefined'){
      new MutationObserver(function(){
        try{
          if(!document.getElementById('provenancePanel')) lastKey = null;
          mountButton();
        }catch(e){}
      }).observe(grid, { childList: true, subtree: true });
    }
    mountButton();
  }catch(e){}
})();
