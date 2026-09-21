// Market languages — top 2 outside English per market (ACS 2022), auto-produced as EN + localized variants. Proven via Nova (unlimited budget) (Amazon Translate + Nova Micro)
/** @type {Object<string, MarketLang[]>} */
const marketLangsOffline = {
  "US-SW-EL PASO": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":62},{"lang_code":"de","lang_name":"German","translate_code":"de","pct_home":0.6}],
  "US-NE-BURLINGTON": [{"lang_code":"fr","lang_name":"French","translate_code":"fr","pct_home":3.2},{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":2.1}],
  "US-NE-BOS": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":9},{"lang_code":"pt","lang_name":"Portuguese","translate_code":"pt","pct_home":2.5}],
  "US-W-SF": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":12},{"lang_code":"zh","lang_name":"Chinese","translate_code":"zh","pct_home":6}],
  "US-W-SANJOSE": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":12},{"lang_code":"zh","lang_name":"Chinese","translate_code":"zh","pct_home":6}],
  "US-CA-CASTROVILLE": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":20},{"lang_code":"zh","lang_name":"Chinese","translate_code":"zh","pct_home":1}],
  "US-CA-PESCADERO": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":12},{"lang_code":"zh","lang_name":"Chinese","translate_code":"zh","pct_home":6}],
  "US-WA-NEAHBAY": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":8},{"lang_code":"zh","lang_name":"Chinese","translate_code":"zh","pct_home":1.5}],
  "US-MW-PARKCITY-84098": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":9},{"lang_code":"de","lang_name":"German","translate_code":"de","pct_home":0.6}],
  "US-SW-ALBQ": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":22.3},{"lang_code":"nv","lang_name":"Navajo","translate_code":"nv","pct_home":1.1,"machine_translate":false,"review":"community","review_note":"Community-authorized translation required — not machine-generated (language sovereignty)."}],
  "_default": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":8},{"lang_code":"fr","lang_name":"French","translate_code":"fr","pct_home":0.5}]
};
// RESTING-LOCALIZATION SEED — real translated copy for the default resting markets so the resting preview
// shows genuine localized text (not 3x English) before the live /localize is ever called on Create. Seed
// entries carry provider:"seed" and are treated by both localized renderers exactly like precomputed #124
// copy: real text, no "showing English source only" note. Live /localize on Create still overrides. Park
// City seeds es + de + pt (canonical top_languages in market-languages.json are es + pt; de retained as a
// resting-preview seed). pt is machine-translatable (Amazon Translate, provider amazon-translate) — its text
// is the real /localize pipeline output persisted to the localization-memory table
// (pk=MARKET#US-MW-PARKCITY-84098, sk=LANG#pt#MSG#dde08b787ca6bcee). NEVER seed community-review languages
// (nv/zip) — those stay human-only; pt is NOT one of them.
window.KODIAK_LOCALIZED_COPY = window.KODIAK_LOCALIZED_COPY || {};
if(!window.KODIAK_LOCALIZED_COPY["US-MW-PARKCITY-84098"]){
  window.KODIAK_LOCALIZED_COPY["US-MW-PARKCITY-84098"] = {
    "es": {text:"Mantente Salvaje — cereales integrales ricos en proteína para tu frontera Wasatch. Nutrición para la Frontera de Hoy", provider:"seed"},
    "de": {text:"Bleib wild — proteinreiche Vollkornprodukte für deine Wasatch-Frontier. Nahrung für die Frontier von heute", provider:"seed"},
    "pt": {text:"Mantenha-o Selvagem — grãos integrais repletos de proteínas para sua fronteira Wasatch. Nutrição para a Fronteira de Hoje", provider:"seed"}
  };
}
/** @param {string} code @returns {Array<{lang_code:string,lang_name:string,translate_code:string,pct_home:number,machine_translate?:boolean,review?:string,review_note?:string}>} */
function marketLangsFor(code){ return (marketLangsOffline[code] || marketLangsOffline._default || []).filter(Boolean); }
/** @returns {void} */
function renderLangChips(){
  // declutter — lang-chips removed from the app page (non-interactive, hardcoded markets).
  // kept as a safe no-op so fillSelects/change-listener/setTimeout/async-fetch callers never throw.
  const el=document.getElementById('lang-chips');
  if(el && el.parentNode) el.parentNode.removeChild(el);
}
document.addEventListener('change', /** @param {Event} e */ (e)=>{ const t = e.target instanceof Element ? e.target : null; if(t && t.id==='locality') renderLangChips(); });
// also fetch full 75-market file when online to upgrade offline seed — try multiple paths for local http.server 8099 vs S3
(async()=>{ for(const url of ['data/localization/market-languages.json','../../data/localization/market-languages.json','./data/localization/market-languages.json']){ try{ const r=await fetch(url); if(r.ok){ const d=await r.json(); if(d.markets){ d.markets.forEach(/** @param {{market?: unknown, top_languages?: Array<{translate_code?: string, lang_code: string, lang_name?: string, pct_home?: number, pct?: number}>}} m */ (m)=>{ if(m.top_languages) marketLangsOffline[String(m.market)]=m.top_languages.map(t=>/** @type {MarketLang} */ ({...t, translate_code: t.translate_code||t.lang_code, pct_home: (t.pct_home!=null?t.pct_home:t.pct)})); }); console.log('[langs] loaded',d.markets.length,'from',url); renderLangChips(); break; } } }catch(e){} }})();
// Inline data — so this page is truly offline (no fetch to a server). Keep a small seed of hundreds-scale places and recipes here; full tables live at ../../data/
const places = [
  {market:"US-MW-PARKCITY-84098", place:"Park City, Utah 84098", retailer:"Target (Kimball Junction), Walmart (Kimball Junction), Smith's Food & Drug (Park City)", zip:"84098", audience:"Mountain families, Wasatch trail households, resort staff — Aaron", message:"Keep It Wild — September aspen gold and protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Farmers Market at Park City Mountain Resort Wed 11-5 — Jensen Farms September peaches, aspen gold up Mirror Lake Highway, elk bugling at dawn, first Uinta snow dusting"},
    {market:"US-UT-KAMASVALLEY", place:"Kamas Valley — Peoa / Oakley, UT 84036 (Wasatch Back rural)", retailer:"Oakley Farmers Market (Rodeo Grounds) + Kamas Valley Market — no commercial retail", zip:"84036", audience:"Peoa ranch families on acreage, Oakley rodeo neighbors, Kamas backyard growers — ranch assembly", message:"September ranch country — aspen gold, bugling elk, low clear Weber. Kodiak Cakes savory waffle + Oakley grass-fed sausage — Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Oakley in September — quaking-aspen gold, Gambel oak copper, straw valley floor with crimson sumac, elk bugling at dawn off Weber Canyon Road, low clear Weber River, first frost at Stevens Grove trailhead, Kodiak Cakes on a tailgate with mountain greens"},
  {market:"US-MW-WASATCH", place:"Park City, Wasatch Mountains", retailer:"Target, Walmart", zip:"84060", audience:"Outdoor families, ski and hike households — Madison", message:"Keep It Wild — protein-packed whole grains for today's frontier", peppers:"—", cheeses:"—", cue:"Wasatch alpenglow, pine, boulder, snow at dawn"},
  {market:"US-SW-LASCRUCES", place:"Las Cruces + Alamogordo, New Mexico", retailer:"Target, Walmart, Albertsons", zip:"88001", audience:"Green chile families, Hatch roast households 28-45 — Eli", message:"Green chile meets grizzly — protein for your Las Cruces frontier", peppers:"—", cheeses:"—", cue:"Roasted Hatch green chile in flapjacks, Organ Mountains bench, trail bench"},
  {market:"US-SW-ALBQ", place:"Albuquerque, New Mexico", retailer:"Target, Walmart, Smith's", zip:"87101", audience:"High desert families, adobe morning — Sarah", message:"Desert dawn flapjacks — 14 grams for your high desert day", peppers:"—", cheeses:"—", cue:"Red chile and piñon, enamel mug on portal"},
  {market:"US-SC-AUSTIN", place:"Austin, Texas", retailer:"Target, Whole Foods, H-E-B", zip:"78701", audience:"Breakfast taco families, keep-it-weird hosts — Emily", message:"Breakfast tacos meet flapjacks — whole grains that keep up", peppers:"—", cheeses:"—", cue:"Salsa over flapjacks, food truck corner"},
  {market:"US-SE-FL", place:"Miami + Orlando, Florida", retailer:"Publix, Target", zip:"33101", audience:"Cuban and Puerto Rican families, porch breakfasts — Elizabeth", message:"Family frontier — protein for your Florida morning", peppers:"—", cheeses:"—", cue:"Guava and café con leche beside stack"},
  {market:"US-SE-COAST", place:"Savannah + Charleston, Coastal Southeast", retailer:"Publix, Harris Teeter", zip:"29401", audience:"Porch families, Gullah seasonality — Nina", message:"Southern porch stack — protein-packed whole grains for your family", peppers:"—", cheeses:"—", cue:"Peach and pecan"},
  {market:"US-SE-ATL", place:"Atlanta, Georgia", retailer:"Publix, Target", zip:"30301", audience:"Urban families, Sunday brunch — Brett", message:"Georgia pecan frontier — 14 grams to start your day", peppers:"—", cheeses:"—", cue:"Pecan praline drizzle"},
  {market:"US-MW-CHI", place:"Chicago, Illinois", retailer:"Target, Jewel-Osco, Meijer", zip:"60601", audience:"City families, lake effect winters — Arnoldo", message:"Fuel your city frontier — 14 grams, 100 percent whole grains", peppers:"—", cheeses:"—", cue:"Maple oatmeal cup on the L"},
  {market:"US-MW-TC", place:"Twin Cities, Minnesota", retailer:"Target (home), Cub Foods", zip:"55401", audience:"Midwest hearty families — Sam", message:"Stock the frontier — every morning, hearty and whole grain", peppers:"—", cheeses:"—", cue:"Maple, wild rice, snow boots"},
  {market:"US-MW-DEN", place:"Denver, Colorado", retailer:"Target, King Soopers, Whole Foods", zip:"80202", audience:"Mountain families, trailheads — Amber", message:"Cast-iron frontier — protein for your Colorado morning", peppers:"—", cheeses:"—", cue:"Cast iron at trailhead"},
  {market:"US-W-SEA", place:"Seattle, Washington", retailer:"Costco (home — Seattle/SODO/Issaquah warehouses), Target, Amazon Subscribe & Save", zip:"98101", audience:"Seattle Costco bulk shoppers — Cory", message:"Evergreen frontier — protein-packed whole grains for gray mornings — bulk Costco + urban frontier awareness", peppers:"—", cheeses:"—", cue:"Coffee beside Kodiak Cakes flapjacks, evergreen, rain-morning griddle, bulk Costco Family Size — and Neah Bay frontier repres"},
  {market:"US-W-PDX", place:"Portland, Oregon", retailer:"Target, Fred Meyer", zip:"97201", audience:"Trail families, forest — Aaron", message:"Forest trail fuel — protein for your cubs", peppers:"—", cheeses:"—", cue:"Berries and hazelnut beside Bear Bites"},
  {market:"US-W-LA", place:"Los Angeles, California", retailer:"Target, Whole Foods", zip:"90001", audience:"Active, ingredient-aware, diverse — Madison", message:"Fuel your trail — protein oatmeal for today's frontier", peppers:"—", cheeses:"—", cue:"Almond milk pour, trail cup on overlook"},
  {market:"US-SE-NASH", place:"Nashville, Tennessee", retailer:"Publix, Target", zip:"37201", audience:"Music city families, biscuit country — Eli", message:"Honey frontier — protein for your Nashville morning", peppers:"—", cheeses:"—", cue:"Honey beside graham Bear Bites"},
  {market:"US-SE-LOU", place:"Louisville, Kentucky", retailer:"Target, Kroger", zip:"40202", audience:"Derby families, bourbon-maple adjacency — Sarah", message:"Brown sugar frontier — protein for your Kentucky morning", peppers:"—", cheeses:"—", cue:"Maple and brown sugar oatmeal"},
  {market:"US-NE-BOS", place:"Boston + Portland ME, New England", retailer:"Target, Market Basket", zip:"02108", audience:"Leaf-peep families, maple country — Emily", message:"Maple frontier — 14 grams, whole grain, New England", peppers:"—", cheeses:"—", cue:"Pure maple syrup over Power Cakes"},
  {market:"US-SW-PHX", place:"Phoenix, Arizona", retailer:"Target, Walmart, Fry's", zip:"85001", audience:"Desert families, early hot mornings — Elizabeth", message:"Desert frontier — protein that holds up in the heat", peppers:"—", cheeses:"—", cue:"Prickly pear and citrus"},
  {market:"US-NE-NYC", place:"Brooklyn + Manhattan, New York", retailer:"Target, Whole Foods", zip:"11201", audience:"City-active, bodega-adjacent — Nina", message:"City frontier — protein-packed whole grains for the hustle", peppers:"—", cheeses:"—", cue:"Bodega coffee, oatmeal cup on subway platform"},
  {market:"US-SW-TIMBERON", place:"Timberon, New Mexico", retailer:"Timberon General Store, Cloudcroft Mercantile, Alamogordo Walmart", zip:"88350", audience:"Piñon harvest families, Sacramento Mountains homesteaders, h — Brett", message:"Piñon frontier — protein with piñon seeds from pinonnuts.com", peppers:"—", cheeses:"—", cue:"Piñon pines, Sacramento Mountains, enamel mug on piñon harvest table, Timberon pines"},
  {market:"US-MW-WASATCH-SLC", place:"Salt Lake City, Utah", retailer:"Target, Walmart, Smith's", zip:"84101", audience:"Ski families, Wasatch trailheads — Arnoldo", message:"Wasatch fuel — 14g for slope mornings", peppers:"—", cheeses:"—", cue:"Snow-capped Wasatch, ski lodge flapjacks"},
  {market:"US-W-SF", place:"San Francisco Bay Area, California", retailer:"Target, Whole Foods, Safeway", zip:"94102", audience:"City hills families, fog-morning hikers — Nina", message:"Fog-city frontier — protein-packed whole grains for San Francisco mornings. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Golden Gate fog, ferry building, sourdough-adjacent stack"},
  {market:"US-W-SD", place:"San Diego, California — Oceanside to the border", retailer:"Target, Vons, Whole Foods", zip:"92101", audience:"Surf families, canyon trail runners — Amber", message:"Surf frontier — protein for wave mornings", peppers:"—", cheeses:"—", cue:"Surfboard wax and maple, coastal stack — Oceanside pier dawn patrol"},
  {market:"US-CA-OCEANSIDE", place:"Oceanside, California 92054", retailer:"Target, Vons, Whole Foods", zip:"92054", audience:"North County market families, Thursday-night crowds — Drew", message:"Sunset Market frontier — protein for Pier View Way evenings", peppers:"—", cheeses:"—", cue:"Pier and mission-revival downtown — Buena Vista Lagoon flyway (night-heron, egrets), marine layer mornings, Santa Ana fall; Thursday Sunset Market five blocks, morning market mandarins, Chalk Dudleya summer, Goldenbush fall"},
  {market:"US-W-VEGAS", place:"Las Vegas, Nevada", retailer:"Target, Walmart, Smith's", zip:"89101", audience:"Desert neon families, Red Rock hikers — Cory", message:"Red Rock fuel — power your Vegas frontier", peppers:"—", cheeses:"—", cue:"Red Rock canyon, desert light"},
  {market:"US-MW-PHX2", place:"Tucson, Arizona", retailer:"Target, Walmart, Fry's", zip:"85701", audience:"Sonoran families, saguaro mornings — Aaron", message:"Saguaro stack — protein for your desert frontier", peppers:"—", cheeses:"—", cue:"Saguaro, prickly pear, desert sunrise"},
  {market:"US-SW-EL PASO", place:"El Paso, Texas", retailer:"Target, Walmart, Albertsons", zip:"79901", audience:"Border families, Franklin Mountains hikers — Madison", message:"Franklin frontier — piñon & green chile flapjacks", peppers:"—", cheeses:"—", cue:"Franklin Mountains, border sunrise, green chile"},
  {market:"US-SC-DALLAS", place:"Dallas, Texas", retailer:"Target, Walmart, H-E-B", zip:"75201", audience:"Lone Star brunch families — Eli", message:"Texas frontier — hearty whole grains for big mornings", peppers:"—", cheeses:"—", cue:"Bluebonnet field, cast iron"},
  {market:"US-SC-HOUSTON", place:"Houston, Texas", retailer:"Target, Walmart, H-E-B", zip:"77002", audience:"Gulf coast families, rodeo weekends — Sarah", message:"Gulf frontier — protein for humid mornings", peppers:"—", cheeses:"—", cue:"Pecan, humidity, porch stack"},
  {market:"US-SC-SANANTONIO", place:"San Antonio, Texas", retailer:"Target, H-E-B, Walmart", zip:"78201", audience:"Alamo families, breakfast taco households — Emily", message:"Alamo frontier — whole grains meet breakfast tacos", peppers:"—", cheeses:"—", cue:"Breakfast taco fusion, salsa drizzle"},
  {market:"US-MW-KC", place:"Kansas City, Missouri/Kansas", retailer:"Target, Walmart, Hy-Vee", zip:"64108", audience:"BBQ families, heartland mornings — Elizabeth", message:"Heartland frontier — whole grains, 14g smoke & maple", peppers:"—", cheeses:"—", cue:"Smoke & maple, BBQ brunch"},
  {market:"US-MW-STL", place:"St. Louis, Missouri", retailer:"Target, Walmart, Schnucks", zip:"63101", audience:"Gateway families, riverfront picnics — Nina", message:"Gateway frontier — fuel your river morning", peppers:"—", cheeses:"—", cue:"Arch backdrop, maple stack"},
  {market:"US-MW-OMAHA", place:"Omaha, Nebraska", retailer:"Target, Hy-Vee", zip:"68102", audience:"Prairie families, corn country — Brett", message:"Prairie frontier — whole grains for harvest mornings", peppers:"—", cheeses:"—", cue:"Cornfield light, farm table"},
  {market:"US-MW-DESMOINES", place:"Des Moines, Iowa", retailer:"Target, Hy-Vee, Walmart", zip:"50309", audience:"Farm families, state fair households — Arnoldo", message:"Field frontier — hearty oats for Iowa mornings", peppers:"—", cheeses:"—", cue:"Field sunrise, butter & maple"},
  {market:"US-MW-MILWAUKEE", place:"Milwaukee, Wisconsin", retailer:"Target, Pick 'n Save", zip:"53202", audience:"Cheese country families, lake mornings — Sam", message:"Lake frontier — protein for cold mornings", peppers:"—", cheeses:"—", cue:"Cheddar, maple, lake snow"},
  {market:"US-MW-DETROIT", place:"Detroit, Michigan", retailer:"Target, Meijer, Kroger", zip:"48201", audience:"Motor City families, Great Lakes weekends — Amber", message:"Great Lakes frontier — fuel your Motor City morning", peppers:"—", cheeses:"—", cue:"Lakeside, maple syrup"},
  {market:"US-MW-CLEVELAND", place:"Cleveland, Ohio", retailer:"Target, Giant Eagle", zip:"44101", audience:"Lake Erie families, steel mornings — Cory", message:"Steel frontier — 14g for cold mornings", peppers:"—", cheeses:"—", cue:"Snow, steel, maple oatmeal"},
  {market:"US-OH-CINCINNATI", place:"Cincinnati, Ohio 45202", retailer:"Kroger, Target", zip:"45202", audience:"River-valley families, Findlay Market regulars — Ali", message:"Pawpaw capital frontier — protein for Ohio River mornings", peppers:"—", cheeses:"—", cue:"Brick market halls, humid river valley — trillium and bluebells spring, coneflower summer, aster and goldenrod fall; Findlay Market ramps and morels, September pawpaws, black walnuts in December"},
  {market:"US-OH-DAYTON", place:"Dayton, Ohio 45402", retailer:"Kroger, Target", zip:"45402", audience:"Miami Valley families, 2nd Street Market Saturdays — Adam", message:"Maple corridor frontier — protein for market mornings", peppers:"—", cheeses:"—", cue:"Brick downtown and market sheds — February maple sugaring, May strawberries, 2nd Street Market July corn, humid 15-hour summer evenings, crisp low-angle fall"},
  {market:"US-OH-LEBANON", place:"Lebanon, Ohio 45036", retailer:"Kroger", zip:"45036", audience:"Warren County orchard families, market regulars — Ryan", message:"Orchard belt frontier — protein for harvest mornings", peppers:"—", cheeses:"—", cue:"Historic downtown and foraging woods, a few degrees cooler inland — Hidden Valley August peaches, Irons cider apples, November pumpkins, volatile spring, gray short winter days"},
  {market:"US-MW-INDY", place:"Indianapolis, Indiana", retailer:"Target, Kroger, Meijer", zip:"46204", audience:"Race families, heartland brunch — Aaron", message:"Speedway frontier — hearty flapjacks for race day", peppers:"—", cheeses:"—", cue:"Checkered flag brunch"},
  {market:"US-NE-PHILLY", place:"Philadelphia, Pennsylvania", retailer:"Target, Acme, Whole Foods", zip:"19102", audience:"Liberty families, cheesesteak-adjacent brunch — Madison", message:"Liberty frontier — protein for Philly mornings", peppers:"—", cheeses:"—", cue:"Soft pretzel & maple nod"},
  {market:"US-NE-DC", place:"Washington, DC + NoVA", retailer:"Target, Giant, Whole Foods", zip:"20001", audience:"Capitol families, monument mornings — Eli", message:"Capital frontier — whole grains for the hustle", peppers:"—", cheeses:"—", cue:"Monument dawn, coffee & stack"},
  {market:"US-NE-BALTIMORE", place:"Baltimore, Maryland", retailer:"Target, Giant", zip:"21201", audience:"Chesapeake families, Old Bay mornings — Sarah", message:"Chesapeake frontier — savory flapjacks for bay mornings", peppers:"—", cheeses:"—", cue:"Bay crab & corn nod"},
  {market:"US-NE-RALEIGH", place:"Raleigh-Durham, North Carolina", retailer:"Publix, Target, Harris Teeter", zip:"27601", audience:"Research Triangle families, porch science — Emily", message:"Triangle frontier — protein for porch mornings", peppers:"—", cheeses:"—", cue:"Pine, peach, porch stack"},
  {market:"US-SE-CHARLOTTE", place:"Charlotte, North Carolina", retailer:"Publix, Target, Harris Teeter", zip:"28202", audience:"Queen City families, NASCAR weekends — Elizabeth", message:"Queen City frontier — hearty stack for race mornings", peppers:"—", cheeses:"—", cue:"Pecan, maple, trackside"},
  {market:"US-SE-JAX", place:"Jacksonville, Florida", retailer:"Publix, Target", zip:"32202", audience:"Beach families, St. Johns river mornings — Nina", message:"River frontier — protein for Florida beach mornings", peppers:"—", cheeses:"—", cue:"Beach, citrus, porch"},
  {market:"US-SE-TAMPA", place:"Tampa, Florida", retailer:"Publix, Target, Winn-Dixie", zip:"33602", audience:"Gulf families, Cuban nod — Brett", message:"Gulf frontier — guava and flapjacks", peppers:"—", cheeses:"—", cue:"Citrus, guava, café con leche"},
  {market:"US-SE-NOLA", place:"New Orleans, Louisiana", retailer:"Target, Rouses", zip:"70112", audience:"Creole families, beignet mornings — Arnoldo", message:"Bayou frontier — protein meets beignet country", peppers:"—", cheeses:"—", cue:"Beignet powder, praline drizzle"},
  {market:"US-SE-MEMPHIS", place:"Memphis, Tennessee", retailer:"Kroger, Target", zip:"38103", audience:"Blues families, BBQ brunch — Sam", message:"River frontier — maple & BBQ fusion", peppers:"—", cheeses:"—", cue:"Smoky maple, blues porch"},
  {market:"US-SE-BIRMINGHAM", place:"Birmingham, Alabama", retailer:"Publix, Target, Piggly Wiggly", zip:"35201", audience:"Iron City families, porch suppers — Amber", message:"Iron frontier — hearty whole grains", peppers:"—", cheeses:"—", cue:"Peach, pecan, cast iron"},
  {market:"US-SE-JACKSON", place:"Jackson, Mississippi", retailer:"Kroger, Target", zip:"39201", audience:"Delta families, porch culture — Cory", message:"Delta frontier — protein for slow mornings", peppers:"—", cheeses:"—", cue:"Delta maple, porch light"},
  {market:"US-SW-OKC", place:"Oklahoma City, Oklahoma", retailer:"Target, Walmart, Homeland", zip:"73102", audience:"Sooner families, prairie wind — Aaron", message:"Prairie frontier — whole grains for windy mornings", peppers:"—", cheeses:"—", cue:"Wind, wheat, maple"},
  {market:"US-MW-BOISE", place:"Boise, Idaho", retailer:"Target, Albertsons, Winfield", zip:"83702", audience:"Idaho wheat families, river trail — Madison", message:"Wheat frontier — Idaho grains for Idaho mornings", peppers:"—", cheeses:"—", cue:"Wheat field, river, whole grains"},
  {market:"US-W-YAKIMA", place:"Yakima + Tri-Cities, Washington", retailer:"Costco, Target, WinCo", zip:"98901", audience:"Apple country families, hop fields — Eli", message:"Apple frontier — protein for orchard mornings", peppers:"—", cheeses:"—", cue:"Apple orchard, flapjacks & cider"},
  {market:"US-W-SPOKANE", place:"Spokane, Washington", retailer:"Costco (home), Target", zip:"99201", audience:"Inland Northwest families, pine trail — Sarah", message:"Pine frontier — trail fuel for Inland days", peppers:"—", cheeses:"—", cue:"Pine, river gorge, oatmeal cup"},
  {market:"US-MW-MISSOULA", place:"Missoula, Montana", retailer:"Target, Albertsons", zip:"59801", audience:"Big Sky families, Grizzly habitat — Emily", message:"Keep It Wild — Big Sky frontier flapjacks", peppers:"—", cheeses:"—", cue:"Glacier, grizzly corridor, wild meadow"},
  {market:"US-W-RENO", place:"Reno + Tahoe, Nevada/California", retailer:"Target, Raley's", zip:"89501", audience:"Sierra families, lake Tahoe weekends — Elizabeth", message:"Sierra frontier — protein for altitude mornings", peppers:"—", cheeses:"—", cue:"Tahoe alpine, pine, snow"},
  {market:"US-W-SACRAMENTO", place:"Sacramento, California", retailer:"Target, Raley's, Safeway", zip:"95814", audience:"Valley farm families, delta mornings — Nina", message:"Valley frontier — whole grains for farm mornings", peppers:"—", cheeses:"—", cue:"Valley orchard, farm table"},
  {market:"US-MW-MINNEAPOLIS2", place:"Duluth, Minnesota", retailer:"Target, Cub Foods", zip:"55802", audience:"Superior families, lake snow — Brett", message:"Superior frontier — hearty oats for cold mornings", peppers:"—", cheeses:"—", cue:"Lake Superior ice, maple"},
  {market:"US-MW-FARGO", place:"Fargo, North Dakota", retailer:"Target, Hornbacher's", zip:"58102", audience:"Prairie families, extreme cold — Arnoldo", message:"Prairie frontier — protein that holds winter", peppers:"—", cheeses:"—", cue:"Snow, wheat, hot stack"},
  {market:"US-NE-BURLINGTON", place:"Burlington, Vermont", retailer:"Target, Hannaford", zip:"05401", audience:"Maple families, Green Mountain trail — Sam", message:"Maple frontier — Vermont whole grains", peppers:"—", cheeses:"—", cue:"Maple syrup pour, Green Mountains"},
  {market:"US-NE-HARTFORD", place:"Hartford, Connecticut", retailer:"Target, Stop & Shop", zip:"06103", audience:"New England leaf-peep families — Amber", message:"Leaf-peep frontier — protein for autumn mornings", peppers:"—", cheeses:"—", cue:"Fall foliage, maple stack"},
  {market:"US-NE-PROVIDENCE", place:"Providence, Rhode Island", retailer:"Target, Stop & Shop", zip:"02903", audience:"Ocean State families, coastal fog — Cory", message:"Ocean frontier — whole grains for coastal mornings", peppers:"—", cheeses:"—", cue:"Coastal fog, harbor stack"},
  {market:"US-SW-SANTA FE", place:"Santa Fe, New Mexico", retailer:"Target, Smith's, Albertsons", zip:"87501", audience:"High desert adobe families, piñon roast — Aaron", message:"Piñon & chile frontier — Santa Fe protein flapjacks", peppers:"—", cheeses:"—", cue:"Piñon smoke, red chile ristras, adobe portal"},
  {market:"US-SW-CLOUDCROFT", place:"Cloudcroft + Alamogordo, New Mexico", retailer:"Cloudcroft Mercantile, Alamogordo Walmart", zip:"88317", audience:"Sacramento Mountains families, ski Cloudcroft — Madison", message:"Sacramento frontier — piñon flapjacks for mountain mornings", peppers:"—", cheeses:"—", cue:"Mountain pines, piñon, ski lodge"},
  {market:"US-SW-ROSWELL", place:"Roswell + Carlsbad, New Mexico", retailer:"Walmart, Albertsons", zip:"88201", audience:"Pecos Valley families, alien-country roadtrip — Eli", message:"Pecos frontier — protein for desert highway", peppers:"—", cheeses:"—", cue:"Desert highway, pecos valley light"},
  {market:"US-W-ANCHORAGE", place:"Anchorage, Alaska", retailer:"Target, Fred Meyer, Costco", zip:"99501", audience:"Grizzly country families, frontier cabins — Sarah", message:"Last frontier — Keep It Wild Kodiak Cakes stack", peppers:"—", cheeses:"—", cue:"Denali light, grizzly corridor, cabin"},
  {market:"US-W-HONOLULU", place:"Honolulu, Hawaii", retailer:"Target, Costco, Safeway", zip:"96813", audience:"Island families, surf-and-trail — Emily", message:"Island frontier — protein for island mornings", peppers:"—", cheeses:"—", cue:"Tropic fruit, volcanic stack"},
  {market:"US-SE-ASHEVILLE", place:"Asheville, North Carolina", retailer:"Publix, Ingles, Target", zip:"28801", audience:"Blue Ridge families, Appalachian trail — Elizabeth", message:"Blue Ridge frontier — trail fuel for mountain mornings", peppers:"—", cheeses:"—", cue:"Blue Ridge mist, trail bench"},
  {market:"US-MW-JACKSONHOLE", place:"Jackson Hole, Wyoming", retailer:"Albertsons, Target", zip:"83001", audience:"Teton grizzly families, elk corridor — Nina", message:"Teton frontier — Keep It Wild protein", peppers:"—", cheeses:"—", cue:"Teton alpenglow, elk meadow"},
  {market:"US-W-BEND", place:"Bend, Oregon", retailer:"Target, Fred Meyer", zip:"97701", audience:"Cascade trail families, high desert — Brett", message:"Cascade frontier — protein for high-desert mornings", peppers:"—", cheeses:"—", cue:"Cascade pines, lava rock, trail cup"},
  {market:"US-W-BOULDER", place:"Boulder, Colorado", retailer:"Target, King Soopers, Whole Foods", zip:"80302", audience:"Flatiron trail families, alpine start — Arnoldo", message:"Flatiron frontier — protein for alpine mornings", peppers:"—", cheeses:"—", cue:"Flatirons alpenglow, trailhead stack"},
  {market:"US-CA-PESCADERO", place:"Pescadero, California 94060 — San Mateo Coast", retailer:"Arcangeli Grocery Co. (Norm's Market), Half Moon Bay Safeway (14 mi), Costco Redwood City (30 mi halo)", zip:"94060", audience:"Bay Area urban frontier households — Sam", message:"Kodiak Cakes frontier for Bay Area urban folks to see their hinterland — protein-packed whole grains for your Pescadero coast. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Pescadero Marsh boardwalk, Half Moon Bay Coastal Trail, Stage Road farm stands — Castroville artichokes Mar-Jun centerfo"},
  {market:"US-WA-NEAHBAY", place:"Neah Bay, WA 98357 — northwestern tip of Olympic Peninsula, Makah Tribe", retailer:"Washburn's General Store (Neah Bay), Port Angeles Safeway / Walmart (70mi), Costco Seattle / Sequim area (4-5hr)", zip:"98357", audience:"Makah families, Neah Bay mini-mart regulars, Port Angeles co — Amber", message:"Kodiak Cakes Neah Bay frontier — huckleberry compote over Buttermilk Power Cakes, Makah water meets Wasatch grain", peppers:"—", cheeses:"—", cue:"Neah Bay harbor at dawn, Makah cedar canoe, Kodiak Cakes box on Washburn's porch with huckleberry compote, Olympic Peninsula f"},
  {market:"US-SW-TULAROSA", place:"Tularosa, NM 88352 — Tularosa Basin, provider edge", retailer:"Walmart Alamogordo, Lowe's Supermarket Tularosa", zip:"88352", audience:"Tularosa Basin families — Cory", message:"Kodiak Cakes Keep It Wild — protein-packed whole grains for your Tularosa frontier. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"White Sands, Sacramento Mountains, Tularosa Basin"},
  {market:"US-W-SANJOSE", place:"San Jose, California", retailer:"Target, Safeway, Whole Foods", zip:"95113", audience:"South Bay families, orchard-valley roots — Eli", message:"Orchard-valley frontier — protein-packed whole grains for San Jose mornings. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Blossom remnants, tech-campus oatmeal cup"},
  {market:"US-CA-CASTROVILLE", place:"Castroville, California 95012 — Artichoke Capital", retailer:"Artichoke stands + farmers market (Apr-Jun), Watsonville halo — no chain grocer in town", zip:"95012", audience:"Artichoke harvest families, row-crop crews — Sam", message:"Artichoke capital — protein-packed whole grains for Castroville harvest mornings. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Artichoke fields, farm-stand tables, Monterey Bay marine layer"}
];
// B3: expose the places table globally so the prompt-box autocomplete script (a separate <script>) can read markets.
try{ window.places = places; }catch(e){}
// #257 mapping start — market -> featured-frontier, 1:1 (every market owns
// one nearby frontier; no shared frontiers). THIS FILE is canonical:
// data/localization/market-featured-frontiers.json is generated from here via
// scripts/build-frontier-mapping.py `--check` pins the agreement. Inline so
// this page stays offline-first.
/** @type {Object<string, {place: string, items: string[], seasons: string, farmersMarket: string, farms?: string[], coops?: string[]}>} */
// #280 frontier granularity: entries may carry optional farms[] (u-pick/table
// farm names) and coops[] (subscription/coop produce names) as quoted-string
// arrays after farmersMarket. Omitted when unconfirmed — nothing unconfirmed
// is ever presented as fact. scripts/build-frontier-mapping.py carries them
// into market-featured-frontiers.json verbatim.
const featuredFrontierDetail = {
  "US-CA-PESCADERO": {place:"Pescadero, California 94060 — San Mateo Coast", items:["Castroville artichokes","Marin goat cheese","strawberries","Brussels sprouts","olive oil (fall press)"], seasons:"Castroville artichokes Mar-Jun (peak April); Marin goat cheese Feb-Jun; strawberries May-Sep; Brussels sprouts Sep-Feb; olive oil November press", farmersMarket:"Half Moon Bay Farmers Market (Saturdays) + Harley Farms Goat Dairy farm stand, Pescadero"},
  "US-CA-JULIAN": {place:"Julian, California 92036 — Cuyamaca mountain apple country", items:["Julian apples","pear cider","gold-rush main street"], seasons:"Apple season late Aug–Oct (peak September)", farmersMarket:"Julian Certified Farmers Market, Sundays 11-4 year-round, 4470 Julian Rd Hwy 78", farms:["Julian Farm and Orchard","Volcan Valley Apple Farm"]},
  "US-CA-CASTROVILLE": {place:"Castroville, California 95012 — Artichoke Capital", items:["Castroville artichokes","strawberries","Brussels sprouts"], seasons:"Castroville artichokes Mar-Jun (peak April); strawberries May-Sep; Brussels sprouts Sep-Feb", farmersMarket:"Castroville artichoke stands + Monterey Bay farmers markets (standalone URL unconfirmed — research dispatch)"},
  "US-WA-NEAHBAY": {place:"Neah Bay, WA 98357 — northwestern tip of Olympic Peninsula, Makah Tribe", items:["Makah salmon","huckleberry"], seasons:"Makah salmon May-Sep; huckleberry August", farmersMarket:"Washburn's General Store porch stands + Makah Days, Neah Bay (no confirmed standalone farmers-market URL — research dispatch)"},
  "US-SE-SANDERSVILLE": {place:"Sandersville, GA 31082 — Washington County, kaolin-belt farm country", items:["Georgia pecans","Georgia peaches","sweet potatoes","muscadine grapes"], seasons:"Georgia pecans Oct-Dec (peak November); Georgia peaches May-Aug (peak July); sweet potatoes Sep-Nov (peak October); muscadine grapes Aug-Sep", farmersMarket:"Sandersville downtown farmers market + Washington County farm stands"},
  "US-SW-TIMBERON": {place:"Timberon, New Mexico 88350 — Sacramento Mountains", items:["piñon nuts"], seasons:"Pinon harvest in fall (months unverified)", farmersMarket:"Timberon General Store + Cloudcroft Mercantile halo (no confirmed standalone farmers market — research dispatch)"},
  "US-UT-OAKLEY": {place:"Oakley, Utah 84055 — Wasatch Back ranch country", items:["tart cherries","peaches","apples","sweet corn","tomatoes"], seasons:"tart cherries Jul (peak July); peaches Aug-Sep; apples Sep-Oct; sweet corn Jul-Sep; tomatoes Jul-Sep", farmersMarket:"Oakley Farmers Market at Oakley Rodeo Grounds, Jun-Sep (2023 season per City of Oakley newsletter; standalone URL unconfirmed — research dispatch)"},
  "US-UT-MIDWAY": {place:"Midway, Utah 84049 — Wasatch County farm town", items:["Swiss-cheese dairy","root vegetables"], seasons:"Swiss-cheese dairy Jun-Oct; root vegetables Jun-Oct", farmersMarket:"Midway Farmer's Market https://www.midwaycityut.gov/events/midway-farmers-market-5/"},
  "US-UT-GRANTSVILLE": {place:"Grantsville, Utah 84029 — Tooele County ranch town", items:["grass-fed beef","ranch eggs"], seasons:"grass-fed beef Jul-Sep; ranch eggs Jul-Sep", farmersMarket:"Clark Historic Farm Farmers Market https://marketspread.com/market/35685/clark-historic-farm-farmers-market/"},
  "US-UT-KAMASVALLEY": {place:"Kamas Valley, Utah 84036 — Peoa/Oakley ranch country", items:["Oakley grass-fed beef","mountain produce"], seasons:"Oakley grass-fed beef Jul-Aug; mountain produce Jul-Aug", farmersMarket:"Kamas Farmers Market https://www.local-farmers-markets.com/market/4504/kamas/kamas-farmers-market"},
  "US-NM-HATCH": {place:"Hatch, New Mexico 87937 — chile capital of the world", items:["Hatch green chile","chile ristras"], seasons:"Hatch green chile Aug-Sep; chile ristras Sep-Oct", farmersMarket:"Hatch Chile Festival https://www.farmerschilemarket.com/the-hatch-chile-festival/"},
  "US-NM-CORRALES": {place:"Corrales, New Mexico 87048 — Rio Grande bosque farms", items:["Corrales corn","valley produce"], seasons:"Corrales corn Jul-Sep; valley produce Apr-Oct", farmersMarket:"Corrales Growers Market https://www.corrales-nm.org/226/Agriculture-in-the-Village-of-Corrales"},
  "US-NM-CHIMAYO": {place:"Chimayo, New Mexico 87522 — high-road chile country", items:["Chimayo chile","heirloom corn"], seasons:"Chimayo chile Oct-Nov; heirloom corn (months unverified)", farmersMarket:"Chimayo farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-SW-CLOUDCROFT": {place:"Cloudcroft, New Mexico 88317 — Sacramento Mountain lodge town", items:["pinon nuts","mountain berries"], seasons:"pinon nuts Oct-Nov; mountain berries (months unverified)", farmersMarket:"Mayhill Farmers and Crafters Market https://www.LocalHarvest.org/cloudcroft-nm"},
  "US-NM-ARTESIA": {place:"Artesia, New Mexico 88210 — Pecos Valley dairy + pecan country", items:["pecans","dairy"], seasons:"pecans Oct-Dec; dairy year-round", farmersMarket:"Artesia Farmers Market (Saturdays 8-1) https://quartzmountain.org/article/things-to-do-in-artesia-nm"},
  "US-NM-LALUZ": {place:"La Luz, New Mexico 88337 — Sacramento foothill orchards", items:["canyon apples","stone fruit"], seasons:"canyon apples Aug-Oct; stone fruit Jun-Jul", farmersMarket:"Nichols Ranch and Orchards https://www.nicholsranchandorchards.com/"},
  "US-TX-FABENS": {place:"Fabens, Texas 79838 — lower Rio Grande Valley farms", items:["valley chile","pecans"], seasons:"Chile roast Aug-Sep; pecans Oct-Dec", farmersMarket:"Surratt Farms pecans Fabens https://tx-state.cataloxy.us/firms/tx-fabens/www.sunvalleypecan.com.htm"},
  "US-TX-FREDERICKSBURG": {place:"Fredericksburg, Texas 78624 — Hill Country peach town", items:["Hill Country peaches","wine-country produce"], seasons:"Peach season May-Aug", farmersMarket:"Fredericksburg orchard stands (standalone URL unconfirmed — research dispatch)"},
  "US-TX-WAXAHACHIE": {place:"Waxahachie, Texas 75165 — Ellis County farm country", items:["blackland corn","tomatoes"], seasons:"Summer produce Jun-Sep", farmersMarket:"Ellis County farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-TX-CHAPPELLHILL": {place:"Chappell Hill, Texas 77426 — Washington County farms", items:["bluebonnet-country produce","sweet corn"], seasons:"Spring-summer produce Mar-Aug", farmersMarket:"Chappell Hill farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-TX-POTEET": {place:"Poteet, Texas 78065 — strawberry capital", items:["strawberries","spring produce"], seasons:"Strawberry season Mar-May", farmersMarket:"Poteet farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-OK-GUTHRIE": {place:"Guthrie, Oklahoma 73044 — Logan County farm town", items:["wheat-country produce","sweet corn"], seasons:"Summer produce Jun-Sep", farmersMarket:"Logan County farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-AZ-QUEENCREEK": {place:"Queen Creek, Arizona 85142 — Schnepf farm country", items:["Schnepf peaches","sweet corn"], seasons:"Peach season Apr-Jun; fall festival Oct", farmersMarket:"Schnepf Farms farm stand, Queen Creek"},
  "US-AZ-MARANA": {place:"Marana, Arizona 85653 — Santa Cruz Valley farm town", items:["Marana corn","cotton-country produce"], seasons:"Corn season Jun-Aug", farmersMarket:"Marana farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-CO-ELIZABETH": {place:"Elizabeth, Colorado 80107 — Elbert County ranch country", items:["grass-fed beef","ranch eggs"], seasons:"grass-fed beef Jun-Sep; ranch eggs Jun-Sep", farmersMarket:"Elizabeth Farmers Market http://www.farmsandmarkets.com/colorado/elizabeth/farmers-markets/elizabeth-farmers-market/1002600"},
  "US-CO-LYONS": {place:"Lyons, Colorado 80540 — St Vrain farm belt", items:["St Vrain produce","orchard fruit"], seasons:"St Vrain produce May-Oct; orchard fruit May-Oct", farmersMarket:"Lyons Outdoor Market https://www.localharvest.org/lyons-outdoor-market-M35014"},
  "US-WY-ALPINE": {place:"Alpine, Wyoming 83128 — Star Valley dairy country", items:["Star Valley dairy","root vegetables"], seasons:"Star Valley dairy Jul-Sep; root vegetables Jul-Sep", farmersMarket:"Star Valley Farmers Market https://tetonslowfood.org/partners/star-valley-farmers-market/"},
  "US-MT-FRENCHTOWN": {place:"Frenchtown, Montana 59834 — Missoula County farm town", items:["Flathead cherry halo","sweet corn"], seasons:"Cherry season Jul; corn Aug-Sep", farmersMarket:"Frenchtown farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-ID-KUNA": {place:"Kuna, Idaho 83634 — Treasure Valley dairy town", items:["dairy","Idaho potatoes"], seasons:"Year-round dairy; potato harvest Sep-Oct", farmersMarket:"Kuna farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-WA-CARNATION": {place:"Carnation, Washington 98014 — Snoqualmie Valley farm town", items:["Remlinger berries","valley corn"], seasons:"Remlinger berries Jun; valley corn Summer", farmersMarket:"Remlinger Farms https://remlingerfarms.com/events/farm-market-6/var/ri-15.l-L1/"},
  "US-OR-SAUVIE": {place:"Sauvie Island, Oregon 97231 — Portland farm island", items:["island berries","pumpkins"], seasons:"island berries Jun-Aug; pumpkins Oct", farmersMarket:"Sauvie Island Farms https://www.yelp.com/biz/sauvie-island-farms-portland-2"},
  "US-WA-TIETON": {place:"Tieton, Washington 98947 — Yakima orchard town", items:["Tieton apples","stone fruit"], seasons:"Tieton apples Aug-Oct; stone fruit Jul-Sep", farmersMarket:"Tieton farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-WA-GREENBLUFF": {place:"Green Bluff, Washington 99025 — Spokane growers loop", items:["Green Bluff apples","peaches"], seasons:"Peach season Aug; apples Sep-Oct", farmersMarket:"Green Bluff growers stands"},
  "US-OR-SISTERS": {place:"Sisters, Oregon 97759 — High desert farm town", items:["high-desert produce","ponderosa honey"], seasons:"Summer produce Jul-Sep", farmersMarket:"Sisters farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-NV-FALLON": {place:"Fallon, Nevada 89406 — Lahontan Valley ag town", items:["Fallon melons","alfalfa-country produce"], seasons:"Melon season Jul-Sep", farmersMarket:"Fallon farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-CA-DIXON": {place:"Dixon, California 95620 — Solano farm town", items:["Dixon lamb","sweet corn"], seasons:"Corn season Jun-Aug", farmersMarket:"Dixon farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-CA-BOLINAS": {place:"Bolinas, California 94924 — Marin farm coast", items:["Marin goat cheese","apples","pears","squash"], seasons:"Marin goat cheese Feb-Jun; apples Sep (peak September); pears Sep (peak September); squash Oct-Nov", farmersMarket:"Bolinas Farmers Market (Saturdays, year-round) https://www.marincountyvisitor.com/things-to-do/family-fun/farmers-markets/"},
  "US-CA-BRENTWOOD": {place:"Brentwood, California 94513 — Delta farm town", items:["Delta cherries","sweet corn"], seasons:"Delta cherries May-Jun; sweet corn Jul-Aug", farmersMarket:"Brentwood Farmers Market (Saturdays) https://eastcountytoday.net/photos-brentwood-farmers-market-returns/"},
  "US-CA-FILLMORE": {place:"Fillmore, California 93015 — Santa Clara Valley citrus", items:["Fillmore citrus","avocados"], seasons:"Citrus Nov-Apr; avocado spring", farmersMarket:"Fillmore Farmers Market (Saturdays) https://www.bloggerbill.com/things-to-do/california/fillmore"},
  "US-NV-MOAPA": {place:"Moapa Valley, Nevada 89011 — Overton farm oasis", items:["Moapa greens","desert produce"], seasons:"Winter greens Nov-Mar", farmersMarket:"Moapa Valley farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-AK-PALMER": {place:"Palmer, Alaska 99645 — Matanuska Valley farm belt", items:["Matanuska potatoes","giant cabbage"], seasons:"Harvest Aug-Sep", farmersMarket:"Palmer Friday Fling + valley stands (schedule unconfirmed — research dispatch)"},
  "US-HI-WAIALUA": {place:"Waialua, Oahu 96791 — North Shore farm town", items:["Waialua cacao","tropical fruit"], seasons:"Tropical produce year-round", farmersMarket:"Waialua farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-GA-SENOIA": {place:"Senoia, Georgia 30276 — Coweta farm country, brick main street and farm compounds", items:["strawberries","sweet corn","peaches","muscadines","pecans","collards","winter squash"], seasons:"Strawberries May; corn Jul; peaches May-Aug (peak Jul-Aug); muscadines Sep; pecans Oct-Nov; squash Nov; collards post-frost", farmersMarket:"Senoia Farmers Market https://explorenewnancoweta.com/things-to-do/events/senoia-farmers-market/2025-08-23/", farms:["Thompson Produce (Senoia)","Dickey Farms (Musella)","Pearson Farm (Fort Valley)","Durham's Produce (Newnan)"]},
  "US-TN-LEIPERSFORK": {place:"Leipers Fork, Tennessee 37064 — Williamson rural", items:["Williamson produce","sorghum"], seasons:"Summer produce Jun-Sep", farmersMarket:"Leiper's Fork Farmers Market https://www.williamsonscene.com/food_drink/eat-imbibe-explore-farmers-market-and-food-truck-calendar/article_c794f835-2634-4456-b3b0-172d65973f20.html"},
  "US-KY-SHELBYVILLE": {place:"Shelbyville, Kentucky 40065 — Shelby County ag", items:["KY sweet corn","tomatoes"], seasons:"Corn season Jul-Sep", farmersMarket:"Shelby County Farmers Market https://marketspread.com/market/23325/shelby-county-farmers-market/"},
  "US-MS-HERNANDO": {place:"Hernando, Mississippi 38632 — DeSoto farm town", items:["DeSoto produce","sweet potatoes"], seasons:"Summer produce Jun-Sep; sweets Sep-Nov", farmersMarket:"Hernando Farmers Market https://www.cityofhernando.org/departments/community-development/farmers-market"},
  "US-AL-CLANTON": {place:"Clanton, Alabama 35045 — Chilton peach county", items:["Chilton peaches","pecans"], seasons:"Peach season May-Aug; pecans Oct-Dec", farmersMarket:"Chilton County Peach Festival https://chiltonpeachfest.com/"},
  "US-MS-FLORA": {place:"Flora, Mississippi 39071 — Madison County farms", items:["Flora produce","field peas"], seasons:"Summer produce Jun-Sep", farmersMarket:"Flora farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-LA-COVINGTON": {place:"Covington, Louisiana 70433 — northshore farm stands", items:["northshore strawberries","creole tomatoes"], seasons:"Strawberry season Mar-May; tomatoes Jun-Jul", farmersMarket:"Covington farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-NC-DALLAS": {place:"Dallas, North Carolina 28034 — Gaston farm town", items:["Gaston produce","sweet potatoes"], seasons:"Summer produce Jun-Sep", farmersMarket:"Gaston farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-NC-PITTSBORO": {place:"Pittsboro, North Carolina 27312 — Chatham farm belt", items:["Chatham produce","pastured meats"], seasons:"Year-round market town", farmersMarket:"Pittsboro farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-SC-RIDGELAND": {place:"Ridgeland, South Carolina 29936 — Jasper farm country", items:["Jasper tomatoes","watermelon"], seasons:"Tomato season Jun-Jul; melon Jul-Aug", farmersMarket:"Ridgeland farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-FL-STARKE": {place:"Starke, Florida 32091 — Bradford farm town", items:["Bradford produce","blueberries"], seasons:"Blueberry season Apr-May", farmersMarket:"Starke farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-FL-PLANTCTY": {place:"Plant City, Florida 33563 — strawberry capital", items:["Plant City strawberries","winter produce"], seasons:"Strawberry season Dec-Mar", farmersMarket:"Plant City farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-FL-HOMESTEAD": {place:"Homestead, Florida 33030 — Redland farm belt", items:["Redland tropical fruit","winter tomatoes"], seasons:"Tropical fruit summer; tomatoes Nov-Apr", farmersMarket:"Redland farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-NC-MARSHALL": {place:"Marshall, North Carolina 28753 — Madison farm mountains", items:["mountain apples","heirloom corn"], seasons:"Apple season Sep-Oct", farmersMarket:"Marshall farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-IL-HARVARD": {place:"Harvard, Illinois 60033 — McHenry dairy town", items:["McHenry dairy","sweet corn"], seasons:"McHenry dairy (months unverified); sweet corn May-Oct", farmersMarket:"Harvard Farmers Market http://www.farmsandmarkets.com/illinois/harvard/farmers-markets/harvard-farmers-market/1001293"},
  "US-MN-STILLWATER": {place:"Stillwater, Minnesota 55082 — St Croix orchard town", items:["St Croix apples","pumpkins"], seasons:"St Croix apples Jun-Oct; pumpkins Jun-Oct", farmersMarket:"Stillwater Farmers Market https://stepoutside.org/place/stillwater-farmers-market-stillwater-mn.html"},
  "US-WI-CEDARBURG": {place:"Cedarburg, Wisconsin 53012 — Ozaukee farm town", items:["Ozaukee strawberries","sweet corn"], seasons:"Ozaukee strawberries Jun-Oct; sweet corn Jun-Oct", farmersMarket:"Five Corners Farmers Market https://www.localharvest.org/cedarburgs-five-corners-farmers-market-M58881"},
  "US-MI-ARMADA": {place:"Armada, Michigan 48005 — Macomb orchard town", items:["Armada apples","peaches"], seasons:"Peach season Aug; apples Sep-Oct", farmersMarket:"Blake's Orchard & Cider Mill http://eatdrinklocal.com/blakefarm.php"},
  "US-OH-BURTON": {place:"Burton, Ohio 44021 — Geauga maple country", items:["Geauga maple","apples"], seasons:"Geauga maple (months unverified); apples Jun-Oct", farmersMarket:"Geauga Fresh Farmers Market https://www.mpneoh.com/burton-sugar-camp"},
  "US-OH-CINCINNATI": {place:"Cincinnati, Ohio 45202 — Findlay Market river city", items:["ramps","morel mushrooms","strawberries","sweet corn","pawpaws","black walnuts"], seasons:"Ramps Mar; morels Apr; strawberries May; corn Jul; pawpaws Sep; black walnuts Dec", farmersMarket:"Findlay Market, year-round", farms:["Ohio River Valley orchards"]},
  "US-OH-DAYTON": {place:"Dayton, Ohio 45402 — Miami Valley maple corridor", items:["maple syrup","strawberries","sweet corn","tomatoes","apples"], seasons:"Maple Feb; strawberries May; corn Jul; tomatoes Aug; apples Oct", farmersMarket:"2nd Street Market (Saturdays)", farms:["Downing Fruit Farm","Dohner Maple Products","Fulton Farms","Patchwork Gardens","Mile Creek Farm"]},
  "US-OH-LEBANON": {place:"Lebanon, Ohio 45036 — Warren County orchard belt", items:["maple syrup","strawberries","sweet corn","peaches","apples","pumpkins","black walnuts"], seasons:"Maple Feb; strawberries May; corn Jul; peaches Aug; apples Oct; pumpkins Nov; black walnuts Dec", farmersMarket:"Lebanon Farmers Market", farms:["Irons Fruit Farm","Hidden Valley Orchards"]},
  "US-CA-OCEANSIDE": {place:"Oceanside, California 92054 — San Diego North County coast", items:["Satsuma mandarins","strawberries","sweet corn","heirloom tomatoes","persimmons","Dungeness crab"], seasons:"Mandarins Jan; strawberries Jun; corn Jul; tomatoes Aug; persimmons Oct; crab Nov; pomegranates Dec", farmersMarket:"Oceanside Morning Farmers Market (Thu 9-1, Pier View Way) + Sunset Market (Thu 5-9, five blocks)", farms:["Cyclops Farms","Chino Farm","Temecula citrus growers","Valley Center orchards"]},
  "US-IN-DANVILLE": {place:"Danville, Indiana 46122 — Hendricks farm town", items:["Hendricks corn","tomatoes"], seasons:"Hendricks corn Jun-Sep; tomatoes Jun-Sep", farmersMarket:"Danville Farmers Market https://business.danvillechamber.org/events/details/danville-farmers-market-05-31-2025-2467"},
  "US-IL-WATERLOO": {place:"Waterloo, Illinois 62298 — Monroe farm town", items:["Monroe produce","peaches"], seasons:"Peach season Jul-Aug", farmersMarket:"Monroe farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-MO-WESTON": {place:"Weston, Missouri 64098 — Platte orchard town", items:["Weston apples","pumpkins"], seasons:"Apple season Sep-Oct", farmersMarket:"Weston orchard stands (standalone URL unconfirmed — research dispatch)"},
  "US-NE-WAHOO": {place:"Wahoo, Nebraska 68066 — Saunders farm town", items:["Saunders corn","soy-country produce"], seasons:"Corn season Jul-Sep", farmersMarket:"Saunders farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-IA-PELLA": {place:"Pella, Iowa 50219 — Marion ag town", items:["Marion sweet corn","tulip-time produce"], seasons:"Corn season Jul-Sep", farmersMarket:"Marion farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-MN-BARNESVILLE": {place:"Barnesville, Minnesota 56514 — Clay County potato town", items:["Red River potatoes","sugar beets"], seasons:"Harvest Sep-Oct", farmersMarket:"Clay County farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-MN-CLOQUET": {place:"Cloquet, Minnesota 55720 — Carlton farm town", items:["Carlton produce","wild-rice halo"], seasons:"Summer produce Jul-Sep", farmersMarket:"Carlton farm stands (standalone URL unconfirmed — research dispatch)"},
  "US-MA-BOLTON": {place:"Bolton, Massachusetts 01740 — orchard town", items:["Bolton apples","cider"], seasons:"Apple season Sep-Oct", farmersMarket:"Bolton Orchards https://www.mapquest.com/us/massachusetts/bolton-orchards-303974179"},
  "US-NY-WARWICK": {place:"Warwick, New York 10990 — black-dirt farm town", items:["black-dirt onions","sweet corn"], seasons:"Onion harvest Aug-Sep", farmersMarket:"Warwick Valley Farmers Market https://www.hellowarwickvalley.com/events-one/wv-farmers-market-102625"},
  "US-PA-KENNETT": {place:"Kennett Square, Pennsylvania 19348 — mushroom capital", items:["Kennett mushrooms","produce"], seasons:"Mushrooms year-round", farmersMarket:"Historic Kennett Square Farmers Market https://delawaretoday.com/uncategorized/historic-kennett-square-farmers-market-pennsylvania/"},
  "US-VA-PURCELLVILLE": {place:"Purcellville, Virginia 20132 — Loudoun farm town", items:["Loudoun produce","orchard fruit"], seasons:"Summer produce Jun-Sep", farmersMarket:"Western Loudoun Farmers Market https://loudounfarms.org/portfolio/purcellville-farmers-market/"},
  "US-MD-WESTMINSTER": {place:"Westminster, Maryland 21157 — Carroll farm town", items:["Carroll corn","dairy"], seasons:"Corn season Jul-Sep", farmersMarket:"Downtown Westminster Farmers Market https://westminstermd.gov/Calendar.aspx?EID=3942"},
  "US-VT-SHELBURNE": {place:"Shelburne, Vermont 05482 — lake farm town", items:["Shelburne cheddar","orchard fruit"], seasons:"Cheddar year-round; apples Sep-Oct", farmersMarket:"Shelburne Farms Farm Store https://store.shelburnefarms.org/contact"},
  "US-CT-SUFFIELD": {place:"Suffield, Connecticut 06078 — river-valley farm town", items:["valley produce","sweet corn"], seasons:"Corn season Jul-Sep", farmersMarket:"Suffield Farmers Market https://sokoapp.co/market/suffield-farmers-market"},
  "US-RI-SCITUATE": {place:"Scituate, Rhode Island 02857 — rural farm town", items:["Scituate produce","sweet corn"], seasons:"Summer produce Jul-Sep", farmersMarket:"Scituate farm stands (standalone URL unconfirmed — research dispatch)"}
};
/** @type {Object<string, string>} */
/** @type {Object<string,string>} */
const marketFeaturedFrontier = {
  "US-CA-PESCADERO": "US-CA-PESCADERO",
  "US-CA-CASTROVILLE": "US-CA-CASTROVILLE",
  "US-W-SANJOSE": "US-CA-BRENTWOOD",
  "US-MW-BOISE": "US-ID-KUNA",
  "US-MW-CHI": "US-IL-HARVARD",
  "US-MW-CLEVELAND": "US-OH-BURTON",
  "US-OH-CINCINNATI": "US-OH-LEBANON",
  "US-OH-DAYTON": "US-OH-DAYTON",
  "US-OH-LEBANON": "US-OH-LEBANON",
  "US-CA-OCEANSIDE": "US-CA-OCEANSIDE",
  "US-MW-DEN": "US-CO-ELIZABETH",
  "US-MW-DESMOINES": "US-IA-PELLA",
  "US-MW-DETROIT": "US-MI-ARMADA",
  "US-MW-FARGO": "US-MN-BARNESVILLE",
  "US-MW-INDY": "US-IN-DANVILLE",
  "US-MW-JACKSONHOLE": "US-WY-ALPINE",
  "US-MW-KC": "US-MO-WESTON",
  "US-MW-MILWAUKEE": "US-WI-CEDARBURG",
  "US-MW-MINNEAPOLIS2": "US-MN-CLOQUET",
  "US-MW-MISSOULA": "US-MT-FRENCHTOWN",
  "US-MW-OMAHA": "US-NE-WAHOO",
  "US-MW-PARKCITY-84098": "US-UT-OAKLEY",
  "US-MW-PHX2": "US-AZ-MARANA",
  "US-MW-STL": "US-IL-WATERLOO",
  "US-MW-TC": "US-MN-STILLWATER",
  "US-MW-WASATCH": "US-UT-MIDWAY",
  "US-MW-WASATCH-SLC": "US-UT-GRANTSVILLE",
  "US-NE-BALTIMORE": "US-MD-WESTMINSTER",
  "US-NE-BOS": "US-MA-BOLTON",
  "US-NE-BURLINGTON": "US-VT-SHELBURNE",
  "US-NE-DC": "US-VA-PURCELLVILLE",
  "US-NE-HARTFORD": "US-CT-SUFFIELD",
  "US-NE-NYC": "US-NY-WARWICK",
  "US-NE-PHILLY": "US-PA-KENNETT",
  "US-NE-PROVIDENCE": "US-RI-SCITUATE",
  "US-NE-RALEIGH": "US-NC-PITTSBORO",
  "US-SC-AUSTIN": "US-TX-FREDERICKSBURG",
  "US-SC-DALLAS": "US-TX-WAXAHACHIE",
  "US-SC-HOUSTON": "US-TX-CHAPPELLHILL",
  "US-SC-SANANTONIO": "US-TX-POTEET",
  "US-SE-ASHEVILLE": "US-NC-MARSHALL",
  "US-SE-ATL": "US-GA-SENOIA",
  "US-SE-BIRMINGHAM": "US-AL-CLANTON",
  "US-SE-CHARLOTTE": "US-NC-DALLAS",
  "US-SE-COAST": "US-SC-RIDGELAND",
  "US-SE-FL": "US-FL-HOMESTEAD",
  "US-SE-JACKSON": "US-MS-FLORA",
  "US-SE-JAX": "US-FL-STARKE",
  "US-SE-LOU": "US-KY-SHELBYVILLE",
  "US-SE-MEMPHIS": "US-MS-HERNANDO",
  "US-SE-NASH": "US-TN-LEIPERSFORK",
  "US-SE-NOLA": "US-LA-COVINGTON",
  "US-SE-SANDERSVILLE": "US-SE-SANDERSVILLE",
  "US-SE-TAMPA": "US-FL-PLANTCTY",
  "US-SW-ALBQ": "US-NM-CORRALES",
  "US-SW-CLOUDCROFT": "US-SW-CLOUDCROFT",
  "US-SW-EL PASO": "US-TX-FABENS",
  "US-SW-LASCRUCES": "US-NM-HATCH",
  "US-SW-OKC": "US-OK-GUTHRIE",
  "US-SW-PHX": "US-AZ-QUEENCREEK",
  "US-SW-ROSWELL": "US-NM-ARTESIA",
  "US-SW-SANTA FE": "US-NM-CHIMAYO",
  "US-SW-TIMBERON": "US-SW-TIMBERON",
  "US-SW-TULAROSA": "US-NM-LALUZ",
  "US-UT-KAMASVALLEY": "US-UT-KAMASVALLEY",
  "US-W-ANCHORAGE": "US-AK-PALMER",
  "US-W-BEND": "US-OR-SISTERS",
  "US-W-BOULDER": "US-CO-LYONS",
  "US-W-HONOLULU": "US-HI-WAIALUA",
  "US-W-LA": "US-CA-FILLMORE",
  "US-W-PDX": "US-OR-SAUVIE",
  "US-W-RENO": "US-NV-FALLON",
  "US-W-SACRAMENTO": "US-CA-DIXON",
  "US-W-SD": "US-CA-JULIAN",
  "US-W-SEA": "US-WA-CARNATION",
  "US-W-SF": "US-CA-BOLINAS",
  "US-W-SPOKANE": "US-WA-GREENBLUFF",
  "US-W-VEGAS": "US-NV-MOAPA",
  "US-W-YAKIMA": "US-WA-TIETON",
  "US-WA-NEAHBAY": "US-WA-NEAHBAY"
};
/** @param {string} market */
function featuredFrontierFor(market){
  try{
    const fk = marketFeaturedFrontier[market]; if(!fk) return null;
    const d = featuredFrontierDetail[fk]; if(!d) return null;
    const items = d.items || [];
    return {frontier: fk, place: d.place, items: items, seasons: d.seasons, farmersMarket: d.farmersMarket,
      farms: d.farms || [], coops: d.coops || [],
      text: d.place + " — " + items.slice(0,3).join(", ") + " — " + d.seasons + " — " + d.farmersMarket};
  }catch(e){ return null; }
}
try{ window.featuredFrontierFor = featuredFrontierFor; }catch(e){}
// #257 mapping end

// #frontier-season start
// Month-aware frontier line: place + that month's in-season ingredient +
// a month-matching local moment, all from KODIAK_FRONTIER_PAIRS (curated pair
// data, never fabricated). Returns {place, ingredient, moment, text} or null
// when the pairs file is absent or the market/month has no entry. Only a
// moment whose months include the target month is named; confirmed moments
// win over proposed ones.
/** @type {Object<string, number>} */
/** @type {Object<string,number>} */
var FRONTIER_MONTH_NAMES = {january:1,february:2,march:3,april:4,may:5,june:6,
  july:7,august:8,september:9,october:10,november:11,december:12};
/**
 * @param {string} market
 * @param {string} monthKey
 * @returns {{place: string, ingredient: (string|null), moment: (string|null), momentStatus: (string|null), text: string}|null}
 */
function frontierSeasonLine(market, monthKey){
  try{
    var pairs = window.KODIAK_FRONTIER_PAIRS;
    if(!pairs || !pairs.length || !market || !monthKey) return null;
    /** @type {FrontierPair|null} */
    var entry = null;
    for(var i = 0; i < pairs.length; i++){
      if(pairs[i] && pairs[i].market === market){ entry = pairs[i]; break; }
    }
    if(!entry || !entry.frontier) return null;
    /** @type {number|null} */
    let monthNum = null;
    var m = String(monthKey).match(/(\d{4})-(\d{1,2})/);
    if(m){ monthNum = parseInt(m[2], 10); }
    else{
      var name = String(monthKey).replace(/^Season:\s*/i, '').trim().toLowerCase();
      if(FRONTIER_MONTH_NAMES[name]) monthNum = FRONTIER_MONTH_NAMES[name];
    }
    if(!monthNum) return null;
    const month = monthNum;
    var monthly = /** @type {Object<string, string>} */ (entry.monthly || {});
    var ingredient = null;
    Object.keys(monthly).forEach(function(k){
      var km = String(k).match(/-(\d{1,2})$/);
      if(km && parseInt(km[1], 10) === month) ingredient = monthly[k];
    });
    var moments = entry.moments || [];
    // teaching note (frontier assignments: assignment is what widens a read —
    // pick is null until the loop body below assigns it).
    /** @type {MomentEntry|null} */
    let pick = null;
    // for..of (not forEach): the pick assignment must sit in this function
    // body so control-flow sees it at the reads below — a forEach closure
    // assignment stays invisible and the reads narrow to null (never).
    for(const mo of moments){
      if(!mo || !mo.months || mo.months.indexOf(month) === -1) continue;
      if(!pick || (pick.status !== 'confirmed' && mo.status === 'confirmed')) pick = mo;
    }
    var place = (entry.frontier && entry.frontier.place) || '';
    if(!place && !ingredient) return null;
    var text = place;
    if(ingredient) text += ' — ' + ingredient + ' in season';
    if(pick && pick.moment) text += '; ' + pick.moment;
    return {place: place, ingredient: ingredient,
      moment: (pick && pick.moment) || null,
      momentStatus: (pick && pick.status) || null, text: text};
  }catch(e){ return null; }
}
try{ window.frontierSeasonLine = frontierSeasonLine; }catch(e){}
// #frontier-season end
const products = [
  {id:"power-cakes", name:"Kodiak Cakes Buttermilk Power Cakes", img:"", base:"1 cup mix + 2/3 cup milk + 1 egg"},
  {id:"protein-biscuits", name:"Kodiak Cakes Cheddar Jalapeno Drop Biscuits", img:"", base:"2 cups mix + cold butter + cheddar + jalapeno, drop bake 14 min"},
  {id:"savory-waffles", name:"Kodiak Cakes Savory Waffles — Regional", img:"", base:"1 cup mix + 2 eggs + milk + 1/2 cup cheese + 1/4 cup roasted peppers, waffle iron 3 min"},
  {id:"oatmeal-cup", name:"Kodiak Cakes Power Cups Protein Oatmeal Cup", img:"", base:"1 Power Cup + water, 5 min"},
  {id:"muffin", name:"Kodiak Cakes Chocolate Chip Muffins", img:"", base:"1 box Muffin Mix + 2 eggs + milk + oil"},
  {id:"waffle-icecream-sandwiches", name:"Kodiak Cakes Waffle Ice Cream Sandwiches", img:"", base:"Toast 2 Power Waffles, sandwich ice cream"}
];
const peppersList = ["Hatch green chile roasted, diced","Red chile","Jalapeño","Chipotle","Poblano","—"];
const cheesesList = ["Oaxaca crumble","Sharp cheddar","Pepper jack","Cotija","Oaxaca","Gruyère","Queso fresco","—"];

// page contract: #locality ships in markup before scripts run.
let localitySel = /** @type {HTMLSelectElement} */ (document.getElementById('locality'));
const productSel = /** @type {HTMLSelectElement|null} */ (document.getElementById('product')); // deprecated — now productChooser checkboxes
const peppersSel = /** @type {HTMLSelectElement|null} */ (document.getElementById('peppers')); // deprecated — now localFlavor derived
const cheesesSel = /** @type {HTMLSelectElement|null} */ (document.getElementById('cheeses'));
const audienceEl = /** @type {HTMLInputElement|null} */ (document.getElementById('audience')); // deprecated — now audienceSelect
const headlineEl = /** @type {HTMLInputElement|null} */ (document.getElementById('headline')); // deprecated — now campaignBrief
const channelSel = /** @type {HTMLSelectElement|null} */ (document.getElementById('channel'));
const campaignBriefEl = /** @type {HTMLTextAreaElement|null} */ (document.getElementById('campaignBrief'));
const previewEl = /** @type {HTMLElement} */ (document.getElementById('preview')); // page contract: #preview ships in markup
const fileNamesEl = /** @type {HTMLElement} */ (document.getElementById('fileNames')); // page contract: #fileNames ships in markup

/** @returns {void} */
function fillSelects(){
  // #213: #locality is declared in markup and present before this runs — no fallback path.
  localitySel = /** @type {HTMLSelectElement} */ (document.getElementById('locality'));
  const ls=localitySel;
  if(ls) {
    ls.innerHTML='';
    places.forEach(p=>{ const o=document.createElement('option'); o.value=p.market; o.textContent=`${p.place} — ${p.retailer.split(',')[0]}`; o.title=p.market; ls.appendChild(o); });
  }
  if(productSel){ try{ productSel.innerHTML=''; products.forEach(p=>{ const o=document.createElement('option'); o.value=p.id; o.textContent=p.name; productSel.appendChild(o); }); }catch(e){} }
  if(peppersSel){ try{ peppersSel.innerHTML=''; peppersList.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; peppersSel.appendChild(o); }); }catch(e){} }
  if(cheesesSel){ try{ cheesesSel.innerHTML=''; cheesesList.forEach(v=>{ const o=document.createElement('option'); o.value=v; o.textContent=v; cheesesSel.appendChild(o); }); }catch(e){} }
  try{ if(localitySel) localitySel.value="US-MW-PARKCITY-84098"; }catch(e){}
  try{ if(productSel) productSel.value="savory-waffles"; }catch(e){}
  try{ if(peppersSel) peppersSel.value="Hatch green chile roasted, diced"; }catch(e){}
  try{ if(cheesesSel) cheesesSel.value="Oaxaca crumble"; }catch(e){}
  try{ onLocality(); }catch(e){}
  try{ if(window.updateLocalFlavor) window.updateLocalFlavor(); }catch(e){}
  try{ if(typeof renderLangChips==='function') renderLangChips(); }catch(e){}
}
// teaching note (frontier calling conventions: one handler, two call shapes —
// the DOM passes an event, direct callers pass nothing).
// decision: two @overload lines, not one optional param — the listener shape
// accepts the Event the DOM always passes; the bare shape is ours.
/**
 * @overload
 * @returns {void}
 * @overload
 * @param {Event} _ev
 * @returns {void}
 * @param {Event} [_ev]
 * @returns {void}
 */
function onLocality(_ev){
  try{
    const cur = localitySel && localitySel.value ? localitySel.value : "US-MW-PARKCITY-84098";
    const p = places.find(x=>x.market===cur);
    if(!p) return;
    if(audienceEl) audienceEl.value=p.audience;
    if(headlineEl) headlineEl.value=p.message;
    if(peppersSel) peppersSel.value=p.peppers||"—";
    if(cheesesSel) cheesesSel.value=p.cheeses||"—";
    // also update new local flavor
    if(window.updateLocalFlavor) window.updateLocalFlavor();
  }catch(e){}
}
try{ const _ls=document.getElementById('locality'); if(_ls) _ls.addEventListener('change', onLocality); else if(localitySel) localitySel.addEventListener('change', onLocality); }catch(e){}
// also re-bind localitySel after fillSelects for auto-preview
try{ localitySel = /** @type {HTMLSelectElement} */ (document.getElementById('locality')) || localitySel; }catch(e){}
/** @type {Array<{canvas: HTMLCanvasElement, ratio: string, product: string}>} */
let canvases=[];
/** @returns {void} */
function render(){
  // robust defaults for prototype — Park City 84098 Keep It Wild, fallback if selects missing (fixes hidden #locality bug)
  /** @type {FarmEntry|null} */
  let prod = null;
  try{ prod = (productSel && productSel.value ? products.find(x=>x.id===productSel.value) : null) || null; }catch(e){}
  if(!prod) prod = products.find(x=>x.id==="savory-waffles") || products[0];
  let headline = "";
  try{ const _b = /** @type {HTMLTextAreaElement|null} */ (document.getElementById('campaignBrief')); const _src = (_b && _b.value.trim()) ? _b : headlineEl; headline = _src && _src.value ? _src.value.trim() : ""; }catch(e){}
  if(!headline){
    try{ const p = localitySel && localitySel.value ? places.find(x=>x.market===localitySel.value) : places.find(x=>x.market==="US-MW-PARKCITY-84098"); headline = p ? p.message : "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today\u0027s Frontier"; }catch(e){ headline = "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today\u0027s Frontier"; }
  }
  const needsMark = !headline.includes('®') || !headline.includes('KODIAK');
  // enforce brand marks preview hint (guard headlineEl deprecated -> campaignBrief)
  try{ const hlEl = headlineEl || document.getElementById('campaignBrief'); if(hlEl) hlEl.style.borderColor = needsMark ? '#E8530E' : '#D9CFC6'; }catch(e){}
  const ratios = [{k:"1x1",w:1080,h:1080},{k:"4x5",w:1080,h:1350},{k:"9x16",w:1080,h:1920},{k:"16x9",w:1920,h:1080}];
  previewEl.innerHTML="";
  canvases=[];
  const date = new Date().toISOString().slice(0,10).replace(/-/g,"");
  let _loc = null; try{ _loc = localitySel && localitySel.value ? places.find(x=>x.market===localitySel.value) : places.find(x=>x.market==="US-MW-PARKCITY-84098"); }catch(e){}
  if(!_loc) _loc = places.find(x=>x.market==="US-MW-PARKCITY-84098") || places[0];
  const localitySlug = _loc.place.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,28);
  let channel = "retailers"; try{ channel = channelSel && channelSel.value ? channelSel.value : "retailers"; }catch(e){} 
  /** @type {string[]} */
  const files=[];
  ratios.forEach(r=>{
    const tile=document.createElement('div'); tile.className='tile';
    const c=document.createElement('canvas'); c.width=r.w; c.height=r.h; c.style.maxWidth='100%'; c.style.height='auto';
    const ctx=/** @type {CanvasRenderingContext2D} */ (c.getContext('2d'));
    // parchment bg then brown box proxy hero (real image if loads)
    ctx.fillStyle=__kodiak.brand().parchment; ctx.fillRect(0,0,r.w,r.h);
    // Try to draw real hero image (offline file) - if fails, fallback to brown kraft with bear proxy
    /** @type {HTMLImageElement|null} */
    let img = new Image();
    // leak-teardown: #preview innerHTML is cleared on every re-render (~line 1048); null the handlers
    // after they fire so the closure (and the retained Image) releases when the old node is dropped.
    // #221: each draw is followed by a fonts-ready re-paint so brand webfonts swap in once loaded.
    img.onload = ()=>{ try{ drawAd(ctx, r.w, r.h, headline, prod, img); __kodiak.redrawOnFontsReady(ctx, r.w, r.h, headline, prod, img); }catch(e){} if(img){ img.onload=img.onerror=null; } img=null; };
    img.onerror = ()=>{ try{ drawAd(ctx, r.w, r.h, headline, prod, null); __kodiak.redrawOnFontsReady(ctx, r.w, r.h, headline, prod, null); }catch(e){} if(img){ img.onload=img.onerror=null; img=null; } };
    img.src = prod.img;
    tile.appendChild(c);
    const meta=document.createElement('div'); meta.className='meta';
    // S12 — localized caption per offline tile (EN source + market top_languages[]; offline shows honest pending)
    let _locCap=''; try{ if(typeof window.KODIAK_locCaption==='function') _locCap='<div class="small loc-cap-wrap">'+window.KODIAK_locCaption(_loc.market)+'</div>'; }catch(e){}
    meta.innerHTML=`<b>Kodiak Cakes ${prod.id} — ${r.k}</b><div class=small>${r.w}×${r.h}</div>`+_locCap;
    tile.appendChild(meta);
    previewEl.appendChild(tile);
    canvases.push({canvas:c,ratio:r.k,product:prod.id});
    const humanName=`KODIAK-CAKES-${prod.id}-US-NM-${localitySlug}-${channel}-${r.k}-${date}-v01.png`;
    files.push(humanName);
  });
  fileNamesEl.innerHTML = files.map(f=>`<span class=kbd>${f}</span>`).join(' ');
  // re-insert the platform-matrix explainer above the canvas tiles (render() cleared #preview above).
  try{ if(window.__renderPlatformMatrix) window.__renderPlatformMatrix(); }catch(e){}
  // preview is ready (offline canvas path) — reveal the Generate Campaign section (guarded no-op if absent)
  try{ if(typeof window.__kodiakRevealCampaign==='function') window.__kodiakRevealCampaign(); }catch(e){}
}
// #221 — canvas preview resolves colors + type from the brand layer.
// Colors read the Panda token layer (design/styles.css --colors-*) via computed
// CSS vars and fall back to the pre-token hex, so rendering stays pixel-compatible
// when tokens are unreadable (stylesheet not yet applied, non-DOM embed context).
// Type uses the brand stack from design/components.css — Gin 800 for slab/headline,
// museo-sans for body/UI. NOTE: Panda --fonts-headline/--fonts-body still name
// Rockwell/Inter (stale vs the brand), so the canvas reads the brand stacks directly
// instead of those two tokens; the stacks keep Rockwell/Georgia and system sans as
// canvas-safe fallbacks because canvas cannot synthesize the webfont before it loads.
const __kodiak = (()=>{
/** @type {Object<string,string>} */
  const FALLBACK = {
    parchment:'#FFF8F0',   // --colors-neutral-50
    kraftCover:'#3B2316',  // --colors-brand-bear-brown
    heroFallback:'#D9CFC6',// --colors-neutral-300
    ink:'#1A1110',         // --colors-neutral-900
    paper:'#FFFFFF',       // --colors-neutral-0
    muted:'#8C7A70',       // --colors-neutral-500
    blaze:'#E8530E',       // --colors-brand-blaze-orange
    scrim:'rgba(26,17,16,0.80)', // --colors-overlay-scrim (#1A1110CC == alpha .8)
  };
/** @type {Object<string,string>} */
  const VAR = {
    parchment:'--colors-neutral-50',
    kraftCover:'--colors-brand-bear-brown',
    heroFallback:'--colors-neutral-300',
    ink:'--colors-neutral-900',
    paper:'--colors-neutral-0',
    muted:'--colors-neutral-500',
    blaze:'--colors-brand-blaze-orange',
    scrim:'--colors-overlay-scrim',
  };
  /** @param {string} name @param {string} fallback @returns {string} */
  function cssVar(name, fallback){
    try{
      const v = getComputedStyle(document.documentElement).getPropertyValue(name);
      const t = (v||'').trim();
      return t || fallback;
    }catch(e){ return fallback; }
  }
  // Brand type stacks (design/components.css): Gin slab + museo-sans body.
  const HEADLINE_STACK = '"gin",Rockwell,Clarendon,Georgia,serif';
  const BODY_STACK = '"museo-sans",system-ui,Helvetica,Arial,sans-serif';
  /** @returns {Object<string,string>} */
  /** @returns {Object<string,string>} */
  function brand(){
    /** @type {Object<string,string>} */
    const out = {};
    for(const k of Object.keys(FALLBACK)) out[k] = cssVar(VAR[k], FALLBACK[k]);
    return out;
  }
  // Re-paint once brand webfonts arrive (Adobe Fonts zjt4wyq via index.html):
  // the first paint may measure/draw with the fallback stack; this swaps in
  // Gin/museo-sans when document.fonts is ready. Guarded no-op without the
  // Font Loading API; harmless if a later render already cleared the tile.
  /**
   * @param {CanvasRenderingContext2D} ctx
   * @param {number} W
   * @param {number} H
   * @param {string} headline
   * @param {FarmEntry|{id: string}|null} prod
   * @param {HTMLImageElement|null} heroImg
   * @returns {void}
   */
  function redrawOnFontsReady(ctx,W,H,headline,prod,heroImg){
    try{
      if(!document.fonts || !document.fonts.ready) return;
      try{
        if(typeof document.fonts.load==='function'){
          document.fonts.load('800 52px "gin"').catch(()=>{});
          document.fonts.load('500 12px "museo-sans"').catch(()=>{});
        }
      }catch(e){}
      document.fonts.ready.then(()=>{ try{ drawAd(ctx,W,H,headline,prod,heroImg); }catch(e){} }).catch(()=>{});
    }catch(e){}
  }
  return { brand, redrawOnFontsReady, HEADLINE_STACK, BODY_STACK };
})();
/**
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} W
 * @param {number} H
 * @param {string} headline
 * @param {FarmEntry|{id: string}|null} prod
 * @param {HTMLImageElement|null} heroImg
 * @returns {void}
 */
function drawAd(ctx,W,H,headline,prod,heroImg){
  const BC = __kodiak.brand();
  const HEAD = __kodiak.HEADLINE_STACK, BODY = __kodiak.BODY_STACK;
  // blurred cover emulation: brown kraft cover
  ctx.fillStyle=BC.kraftCover; ctx.fillRect(0,0,W,H);
  // hero contain at 8% down, ~82% width
  const scale = Math.min(W*0.82/400, H*0.58/400);
  const fw=400*scale, fh=400*scale, fx=(W-fw)/2, fy=H*0.08;
  if(heroImg){
    // contain mimic
    ctx.drawImage(heroImg, fx, fy, fw, fh);
  } else {
    ctx.fillStyle=BC.heroFallback; ctx.fillRect(fx,fy,fw,fh);
    ctx.fillStyle=BC.ink; ctx.font=`${Math.round(fw*0.08)}px ${HEAD}`; ctx.textAlign='center';
    ctx.fillText('KODIAK®', W/2, fy+fh*0.45);
    ctx.font=`12px ${BODY}`; ctx.fillText('KODIAK® — Nourishment for Today\'s Frontier', W/2, fy+fh*0.55);
  }
  // scrim band 32% at 68%
  const barTop=H*0.68; ctx.fillStyle=BC.scrim; ctx.fillRect(0,barTop,W,H-barTop);
  // headline — slab style, centered, 3-line clamp
  const pad=48, maxW=W-pad*2;
  ctx.fillStyle=BC.paper; ctx.textAlign='center';
  const size = W>=1920? 52 : W>=1080 && H>=1920? 46 : 38;
  ctx.font=`800 ${size}px ${HEAD}`;
  // wrap to 3 lines
  const words=headline.split(' '); let lines=[], cur="";
  for(const w of words){ const test=cur?cur+" "+w:w; if(ctx.measureText(test).width<=maxW) cur=test; else {lines.push(cur); cur=w; if(lines.length===2) break;} }
  if(cur) lines.push(cur); lines=lines.slice(0,3);
  let y=barTop+46;
  for(const line of lines){ ctx.fillText(line, W/2, y); y+= size*1.08; }
  // footer
  // NON-TOKEN: footer ink is neutral-50 at 85% alpha; no such alpha-variant token
  // exists, so it stays literal rather than inventing a one-off token read.
  ctx.font=`500 11px ${BODY}`; ctx.fillStyle='rgba(255,248,240,0.85)';
  ctx.fillText('KODIAK® • kodiakcakes.com • Keep It Wild  •  Nourishment for Today\'s Frontier', W/2, H-18);
  // orange bar
  ctx.fillStyle=BC.blaze; ctx.fillRect(0,H-8,W,8);
  // bear mark at 24,24 — KODIAK Bear silhouette lockup (brand compliant: Blaze Orange badge, Bear Brown bear)
  // per docs/kodiak-brand-explained.md: bear silhouette does visual lifting at 24,24
  ctx.save();
  ctx.fillStyle=BC.blaze; ctx.beginPath(); ctx.roundRect(24-4,24-4,36,36,8); ctx.fill();
  // bear silhouette path scaled to badge
  ctx.translate(24+14, 24+14);
  ctx.scale(1.2,1.2);
  ctx.fillStyle=BC.kraftCover;
  ctx.beginPath();
  ctx.moveTo(-6,-8); ctx.lineTo(-4,-10); ctx.lineTo(-2,-9); ctx.lineTo(0,-10); ctx.lineTo(2,-9); ctx.lineTo(4,-10); ctx.lineTo(6,-8);
  ctx.lineTo(7,-5); ctx.lineTo(5,-2); ctx.lineTo(4,4); ctx.lineTo(2,6); ctx.lineTo(-2,6); ctx.lineTo(-4,4); ctx.lineTo(-5,-2); ctx.lineTo(-7,-5);
  ctx.closePath(); ctx.fill();
  // eyes
  ctx.fillStyle=BC.parchment; ctx.beginPath(); ctx.arc(-2,-2,1,0,Math.PI*2); ctx.arc(2,-2,1,0,Math.PI*2); ctx.fill();
  ctx.restore();
  // KODIAK wordmark beside bear
  ctx.fillStyle=BC.kraftCover; ctx.font=`800 10px ${HEAD}`; ctx.textAlign='left'; ctx.fillText('KODIAK®', 24+40, 24+10);
  ctx.fillStyle=BC.muted; ctx.font=`600 7px ${BODY}`; ctx.fillText('Keep It Wild', 24+40, 24+20);
  ctx.fillStyle=BC.blaze; ctx.beginPath(); ctx.arc(24+18,24+18,14,0,Math.PI*2); ctx.fill();
  ctx.fillStyle=BC.kraftCover; ctx.font=`700 9px ${BODY}`; ctx.textAlign='center'; ctx.fillText('BEAR', 42, 46);
}

document.getElementById('renderBtn')?.addEventListener('click', render);
document.getElementById('downloadBrief')?.addEventListener('click', ()=>{
  const _pid = productSel && productSel.value ? productSel.value : "savory-waffles";
  const prod = products.find(x=>x.id===_pid) || products[0];
  const _mk = localitySel && localitySel.value ? localitySel.value : "US-MW-PARKCITY-84098";
  const place = places.find(x=>x.market===_mk) || places[0];
  const _aud = (audienceEl && audienceEl.value) || "";
  const _cb = campaignBriefEl && campaignBriefEl.value ? campaignBriefEl.value : "";
  const _head = _cb || ((headlineEl && headlineEl.value) || "");
  const yaml = `campaign_name: "KODIAK® ${place.place} — ${prod.name}"\nbrand: "KODIAK®"\ntarget_region: "${place.market.split('-')[0]}"\ntarget_market: "${place.market}"\ntarget_audience: "${_aud}"\ncampaign_message: "${_head.replace(/"/g,'\\"')}"\nlanguage: "en-US"\nbrand_colors: ["#3B2316", "#E8530E", "#1A3C34"]\nproducts:\n  - {id: ${prod.id}, name: "${prod.name}", description: "${prod.base}"}\n`;
  const blob=new Blob([yaml],{type:'text/yaml'}); const a=document.createElement('a'); const _u=URL.createObjectURL(blob); a.href=_u; a.download=`KODIAK-CAKES-${prod.id}-${place.market.toLowerCase()}-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-v01.yaml`; a.click(); setTimeout(()=>{ try{ URL.revokeObjectURL(_u); }catch(e){} }, 0);
});
document.getElementById('downloadAll')?.addEventListener('click', ()=>{
  canvases.forEach(({canvas,ratio,product})=>{
    const _mk2 = localitySel && localitySel.value ? localitySel.value : "US-MW-PARKCITY-84098";
    const place = places.find(x=>x.market===_mk2) || places[0];
    const _ch = channelSel && channelSel.value ? channelSel.value : "retailers";
    const localitySlug = place.place.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,28);
    const date = new Date().toISOString().slice(0,10).replace(/-/g,"");
    const name=`KODIAK-CAKES-${product}-US-NM-${localitySlug}-${_ch}-${ratio}-${date}-v01.png`;
    const a=document.createElement('a'); a.href=canvas.toDataURL('image/png'); a.download=name; a.click();
  });
});

// Location-aware: nearest market via haversine across all 72 markets (with coords) — fixes Tularosa NM bug where crude bbox defaulted to Park City
// teaching note (frontier coords: an intersection says AND, not OR — every
// row must be identifiable and located at once).
/** @typedef {Pick<PlaceEntry,'market'> & {lat: number, lon: number}} MarketCoord */
// decision: & not a union — a union would let a row drop its coords and
// nearestMarketForCoords would crash on m.lat.
/** @type {MarketCoord[]} */
const marketCoords = places.map(p=>({market:p.market, lat: (p.market.includes('SANJOSE')?37.3382 : p.market.includes('CASTROVILLE')?36.7656 : p.market==='US-W-SF'?37.7749 : p.market.includes('PESCADERO')?37.2534 : p.market.includes('NEAHBAY')?48.3647 : p.market.includes('PARKCITY')?40.6461 : p.market.includes('TULAROSA')?33.0581 : p.market.includes('LASCRUCES')?32.3199 : p.market.includes('TIMBERON')?32.6376 : p.market.includes('ALBQ')?35.0844 : p.market.includes('AUSTIN')?30.2672 : p.market.includes('MIAMI')?25.7617 : p.market.includes('CHI')?41.8781 : p.market.includes('BK')?40.6782 : 39.0), lon: (p.market.includes('SANJOSE')?-121.8863 : p.market.includes('CASTROVILLE')?-121.7588 : p.market==='US-W-SF'?-122.4194 : p.market.includes('PESCADERO')?-122.3806 : p.market.includes('NEAHBAY')?-124.6249 : p.market.includes('PARKCITY')?-111.4980 : p.market.includes('TULAROSA')?-106.0228 : p.market.includes('LASCRUCES')?-106.7637 : p.market.includes('TIMBERON')?-105.6947 : p.market.includes('ALBQ')?-106.6504 : p.market.includes('AUSTIN')?-97.7431 : p.market.includes('MIAMI')?-80.1918 : p.market.includes('CHI')?-87.6298 : p.market.includes('BK')?-73.9442 : -98.0)}));
/** @param {number} lat1 @param {number} lon1 @param {number} lat2 @param {number} lon2 @returns {number} */
function haversine(lat1,lon1,lat2,lon2){ const R=6371, toRad=/** @param {number} x @returns {number} */ (x)=>x*Math.PI/180, dLat=toRad(lat2-lat1), dLon=toRad(lon2-lon1), a=Math.sin(dLat/2)**2+Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)**2; return 2*R*Math.asin(Math.sqrt(a)); }
/** @param {number} lat @param {number} lon @returns {string} */
function nearestMarketForCoords(lat, lon){
  /** @type {string|null} */
  let best=null; let bestD=1e9;
  for(const m of marketCoords){
    const d=haversine(lat,lon,m.lat,m.lon);
    if(d<bestD){ bestD=d; best=m.market; }
  }
  return best || "US-SW-TULAROSA";
}
// #useLocationBtn / #showAllBtn / #locationStatus moved to details.html (frontier prototype context card) — handlers removed in lockstep

try{ if(typeof fillSelects==='function') fillSelects(); }catch(e){ console.warn('fillSelects', e); }
// Default preview hero (static #previewHero markup) owns the first impression — only
// fall back to the offline canvas render when no hero is present.
try{ if(!document.getElementById('previewHero') && typeof render==='function') render(); }catch(e){ console.warn('render', e); }
// Show images right away on load for Park City 84098 and nearby Kamas Valley (Peoa/Oakley) as demanded — not generic 6-piece template text
(() => {
  try {
    // Force initial preview for Park City and Kamas Valley side-by-side
    const preview = document.getElementById('preview');
    if(preview && preview.children.length===0){
      // Trigger render for Park City
      const sel=/** @type {HTMLSelectElement|null} */ (document.getElementById('locality'));
      if(sel){
        // First render Park City
        sel.value='US-MW-PARKCITY-84098';
        sel.dispatchEvent(new Event('change'));
        if(typeof onLocality==='function') onLocality();
        if(typeof render==='function') render();
        // After 300ms also show Kamas Valley dual prototype — draws second 3-ratio row with rural message + localFlavor
        setTimeout(()=>{
          try{
            const orig=sel.value;
            sel.value='US-UT-KAMASVALLEY';
            sel.dispatchEvent(new Event('change'));
            if(typeof onLocality==='function') onLocality();
            // Update localFlavor for Kamas explicitly
            try{ if(window.updateLocalFlavor) window.updateLocalFlavor(); }catch(e){}
            const vibe=document.createElement('div');
            vibe.id='kamas-vibe';
            vibe.innerHTML='<div class="kamas-vibe"><div class="kamas-vibe-title">Kamas Valley — The Vibe: Pure, quiet ranching country. Places like Peoa feature spectacular river valleys and single-family properties on massive acreage, but have strictly zero commercial retail or downtown stores.</div><div class="kamas-vibe-market">The Market: Bi-weekly Oakley Farmers Market at Oakley Rodeo Grounds + monthly Kamas Valley Market. Community Feel: Hyper-local assembly, not tourist trap — ranchers sell grass-fed meats directly to neighbors, backyard growers bring seasonal mountain produce, Summit County Arts Council free live acoustic. <b>For Park City use Target Kimball Junction / Walmart + Smiths; for Kamas drive DTC subscription + Amazon.com (no store).</b> — Preview below is Kamas Valley (Peoa) savory waffle with Oakley grass-fed sausage. Hero from <code>input_assets/power-cakes/hero.png</code> with CDN fallback.</div><div id="kamas-preview" class="preview kamas-preview"></div><div class="hint">Kamas Valley rural message: "Quiet ranch country — no store, no downtown, just river valley and a hot griddle. Kodiak Cakes savory waffle + Oakley grass-fed sausage — Nourishment for Today\'s Frontier" — localFlavor derived: Oakley grass-fed beef + Ballerina Farm butter year-round at Oakley Rodeo Grounds.</div></div>';
            const wrap=document.querySelector('.wrap');
            if(wrap) wrap.appendChild(vibe);
            // Draw Kamas 3-ratio preview immediately (reuse drawAd but with Kamas message & hero)
            try{
              const kamasProd = (typeof products!=='undefined' ? (products.find(p=>p.id==='savory-waffles')||products[0]) : null);
              const kamasMsg = sel.options[sel.selectedIndex]?.textContent?.includes('Kamas') ? (places.find(p=>p.market==='US-UT-KAMASVALLEY')?.message || "Quiet ranch country — no store, no downtown, just river valley and a hot griddle. Kodiak Cakes savory waffle + Oakley grass-fed sausage — Nourishment for Today\'s Frontier") : "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today\'s Frontier";
              const ratios = [{k:"1x1",w:1080,h:1080},{k:"9x16",w:1080,h:1920},{k:"16x9",w:1920,h:1080}];
              const kamasPreview=document.getElementById('kamas-preview');
              // CDN fallback hero — a real resolvable https url. only load an Image for a real
              // http(s) url; the input_assets/*.png stubs do not exist and would 404 to console.
              const cdnFallback="https://kodiakcakes.com/cdn/shop/files/Buttermilk_Power_Cakes_24oz_Front.png";
              const rawHero = (kamasProd && kamasProd.img) ? kamasProd.img : "";
              const isRealUrl = /** @param {unknown} u @returns {boolean} */ (u)=> typeof u==='string' && /^https?:\/\//.test(u) && u.indexOf('input_assets/')===-1;
              const heroSrc = isRealUrl(rawHero) ? rawHero : "";
              ratios.forEach(r=>{
                const tile=document.createElement('div'); tile.className='tile';
                const c=document.createElement('canvas'); c.width=r.w; c.height=r.h; c.style.maxWidth='100%'; c.style.height='auto';
                const ctx=/** @type {CanvasRenderingContext2D} */ (c.getContext('2d'));
                // no resolvable hero -> draw with no photo (paint null), NO Image(), NO 404.
                if(!heroSrc){
                  try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,null); }catch(e){}
                } else {
                  /** @type {HTMLImageElement|null} */
                  let img=new Image(); img.crossOrigin='anonymous';
                  // leak-teardown: null handlers after they fire so the closure + Image release on the next #preview clear.
                  img.onload=()=>{ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,img); }catch(e){} if(img){ img.onload=img.onerror=null; img=null; } };
                  img.onerror=()=>{ let fb=new Image(); fb.crossOrigin='anonymous'; fb.onload=()=>{ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,fb); }catch(e){ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,null); }catch(e2){} } fb.onload=fb.onerror=null; }; fb.onerror=()=>{ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,null); }catch(e){} fb.onload=fb.onerror=null; }; fb.src=cdnFallback; if(img){ img.onload=img.onerror=null; } img=null; };
                  img.src=heroSrc;
                }
                tile.appendChild(c);
                const meta=document.createElement('div'); meta.className='meta';
                meta.innerHTML=`<b>Kodiak Cakes ${kamasProd?kamasProd.id:'savory-waffles'} — ${r.k} — Kamas Valley rural</b><div class=small>${r.w}×${r.h}</div>`;
                tile.appendChild(meta);
                if(kamasPreview) kamasPreview.appendChild(tile);
              });
            }catch(e){ console.warn('kamas preview draw failed', e); }
            // restore to Park City for primary selector but keep both visible
            sel.value='US-MW-PARKCITY-84098';
            sel.dispatchEvent(new Event('change'));
            if(typeof onLocality==='function') onLocality();
            try{ if(window.updateLocalFlavor) window.updateLocalFlavor(); }catch(e){}
          }catch(e){ console.warn('kamas dual failed', e); }
        }, 420);
      }
    }
  } catch(e){ console.log('auto-preview failed', e); }
})();
// Consent-gated mock coordinates for ?mockLat&mockLon (#197).
// Headless/QA helper for the tap-to-locate path: coordinates are STASHED on window.__mockGeo
// and consumed ONLY by the explicit "My location" tap handler (market-disclosure.js). A clean
// load never resolves location and never touches #locality — the market dropdown
// (Park City default) is the default path. No geolocation of any kind runs until the user taps.
(() => {
  try{
    const params=new URLSearchParams(location.search);
    if(params.has('mockLat') && params.has('mockLon')){
      const lat=parseFloat(params.get('mockLat') || ''), lon=parseFloat(params.get('mockLon') || '');
      if(Number.isFinite(lat) && Number.isFinite(lon)){
        window.__mockGeo={lat, lon};
        const status=document.getElementById('locationStatus');
        if(status) status.textContent='Mocked coordinates staged — tap My location to apply.';
      }
    }
  }catch(e){}
})();

// === AXIS 2 + AXIS 3 — grouped market taxonomy (derived) + per-market localized-copy surface ===
// Self-contained: reuses the existing `places` array, `marketLangsOffline`/`marketLangsFor`, and the
// declared #locality <select> as the selection source of truth. The #marketDisclosure listbox was inert
// markup (never populated by any JS); this wires it as the real surface and mirrors selection into
// #locality so all downstream plumbing (onLocality/render/updateLocalFlavor) keeps working unchanged.
(function(){
  // page contract: #marketListbox ships in markup; callbacks below lose narrowing, so cast once here.
  const listbox = /** @type {HTMLElement} */ (document.getElementById('marketListbox'));
  const disclosure = /** @type {HTMLDetailsElement|null} */ (document.getElementById('marketDisclosure'));
  const btnLabel = /** @type {HTMLElement|null} */ (document.getElementById('marketButtonLabel'));
  const langLine = /** @type {HTMLElement|null} */ (document.getElementById('marketLangLine'));
  const featured = /** @type {HTMLElement|null} */ (document.getElementById('featuredFrontier'));
  const summary   = disclosure ? disclosure.querySelector('summary') : null;
  const filter = /** @type {HTMLInputElement|null} */ (document.getElementById('marketFilter'));
  if(!listbox || typeof places==='undefined') return;
  // #278 — type-ahead filter text; build() reads it from the closure so the
  // async frontier-gaps rebuild (no args) keeps the current filter.
  let filterText = '';
  /** @type {HTMLElement|null} */
  let activeOpt = null;

  // === S12 — live /localize gate ===
  // Flip localization from a permanent no-op to a real translate path on the HOSTED origin, while keeping
  // it OFF for file:// + localhost so the honest offline degrade (EN-source + single offline note) still
  // applies there. The renderer targets window.KODIAK_LOCALIZE_ENDPOINT via localizeText() below, which
  // carries a 6s AbortController timeout + .catch safety net — hosted origin attempts real translation and
  // degrades honestly to EN-source if /localize 403s or times out. NEVER fabricate translated text offline.
  if(!window.KODIAK_LOCALIZE_ENDPOINT){
    var _isLocal = (location.protocol==='file:') || ['127.0.0.1','localhost'].includes(location.hostname);
    if(!_isLocal) window.KODIAK_LOCALIZE_ENDPOINT = '/localize';
  }

  // --- frontier-gaps overlay (frontier:true markets). offline-tolerant multi-path fetch; overlay only. ---
  const frontierMarkets = new Set();
  (async ()=>{
    for(const url of ['data/localization/frontier-gaps.json','../../data/localization/frontier-gaps.json','./data/localization/frontier-gaps.json']){
      try{ const r=await fetch(url); if(r.ok){ const d=await r.json(); (d.gaps||[]).forEach(/** @param {{frontier?: unknown, market?: unknown}} g */ (g)=>{ if(g.frontier) frontierMarkets.add(g.market); }); build(); break; } }catch(e){}
    }
  })();

  // --- location_class DERIVED at render time (no data mutation, no new persisted field) ---
  // "market" when the retailer STRING names a chain grocer; else "featured-frontier"
  // (retail gap / general-store or farmers-market only / frontier:true from frontier-gaps).
  const CHAIN_GROCERS = /\b(target|walmart|smith'?s|costco|publix|h-?e-?b|keb|kroger|safeway|albertsons|whole foods|fred meyer|meijer|jewel-?osco|king soopers|hy-?vee|giant eagle|giant|stop & shop|hannaford|market basket|winco|raley'?s|vons|harris teeter|ingles|fry'?s|schnucks|piggly wiggly|rouses|acme|cub foods|pick 'n save|homeland|hornbacher'?s|winn-?dixie)\b/i;
  const GAP_ONLY = /general store|mercantile|farmers market|no commercial retail|no grocery|limited sku/i;
  /** @param {PlaceEntry} p @returns {'market'|'featured-frontier'} */
  function locationClass(p){
    if(frontierMarkets.has(p.market)) return 'featured-frontier';
    const r = p.retailer||'';
    if(GAP_ONLY.test(r) && !CHAIN_GROCERS.test(r)) return 'featured-frontier';
    if(CHAIN_GROCERS.test(r)) return 'market';
    return 'featured-frontier';
  }

  // --- derive a US state abbreviation for the sublabel + sort key ---
  /** @type {Object<string,string>} */
  const STATE_ABBR = {alabama:'AL',alaska:'AK',arizona:'AZ',arkansas:'AR',california:'CA',colorado:'CO',connecticut:'CT',delaware:'DE',florida:'FL',georgia:'GA',hawaii:'HI',idaho:'ID',illinois:'IL',indiana:'IN',iowa:'IA',kansas:'KS',kentucky:'KY',louisiana:'LA',maine:'ME',maryland:'MD',massachusetts:'MA',michigan:'MI',minnesota:'MN',mississippi:'MS',missouri:'MO',montana:'MT',nebraska:'NE',nevada:'NV','new hampshire':'NH','new jersey':'NJ','new mexico':'NM','new york':'NY','north carolina':'NC','north dakota':'ND',ohio:'OH',oklahoma:'OK',oregon:'OR',pennsylvania:'PA','rhode island':'RI','south carolina':'SC','south dakota':'SD',tennessee:'TN',texas:'TX',utah:'UT',vermont:'VT',virginia:'VA',washington:'WA','west virginia':'WV',wisconsin:'WI',wyoming:'WY'};
  const ABBR_SET = new Set(Object.values(STATE_ABBR));
  // teaching note (frontier every-path returns: the contract says string, so the
  // fallthrough return '' is the missing else — without it the fallthrough is undefined).
  /** @param {PlaceEntry} p @returns {string} */
  function stateOf(p){
    const place = p.place||'';
    // explicit "City, ST" two-letter token
    const m2 = place.match(/,\s*([A-Z]{2})\b/);
    if(m2 && ABBR_SET.has(m2[1])) return m2[1];
    // full state name anywhere in the place string
    const low = place.toLowerCase();
    for(const name in STATE_ABBR){ if(low.includes(name)) return STATE_ABBR[name]; }
    // fall back to zip-based? none reliable — use region segment
    return '';
  }
  // short display name for the button + option label
  /** @param {PlaceEntry} p @returns {string} */
  function shortName(p){ return (p.place||p.market).split(/\s+—\s+/)[0].replace(/\s*\(.*/,'').trim() || p.market; }

  // --- build the two-group listbox (Axis 2) ---
  /** @type {Object<string,string>} */
  const CLASS_LABEL = {'market':'Market','featured-frontier':'Featured Frontier'};
  // #278 — substring match over short name + place + market id + zip + state.
  // Every whitespace-separated token must match somewhere ("san 94060" works).
  /** @param {PlaceEntry} p @returns {boolean} */
  function matchesFilter(p){
    const q = (filterText||'').trim().toLowerCase();
    if(!q) return true;
    const hay = (shortName(p)+' '+(p.place||'')+' '+p.market+' '+(p.zip||'')+' '+stateOf(p)).toLowerCase();
    return q.split(/\s+/).every(tok=>hay.indexOf(tok)!==-1);
  }
  function build(){
    // teaching note (frontier never: [] infers never[] — the empty literal means
    // no value possible until the annotation widens it; push proved it).
    /** @type {Object<string, PlaceEntry[]>} */
    const groups = {'market':[], 'featured-frontier':[]};
    places.forEach(/** @param {PlaceEntry} p */ (p)=>{ if(matchesFilter(p)) groups[locationClass(p)].push(p); });
    activeOpt = null; listbox.removeAttribute('aria-activedescendant');
    const cmp = /** @param {PlaceEntry} a @param {PlaceEntry} b @returns {number} */ (a,b)=>{ const sa=stateOf(a), sb=stateOf(b); if(sa!==sb) return sa<sb?-1:1; const na=shortName(a).toLowerCase(), nb=shortName(b).toLowerCase(); return na<nb?-1:na>nb?1:0; };
    groups.market.sort(cmp); groups['featured-frontier'].sort(cmp);
    listbox.innerHTML='';
    ['market','featured-frontier'].forEach(cls=>{
      const rows = groups[cls]; if(!rows.length) return;
      const gid = 'ffgrp-'+cls;
      const head = document.createElement('div'); head.id=gid; head.setAttribute('role','presentation');
      head.style.cssText='padding:6px 10px 2px;font:700 10px/1.2 "kodiak_sans","museo-sans",sans-serif;letter-spacing:.07em;text-transform:uppercase;color:var(--colors-foreground-muted)';
      head.textContent = CLASS_LABEL[cls]+'s';
      listbox.appendChild(head);
      const grp = document.createElement('div'); grp.setAttribute('role','group'); grp.setAttribute('aria-labelledby',gid);
      rows.forEach(/** @param {PlaceEntry} p */ (p)=>{
        const opt=document.createElement('div');
        opt.setAttribute('role','option'); opt.id='ffopt-'+p.market; opt.dataset.market=p.market;
        opt.setAttribute('aria-selected','false'); opt.tabIndex=-1;
        const st=stateOf(p); const sub=CLASS_LABEL[cls]+(st?' — '+st:'');
        opt.innerHTML='<span class="ff-opt-name">'+esc(shortName(p))+'</span><span class="ff-opt-sub">'+esc(sub)+'</span>';
        opt.addEventListener('click',()=>select(p.market));
        grp.appendChild(opt);
      });
      listbox.appendChild(grp);
    });
    // #278 — honest empty state; selection stays on the previous market.
    if(!groups.market.length && !groups['featured-frontier'].length){
      const empty = document.createElement('div');
      empty.className = 'ff-market-empty'; empty.setAttribute('role','presentation');
      empty.textContent = 'No markets match "'+filterText.trim()+'" — clear the filter to see all '+places.length+'.';
      listbox.appendChild(empty);
    }
    // reflect whatever #locality currently holds
    const cur = /** @type {HTMLSelectElement|null} */ (document.getElementById('locality'))?.value; if(cur) markSelected(cur);
  }

  // #278 — filter wiring + keyboard nav. Selection still flows through select()
  // so snapshot/persist/brief plumbing is untouched.
  /** @returns {HTMLElement[]} */
  function visibleOpts(){ return Array.prototype.slice.call(listbox.querySelectorAll('[role="option"]')); }
  // teaching note (frontier signatures: names are positional, never nominal —
  // the signature says el, callers pass o and opts[i], and only count/order/types must line up).
  /** @param {HTMLElement|null} el @returns {void} */
  function setActive(el){
    visibleOpts().forEach(o=>o.classList.remove('is-active'));
    activeOpt = el || null;
    if(activeOpt){ activeOpt.classList.add('is-active'); listbox.setAttribute('aria-activedescendant', activeOpt.id); }
    else listbox.removeAttribute('aria-activedescendant');
  }
  /** @param {number} dir @returns {void} */
  function moveActive(dir){
    const opts = visibleOpts(); if(!opts.length) return;
    let i = activeOpt ? opts.indexOf(activeOpt) : -1;
    i = (i===-1) ? (dir>0 ? 0 : opts.length-1) : (i+dir+opts.length)%opts.length;
    setActive(opts[i]);
    try{ opts[i].scrollIntoView({block:'nearest'}); }catch(e){}
  }
  if(filter){
    filter.addEventListener('input', ()=>{ filterText = filter.value; build(); });
    // teaching note (frontier handlers: this is the element the listener was
    // bound to — rebind it elsewhere and this.value reads the wrong control).
    // decision: @this {HTMLInputElement} lets the handler read this.value
    // instead of the closed-over filter; the Escape branch proves it.
    filter.addEventListener('keydown', /** @this {HTMLInputElement} @param {KeyboardEvent} e @returns {void} */ function(e){
      if(e.key==='ArrowDown'){ e.preventDefault(); moveActive(1); }
      else if(e.key==='ArrowUp'){ e.preventDefault(); moveActive(-1); }
      else if(e.key==='Enter'){ if(activeOpt){ e.preventDefault(); activeOpt.click(); } }
      else if(e.key==='Escape'){ this.value=''; filterText=''; build(); if(disclosure) disclosure.open=false; }
    });
    // option clicks keep mouse behavior; hover claims the active slot.
    // teaching note (frontier instanceof: the check replaces the cast — e.target
    // is EventTarget|null until instanceof proves Element; a non-element target
    // now yields null instead of a lying cast).
    // decision: instanceof Element, not HTMLElement — closest lives on Element,
    // so SVG option content keeps working; the HTMLElement cast stays only where
    // setActive demands it.
    listbox.addEventListener('mouseover', (e)=>{ const t=e.target instanceof Element ? e.target : null; const o=(t && t.closest) ? /** @type {HTMLElement} */ (t.closest('[role="option"]')) : null; if(o) setActive(o); });
  }
  // opening the disclosure lands focus in the filter so typing filters immediately.
  if(disclosure) disclosure.addEventListener('toggle', ()=>{ if(disclosure.open && filter){ try{ filter.focus(); }catch(e){} } });
  /** @param {unknown} s @returns {string} */
  /** @param {unknown} s @returns {string} */
  function esc(s){
    /** @type {Record<string,string>} */
    const ENT = {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'};
    return String(s==null?'':s).replace(/[&<>"']/g, (c)=>ENT[c]);
  }

  /** @param {string} market @returns {void} */
  function markSelected(market){
    listbox.querySelectorAll('[role="option"]').forEach(o=>o.setAttribute('aria-selected', /** @type {HTMLElement} */ (o).dataset.market===market?'true':'false'));
  }

  // --- selection: mirror into the declared #locality select (the existing source of truth) ---
  /** @param {string} market @returns {void} */
  function select(market){
    // teaching note (frontier control flow: the early return is the narrowing —
    // past this line p is PlaceEntry, no guards needed below).
    const p = places.find(x=>x.market===market); if(!p) return;
    const loc = /** @type {HTMLSelectElement|null} */ (document.getElementById('locality'));
    // bubbles:true — the document-level change listeners (market-disclosure
    // reflectMarket + brief footer + market source line, autocomplete suffix)
    // observe listbox-driven changes through this event. Without bubbles the
    // dropdown relabels itself but all derived state stays on the previous
    // market (#213).
    if(loc){ loc.value=market; loc.dispatchEvent(new Event('change', {bubbles:true})); }
    if(typeof onLocality==='function') try{ onLocality(); }catch(e){}
    markSelected(market);
    if(btnLabel) btnLabel.textContent = shortName(p);
    if(summary) summary.setAttribute('aria-label','Market — currently '+shortName(p));
    renderMarketLangs(market);
    if(disclosure) disclosure.open=false;
    if(summary) summary.setAttribute('aria-expanded','false');
  }

  // === AXIS 3 — translation render surface (surface only; content STUBBED, blocked on backend #124) ===
  // renderMarketLangs replaces the old renderLangChips no-op behaviour: on market selection it reads the
  // selected market's top languages from market-languages.json (via marketLangsFor) and paints .loc-line rows.
  //
  // BLOCKER: no precomputed market x lang -> {text,provider} JSON exists in the repo (localize() is a backend
  // python service). So this renders PLACEHOLDERS, never fabricated machine translations:
  //   - English source line       -> data-provider="source" (real English source string from places[].message)
  //   - machine-translatable       -> data-provider="pending"            (placeholder "translation pending")
  //   - community-review (nv/zip)  -> data-provider="community-review"   (FIRST-CLASS row + visible review badge)
  //
  // COMMUNITY-REVIEW LANGUAGES (nv/zip): these are low-resource Indigenous languages under community sovereignty.
  // They are SUPPORTED and VISIBLE — never machine-translated, never hidden or dimmed into an apology. The row
  // renders full-strength with the English source they'd be translated from and a respectful badge explaining WHY
  // (community-authorized translation, not machine). SOURCE OF TRUTH is the DATA flag machine_translate:false in
  // market-languages.json; the HUMAN_REQUIRED set below is a defense-in-depth fallback if that flag is ever absent.
  //
  // #124 populates window.KODIAK_LOCALIZED_COPY = { "<market>": { "<translate_code>": {text, provider} } }.
  // When that object exists, real text swaps in for the placeholder with NO structural change. For a
  // community-review language the authorized copy is presented as data-provider="community-authorized" with a
  // "community-authorized" badge — it is NEVER relabeled as "machine", regardless of what provider the data claims.
  const HUMAN_REQUIRED = new Set(['nv','zip']); // Navajo, Zapotec — fallback safety net; DATA flag is primary (#123)

  // primary source of truth: the market-languages.json entry says machine_translate:false.
  // returns true if this language must not be machine-translated (data flag OR fallback set).
  /** @param {MarketLang} l @param {string} code @returns {boolean} */
  function isCommunityReview(l, code){
    if(l && l.machine_translate === false) return true;   // DATA is authoritative
    return HUMAN_REQUIRED.has(code);                        // defense-in-depth fallback
  }

  // === S12 — live translate helper (single source of truth for the /localize path) ===
  // POSTs {text, market, target_lang} to window.KODIAK_LOCALIZE_ENDPOINT and returns the translated string,
  // or null on ANY failure (endpoint off, 403, timeout, malformed response). Callers degrade to EN-source
  // when this returns null — translated text is NEVER fabricated. 6s AbortController timeout is the safety net.
  // NEVER call this for community-review languages (nv/zip machine_translate:false) — that path stays human-only.
  // teaching note (frontier generics: Map<string,string> instantiates both slots —
  // set() rejects non-strings, get() returns string|undefined, so the hit path coalesces to null).
  /** @type {Map<string,string>} */
  const _locCache = new Map(); // key: market|code|text  -> translated string (dedupe repeat renders)
  /** @param {string} text @param {string} market @param {string} code @returns {Promise<string|null>} */
  function localizeText(text, market, code){
    const ep = window.KODIAK_LOCALIZE_ENDPOINT;
    if(!ep) return Promise.resolve(null);                   // offline / file:// / localhost — honest degrade
    const key = market+'|'+code+'|'+text;
    if(_locCache.has(key)) return Promise.resolve(_locCache.get(key) ?? null);
    const controller = new AbortController();
    const timer = setTimeout(()=>controller.abort(), 6000); // 6s timeout — degrade if backend is slow/unreachable
    return fetch(ep, {method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({text, market, target_lang: code}), signal: controller.signal})
      .then(r=>{ if(!r.ok) throw new Error('localize HTTP '+r.status); return r.json(); })
      .then(j=>{ const t=(j && (j.text || j.translated || j.translation)); const out=(typeof t==='string' && t.trim())?t:null; if(out) _locCache.set(key, out); return out; })
      .catch(()=>null)                                       // 403 / timeout / offline -> null -> EN-source degrade
      .finally(()=>clearTimeout(timer));
  }
  window.KODIAK_localizeText = localizeText;                 // reuse from tile-caption renderers in other scopes
  window.KODIAK_isCommunityReview = isCommunityReview;
  window.KODIAK_marketLangsFor = marketLangsFor;             // #241: campaign copy panel lists the same top langs

  // Standalone #locPreview headlines retired 2026-09-08 (cleanup order): translated copy
  // lives only in the preview tile captions. renderMarketLangs now updates the language-names
  // line + the featured framing only — no headline rows, no host, no live jobs.
  /** @param {string} market @returns {void} */
  function renderMarketLangs(market){
    const p = places.find(x=>x.market===market);
    const langs = (typeof marketLangsFor==='function') ? marketLangsFor(market) : [];

    // update #marketLangLine to reflect this market's REAL top languages (Axis 3 requirement)
    if(langLine){
      const names = langs.map(l=>l.lang_name).filter(Boolean);
      // English is inferred (source language) — list only the generated others.
      langLine.innerHTML = 'localized in languages: <b>'+esc(names.length ? names.join(', ') : 'English')+'</b>';
    }

    // === S12 — #featuredFrontier: FRAMING CONTEXT ONLY ===
    // featuredFrontier carries framing only: a tight contextual lead, the market/place + scene cue,
    // and the localized-reach summary (language names, never translated copy — that lives only in
    // the preview tile captions since the 2026-09-08 cleanup). aria-live=polite is preserved.
    if(featured){
      const placeName = (p && (p.place || p.market)) ? (p.place || p.market) : market;
      const scene = (p && p.cue) ? p.cue : '';
      const names = langs.map(l=>l.lang_name).filter(Boolean);
      const reach = esc(names.length ? names.join(', ') : 'English');
      const sceneHtml = scene ? '<span class="ff-cue">'+esc(scene)+'</span>' : '';
      // Rural-counterpart display retired: the caption names this market only.
      // (featuredFrontierFor data still feeds the backend nearest-frontier hint.)
      featured.innerHTML =
        '<span class="ff-context-lead">This campaign, localized for</span> '+
        '<span class="ff-place">'+esc(placeName)+'</span>'+
        sceneHtml+
        '<span class="ff-reach">localized reach: '+reach+'</span>';
    }

    // (standalone rows retired — no live jobs; tile captions run their own.)
  }

  // === S12 — compact localized tile caption (Task 3) ===
  // Returns compact .loc-line HTML for a tile caption: EN source + this market's top_languages[]. Reuses the
  // SAME source-of-truth (places[].message, marketLangsFor) and the SAME live/community/offline rules as the
  // full preview, kept compact for a tile. Live machine rows swap real /localize text in after paint (via the
  // uniqueId row + a microtask), community-review stays human-only, offline shows a single honest pending note.
  // Exposed globally so showRenderSet (hosted) and the offline canvas render() can both call it.
  let _capSeq = 0;
  /** @param {string} market @returns {string} */
  function locCaptionHtml(market){
    const p = places.find(x=>x.market===market);
    let source = (p && p.message) ? p.message : "Kodiak Cakes — Nourishment for Today's Frontier";
    // KODIAK-forbidden-in-copy law: backend/seed strings predate the law — clean at paint time.
    try{ if(typeof window.KODIAK_brandClean==='function') source = window.KODIAK_brandClean(source); }catch(e){}
    const langs = (typeof marketLangsFor==='function') ? marketLangsFor(market) : [];
    const seq = ++_capSeq;
    /** @type {Array<{rowId: string, code: string, source: string, market: string}>} */
    const jobs = [];
    const rows = ['<span class="loc-line" lang="en" data-provider="source"><span class="loc-langtag">EN</span><span class="loc-txt">'+esc(source)+'</span></span>'];
    langs.forEach((l,i)=>{
      const code = (l.translate_code||l.lang_code||'').toLowerCase();
      const community = isCommunityReview(l, code);
      const note = l.review_note || 'Community-authorized translation required — not machine-generated (language sovereignty).';
      const rowId = 'loccap-'+seq+'-'+code+'-'+i;
      /** @type {CaptionProvider} */
      let provider;
      let fill, badge='';
      if(community){
        provider='community-review'; fill=source;          // never machine-translated — EN source + badge, full-strength
        badge='<span class="loc-review" title="'+esc(note)+'">community review</span>';
      } else if(window.KODIAK_LOCALIZE_ENDPOINT){
        provider='pending-live'; fill=source; jobs.push({rowId, code, source, market});
      } else {
        provider='pending'; fill='translation pending';    // offline honest state
      }
      rows.push('<span class="loc-line" id="'+esc(rowId)+'" lang="'+esc(l.lang_code||code)+'" data-provider="'+esc(provider)+'">'+
                '<span class="loc-langtag">'+esc((l.lang_code||code).toUpperCase())+'</span>'+
                '<span class="loc-txt">'+esc(fill)+'</span>'+badge+'</span>');
    });
    // fire the live translations on the next tick (after the caller has inserted this HTML into the DOM)
    if(jobs.length) setTimeout(()=>{ jobs.forEach(job=>{
      localizeText(job.source, job.market, job.code).then(t=>{
        // KODIAK-forbidden-in-copy law: brand mark only, never reword the translation.
        try{ if(typeof window.KODIAK_brandClean==='function' && typeof t==='string') t = window.KODIAK_brandClean(t); }catch(e){}
        const row=document.getElementById(job.rowId); if(!row||!t) return;   // null -> EN-source stays (honest)
        const txt=row.querySelector('.loc-txt'); if(txt) txt.textContent=t;
        row.setAttribute('data-provider','machine-live');
      });
    }); }, 0);
    return '<span class="loc-cap">'+rows.join('')+'</span>';
  }
  window.KODIAK_locCaption = locCaptionHtml;

  // Replace the legacy renderLangChips no-op so any caller (fillSelects, change listener, fetch upgrade)
  // now repaints the localized surface for the current market instead of deleting #lang-chips.
  try{
    window.renderLangChips = function(){
      const cur = /** @type {HTMLSelectElement|null} */ (document.getElementById('locality'))?.value || 'US-MW-PARKCITY-84098';
      renderMarketLangs(cur);
    };
  }catch(e){}

  // initial build + paint for the default market
  build();
  renderMarketLangs(/** @type {HTMLSelectElement|null} */ (document.getElementById('locality'))?.value || 'US-MW-PARKCITY-84098');
})();
