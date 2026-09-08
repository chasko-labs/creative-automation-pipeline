// === Progress timeline — slim tracker (Setup + 5/6/7) with a live heuristic line ===
// The note mirrors ONLY real page events: #sampleStatus + #generateCampaignStatus
// text (the exact strings generate.js / campaign-sections.js already write) and the
// gate/assets hidden states. No invented events, no new instrumentation — if a
// source goes quiet the line simply keeps the last real event.
(function(){
  'use strict';
  var bar = document.getElementById('progressTimeline');
  if(!bar) return;
  var note = document.getElementById('timelineNote');
  var nodes = {};
  Array.prototype.forEach.call(bar.querySelectorAll('[data-node]'), function(li){
    nodes[li.getAttribute('data-node')] = li;
  });
  function set(node, state){
    var li = nodes[node];
    if(li && li.getAttribute('data-state') !== state) li.setAttribute('data-state', state);
  }
  function say(text){
    if(note && text && note.textContent !== text) note.textContent = text;
  }
  window.__kodiakTimelineNote = say;   // optional direct hook; observers below are the main feed

  function syncFromDom(){
    try{
      var brief = document.getElementById('campaignBrief');
      var briefFull = !!(brief && brief.value && brief.value.trim());
      var gate = document.getElementById('generateCampaignSection');
      var gated = !gate || gate.getAttribute('data-gated') !== 'false';
      var assets = document.getElementById('campaignAssetsSection');
      var assetsShown = !!(assets && !assets.hidden);
      if(assetsShown){ set('setup','done'); set('preview','done'); set('generate','done'); set('assets','done'); return; }
      set('setup', briefFull ? 'done' : 'active');
      var sample = document.getElementById('sampleStatus');
      var sampleText = (sample && sample.textContent || '').trim();
      var previewReady = /ready/i.test(sampleText);
      // Preview stays greyed (todo) until Create is hit — sampleStatus only
      // carries text once a run starts. Composing = active, ready = done.
      var createHit = sampleText.length > 0;
      set('preview', previewReady ? 'done' : (createHit ? 'active' : 'todo'));
      set('generate', gated ? 'locked' : 'active');
      set('assets','todo');
    }catch(e){ /* timeline must never break the page */ }
  }

  // brief typing advances Setup; status mirrors feed the note + preview state.
  try{
    var briefEl = document.getElementById('campaignBrief');
    if(briefEl) briefEl.addEventListener('input', syncFromDom);
    var sampleEl = document.getElementById('sampleStatus');
    if(sampleEl && typeof MutationObserver !== 'undefined'){
      new MutationObserver(function(){
        try{
          var t = (sampleEl.textContent || '').trim();
          if(t) say(t);
          syncFromDom();
        }catch(e){}
      }).observe(sampleEl, {childList:true, characterData:true, subtree:true});
    }
    var genStatus = document.getElementById('generateCampaignStatus');
    if(genStatus && typeof MutationObserver !== 'undefined'){
      new MutationObserver(function(){
        try{
          var t = (genStatus.textContent || '').trim();
          if(t) say(t);
        }catch(e){}
      }).observe(genStatus, {childList:true, characterData:true, subtree:true});
    }
    var gateEl = document.getElementById('generateCampaignSection');
    if(gateEl && typeof MutationObserver !== 'undefined'){
      new MutationObserver(syncFromDom).observe(gateEl, {attributes:true, attributeFilter:['data-gated']});
    }
    var assetsEl = document.getElementById('campaignAssetsSection');
    if(assetsEl && typeof MutationObserver !== 'undefined'){
      new MutationObserver(syncFromDom).observe(assetsEl, {attributes:true, attributeFilter:['hidden']});
    }
  }catch(e){ /* observers are enhancement; initial sync below still runs */ }
  syncFromDom();
})();
