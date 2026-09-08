/* =============================================================================
   PROTOTYPE VIEW — live layout overlay (dev only, gated behind ?debug=layout)
   Draws the form+function diagram over the REAL rendered page so it cannot drift.
   100% additive: without ?debug=layout this block adds zero DOM and no listeners
   that touch page behavior. All overlay DOM lives under a single #proto-overlay
   node so it is trivially removable. pointer-events:none end to end.
   View: index.html?debug=layout (then enter the shared word on the courtesy screen)
   ============================================================================= */
(function(){
  // gate: do nothing at all unless ?debug=layout is present
  if(!new URLSearchParams(location.search).has('debug') ||
     new URLSearchParams(location.search).get('debug')!=='layout') return;

  // role palette — DEBUG colors, not kodiak brand tokens (intentional for a dev overlay)
  var ROLE={
    brand:      '#1A73E8',
    input:      '#188038',
    control:    '#9334E6',
    output:     '#E8710A',
    navigation: '#00897B',
    decorative: '#9AA0A6',
    meta:       '#5F6368'
  };
  var DASHED={decorative:1, meta:1}; // dashed outline for these roles

  // single source of truth: one record per structural element
  // {sel, name, fn, role, state}
  var PROTOTYPE_MAP=[
    {sel:'body',                              name:'page body',       fn:'root of visible page',                      role:'meta',       state:'always'},
    {sel:'header.kodiak-header',              name:'site header',     fn:'brand header, sticky on scroll',            role:'brand',      state:'always'},
    {sel:'.kodiak-headline-plate',            name:'headline plate',  fn:'green plate holding page title',            role:'brand',      state:'always'},
    {sel:'.wrap',                             name:'content wrap',    fn:'centered main content column',              role:'meta',       state:'always'},
    {sel:'.card[data-mcp="campaign-brief"]',  name:'campaign card',   fn:'primary create-a-campaign surface',         role:'control',    state:'always'},
    {sel:'.ff-prompt',                        name:'prompt bar',      fn:'Firefly-style campaign prompt surface',     role:'input',      state:'always'},
    {sel:'.ff-inputwrap',                     name:'input row',       fn:'textarea + upload + create button',         role:'input',      state:'always'},
    {sel:'#campaignBrief',                    name:'brief textarea',  fn:'type the campaign idea',                    role:'input',      state:'always'},
    {sel:'#promptUpload',                     name:'upload button',   fn:'opens image/document upload',               role:'control',    state:'always'},
    {sel:'#generateCampaign',                 name:'create button',   fn:'generates full campaign set',               role:'control',    state:'always'},
    {sel:'.ff-controlrow',                    name:'control row',     fn:'market, season, location, detail controls', role:'control',    state:'always'},
    {sel:'#marketDisclosure',                 name:'market picker',   fn:'choose target market (disclosure)',         role:'control',    state:'always'},
    {sel:'#useMyLocation',                    name:'my location',     fn:'snap to nearest market',                    role:'control',    state:'always'},
    {sel:'#seasonalSelect',                   name:'season select',   fn:'pick month/season/holiday',                 role:'input',      state:'always'},
    {sel:'.ff-detail',                        name:'detail block',    fn:'featured frontier + languages readout',     role:'output',     state:'always'},
    {sel:'#existingAssets',                   name:'product chooser', fn:'add up to 3 Kodiak SKUs (disclosure)',      role:'control',    state:'always'},
    {sel:'.ff-tray#selectionTray',            name:'selection tray',  fn:'staged assets + chosen SKU chips',          role:'output',     state:'js-created'},
    {sel:'.ff-optiongroup',                   name:'option group',    fn:'campaign starting-point chips',             role:'control',    state:'always'},
    {sel:'#promptChips',                      name:'chip row',        fn:'quick-start theme pills',                   role:'control',    state:'always'},
    {sel:'#downloadPack',                     name:'download pack',   fn:'downloads campaign zip',                    role:'control',    state:'always'},
    {sel:'.ff-ridge',                         name:'ridge divider',   fn:'decorative Wasatch silhouette band',        role:'decorative', state:'always'},
    {sel:'#previewCard',                      name:'preview card',    fn:'campaign preview in three sizes (disclosure)', role:'output',  state:'always'},
    {sel:'#preview',                          name:'preview region',  fn:'renders 1x1/9x16/16x9 (built on generate)', role:'output',     state:'js-created'},
    {sel:'.ff-detailslink-row',               name:'details link row',fn:'link to the design-system page',            role:'navigation', state:'always'},
    {sel:'#aboutTool',                        name:'about tool',      fn:'explains what the tool does (disclosure)',  role:'output',     state:'always'},
    {sel:'#buildStamp',                       name:'build stamp',     fn:'shows live build version',                  role:'meta',       state:'always'},
    {sel:'.render-set',                       name:'render set',      fn:'multi-size render tiles (built on generate)', role:'output',   state:'js-created'},
    {sel:'.provenance',                       name:'provenance panel',fn:'generation-source disclosure (built on generate)', role:'output', state:'js-created'}
  ];

  var OVERLAY_ID='proto-overlay';
  var rafPending=false;
  var hidden=false; // "L" toggle state

  function hexToRgba(hex, a){
    var h=hex.replace('#','');
    var r=parseInt(h.substring(0,2),16),
        g=parseInt(h.substring(2,4),16),
        b=parseInt(h.substring(4,6),16);
    return 'rgba('+r+','+g+','+b+','+a+')';
  }

  function ensureOverlay(){
    var o=document.getElementById(OVERLAY_ID);
    if(o) return o;
    o=document.createElement('div');
    o.id=OVERLAY_ID;
    o.style.cssText='position:absolute;top:0;left:0;width:0;height:0;'+
      'pointer-events:none;z-index:2147483000;';
    document.body.appendChild(o);
    return o;
  }

  function makeBox(rect, rec){
    var color=ROLE[rec.role]||ROLE.meta;
    var dashed=!!DASHED[rec.role];
    var box=document.createElement('div');
    box.style.cssText=
      'position:absolute;pointer-events:none;box-sizing:border-box;'+
      'top:'+(rect.top+window.scrollY)+'px;'+
      'left:'+(rect.left+window.scrollX)+'px;'+
      'width:'+rect.width+'px;'+
      'height:'+rect.height+'px;'+
      'outline:2px '+(dashed?'dashed':'solid')+' '+color+';'+
      'outline-offset:-1px;'+
      'background:'+hexToRgba(color,0.08)+';';
    var chip=document.createElement('div');
    chip.textContent=rec.name+' — '+rec.fn;
    chip.style.cssText=
      'position:absolute;top:0;left:0;pointer-events:none;'+
      'font:600 10px/1.3 system-ui,-apple-system,sans-serif;'+
      'white-space:nowrap;max-width:96vw;overflow:hidden;text-overflow:ellipsis;'+
      'background:'+color+';color:#fff;padding:1px 5px;border-radius:0 0 3px 0;';
    box.appendChild(chip);
    return box;
  }

  function isVisible(el){
    var r=el.getBoundingClientRect();
    return r.width>0 && r.height>0;
  }

  function legendRole(){
    var panel=document.createElement('div');
    panel.style.cssText=
      'position:fixed;left:8px;bottom:8px;pointer-events:none;'+
      'font:500 11px/1.5 system-ui,-apple-system,sans-serif;color:#fff;'+
      'background:rgba(32,33,36,0.92);padding:8px 10px;border-radius:6px;'+
      'max-width:280px;box-shadow:0 2px 8px rgba(0,0,0,0.4);';
    var title=document.createElement('div');
    title.textContent='role → outline color';
    title.style.cssText='font-weight:700;margin-bottom:4px;letter-spacing:.02em;';
    panel.appendChild(title);
    Object.keys(ROLE).forEach(function(role){
      var row=document.createElement('div');
      row.style.cssText='display:flex;align-items:center;gap:6px;';
      var sw=document.createElement('span');
      sw.style.cssText='display:inline-block;width:12px;height:12px;border-radius:2px;'+
        'background:'+hexToRgba(ROLE[role],0.5)+';'+
        'border:2px '+(DASHED[role]?'dashed':'solid')+' '+ROLE[role]+';';
      var lbl=document.createElement('span');
      lbl.textContent=role;
      row.appendChild(sw); row.appendChild(lbl);
      panel.appendChild(row);
    });
    var note=document.createElement('div');
    note.textContent='?debug=layout — resize the window to see responsive form change';
    note.style.cssText='margin-top:6px;opacity:.75;font-size:10px;';
    panel.appendChild(note);
    return panel;
  }

  function legendPending(items){
    if(!items.length) return null;
    var panel=document.createElement('div');
    panel.style.cssText=
      'position:fixed;right:8px;bottom:8px;pointer-events:none;'+
      'font:500 11px/1.5 system-ui,-apple-system,sans-serif;color:#fff;'+
      'background:rgba(32,33,36,0.92);padding:8px 10px;border-radius:6px;'+
      'max-width:300px;box-shadow:0 2px 8px rgba(0,0,0,0.4);';
    var title=document.createElement('div');
    title.textContent='appears on interaction';
    title.style.cssText='font-weight:700;margin-bottom:4px;letter-spacing:.02em;';
    panel.appendChild(title);
    items.forEach(function(rec){
      var row=document.createElement('div');
      row.style.cssText='display:flex;align-items:center;gap:6px;';
      var sw=document.createElement('span');
      sw.style.cssText='display:inline-block;width:10px;height:10px;border-radius:50%;'+
        'background:'+ROLE[rec.role]+';flex:0 0 auto;';
      var lbl=document.createElement('span');
      lbl.textContent=rec.name+' — '+rec.fn;
      lbl.style.cssText='white-space:nowrap;overflow:hidden;text-overflow:ellipsis;';
      row.appendChild(sw); row.appendChild(lbl);
      panel.appendChild(row);
    });
    return panel;
  }

  function render(){
    if(hidden) return;
    var overlay=ensureOverlay();
    overlay.innerHTML=''; // clear + redraw
    var pending=[];
    PROTOTYPE_MAP.forEach(function(rec){
      var nodes=document.querySelectorAll(rec.sel);
      if(!nodes.length){
        if(rec.state==='js-created') pending.push(rec);
        return;
      }
      var drewOne=false;
      Array.prototype.forEach.call(nodes, function(el){
        if(!isVisible(el)) return;
        overlay.appendChild(makeBox(el.getBoundingClientRect(), rec));
        drewOne=true;
      });
      // js-created element exists in DOM but not yet visible -> still list as pending
      if(!drewOne && rec.state==='js-created') pending.push(rec);
    });
    overlay.appendChild(legendRole());
    var pend=legendPending(pending);
    if(pend) overlay.appendChild(pend);
  }

  function scheduleRender(){
    if(rafPending) return;
    rafPending=true;
    requestAnimationFrame(function(){ rafPending=false; render(); });
  }

  // redraw hooks — all additive, none alter existing behavior
  window.addEventListener('resize', scheduleRender, {passive:true});
  window.addEventListener('scroll', scheduleRender, {passive:true});

  // re-run after load so js-created + disclosure elements get outlined once they exist
  window.addEventListener('load', function(){ setTimeout(render, 600); });

  // clicks on generate / any <summary> reveal js-created + disclosure-opened elements
  document.addEventListener('click', function(e){
    var t=e.target;
    if(!t) return;
    if((t.closest && (t.closest('#generateCampaign') || t.closest('summary')))){
      setTimeout(render, 600);
    }
  }, true);

  // "L" toggles the overlay off/on for a clean screenshot
  document.addEventListener('keydown', function(e){
    if(e.key==='l' || e.key==='L'){
      hidden=!hidden;
      var o=document.getElementById(OVERLAY_ID);
      if(hidden){ if(o) o.innerHTML=''; }
      else { render(); }
    }
  });

  // first paint
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded', scheduleRender);
  } else {
    scheduleRender();
  }
})();
