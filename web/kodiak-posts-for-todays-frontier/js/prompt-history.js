// prompt-history.js — semi-permanent prompt ledger (offline-first, zero-dependency).
//
// Every campaign preview records one entry: what was SENT (the dish-first
// scene prompt, the copy base, the market/season/product) and what CAME BACK
// (headline, recipe, render engine, image url). Stored in localStorage under
// a versioned key (cap 100, newest first) so the ledger survives reloads and
// needs no backend. prompt-history.html renders it article-per-run in the
// aaliyah-review style (prompt / dish / base / headline / recipe / render).
//
// Loaded with bare `window` + `localStorage` globals so both the browser and
// the vitest suite (which evals this file with stub globals) share one path.
// Every storage touch is guarded — private-mode throws degrade to a
// memory-only ledger, never a broken generate.
(function(){
  'use strict';
  var KEY = 'kodiak.promptHistory.v1';
  var CAP = 100;
  var mem = [];

  function store(){
    try{
      if(typeof localStorage !== 'undefined' && localStorage) return localStorage;
    }catch(e){}
    return null;
  }

  function read(){
    var s = store();
    if(s){
      try{
        var raw = s.getItem(KEY);
        if(!raw) return [];
        var parsed = JSON.parse(raw);
        return Array.isArray(parsed) ? parsed : [];
      }catch(e){ return mem.slice(); }
    }
    return mem.slice();
  }

  function write(entries){
    var trimmed = (Array.isArray(entries) ? entries : []).slice(0, CAP);
    var s = store();
    if(s){
      try{ s.setItem(KEY, JSON.stringify(trimmed)); }catch(e){}
    }
    mem = trimmed.slice();
    return trimmed;
  }

  function cleanStr(v){
    return (v == null ? '' : String(v));
  }

  /**
   * Record one preview run. Only plain-string fields are kept (no DOM, no
   * file blobs) so the entry stays JSON-serializable and small.
   * @param {Object<string, unknown>} entry
   * @returns {Object<string, string>|null} the stored entry, or null when empty
   */
  function record(entry){
    try{
      entry = (entry && typeof entry === 'object') ? entry : {};
      var stored = {
        ts: cleanStr(entry.ts) || new Date().toISOString(),
        market: cleanStr(entry.market),
        season: cleanStr(entry.season),
        product: cleanStr(entry.product),
        dish: cleanStr(entry.dish),
        base: cleanStr(entry.base),
        scene_prompt: cleanStr(entry.scene_prompt),
        headline: cleanStr(entry.headline),
        recipe: cleanStr(entry.recipe),
        source: cleanStr(entry.source),
        engines: (entry.engines && typeof entry.engines === 'object')
          ? JSON.stringify(entry.engines) : cleanStr(entry.engines),
        image_url: cleanStr(entry.image_url)
      };
      // Empty record (nothing sent, nothing back) is noise — skip it.
      if(!stored.scene_prompt && !stored.base && !stored.headline && !stored.image_url) return null;
      var entries = read();
      entries.unshift(stored);
      write(entries);
      return stored;
    }catch(e){ return null; }
  }

  function clear(){
    try{ write([]); }catch(e){}
  }

  var api = { record: record, read: read, clear: clear, KEY: KEY, CAP: CAP };
  try{
    if(typeof window !== 'undefined' && window) window.KODIAK_promptHistory = api;
  }catch(e){}
  // CommonJS seam for the vitest suite (browser keeps the window global).
  try{
    if(typeof module !== 'undefined' && module && module.exports) module.exports = api;
  }catch(e){}
})();
