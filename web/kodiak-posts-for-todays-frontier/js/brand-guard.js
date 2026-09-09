// === KODIAK-forbidden-in-copy law (frontend enforcement) ===
// Standing law: bare KODIAK never ships in customer-visible campaign copy
// (logo lockups only). Allowed in copy: "Kodiak Cakes", "Kodiak Park City",
// and #kodiakcakes-style hashtags. This guard is enforcement only — it
// rewrites the brand mark and never invents translations or copy around it.
//
// Producers covered: flavorMap/local-flavor readout, campaign-copy renderers
// (paintCampaignCopy, renderPlatformCopy, paintCopyPanel, locCaptionHtml),
// resting copy, figcaptions. Call KODIAK_brandClean() on any string before it
// is painted into those surfaces; KODIAK_hasBareKodiak() is the test hook.
(function(){
  'use strict';

  // True when text carries a bare KODIAK/Kodiak brand mark outside the
  // allowed forms. Hashtags (#kodiakcakes…) and the multiword marks
  // "Kodiak Cakes" / "Kodiak Park City" are stripped before scanning.
  function hasBareKodiak(text){
    if(text == null) return false;
    var s = String(text);
    if(!s) return false;
    s = s.replace(/#[A-Za-z0-9_-]*/g, ' ');
    s = s.replace(/\bKodiak\s+Cakes\b/gi, ' ');
    s = s.replace(/\bKodiak\s+Park\s+City\b/gi, ' ');
    return /\bKodiak\b/i.test(s);
  }

  // Rewrite only the brand mark: bare KODIAK (any case, optional ®/™)
  // becomes "Kodiak Cakes"; all-caps allowed forms are title-cased.
  // Hashtag segments pass through untouched. Surrounding words are never
  // reworded or translated.
  function brandClean(text){
    if(text == null) return text;
    var parts = String(text).split(/(#[A-Za-z0-9_-]*)/g);
    for(var i = 0; i < parts.length; i++){
      if(i % 2 === 1) continue;   // hashtag segment — allowed, untouched
      var seg = parts[i];
      seg = seg.replace(/\bKODIAK\s+CAKES\b/gi, 'Kodiak Cakes');
      seg = seg.replace(/\bKODIAK\s+PARK\s+CITY\b/gi, 'Kodiak Park City');
      seg = seg.replace(/\bKODIAK\b[\u00AE\u2122]?/g, 'Kodiak Cakes');
      seg = seg.replace(/\bKodiak\b(?!\s+(Cakes|Park\s+City))/g, 'Kodiak Cakes');
      parts[i] = seg;
    }
    return parts.join('');
  }

  try{
    window.KODIAK_hasBareKodiak = hasBareKodiak;
    window.KODIAK_brandClean = brandClean;
  }catch(e){}
})();
