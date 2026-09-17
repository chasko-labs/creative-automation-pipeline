/* Ambient frontier globals — the page assembles itself from separate classic
 * scripts and fetched JSON, so the cross-file contracts live here instead of
 * in imports (course module 05: modules without a bundler; videos module 00:
 * the compile mental model — this file emits nothing, it only describes).
 *
 * Included in js/jsconfig.json so checkJs resolves every KODIAK_* read in the
 * five hand-written modules. The shapes themselves (TileSize, RecipeCard,
 * PlatformMatrix, Localized, CaptionLang, BuildId) are defined in
 * frontier-contracts.js; this file only says which globals carry them.
 */

interface Window {
  KODIAK_RECIPE_CARDS?: CardBook;
  KODIAK_FRONTIER_PAIRS?: FrontierPair[];
  KODIAK_MARKET_PLACES?: Record<string, string>;
  KODIAK_LOCALIZED_COPY?: Record<string, Record<string, LocalizedCopyEntry>>;
  KODIAK_LOCALIZE_ENDPOINT?: string;
  KODIAK_renderRecipesBrainstorm?: () => void;
  KODIAK_RECIPE_I18N?: Record<string, Record<string, Record<string, I18nEntry>>>;
  KODIAK_RECIPE_META_LABELS?: Record<string, Record<string, string>>;
  KODIAK_renderRecipeGallery?: () => void;
  KODIAK_renderPreviewCard?: () => void;
  KODIAK_locCaption?: (market: string) => string;
  KODIAK_tileSizeFromClass?: (cls: unknown) => TileSize | null;
  // teaching note (frontier contracts: an interface can describe a callable
  // value — the signature is the contract, the window property is only where it lives).
  // decision: unknown in, TileSize|null out — callers pass strings they don't
  // own (backend slugs, DOM classes), so the signature forces the null check.
  KODIAK_tileSizeFromString?: (ratio: unknown) => TileSize | null;
  KODIAK_adoptPlatformMatrix?: (ratios: unknown, fallback: PlatformMatrix) => PlatformMatrix;
  KODIAK_localeFromLang?: (lang: unknown) => CaptionLang | null;
  KODIAK_parseBuildId?: (s: unknown) => BuildId | null;
  KODIAK_TILE_ORDER?: TileSize[];
  KODIAK_provenanceHeuristics?: unknown;
  KODIAK_locCaptionList?: unknown;
  __renderPlatformMatrix?: () => void;
  __renderDefaultHero?: () => void;
  __selectedLayers?: () => Record<string, unknown>;
  __mockGeo?: {lat: number, lon: number};
  KODIAK_localizeText?: (text: string, market: string, code: string) => Promise<string | null>;
  KODIAK_isCommunityReview?: (l: MarketLang, code: string) => boolean;
  KODIAK_marketLangsFor?: (code: string) => MarketLang[];
  __activeRetailerValue?: () => string | null;
  skuCatalog?: SkuEntry[];
  KODIAK_SCORECARDS?: {render: () => void};
  __syncProductPopover?: () => void;
  __activeSeason?: string | null;
  seasonFlavorFor?: (market: string, season: string | null) => {text: string, source: string, frontier: string};
  updateLocalFlavor?: () => void;
  KODIAK_brandClean?: (text: string) => string;
  __kodiakUpdateProvenanceCopy?: (copy: unknown) => void;
  __kodiakRevealCampaign?: () => void;
  __lastSidecar?: unknown;
  __lastPack?: unknown;
  __requestedSku?: unknown;
  __lastCopyDriving?: unknown;
  KODIAK_sharpenPlatformCopy?: unknown;
  __lastLayers?: unknown;
  GlimmerProxy?: {isLocal?: boolean, pickSkus?: (brief: string, skus: string[], n: number) => Promise<unknown>};
  __userAssets?: {name: string, source?: string, key?: string}[];
  places?: MarketPlace[];
  __activeTheme?: string | null;
  __lastHeroUrl?: string;
  __lastPlatformCopy?: unknown;
  __lastCopyJson?: unknown;
  __kodiakClearFFState?: () => void;
  KODIAK_resetCampaign?: () => void;
  KODIAK_showRenderSet?: (renders: RenderItem[], opts?: ShowOpts) => void;
  downloadAssetPack?: (opts?: {pack?: boolean}) => void;
  ffLog?: (...args: unknown[]) => void;
  __campaignScope?: string;
}

/* Farm catalog entries (data-core.js): products carry art + base recipe,
 * so renderers can place the box and print the base without guards. */
interface FarmEntry {
  id: string;
  name: string;
  img: string;
  base: string;
}
/* Metro catalog entries (data-core.js const places): the market panel reads
 * these nine fields; anything richer flows through structurally. */
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
