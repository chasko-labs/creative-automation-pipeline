// === Season flavors — month-aware "In season here" engine (offline-first, zero-dep) ===
// Every market x every season resolves a flavor line: curated frontier calendars
// first, regional archetypes second, never empty. window.seasonFlavorFor(market,
// season) -> {text, source, frontier}. source is 'curated' (market override or
// in-season frontier items), 'frontier' (frontier shoulder), or 'archetype'
// (regional seasonality — the coach AI fallback covers event-anchored ideas there).
// Seasons accepted: 12 months, Spring/Summer/Fall/Winter, the 10 holiday labels,
// '' (year-round). Unknown input degrades to year-round, never throws.
(function(){
  'use strict';

  var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];
  var SEASON_OF = [0,0,2,2,2,1,1,1,3,3,3,0]; // Winter,Spring,Summer,Fall per month idx
  var SEASON_NAMES = ['Winter','Spring','Summer','Fall'];
  var HOLIDAY_MONTH = {'New Year':0,'Valentine\u2019s Day':1,'Easter':3,'Memorial Day':4,'Fourth of July':6,'Labor Day':8,'Halloween':9,'Thanksgiving':10,'Christmas':11,'Holiday season':11};

  // Resolve any season input to {month, label}. -1 month = year-round.
  function resolveSeason(season){
    var s = (season == null ? '' : String(season)).trim();
    if(!s) return {month:-1, label:'Year-round'};
    var mi = MONTHS.indexOf(s);
    if(mi !== -1) return {month:mi, label:s};
    var si = SEASON_NAMES.indexOf(s);
    if(si !== -1) return {month:[0,3,6,9][si], label:s};
    if(Object.prototype.hasOwnProperty.call(HOLIDAY_MONTH, s)){
      var hm = HOLIDAY_MONTH[s];
      return {month:hm, label:s};
    }
    return {month:-1, label:'Year-round'};
  }

  // Frontier harvest windows — mirrors featuredFrontierDetail seasons in data-core.js.
  // m = month indices with real items; off = honest shoulder line (no invented farms).
  var FRONTIER_CAL = {
    'US-CA-PESCADERO': {
      items:[{m:[2,3,4,5],t:'Castroville artichokes'},{m:[1,2,3,4,5],t:'Marin goat cheese'},{m:[4,5,6,7,8],t:'strawberries'},{m:[8,9,10,11,0,1],t:'Brussels sprouts'},{m:[10],t:'fall olive-oil press'}],
      off:'winter farm stands + stored sprouts',
      market:'Half Moon Bay Farmers Market (Saturdays) + Harley Farms farm stand'},
    'US-CA-JULIAN': {
      items:[{m:[7,8,9],t:'Julian apples (peak September)'},{m:[8,9],t:'pear cider'}],
      off:'gold-rush main street stands + holiday apple pies (orchards dormant)',
      market:'Julian farm stands + mountain orchards'},
    'US-CA-CASTROVILLE': {
      items:[{m:[2,3,4,5],t:'Castroville artichokes (peak April)'},{m:[4,5,6,7,8],t:'strawberries'},{m:[8,9,10,11,0,1],t:'Brussels sprouts'}],
      off:'winter artichoke stands + stored sprouts',
      market:'Castroville artichoke stands + Monterey Bay farmers markets'},
    'US-WA-NEAHBAY': {
      items:[{m:[4,5,6,7,8],t:'Makah salmon'},{m:[6,7],t:'huckleberry (peak August)'},{m:[2,3,4,5],t:'halibut (peak Apr-May)'}],
      off:'winter harbor + preserved salmon (fishing dormant)',
      market:'Washburn\u2019s General Store porch stands + Makah Days'},
    'US-SE-SANDERSVILLE': {
      items:[{m:[3,4],t:'strawberries'},{m:[4,5,6,7],t:'Georgia peaches (peak July)'},{m:[7,8],t:'muscadine grapes'},{m:[8,9,10],t:'sweet potatoes (peak October)'},{m:[9,10,11],t:'Georgia pecans (peak November)'}],
      off:'stored pecans + holiday baking season',
      market:'Sandersville downtown farmers market + Washington County stands'},
    'US-SW-TIMBERON': {
      items:[{m:[8,9,10],t:'pi\u00f1on harvest (exact months unconfirmed \u2014 research dispatch)'}],
      off:'high-country stands dormant \u2014 Cloudcroft Mercantile halo (research dispatch)',
      market:'Timberon General Store + Cloudcroft Mercantile halo'},
    'US-UT-OAKLEY': {
      items:[{m:[5,6,7,8],t:'Oakley Farmers Market at Rodeo Grounds (Jun-Sep, 2023 season)'},{m:[],t:'Splendor Valley Farms produce (exact months unconfirmed \u2014 research dispatch)'},{m:[0,1,2,3,4,5,6,7,8,9,10,11],t:'Oakley grass-fed beef + ranch butter, year-round'}],
      off:'ranch beef + butter, year-round (market dormant)',
      market:'Oakley Farmers Market at Oakley Rodeo Grounds'}
  };

  function frontierDetail(market){
    try{
      if(typeof featuredFrontierFor === 'function') return featuredFrontierFor(market);
    }catch(e){}
    return null;
  }

  // Climate month-windows for frontiers without a researched calendar: honest
  // region-level produce timing keyed by the MARKET's archetype. No farm names.
  var CLIMATE_WIN = {
    wasatch: [{m:[5,6,7,8],t:'stone fruit + sweet corn'},{m:[8,9],t:'orchard apples + pumpkins'},{m:[11,0,1],t:'storage roots + holiday baking'},{m:[2,3,4],t:'spring greens + ranch dairy'}],
    rockies: [{m:[6,7,8],t:'peaches + sweet corn'},{m:[8,9],t:'chile roast + apples'},{m:[9,10],t:'pumpkins + squash'},{m:[11,0,1,2,3,4,5],t:'root cellar + citrus halo'}],
    southwest: [{m:[7,8],t:'chile roast season'},{m:[8,9,10],t:'pinon + chile harvest'},{m:[11,0,1,2],t:'citrus + winter markets'},{m:[3,4,5,6],t:'spring greens + desert produce'}],
    southplains: [{m:[2,3,4],t:'strawberries + spring produce'},{m:[5,6,7],t:'peaches + corn + tomatoes'},{m:[8,9,10],t:'pecans + sweet potatoes'},{m:[11,0,1],t:'citrus + hearty greens'}],
    southeast: [{m:[3,4],t:'strawberries'},{m:[5,6,7],t:'peaches + butterbeans'},{m:[7,8],t:'muscadines'},{m:[8,9,10],t:'sweet potatoes + pecans'},{m:[11,0,1,2],t:'stored pecans + citrus + greens'}],
    tropical: [{m:[11,0,1,2,3],t:'citrus peak'},{m:[5,6,7],t:'mango season'},{m:[4,8,9,10],t:'tropical produce + tomatoes'}],
    newengland: [{m:[2,3],t:'maple sugaring'},{m:[5,6],t:'strawberries + greens'},{m:[6,7],t:'blueberries + sweet corn'},{m:[8,9],t:'apples + foliage markets'},{m:[10],t:'cranberries'},{m:[11,0,1],t:'root cellar + cider'}],
    heartland: [{m:[6,7,8],t:'sweet corn + tomatoes'},{m:[8,9],t:'apples + pumpkins'},{m:[10,11,0,1,2,3,4,5],t:'cellar apples + storage roots'}],
    north: [{m:[6,7],t:'short-season berries'},{m:[7,8],t:'wheat + sweet-corn harvest'},{m:[8,9],t:'apples + squash'},{m:[10,11,0,1,2,3,4,5],t:'storage + baking season'}],
    pacific: [{m:[1,2,3,4,5],t:'artichokes + asparagus + strawberries'},{m:[6,7,8],t:'stone fruit + berries'},{m:[8,9,10],t:'apples + pears + grapes'},{m:[11,0],t:'citrus + winter greens'}],
    desert: [{m:[11,0,1,2],t:'citrus + dates peak'},{m:[3,4],t:'spring greens + early fruit'},{m:[5,6],t:'melons'},{m:[7,8],t:'heat lull, early markets'},{m:[9,10],t:'date harvest + citrus arrives'}],
    alaska: [{m:[5,6,7],t:'salmon runs + berries'},{m:[7,8],t:'harvest + berries'},{m:[9,10,11,0,1,2,3,4],t:'cellar + preserved salmon'}]
  };

  // month items for a frontier: researched calendar first, climate windows
  // second, frontier detail items as the year-round fallback. Never empty
  // when a detail object exists.
  function frontierMonthItems(det, month, arch){
    var fk = det && det.frontier;
    var cal = fk && FRONTIER_CAL[fk];
    if(cal){
      if(month === -1) return {items:[cal.items.length ? cal.items[0].t : cal.off], shoulder:false, cal:true};
      var hits = [];
      cal.items.forEach(function(w){ if(w.m.indexOf(month) !== -1) hits.push(w.t); });
      if(hits.length) return {items:hits.slice(0,2), shoulder:false, cal:true};
      return {items:[cal.off], shoulder:true, cal:true};
    }
    var wins = CLIMATE_WIN[arch] || CLIMATE_WIN.heartland;
    if(month === -1){
      var base = (det && det.items && det.items[0]) || 'seasonal produce';
      return {items:[base], shoulder:false, cal:false};
    }
    var found = [];
    wins.forEach(function(w){ if(w.m.indexOf(month) !== -1) found.push(w.t); });
    if(found.length) return {items:found.slice(0,2), shoulder:false, cal:false};
    return {items:[(det && det.items && det.items[0]) || 'seasonal produce'], shoulder:true, cal:false};
  }

  function frontierTownShort(det){
    try{
      if(det && det.place) return String(det.place).split(' \u2014 ')[0];
    }catch(e){}
    return null;
  }

  // Regional archetypes — honest region-level seasonality, no invented farm names.
  // seasons[0..3] = Winter/Spring/Summer/Fall lines; peaks override single months.
  var ARCHETYPES = {
    wasatch: {seasons:['storage roots + holiday baking + ski-lodge cocoa season','spring greens + ranch dairy as stands reopen','Jensen Farms stone fruit + rhubarb at Park City + Oakley markets','orchard apples + squash before first Wasatch snow'],
      peaks:{6:'peach peak + sweet corn',8:'apple + pumpkin harvest',11:'holiday baking + citrus halo'}},
    rockies: {seasons:['root cellar + citrus halo + ski-town cocoa season','spring greens + early asparagus stands','Palisade peaches + Olathe corn at trailhead markets','Pueblo chile roast + apples + first-snow squash'],
      peaks:{7:'Palisade peach peak',8:'green-chile roast season',9:'apple + pumpkin harvest'}},
    southwest: {seasons:['citrus + winter farmers markets + red-chile ristras','spring greens + early desert produce','summer squash + desert heat (early-morning markets)','Hatch chile roast + pi\u00f1on season'],
      peaks:{7:'Hatch roast opens (Aug-Sep)',8:'Hatch by the bushel + pi\u00f1on',11:'citrus + tamale season'}},
    southplains: {seasons:['citrus valley fruit + hearty greens + stock-show season','strawberries + spring onions + wildflowers','peaches + blackberries + sweet corn + tomato season','pecan + sweet-potato + fall harvest fairs'],
      peaks:{5:'Fredericksburg peach season opens',9:'pecan + sweet-potato harvest',10:'pecan peak + citrus arrives'}},
    southeast: {seasons:['citrus + stored pecans + greens + holiday baking','strawberries + spring peas + Vidalia onions','peaches + butterbeans + tomato + corn season','pecans + sweet potatoes + muscadines + harvest fairs'],
      peaks:{6:'peach peak',9:'pecan + sweet-potato harvest',10:'pecan peak'}},
    tropical: {seasons:['citrus peak + guava + winter produce season','mango blossom + spring citrus tail','mango + lychee + summer produce season','carambola + citrus arrives + holiday produce'],
      peaks:{0:'citrus peak',6:'mango season',11:'citrus + holiday produce'}},
    newengland: {seasons:['root cellar + cider + holiday baking season','maple sugaring + early greens','berries + sweet corn + tomato season','apples + pumpkins + foliage-market season'],
      peaks:{2:'maple sugaring peak',6:'blueberry season',8:'apple harvest + foliage',10:'cranberry season'}},
    heartland: {seasons:['stored apples + root cellar + baking season','asparagus + rhubarb + maple tail','sweet corn + tomatoes + berry season','apples + pumpkins + harvest season'],
      peaks:{6:'sweet-corn peak',8:'apple + pumpkin harvest',9:'cider-mill season'}},
    north: {seasons:['deep-winter storage + game + baking season','late thaw greens + maple tail','short-season berries + sweet corn + wheat season','harvest + apple + first-freeze squash'],
      peaks:{6:'short-season berry peak',7:'wheat + sweet-corn harvest',8:'apple + squash harvest'}},
    pacific: {seasons:['citrus + Dungeness crab + winter greens season','artichokes + asparagus + strawberry start','stone fruit + berries + tomato season','apples + pears + grape-harvest season'],
      peaks:{1:'Dungeness + citrus',5:'strawberry peak',7:'stone-fruit peak',8:'apple + grape harvest'}},
    desert: {seasons:['citrus + date + winter produce peak season','spring greens + early stone fruit','extreme-heat lull \u2014 early-morning markets + melon season','dates + citrus arrives + Hatch halo'],
      peaks:{0:'citrus + date peak',5:'melon season',9:'date harvest + citrus arrives'}},
    alaska: {seasons:['root cellar + preserved salmon + winter market season','breakup greens + early herbs','salmon runs + summer berries + midnight-sun produce','root harvest + preserved-fish + first-snow season'],
      peaks:{5:'early salmon runs',6:'salmon + berry peak',7:'berry + harvest season'}}
  };

  // market -> archetype: specific prefixes first, broad prefixes last.
  var ARCH_RULES = [
    ['US-UT-', 'wasatch'], ['US-MW-PARKCITY', 'wasatch'], ['US-MW-WASATCH', 'wasatch'],
    ['US-MW-JACKSONHOLE', 'rockies'], ['US-MW-MISSOULA', 'rockies'], ['US-MW-BOISE', 'rockies'],
    ['US-MW-DEN', 'rockies'], ['US-W-BOULDER', 'rockies'], ['US-W-RENO', 'rockies'],
    ['US-MW-FARGO', 'north'], ['US-MW-MINNEAPOLIS2', 'north'],
    ['US-W-ANCHORAGE', 'alaska'], ['US-W-HONOLULU', 'tropical'], ['US-SE-FL', 'tropical'],
    ['US-W-VEGAS', 'desert'], ['US-MW-PHX2', 'desert'], ['US-SW-PHX', 'desert'],
    ['US-W-', 'pacific'], ['US-CA-', 'pacific'],
    ['US-SC-', 'southplains'], ['US-SW-OKC', 'southplains'],
    ['US-SW-', 'southwest'], ['US-SE-', 'southeast'], ['US-NE-', 'newengland'],
    ['US-MW-', 'heartland']
  ];

  function archetypeFor(market){
    var m = String(market || '');
    for(var i = 0; i < ARCH_RULES.length; i++){
      if(m.indexOf(ARCH_RULES[i][0]) === 0) return ARCH_RULES[i][1];
    }
    return 'heartland';
  }

  function archetypeLine(arch, month){
    var a = ARCHETYPES[arch] || ARCHETYPES.heartland;
    if(month === -1) return a.seasons[1] + ' \u2014 ' + a.seasons[2];
    if(a.peaks[month]) return a.peaks[month];
    return a.seasons[SEASON_OF[month]];
  }

  // Curated market bases (from the flavorMap voice in generate.js).
  var MARKET_BASE = {
    'US-MW-PARKCITY-84098': 'Wasatch Back \u2014 Jensen Farms peaches + Copper Moose rhubarb compote at Park City Farmers Market',
    'US-UT-KAMASVALLEY': 'Kamas Valley \u2014 Oakley grass-fed beef + Ballerina Farm butter at Oakley Rodeo Grounds market',
    'US-SW-LASCRUCES': 'Hatch green chile, roasted by the bushel \u2014 Organ Mountains bench',
    'US-CA-PESCADERO': 'Pescadero farm stands \u2014 Castroville artichokes + Marin goat cheese',
    'US-WA-NEAHBAY': 'Neah Bay harbor \u2014 Makah salmon + huckleberry at Washburn\u2019s General Store'
  };

  function placeName(market){
    try{
      if(typeof places !== 'undefined'){
        for(var i = 0; i < places.length; i++){
          if(places[i].market === market) return (places[i].place || market).split(' \u2014 ')[0];
        }
      }
    }catch(e){}
    return market;
  }

  // Main entry: always returns {text, source, frontier}. Never null, never throws.
  function seasonFlavorFor(market, season){
    try{
      var mk = market || 'US-MW-PARKCITY-84098';
      var r = resolveSeason(season);
      var det = frontierDetail(mk);
      var arch = archetypeFor(mk);
      var fm = det ? frontierMonthItems(det, r.month, arch) : {items:[], shoulder:true, cal:false};
      var line = archetypeLine(arch, r.month);
      var place = placeName(mk);
      var town = frontierTownShort(det);
      var text, source;
      if(MARKET_BASE[mk] && r.month !== -1){
        text = place + ': ' + r.label + ' brings ' + fm.items.join(' + ') + ' \u2014 ' + MARKET_BASE[mk] + '.';
        source = fm.shoulder ? 'frontier' : 'curated';
      } else if(MARKET_BASE[mk]){
        text = place + ': ' + MARKET_BASE[mk] + ' \u2014 ' + line + '.';
        source = 'curated';
      } else if(town && fm.items.length && !fm.shoulder){
        text = place + ': ' + r.label + ' brings ' + fm.items.join(' + ') + ' \u2014 Featured Frontier: ' + town + '.';
        source = fm.cal ? 'curated' : 'frontier';
      } else if(town && fm.items.length){
        text = place + ': ' + r.label + ' \u2014 ' + line + ' \u2014 Featured Frontier: ' + town + ' (' + fm.items[0] + ').';
        source = 'frontier';
      } else {
        text = place + ': ' + r.label + ' \u2014 ' + line + '.';
        source = 'archetype';
      }
      try{ window.__seasonFlavorSource = source; }catch(e){}
      return {text:text, source:source, frontier:(det && det.frontier) || null};
    }catch(e){
      return {text:String(market || '') + ': seasonal frontier flavor.', source:'archetype', frontier:null};
    }
  }

  try{
    window.seasonFlavorFor = seasonFlavorFor;
    window.__seasonFlavorSource = null;
  }catch(e){}
})();
