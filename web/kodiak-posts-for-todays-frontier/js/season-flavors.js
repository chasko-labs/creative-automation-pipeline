/**
 * season-flavors.js — month-aware "In season here" engine (offline-first zero-dependency)
 *
 * What it is:
 *   Resolves every market × every season into a single display line for the
 *   "In season here" surface. The engine runs offline in the browser with no
 *   network dependency and no external library.
 *
 * Why it exists:
 *   Markets need a localized seasonal line even when the canonical pair file
 *   has not yet been fetched or when a frontier has no researched produce
 *   calendar for the requested month. This file guarantees a line for every
 *   input without ever fabricating a farm name or produce claim.
 *
 * Canonical data derivation:
 *   - Primary source of truth is `data/localization/retailer-frontier-pairs.json`.
 *     Each entry there pairs a metro market (for example US-MW-PARKCITY-84098)
 *     with a frontier sister (for example US-UT-OAKLEY), and carries
 *     `monthly_ingredients` (YYYY-MM → ingredient at the frontier farmers market)
 *     and `seasonal_moments` (holiday and season entries). The richest example
 *     is the US-OH-LEBANON frontier whose September pawpaws entry was added in
 *     2026-09 and is typed through `FrontierCalendarEntry`.
 *   - Secondary inline source is `featuredFrontierDetail` in `data-core.js`,
 *     which maps every market to its featured frontier via
 *     `marketFeaturedFrontier` and `featuredFrontierDetail`. That map declares
 *     the frontier place name, its `items` (produce names), `seasons` (month
 *     windows as text), and `farmersMarket` URL. `FRONTIER_CAL` below is a
 *     hand-curated month-index mirror of those season strings so lookups stay
 *     constant-time and offline.
 *   - `frontier-contracts.js` types the calendar shape as
 *     `FrontierCalendarEntry` — `{ items: {m:number[], t:string}[], off:string, market:string }`
 *     — and this file imports that type via JSDoc for editor checking.
 *
 * How it degrades — three-tier fallback ladder (never empty never throws):
 *   1. Curated frontier calendar (`FRONTIER_CAL` hit + in-season match) → source `curated`.
 *      Month maps to one or two named items that are in season there.
 *   2. Frontier shoulder (`FRONTIER_CAL` hit but month has no in-season items) → source `frontier`.
 *      Returns the `off` line — stored harvest or market-dormant phrasing that
 *      names storage or preservation without inventing a fresh harvest.
 *   3. Climate windows (`CLIMATE_WIN` per archetype) → source `frontier` when
 *      outside any curated calendar, or when the frontier has no `FRONTIER_CAL`
 *      entry at all. Region-level produce timing keyed by the market archetype.
 *      No farm names are invented at this tier.
 *   4. Regional archetypes (`ARCHETYPES` + `ARCH_RULES`) → source `archetype`.
 *      Purely regional seasonality lines (Winter/Spring/Summer/Fall and per-month
 *      peaks). Used when no frontier detail exists for the market or when the
 *      market has no town name to anchor a frontier line.
 *   5. Shoulder and year-round inputs (`month === -1`) → the engine treats empty
 *      string, null, undefined, and any unrecognized token as year-round. Year-round
 *      never throws; it composes Spring plus Summer archetype text or the first
 *      curated item as a stable placeholder.
 *
 * Public contract:
 *   `window.seasonFlavorFor(market, season)` → `{ text:string, source:string, frontier:string|null }`
 *   `source` is `curated` (market override or in-season frontier items)
 *           | `frontier` (frontier shoulder or climate-window shoulder)
 *           | `archetype` (regional line — the coach AI fallback covers event-anchored ideas there)
 *   `frontier` is the resolved frontier key or null when no detail exists.
 *   `window.__seasonFlavorSource` mirrors the last source for debug overlay use.
 *
 * Accepted season inputs:
 *   - 12 full month names (January through December) → exact month index 0-11
 *   - 4 season names (Winter/Spring/Summer/Fall) → representative month 0/3/6/9
 *   - 10 holiday labels (New Year, Valentine's Day, Easter, Memorial Day, Fourth of July,
 *     Labor Day, Halloween, Thanksgiving, Christmas, Holiday season) → mapped month
 *   - empty string / null / undefined → year-round sentinel `month === -1`
 *   Any other string degrades to year-round sentinel, never throws.
 */
(function(){
  'use strict';

  /**
   * Ordered month names used for exact string matching in `resolveSeason`.
   * What: canonical Gregorian month vocabulary for the public season API.
   * Why: month strings are the most precise input tier — they bypass season and
   *      holiday indirection and map directly to harvest windows.
   * Derives from: static calendar vocabulary; not data-driven, but its indices
   *   (0 = January … 11 = December) are the keys used inside `FRONTIER_CAL`
   *   items, `CLIMATE_WIN` windows, `ARCHETYPES.peaks`, and the canonical
   *   `retailer-frontier-pairs.json` monthly_ingredients keys (YYYY-MM).
   * Degrades: not applicable — this is a fixed vocabulary table.
   * @type {string[]}
   */
  var MONTHS = ['January','February','March','April','May','June','July','August','September','October','November','December'];

  /**
   * Month index → season bucket lookup.
   * What: maps each month (0-11) to one of four season indices 0=Winter 1=Summer 2=Spring 3=Fall.
   *   Encoding: [0,0,2,2,2,1,1,1,3,3,3,0] means Jan→Winter, Feb→Winter, Mar→Spring,
   *   Apr→Spring, May→Spring, Jun→Summer, Jul→Summer, Aug→Summer, Sep→Fall,
   *   Oct→Fall, Nov→Fall, Dec→Winter.
   * Why: archetype fallback text is stored per season (Winter/Spring/Summer/Fall),
   *   so a month that lacks a per-month peak still resolves to a season line.
   * Derives from: conventional northern-hemisphere seasonality used in
   *   `ARCHETYPES.seasons` — index 0 is Winter, 1 is Summer, 2 is Spring, 3 is Fall.
   *   Note the non-alphabetic order preserves the legacy `SEASON_NAMES` order.
   * Degrades: every month has a bucket, so lookup never yields undefined.
   * @type {number[]}
   */
  var SEASON_OF = [0,0,2,2,2,1,1,1,3,3,3,0]; // Winter Spring Summer Fall per month idx

  /**
   * Season name vocabulary ordered to match `SEASON_OF` indices.
   * What: Winter=0 Summer=1 Spring=2 Fall=3 in this file's internal ordering.
   * Why: `resolveSeason` accepts season names as input and must map them to a
   *   representative month; `archetypeLine` indexes `ARCHETYPES.seasons` by the
   *   same indices via `SEASON_OF[month]`.
   * Derives from: static vocabulary shared with the place data model.
   * Degrades: unknown season strings fall through to year-round sentinel.
   * @type {string[]}
   */
  var SEASON_NAMES = ['Winter','Spring','Summer','Fall'];

  /**
   * Holiday label → representative month index.
   * What: maps 10 holiday and seasonal labels to the month that best represents
   *   their produce moment. For example Christmas → 11 (December), Halloween → 9 (October).
   * Why: holidays are event-anchored inputs that lack a direct month name but
   *   still need a harvest window. Mapping them to a month lets the same
   *   frontier calendar lookup run for holidays as for any other input.
   * Derives from: retail and cultural calendar alignment; kept in sync with
   *   `retailer-frontier-pairs.json` seasonal_moments months arrays (for example
   *   Thanksgiving moments carry months [10 11] and this map resolves
   *   Thanksgiving → 10 for the primary lookup).
   * Degrades: a label not in this map proceeds to year-round sentinel.
   * @type {Object<string,number>}
   */
  var HOLIDAY_MONTH = {'New Year':0,'Valentine\u2019s Day':1,'Easter':3,'Memorial Day':4,'Fourth of July':6,'Labor Day':8,'Halloween':9,'Thanksgiving':10,'Christmas':11,'Holiday season':11};

  /**
   * Resolve any caller-supplied season token to a normalized month and label.
   *
   * What: normalizes the wide input surface (months, seasons, holidays, empty,
   *   unknown) into a single `{ month, label }` shape. `month` is 0-11 for a
   *   precise month or -1 as the year-round sentinel. `label` is the display
   *   string that prefixes the rendered line (for example "September" or
   *   "Holiday season" or "Year-round").
   *
   * Why: downstream lookups (`frontierMonthItems`, `archetypeLine`) branch on
   *   `month === -1` to choose year-round composition. Centralizing parsing
   *   here keeps those branches trivial and guarantees every path returns a
   *   usable label.
   *
   * How it derives from canonical data:
   *   Month names align with the YYYY-MM keys in `retailer-frontier-pairs.json`
   *   monthly_ingredients; holiday months align with that file's seasonal_moments
   *   months arrays. Keeping this mapping stable ensures the market×season
   *   matrix stays coherent across data and display.
   *
   * How it degrades:
   *   - null/undefined/empty/whitespace-only → `{month:-1, label:'Year-round'}`
   *   - Exact month name match → that month index
   *   - Season name match → representative month [0,3,6,9][seasonIndex]
   *     (Winter→0 January, Spring→3 April, Summer→6 July, Fall→9 October)
   *   - Holiday label match → mapped month from `HOLIDAY_MONTH`
   *   - Anything else (typo, unknown token) → year-round sentinel; never throws.
   *
   * @param {unknown} season - caller input; any type is accepted and coerced
   * @returns {{month:number,label:string}} month -1 means year-round
   */
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

  /**
   * Curated frontier harvest calendars — researched month windows per frontier.
   *
   * What: each key is a frontier identifier (the `market` field of a frontier
   *   sister in `retailer-frontier-pairs.json` and the key of
   *   `featuredFrontierDetail` in `data-core.js`). Each value has:
   *   - `items`: array of `{m:number[], t:string}` where `m` lists month indices
   *     (0=January … 11=December) when `t` is in season there, and `t` is the
   *     display name for that produce or market offering.
   *   - `off`: shoulder-season line shown when the requested month has no
   *     in-season items in `items`. Describes stored harvest or dormant-market
   *     state without inventing a fresh harvest.
   *   - `market`: display name for the farmers market or stand that anchors the
   *     line in copy.
   *
   * Why: curated calendars are the highest-fidelity tier. They let the engine
   *   name specific produce that is actually in season at that frontier's
   *   market, rather than falling back to region-level phrasing.
   *
   * How it derives from canonical data:
   *   Mirrors `featuredFrontierDetail[*].seasons` text in `data-core.js`, which
   *   itself is kept in sync with the generated
   *   `data/localization/market-featured-frontiers.json` via
   *   `scripts/build-frontier-mapping.py --check`. The month index lists here
   *   are the structured form of those season strings. The US-OH-LEBANON entry
   *   is additionally data-driven from `retailer-frontier-pairs.json` where the
   *   September pawpaws ingredient was added in 2026-09 as the north-star
   *   campaign month for the Ohio orchard belt.
   *   Typed via `frontier-contracts.js` as `FrontierCalendarEntry`.
   *
   * How it degrades:
   *   - If the requested month appears in any `items[].m`, those `t` values are
   *     returned as in-season hits (source becomes `curated`).
   *   - If the month appears in no window, `off` is returned as the shoulder
   *     line (source becomes `frontier`). Stored or preserved phrasing is used
   *     rather than fabricating freshness.
   *   - Year-round sentinel (`month === -1`) returns the first curated item as
   *     a stable placeholder or `off` when no items exist.
   *   - Frontiers absent from this map skip to `CLIMATE_WIN` / `ARCHETYPES`.
   *
   * Client language note: values contain display strings shown to shoppers and
   *   to the Digital Asset Library export path; they stay plain text and are
   *   escaped at render time by the caller when needed.
   *
   * @type {Record<string, import('./frontier-contracts.js').FrontierCalendarEntry>}
   */
  var FRONTIER_CAL = {
    // US-CA-PESCADERO — San Mateo coast frontier sister for US-CA-PESCADERO and halo markets.
    // Canonical: featuredFrontierDetail['US-CA-PESCADERO'] in data-core.js declares
    //   seasons "Castroville artichokes Mar-Jun (peak April); Marin goat cheese Feb-Jun;
    //   strawberries May-Sep; Brussels sprouts Sep-Feb; olive oil November press" and
    //   farmersMarket "Half Moon Bay Farmers Market (Saturdays) + Harley Farms Goat Dairy".
    // Mirrors retailer-frontier-pairs.json monthly_ingredients for the Pescadero pair
    // (strawberries hold September as the campaign month; Brussels sprouts hold December).
    'US-CA-PESCADERO': {
      items:[{m:[2,3,4,5],t:'Castroville artichokes'},{m:[1,2,3,4,5],t:'Marin goat cheese'},{m:[4,5,6,7,8],t:'strawberries'},{m:[8,9,10,11,0,1],t:'Brussels sprouts'},{m:[10],t:'fall olive-oil press'}],
      off:'winter farm stands + stored sprouts',
      market:'Half Moon Bay Farmers Market (Saturdays) + Harley Farms farm stand'},
    // US-CA-JULIAN — Cuyamaca mountain apple country frontier.
    // Canonical: featuredFrontierDetail['US-CA-JULIAN'] seasons "Apple season late Aug-Oct (peak September)".
    'US-CA-JULIAN': {
      items:[{m:[7,8,9],t:'Julian apples (peak September)'},{m:[8,9],t:'pear cider'}],
      off:'gold-rush main street stands + holiday apple pies (orchards dormant)',
      market:'Julian farm stands + mountain orchards'},
    // US-CA-CASTROVILLE — Artichoke Capital stand-alone frontier.
    // Canonical: featuredFrontierDetail['US-CA-CASTROVILLE'] seasons match Pescadero artichoke window.
    'US-CA-CASTROVILLE': {
      items:[{m:[2,3,4,5],t:'Castroville artichokes (peak April)'},{m:[4,5,6,7,8],t:'strawberries'},{m:[8,9,10,11,0,1],t:'Brussels sprouts'}],
      off:'winter artichoke stands + stored sprouts',
      market:'Castroville artichoke stands + Monterey Bay farmers markets'},
    // US-WA-NEAHBAY — Northwestern tip of Olympic Peninsula Makah frontier.
    // Canonical: featuredFrontierDetail['US-WA-NEAHBAY'] seasons "Makah salmon May-Sep; huckleberry August".
    'US-WA-NEAHBAY': {
      items:[{m:[4,5,6,7,8],t:'Makah salmon'},{m:[6,7],t:'huckleberry (peak August)'},{m:[2,3,4,5],t:'halibut (peak Apr-May)'}],
      off:'winter harbor + preserved salmon (fishing dormant)',
      market:'Washburn\u2019s General Store porch stands + Makah Days'},
    // US-SE-SANDERSVILLE — Washington County Georgia kaolin-belt farm frontier.
    // Canonical: featuredFrontierDetail['US-SE-SANDERSVILLE'] seasons list Georgia pecans/peaches/sweet potatoes/muscadines.
    'US-SE-SANDERSVILLE': {
      items:[{m:[3,4],t:'strawberries'},{m:[4,5,6,7],t:'Georgia peaches (peak July)'},{m:[7,8],t:'muscadine grapes'},{m:[8,9,10],t:'sweet potatoes (peak October)'},{m:[9,10,11],t:'Georgia pecans (peak November)'}],
      off:'stored pecans + holiday baking season',
      market:'Sandersville downtown farmers market + Washington County stands'},
    // US-SW-TIMBERON — Sacramento Mountains high-country frontier.
    // Canonical: featuredFrontierDetail['US-SW-TIMBERON'] seasons "Piñon harvest in fall (months unverified)".
    // Note: piñon window carries an explicit unconfirmed-months flag; `off` notes Cloudcroft Mercantile halo as research dispatch.
    'US-SW-TIMBERON': {
      items:[{m:[8,9,10],t:'pi\u00f1on harvest (exact months unconfirmed \u2014 research dispatch)'}],
      off:'high-country stands dormant \u2014 Cloudcroft Mercantile halo (research dispatch)',
      market:'Timberon General Store + Cloudcroft Mercantile halo'},
    // US-UT-OAKLEY — Wasatch Back ranch country frontier for Park City markets.
    // Canonical: featuredFrontierDetail['US-UT-OAKLEY'] seasons "tart cherries Jul; peaches Aug-Sep; apples Sep-Oct; sweet corn Jul-Sep; tomatoes Jul-Sep".
    // Items include market-dated entry (Jun-Sep 2023 Oakley Farmers Market) and year-round ranch proteins.
    'US-UT-OAKLEY': {
      items:[{m:[5,6,7,8],t:'Oakley Farmers Market at Rodeo Grounds (Jun-Sep, 2023 season)'},{m:[],t:'Splendor Valley Farms produce (exact months unconfirmed \u2014 research dispatch)'},{m:[0,1,2,3,4,5,6,7,8,9,10,11],t:'Oakley grass-fed beef + ranch butter, year-round'}],
      off:'ranch beef + butter, year-round (market dormant)',
      market:'Oakley Farmers Market at Oakley Rodeo Grounds'},
    // US-OH-LEBANON — Warren County orchard belt featured frontier (Cincinnati and Dayton resolve here).
    // Data-driven from data/localization/retailer-frontier-pairs.json (US-OH-LEBANON, 2026-09: pawpaws).
    // That file's monthly_ingredients carry maple syrup Feb, strawberries May, sweet corn Jul,
    // pawpaws Sep, black walnuts Dec; monthly_ingredient_notes confirm pawpaws peak September.
    // Typed via frontier-contracts.js (FrontierCalendarEntry); keep in sync with emit_frontier_pairs check.
    'US-OH-LEBANON': {
      items:[{m:[1,2],t:'maple syrup (peak March)'},{m:[4,5],t:'strawberries'},{m:[6],t:'sweet corn (peak July)'},{m:[8],t:'pawpaws (peak September)'},{m:[11],t:'black walnuts'}],
      off:'orchard belt dormant — stored walnuts + holiday baking',
      market:'Findlay Market + Warren County orchard stands (Lebanon)'}
  };

  /**
   * Look up the featured frontier detail for a market via the shared data-core helper.
   *
   * What: thin wrapper around global `featuredFrontierFor(market)` defined in
   *   `data-core.js`. Returns the frontier detail object
   *   `{ frontier, place, items, seasons, farmersMarket, farms, coops, text }`
   *   or null when the market has no featured frontier.
   *
   * Why: this file must not hard-code the 70+ market→frontier mappings inline;
   *   data-core.js is the single source for that map and is the file generated
   *   checked against `data/localization/market-featured-frontiers.json` by
   *   `scripts/build-frontier-mapping.py --check`. Delegating keeps the two
   *   files in sync.
   *
   * How it derives from canonical data:
   *   `featuredFrontierFor` reads `marketFeaturedFrontier` and
   *   `featuredFrontierDetail` in data-core.js, which are the offline
   *   publication of the frontier sister assignments in `retailer-frontier-pairs.json`.
   *
   * How it degrades:
   *   - When `featuredFrontierFor` is not yet loaded or throws, returns null.
   *   - When the market key has no frontier assignment, returns null.
   *   - Callers treat null as "no frontier" and proceed to archetype fallback.
   *
   * @param {string} market - market key such as US-MW-PARKCITY-84098
   * @returns {{frontier:string,place:string,items:string[],seasons:string,farmersMarket:string}|null}
   */
  function frontierDetail(market){
    try{
      if(typeof featuredFrontierFor === 'function') return featuredFrontierFor(market);
    }catch(e){}
    return null;
  }

  /**
   * Climate month-windows for frontiers that lack a researched calendar.
   *
   * What: region-level produce timing tables keyed by market archetype
   *   (wasatch, rockies, southwest, southplains, southeast, tropical,
   *   newengland, heartland, north, pacific, desert, alaska). Each archetype
   *   holds an array of `{m:number[], t:string}` windows where `m` lists
   *   month indices when `t` (a produce or market phrase) is in its window.
   *
   * Why: many frontiers have no per-frontier researched calendar in
   *   `FRONTIER_CAL`. Rather than show a blank or invent a farm name, the
   *   engine shows a region-supplied window derived from the *market* archetype
   *   of the calling market. This keeps the line grounded in regional timing
   *   while staying transparent about its granularity.
   *
   * How it derives from canonical data:
   *   These are editorial summaries of extension-service crop calendars and the
   *   regional archetype seasons in `ARCHETYPES`. They do not name farms; they
   *   name produce categories whose timing is broadly consistent within the
   *   archetype. When a frontier later gains a researched entry in
   *   `FRONTIER_CAL`, that entry takes priority and these windows stop being
   *   consulted for that frontier key.
   *
   * How it degrades:
   *   - Looked up by the market archetype of the calling market (via `archetypeFor`).
   *   - If the archetype key is unknown, `heartland` is used as the default.
   *   - If the requested month falls in a window, that window's `t` values are
   *     returned as hits (up to two joined with " + ").
   *   - If the month falls in no window, the caller falls through to the
   *     frontier's own `det.items[0]` or the string "seasonal produce" as a
   *     year-round placeholder, marked `shoulder:true` so the outer renderer
   *     knows to attribute via `frontier` rather than `curated`.
   *   - Year-round sentinel (`month === -1`) returns the frontier's first item
   *     or "seasonal produce" directly without consulting windows.
   *
   * @type {Object<string, Array<{m:number[],t:string}>>}
   */
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

  /**
   * Resolve month items for a frontier — curated calendar first, climate windows second.
   *
   * What: given a frontier detail, a target month index, and the market's
   *   archetype, returns `{ items:string[], shoulder:boolean, cal:boolean }`.
   *   `items` is the display list (one or two strings), `shoulder` is true
   *   when the returned text is a dormant or storage line rather than an
   *   in-season hit, and `cal` is true when the result came from a researched
   *   `FRONTIER_CAL` entry (used by the caller to choose source attribution).
   *
   * Why: centralizes the two-tier lookup so the main renderer
   *   (`seasonFlavorFor`) stays a straight composition of this result with
   *   archetype and curated-base phrasing.
   *
   * How it derives from canonical data:
   *   - Tier 1 checks `FRONTIER_CAL[det.frontier]`. When present its `items`
   *     windows are matched against the target month. Hits return those
   *     curated names. A miss returns that entry's `off` shoulder line.
   *   - Tier 2 checks `CLIMATE_WIN[arch]`. Windows there are matched the same
   *     way. A miss returns `det.items[0]` from data-core.js (the frontier's
   *     lead produce name) or the fallback string "seasonal produce".
   *
   * How it degrades:
   *   - Curated hit (`cal:true, shoulder:false`) → source `curated` in caller.
   *   - Curated miss (`cal:true, shoulder:true`) → source `frontier` in caller.
   *   - Climate hit (`cal:false, shoulder:false`) → source picked by caller
   *     (usually `frontier` unless a curated market base applies).
   *   - Climate miss (`cal:false, shoulder:true`) → placeholder item with
   *     shoulder true, so caller renders an archetype-anchored line with the
   *     frontier town parenthetical rather than an empty string.
   *   - Year-round sentinel (`month === -1`) → first curated item or `off` for
   *     tier 1; frontier lead item or "seasonal produce" for tier 2; always
   *     shoulder false so it reads as a stable placeholder not a dormant note.
   *   - Never returns an empty `items` array when a detail object exists; the
   *     fallback placeholder guarantees a line.
   *
   * @param {{frontier:string,items:string[]}|null} det - frontier detail or null
   * @param {number} month - 0-11 month index or -1 for year-round
   * @param {string} arch - archetype key from `archetypeFor` (for example "wasatch")
   * @returns {{items:string[],shoulder:boolean,cal:boolean}}
   */
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

  /**
   * Extract a short town name from a frontier place string.
   *
   * What: splits `det.place` on the em dash separator " — " and returns the
   *   first segment (for example "Pescadero, California 94060 — San Mateo Coast"
   *   → "Pescadero, California 94060").
   *
   * Why: the main renderer appends "Featured Frontier: <town>" to lines where
   *   no curated market base exists but a frontier is available. Using the
   *   short town keeps that suffix readable and avoids repeating the full
   *   place description already present in other UI.
   *
   * How it derives from canonical data:
   *   `det.place` comes from `featuredFrontierDetail[*].place` in data-core.js,
   *   which is populated from the `place` field of each frontier sister in
   *   `retailer-frontier-pairs.json` and from the curated place strings that
   *   accompany each frontier in that file's `places` exposition.
   *
   * How it degrades:
   *   - Null or missing `det` or `det.place` → returns null.
   *   - Any exception during string coercion → returns null.
   *   - Caller treats null as "no town to display" and falls through to the
   *     archetype-only branch rather than throwing.
   *
   * @param {{place:string}|null} det - frontier detail or null
   * @returns {string|null} short town or null when unavailable
   */
  function frontierTownShort(det){
    try{
      if(det && det.place) return String(det.place).split(' \u2014 ')[0];
    }catch(e){}
    return null;
  }

  /**
   * Regional archetype seasonality tables — region-level lines without farm names.
   *
   * What: each key is an archetype label (wasatch, rockies, southwest, southplains,
   *   southeast, tropical, newengland, heartland, north, pacific, desert, alaska).
   *   Each value has:
   *   - `seasons`: array of 4 strings indexed [Winter, Summer, Spring, Fall] in this
   *     file's ordering (note the non-standard order inherited from `SEASON_NAMES`
   *     / `SEASON_OF`). Used when the requested month has no per-month `peaks`.
   *   - `peaks`: object `monthIndex → line` for months where a single phrase
   *     should override the broader season line.
   *
   * Why: archetypes are the last-resort tier that guarantees a line for any
   *   market × any season even when no frontier detail exists. They describe
   *   regional seasonality at a granularity that stays accurate without needing
   *   per-farm verification — no farm names appear here, only produce categories
   *   and cultural moments whose timing is broadly consistent across the region.
   *
   * How it derives from canonical data:
   *   Editorial synthesis of extension-service calendars and the regional flavor
   *   of curated frontier seasons. Archetype keys are assigned via `ARCH_RULES`
   *   from market key prefixes, which are themselves derived from the market
   *   geography in `retailer-frontier-pairs.json` and `data-core.js` places.
   *   Peak months align with historically notable harvest moments within each
   *   region (for example wasatch peak 6 is peach peak + sweet corn).
   *
   * How it degrades:
   *   - `archetypeLine` checks `peaks[month]` first; when a direct peak exists
   *     that phrase overrides the season bucket.
   *   - Otherwise it indexes `seasons[SEASON_OF[month]]` to pick the season line.
   *   - Year-round sentinel (`month === -1`) composes `seasons[Spring] + " — " + seasons[Summer]`
   *     as a stable warmer-month placeholder.
   *   - Unknown archetype key degrades to `heartland` entry.
   *
   * @type {Object<string, {seasons:string[], peaks:Object<number,string>}>}
   */
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

  /**
   * Market prefix → archetype routing table.
   *
   * What: ordered array of `[marketPrefix, archetypeKey]` pairs. The first
   *   prefix that matches the start of the market key wins. Archetype values
   *   are keys into `ARCHETYPES` and `CLIMATE_WIN`.
   *
   * Why: markets carry geography in their key prefix (for example US-CA-*
   *   is coastal California, US-MW-* is Midwest). Routing by prefix assigns
   *   each market the regional seasonality that best matches its location
   *   without needing a separate lookup table per market. Specific prefixes
   *   are listed before broad ones so they take priority.
   *
   * How it derives from canonical data:
   *   Prefixes mirror the metro market keys in `retailer-frontier-pairs.json`
   *   and `data-core.js` places. For example US-UT-* markets route to wasatch,
   *   US-SE-* to southeast, US-NE-* to newengland, and so on. The table is
   *   the editorial translation of USDA extension zones and regional produce
   *   calendars into the market namespace.
   *
   * How it degrades:
   *   - Iterates top to bottom; first `market.indexOf(prefix) === 0` match wins.
   *   - Broad catch-alls near the end (US-W-, US-CA-, US-MW-) ensure most
   *     markets match something.
   *   - No prefix matching → returns `heartland` as the default archetype,
   *     which is the most broadly applicable seasonal vocabulary.
   *
   * @type {Array<[string,string]>}
   */
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

  /**
   * Map a market key to its regional archetype.
   *
   * What: scans `ARCH_RULES` in order and returns the archetype whose prefix
   *   first matches the market string.
   *
   * Why: determines which `CLIMATE_WIN` window set and which `ARCHETYPES`
   *   season lines apply for the calling market. This is the sole branching
   *   point between all regional voices.
   *
   * How it degrades:
   *   - Empty or missing market → no prefix matches → `heartland`.
   *   - Unknown market not covered by any prefix → `heartland`.
   *   - Always returns a valid archetype key; never returns null or undefined.
   *
   * @param {unknown} market - market key such as US-MW-PARKCITY-84098
   * @returns {string} archetype key present in ARCHETYPES and CLIMATE_WIN
   */
  function archetypeFor(market){
    var m = String(market || '');
    for(var i = 0; i < ARCH_RULES.length; i++){
      if(m.indexOf(ARCH_RULES[i][0]) === 0) return ARCH_RULES[i][1];
    }
    return 'heartland';
  }

  /**
   * Resolve the display line for an archetype and month.
   *
   * What: given an archetype key and a month index, returns the archetype
   *   display phrase. Per-month peaks override the broader season bucket.
   *
   * Why: archetype phrasing is the guaranteed fallback line. Every market ×
   *   month that reaches this function gets a non-empty, location-appropriate
   *   phrase even when no frontier data is available.
   *
   * How it derives from canonical data:
   *   Reads `ARCHETYPES[arch].peaks` for an exact month override, otherwise
   *   indexes `ARCHETYPES[arch].seasons` via `SEASON_OF[month]`. The season
   *   and peak phrases are the region-level editorial layer described above.
   *
   * How it degrades:
   *   - Year-round sentinel (`month === -1`) → spring + summer seasons joined
   *     with an em dash as a stable warm-month placeholder.
   *   - Per-month peak exists (`ARCHETYPES[arch].peaks[month]`) → that peak line.
   *   - Otherwise → `ARCHETYPES[arch].seasons[SEASON_OF[month]]` season line.
   *   - Unknown archetype key → `ARCHETYPES.heartland` fallback entry.
   *   - Never returns empty; every month resolves to at least the season bucket.
   *
   * @param {string} arch - archetype key from archetypeFor
   * @param {number} month - 0-11 month index or -1 for year-round
   * @returns {string} archetype display phrase
   */
  function archetypeLine(arch, month){
    var a = ARCHETYPES[arch] || ARCHETYPES.heartland;
    if(month === -1) return a.seasons[1] + ' \u2014 ' + a.seasons[2];
    if(a.peaks[month]) return a.peaks[month];
    return a.seasons[SEASON_OF[month]];
  }

  /**
   * Curated market base lines — voice-matched flavor leads for top markets.
   *
   * What: exact display fragments for a handful of markets that have a
   *   distinctive frontier pairing deserving a persistent, voice-matched lead.
   *   These fragments are appended verbatim to the rendered line when the
   *   calling market matches a key here.
   *
   * Why: some markets have frontier pairings that warrant copy beyond a produce
   *   name — a market name, preparation cue, and landscape anchor that reads
   *   as a place, not just an ingredient. Keeping those fragments here lets the
   *   engine name them consistently without rebuilding them from frontier detail
   *   fields on each call.
   *
   * How it derives from canonical data:
   *   Mirrors the `flavorMap` voice object in `generate.js` for the same market
   *   keys. That map's entries are editorial leads drawn from
   *   `retailer-frontier-pairs.json` frontier place names and
   *   `featuredFrontierDetail` farmersMarket fields, refined for the
   *   "In season here" surface. US-MW-PARKCITY-84098 names Jensen Farms and
   *   Copper Moose at Park City Farmers Market; US-UT-KAMASVALLEY names Oakley
   *   ranch proteins at the Rodeo Grounds; US-SW-LASCRUCES names the Hatch
   *   bushel roast; and so on.
   *
   * How it degrades:
   *   - A market present in this map gets its lead appended to every in-season
   *     rendering for that market. On a shoulder month the source still
   *     downgrades to `frontier` while preserving the curated base phrasing.
   *   - Year-round sentinel (`month === -1`) composes `place + ": " + base + " — " + archetypeLine`
   *     with source `curated`, keeping the curated lead visible even outside a
   *     specific month window.
   *   - Markets absent from this map skip this tier and use the frontier-town
   *     or archetype branches instead.
   *
   * @type {Object<string,string>}
   */
  var MARKET_BASE = {
    'US-MW-PARKCITY-84098': 'Wasatch Back \u2014 Jensen Farms peaches + Copper Moose rhubarb compote at Park City Farmers Market',
    'US-UT-KAMASVALLEY': 'Kamas Valley \u2014 Oakley grass-fed beef + Ballerina Farm butter at Oakley Rodeo Grounds market',
    'US-SW-LASCRUCES': 'Hatch green chile, roasted by the bushel \u2014 Organ Mountains bench',
    'US-CA-PESCADERO': 'Pescadero farm stands \u2014 Castroville artichokes + Marin goat cheese',
    'US-WA-NEAHBAY': 'Neah Bay harbor \u2014 Makah salmon + huckleberry at Washburn\u2019s General Store'
  };

  /**
   * Resolve a short place display name for a market.
   *
   * What: looks up the market key in the global `places` array (published by
   *   `data-core.js` as `window.places`) and returns the first segment of its
   *   `place` field split on " — ". For example "Park City, Utah 84098 — Kimball
   *   Junction" → "Park City, Utah 84098".
   *
   * Why: every rendered line is prefixed with `Place:` so shoppers can see
   *   which market the seasonal note belongs to. Using the short segment keeps
   *   the prefix compact and avoids repeating the full place description.
   *
   * How it derives from canonical data:
   *   `places` entries are the inline publication of metro locations from
   *   `retailer-frontier-pairs.json` (metro_location name) and the curated
   *   `places[]` array in data-core.js. Both name the town and metro area that
   *   pair with each frontier sister.
   *
   * How it degrades:
   *   - `places` global not yet loaded or not an array → returns the raw market
   *     key as the display name.
   *   - Market key not found in `places` → returns the raw market key.
   *   - Any exception → returns the raw market key.
   *   - Never returns empty or null; the line always has a place prefix.
   *
   * @param {string} market - market key
   * @returns {string} short place name or the market key itself
   */
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

  /**
   * Main engine entry — resolve market × season to a display line and source tag.
   *
   * What: `window.seasonFlavorFor(market, season)` is the sole public API of
   *   this module and the only function other scripts call. It always returns
   *   `{ text:string, source:string, frontier:string|null }` and never returns
   *   null or throws to the caller — the outermost try/catch catches any
   *   unexpected exception.
   *
   * Why: the UI needs a single call that never leaves a market without a line.
   *   The caller (for example `generate.js` `updateLocalFlavor`) can render
   *   `text` directly and inspect `source` to decide whether to also offer
   *   coach-AI event-anchored fallback suggestions.
   *
   * How it derives from canonical data:
   *   Composes four sources in priority order on each call:
   *   1. `resolveSeason(season)` → normalized `{month, label}` where month
   *      indices map to `retailer-frontier-pairs.json` monthly_ingredients YYYY-MM.
   *   2. `frontierDetail(mk)` → frontier detail via data-core.js
   *      `featuredFrontierFor`, which reflects the frontier sister assignments
   *      in `retailer-frontier-pairs.json`.
   *   3. `frontierMonthItems(det, month, arch)` → curated `FRONTIER_CAL`
   *      items or `CLIMATE_WIN` windows for that month.
   *   4. `archetypeLine(arch, month)` → regional fallback line when frontier
   *      data is unavailable or the month is a shoulder month.
   *   `placeName` and `frontierTownShort` supply the geographic anchors
   *   from the same frontier detail.
   *
   * How it degrades — branching ladder inside:
   *   - Branch A — curated market base + specific month (`MARKET_BASE[mk]` hit,
   *     `month !== -1`): `Place: Label brings <frontier items> — <curated base>.`
   *     source = `shoulder ? 'frontier' : 'curated'`. In-season items make it
   *     curated; shoulder items downgrade the tag to frontier while preserving
   *     the curated base phrasing.
   *   - Branch B — curated market base + year-round (`MARKET_BASE[mk]` hit,
   *     `month === -1`): `Place: <curated base> — <archetype line>.`
   *     source = `curated`. Keeps the curated lead visible outside a month window.
   *   - Branch C — frontier town with in-season hits (`town` exists,
   *     `fm.items.length` true, `!fm.shoulder`): `Place: Label brings <items> — Featured Frontier: <town>.`
   *     source = `fm.cal ? 'curated' : 'frontier'`. Researched calendars read
   *     as curated; climate-window hits read as frontier.
   *   - Branch D — frontier town shoulder (`town` exists, `fm.items.length`
   *     true, `fm.shoulder`): `Place: Label — <archetype line> — Featured Frontier: <town> (<item>).`
   *     source = `frontier`. Shows the shoulder item parenthetically alongside
   *     the archetype line so the line stays empty-free.
   *   - Branch E — no frontier or no items (`town` missing or `fm` empty):
   *     `Place: Label — <archetype line>.` source = `archetype`. Purely
   *     regional phrasing; no farm name is invented.
   *   - Outermost catch → `{text:'<market>: seasonal frontier flavor.', source:'archetype', frontier:null}`
   *     guarantees a non-throwing return even on catastrophic input.
   *   - In every branch `frontier` is set to `det.frontier` or null, and
   *     `window.__seasonFlavorSource` is mirrored for debug overlay inspection.
   *     Empty or unknown `market` defaults to `US-MW-PARKCITY-84098`.
   *     Empty or unknown `season` degrades via `resolveSeason` to year-round.
   *
   * Client note: returned `text` is plain text for insertion via textContent or
   *   the surrounding Digital Asset Library export serializer — callers that
   *   inject as HTML must escape separately (see `generate.js` escapeHtml).
   *
   * @param {unknown} market - market key; falsy defaults to US-MW-PARKCITY-84098
   * @param {unknown} season - season token; see accepted inputs in file header
   * @returns {{text:string,source:string,frontier:(string|null)}} display line, source tag, frontier key
   */
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

  // Publish the public surface on window — the only exports of this IIFE.
  // What: exposes `window.seasonFlavorFor` as the engine entry point and
  //   `window.__seasonFlavorSource` as a mirrored debug signal for the overlay
  //   and for tests that assert the source tag.
  // Why: this file is loaded as a plain <script> (offline-first, no bundler),
  //   so window is the module boundary. `try/catch` keeps non-browser eval
  //   (vitest direct eval of the slice) from throwing on missing window.
  // How it degrades: when window is absent the locals remain usable in tests;
  //   when window exists both names are assigned. Initial value of
  //   `__seasonFlavorSource` is null until the first engine call.
  try{
    window.seasonFlavorFor = seasonFlavorFor;
    window.__seasonFlavorSource = null;
  }catch(e){}
})();
