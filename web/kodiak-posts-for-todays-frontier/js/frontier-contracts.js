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
// ---- shared vocabulary (course modules 01-02, videos 01/02/04/05) ----
// Unions, not enums, on purpose: every value here crosses a JSON or DOM
// boundary as a plain string, and a union narrows for free where an enum
// would need a cast at each crossing. See README "living examples".

/**
 * Every export size the frontier renders.
 * @typedef {'1x1'|'4x5'|'9x16'|'16x9'|'2x3'|'blog'} TileSize
 */

/**
 * Languages the tile captions actually carry (loc-line lang attributes).
 * Market lang_codes are a wider open set (ISO codes plus community codes
 * like nv) and stay plain strings — only the caption trio is closed.
 * @typedef {'en'|'es'|'pt'} CaptionLang
 */

/**
 * One value per caption language. Generic so the same shape serves caption
 * strings, label maps, and anything else the tiles weave per language.
 * @template T
 * @typedef {Object<CaptionLang, T>} Localized
 */

// teaching note (frontier closed unions: CaptionProvider names every provenance
// state the renderer assigns — no fourth string can pass the annotation below).
// decision: closed union, not string — a new state must be added here first,
// which forces the renderer branches to handle it.
/**
 * Tile caption provenance states assigned at render time (data-provider
 * attributes). Live-machine and community-authorized states are set by id in
 * the localization pass, never through the render variable.
 * @typedef {'community-review'|'pending-live'|'pending'} CaptionProvider
 */

/** @typedef {'winter'|'spring'|'summer'|'fall'} Season */

/**
 * A build id minted ONLY by scripts/bump-version.sh.
 * @typedef {string} BuildId
 */

/**
 * One row of the platform matrix: dims plus the platform slugs the tile serves.
 * @typedef {{label: string, w: number, h: number, platforms: string[]}} PlatformRow
 */

/** @typedef {Object<TileSize, PlatformRow>} PlatformMatrix */

/**
 * Generated line-art per zone; null means "not generated yet", never "".
 * @typedef {{raw_ingredient: (string|null), technique: (string|null), finished_plate: (string|null)}} RecipeArt
 */

/** @typedef {{qty_name: string, price: (string|null)}} RecipeIngredient */

/**
 * One month cell of the recipe book (videos module 05: interfaces as the
 * shape of data; optional fields stay explicit — no `any`, no guessing).
 * @typedef {object} MonthCard
 * @property {string} [ingredient]
 * @property {string} [title]
 * @property {string[]} [steps]
 * @property {Object<string,string>} [meta]
 * @property {RecipeIngredient[]} [ingredients]
 * @property {RecipeArt} [art]
 * @property {string} [substrate]
 * @property {string} [market]
 * @property {string} [month]
 * @property {string} [reason]
 * @property {Object<string,string>} [metaLabels]
 * @property {Object<string,string>} [colLabels]
 * @property {{name: string}} [recipe]
 */

/** @typedef {Object<string, Object<string, MonthCard>>} CardBook */

/**
 * Metro -> frontier pairing panel data (loose: curated by hand, so every
 * field is optional and renderers fall back honestly).
 * @typedef {object} FrontierPair
 * @property {string} [market]
 * @property {{market?: string, retailer?: string, address?: string}} [metro]
 * @property {{market?: string, place?: string, url?: string}} [frontier]
 * @property {string[]} [retailers]
 * @property {Object<string,string>} [monthly]
 * @property {MomentEntry[]} [moments]
 */

  /**
   * One curated local moment: a named event plus the months it belongs to.
   * @typedef {object} MomentEntry
   * @property {string} moment
   * @property {string} [status]
   * @property {number[]} [months]
   */

/** @typedef {{text: string, provider: string}} LocalizedCopyEntry */

/**
 * Baked per-language card entry (recipe-i18n-data.js). Only title,
 * ingredients, steps, and prep/cook/serves values translate — prices, art,
 * and meta never do.
 * @typedef {object} I18nEntry
 * @property {string} [title]
 * @property {RecipeIngredient[]} [ingredients]
 * @property {string[]} [steps]
 * @property {Object<string,string>} [meta]
 * @property {TranslationProvenance} [translation]
 */

/** @typedef {{allergen_fallback_lines: string[]}} TranslationProvenance */

/**
 * One market row of the places table (data-core.js owns it, window.places
 * publishes it for the prompt-box autocomplete and the flavor fallback).
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
 * @typedef {object} MarketLang
 * @property {string} lang_code
 * @property {string} lang_name
 * @property {string} translate_code
 * @property {number} pct_home
 * @property {boolean} [machine_translate]
 * @property {string} [review]
 * @property {string} [review_note]
 */

/**
 * One backend platform_copy entry. Every field optional — the renderer falls
 * back to labels, then to the key itself, never to a guess.
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
 * @typedef {object} Provenance
 * @property {string} [rung]
 * @property {string} [engine]
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
 */

/**
 * One backend render row (ratio slug + image url; dims ride along when known).
 * @typedef {object} RenderItem
 * @property {string} ratio
 * @property {string} image_url
 * @property {unknown} [w]
 * @property {unknown} [h]
 * @property {string} [s3_uri]
 */

/**
 * Render options: grid vs hero, theme line, provenance for the badge.
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

/** @typedef {{key: string, name: string, short: string, season: Season}} MonthEntry */

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
    return lang === 'en' || lang === 'es' || lang === 'pt' ? lang : null;
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
