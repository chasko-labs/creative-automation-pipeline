"""Precomputed recipe card-DATA emit for the offline Recipes tab.

The kodiak-dev Recipes tab is offline (file://) and cannot call Python live, so
this builds a {market: {month: card_data}} matrix via build_recipe_card_data and
writes it as a JS data file that assigns window.KODIAK_RECIPE_CARDS, matching the
existing window.KODIAK_* offline pattern (web/.../js/data-core.js). Months with no
seeded ingredient emit the honest no-ingredient shape rather than being dropped, so
the frontend can render an honest empty state.

Deterministic: same markets x months -> byte-identical file. The payload carries no
timestamps; only a static build-comment line precedes the assignment.

# === EXHAUSTIVE FLOW: ingredients / seasons -> web data files =================
# Source of truth: data/localization/retailer-frontier-pairs.json (76 pairs).
#   Each entry: {market, metro_location, frontier_sister:{place, market, ...},
#   monthly_ingredients:{YYYY-MM: ingredient|null}, seasonal_moments:[{moment,
#   available_ingredients, favorite_flavors, source, confidence, status}]}.
#   monthly_ingredients is authored per frontier from local farmers-market
#   calendars + extension-service crop calendars. Months marked null / todo are
#   honest gaps, not fabricated.
#
# Ingestion: locales.load_pairs() (data_path-aware, parents[2]/data vs
#   Lambda site-packages) loads the JSON once (lru_cache), indexes by market
#   plus legacy_market alias, returns {market: FrontierPair}. all_seeded_markets()
#   enumerates the DYNAMIC universe (distinct pair.market with >=1 non-null
#   ingredient) so the emit grows as seeding continues without a hardcoded list.
#
# Per-cell resolution: locales.resolve_this_month(market, ym=month) is the
#   SINGLE source of truth for the in-season ingredient. _resolve_ingredient()
#   is the thin wrapper used here and in seed/load/coverage. It returns None
#   for unknown market or unfilled month (caller emits honest no-ingredient
#   shape, never fabricates).
#
# Card construction: build_recipe_cards_matrix(markets, months, art_by_slug)
#   iterates markets x months, slugs the ingredient (recipe_art.slugify), looks
#   up shared art, and calls recipe_card.build_recipe_card_data(market,
#   month=month, art=art). That function re-calls resolve_this_month,
#   resolve_seasonal_moments, frontier_market_for, pick_recipe_with_provenance
#   (featured_for exact-match with paren-normalization, token overlap,
#   deterministic rotation, season-table fallback), then composes the
#   recipe-card@v1 DATA object (title/meta/ingredients/steps/art/render/
#   provenance). Seasons flow via recipe_card._seasons.resolve_season and
#   pairing_for_season (data/recipes/season-pairing); ingredients flow via
#   monthly_ingredients.
#
# Web emission:
#   emit_recipe_cards_js(markets, months) -> build_recipe_cards_matrix -> JSON
#   dumps sorted keys + indent -> writes
#   web/kodiak-posts-for-todays-frontier/js/recipe-cards-data.js as
#   window.KODIAK_RECIPE_CARDS = {market:{month:card_data}}. Deterministic,
#   no timestamp, static build comment only.
#   bake_recipe_i18n_js(markets, months) -> for each market/month with an
#   ingredient, resolve_target_languages(market) (English + market top-2 from
#   data/localization/market-languages.json), rebuild the card per
#   non-English lang, machine-translate title/ingredients/steps/meta via
#   recipe_i18n/translate (allergenic fail-safe per line, memoized), then
#   writes web/.../js/recipe-i18n-data.js as
#   window.KODIAK_RECIPE_I18N = {market:{month:{lang:{title,ingredients,
#   steps,meta,translation}}}} + window.KODIAK_RECIPE_META_LABELS.
#   The frontend preview toggle swaps languages fully offline via these
#   companion files (file://, no /localize fetch).
#
# Art: seed_recipe_art() head-checks DAM before Bedrock spend; art_by_slug
#   uses art_slug_candidates() (full slug + paren-stripped slug) so qualifier
#   variants like "pumpkins (corn maze)" reuse the base "pumpkins" drawing.
#   _load_seeded_art() is the emit-time best-effort presign path (no spend
#   unless KODIAK_RECIPE_ART_GENERATE_MISSING=1).
#
# === RESILIENT MARKET HANDLING ===============================================
# Ohio (Cincinnati/Dayton/Lebanon):
#   Cincinnati US-OH-CINCINNATI and Dayton US-OH-DAYTON both frontier_sister
#   US-OH-LEBANON (Lebanon, OH 45036 — Warren County orchard belt, Lebanon
#   Farmers Market, farms Irons Fruit Farm / Hidden Valley Orchards). That
#   market's monthly_ingredients carry qualifiers: "strawberries (late)",
#   "tomatoes (late harvest)", "maple syrup (late run)", "spring greens
#   (high tunnel)". Lebanon itself is a FEATURED FRONTIER not a selectable
#   market (marketFeaturedFrontier["US-OH-CINCINNATI"]="US-OH-LEBANON",
#   likewise Dayton; no places[] row for Lebanon) so the picker never offers
#   it alone. all_seeded_markets() emits one entry per distinct pair.market,
#   deduping the shared Lebanon via the .market field, not via load_pairs keys
#   (which double-index legacy_market). Resilient matching: recipe picking
#   strips parenthetical qualifiers and lowercases before comparing
#   featured_for, so "tomatoes (late harvest)" -> "tomatoes" matches a recipe
#   curated for "tomatoes" (exact-match bug fix in recipe_card._pick_recipe_detail).
#
# SoCal (San Diego, Oceanside, Julian):
#   San Diego metro US-W-SD frontier_sister US-CA-JULIAN (Julian, CA 92036 —
#   Cuyamaca mountain apple country, ~4200 ft, real fall apple harvest/cider
#   tradition); monthly picks like "pumpkins (Julian)", "pears (late)",
#   "citrus (from lowland San Diego County)" carry mountain/lowland notes.
#   Oceanside US-CA-OCEANSIDE is a SELF-FRONTIER (North County coast, Morning
#   Farmers Market Thu 9-1 + Sunset Market, farms Cyclops Farms/Chino Farm)
#   with qualifier-heavy picks: "strawberries (early/peak/late spring)",
#   "heirloom tomatoes (late harvest)", "citrus (Temecula/Valley Center)".
#   Both markets flow through the same normalize-then-exact-match path; art
#   candidates reuse the base slug ("heirloom tomatoes" serves all three
#   strawberry qualifiers).
#
# Georgia (Atlanta/Senoia):
#   Atlanta US-SE-ATL frontier_sister US-GA-SENOIA (Senoia, GA 30276 — Coweta
#   farm country, brick main street, Senoia Farmers Market, farms Thompson
#   Produce/Dickey Farms/Pearson Farm/Durham's Produce). Monthly picks:
#   "Vidalia onions (early)" vs "Vidalia onions" (April/May contrast),
#   muscadine grapes Sep, pecans Oct. The (early) qualifier is normalized
#   away before the curated match, so "Vidalia onions (early)" still finds a
#   recipe featuring "vidalia onions" without forking the card per note.
#
# Determinism + honesty: same markets×months always byte-identical; months with
#   no ingredient carry {ingredient:null, recipe:null, reason:...} so the
#   offline UI can render the empty state instead of crashing or inventing.
"""
from __future__ import annotations

import hashlib  # stable hash for deterministic Nova seed (hash() is salted per-process)
import json  # deterministic sort_keys dump -> byte-identical JS payload
import os  # opt-in generate-missing flag via env (no spend by default)
from pathlib import Path  # repo-root-relative JS output paths

from . import locales  # retailer-frontier registry loader (source of truth for ingredients)
from .locales import resolve_this_month  # per-cell ingredient resolver; never fabricate
from .recipe_card import build_recipe_card_data  # per-cell card DATA builder (honest no-ingredient shape)

# _ROOT is repo checkout root (src/creative_automation -> parents[2]); Lambda
# resolves data/ via _datapaths.data_path, but the web JS lives under _ROOT/web.
_ROOT = Path(__file__).parents[2]
# Precomputed matrix: window.KODIAK_RECIPE_CARDS = {market:{month:card_data}}
# Pattern-matched to window.KODIAK_* offline files in web/.../js/data-core.js
# so the file:// Recipes tab needs no live Python.
RECIPE_CARDS_JS_PATH = (
    _ROOT
    / "web"
    / "kodiak-posts-for-todays-frontier"
    / "js"
    / "recipe-cards-data.js"
)
# Baked translations: window.KODIAK_RECIPE_I18N + window.KODIAK_RECIPE_META_LABELS
# Same directory so both offline files travel together; bake is memoized per
# (source text, lang) to keep the 876-cell book cheap.
RECIPE_I18N_JS_PATH = (
    _ROOT
    / "web"
    / "kodiak-posts-for-todays-frontier"
    / "js"
    / "recipe-i18n-data.js"
)

# Label sources: the fuller phrases bake into per-language labels
# (window.KODIAK_RECIPE_META_LABELS) so short English labels never produce
# clipped verb translations. est_cost's VALUE is a universal figure and never
# translates; only its label does. Column headings ride the same table.
# Fuller source matters: "Prep time" -> Spanish "Tiempo de preparación"
# renders better than a terse "Prep" -> "Preparación" clip.
_META_LABEL_SOURCE = (
    ("prep", "Prep time"),  # meta bar column: prepTime -> "Prep time"
    ("cook", "Cook time"),  # meta bar column: cookTime -> "Cook time"
    ("serves", "Servings"),  # yield -> "Servings"
    ("est_cost", "Estimated cost"),  # label only; value ($8.40) is universal
    ("ingredients", "Ingredients"),  # section heading
    ("steps", "Steps"),  # section heading
)


# The three probe markets and the full 2026 calendar. US-W-SF is its own market
# since the 2026-09-15 reassignment (frontier sister Castroville), not a Pescadero
# alias. PROBE_MARKETS stays a named constant for targeted probe runs; the full
# universe comes from all_seeded_markets().
# Ohio Cincinnati/Dayton share Lebanon, SoCal SD->Julian/Oceanside self, Georgia
# Atlanta->Senoia are NOT probes but are covered by the dynamic universe.
PROBE_MARKETS = ("US-SE-ATL", "US-W-SF", "US-MW-PARKCITY-84098")
# Grep-friendly ISO months for the 2026 crop calendar (matches monthly_ingredients keys).
MONTHS_2026 = tuple(f"2026-{m:02d}" for m in range(1, 13))


def all_seeded_markets() -> tuple[str, ...]:
    """The real market universe: every canonical market with >=1 non-null monthly
    ingredient. DYNAMIC — reads the retailer-frontier-pairs registry via the
    locales loader (never a hardcoded market list, never re-opening the JSON with a
    hardcoded path), so it grows as seeding continues.

    Dedup via canonical .market: locales.load_pairs may index a `legacy_market`
    key to the same FrontierPair as `market`, so iterating keys would
    double-count.
    We iterate pair.market values instead, emitting one entry per distinct pair that
    has at least one filled month. Sorted for deterministic output.

    # Flow tie-in: this is the entry point for the ingredient calendar. It reads
    # data/localization/retailer-frontier-pairs.json via locales.load_pairs()
    # (which itself lru_caches the raw JSON). Each FrontierPair carries
    # monthly_ingredients: dict[str, str|None] for ISO months 2026-01..2026-12.
    # Example rows:
    #   Ohio Cincy: {"2026-09":"pawpaws", "2026-06":"strawberries (late)"}
    #   Ohio Dayton: {"2026-09":"tomatoes (late harvest)", ...}
    #   SoCal SD: {"2026-10":"pumpkins (Julian)", "2026-11":"pears (late)"}
    #   SoCal Oceanside: {"2026-09":"heirloom tomatoes (late harvest)", ...}
    #   Georgia ATL: {"2026-04":"Vidalia onions (early)", "2026-05":"Vidalia onions", ...}
    # Only markets with at least one filled month are emitted; months with null
    # stay honest gaps downstream. Includes the shared Ohio Lebanon frontier via
    # the dedup on pair.market (Cincy+Dayton both point at US-OH-LEBANON but
    # count once).
    """
    seen: set[str] = set()  # dedup by canonical market code, not by dict keys
    for pair in locales.load_pairs().values():  # values() may contain duplicates via legacy_market alias
        if pair.market in seen:
            continue  # already counted this physical frontier once
        if any(v for v in pair.monthly_ingredients.values()):  # at least one real in-season ingredient
            seen.add(pair.market)
    return tuple(sorted(seen))  # sorted -> deterministic emit order (Ohio, SoCal, Georgia stable)


# Convenience: the full dynamic universe, evaluated at import. main() calls
# all_seeded_markets() directly so a mid-process re-seed is picked up, but this
# gives callers a ready handle to the breadth.
# Example: ["US-CA-OCEANSIDE","US-OH-CINCINNATI","US-OH-DAYTON","US-SE-ATL","US-W-SD",...]
ALL_MARKETS = all_seeded_markets()


def _ingredient_seed(slug: str) -> int:
    """Deterministic Nova seed from an ingredient slug so re-runs reproduce the same
    drawing. hashlib (not builtin hash, which is salted per-process) keeps it stable
    across processes; bounded to Nova's valid seed range [0, 2147483646].

    # Why slug-based: raw ingredient strings fork on qualifiers
    # ("tomatoes (late harvest)" vs "tomatoes"), but art_slug_candidates()
    # maps them to the same canonical slug ("tomatoes") so one drawing serves
    # all qualifier variants. The seed follows the canonical slug, not the raw
    # display string, keeping the 12-month calendar stable.
    """
    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()  # stable cross-process
    return int(digest, 16) % 2147483646  # Nova Micro/Canvas seed ceiling


def _resolve_ingredient(market: str, month: str) -> str | None:
    """The in-season ingredient for a (market, month), or None. Single source of
    truth is locales.resolve_this_month — never fabricated here.

    # Thin wrapper over locales.resolve_this_month(market, ym=month) which
    # itself is pair.ingredient_for(month) against the FrontierPair loaded from
    # retailer-frontier-pairs.json. Returns None for unknown market or unfilled
    # month (the caller then emits the honest no-ingredient card shape with
    # reason, rather than inventing a pick). Used by seed, load, matrix, and
    # coverage — one resolver for the whole file.
    """
    resolved = resolve_this_month(market, ym=month)  # {market, month, ingredient, frontier_sister, ...} or None
    if resolved is None:
        return None  # no pair seeded for this market (unknown code or pre-seed)
    return resolved.get("ingredient") or None  # monthly_ingredients[ym] may be null/"" -> honest gap


def seed_recipe_art(
    markets: tuple[str, ...] | list[str],
    months: tuple[str, ...] | list[str],
    *,
    zones: tuple[str, ...] = ("raw_ingredient",),
) -> dict[str, dict[str, str | None]]:
    """Generate + upload recipe-art for every distinct in-season ingredient across
    the (market, month) grid, returning {ingredient_slug: {zone: url|None}}.

    Wave 1 prioritizes the raw_ingredient zone (default) because it is ingredient-
    keyed and dedupes best — the same ingredient across markets/months reuses one
    drawing. technique/finished_plate can be requested via zones= too.

    Dedupe + idempotence:
      - within a run, each ingredient slug is generated at most once (the returned
        map is the cache)
      - across runs, dam.recipe_art_exists head-checks the S3 key first; an existing
        object is reused (presigned, not regenerated) so re-running does not re-bill

    Offline / no-creds: generate_recipe_art returns None per zone and the url map
    carries null; the emit then embeds null and the frontend keeps its SVG
    placeholder. Never raises.

    # Ingredient -> art flow: ingredient "tomatoes (late harvest)"
    #   -> art_slug_candidates() = ["tomatoes-late-harvest", "tomatoes"]
    #   -> canonical slug = candidates[0] (full) first, then base ("tomatoes")
    #   -> _ingredient_seed(canonical_slug) -> deterministic seed
    #   -> dam.recipe_art_exists(c, zone) head-check per candidate (base hit
    #      reuses "tomatoes" drawing for the qualifier variant)
    #   -> generate_recipe_art(ingredient, zone, seed=seed) when missing
    #   -> dam.upload_recipe_art(local, candidates[-1], zone) publishes under
    #      the canonical (paren-stripped) slug so qualifier variants share one object.
    #   Covers Ohio "strawberries (late)", SoCal "pumpkins (Julian)", etc.
    """
    from . import dam as _dam  # lazy import so offline/no-DAM still imports this module
    from .recipe_art import art_slug_candidates, generate_recipe_art  # slug + Bedrock generator

    art_by_slug: dict[str, dict[str, str | None]] = {}  # ingredient_slug -> {zone: url|None}
    for market in markets:  # outer: market (e.g. US-OH-DAYTON, US-CA-OCEANSIDE, US-SE-ATL)
        for month in months:  # inner: ISO month like "2026-09" (keys into monthly_ingredients)
            ingredient = _resolve_ingredient(market, month)  # single source of truth, handles Ohio/SoCal/Georgia qualifiers
            if not ingredient:
                continue  # honest gap: no ingredient for this cell (do not fabricate)
            candidates = art_slug_candidates(ingredient)  # ["tomatoes-late-harvest", "tomatoes"] — full then base
            slug = candidates[0]  # within-run dedupe key (full slug) — qualifier variant maps to base upload later
            if slug in art_by_slug:
                continue  # already handled this ingredient this run (deduped)
            zone_urls: dict[str, str | None] = {}
            seed = _ingredient_seed(slug)  # deterministic per canonical ingredient
            for zone in zones:  # default just raw_ingredient; can include technique/finished_plate
                # idempotent skip: reuse an already-published object (no re-bill).
                # paren-qualified values fall back to the base-ingredient drawing
                # (e.g. "pumpkins (corn maze)" reuses "pumpkins").
                hit = next(
                    (c for c in candidates if _dam.recipe_art_exists(c, zone)),
                    None,
                )
                if hit is not None:
                    # permanent site url, never a presign (session-bound presigns
                    # ExpiredToken within hours and blank every card overnight).
                    zone_urls[zone] = _dam.recipe_art_site_url(hit, zone)
                    print(f"[seed] reuse existing s3 recipe-art {hit}/{zone}")
                    continue
                local = generate_recipe_art(ingredient, zone, seed=seed)  # Bedrock Nova Canvas; None offline/no-creds/heavy-ink
                if local is None:
                    zone_urls[zone] = None  # keeps key present -> frontend SVG fallback
                    continue
                # new drawings publish under the canonical (paren-stripped) slug so
                # qualifier variants share one object instead of forking per note.
                # Ohio "strawberries (late)" and "strawberries" both publish as "strawberries".
                url = _dam.upload_recipe_art(local, candidates[-1], zone)
                zone_urls[zone] = url
            art_by_slug[slug] = zone_urls
    return art_by_slug  # caller threads this into build_recipe_cards_matrix


# Opt-in generate-on-missing for emit-only runs: when set, _load_seeded_art
# generates (and publishes) art for zone objects that do not exist yet
# instead of leaving null -> SVG placeholder. Default OFF so a plain emit
# can never spend. Same escalation + gate as seed_recipe_art.
# Env is read once at import so tests can monkeypatch dam easily.
GENERATE_MISSING_ART = os.getenv("KODIAK_RECIPE_ART_GENERATE_MISSING", "") == "1"


def _load_seeded_art(
    markets: tuple[str, ...] | list[str],
    months: tuple[str, ...] | list[str],
    *,
    generate_missing: bool | None = None,
) -> dict[str, dict[str, str | None]]:
    """Best-effort: presign already-published recipe-art for every distinct
    ingredient in the grid, WITHOUT generating by default (no Bedrock spend).
    Used by emit_recipe_cards_js so an emit-only run still embeds urls for art
    seeded earlier. Missing objects yield an empty map -> null art -> SVG
    fallback — unless generate_missing (or KODIAK_RECIPE_ART_GENERATE_MISSING=1),
    in which case each missing zone object is generated via generate_recipe_art
    and published under the canonical slug, exactly as seed_recipe_art does.

    # Why not generate by default: emit_recipe_cards_js is the deterministic
    # offline build. It should never silently bill Bedrock when a pair is
    # newly seeded. The separate seed_recipe_art() step owns spend; this
    # helper just presigns what already exists (dam.recipe_art_exists +
    # dam.recipe_art_site_url) per candidate, falling back to base slug for
    # qualifiers (see art_slug_candidates doc). SoCal "heirloom tomatoes
    # (late harvest)" presigns "heirloom-tomatoes" when "heirloom-tomatoes-
    # late-harvest" is missing. Only with generate_missing=True does it
    # escalate to Bedrock and publish under the canonical slug.
    """
    from . import dam as _dam
    from .recipe_art import ZONES, art_slug_candidates, generate_recipe_art

    if generate_missing is None:
        generate_missing = GENERATE_MISSING_ART  # env default (OFF unless explicitly 1)

    art_by_slug: dict[str, dict[str, str | None]] = {}
    for market in markets:  # same grid walk as seed: markets x months
        for month in months:
            ingredient = _resolve_ingredient(market, month)  # retailer-frontier-pairs.json single source
            if not ingredient:
                continue
            candidates = art_slug_candidates(ingredient)  # full + base slug (covers Ohio/SoCal/Georgia qualifiers)
            slug = candidates[0]
            if slug in art_by_slug:
                continue  # already presigned this ingredient
            zone_urls: dict[str, str | None] = {}
            seed = _ingredient_seed(slug)  # deterministic seed per canonical ingredient
            for zone in ZONES:  # all three zones (raw_ingredient, technique, finished_plate)
                hit = next(
                    (c for c in candidates if _dam.recipe_art_exists(c, zone)),
                    None,
                )
                if hit is not None:
                    zone_urls[zone] = _dam.recipe_art_site_url(hit, zone)  # permanent URL, not presigned
                    continue
                if not generate_missing:
                    continue  # HONEST null -> frontend keeps SVG placeholder (no spend)
                local = generate_recipe_art(ingredient, zone, seed=seed)  # only when explicitly opted in
                if local is None:
                    continue  # no creds / heavy-ink rejection -> stays missing
                url = _dam.upload_recipe_art(local, candidates[-1], zone)  # canonical slug upload
                if url:
                    print(f"[load] generated missing s3 recipe-art {candidates[-1]}/{zone}")
                zone_urls[zone] = url
            if zone_urls:
                art_by_slug[slug] = zone_urls  # only emit non-empty; missing -> caller falls back to all-null
    return art_by_slug


def build_recipe_cards_matrix(
    markets: tuple[str, ...] | list[str],
    months: tuple[str, ...] | list[str],
    art_by_slug: dict[str, dict[str, str | None]] | None = None,
) -> dict[str, dict[str, dict]]:
    """Build the {market: {month: card_data}} matrix. Honest null shapes included.

    art_by_slug (optional): {ingredient_slug: {zone: url|None}} from seed_recipe_art
    (or _load_seeded_art). Each card's in-season ingredient is slugged and its art
    map looked up, then passed into build_recipe_card_data so the card carries the
    hand-drawn line-art urls. Missing => all-null art => frontend SVG fallback.

    # Core ingredient/season -> card flow:
    #   retailer-frontier-pairs.json
    #     -> locales.resolve_this_month(market, ym=month)  (this file's _resolve_ingredient)
    #     -> recipe_card.build_recipe_card_data(market, month=month, art=art)
    #       -> locales.resolve_this_month (again, honest ingredient)
    #       -> locales.resolve_seasonal_moments + season_pairing (season label)
    #       -> recipe_card.pick_recipe_with_provenance (featured_for curated
    #          with paren-normalized exact-match resilient for Ohio/SoCal/Georgia,
    #          else overlap/rotation/season-table fallback)
    #       -> recipe_card.frontier_market_for (Ohio Lebanon, SoCal Julian, Georgia Senoia)
    #       -> recipe_i18n.translate_recipe_texts when lang != en (bake only)
    #     -> card_data {market, month, season, ingredient, recipe, title, meta,
    #        ingredients, steps, art{raw_ingredient,technique,finished_plate},
    #        provenance, render, ...}
    #   The matrix keeps EVERY (market, month) cell, even when ingredient is null
    #   (then build_recipe_card_data returns the no-ingredient shape with reason),
    #   so coverage_report can count honest filled breadth vs naive N*12.
    """
    from .recipe_art import slugify  # ingredient -> S3-safe slug (lowercase, hyphenated)

    art_by_slug = art_by_slug or {}  # missing -> all-null art downstream (SVG fallback)
    matrix: dict[str, dict[str, dict]] = {}
    for market in markets:  # e.g. US-OH-CINCINNATI (Ohio), US-CA-OCEANSIDE (SoCal), US-SE-ATL (Georgia)
        by_month: dict[str, dict] = {}
        for month in months:  # e.g. "2026-04" -> "Vidalia onions (early)" for Georgia, normalized before match
            ingredient = _resolve_ingredient(market, month)  # None for unfilled month -> honest gap
            # art lookup is by slugified ingredient; "tomatoes (late harvest)" slug
            # "tomatoes-late-harvest" maps to the same base art as "tomatoes" via
            # art_slug_candidates dedup upstream, so qualifier variants share art.
            art = art_by_slug.get(slugify(ingredient)) if ingredient else None
            by_month[month] = build_recipe_card_data(market, month=month, art=art)  # honest card even when ingredient None
        matrix[market] = by_month
    return matrix  # consumed by emit_recipe_cards_js (JS serialization) and coverage_report (counts)


def emit_recipe_cards_js(
    markets: tuple[str, ...] | list[str],
    months: tuple[str, ...] | list[str],
    out_path: str | Path | None = None,
    art_by_slug: dict[str, dict[str, str | None]] | None = None,
) -> Path:
    """Build the matrix and write it as window.KODIAK_RECIPE_CARDS to a JS file.

    Deterministic: sorted keys, no timestamp in the payload. Returns the path
    written.

    art_by_slug (optional): the seed map from seed_recipe_art. When omitted, the
    emit best-effort presigns any already-published recipe-art via _load_seeded_art
    (no Bedrock spend) so an emit-only run still embeds urls for previously seeded
    art. Pass an explicit map (e.g. the seed_recipe_art return) to skip the lookup.

    # Web output: web/kodiak-posts-for-todays-frontier/js/recipe-cards-data.js
    #   // Precomputed recipe card-DATA for the offline Recipes tab (file://).
    #   window.KODIAK_RECIPE_CARDS = { "US-OH-CINCINNATI": {"2026-09": {...}}, ... };
    # The file is loaded synchronously via <script> in the offline page, so the
    # tab works under file:// with no fetch/CORS and no live Python. Matches the
    # existing offline pattern window.KODIAK_* (see web/.../js/data-core.js:
    # window.places, window.marketFeaturedFrontier). The JSON payload is sorted
    # keys + indent=2 -> git-diffable and byte-identical for same markets×months.
    # Resilient for Ohio/SoCal/Georgia because the ingredient normalization
    # happens inside build_recipe_card_data's curated match (this emit just threads
    # art and calls the builder).
    """
    if art_by_slug is None:
        art_by_slug = _load_seeded_art(markets, months)  # best-effort presign; no spend unless opted in
    matrix = build_recipe_cards_matrix(markets, months, art_by_slug)  # honest matrix, every market×month
    payload = json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True)  # deterministic, sorted for diffability
    out = Path(out_path) if out_path else RECIPE_CARDS_JS_PATH  # default web JS data file
    out.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "// Precomputed recipe card-DATA for the offline Recipes tab (file://).\n"
        "// Generated by creative_automation.recipe_cards_emit — do not edit by hand.\n"
        "// schema: kodiak/recipe-card@v1 (card-DATA, no image). Deterministic build.\n"
        f"window.KODIAK_RECIPE_CARDS = {payload};\n"
    )
    out.write_text(body, encoding="utf-8")
    return out


def bake_recipe_i18n_js(
    markets: tuple[str, ...] | list[str],
    months: tuple[str, ...] | list[str],
    out_path: str | Path | None = None,
) -> Path:
    """Bake per-market card translations to a JS file (no live endpoint).

    For every market x month card with a seeded ingredient, renders the card in
    each of the market's non-English target languages
    (locales.resolve_target_languages: English + market top-2) and stores only
    the text the preview toggle swaps: {title, ingredients, steps, translation
    provenance}. The English matrix stays byte-identical; the toggle reads this
    companion file (window.KODIAK_RECIPE_I18N) so previews switch language fully
    offline. Machine output, human_reviewed False, allergen fail-safe per line —
    same guarantees as a single translated card.

    Provider calls are memoized on (source text, lang) for the run: cards
    sharing a recipe share translations, so the full 876-cell book costs one
    distinct-line set per language, not one per cell. Deterministic: sorted
    markets, given month order, resolve_target_languages order, sorted JSON
    keys, no timestamps.

    Each per-language entry also carries the translated meta-bar values
    (prep/cook/serves; est_cost is a universal figure and never translates)
    plus the entry's translation provenance. The four meta-bar LABELS are
    baked once per language as window.KODIAK_RECIPE_META_LABELS from the
    fuller phrases ("Prep time", "Cook time", "Servings", "Estimated cost")
    so short English labels never produce clipped verb translations.

    # i18n flow (ingredients/seasons -> translations -> web):
    #   For each market in sorted(markets) (deterministic):
    #     langs = resolve_target_languages(market) non-English (e.g. ATL
    #       en+es+zh via ACS; Park City en+es+pt) — Ohio/SoCal/Georgia each
    #       get their market top-2.
    #     For each month with ingredient (honest gap skipped):
    #       en_card = build_recipe_card_data(market, month) -> English source
    #       For each lang in langs:
    #         card = build_recipe_card_data(market, month, lang=lang) -> goes
    #           through recipe_i18n.translate_recipe_texts -> translate
    #           provider chain (AWS Translate -> Nova Micro -> offline dict ->
    #           tagged passthrough) with per-line allergen_ok glossary check
    #           (milk->leche etc.; fail-safe falls back to English source line
    #           and records it in provenance.allergen_fallback_lines).
    #         Store {title, ingredients, steps, meta{prep,cook,serves},
    #                translation: provenance.translation}. Prices/meta values
    #           beyond prep/cook/serves stay universal (not translated).
    #   Also bake labels: for each distinct lang, translate the fuller phrases
    #   _META_LABEL_SOURCE ("Prep time" etc.) once via memoized
    #   translate_with_provenance -> window.KODIAK_RECIPE_META_LABELS.
    #   Memoization: memo[(text, lang)] wraps whatever translate entry the
    #   i18n module currently binds (real chain or test stub) so repeated
    #   lines across the market×month grid translate once.
    #   The English matrix (emit) stays untouched; the offline toggle reads
    #   window.KODIAK_RECIPE_I18N to swap text without a live /localize call.
    #   Ohio/SoCal/Georgia qualifier normalization lives one layer down in
    #   recipe_card picking, so the baked translations inherit the correct
    #   curated recipe per qualifier variant.
    """
    from . import recipe_i18n as _i18n  # machine translation + allergen glossary
    from .locales import resolve_target_languages  # market -> [en, top2 non-English]

    # wrap whatever translate entry the i18n module currently binds (real
    # provider chain, or a test stub) so memoization never bypasses it.
    real_translate = _i18n.translate_with_provenance
    memo: dict[tuple[str, str], tuple[str, str, bool]] = {}  # (text, lang) -> (translated, provider, proven)

    def _cached(text: str, target_lang: str, region: str = "US"):
        # Memoize on (source text, lang) so identical lines across the
        # 876-cell grid (same recipe shared by Ohio/SoCal/Georgia markets)
        # cost one provider call per distinct line, not per cell.
        key = (text, target_lang)
        if key not in memo:
            memo[key] = real_translate(text, target_lang, region)
        return memo[key]

    from .recipe_i18n import allergen_ok  # per-line safety gate (allergen glossary)

    def _meta_value(text: str | None, target_lang: str, region: str) -> str | None:
        """Translate one meta-bar value with the same allergen fail-safe as
        body lines. est_cost never reaches here (universal figure)."""
        if not text:
            return text  # null/empty stays null (honest missing prep/cook/serves)
        out, _provider, _proven = _cached(text, target_lang, region)
        if out != text and not allergen_ok(text, out, target_lang):
            return text  # allergen line failed glossary -> fail safe to English
        return out

    _i18n.translate_with_provenance = _cached  # monkeypatch for this bake run (restored in finally)
    try:
        book: dict[str, dict[str, dict[str, dict]]] = {}  # market -> month -> lang -> {title,ingredients,steps,meta,translation}
        labels: dict[str, dict[str, str]] = {}  # lang -> {prep,cook,serves,est_cost,ingredients,steps} translated labels
        for market in sorted(markets):  # sorted -> deterministic output (Ohio before SoCal before Georgia in codepoint order)
            langs = [
                lang.get("translate_code", "")
                for lang in resolve_target_languages(market)  # e.g. Atlanta en+es+zh, Oceanside en+es+zh
                if lang.get("translate_code", "") and lang.get("translate_code") != "en"
            ]
            if not langs:
                continue  # market with no non-English target (shouldn't happen; default is en/es/pt)
            by_month: dict[str, dict[str, dict]] = {}
            for month in months:  # caller order (typically MONTHS_2026)
                en_card = build_recipe_card_data(market, month=month)  # English source; also honest no-ingredient shape
                if not en_card.get("ingredient"):
                    continue  # no seeded ingredient — nothing to translate (honest gap)
                en_meta = en_card.get("meta") or {}  # prep/cook/serves/est_cost from real recipe fields or null
                per_lang: dict[str, dict] = {}
                for lang in langs:  # e.g. es, pt for Park City; es, zh for SD
                    card = build_recipe_card_data(market, month=month, lang=lang)  # -> recipe_i18n path per lang
                    per_lang[lang] = {
                        "title": card.get("title"),
                        "ingredients": card.get("ingredients"),
                        "steps": card.get("steps"),
                        "meta": {
                            key: _meta_value(en_meta.get(key), lang, market)
                            for key in ("prep", "cook", "serves")  # est_cost is universal -> excluded here
                        },
                        "translation": (card.get("provenance") or {}).get("translation"),  # {lang, providers, machine_translated,...}
                    }
                    if lang not in labels:
                        # First time we see this lang in the run, bake its meta-bar labels
                        # from the fuller source phrases so short labels never clip verbs.
                        labels[lang] = {
                            key: _cached(source, lang, market)[0]
                            for key, source in _META_LABEL_SOURCE
                        }
                if per_lang:
                    by_month[month] = per_lang  # only months with at least one lang entry
            if by_month:
                book[market] = by_month  # only markets with at least one month with ingredient
    finally:
        _i18n.translate_with_provenance = real_translate  # restore chain (important for tests that stub it)
    payload = json.dumps(book, ensure_ascii=False, indent=2, sort_keys=True)  # deterministic, preserves diacritics
    label_payload = json.dumps(labels, ensure_ascii=False, indent=2, sort_keys=True)
    out = Path(out_path) if out_path else RECIPE_I18N_JS_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    body = (
        "// Baked recipe-card translations for the preview language toggle (offline).\n"
        "// Generated by creative_automation.recipe_cards_emit — do not edit by hand.\n"
        "// schema: kodiak/recipe-card-i18n@v1. Machine-translated, human_reviewed false;\n"
        "// allergen lines fail safe to English per recipe_i18n. Deterministic build.\n"
        f"window.KODIAK_RECIPE_I18N = {payload};\n"
        "// Meta-bar labels per language (est_cost value itself is universal).\n"
        f"window.KODIAK_RECIPE_META_LABELS = {label_payload};\n"
    )
    out.write_text(body, encoding="utf-8")
    print(f"[i18n] baked {len(book)} markets, {len(memo)} distinct (text, lang) calls")
    return out


def coverage_report(
    markets: tuple[str, ...] | list[str],
    months: tuple[str, ...] | list[str],
) -> dict:
    """Read-only breadth numbers for the 100x proof — never generates.

    Walks the (market, month) grid, collects the distinct in-season ingredients,
    then head-checks the DAM (dam.recipe_art_exists) to count how many already have
    published art. total_market_months is the count of (market, month) cells that
    actually resolve to a non-null ingredient (the honest filled breadth), not the
    naive N*12.

    # Counts the honest breadth: distinct ingredients are deduped by canonical
    # slug (art_slug_candidates()[0]) so Ohio "strawberries (late)" and
    # "strawberries" collapse to one; qualifier variants do not inflate the
    # distinct count. Filled_cells counts only cells with ingredient != None,
    # so the "100x proof" is real coverage, not grid size. Art existence
    # checks per candidate fallback to base (reuses base drawing for qualifier).
    """
    from . import dam as _dam
    from .recipe_art import art_slug_candidates

    distinct: dict[str, list[str]] = {}  # canonical slug -> [full, base] candidates
    filled_cells = 0
    for market in markets:
        for month in months:
            ingredient = _resolve_ingredient(market, month)  # retailer-frontier-pairs.json single source
            if not ingredient:
                continue
            filled_cells += 1
            cands = art_slug_candidates(ingredient)  # dedup via canonical slug (full first, base fallback)
            distinct.setdefault(cands[0], cands)  # qualifier variants collapse to same key

    with_art = sum(
        1
        for cands in distinct.values()
        if any(_dam.recipe_art_exists(c, "raw_ingredient") for c in cands)  # base fallback: "pumpkins (Julian)" hits "pumpkins"
    )
    return {
        "markets": len(markets),
        "months_per_market": len(months),
        "total_market_months": filled_cells,
        "distinct_ingredients": len(distinct),
        "ingredients_with_art": with_art,
        "ingredients_without_art": len(distinct) - with_art,
    }


def main() -> None:
    """Seed recipe-art across ALL seeded markets, then emit the JS for all 12 months.

    Markets are enumerated dynamically via all_seeded_markets() (re-read here so a
    mid-run reseed is reflected), covering the full market x MONTHS_2026 breadth.
    seed_recipe_art head-checks each ingredient so already-published art is reused
    (no re-bill) and only missing ingredients generate. The emit then renders every
    card, embedding art urls where they exist and null (SVG fallback) elsewhere.

    # Ohio/SoCal/Georgia: all are included because all_seeded_markets() is
    # dynamic — Cincinnati/Dayton/Lebanon share one Lebanon frontier but count
    # once via dedup, San Diego (Julian) and Oceanside (self) both appear,
    # Atlanta (Senoia) appears. Qualifier normalization happens per-card in
    # recipe_card, so this sweep does not need per-market branching.
    """
    markets = all_seeded_markets()  # dynamic universe (one re-read after any reseed)
    art = seed_recipe_art(markets, MONTHS_2026)  # idempotent: reuses existing DAM keys, only missing art generates
    path = emit_recipe_cards_js(markets, MONTHS_2026, art_by_slug=art)  # deterministic JS assignment
    print(f"wrote {path} across {len(markets)} markets")


if __name__ == "__main__":
    main()
