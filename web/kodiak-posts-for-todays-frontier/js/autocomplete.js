// === B3 + B4 — prompt-box autocomplete + two-way selection reflection ===
// Additive only. Binds by id, reuses already-loaded window.skuCatalog (88 SKUs) + window.places (75 places).
// Coordinates with the existing chip/theme block via a shared programmatic-write guard so it never
// clobbers the user's text, never spuriously clears window.__activeTheme, and never fights auto-grow.
(function(){
  'use strict';
  var briefEl = document.getElementById('campaignBrief');
  if(!briefEl) return;

  // ---- shared helpers ----
  function grow(){ try{ briefEl.style.height='auto'; briefEl.style.height=Math.min(briefEl.scrollHeight,160)+'px'; }catch(e){} }
  function skus(){ return (window.skuCatalog && window.skuCatalog.length) ? window.skuCatalog : []; }
  function markets(){ return (window.places && window.places.length) ? window.places : []; }

  // =========================================================================
  // B4 — two-way reflection: selections assemble a de-duped context suffix in the
  // visible prompt so Create (which reads #campaignBrief.value) sends what the user sees.
  //
  // The value = <user free text> + <SUFFIX_MARKER><context suffix>. The suffix is regenerated
  // from CURRENT selection state on every change, so unchecking a product removes it from the
  // visible prompt. The user's free-text portion is preserved separately (recovered by stripping
  // the marker+suffix from the end on manual edits).
  // =========================================================================
  var SUFFIX_MARKER = '\n\n\u2014 ';   // "\n\n— " — visually separates the auto-context from the user's line
  window.__briefUserText = window.__briefUserText != null ? window.__briefUserText : (briefEl.value || '');
  window.__briefReflecting = false;    // guard: our programmatic writes must not be read as manual edits

  // current market label (readable place name), from the declared #locality select generate() reads
  function currentMarketLabel(){
    var sel = document.getElementById('locality');
    var code = sel && sel.value ? sel.value : '';
    if(!code) return '';
    var p = markets().find(function(x){ return x.market===code; });
    return p ? (p.place || code) : code;
  }
  // current season — the selected option's visible text (skip the "Season: any" placeholder)
  function currentSeasonLabel(){
    var s = document.getElementById('seasonalSelect');
    if(!s || !s.value) return '';
    var opt = s.options[s.selectedIndex];
    return opt ? opt.textContent.replace(/^Season:\s*/i,'').trim() : '';
  }
  // currently-checked product names
  function currentProducts(){
    return Array.prototype.slice.call(document.querySelectorAll('#productChooser .sku-check:checked'))
      .map(function(c){ return c.value; }).filter(Boolean);
  }
  // build the de-duped, readable context suffix from current selection state ('' when nothing selected).
  // frontier + in-season parts come from curated pair data (never fabricated);
  // appended after season so the market:/season:/products: shape checks still match.
  function currentMarketCode(){
    var s = document.getElementById('locality');
    return s ? (s.value || '') : '';
  }
  function buildSuffix(){
    var parts = [];
    var m = currentMarketLabel(); if(m) parts.push('market: ' + m);
    var s = currentSeasonLabel(); if(s) parts.push('season: ' + s);
    // Ecology / locality cue from the data model (places[].cue) — e.g., trillium/bluebells/coneflower/aster for Ohio River valley.
    // This is the plant ecology that helps the image prompt accurately represent the locality for the time of year / festivity,
    // and it comes from the schema (data-core.js places, built from regional-scoreboard), not a hardcoded string in code.
    // Seasonal moments supplement monthly_ingredients (favorite_flavors) — they do not override the ingredient.
    try{
      var code = currentMarketCode();
      var marketEntry = markets().find(function(entry){ return entry.market===code; });
      if(marketEntry && marketEntry.cue){
        // Use a short, season-relevant slice of the cue so the prompt stays stunning, not vague (full cue can be long)
        // The cue already names the ecology (trillium/bluebells etc.) appropriate for the market; we keep it verbatim.
        parts.push('ecology: ' + marketEntry.cue);
      }
      var rich = (typeof frontierSeasonLine === 'function' && code && s)
        ? frontierSeasonLine(code, s) : null;
      if(rich){
        if(rich.place) parts.push('frontier: ' + rich.place + (rich.moment ? ' — ' + rich.moment : ''));
        if(rich.ingredient){
          var flav = (rich.favorite_flavors && rich.favorite_flavors.length) ? ' (' + rich.favorite_flavors.join(', ') + ')' : '';
          parts.push('in-season: ' + rich.ingredient + flav);
        }
      }
    }catch(e){}
    var prods = currentProducts(); if(prods.length) parts.push('products: ' + prods.join(', '));
    return parts.length ? parts.join(' \u00b7 ') : '';
  }
  // recover the user's free-text base by stripping a trailing marker+suffix, if present
  function stripSuffix(val){
    var i = val.lastIndexOf(SUFFIX_MARKER);
    if(i === -1) return val;
    // only treat the tail as auto-context if it looks like our generated shape (starts market:/season:/products:)
    var tail = val.slice(i + SUFFIX_MARKER.length);
    if(/^(market:|season:|products:)/.test(tail)) return val.slice(0, i);
    return val;
  }
  // shared seams for the one brief assembly (#218/#236): prompt-chips.js owns __rebuildBrief and
  // reads these live, so the suffix shape cannot drift between the two files.
  window.__briefSuffixMarker = SUFFIX_MARKER;
  window.__briefContextSuffix = buildSuffix;
  // rewrite the visible prompt. Delegates to the one assembly in prompt-chips.js (free text + fresh
  // suffix + fresh directions tail) so market/season/product changes never drop active chip clauses.
  // Falls back to the local suffix-only write when that sibling is absent.
  function reflect(){
    if(typeof window.__rebuildBrief === 'function'){ window.__rebuildBrief(); grow(); return; }
    var suffix = buildSuffix();
    var base = window.__briefUserText || '';
    var next = suffix ? (base + SUFFIX_MARKER + suffix) : base;
    if(briefEl.value === next) return;
    window.__briefReflecting = true;
    briefEl.value = next;
    window.__briefReflecting = false;
    grow();
  }
  window.__reflectBrief = reflect;

  // manual edit: recover the user's base text via the shared free-text definition (which also drops
  // the chip-owned directions tail). Runs after prompt-chips' own adopter; we only update the stored
  // base here, never re-append — the next assembly re-canonicalizes.
  briefEl.addEventListener('input', function(){
    if(window.__briefReflecting || window.__chipSettingBrief) return;
    window.__briefUserText = (typeof window.__briefFreeText === 'function')
      ? window.__briefFreeText(briefEl.value) : stripSuffix(briefEl.value);
  });
  // a card change reassembles the brief in its own handler. Re-run the one assembly deferred to
  // end of task so card + market/season/products compose even if the card handler's own rebuild
  // was a no-op ordering edge.
  document.addEventListener('click', function(e){
    var card = e.target && e.target.closest ? e.target.closest('#promptChips .ff-check-card[data-brief]') : null;
    if(!card) return;
    setTimeout(function(){ reflect(); }, 0);
  });
  // market (declared #locality), season, and product checkbox changes all rebuild the suffix
  document.addEventListener('change', function(e){
    var t = e.target; if(!t) return;
    if(t.id === 'locality' || t.id === 'seasonalSelect' || (t.classList && t.classList.contains('sku-check'))){
      reflect();
    }
  });

  // =========================================================================
  // B3 — prompt-box autocomplete from loaded catalog + places. Suggests product names and market
  // names matching the last token being typed. Reuses the ff-products-results listbox visual pattern.
  // Keyboard accessible (arrow/enter/escape). Debounced. Does not touch #productSearch (its own combobox).
  // =========================================================================
  var box = document.getElementById('briefSuggest');
  if(box){
    var activeIdx = -1, items = [], debounceTimer = null;

    // the token under the caret: the trailing fragment after the last separator
    function currentToken(){
      var pos = briefEl.selectionStart != null ? briefEl.selectionStart : briefEl.value.length;
      var upto = briefEl.value.slice(0, pos);
      var m = upto.match(/[^\s,\u00b7\u2014\n]+$/);   // stop at whitespace, comma, middot, em-dash, newline
      return m ? { text:m[0], start: pos - m[0].length, end: pos } : { text:'', start: pos, end: pos };
    }
    function matches(frag){
      // guarded: window.skuCatalog / window.places can be upgraded async from fetched JSON; a malformed
      // payload could leave a non-array (or array of non-objects) behind. A throw here fires inside the
      // debounced input handler and would silently kill typing autocomplete. Degrade to no suggestions.
      try{
        var q = frag.toLowerCase();
        if(q.length < 2) return [];
        var out = [];
        var skuList = skus(); if(!Array.isArray(skuList)) skuList = [];
        var marketList = markets(); if(!Array.isArray(marketList)) marketList = [];
        skuList.forEach(function(p){
          var name = p && p.name ? String(p.name) : '';
          if(name && name.toLowerCase().indexOf(q) !== -1) out.push({ type:'product', name:name });
        });
        marketList.forEach(function(p){
          var name = p && p.place ? String(p.place) : '';
          if(name && name.toLowerCase().indexOf(q) !== -1) out.push({ type:'market', name:name });
        });
        return out.slice(0, 8);
      }catch(e){ return []; }
    }
    // typed-pattern recognition — scans the FULL brief text (a URL/zip is not a clean single token),
    // returns additive actionable/note rows. All guarded; never throws into the debounced handler.
    var ZIP_RE = /\b\d{5}\b/g, URL_RE = /https?:\/\/[^\s]+/g, MENTION_RE = /@[\w.-]+/g;
    function patternMatches(full){
      var out = [];
      try{
        var text = String(full || '');
        var seen = {};   // de-dupe by row label so repeated tokens do not stack
        ZIP_RE.lastIndex = 0; URL_RE.lastIndex = 0; MENTION_RE.lastIndex = 0;   // /g regex is persisted — reset per scan
        // 1. US ZIP -> resolve against places[] zip field
        var zm, zc = 0;
        while((zm = ZIP_RE.exec(text)) && zc < 3){
          zc++;
          var zip = zm[0];
          if(seen['zip:'+zip]) continue; seen['zip:'+zip] = 1;
          var place = markets().find(function(p){ return p && String(p.zip||'') === zip; });
          if(place){
            out.push({ type:'action', tag:'zip', action:'setmarket', market:place.market,
              name:'Set market: ' + (place.place || place.market) });
          } else {
            out.push({ type:'note', tag:'zip', noteOnly:true, name:'ZIP ' + zip + ' — no mapped market yet' });
          }
        }
        // 2. URL -> acknowledge, do not fetch
        var um, uc = 0;
        while((um = URL_RE.exec(text)) && uc < 2){
          uc++;
          if(seen['url']) break; seen['url'] = 1;
          out.push({ type:'note', tag:'link', noteOnly:true, name:'Reference link noted' });
        }
        // 3. @mention -> acknowledge, do not resolve
        var mm, mc = 0;
        while((mm = MENTION_RE.exec(text)) && mc < 3){
          mc++;
          var handle = mm[0];
          if(seen['mention:'+handle]) continue; seen['mention:'+handle] = 1;
          out.push({ type:'note', tag:'@', noteOnly:true, name:'Social handle: ' + handle });
        }
      }catch(e){ /* pattern scan must never break the autocomplete */ }
      return out;
    }
    function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];}); }
    function close(){
      box.hidden = true; box.innerHTML = ''; items = []; activeIdx = -1;
      briefEl.setAttribute('aria-expanded','false');
    }
    function open(list){
      items = list;
      box.innerHTML = list.map(function(it, i){
        var tag = it.tag || it.type;
        var tagCls = (it.type==='market' ? ' is-market' : (it.type==='action' ? ' is-action' : (it.type==='note' ? ' is-note' : '')));
        var optCls = it.noteOnly ? ' is-noteopt' : '';
        var role = it.noteOnly ? 'presentation' : 'option';
        var attrs = ' data-name="'+esc(it.name)+'"'
          + ' data-action="'+esc(it.action||'')+'"'
          + ' data-market="'+esc(it.market||'')+'"'
          + (it.noteOnly ? ' data-note="1"' : '');
        return '<div class="ff-suggest-opt'+optCls+'" role="'+role+'" id="briefSuggestOpt'+i+'" aria-selected="false"'+attrs+'>'
          + '<span class="ff-suggest-tag'+tagCls+'">'+esc(tag)+'</span>'
          + '<span class="ff-suggest-name">'+esc(it.name)+'</span></div>';
      }).join('');
      box.hidden = false; activeIdx = -1;
      briefEl.setAttribute('aria-expanded','true');
    }
    function setActive(i){
      var opts = box.querySelectorAll('.ff-suggest-opt');
      if(!opts.length) return;
      if(i < 0) i = opts.length - 1; if(i >= opts.length) i = 0;
      activeIdx = i;
      opts.forEach(function(o, j){ o.setAttribute('aria-selected', j===i ? 'true':'false'); });
      var el = opts[i]; if(el){ briefEl.setAttribute('aria-activedescendant', el.id); el.scrollIntoView({block:'nearest'}); }
    }
    // where the generated tail starts (-1 when the brief is pure free text)
    function generatedStart(val){
      var v = String(val == null ? '' : val);
      var dir = (typeof window.__briefDirBegin === 'string' && window.__briefDirBegin) ? window.__briefDirBegin : '— directions: ';
      var a = v.indexOf(SUFFIX_MARKER), b = v.indexOf(dir);
      if(a === -1) return b;
      if(b === -1) return a;
      return Math.min(a, b);
    }
    // insert the canonical name at the caret, replacing the token being typed. #236: a pick is
    // typing, not a reset — chips stay armed and typed text survives. When the caret sits inside
    // the owned tail the insert relocates to the end of the free text (writing into owned regions
    // would mangle them); owned regions are left byte-identical so no rebuild is needed.
    function choose(name){
      var val = briefEl.value;
      var caretPos = (briefEl.selectionStart != null) ? briefEl.selectionStart : val.length;
      var gs = generatedStart(val);
      window.__briefReflecting = true;
      var caret;
      if(gs !== -1 && caretPos >= gs){
        var prefix = val.slice(0, gs).replace(/\s+$/,'');
        var rest = val.slice(gs);
        var glue = prefix ? ' ' : '';
        briefEl.value = prefix + glue + name + rest;
        caret = (prefix + glue + name).length;
      } else {
        var tok = currentToken();
        var before = val.slice(0, tok.start);
        var after = val.slice(tok.end);
        var sep = (before && !/\s$/.test(before)) ? ' ' : '';
        briefEl.value = before + sep + name + after;
        caret = (before + sep + name).length;
      }
      try{ briefEl.setSelectionRange(caret, caret); }catch(e){}
      window.__briefReflecting = false;
      window.__briefUserText = (typeof window.__briefFreeText === 'function')
        ? window.__briefFreeText(briefEl.value) : stripSuffix(briefEl.value);
      grow();
      close();
      briefEl.focus();
    }
    // set the market from a zip-resolved action row: drive the declared #locality select generate() reads,
    // fire change so onLocality + reflect + any listeners run exactly as a manual pick would.
    function setMarket(code){
      try{
        var sel = document.getElementById('locality');
        if(sel){
          if(!Array.prototype.some.call(sel.options, function(o){ return o.value===code; })){
            var o = document.createElement('option'); o.value = code; o.textContent = code; sel.appendChild(o);
          }
          sel.value = code;
          sel.dispatchEvent(new Event('change', {bubbles:true}));
        }
      }catch(e){ /* market set must never throw out of the suggest handler */ }
      close();
      briefEl.focus();
    }
    // route a chosen row: note rows are inert, action rows drive their side effect, plain rows insert text
    function activate(it){
      if(!it || it.noteOnly) return;
      if(it.type==='action' && it.action==='setmarket' && it.market){ setMarket(it.market); return; }
      if(it.name) choose(it.name);
    }
    briefEl.addEventListener('input', function(){
      if(window.__briefReflecting || window.__chipSettingBrief) return;
      if(debounceTimer) clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function(){
        // whole scan+render is guarded: a throw inside the debounce callback cannot be caught by the
        // caller (it runs on a timer), so an unguarded throw here would silently kill autocomplete for
        // the rest of the session. On any failure, close the listbox and keep typing responsive.
        try{
          var tok = currentToken();
          var tokenList = tok.text ? matches(tok.text) : [];
          var patList = patternMatches(briefEl.value);
          // additive: pattern rows lead (actionable), then token substring matches. hard cap so the
          // listbox never renders hundreds of nodes even with a huge brief + long catalog.
          var list = patList.concat(tokenList).slice(0, 12);
          if(list.length) open(list); else close();
        }catch(e){ try{ close(); }catch(_e){} }
      }, 140);
    });
    briefEl.addEventListener('keydown', function(e){
      if(box.hidden) return;
      if(e.key === 'ArrowDown'){ e.preventDefault(); setActive(activeIdx + 1); }
      else if(e.key === 'ArrowUp'){ e.preventDefault(); setActive(activeIdx - 1); }
      else if(e.key === 'Enter'){ if(activeIdx >= 0 && items[activeIdx]){ e.preventDefault(); activate(items[activeIdx]); } }
      else if(e.key === 'Escape'){ e.preventDefault(); close(); }
    });
    box.addEventListener('mousedown', function(e){
      var opt = e.target && e.target.closest ? e.target.closest('.ff-suggest-opt') : null;
      if(!opt) return;
      e.preventDefault();
      if(opt.getAttribute('data-note')){ return; }   // note rows are inert acknowledgments
      var action = opt.getAttribute('data-action'), market = opt.getAttribute('data-market');
      if(action==='setmarket' && market){ setMarket(market); return; }
      choose(opt.getAttribute('data-name'));
    });
    briefEl.addEventListener('blur', function(){ setTimeout(close, 120); });   // allow mousedown to fire first
  }
})();
