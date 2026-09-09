// === Coach insights — "Why this works" on the preview card (Unit 3) ===
// On-demand only: a button appears after the provenance panel; one click POSTs
// {brief, theme, market, provenance} to the coach /insights endpoint and renders
// bullets in the card style. One fetch max per preview (cached by image key).
// No coach URL configured (meta empty) = the button never appears. Never
// auto-fetches, never blocks Create or Download, never throws into the page.
(function(){
  'use strict';
  function coachUrl(){
    try{
      var m = document.querySelector('meta[name="kodiak-coach-url"]');
      var u = m && m.getAttribute('content');
      return (u && u.trim()) ? u.trim().replace(/\/$/, '') : null;
    }catch(e){ return null; }
  }
  function esc(s){
    return String(s == null ? '' : s).replace(/[&<>"']/g, function(c){
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
    });
  }
  var lastKey = null;

  function mountButton(){
    try{
      if(document.getElementById('insightsPanel') || document.getElementById('insightsBtn')) return;
      var prov = document.getElementById('provenancePanel');
      if(!prov || !coachUrl()) return;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.id = 'insightsBtn';
      btn.className = 'btn ghost';
      btn.textContent = 'Why this works';
      btn.setAttribute('aria-describedby', 'insightsHint');
      btn.addEventListener('click', fetchInsights);
      prov.parentNode.insertBefore(btn, prov.nextSibling);
    }catch(e){ /* insights are enhancement */ }
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
    if(btn) btn.parentNode.insertBefore(d, btn.nextSibling);
    return d;
  }

  function fetchInsights(){
    try{
      var url = coachUrl();
      if(!url) return;
      var p = panel();
      var key = '';
      try{
        var img = document.querySelector('#preview img');
        key = (img && img.getAttribute('src')) || document.getElementById('preview').innerHTML.length;
      }catch(e){}
      if(key && key === lastKey) return; // one fetch max per preview
      p.innerHTML = '<summary>Why this works</summary><div class="prov-body"><p>Asking the coach…</p></div>';
      if(!p.open) p.open = true;
      var briefEl = document.getElementById('campaignBrief');
      var themeEl = document.querySelector('#promptChips .ff-check-card__input[data-theme]:checked');
      var marketEl = document.getElementById('marketSummary');
      // Ground the coach in what is ACTUALLY selected — ungrounded theme claims
      // ("aligns with X") are worse than none. Products, season, scope included.
      var prodEl = document.getElementById('productChooser');
      var prodNames = [];
      try{
        prodNames = Array.from(prodEl ? prodEl.querySelectorAll('.sku-check:checked') : []).map(function(b){ return b.value; });
      }catch(e){}
      var seasonEl = document.getElementById('seasonalSelect');
      var payload = {
        brief: briefEl ? briefEl.value : '',
        theme: themeEl ? themeEl.getAttribute('data-theme') : 'none',
        market: marketEl ? marketEl.textContent : 'us',
        products: prodNames,
        season: seasonEl ? seasonEl.value : '',
        scope: (window.__campaignScope && window.__campaignScope.mode) || '',
      };
      fetch(url + '/insights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }).then(function(r){
        if(!r.ok) throw new Error('http ' + r.status);
        return r.json();
      }).then(function(j){
        var items = (j && j.insights) || [];
        if(!items.length) throw new Error('empty');
        lastKey = key;
        p.innerHTML = '<summary>Why this works</summary><div class="prov-body"><ul>' +
          items.slice(0, 5).map(function(t){ return '<li>' + esc(t) + '</li>'; }).join('') +
          '</ul></div>';
      }).catch(function(){
        p.innerHTML = '<summary>Why this works</summary><div class="prov-body"><p>Insights are busy — try again.</p></div>';
      });
    }catch(e){ /* never break the page */ }
  }

  // mount after every preview render; reset the per-preview cache when the
  // preview grid itself is replaced (a fresh Create is a fresh question).
  try{
    var grid = document.getElementById('preview');
    if(grid && typeof MutationObserver !== 'undefined'){
      new MutationObserver(function(muts){
        try{
          for(var i = 0; i < muts.length; i++){
            var m = muts[i];
            if(m.type === 'childList' && (m.addedNodes.length || m.removedNodes.length)){
              if(!document.getElementById('provenancePanel')) lastKey = null;
              mountButton();
            }
          }
        }catch(e){}
      }).observe(grid, { childList: true, subtree: true });
    }
    mountButton();
  }catch(e){}
})();
