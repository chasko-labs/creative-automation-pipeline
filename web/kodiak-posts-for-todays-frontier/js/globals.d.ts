/* =============================================================================
 * Ambient frontier globals — the page assembles itself from separate classic
 * scripts and fetched JSON, so the cross-file contracts live here instead of
 * in imports (course module 05: modules without a bundler; videos module 00:
 * the compile mental model — this file emits nothing, it only describes).
 *
 * Included in js/tsconfig.json so checkJs resolves every KODIAK_* read in the
 * five hand-written modules. The shapes themselves (TileSize, MonthCard,
 * CardBook, PlatformMatrix, FrontierCalendarEntry, FrontierPair, Localized,
 * CaptionLang, BuildId, SkuEntry, Provenance, RenderItem, etc.) are defined
 * in frontier-contracts.js; this file only says which globals carry them and
 * anchors each global to its canonical JSON under data/ and the renderer that
 * degrades when it is missing.
 *
 * Data-file map (canonical -> emitted JS global):
 *
 *   data/recipes/recipe-card-v1.schema.json        -> js/recipe-cards-data.js       (window.KODIAK_RECIPE_CARDS: CardBook)
 *   data/recipes/kodiak-recipes.json               -> same + web/data/recipes/...    (catalog source for recipe: {id,name})
 *   data/localization/retailer-frontier-pairs.json -> js/recipes-frontier-pairs.js   (window.KODIAK_FRONTIER_PAIRS: FrontierPair[])
 *   data/localization/store-finder-markets.json    -> js/data-core.js const places  (window.places: MarketPlace[], KODIAK_MARKET_PLACES)
 *   data/localization/market-languages.json        -> js/data-core.js marketLangs*  (KODIAK_marketLangsFor, KODIAK_isCommunityReview)
 *   data/products/kodiak-full-catalog.json         -> js/generate.js skuCatalog      (window.skuCatalog: SkuEntry[] with offline skuList stub)
 *   data/platforms/platform-matrix.json            -> fetched at runtime              (adoptPlatformMatrix -> PlatformMatrix)
 *   season-flavors.js FRONTIER_CAL (inline table)  -> window.seasonFlavorFor          (FrontierCalendarEntry windows + CLIMATE_WIN fallback)
 *   recipe-i18n pipeline (recipe_cards_emit)       -> js/recipe-i18n-data.js         (window.KODIAK_RECIPE_I18N: per-lang I18nEntry)
 *
 * Degradation invariants (see frontier-contracts.js header for the per-field
 * detail): missing global -> no throw; undefined globals show an empty state
 * or keep an offline fallback; missing subfields show em dash (—), placeholder
 * SVG, skeleton+lazy-gen, or a hidden section — never fabricated data.
 * =============================================================================
 */

interface Window {
  /**
   * The full offline card book: frontier market -> "YYYY-MM" -> MonthCard.
   *
   * Canonical: `data/recipes/recipe-card-v1.schema.json` (schema `recipe-card@v1`)
   * emitted deterministically by `creative_automation.recipe_cards_emit` into
   * `js/recipe-cards-data.js` and mirrored as
   * `web/.../data/recipes/kodiak-recipes.json` for file:// offline.
   *
   * Shape: `CardBook` = `Record<string, Record<string, MonthCard>>`.
   * Key is the frontier market id (e.g. `"US-CA-CASTROVILLE"`), not the metro
   * picker key — `data-core.js#marketFeaturedFrontier` maps the picker to the
   * frontier key when they differ (e.g. `"US-MW-PARKCITY-84098"` -> frontier).
   * Each month value is a `MonthCard` (see frontier-contracts.js): `ingredient`
   * is the in-season pick (null -> empty state), `title`/`steps`/`meta`/
   * `ingredients`/`art`/`recipe` carry the real catalog data + provenance.
   *
   * Consumers: `js/recipe-cards.js#buildMarketGroup()` and `js/recipes.js`.
   * Degradation: `undefined` (script not yet loaded, file:// before data) ->
   * gallery shows graceful empty state, never throws. Missing market/month key
   * -> `selectedCardMarket()` / `MONTH_TO_KEY` misses -> honest "no card for
   * this season" state. Individual `MonthCard` missingness is handled per
   * `MonthCard` (orDash, placeholder SVG, buildEmptyStateCard).
   */
  KODIAK_RECIPE_CARDS?: CardBook;
  /**
   * Metro -> frontier pairing panels (the retail -> farm-sister link).
   *
   * Canonical: `data/localization/retailer-frontier-pairs.json` (76 pairs,
   * schema `retailer-frontier-pairs-v1.json`) emitted via
   * `scripts/emit_frontier_pairs_js.py` into `js/recipes-frontier-pairs.js`.
   * Each element is a `FrontierPair` (see frontier-contracts.js).
   *
   * Consumers: `js/recipes.js` brainstorm renderer (ingredient matrix +
   * pairing panels).
   * Degradation: `undefined` -> ingredient matrix + pairing sections hidden,
   * no throw. Individual `FrontierPair` missing subfields -> em dash / hidden
   * moments section (see `FrontierPair` / `MomentEntry` docs).
   */
  KODIAK_FRONTIER_PAIRS?: FrontierPair[];
  /**
   * Market places lookup: market key -> place label (human display).
   *
   * Canonical: `data/localization/store-finder-markets.json` (77+ markets)
   * inlined in `js/data-core.js` as `const places: MarketPlace[]` and published
   * as `window.places`; this map is the derived index built from the same rows.
   *
   * Degradation: `undefined` -> prompt-box autocomplete falls back to the
   * inlined `places[]` or to an empty suggest list; no throw.
   */
  KODIAK_MARKET_PLACES?: Record<string, string>;
  /**
   * Baked per-market per-language copy seed (resting-preview localization).
   *
   * Canonical: `js/data-core.js` seed for `US-MW-PARKCITY-84098` (es/de/pt with
   * `provider:"seed"`) plus runtime upgrades from
   * `data/localization/market-languages.json` and the live `/localize` table
   * (`localization-memory` DynamoDB). Shape: `Record<market, Record<langCode,
   * LocalizedCopyEntry>>` where `LocalizedCopyEntry = {text, provider}`.
   *
   * Degradation: missing market/lang entry -> renderer keeps English source and
   * shows the "showing English source only" note; `provider:"seed"` is treated
   * as real text (no note). Community-review languages (`nv`) never receive
   * machine text here.
   */
  KODIAK_LOCALIZED_COPY?: Record<string, Record<string, LocalizedCopyEntry>>;
  /**
   * Live localization endpoint URL (Bedrock Nova Micro + Amazon Translate).
   *
   * When `undefined` or fetch fails, the app stays on offline seeds + English
   * source — never a throw. The provider badge shows `pending` / `pending-live`
   * accordingly (see `CaptionProvider`).
   */
  KODIAK_LOCALIZE_ENDPOINT?: string;
  /** Entrypoint that paints the brainstorm page (js/recipes.js); missing -> no-op. */
  KODIAK_renderRecipesBrainstorm?: () => void;
  /**
   * Baked per-card per-month per-language translations (machine, not human).
   *
   * Canonical: `js/recipe-i18n-data.js` (`window.KODIAK_RECIPE_I18N`) as
   * `Record<market, Record<monthKey, Record<langCode, I18nEntry>>>` built by
   * `recipe_cards_emit` (`kodiak/recipe-card-i18n@v1`). Only `title`,
   * `ingredients[].qty_name`, `steps`, and `meta.{prep,cook,serves}` translate;
   * prices, art, and `est_cost` never do. Allergen-bearing lines stay English
   * via `I18nEntry.translation.allergen_fallback_lines`.
   *
   * Degradation: missing market/month/lang entry -> gallery keeps the English
   * `MonthCard` verbatim. Missing subfield inside an `I18nEntry` -> that
   * subfield keeps English; allergen fallback lines always show English.
   */
  KODIAK_RECIPE_I18N?: Record<string, Record<string, Record<string, I18nEntry>>>;
  /**
   * Optional per-market per-language meta cell label overrides.
   *
   * E.g. `KODIAK_RECIPE_META_LABELS[market][lang]` overrides the four
   * `META_CELLS` labels ("Prep"/"Cook"/"Serves"/"Est cost"). Missing -> English
   * `META_CELLS` labels. Part of `Localized` caption weaving.
   */
  KODIAK_RECIPE_META_LABELS?: Record<string, Record<string, string>>;
  /** Gallery paint entrypoint for `js/recipe-cards.js`; missing -> no-op. */
  KODIAK_renderRecipeGallery?: () => void;
  /** Legacy gallery helper kept for compatibility; missing -> no-op. */
  KODIAK_renderPreviewCard?: () => void;
  /** Returns the localized caption line for a market (data-core.js); missing -> English source. */
  KODIAK_locCaption?: (market: string) => string;
  /**
   * Tile class suffix ("r-1x1") -> TileSize. Validates a DOM class string
   * across a JSON/DOM boundary; unknown classes return null so callers keep
   * their fallback instead of indexing with a stranger. See frontier-contracts.js.
   */
  KODIAK_tileSizeFromClass?: (cls: unknown) => TileSize | null;
  // teaching note (frontier contracts: an interface can describe a callable
  // value — the signature is the contract, the window property is only where it lives).
  // decision: unknown in, TileSize|null out — callers pass strings they don't
  // own (backend slugs, DOM classes), so the signature forces the null check.
  /**
   * Backend ratio slug ("1x1") -> TileSize. Validates external `/generate`
   * slugs before indexing `PLATFORM_MATRIX_FALLBACK` or `RATIO_LABELS`.
   * Unknown string -> null. See frontier-contracts.js.
   */
  KODIAK_tileSizeFromString?: (ratio: unknown) => TileSize | null;
  /**
   * Adopt a fetched platform matrix only when every key is a known TileSize
   * carrying a `platforms` array. Anything else -> typed fallback.
   * See `PlatformRow` / `PlatformMatrix` in frontier-contracts.js.
   */
  KODIAK_adoptPlatformMatrix?: (ratios: unknown, fallback: PlatformMatrix) => PlatformMatrix;
  /**
   * Caption lang attribute ("es") -> CaptionLang. Tile captions carry
   * `lang="en|es|pt"`; anything else is a stranger, not a locale.
   * Unknown -> null -> renderer keeps English source. See `CaptionLang`.
   */
  KODIAK_localeFromLang?: (lang: unknown) => CaptionLang | null;
  /**
   * Build id minted ONLY by `scripts/bump-version.sh`: `0.1.012-f618fd8-20260917`.
   * Validates the `?v=` cache-bust pins across index.html / glimmer-proxy /
   * webmcp.json; unknown format -> null. See `BuildId`.
   */
  KODIAK_parseBuildId?: (s: unknown) => BuildId | null;
  /**
   * Every export size in DOM order for `#previewHero .render-tile` blocks.
   * Must match markup order (asserted in frontier-contracts.test.mjs).
   * `2x3` (Story) is a valid TileSize but has no resting-hero block and stays
   * out of this array per the DOM-order contract.
   */
  KODIAK_TILE_ORDER?: TileSize[];
  /** Backend provenance heuristics blob for the debug overlay; display-only. */
  KODIAK_provenanceHeuristics?: unknown;
  /** Optional caption list helper; display-only. */
  KODIAK_locCaptionList?: unknown;
  /** Renders the platform/dimension matrix panel using adopted or fallback matrix; honours degradation. */
  __renderPlatformMatrix?: () => void;
  /** Paints the resting hero previews; honours degradation (fallback dims/copy when backend absent). */
  __renderDefaultHero?: () => void;
  /** Returns the currently selected layer map (market, season, retailer, theme, etc.); missing keys -> fallback. */
  __selectedLayers?: () => Record<string, unknown>;
  /** Mock geolocation override for local preview / tests. */
  __mockGeo?: {lat: number, lon: number};
  /**
   * Live translate a string for a market via `KODIAK_LOCALIZE_ENDPOINT`.
   * Community-review languages (`nv`) never call through; they stay human-only.
   * Failure / missing endpoint -> Promise resolves null and caller keeps English.
   */
  KODIAK_localizeText?: (text: string, market: string, code: string) => Promise<string | null>;
  /**
   * Returns true when `lang` for market `code` requires community review
   * (`market-languages.json#machine_translate:false` or `review:"community"`).
   * E.g. Navajo (`nv`) in `US-SW-ALBQ`. True -> no machine call, badge shows
   * `community-review` provenance.
   */
  KODIAK_isCommunityReview?: (l: MarketLang, code: string) => boolean;
  /**
   * Market -> MarketLang[] (top 2 non-English per ACS S1601).
   * Canonical: `data/localization/market-languages.json#markets[].top_languages`
   * inlined as `marketLangsOffline` in `js/data-core.js`; upgraded at runtime
   * by fetching the JSON over several candidate URLs. Missing market -> `_default`
   * (es + fr). See `MarketLang` in frontier-contracts.js.
   */
  KODIAK_marketLangsFor?: (code: string) => MarketLang[];
  /** Currently selected retailer value from the retailer combo; null when none. */
  __activeRetailerValue?: () => string | null;
  /**
   * Live product catalog. Canonical: `data/products/kodiak-full-catalog.json`
   * (88 products) and its web copy; fetched by `js/generate.js#loadCatalog()`
   * over 4 URLs. On success carries full `SkuEntry[]`; on failure the chooser
   * still has the 18-item static `skuList` stub (`{name}`) so the UI is never
   * empty. See `SkuEntry` in frontier-contracts.js.
   */
  skuCatalog?: SkuEntry[];
  /** Scorecard dashboard renderer; `render()` is safe to call even when catalog is stub-only. */
  KODIAK_SCORECARDS?: {render: () => void};
  /** Syncs the product popover position/content; missing -> no-op. */
  __syncProductPopover?: () => void;
  /** Currently active season filter (e.g. "winter"); null -> any season (year-round). */
  __activeSeason?: string | null;
  /**
   * Season-flavors engine: market x season -> {text, source, frontier}.
   *
   * Canonical windows: `js/season-flavors.js#FRONTIER_CAL` typed as
   * `Record<string, FrontierCalendarEntry>` (the researched harvest windows;
   * see `FrontierCalendarEntry`), plus `CLIMATE_WIN` fallback per regional
   * archetype (wasatch/rockies/southwest/…/alaska). `source` is
   * `"curated"` (in-season hit), `"frontier"` (shoulder/off text), or
   * `"archetype"` (climate-window fallback); `frontier` is the feature
   * frontier place id when known. Missing market or unknown season degrades
   * to year-round / archetype, never throws.
   */
  seasonFlavorFor?: (market: string, season: string | null) => {text: string, source: string, frontier: string};
  /** Recomputes the local-flavor chip / hint after layer changes; missing -> no-op. */
  updateLocalFlavor?: () => void;
  /** Strips banned brand-lore tokens from AI copy before render; idempotent. */
  KODIAK_brandClean?: (text: string) => string;
  /**
   * Updates the provenance copy panel with backend provenance.
   * Unknown / missing copy -> panel keeps honest fallback (narrowing, not cast).
   */
  __kodiakUpdateProvenanceCopy?: (copy: unknown) => void;
  /** Reveals the generated campaign strip; missing -> no-op. */
  __kodiakRevealCampaign?: () => void;
  /** Last generation sidecar (debug overlay); display-only, may be undefined. */
  __lastSidecar?: unknown;
  /** Last asset pack manifest; display-only, may be undefined. */
  __lastPack?: unknown;
  /** Last requested SKU name; display-only. */
  __requestedSku?: unknown;
  /** Last copy-driving map that was sent to /generate; display-only. */
  __lastCopyDriving?: unknown;
  /** Sharpens backend platform_copy heuristically; display-only. */
  KODIAK_sharpenPlatformCopy?: unknown;
  /** Last resolved layer map; display-only. */
  __lastLayers?: unknown;
  /** Glimmer proxy bridge (local vs remote); `pickSkus()` is budget-aware. */
  GlimmerProxy?: {isLocal?: boolean, pickSkus?: (brief: string, skus: string[], n: number) => Promise<unknown>};
  /** User-uploaded assets for compositing; each entry needs at least `name`. */
  __userAssets?: {name: string, source?: string, key?: string}[];
  /** Scenic-bg asset key for the current brief (text-to-image scene); rides as seed_key. */
  __scenicSeedKey?: string | null;
  /** Briefs already scenic-upgraded this session (no repeat SDXL billing). */
  __scenicDoneFor?: Record<string, boolean>;
  /**
   * Inlined market places table (offline-safe). Canonical:
   * `data/localization/store-finder-markets.json` -> `js/data-core.js`
   * `const places: MarketPlace[]` published as `window.places`. Also drives
   * `marketFeaturedFrontier` mapping and the prompt-box autocomplete.
   * Missing -> features that read it hide quietly; individual `MarketPlace`
   * missing subfields fall to "" / "—" (see `MarketPlace`).
   */
  places?: MarketPlace[];
  /** Currently active theme slug; null -> no theme. */
  __activeTheme?: string | null;
  /** Last hero image URL (presigned); undefined before first generate. */
  __lastHeroUrl?: string;
  /** Last backend platform_copy payload (raw, not sharpened); display-only. */
  __lastPlatformCopy?: unknown;
  /** Last backend platform_copy JSON raw blob; display-only. */
  __lastCopyJson?: unknown;
  /** Clears the frontier-featured state; missing -> no-op. */
  __kodiakClearFFState?: () => void;
  /** Resets campaign state and clears picked SKUs; missing -> no-op. */
  KODIAK_resetCampaign?: () => void;
  /**
   * Paints the backend render set (`RenderItem[]` + `ShowOpts`).
   *
   * Canonical: backend `/generate` `renders[]` (each `RenderItem`) plus the
   * `ShowOpts` the caller builds. Valid rows are tiled; invalid rows (missing
   * `ratio` / empty `image_url` / non-TileSize slug) are dropped and the tile
   * keeps its fallback dims/copy.
   */
  KODIAK_showRenderSet?: (renders: RenderItem[], opts?: ShowOpts) => void;
  /** Upgrades tall/wide pad tiles to live outpaints as extends land; pads keep their honest mark on failure. */
  KODIAK_extendTallTiles?: (renders: RenderItem[], fields: unknown) => Promise<void>;
  /** Wires one ff-filmstrip (arrows, dots, track keys, thumb->lightbox). Idempotent. */
  KODIAK_wireFilmstrip?: (strip: HTMLElement) => void;
  /** Opens the dependency-free lightbox over a strip's items at an index. */
  KODIAK_ffLightboxOpen?: (items: Array<{src: string, alt: string, cap: string}>, index: number, opener: HTMLElement | null) => void;
  /** Triggers the asset-pack download (zip of renders + copy + provenance). */
  downloadAssetPack?: (opts?: {pack?: boolean}) => void;
  /** Frontier logger (ffLog) — noisy in dev, gated in prod. */
  ffLog?: (...args: unknown[]) => void;
  /** Campaign scope tag (e.g. frontier code) for analytics; free-form. */
  __campaignScope?: string;
  /**
   * Resting-showcase copy for a non-Park-City market (generate.js).
   * Null for Park City markets (the shipped example stays untouched).
   */
  KODIAK_restingCopyFor?: (marketId: string) => {place: string, title: string, lede: string, enLine: string} | null;
  /** Repaints resting showcase words for the selected market (generate.js); missing -> no-op. */
  KODIAK_repaintRestingShowcase?: () => void;
  /** Repaints resting showcase images for the selected market (generate.js); missing -> no-op. */
  KODIAK_repaintRestingImages?: () => void;
  /** Market x month -> size -> image URL picks from the campaign-art index (generate.js). */
  KODIAK_marketHeroPicks?: (marketId: string, month: number) => Record<string, string>;
  /** Page build stamp (?v= cache-bust); set inline, read by withVersion. */
  KODIAK_VERSION?: string;
  /**
   * Generated campaign-art index (campaign-art-index.js, GENERATED — do not
   * hand-edit the source). Kept loose: the emitted JSON shape varies by
   * season; callers narrow what they read.
   */
  KODIAK_CAMPAIGN_ART?: {markets?: Record<string, any>, season_months?: Record<string, number[]>} | null;
  /** Which tall/wide tiles earn a live outpaint (generate.js top level). */
  KODIAK_extendTargets?: (renders: unknown) => unknown[];
  /** The 1x1 hero a mode=extend derives from (generate.js top level). */
  KODIAK_extendHero?: (renders: unknown) => unknown;
  /** Builds a mode=extend request body (generate.js top level). */
  KODIAK_extendBody?: (ratio: unknown, hero: unknown, fields: unknown) => {mode: string, ratio: unknown, hero_s3_uri: unknown, subject: unknown, product: unknown, region: unknown, theme: unknown};
  /** Primary theme first, then checked cards in DOM order, deduped (generate.js top level). */
  KODIAK_orderThemes?: (primary: unknown, list: unknown) => unknown[];
  /** Per-tile engine mark {text, cls} (generate.js top level). */
  KODIAK_tileEngineMark?: (engine: unknown) => {text: string, cls: string};
  /** Rung badge {text, fallback} shared by click badge, render set, tests (generate.js top level). */
  KODIAK_rungBadge?: (source: unknown, prov: unknown) => {text: string, fallback: boolean};
  /** Checked theme slugs from the prompt chips (prompt-chips.js); missing -> []. */
  __activeThemes?: () => unknown;
  /** Month key/Season name -> 1-12 month number (data-core.js local signature, exact). */
  KODIAK_frontierMonthNum?: (monthKey: string) => number | null;
  /** Request body for one lazy art-zone generation (recipe-cards.js local signature, exact). */
  KODIAK_recipeArtBody?: (recipeId: string | null, artKey: string) => {mode: string, recipe_id: string, zone: string} | null;
}

/**
 * Farm catalog entries (`js/data-core.js` inlined farm data): products carry
 * art + base recipe so renderers can place the box and print the base without
 * guards.
 *
 * Not a standalone JSON file — the catalog lives inlined in `js/data-core.js`
 * and is also backed by `web/.../data/products/kodiak-full-catalog.json`
 * (88 products) for the live path. `js/generate.js` upgrades the inlined stub
 * when the fetch succeeds.
 *
 * - `id` — stable product id (slug-like).
 * - `name` — display name (matches `SkuEntry.name` / `MarketPlace` usage).
 * - `img` — product art URL (may be CDN; missing -> no image chip, never broken).
 * - `base` — base recipe line (e.g. `"1 cup mix + 2/3 cup milk + 1 egg"`); the
 *   renderer prints this under the box art. Missing -> empty string (no throw).
 */
interface FarmEntry {
  id: string;
  name: string;
  img: string;
  base: string;
}
/**
 * Metro places row (the named metro catalog inside `js/data-core.js`).
 *
 * Alias of `MarketPlace` (see frontier-contracts.js) with the nine fields the
 * market panel actually reads. Duplicated here for the two import styles that
 * expect either name; both describe the same underlying rows from
 * `data/localization/store-finder-markets.json` as inlined in `js/data-core.js`.
 *
 * Fields (in `places[]` order): `market`, `place`, `retailer`, `zip`,
 * `audience`, `message`, `peppers`, `cheeses`, `cue`.
 *
 * Renderer degradation: any missing string field falls to `""` or `"—"` via
 * `orDash()`; a missing `market` key causes the frontier lookup to miss and
 * the chip falls to year-round archetype copy (see `MarketPlace` + `seasonFlavorFor`).
 */
// teaching note (frontier aliases: PlaceEntry names the shape once; six
// signatures reuse it instead of spelling the object inline — the 010 composition rule).
interface PlaceEntry {
  market: string;
  place: string;
  retailer: string;
  zip: string;
  audience: string;
  message: string;
  peppers: string;
  cheeses: string;
  cue: string;
}
