// Market languages — top 2 outside English per market (ACS 2022), auto-produced as EN + localized variants. Proven via Nova (unlimited budget) (Amazon Translate + Nova Micro)
const marketLangsOffline = {
  "US-SW-EL PASO": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":62},{"lang_code":"de","lang_name":"German","translate_code":"de","pct_home":0.6}],
  "US-NE-BURLINGTON": [{"lang_code":"fr","lang_name":"French","translate_code":"fr","pct_home":3.2},{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":2.1}],
  "US-NE-BOS": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":9},{"lang_code":"pt","lang_name":"Portuguese","translate_code":"pt","pct_home":2.5}],
  "US-W-SF": [{"lang_code":"es","lang_name":"Spanish","translate_code":"es","pct_home":12},{"lang_code":"zh","lang_name":"Chinese","translate_code":"zh","pct_home":6}],
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
// City real top_languages are es + de. NEVER seed community-review languages (nv/zip) — those stay human-only.
window.KODIAK_LOCALIZED_COPY = window.KODIAK_LOCALIZED_COPY || {};
if(!window.KODIAK_LOCALIZED_COPY["US-MW-PARKCITY-84098"]){
  window.KODIAK_LOCALIZED_COPY["US-MW-PARKCITY-84098"] = {
    "es": {text:"Mantente Salvaje — cereales integrales ricos en proteína para tu frontera Wasatch. Nutrición para la Frontera de Hoy", provider:"seed"},
    "de": {text:"Bleib wild — proteinreiche Vollkornprodukte für deine Wasatch-Frontier. Nahrung für die Frontier von heute", provider:"seed"}
  };
}
/** @param {string} code @returns {Array<{lang_code:string,lang_name:string,translate_code:string,pct_home:number,machine_translate?:boolean,review?:string,review_note?:string}>} */
function marketLangsFor(code){ return (marketLangsOffline[code] || marketLangsOffline._default || []).filter(Boolean); }
/** @param {void} @returns {void} */
function renderLangChips(){
  // declutter — lang-chips removed from the app page (non-interactive, hardcoded markets).
  // kept as a safe no-op so fillSelects/change-listener/setTimeout/async-fetch callers never throw.
  const el=document.getElementById('lang-chips');
  if(el && el.parentNode) el.parentNode.removeChild(el);
}
document.addEventListener('change', e=>{ if(e.target && e.target.id==='locality') renderLangChips(); });
// also fetch full 73-market file when online to upgrade offline seed — try multiple paths for local http.server 8099 vs S3
(async()=>{ for(const url of ['data/localization/market-languages.json','../../data/localization/market-languages.json','./data/localization/market-languages.json']){ try{ const r=await fetch(url); if(r.ok){ const d=await r.json(); if(d.markets){ d.markets.forEach(m=>{ if(m.top_languages) marketLangsOffline[m.market]=m.top_languages.map(t=>({...t, translate_code: t.translate_code||t.lang_code, pct_home: (t.pct_home!=null?t.pct_home:t.pct)})); }); console.log('[langs] loaded',d.markets.length,'from',url); renderLangChips(); break; } } }catch(e){} }})();
// Inline data — so this page is truly offline (no fetch to a server). Keep a small seed of hundreds-scale places and recipes here; full tables live at ../../data/
const places = [
  {market:"US-MW-PARKCITY-84098", place:"Park City, Utah 84098", retailer:"Target (Kimball Junction), Walmart (Kimball Junction), Smith's Food & Drug (Park City)", zip:"84098", audience:"Mountain families, Wasatch trail households, resort staff — Aaron", message:"Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Farmers Market at Park City Mountain Resort Wed 11-5 — Jensen Farms peaches, Copper Moose rhubarb, Tagges preserves, Bal"},
    {market:"US-UT-KAMASVALLEY", place:"Kamas Valley — Peoa / Oakley, UT 84036 (Wasatch Back rural)", retailer:"Oakley Farmers Market (Rodeo Grounds) + Kamas Valley Market — no commercial retail", zip:"84036", audience:"Peoa ranch families on acreage, Oakley rodeo neighbors, Kamas backyard growers — ranch assembly", message:"Quiet ranch country — no store, no downtown, just river valley and a hot griddle. Kodiak savory waffle + Oakley grass-fed sausage — Nourishment for Today''s Frontier", peppers:"—", cheeses:"—", cue:"Peoa river valley at dawn, Oakley Rodeo Grounds folding tables of grass-fed meats, Kodiak on tailgate with mountain greens, acoustic guitar"},
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
  {market:"US-W-SEA", place:"Seattle, Washington", retailer:"Costco (home — Seattle/SODO/Issaquah warehouses), Target, Amazon Subscribe & Save", zip:"98101", audience:"Seattle Costco bulk shoppers — Cory", message:"Evergreen frontier — protein-packed whole grains for gray mornings — bulk Costco + urban frontier awareness", peppers:"—", cheeses:"—", cue:"Coffee beside KODIAK® flapjacks, evergreen, rain-morning griddle, bulk Costco Family Size — and Neah Bay frontier repres"},
  {market:"US-W-PDX", place:"Portland, Oregon", retailer:"Target, Fred Meyer", zip:"97201", audience:"Trail families, forest — Aaron", message:"Forest trail fuel — protein for your cubs", peppers:"—", cheeses:"—", cue:"Berries and hazelnut beside Bear Bites"},
  {market:"US-W-LA", place:"Los Angeles, California", retailer:"Target, Whole Foods", zip:"90001", audience:"Active, ingredient-aware, diverse — Madison", message:"Fuel your trail — protein oatmeal for today's frontier", peppers:"—", cheeses:"—", cue:"Almond milk pour, trail cup on overlook"},
  {market:"US-SE-NASH", place:"Nashville, Tennessee", retailer:"Publix, Target", zip:"37201", audience:"Music city families, biscuit country — Eli", message:"Honey frontier — protein for your Nashville morning", peppers:"—", cheeses:"—", cue:"Honey beside graham Bear Bites"},
  {market:"US-SE-LOU", place:"Louisville, Kentucky", retailer:"Target, Kroger", zip:"40202", audience:"Derby families, bourbon-maple adjacency — Sarah", message:"Brown sugar frontier — protein for your Kentucky morning", peppers:"—", cheeses:"—", cue:"Maple and brown sugar oatmeal"},
  {market:"US-NE-BOS", place:"Boston + Portland ME, New England", retailer:"Target, Market Basket", zip:"02108", audience:"Leaf-peep families, maple country — Emily", message:"Maple frontier — 14 grams, whole grain, New England", peppers:"—", cheeses:"—", cue:"Pure maple syrup over Power Cakes"},
  {market:"US-SW-PHX", place:"Phoenix, Arizona", retailer:"Target, Walmart, Fry's", zip:"85001", audience:"Desert families, early hot mornings — Elizabeth", message:"Desert frontier — protein that holds up in the heat", peppers:"—", cheeses:"—", cue:"Prickly pear and citrus"},
  {market:"US-NE-NYC", place:"Brooklyn + Manhattan, New York", retailer:"Target, Whole Foods", zip:"11201", audience:"City-active, bodega-adjacent — Nina", message:"City frontier — protein-packed whole grains for the hustle", peppers:"—", cheeses:"—", cue:"Bodega coffee, oatmeal cup on subway platform"},
  {market:"US-SW-TIMBERON", place:"Timberon, New Mexico", retailer:"Timberon General Store, Cloudcroft Mercantile, Alamogordo Walmart", zip:"88350", audience:"Piñon harvest families, Sacramento Mountains homesteaders, h — Brett", message:"Piñon frontier — protein with piñon seeds from pinonnuts.com", peppers:"—", cheeses:"—", cue:"Piñon pines, Sacramento Mountains, enamel mug on piñon harvest table, Timberon pines"},
  {market:"US-MW-WASATCH-SLC", place:"Salt Lake City, Utah", retailer:"Target, Walmart, Smith's", zip:"84101", audience:"Ski families, Wasatch trailheads — Arnoldo", message:"Wasatch fuel — 14g for slope mornings", peppers:"—", cheeses:"—", cue:"Snow-capped Wasatch, ski lodge flapjacks"},
  {market:"US-W-SF", place:"San Francisco Bay Area, California", retailer:"Target, Whole Foods, Safeway", zip:"94102", audience:"Tech families, fog-morning hikers — Sam", message:"Bay frontier — whole grains for bridge mornings", peppers:"—", cheeses:"—", cue:"Golden Gate fog, sourdough-adjacent stack"},
  {market:"US-W-SD", place:"San Diego, California", retailer:"Target, Vons, Whole Foods", zip:"92101", audience:"Surf families, canyon trail runners — Amber", message:"Surf frontier — protein for wave mornings", peppers:"—", cheeses:"—", cue:"Surfboard wax and maple, coastal stack"},
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
  {market:"US-W-ANCHORAGE", place:"Anchorage, Alaska", retailer:"Target, Fred Meyer, Costco", zip:"99501", audience:"Grizzly country families, frontier cabins — Sarah", message:"Last frontier — Keep It Wild Kodiak stack", peppers:"—", cheeses:"—", cue:"Denali light, grizzly corridor, cabin"},
  {market:"US-W-HONOLULU", place:"Honolulu, Hawaii", retailer:"Target, Costco, Safeway", zip:"96813", audience:"Island families, surf-and-trail — Emily", message:"Island frontier — protein for island mornings", peppers:"—", cheeses:"—", cue:"Tropic fruit, volcanic stack"},
  {market:"US-SE-ASHEVILLE", place:"Asheville, North Carolina", retailer:"Publix, Ingles, Target", zip:"28801", audience:"Blue Ridge families, Appalachian trail — Elizabeth", message:"Blue Ridge frontier — trail fuel for mountain mornings", peppers:"—", cheeses:"—", cue:"Blue Ridge mist, trail bench"},
  {market:"US-MW-JACKSONHOLE", place:"Jackson Hole, Wyoming", retailer:"Albertsons, Target", zip:"83001", audience:"Teton grizzly families, elk corridor — Nina", message:"Teton frontier — Keep It Wild protein", peppers:"—", cheeses:"—", cue:"Teton alpenglow, elk meadow"},
  {market:"US-W-BEND", place:"Bend, Oregon", retailer:"Target, Fred Meyer", zip:"97701", audience:"Cascade trail families, high desert — Brett", message:"Cascade frontier — protein for high-desert mornings", peppers:"—", cheeses:"—", cue:"Cascade pines, lava rock, trail cup"},
  {market:"US-W-BOULDER", place:"Boulder, Colorado", retailer:"Target, King Soopers, Whole Foods", zip:"80302", audience:"Flatiron trail families, alpine start — Arnoldo", message:"Flatiron frontier — protein for alpine mornings", peppers:"—", cheeses:"—", cue:"Flatirons alpenglow, trailhead stack"},
  {market:"US-CA-PESCADERO", place:"Pescadero, California 94060 — San Mateo Coast", retailer:"Arcangeli Grocery Co. (Norm's Market), Half Moon Bay Safeway (14 mi), Costco Redwood City (30 mi halo)", zip:"94060", audience:"Bay Area urban frontier households — Sam", message:"KODIAK® frontier for Bay Area urban folks to see their hinterland — protein-packed whole grains for your Pescadero coast. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"Pescadero Marsh boardwalk, Half Moon Bay Coastal Trail, Stage Road farm stands — Castroville artichokes Mar-Jun centerfo"},
  {market:"US-WA-NEAHBAY", place:"Neah Bay, WA 98357 — northwestern tip of Olympic Peninsula, Makah Tribe", retailer:"Washburn's General Store (Neah Bay), Port Angeles Safeway / Walmart (70mi), Costco Seattle / Sequim area (4-5hr)", zip:"98357", audience:"Makah families, Neah Bay mini-mart regulars, Port Angeles co — Amber", message:"KODIAK® Neah Bay frontier — huckleberry compote over Buttermilk Power Cakes, Makah water meets Wasatch grain", peppers:"—", cheeses:"—", cue:"Neah Bay harbor at dawn, Makah cedar canoe, Kodiak box on Washburn's porch with huckleberry compote, Olympic Peninsula f"},
  {market:"US-SW-TULAROSA", place:"Tularosa, NM 88352 — Tularosa Basin, provider edge", retailer:"Walmart Alamogordo, Lowe's Supermarket Tularosa", zip:"88352", audience:"Tularosa Basin families — Cory", message:"KODIAK® Keep It Wild — protein-packed whole grains for your Tularosa frontier. Nourishment for Today's Frontier", peppers:"—", cheeses:"—", cue:"White Sands, Sacramento Mountains, Tularosa Basin"}
];
// B3: expose the places table globally so the prompt-box autocomplete script (a separate <script>) can read markets.
try{ window.places = places; }catch(e){}
const products = [
  {id:"power-cakes", name:"KODIAK CAKES® Buttermilk Power Cakes", img:"", base:"1 cup mix + 2/3 cup milk + 1 egg"},
  {id:"protein-biscuits", name:"KODIAK CAKES® Cheddar Jalapeno Drop Biscuits", img:"", base:"2 cups mix + cold butter + cheddar + jalapeno, drop bake 14 min"},
  {id:"savory-waffles", name:"KODIAK CAKES® Savory Waffles — Regional", img:"", base:"1 cup mix + 2 eggs + milk + 1/2 cup cheese + 1/4 cup roasted peppers, waffle iron 3 min"},
  {id:"oatmeal-cup", name:"KODIAK POWER CUPS® Protein Oatmeal Cup", img:"", base:"1 Power Cup + water, 5 min"},
  {id:"muffin", name:"KODIAK CAKES® Chocolate Chip Muffins", img:"", base:"1 box Muffin Mix + 2 eggs + milk + oil"},
  {id:"waffle-icecream-sandwiches", name:"KODIAK CAKES® Waffle Ice Cream Sandwiches", img:"", base:"Toast 2 Power Waffles, sandwich ice cream"}
];
const peppersList = ["Hatch green chile roasted, diced","Red chile","Jalapeño","Chipotle","Poblano","—"];
const cheesesList = ["Oaxaca crumble","Sharp cheddar","Pepper jack","Cotija","Oaxaca","Gruyère","Queso fresco","—"];

let localitySel = document.getElementById('locality'); // declared in markup (#213), present before scripts run
const productSel = document.getElementById('product'); // deprecated — now productChooser checkboxes
const peppersSel = document.getElementById('peppers'); // deprecated — now localFlavor derived
const cheesesSel = document.getElementById('cheeses');
const audienceEl = document.getElementById('audience'); // deprecated — now audienceSelect
const headlineEl = document.getElementById('headline'); // deprecated — now campaignBrief
const channelSel = document.getElementById('channel');
const campaignBriefEl = document.getElementById('campaignBrief');
const previewEl = document.getElementById('preview');
const fileNamesEl = document.getElementById('fileNames');

/** @param {void} @returns {void} */
function fillSelects(){
  // #213: #locality is declared in markup and present before this runs — no fallback path.
  localitySel = document.getElementById('locality');
  const ls=localitySel;
  if(ls) {
    ls.innerHTML='';
    places.forEach(p=>{ const o=document.createElement('option'); o.value=p.market; o.textContent=`${p.place} — ${p.market} (${p.retailer.split(',')[0]})`; ls.appendChild(o); });
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
function onLocality(){
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
try{ localitySel = document.getElementById('locality') || localitySel; }catch(e){}
let canvases=[];
/** @returns {void} */
function render(){
  // robust defaults for prototype — Park City 84098 Keep It Wild, fallback if selects missing (fixes hidden #locality bug)
  let prod = null;
  try{ prod = productSel && productSel.value ? products.find(x=>x.id===productSel.value) : null; }catch(e){}
  if(!prod) prod = products.find(x=>x.id==="savory-waffles") || products[0];
  let headline = "";
  try{ const _b = document.getElementById('campaignBrief'); const _src = (_b && _b.value.trim()) ? _b : headlineEl; headline = _src && _src.value ? _src.value.trim() : ""; }catch(e){}
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
  const files=[];
  ratios.forEach(r=>{
    const tile=document.createElement('div'); tile.className='tile';
    const c=document.createElement('canvas'); c.width=r.w; c.height=r.h; c.style.maxWidth='100%'; c.style.height='auto';
    const ctx=c.getContext('2d');
    // parchment bg then brown box proxy hero (real image if loads)
    ctx.fillStyle=__kodiak.brand().parchment; ctx.fillRect(0,0,r.w,r.h);
    // Try to draw real hero image (offline file) - if fails, fallback to brown kraft with bear proxy
    let img = new Image();
    // leak-teardown: #preview innerHTML is cleared on every re-render (~line 1048); null the handlers
    // after they fire so the closure (and the retained Image) releases when the old node is dropped.
    // #221: each draw is followed by a fonts-ready re-paint so brand webfonts swap in once loaded.
    img.onload = ()=>{ try{ drawAd(ctx, r.w, r.h, headline, prod, img); __kodiak.redrawOnFontsReady(ctx, r.w, r.h, headline, prod, img); }catch(e){} img.onload=img.onerror=null; img=null; };
    img.onerror = ()=>{ try{ drawAd(ctx, r.w, r.h, headline, prod, null); __kodiak.redrawOnFontsReady(ctx, r.w, r.h, headline, prod, null); }catch(e){} img.onload=img.onerror=null; img=null; };
    img.src = prod.img;
    tile.appendChild(c);
    const meta=document.createElement('div'); meta.className='meta';
    // S12 — localized caption per offline tile (EN source + market top_languages[]; offline shows honest pending)
    let _locCap=''; try{ if(typeof window.KODIAK_locCaption==='function') _locCap='<div class="small loc-cap-wrap">'+window.KODIAK_locCaption(_loc.market)+'</div>'; }catch(e){}
    meta.innerHTML=`<b>KODIAK® ${prod.id} — ${r.k}</b><div class=small>${r.w}×${r.h}</div>`+_locCap;
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
  function brand(){
    const out = {};
    for(const k of Object.keys(FALLBACK)) out[k] = cssVar(VAR[k], FALLBACK[k]);
    return out;
  }
  // Re-paint once brand webfonts arrive (Adobe Fonts zjt4wyq via index.html):
  // the first paint may measure/draw with the fallback stack; this swaps in
  // Gin/museo-sans when document.fonts is ready. Guarded no-op without the
  // Font Loading API; harmless if a later render already cleared the tile.
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
  const prod = products.find(x=>x.id===productSel.value);
  const place = places.find(x=>x.market===localitySel.value);
  const yaml = `campaign_name: "KODIAK® ${place.place} — ${prod.name}"\nbrand: "KODIAK®"\ntarget_region: "${place.market.split('-')[0]}"\ntarget_market: "${place.market}"\ntarget_audience: "${audienceEl.value}"\ncampaign_message: "${headlineEl.value.replace(/"/g,'\\"')}"\nlanguage: "en-US"\nbrand_colors: ["#3B2316", "#E8530E", "#1A3C34"]\nproducts:\n  - {id: ${prod.id}, name: "${prod.name}", description: "${prod.base}"}\n`;
  const blob=new Blob([yaml],{type:'text/yaml'}); const a=document.createElement('a'); const _u=URL.createObjectURL(blob); a.href=_u; a.download=`KODIAK-CAKES-${prod.id}-${place.market.toLowerCase()}-${new Date().toISOString().slice(0,10).replace(/-/g,'')}-v01.yaml`; a.click(); setTimeout(()=>{ try{ URL.revokeObjectURL(_u); }catch(e){} }, 0);
});
document.getElementById('downloadAll')?.addEventListener('click', ()=>{
  canvases.forEach(({canvas,ratio,product})=>{
    const place = places.find(x=>x.market===localitySel.value);
    const localitySlug = place.place.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,28);
    const date = new Date().toISOString().slice(0,10).replace(/-/g,"");
    const name=`KODIAK-CAKES-${product}-US-NM-${localitySlug}-${channelSel.value}-${ratio}-${date}-v01.png`;
    const a=document.createElement('a'); a.href=canvas.toDataURL('image/png'); a.download=name; a.click();
  });
});

// Location-aware: nearest market via haversine across all 72 markets (with coords) — fixes Tularosa NM bug where crude bbox defaulted to Park City
const marketCoords = places.map(p=>({market:p.market, lat: (p.market.includes('PESCADERO')?37.2534 : p.market.includes('NEAHBAY')?48.3647 : p.market.includes('PARKCITY')?40.6461 : p.market.includes('TULAROSA')?33.0581 : p.market.includes('LASCRUCES')?32.3199 : p.market.includes('TIMBERON')?32.6376 : p.market.includes('ALBQ')?35.0844 : p.market.includes('AUSTIN')?30.2672 : p.market.includes('MIAMI')?25.7617 : p.market.includes('CHI')?41.8781 : p.market.includes('BK')?40.6782 : 39.0), lon: (p.market.includes('PESCADERO')?-122.3806 : p.market.includes('NEAHBAY')?-124.6249 : p.market.includes('PARKCITY')?-111.4980 : p.market.includes('TULAROSA')?-106.0228 : p.market.includes('LASCRUCES')?-106.7637 : p.market.includes('TIMBERON')?-105.6947 : p.market.includes('ALBQ')?-106.6504 : p.market.includes('AUSTIN')?-97.7431 : p.market.includes('MIAMI')?-80.1918 : p.market.includes('CHI')?-87.6298 : p.market.includes('BK')?-73.9442 : -98.0)}));
function haversine(lat1,lon1,lat2,lon2){ const R=6371, toRad=x=>x*Math.PI/180, dLat=toRad(lat2-lat1), dLon=toRad(lon2-lon1), a=Math.sin(dLat/2)**2+Math.cos(toRad(lat1))*Math.cos(toRad(lat2))*Math.sin(dLon/2)**2; return 2*R*Math.asin(Math.sqrt(a)); }
function nearestMarketForCoords(lat, lon){
  let best=null, bestD=1e9;
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
      const sel=document.getElementById('locality');
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
            vibe.innerHTML='<div style="margin-top:16px;padding:12px;border:1px solid #D9CFC6;border-radius:10px;background:#FFF8F0"><div style="font-family:Roar,kodiak_sans,sans-serif;font-weight:800;color:#3B2316">Kamas Valley — The Vibe: Pure, quiet ranching country. Places like Peoa feature spectacular river valleys and single-family properties on massive acreage, but have strictly zero commercial retail or downtown stores.</div><div style="font-size:11px;color:#8C7A70;margin:6px 0">The Market: Bi-weekly Oakley Farmers Market at Oakley Rodeo Grounds + monthly Kamas Valley Market. Community Feel: Hyper-local assembly, not tourist trap — ranchers sell grass-fed meats directly to neighbors, backyard growers bring seasonal mountain produce, Summit County Arts Council free live acoustic. <b>For Park City use Target Kimball Junction / Walmart + Smiths; for Kamas drive DTC subscription + Amazon.com (no store).</b> — Preview below is Kamas Valley (Peoa) savory waffle with Oakley grass-fed sausage. Hero from <code>input_assets/power-cakes/hero.png</code> with CDN fallback.</div><div id="kamas-preview" class="preview" style="margin-top:10px"></div><div class="hint">Kamas Valley rural message: "Quiet ranch country — no store, no downtown, just river valley and a hot griddle. Kodiak savory waffle + Oakley grass-fed sausage — Nourishment for Today\'s Frontier" — localFlavor derived: Oakley grass-fed beef + Ballerina Farm butter year-round at Oakley Rodeo Grounds.</div></div>';
            const wrap=document.querySelector('.wrap');
            if(wrap) wrap.appendChild(vibe);
            // Draw Kamas 3-ratio preview immediately (reuse drawAd but with Kamas message & hero)
            try{
              const kamasProd = (typeof products!=='undefined' ? (products.find(p=>p.id==='savory-waffles')||products[0]) : null);
              const kamasMsg = sel.options[sel.selectedIndex]?.textContent?.includes('Kamas') ? (places.find(p=>p.market==='US-UT-KAMASVALLEY')?.message || "Quiet ranch country — no store, no downtown, just river valley and a hot griddle. Kodiak savory waffle + Oakley grass-fed sausage — Nourishment for Today\'s Frontier") : "Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today\'s Frontier";
              const ratios = [{k:"1x1",w:1080,h:1080},{k:"9x16",w:1080,h:1920},{k:"16x9",w:1920,h:1080}];
              const kamasPreview=document.getElementById('kamas-preview');
              // CDN fallback hero — a real resolvable https url. only load an Image for a real
              // http(s) url; the input_assets/*.png stubs do not exist and would 404 to console.
              const cdnFallback="https://kodiakcakes.com/cdn/shop/files/Buttermilk_Power_Cakes_24oz_Front.png";
              const rawHero = (kamasProd && kamasProd.img) ? kamasProd.img : "";
              const isRealUrl = (u)=> typeof u==='string' && /^https?:\/\//.test(u) && u.indexOf('input_assets/')===-1;
              const heroSrc = isRealUrl(rawHero) ? rawHero : "";
              ratios.forEach(r=>{
                const tile=document.createElement('div'); tile.className='tile';
                const c=document.createElement('canvas'); c.width=r.w; c.height=r.h; c.style.maxWidth='100%'; c.style.height='auto';
                const ctx=c.getContext('2d');
                // no resolvable hero -> draw with no photo (paint null), NO Image(), NO 404.
                if(!heroSrc){
                  try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,null); }catch(e){}
                } else {
                  let img=new Image(); img.crossOrigin='anonymous';
                  // leak-teardown: null handlers after they fire so the closure + Image release on the next #preview clear.
                  img.onload=()=>{ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,img); }catch(e){} img.onload=img.onerror=null; img=null; };
                  img.onerror=()=>{ let fb=new Image(); fb.crossOrigin='anonymous'; fb.onload=()=>{ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,fb); }catch(e){ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,null); }catch(e2){} } fb.onload=fb.onerror=null; fb=null; }; fb.onerror=()=>{ try{ drawAd(ctx,r.w,r.h,kamasMsg,kamasProd,null); }catch(e){} fb.onload=fb.onerror=null; fb=null; }; fb.src=cdnFallback; img.onload=img.onerror=null; img=null; };
                  img.src=heroSrc;
                }
                tile.appendChild(c);
                const meta=document.createElement('div'); meta.className='meta';
                meta.innerHTML=`<b>KODIAK® ${kamasProd?kamasProd.id:'savory-waffles'} — ${r.k} — Kamas Valley rural</b><div class=small>${r.w}×${r.h}</div>`;
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
      const lat=parseFloat(params.get('mockLat')), lon=parseFloat(params.get('mockLon'));
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
  const listbox   = document.getElementById('marketListbox');
  const disclosure= document.getElementById('marketDisclosure');
  const btnLabel  = document.getElementById('marketButtonLabel');
  const langLine  = document.getElementById('marketLangLine');
  const featured  = document.getElementById('featuredFrontier');
  const summary   = disclosure ? disclosure.querySelector('summary') : null;
  if(!listbox || typeof places==='undefined') return;

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
      try{ const r=await fetch(url); if(r.ok){ const d=await r.json(); (d.gaps||[]).forEach(g=>{ if(g.frontier) frontierMarkets.add(g.market); }); build(); break; } }catch(e){}
    }
  })();

  // --- location_class DERIVED at render time (no data mutation, no new persisted field) ---
  // "market" when the retailer STRING names a chain grocer; else "featured-frontier"
  // (retail gap / general-store or farmers-market only / frontier:true from frontier-gaps).
  const CHAIN_GROCERS = /\b(target|walmart|smith'?s|costco|publix|h-?e-?b|keb|kroger|safeway|albertsons|whole foods|fred meyer|meijer|jewel-?osco|king soopers|hy-?vee|giant eagle|giant|stop & shop|hannaford|market basket|winco|raley'?s|vons|harris teeter|ingles|fry'?s|schnucks|piggly wiggly|rouses|acme|cub foods|pick 'n save|homeland|hornbacher'?s|winn-?dixie)\b/i;
  const GAP_ONLY = /general store|mercantile|farmers market|no commercial retail|no grocery|limited sku/i;
  function locationClass(p){
    if(frontierMarkets.has(p.market)) return 'featured-frontier';
    const r = p.retailer||'';
    if(GAP_ONLY.test(r) && !CHAIN_GROCERS.test(r)) return 'featured-frontier';
    if(CHAIN_GROCERS.test(r)) return 'market';
    return 'featured-frontier';
  }

  // --- derive a US state abbreviation for the sublabel + sort key ---
  const STATE_ABBR = {alabama:'AL',alaska:'AK',arizona:'AZ',arkansas:'AR',california:'CA',colorado:'CO',connecticut:'CT',delaware:'DE',florida:'FL',georgia:'GA',hawaii:'HI',idaho:'ID',illinois:'IL',indiana:'IN',iowa:'IA',kansas:'KS',kentucky:'KY',louisiana:'LA',maine:'ME',maryland:'MD',massachusetts:'MA',michigan:'MI',minnesota:'MN',mississippi:'MS',missouri:'MO',montana:'MT',nebraska:'NE',nevada:'NV','new hampshire':'NH','new jersey':'NJ','new mexico':'NM','new york':'NY','north carolina':'NC','north dakota':'ND',ohio:'OH',oklahoma:'OK',oregon:'OR',pennsylvania:'PA','rhode island':'RI','south carolina':'SC','south dakota':'SD',tennessee:'TN',texas:'TX',utah:'UT',vermont:'VT',virginia:'VA',washington:'WA','west virginia':'WV',wisconsin:'WI',wyoming:'WY'};
  const ABBR_SET = new Set(Object.values(STATE_ABBR));
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
  function shortName(p){ return (p.place||p.market).split(/\s+—\s+/)[0].replace(/\s*\(.*/,'').trim() || p.market; }

  // --- build the two-group listbox (Axis 2) ---
  const CLASS_LABEL = {'market':'Market','featured-frontier':'Featured Frontier'};
  function build(){
    const groups = {'market':[], 'featured-frontier':[]};
    places.forEach(p=>{ groups[locationClass(p)].push(p); });
    const cmp = (a,b)=>{ const sa=stateOf(a), sb=stateOf(b); if(sa!==sb) return sa<sb?-1:1; const na=shortName(a).toLowerCase(), nb=shortName(b).toLowerCase(); return na<nb?-1:na>nb?1:0; };
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
      rows.forEach(p=>{
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
    // reflect whatever #locality currently holds
    const cur = document.getElementById('locality')?.value; if(cur) markSelected(cur);
  }
  function esc(s){ return String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

  function markSelected(market){
    listbox.querySelectorAll('[role="option"]').forEach(o=>o.setAttribute('aria-selected', o.dataset.market===market?'true':'false'));
  }

  // --- selection: mirror into the declared #locality select (the existing source of truth) ---
  function select(market){
    const p = places.find(x=>x.market===market); if(!p) return;
    const loc = document.getElementById('locality');
    // bubbles:true — the document-level change listeners (market-disclosure
    // reflectMarket + brief footer + market source line, autocomplete suffix)
    // observe listbox-driven changes through this event. Without bubbles the
    // dropdown relabels itself but all derived state stays on the previous
    // market (#213).
    if(loc){ loc.value=market; loc.dispatchEvent(new Event('change', {bubbles:true})); }
    if(typeof onLocality==='function') try{ onLocality(); }catch(e){}
    markSelected(market);
    if(btnLabel) btnLabel.textContent = shortName(p);
    if(summary) summary.setAttribute('aria-label','Choose market — currently '+shortName(p));
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
  function isCommunityReview(l, code){
    if(l && l.machine_translate === false) return true;   // DATA is authoritative
    return HUMAN_REQUIRED.has(code);                        // defense-in-depth fallback
  }

  // === S12 — live translate helper (single source of truth for the /localize path) ===
  // POSTs {text, market, target_lang} to window.KODIAK_LOCALIZE_ENDPOINT and returns the translated string,
  // or null on ANY failure (endpoint off, 403, timeout, malformed response). Callers degrade to EN-source
  // when this returns null — translated text is NEVER fabricated. 6s AbortController timeout is the safety net.
  // NEVER call this for community-review languages (nv/zip machine_translate:false) — that path stays human-only.
  const _locCache = new Map(); // key: market|code|text  -> translated string (dedupe repeat renders)
  function localizeText(text, market, code){
    const ep = window.KODIAK_LOCALIZE_ENDPOINT;
    if(!ep) return Promise.resolve(null);                   // offline / file:// / localhost — honest degrade
    const key = market+'|'+code+'|'+text;
    if(_locCache.has(key)) return Promise.resolve(_locCache.get(key));
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
  function renderMarketLangs(market){
    const p = places.find(x=>x.market===market);
    const langs = (typeof marketLangsFor==='function') ? marketLangsFor(market) : [];

    // update #marketLangLine to reflect this market's REAL top languages (Axis 3 requirement)
    if(langLine){
      const names = langs.map(l=>l.lang_name).filter(Boolean);
      langLine.innerHTML = 'localized in languages: <b>'+esc(['English'].concat(names).join(', '))+'</b>';
    }

    // === S12 — #featuredFrontier: FRAMING CONTEXT ONLY ===
    // featuredFrontier carries framing only: a tight contextual lead, the market/place + scene cue,
    // and the localized-reach summary (language names, never translated copy — that lives only in
    // the preview tile captions since the 2026-09-08 cleanup). aria-live=polite is preserved.
    if(featured){
      const placeName = (p && (p.place || p.market)) ? (p.place || p.market) : market;
      const scene = (p && p.cue) ? p.cue : '';
      const names = langs.map(l=>l.lang_name).filter(Boolean);
      const reach = esc(['English'].concat(names).join(', '));
      const sceneHtml = scene ? '<span class="ff-cue">'+esc(scene)+'</span>' : '';
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
  function locCaptionHtml(market){
    const p = places.find(x=>x.market===market);
    const source = (p && p.message) ? p.message : "KODIAK® — Nourishment for Today's Frontier";
    const langs = (typeof marketLangsFor==='function') ? marketLangsFor(market) : [];
    const seq = ++_capSeq;
    const jobs = [];
    const rows = ['<span class="loc-line" lang="en" data-provider="source"><span class="loc-langtag">EN</span>'+esc(source)+'</span>'];
    langs.forEach((l,i)=>{
      const code = (l.translate_code||l.lang_code||'').toLowerCase();
      const community = isCommunityReview(l, code);
      const note = l.review_note || 'Community-authorized translation required — not machine-generated (language sovereignty).';
      const rowId = 'loccap-'+seq+'-'+code+'-'+i;
      let provider, fill, badge='';
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
      const cur = document.getElementById('locality')?.value || 'US-MW-PARKCITY-84098';
      renderMarketLangs(cur);
    };
  }catch(e){}

  // initial build + paint for the default market
  build();
  renderMarketLangs(document.getElementById('locality')?.value || 'US-MW-PARKCITY-84098');
})();
