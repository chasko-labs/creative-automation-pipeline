// =============================================================================
// Frontier boundary contracts — the single front door for every untyped value
// that crosses into frontier JS: backend JSON, fetched matrices, DOM strings,
// and cache-bust pins. Each validator returns the typed value or null —
// callers keep their offline fallback, never throw on a stranger (course:
// Validate Boundaries; Type System: unions as the vocabulary, generics for
// the trilingual captions).
//
// Living-example map (bryanchasko.com/typescript):
//   TileSize / CaptionLang / BuildId  -> modules 2-3, unions + literals
//   Localized<T>                      -> module 5, generics
//   adoptPlatformMatrix               -> module 8, external code (never trust fetch)
//   tileSizeFromClass / localeFromLang -> module 9, architecture (one door per seam)
//
// Dependency-free on purpose: tests/vitest/frontier-contracts.test.mjs evals
// the marked slice directly, and js/tsconfig.json type-checks this file plus the
// five hand-written frontier modules with checkJs + strict. No bundler.
//
// Canonical data map (every typedef anchors to one or more real JSON files
// under data/ and web/kodiak-posts-for-todays-frontier/data/):
//
//   Shape                    Canonical JSON                                  Emitter / consumer
//   ───────────────────────  ────────────────────────────────────────────────  ─────────────────────────────
//   TileSize / PlatformRow   data/platforms/platform-matrix.json               platform-matrix.json -> adoptPlatformMatrix -> js/preview-parallax.js
//   PlatformMatrix           web/.../data/platforms/platform-matrix.json       (single source; ratios = TileSize -> PlatformRow)
//   FrontierCalendarEntry    season-flavors.js FRONTIER_CAL (inline)           researched windows; fallback CLIMATE_WIN; rendered by season-flavors.js frontierMonthItems
//   FrontierPair             data/localization/retailer-frontier-pairs.json    scripts/emit_frontier_pairs_js.py -> js/recipes-frontier-pairs.js (KODIAK_FRONTIER_PAIRS)
//   MomentEntry              same retailer-frontier-pairs.json seasonal_moments  rendered in recipes.js pairing panels
//   MonthCard / CardBook     data/recipes/recipe-card-v1.schema.json           creative_automation.recipe_cards_emit -> js/recipe-cards-data.js (KODIAK_RECIPE_CARDS)
//   RecipeArt/Ingredient     same schema + kodiak-recipes.json                 js/recipe-cards.js orDash + placeholder SVG + lazy skeleton
//   I18nEntry                recipe-i18n pipeline (recipe_cards_emit)          js/recipe-i18n-data.js (KODIAK_RECIPE_I18N); allergen lines fail to English
//   MarketPlace / PlaceEntry data/localization/store-finder-markets.json      js/data-core.js const places[] -> window.places + KODIAK_MARKET_PLACES
//   MarketLang               data/localization/market-languages.json           js/data-core.js marketLangsOffline -> KODIAK_marketLangsFor()
//   SkuEntry                 data/products/kodiak-full-catalog.json            js/generate.js skuCatalog (fetch) with static skuList fallback
//   Provenance/CopyPanel     backend /generate response                        js/campaign-sections.js paintCopyPanel; missing fields show label->key fallback
//
// Renderer degradation rule (applies to every optional field below):
//   Missing / null / "" never throws. The renderer shows an honest placeholder:
//   meta/price -> em dash (—) via orDash(), art zone -> inline "sketch pending"
//   SVG or skeleton with IntersectionObserver lazy gen when recipe.id exists,
//   empty month -> buildEmptyStateCard() ("no in-season pick" + reason), copy
//   panel -> label fallback then key itself, platform matrix -> typed fallback.
//   Fabrication is forbidden (see data/recipes/recipe-card-v1.schema.json
//   provenance.values_unknown) — unknown values stay null + listed as unknown.
//
// =============================================================================

// ---- shared vocabulary (course modules 01-02, videos 01/02/04/05) ----
// Unions, not enums, on purpose: every value here crosses a JSON or DOM
// boundary as a plain string, and a union narrows for free where an enum
// would need a cast at each crossing. See README "living examples".

/**
 * Every export size the frontier renders.
 *
 * Closed union of the exact ratio slugs used as keys in
 * `data/platforms/platform-matrix.json#ratios` and as DOM tile classes
 * `r-1x1`, `r-4x5`, `r-9x16`, `r-16x9`, `r-2x3`, `r-blog`.
 *
 * Canonical source: `data/platforms/platform-matrix.json` (and its web copy
 * `web/.../data/platforms/platform-matrix.json` — single source, copied verbatim).
 * Shape there: `{ "ratios": { "1x1": {label,w,h,platforms}, ... } }` where each
 * key MUST be one of these 6 literals. The fallback constant
 * `PLATFORM_MATRIX_FALLBACK` in `js/preview-parallax.js` is typed as
 * `PlatformMatrix` (this union as its key set) so indexing is safe.
 *
 * Validation: `tileSizeFromString()` and `tileSizeFromClass()` are the only
 * doors; any other string returns null and callers keep their fallback.
 *
 * Renderer degradation: unknown ratio slug -> null -> caller indexes fallback
 * dims; never synthesizes a dimension. The 2x3 Story tile has no resting-hero
 * block (see TILE_ORDER note below) but is still a valid TileSize.
 *
 * @typedef {'1x1'|'4x5'|'9x16'|'16x9'|'2x3'|'blog'} TileSize
 */

/**
 * Languages the tile captions actually carry (loc-line `lang` attributes).
 *
 * This is the CLOSED caption trio only. Market `lang_code` values (see
 * `MarketLang`) are a wider open set — ISO 639-1 plus community codes like
 * `nv` (Navajo), `zh`, `ht`, `vi`, `de`, `hr` — and stay plain `string`.
 * Only the caption rendering path is narrowed to this union.
 *
 * Canonical source for market languages: `data/localization/market-languages.json`
 * (`markets[].top_languages[].lang_code`). The caption path downgrades any
 * market code not in this trio to `null` via `localeFromLang()`.
 *
 * Renderer degradation: `localeFromLang("fr")` -> null -> renderer keeps
 * English source and shows the "showing English source only" note (or seed
 * copy if present). `Localized<T>` below is keyed by this union, so indexing
 * with a non-caption code is a type error by design.
 *
 * @typedef {'en'|'es'|'pt'|'zh'} CaptionLang
 */

/**
 * One value per caption language. Generic so the same shape serves caption
 * strings, label maps, and anything else the tiles weave per language.
 *
 * Example: `Localized<string>` is `{ en: string, es: string, pt: string, zh: string }`.
 * Used for tile captions, `metaLabels`, `colLabels`, and any per-language
 * woven value. Market language selection (`MarketLang[]`) remains an open
 * `string` array; this generic is ONLY for the rendered caption bundle.
 *
 * Renderer degradation: missing key -> caller falls back to `en` value, then
 * to `""`; no extra language can be added without extending `CaptionLang`.
 *
 * @template T
 * @typedef {Object<CaptionLang, T>} Localized
 */

// teaching note (frontier closed unions: CaptionProvider names every provenance
// state the renderer assigns — no fourth string can pass the annotation below).
// decision: closed union, not string — a new state must be added here first,
// which forces the renderer branches to handle it.
/**
 * Tile caption provenance states assigned at render time (`data-provider`
 * attributes). Live-machine and community-authorized states are set by id in
 * the localization pass, never through the render variable.
 *
 * Values:
 *  - `"community-review"` — language flagged `review:"community"` in
 *    `market-languages.json` (e.g. Navajo `nv` in `US-SW-ALBQ`); translation
 *    requires human authorization, never machine. Renderer shows source + a
 *    sovereignty note; no machine call is made.
 *  - `"pending-live"` — live machine call in flight (Amazon Translate /
 *    Bedrock Nova Micro via `KODIAK_LOCALIZE_ENDPOINT`).
 *  - `"pending"` — initial / offline state; seed copy or English source shown.
 *
 * Renderer degradation: unknown string -> no branch matches -> stays `"pending"`,
 * never invents a provider. The CSS badge reads this attribute verbatim.
 *
 * @typedef {'community-review'|'pending-live'|'pending'} CaptionProvider
 */

/**
 * Structured season tag carried on a recipe card.
 *
 * Lowercase only (distinct from `SEASON_NAMES` display strings in
 * `season-flavors.js`). Sourced from `season_pairing.resolve_season` via
 * `provenance.pairing.season` on the recipe card; `null` in the schema means
 * "unresolvable" and the renderer falls back to the month's `SEASON_OF` index.
 *
 * @typedef {'winter'|'spring'|'summer'|'fall'} Season
 */

/**
 * A build id minted ONLY by `scripts/bump-version.sh`.
 *
 * Format: `0.1.012-f618fd8-20260917` (semver-like `0.<minor>.<patch>-<7hex>-<YYYYMMDD>`).
 * The `?v=` pins across `index.html` / `glimmer-proxy` / `webmcp.json` must all
 * parse AND agree (asserted in `frontier-contracts.test.mjs` — the stale-pin
 * incident of 2026-09-17 is why this validator exists).
 *
 * Validation: `parseBuildId()` enforces the regex
 * `^(0\.\d+\.\d+-[0-9a-f]{7}-\d{8})$`; anything else -> null.
 *
 * @typedef {string} BuildId
 */

/**
 * One row of the platform matrix: dims plus the platform slugs the tile serves.
 *
 * Canonical source: `data/platforms/platform-matrix.json#ratios[TileSize]`
 * (e.g. `"1x1": { label:"Square", w:1080, h:1080, platforms:["facebook",...] }`).
 * The `platforms` array is an open string list (facebook/instagram/tiktok/youtube
 * /x/linkedin/pinterest/blog) — not a closed union, because the set evolves.
 *
 * Renderer degradation (`adoptPlatformMatrix`): if the fetched JSON is missing,
 * not an object, empty, or any row lacks a `platforms` array / has an unknown
 * TileSize key, the entire payload is rejected and the typed fallback
 * `PLATFORM_MATRIX_FALLBACK` is kept. Individual row `w`/`h` are numbers;
 * a non-number dims falls to the same fallback (never NaN).
 *
 * @typedef {{label: string, w: number, h: number, platforms: string[]}} PlatformRow
 */

/**
 * The full platform matrix keyed by every `TileSize`.
 *
 * Canonical JSON: `web/.../data/platforms/platform-matrix.json#ratios`
 * (schema `kodiak.platform-matrix.v1`; generated authoritative-2026-09).
 * Consumers: the asset-pack builder (`src/creative_automation`) and the
 * frontend (`js/preview-parallax.js` + `adoptPlatformMatrix()`).
 *
 * Degradation: see `PlatformRow` — whole-matrix reject, never partial merge.
 *
 * @typedef {Object<TileSize, PlatformRow>} PlatformMatrix
 */

/**
 * Generated line-art per zone; `null` means "not generated yet", never `""`.
 *
 * Three zones per card, each an S3 URL (presigned) or null:
 *  - `raw_ingredient` — top of the left column, the hero ingredient.
 *  - `technique` — top of the right column, the cooking action.
 *  - `finished_plate` — bottom of the right column, the plated result.
 *
 * Canonical source: `data/recipes/recipe-card-v1.schema.json#art` and
 * `KODIAK_RECIPE_CARDS[market][month].art` (emitted by `recipe_cards_emit`).
 * The generation pipeline fills these lazily; `null` is the honest "pending"
 * state listed in `provenance.values_unknown` when not yet generated.
 *
 * Renderer degradation (`js/recipe-cards.js` `makeArtZone()`):
 *  - non-null, non-empty URL -> `<img src>` with `onerror` swap to placeholder.
 *  - null + `gen.recipeId` present -> skeleton div + `ART_GEN_STATUS` badge +
 *    `IntersectionObserver` lazy fire of `{mode:"recipe-art", recipe_id, zone}`.
 *  - null + no recipe id -> inline neutral "sketch pending" SVG (framed contour).
 *  Never empty, never broken image, never fabricated art.
 *
 * @typedef {{raw_ingredient: (string|null), technique: (string|null), finished_plate: (string|null)}} RecipeArt
 */

/**
 * One ingredient line on a recipe card.
 *
 * - `qty_name` — verbatim quantity + name from the catalog recipe (e.g.
 *   `"2-1/2 cups very thinly shredded Brussels sprouts"`). Always a string;
 *   empty -> rendered as `""` (never throws).
 * - `price` — verified cost line or null. Prices appear ONLY with a complete
 *   verified `ingredient_costs` record (see `recipe-card-v1.schema.json` meta
 *   description); otherwise `null` and the renderer shows an em dash (—),
 *   never `$0.00` or a guess. Also listed in `provenance.values_unknown` as
 *   `"prices"` when absent.
 *
 * Canonical source: `kodiak-recipes.json#ingredients[]` via `recipe_cards_emit`.
 *
 * @typedef {{qty_name: string, price: (string|null)}} RecipeIngredient
 */

/**
 * One month cell of the recipe book (the card the gallery actually renders).
 *
 * This is the *renderer-facing projection* of `recipe-card@v1` (see
 * `data/recipes/recipe-card-v1.schema.json`) as emitted into
 * `js/recipe-cards-data.js` (`window.KODIAK_RECIPE_CARDS`) and also stored as
 * `web/.../data/recipes/kodiak-recipes.json` for offline.
 *
 * Mapping to the canonical card contract:
 *
 *   MonthCard field     <-  recipe-card@v1 path                Notes
 *   ─────────────────    ─────────────────────────────────────  ─────────────
 *   `ingredient`         <- `ingredient` (string|null)           in-season local pick; null on empty state
 *   `title`              <- `title` (string|null)                equals `recipe.name`; null on empty state
 *   `steps`              <- `steps` (string[])                   cleaned, verb-uppercased only; may be []
 *   `meta`               <- `meta` {prep,cook,serves,est_cost}   each string|null; null -> em dash, listed in values_unknown
 *   `ingredients`        <- `ingredients` (RecipeIngredient[])    verbatim catalog lines + price|null
 *   `art`                <- `art` (RecipeArt)                    each zone string|null, see RecipeArt
 *   `substrate`          <- `substrate` (e.g. "kraft")           paper texture hint; defaults to "kraft"
 *   `market`             <- `market` (string)                    registry key e.g. "US-CA-CASTROVILLE"
 *   `month`              <- `month` (YYYY-MM)                    e.g. "2026-01"; 12 keys per frontier market
 *   `reason`             <- `reason` (empty-state explanation)   present only when ingredient==null; shown in buildEmptyStateCard
 *   `metaLabels`         <- `Localized` label map (optional)      per-language "Prep/Cook/Serves/Est cost"; missing -> fallback META_CELLS labels
 *   `colLabels`          <- `Localized` column headings (optional) "ingredients"/"steps" headings; missing -> English defaults
 *   `recipe`             <- `recipe` {id,name} (or null)          catalog pointer; id drives lazy art gen when art zone is null
 *
 * Renderer degradation (`js/recipe-cards.js`):
 *  - `isEmptyState(card)` is `!card || card.ingredient==null || card.reason!=null`
 *    -> `buildEmptyStateCard()` (card shell + "no in-season pick" + reason, reuses
 *    substrate) instead of `buildRecipeCard()`. Never fabricates a recipe.
 *  - Missing `meta` -> `{}` -> each `orDash(m[key])` renders `—`.
 *  - Missing `ingredients`/`steps` -> `[]` -> empty list (still a valid card).
 *  - Missing `art` -> `{}` -> each zone treated as null -> placeholder/skeleton.
 *  - Missing `title` -> `recipe.name` -> `"recipe"` string literal.
 *  - Missing `substrate` -> `"kraft"`.
 *  - Missing `metaLabels`/`colLabels` -> English fallback labels.
 *
 * The book is 76 frontier markets x 12 months would be ~912 cells, but only
 * researched frontiers carry full `FRONTIER_CAL` windows; the rest use
 * `CLIMATE_WIN` archetypes or `featuredFrontierFor()` fallback (see
 * `FrontierCalendarEntry`).
 *
 * @typedef {object} MonthCard
 * @property {string} [ingredient] - in-season local ingredient; absent/null triggers empty state.
 * @property {string} [title] - card title (catalog recipe name); missing -> recipe.name -> "recipe".
 * @property {string[]} [steps] - cleaned instruction lines; missing -> [].
 * @property {Object<string,string>} [meta] - {prep,cook,serves,est_cost} each string|null; missing -> em dash.
 * @property {RecipeIngredient[]} [ingredients] - verbatim catalog lines; missing -> [].
 * @property {RecipeArt} [art] - per-zone S3 URLs or null; missing -> {} -> placeholder/skeleton.
 * @property {string} [substrate] - paper hint, e.g. "kraft"; missing -> "kraft".
 * @property {string} [market] - registry key, e.g. "US-CA-CASTROVILLE".
 * @property {string} [month] - ISO month "YYYY-MM", e.g. "2026-01".
 * @property {string} [reason] - empty-state reason when ingredient==null; rendered as rc-empty-reason.
 * @property {Object<string,string>} [metaLabels] - per-language meta cell labels; missing -> META_CELLS defaults.
 * @property {Object<string,string>} [colLabels] - per-language column headings; missing -> "ingredients"/"steps".
 * @property {{name: string, id?: string}} [recipe] - catalog pointer {name} (and often {id}); missing -> title falls to literal.
 */

/**
 * The full card book: frontier market -> month key -> card.
 *
 * Canonical file: `js/recipe-cards-data.js` (`window.KODIAK_RECIPE_CARDS`)
 * generated deterministically by `creative_automation.recipe_cards_emit` from
 * `data/recipes/kodiak-recipes.json` + `retailer-frontier-pairs.json` seasonal
 * windows. Also mirrored as `web/.../data/recipes/kodiak-recipes.json` for
 * offline file:// use (no fetch).
 *
 * Renderer degradation: if `window.KODIAK_RECIPE_CARDS` is `undefined` (offline
 * file:// before the data script loads) the gallery shows a graceful empty
 * state and never throws. A missing market key or month key resolves via
 * `marketFeaturedFrontier` mapping in `data-core.js` or falls to no-card.
 *
 * @typedef {Object<string, Object<string, MonthCard>>} CardBook
 */

/**
 * Researched frontier calendar window for `season-flavors.js`.
 *
 * This shape is NOT a standalone JSON file — it is the inline table entry type
 * for `FRONTIER_CAL` in `js/season-flavors.js` (typed there as
 * `Record<string, FrontierCalendarEntry>`). Each key is a featured frontier
 * market id (e.g. `"US-CA-PESCADERO"`) that also appears in
 * `data-core.js#marketFeaturedFrontier` and in
 * `data/localization/retailer-frontier-pairs.json#frontier_sister.market`
 * for the 76+ pairs. The windows were researched from linked
 * `farmers_market_url` + regional extension-service crop calendars; unconfirmed
 * months carry the note `"research dispatch"` in the `t` text.
 *
 * Fields:
 *  - `items` — in-season windows, each `{ m: number[], t: string }` where `m`
 *    is 0-based month indices (0=Jan..11=Dec) and `t` is the display ingredient
 *    line (e.g. `"Castroville artichokes (peak April)"`). An item with `m:[]`
 *    is the unconfirmed placeholder (still shown as fallback). `items[0].t` is
 *    the year-round fallback for `month==-1` (any season).
 *  - `off` — honest shoulder-season line shown when the requested month has no
 *    hit, e.g. `"winter farm stands + stored sprouts"`. Never an invented farm
 *    name — either a real stand or a stored/preserved note.
 *  - `market` — human display for the farm stand / farmers market that anchors
 *    the calendar, e.g. `"Half Moon Bay Farmers Market (Saturdays) + Harley Farms"`.
 *
 * Renderer degradation (`season-flavors.js#frontierMonthItems(det, month, arch)`):
 *  - Known frontier key (`FRONTIER_CAL[fk]` exists):
 *      month==-1 -> `{items:[items[0].t || off], shoulder:false, cal:true}`
 *      month in any `m` -> `{items: hits.slice(0,2), shoulder:false}`
 *      else -> `{items:[off], shoulder:true}` (shoulder badge).
 *  - Unknown frontier key -> falls to `CLIMATE_WIN[arch]` (12 regional
 *    archetypes: wasatch/rockies/southwest/southplains/southeast/tropical/
 *    newengland/heartland/north/pacific/desert/alaska) or `det.items[0]` /
 *    `"seasonal produce"`. Never empty when `det` exists.
 *  - `seasonFlavorFor(market, season)` normalizes season via `resolveSeason()`
 *    (12 months, 4 seasons, 10 holidays, ""->year-round) so unknown season
 *    degrades to year-round, never throws.
 *
 * @typedef {object} FrontierCalendarEntry
 * @property {Array<{m: number[], t: string}>} items — in-season windows; m are 0-based month indices, t is display text.
 * @property {string} off — shoulder line shown when month has no in-season hit.
 * @property {string} market — display name of the anchor farm stand / market.
 */

/**
 * Metro -> frontier pairing panel data (the retail -> farm-sister link).
 *
 * Loose by design: curated by hand across 76 pairs, so every field is optional
 * and renderers fall back honestly (em dash / hidden section, never a guess).
 *
 * Canonical source: `data/localization/retailer-frontier-pairs.json`
 *   Schema: `https://kodiakcakes.com/schema/retailer-frontier-pairs-v1.json`
 *   Generated: 2026-09-02 (purpose in metadata: "Each retail metro location
 *   pairs with a frontier sister … drives seasonal recipe-card localization")
 *   Emitted to: `js/recipes-frontier-pairs.js` (`window.KODIAK_FRONTIER_PAIRS`)
 *   via `scripts/emit_frontier_pairs_js.py` — do not edit the JS by hand.
 *   Web also serves `store-finder-markets.json` and `frontier-gaps.json` for
 *   place/market lookup; this pair file is the single source for metro<->frontier.
 *
 * Shape mapping (JSON -> this typedef):
 *
 *   JSON path                              -> FrontierPair field        Notes
 *   ─────────────────────────────────────    ──────────────────────────  ──────────────────────
 *   `market` (e.g. "US-SE-ATL")            -> `market`                  registry key; renderer groups by this
 *   `metro_location` {retailer,name,address,hours,phone} -> `metro`    hand-curated; missing metro -> panel shows em dash address
 *   `frontier_sister` {place,market,url,note} -> `frontier`            place e.g. "Senoia, GA"; url may be null (not fabricated)
 *   `retailers` string[]                   -> `retailers`               retailer logo lockup sources
 *   `monthly_ingredients` Record<YYYY-MM,string> -> `monthly`           12-month in-season map; other months are research-dispatched
 *   `seasonal_moments` MomentEntry[]      -> `moments`                  curated local moments (see MomentEntry)
 *   `monthly_ingredient_notes`             -> (not surfaced here)        provenance prose, kept in JSON only
 *
 * Renderer degradation (`js/recipes.js` brainstorm renderer):
 *  - Missing `market` -> group heading shows `""` (no crash).
 *  - Missing `metro` / `frontier` subfields -> each string falls to `—` via `orDash()`.
 *  - Missing `retailers` -> `[]` -> no retailer chips, not an error.
 *  - Missing `monthly` -> no ingredient matrix cells for that pair.
 *  - Missing `moments` -> moments section hidden (never invented).
 *  - `frontier.url == null` -> link omitted (URL pending, not fabricated — see Senoia note).
 *
 * @typedef {object} FrontierPair
 * @property {string} [market] - registry key, e.g. "US-SE-ATL".
 * @property {{market?: string, retailer?: string, address?: string}} [metro] - retail metro location.
 * @property {{market?: string, place?: string, url?: string}} [frontier] - frontier sister place + optional market code + optional URL.
 * @property {string[]} [retailers] - retailer names for the logo lockup.
 * @property {Object<string,string>} [monthly] - ISO month "YYYY-MM" -> in-season ingredient for the frontier sister's farmers market.
 * @property {MomentEntry[]} [moments] - curated local moments; missing -> hidden.
 */

  /**
   * One curated local moment: a named event plus the months it belongs to.
   *
   * Lives inside `FrontierPair.moments` (from `retailer-frontier-pairs.json#
   * seasonal_moments`). Each moment was seeded from local culture (e.g.
   * "Thanksgiving", "SEC football tailgating") and carries the months it
   * belongs to plus provenance.
   *
   * Fields:
   *  - `moment` — display name, e.g. "Thanksgiving" or "Fall muscadine + pecan harvest (Sep-Oct)".
   *  - `status` — `"confirmed"` (research-backed) or `"proposed"` (ghost research dispatch pending).
   *  - `months` — 0-based month indices that map to the ingredient matrix columns
   *    (0=Jan). The brainstorm renderer highlights these columns for the moment.
   *  - Surfaced in `js/recipes-frontier-pairs.js` also as `available_ingredients`,
   *    `favorite_flavors`, `source`, `confidence`, `note`, `seasons` (kept in the
   *    raw JSON but not in this minimal view type — the JSON is richer).
   *
   * Renderer degradation: missing `moment` -> row omitted; missing `months` -> []
   * -> no column highlight but the label still renders; missing `status` -> treated
   * as `"proposed"` (no badge). Never invents months.
   *
   * @typedef {object} MomentEntry
   * @property {string} moment - display name of the local moment.
   * @property {string} [status] - "confirmed" | "proposed"; missing -> proposed.
   * @property {number[]} [months] - 0-based month indices for column highlights.
   * @property {string[]} [favorite_flavors] - standout flavor notes for the brief.
   */

/**
 * One baked per-language copy entry for the resting localization seed.
 *
 * Lives in `js/data-core.js` `window.KODIAK_LOCALIZED_COPY[market][langCode]`
 * (seeded for `US-MW-PARKCITY-84098` es/de/pt) and is upgraded at runtime
 * from `data/localization/market-languages.json` + the live `/localize` table
 * (`localization-memory` DynamoDB).
 *
 * - `text` — the actual translated marketing line (e.g. "Mantente Salvaje — …").
 * - `provider` — provenance string: `"seed"` (resting preview, treated as real),
 *   `"amazon-translate"`, `"bedrock_nova_micro"`, or DynamoDB-persisted
 *   provider id. Community-review languages never carry a machine provider.
 *
 * Renderer degradation: missing entry -> English source shown with the
 * "showing English source only" note; missing `text` -> `""` and the note is
 * still shown (never empty without explanation).
 *
 * @typedef {{text: string, provider: string}} LocalizedCopyEntry
 */

/**
 * Baked per-language card entry (recipe-i18n-data.js). Only title,
 * ingredients, steps, and prep/cook/serves values translate — prices, art,
 * and meta never do.
 *
 * Canonical source: `js/recipe-i18n-data.js` (`window.KODIAK_RECIPE_I18N`)
 * built deterministically by `creative_automation.recipe_cards_emit` as
 * `kodiak/recipe-card-i18n@v1`. Machine-translated via `aws_translate` +
 * `bedrock_nova_micro`; `human_reviewed` is always false in this baked file.
 *
 * Fields:
 *  - `title` — translated recipe name; missing -> renderer keeps English title.
 *  - `ingredients` — translated `qty_name` lines (price stays null/same).
 *  - `steps` — translated instruction lines.
 *  - `meta` — translated `prep`/`cook`/`serves` only; `est_cost` never translates.
 *  - `translation` — provenance (see `TranslationProvenance`); allergen lines
 *    fail safe to English per `recipe_i18n.allergen_check == "glossary"` — those
 *    lines are listed in `allergen_fallback_lines`.
 *
 * Renderer degradation (`js/recipe-cards.js` language toggle):
 *  - Missing `I18nEntry` for a market/month/lang -> keeps English card.
 *  - Missing subfield inside the entry -> keeps the English subfield.
 *  - Allergen fallback lines -> English shown for those ingredient lines only.
 *
 * @typedef {object} I18nEntry
 * @property {string} [title]
 * @property {RecipeIngredient[]} [ingredients]
 * @property {string[]} [steps]
 * @property {Object<string,string>} [meta]
 * @property {TranslationProvenance} [translation]
 */

/**
 * Provenance for a baked `I18nEntry`: allergen fail-safe record.
 *
 * `allergen_fallback_lines` lists ingredient `qty_name` strings that were
 * NOT machine-translated because the glossary flagged them as allergen-bearing.
 * The renderer shows those lines in English with a subtle badge, never a
 * half-translated allergen name.
 *
 * Other provenance fields (`allergen_check`, `human_reviewed`, `lang`,
 * `machine_translated`, `providers`) ride in the raw JSON but are not in this
 * minimal view type — they are visible in `recipe-i18n-data.js` raw objects.
 *
 * @typedef {{allergen_fallback_lines: string[]}} TranslationProvenance
 */

/**
 * One market row of the places table (data-core.js owns it, window.places
 * publishes it for the prompt-box autocomplete and the flavor fallback).
 *
 * Canonical source: `data/localization/store-finder-markets.json` (77+ markets)
 * -> inlined as `const places: MarketPlace[]` in `js/data-core.js` (offline-safe,
 * no fetch). Also available as `web/.../data/localization/store-finder-markets.json`
 * for the fetch upgrade path.
 *
 * Fields:
 *  - `market` — registry key (e.g. "US-MW-PARKCITY-84098"); the join key for
 *    frontier lookup (`marketFeaturedFrontier[market]` -> featured frontier code).
 *  - `place` — human place label, e.g. "Park City, Utah 84098".
 *  - `retailer` — display retailer line, e.g. "Target (Kimball Junction), Walmart …".
 *  - `zip` — 5-digit ZIP string; used for geo proximity hints.
 *  - `audience` — persona line (e.g. "Mountain families … — Aaron"); used for
 *    prompt chips and coach context, not for rendering.
 *  - `message` — default campaign message / frontier tagline.
 *  - `peppers`/`cheeses`/`cue` — localization slots (region flavors + photo cue);
 *    `"—"` means "no override" (renderer keeps product default).
 *
 * Renderer degradation:
 *  - Missing `places` array -> autocomplete and flavor fallback hide quietly.
 *  - Missing `market` -> row is skipped in `featuredFrontierFor()` lookup.
 *  - Missing `place`/`retailer`/`zip`/`audience`/`message`/`peppers`/`cheeses`/`cue`
 *    -> each falls to `""` or `"—"` via `orDash()` / `String(v||"")`; never `undefined`
 *    shown. The `marketFeaturedFrontier` map owns the frontier resolution, not
 *    `places[]`, so a missing mapping never invents a frontier.
 *
 * @typedef {object} MarketPlace
 * @property {string} market
 * @property {string} [place]
 * @property {string} [retailer]
 * @property {string} [zip]
 * @property {string} [audience]
 * @property {string} [message]
 * @property {string} [peppers]
 * @property {string} [cheeses]
 * @property {string} [cue]
 */

/**
 * One market language row (market-languages seed + fetched upgrade).
 *
 * Canonical source: `data/localization/market-languages.json` (76 markets,
 * each `top_languages: MarketLang[2]` — top 2 non-English per ACS S1601
 * Language Spoken at Home + 2020 Census PL94). Also inlined as
 * `marketLangsOffline: Record<string, MarketLang[]>` in `js/data-core.js`
 * (seed + `_default` for offline) and upgraded at runtime by fetching
 * `market-languages.json` over multiple candidate URLs.
 *
 * Fields:
 *  - `lang_code` — ISO 639-1 or community code (`es`, `pt`, `zh`, `fr`, `de`,
 *    `nv` (Navajo), `vi`, `ht`, `hr`, `ja`, `ilo` …). Never validated against
 *    `CaptionLang` — that union is caption-only.
 *  - `lang_name` — display name ("Spanish", "Navajo", "Haitian Creole"...).
 *  - `translate_code` — code sent to Amazon Translate / Bedrock (usually same
 *    as `lang_code`; may differ for community codes).
 *  - `pct_home` — percent of 5+ population speaking this language at home (ACS S1601).
 *  - `machine_translate` — `false` means "human-only" (language sovereignty);
 *    e.g. Navajo in `US-SW-ALBQ` carries `machine_translate:false, review:"community"`.
 *  - `review` — `"community"` when community review is required.
 *  - `review_note` — human-readable sovereignty note (shown as caption provenance
 *    `"community-review"` badge, never a machine call).
 *
 * Renderer degradation (`KODIAK_isCommunityReview()` / `KODIAK_marketLangsFor()`):
 *  - Missing market key -> returns `marketLangsOffline._default` (es + fr).
 *  - `machine_translate===false` or `review==="community"` -> `isCommunityReview()==true`
 *    -> no live `/localize` call; caption stays English source with a
 *    community-review badge.
 *  - Missing `lang_code`/`lang_name`/`pct_home` -> row omitted from chips.
 *
 * @typedef {object} MarketLang
 * @property {string} lang_code
 * @property {string} lang_name
 * @property {string} translate_code
 * @property {number} pct_home
 * @property {boolean} [machine_translate] - false -> human-only, never machine.
 * @property {string} [review] - "community" when community review required.
 * @property {string} [review_note] - sovereignty note shown as provenance badge.
 */

/**
 * One backend platform_copy entry. Every field optional — the renderer falls
 * back to labels, then to the key itself, never to a guess.
 *
 * Canonical source: backend `/generate` response `platform_copy: Record<string,
 * PlatformCopyEntry>` keyed by platform slug (facebook/instagram/tiktok/…).
 * Not a static JSON file — it is produced per request by the Nova / Translate
 * copy pipeline and sharpened by `KODIAK_sharpenPlatformCopy` heuristics.
 *
 * Fields (all optional):
 *  - `label` — short platform label override.
 *  - `headline` / `title` / `body` / `description` / `post` — copy variants;
 *    the renderer tries `headline -> title -> body -> description -> post -> key`
 *    and shows the first non-empty string.
 *  - `hashtags` — either array of tags or a single string (split on whitespace).
 *  - `source` — provenance hint (e.g. "amazon-translate").
 *
 * Renderer degradation (`paintCopyPanel` in `campaign-sections.js`):
 *  - Missing entry for a platform -> falls to `PLATFORM_MATRIX_FALLBACK[TileSize].label`
 *    then to the ratio slug itself.
 *  - Missing `hashtags` -> no hashtag line rendered.
 *  - Empty string values -> treated as missing (trimmed length check).
 *
 * @typedef {object} PlatformCopyEntry
 * @property {string} [label]
 * @property {string} [headline]
 * @property {string} [title]
 * @property {string} [body]
 * @property {string} [description]
 * @property {string} [post]
 * @property {(string[]|string)} [hashtags]
 * @property {string} [source]
 */

/**
 * Copy-first panel argument: request inputs (driving) or backend response (used).
 *
 * Threaded through `campaign-sections.js` copy-panel helpers. `phase` tracks
 * which render step is active (`"driving"` vs `"used"`). The panel never throws
 * on live data — every field is optional and falls to a label/key chain.
 *
 * Canonical shape: ad-hoc per-request; validated by narrowing, never cast.
 * `json` carries the raw backend payload when present; `driving` carries the
 * request's `copy_driving` map.
 *
 * Renderer degradation: absent `brief`/`theme`/`market`/`place`/`products` ->
 * panel shows generic fallback copy ("—" or default frontier line).
 *
 * @typedef {object} CopyPanelArg
 * @property {string} [phase]
 * @property {(string|null)} [brief]
 * @property {(string|null)} [theme]
 * @property {(string|null)} [themeLabel]
 * @property {(string|null)} [market]
 * @property {(string|null)} [place]
 * @property {string[]} [products]
 * @property {unknown} [driving]
 * @property {unknown} [json]
 */

/**
 * Backend provenance envelope. Every field is optional — an absent field
 * reads "not reported", never a guess (narrowing, not casting, at each use).
 *
 * Canonical source: backend `/generate` top-level `provenance: Provenance`
 * (and `provenanceHeuristics` for the dashboard). The envelope records the
 * R&D rung, engine, seed selection, copy owner, and the request's prompt/model
 * lineage so the provenance panel and the debug overlay can explain what ran.
 *
 * Degradation: the provenance panel checks each field with `typeof x==="string"`
 * before rendering; missing fields simply omit their badge line. `incoming_prompt`
 * / `headline` / `model` / `scene_prompt` / `control_strength` / `overlay_applied`
 * / `paper_overlay` / `ratios` may be any shape or absent — displayed via
 * `String(v)` only when present and non-empty.
 *
 * @typedef {object} Provenance
 * @property {string} [rung]
 * @property {string} [engine]
 * @property {string} [origin]
 * @property {string} [seed_selection]
 * @property {string} [seed_source]
 * @property {string} [fallthrough_reason]
 * @property {string} [copy_owner]
 * @property {string[]} [platforms]
 * @property {string[]} [languages]
 * @property {string} [retailer]
 * @property {string} [recipe]
 * @property {string} [mode]
 * @property {unknown} [incoming_prompt]
 * @property {unknown} [headline]
 * @property {unknown} [model]
 * @property {unknown} [scene_prompt]
 * @property {unknown} [control_strength]
 * @property {unknown} [overlay_applied]
 * @property {unknown} [paper_overlay]
 * @property {unknown} [ratios]
 * @property {unknown} [recipe_pairing] - season-pairing record the request season resolved to.
 */

/**
 * One backend render row (ratio slug + image url; dims ride along when known).
 *
 * Canonical source: backend `/generate` `renders: RenderItem[]`. Each row maps
 * 1:1 to a `TileSize` via `ratio` (validated by `tileSizeFromString()` before
 * indexing `PLATFORM_MATRIX_FALLBACK` / `RATIO_LABELS`). `image_url` is the
 * only required field; `w`/`h` may be missing or non-number while a guard
 * validates them.
 *
 * Degradation (`KODIAK_showRenderSet`): row with missing/invalid `ratio` or
 * empty `image_url` is skipped (never a broken tile). Missing `w`/`h` -> dims
 * fall to the `PlatformRow` fallback dims. `s3_uri` (when present) is used for
 * the download pack provenance, not for rendering.
 *
 * @typedef {object} RenderItem
 * @property {string} ratio — ratio slug, validated as TileSize before use.
 * @property {string} image_url — required presigned URL; empty -> row skipped.
 * @property {unknown} [w] - width hint; non-number -> fallback dims.
 * @property {unknown} [h] - height hint; non-number -> fallback dims.
 * @property {string} [s3_uri] - canonical S3 URI for the pack manifest.
 */

/**
 * Render options: grid vs hero, theme line, provenance for the badge.
 *
 * Canonical flow: constructed in `js/generate.js` `oneGenerate()` from the
 * request state and the backend `provenance`; passed to `KODIAK_showRenderSet()`
 * alongside `RenderItem[]`. Every field is `unknown` because it crosses a JSON
 * or DOM boundary and must be narrowed.
 *
 * Degradation: missing `grid`/`append`/`theme`/`provenance` -> sensible defaults
 * (grid layout, no append, generic theme line, no badge). Never throws.
 *
 * @typedef {object} ShowOpts
 * @property {unknown} [grid]
 * @property {unknown} [append]
 * @property {unknown} [theme]
 * @property {unknown} [themeLabel]
 * @property {unknown} [productName]
 * @property {unknown} [provenance]
 * @property {unknown} [source]
 */

/**
 * Provenance-panel context: what the requester provided.
 *
 * Canonical source: assembled in `js/generate.js` from `__selectedLayers()`,
 * `__activeRetailerValue()`, `__activeTheme`, and the copy panel's
 * `driving` map. Fed to `__kodiakUpdateProvenanceCopy()` so the panel can
 * explain the request provenance (brief, theme, market, product, platformCopy).
 *
 * Degradation: missing keys -> panel shows the honest "not reported" state
 * (narrowing guard, never a cast).
 *
 * @typedef {object} ProvCtx
 * @property {unknown} [brief]
 * @property {unknown} [themeLabel]
 * @property {unknown} [theme]
 * @property {unknown} [market]
 * @property {unknown} [product]
 * @property {unknown} [platformCopy]
 */

/**
 * One catalog product (kodiak-full-catalog.json). Only name is required —
 * the offline fallback seeds {name} stubs and everything downstream
 * treats the rest as optional.
 *
 * Canonical sources:
 *  - Authoritative: `data/products/kodiak-full-catalog.json` (88 products,
 *    metadata + products[] + amazon_listings + brand_lore).
 *  - Web copy: `web/.../data/products/kodiak-full-catalog.json` (same).
 *  - Fetched at runtime by `js/generate.js#loadCatalog()` over 4 candidate
 *    URLs; on success `window.skuCatalog = SkuEntry[]` and `skuList` is derived.
 *  - Offline seed: `js/generate.js#skuList` (18 hardcoded names) is the fallback
 *    when the fetch fails — those entries become `SkuEntry` stubs `{name}`.
 *
 * Fields:
 *  - `name` — display name, the only required field (e.g.
 *    "Buttermilk Power Cakes Flapjack & Waffle Mix").
 *  - `handle` — URL slug / SKU handle (e.g. "buttermilk-power-cakes").
 *  - `category` — merchandising category ("baking-mixes", "muffins"…).
 *  - `images` — CDN image URLs (may be [] or missing).
 *  - `img` — legacy single-image alias (prefer `images[0]`).
 *  - `price_usd` — string price (e.g. "6.45"); missing -> no price chip.
 *
 * Renderer degradation (`js/generate.js` product chooser):
 *  - Empty fetch / offline -> chooser renders the 18-item `skuList` as plain
 *    checkboxes with `window.skuCatalog = [{name}]` stubs, `hint` says
 *    "18 SKUs (offline)".
 *  - No-match filter -> falls back to first 12 SKUs (chooser never blank).
 *  - Checked SKUs outside the filter ride along on top via `preserveChecked()`
 *    so typing a second product never destroys the first pick.
 *  - Missing `images`/`price_usd` -> no image / no price badge, never broken.
 *
 * @typedef {object} SkuEntry
 * @property {string} name
 * @property {string} [handle]
 * @property {string} [category]
 * @property {string[]} [images]
 * @property {string} [img]
 * @property {unknown} [price_usd]
 */

/**
 * Backend /generate response as oneGenerate guarantees it: image_url is
 * required (it throws otherwise) and everything else degrades through the
 * fallbacks in paintCopyPanel / showRenderSet.
 *
 * Canonical source: `POST /generate` (GlimmerProxy / Bedrock nova render).
 * Validated in `js/generate.js#oneGenerate()` — `image_url` missing/empty
 * throws and the caller never reaches `KODIAK_showRenderSet()`; all other
 * fields are optional and flow through the panel/matrix fallbacks.
 *
 * Fields:
 *  - `image_url` — required presigned URL for the hero tile.
 *  - `theme`/`source`/`headline`/`message` — optional copy seeds.
 *  - `renders` — optional multi-ratio set (each `RenderItem`); valid rows are
 *    rendered, invalid rows are dropped.
 *  - `provenance` / `platform_copy` — optional envelopes (see `Provenance`
 *    and `PlatformCopyEntry`); absent -> provenance badge hidden / copy falls
 *    to labels-then-key chain.
 *
 * Renderer degradation: missing optional fields -> generic fallback copy and
 * fallback matrix dims; never synthesized or guessed.
 *
 * @typedef {object} BackendResponse
 * @property {string} image_url
 * @property {string} [theme]
 * @property {string} [source]
 * @property {string} [headline]
 * @property {string} [message]
 * @property {RenderItem[]} [renders]
 * @property {unknown} [provenance]
 * @property {unknown} [platform_copy]
 */

/**
 * One canonical month entry used by both gallery and brainstorm renderers.
 *
 * The 12 months in `js/recipes.js` / `js/recipe-cards.js` `MONTHS[]` are
 * typed as `MonthEntry[]` and drive the grid's sorted iteration and seasonal
 * badges. `key` is the gallery's map key (e.g. `"2026-01"`), matching
 * `MonthCard.month` and `FrontierPair.monthly` keys; `name`/`short` are display;
 * `season` is the structured tag (winter/spring/summer/fall).
 *
 * Degradation: unknown month string -> `MONTH_TO_KEY` miss -> gallery shows the
 * honest "no card for this season" state (seasons/holidays have no card keys,
 * 12 month keys only), never a guessed card.
 *
 * @typedef {{key: string, name: string, short: string, season: Season}} MonthEntry
 */

(function () {
  'use strict';

  // contracts start

  /**
   * Every export size the frontier renders, shortest first. The DOM order of
   * #previewHero .render-tile blocks MUST match this array (asserted in
   * frontier-contracts.test.mjs) — reorder here, not by dragging markup.
   * @type {TileSize[]}
   */
  var TILE_ORDER = ['blog', '1x1', '16x9', '4x5', '9x16'];
  // NOTE: TileSize also covers '2x3' (generated-campaign Story tile), which
  // has no resting-hero block and so stays out of the DOM order contract.

  /**
   * Tile class suffix ("r-1x1") -> TileSize. Unknown classes return null so
   * the caller keeps its fallback instead of indexing with a stranger.
   * @param {unknown} cls
   * @returns {TileSize|null}
   */
  // teaching note (frontier typeof: typeof cls === 'string' narrows unknown
  // to string — the && right side only ever sees the narrowed half).
  function tileSizeFromClass(cls) {
    var m = typeof cls === 'string' && cls.match(/(?:^|\s)r-(1x1|4x5|9x16|16x9|2x3|blog)(?:\s|$)/);
    return m ? /** @type {TileSize} */ (m[1]) : null;
  }

  /**
   * Backend ratio slug ("1x1") -> TileSize. The /generate response is external
   * code: validate before indexing PLATFORM_MATRIX_FALLBACK or RATIO_LABELS.
   * @param {unknown} ratio
   * @returns {TileSize|null}
   */
  function tileSizeFromString(ratio) {
    return ratio === '1x1' || ratio === '4x5' || ratio === '9x16' ||
      ratio === '16x9' || ratio === '2x3' || ratio === 'blog' ? ratio : null;
  }

  /**
   * Adopt a fetched platform matrix only when every key is a known TileSize
   * carrying a platforms array. Anything else -> keep the typed fallback.
   * @param {unknown} ratios
   * @param {PlatformMatrix} fallback
   * @returns {PlatformMatrix}
   */
  function adoptPlatformMatrix(ratios, fallback) {
    // teaching note (frontier truthiness: !ratios catches null, undefined, 0,
    // and '' up front — the first disjunct is truthiness, the rest are typeof guards).
    if (!ratios || typeof ratios !== 'object' || Array.isArray(ratios)) return fallback;
    var table = /** @type {Object<string, {platforms: unknown}>} */ (ratios);
    var keys = Object.keys(table);
    if (!keys.length) return fallback;
    for (var i = 0; i < keys.length; i++) {
      var row = table[keys[i]];
      if (tileSizeFromString(keys[i]) === null || !row || typeof row !== 'object' ||
        !Array.isArray(row.platforms)) return fallback;
    }
    return /** @type {PlatformMatrix} */ (ratios);
  }

  /**
   * Caption lang attribute ("es") -> CaptionLang. Tile captions carry
   * lang="en|es|pt"; anything else is a stranger, not a locale.
   * @param {unknown} lang
   * @returns {CaptionLang|null}
   */
  function localeFromLang(lang) {
    return lang === 'en' || lang === 'es' || lang === 'pt' || lang === 'zh' ? lang : null;
  }

  /**
   * Build id minted ONLY by scripts/bump-version.sh: 0.1.012-f618fd8-20260917.
   * The ?v= pins across index.html / glimmer-proxy / webmcp.json must all
   * parse AND agree (asserted in frontier-contracts.test.mjs — the stale-pin
   * incident of 2026-09-17 is why this validator exists).
   * @param {unknown} s
   * @returns {BuildId|null}
   */
  function parseBuildId(s) {
    var m = typeof s === 'string' && s.match(/^(0\.\d+\.\d+-[0-9a-f]{7}-\d{8})$/);
    return m ? /** @type {BuildId} */ (m[1]) : null;
  }

  try {
    window.KODIAK_tileSizeFromClass = tileSizeFromClass;
    window.KODIAK_tileSizeFromString = tileSizeFromString;
    window.KODIAK_adoptPlatformMatrix = adoptPlatformMatrix;
    window.KODIAK_localeFromLang = localeFromLang;
    window.KODIAK_parseBuildId = parseBuildId;
    window.KODIAK_TILE_ORDER = TILE_ORDER;
  } catch (e) { /* non-browser eval (tests) keeps the locals */ }

  // contracts end
}());
