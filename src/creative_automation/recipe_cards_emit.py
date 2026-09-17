"""Precomputed recipe card-DATA emit for the offline Recipes tab.

The kodiak-dev Recipes tab is offline (file://) and cannot call Python live, so
this builds a {market: {month: card_data}} matrix via build_recipe_card_data and
writes it as a JS data file that assigns window.KODIAK_RECIPE_CARDS, matching the
existing window.KODIAK_* offline pattern (web/.../js/data-core.js). Months with no
seeded ingredient emit the honest no-ingredient shape rather than being dropped, so
the frontend can render an honest empty state.

Deterministic: same markets x months -> byte-identical file. The payload carries no
timestamps; only a static build-comment line precedes the assignment.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

from . import locales
from .locales import resolve_this_month
from .recipe_card import build_recipe_card_data

_ROOT = Path(__file__).parents[2]
RECIPE_CARDS_JS_PATH = (
    _ROOT
    / "web"
    / "kodiak-posts-for-todays-frontier"
    / "js"
    / "recipe-cards-data.js"
)
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
_META_LABEL_SOURCE = (
    ("prep", "Prep time"),
    ("cook", "Cook time"),
    ("serves", "Servings"),
    ("est_cost", "Estimated cost"),
    ("ingredients", "Ingredients"),
    ("steps", "Steps"),
)


# The three probe markets and the full 2026 calendar. US-W-SF is its own market
# since the 2026-09-15 reassignment (frontier sister Castroville), not a Pescadero
# alias. PROBE_MARKETS stays a named constant for targeted probe runs; the full
# universe comes from all_seeded_markets().
PROBE_MARKETS = ("US-SE-ATL", "US-W-SF", "US-MW-PARKCITY-84098")
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
    """
    seen: set[str] = set()
    for pair in locales.load_pairs().values():
        if pair.market in seen:
            continue
        if any(v for v in pair.monthly_ingredients.values()):
            seen.add(pair.market)
    return tuple(sorted(seen))


# Convenience: the full dynamic universe, evaluated at import. main() calls
# all_seeded_markets() directly so a mid-process re-seed is picked up, but this
# gives callers a ready handle to the breadth.
ALL_MARKETS = all_seeded_markets()


def _ingredient_seed(slug: str) -> int:
    """Deterministic Nova seed from an ingredient slug so re-runs reproduce the same
    drawing. hashlib (not builtin hash, which is salted per-process) keeps it stable
    across processes; bounded to Nova's valid seed range [0, 2147483646]."""
    digest = hashlib.sha256(slug.encode("utf-8")).hexdigest()
    return int(digest, 16) % 2147483646


def _resolve_ingredient(market: str, month: str) -> str | None:
    """The in-season ingredient for a (market, month), or None. Single source of
    truth is locales.resolve_this_month — never fabricated here."""
    resolved = resolve_this_month(market, ym=month)
    if resolved is None:
        return None
    return resolved.get("ingredient") or None


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
    """
    from . import dam as _dam
    from .recipe_art import art_slug_candidates, generate_recipe_art

    art_by_slug: dict[str, dict[str, str | None]] = {}
    for market in markets:
        for month in months:
            ingredient = _resolve_ingredient(market, month)
            if not ingredient:
                continue
            candidates = art_slug_candidates(ingredient)
            slug = candidates[0]
            if slug in art_by_slug:
                continue  # already handled this ingredient this run
            zone_urls: dict[str, str | None] = {}
            seed = _ingredient_seed(slug)
            for zone in zones:
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
                local = generate_recipe_art(ingredient, zone, seed=seed)
                if local is None:
                    zone_urls[zone] = None
                    continue
                # new drawings publish under the canonical (paren-stripped) slug so
                # qualifier variants share one object instead of forking per note.
                url = _dam.upload_recipe_art(local, candidates[-1], zone)
                zone_urls[zone] = url
            art_by_slug[slug] = zone_urls
    return art_by_slug


# Opt-in generate-on-missing for emit-only runs: when set, _load_seeded_art
# generates (and publishes) art for zone objects that do not exist yet
# instead of leaving null -> SVG placeholder. Default OFF so a plain emit
# can never spend. Same escalation + gate as seed_recipe_art.
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
    and published under the canonical slug, exactly as seed_recipe_art does."""
    from . import dam as _dam
    from .recipe_art import ZONES, art_slug_candidates, generate_recipe_art

    if generate_missing is None:
        generate_missing = GENERATE_MISSING_ART

    art_by_slug: dict[str, dict[str, str | None]] = {}
    for market in markets:
        for month in months:
            ingredient = _resolve_ingredient(market, month)
            if not ingredient:
                continue
            candidates = art_slug_candidates(ingredient)
            slug = candidates[0]
            if slug in art_by_slug:
                continue
            zone_urls: dict[str, str | None] = {}
            seed = _ingredient_seed(slug)
            for zone in ZONES:
                hit = next(
                    (c for c in candidates if _dam.recipe_art_exists(c, zone)),
                    None,
                )
                if hit is not None:
                    zone_urls[zone] = _dam.recipe_art_site_url(hit, zone)
                    continue
                if not generate_missing:
                    continue
                local = generate_recipe_art(ingredient, zone, seed=seed)
                if local is None:
                    continue
                url = _dam.upload_recipe_art(local, candidates[-1], zone)
                if url:
                    print(f"[load] generated missing s3 recipe-art {candidates[-1]}/{zone}")
                zone_urls[zone] = url
            if zone_urls:
                art_by_slug[slug] = zone_urls
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
    """
    from .recipe_art import slugify

    art_by_slug = art_by_slug or {}
    matrix: dict[str, dict[str, dict]] = {}
    for market in markets:
        by_month: dict[str, dict] = {}
        for month in months:
            ingredient = _resolve_ingredient(market, month)
            art = art_by_slug.get(slugify(ingredient)) if ingredient else None
            by_month[month] = build_recipe_card_data(market, month=month, art=art)
        matrix[market] = by_month
    return matrix


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
    """
    if art_by_slug is None:
        art_by_slug = _load_seeded_art(markets, months)
    matrix = build_recipe_cards_matrix(markets, months, art_by_slug)
    payload = json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True)
    out = Path(out_path) if out_path else RECIPE_CARDS_JS_PATH
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
    """
    from . import recipe_i18n as _i18n
    from .locales import resolve_target_languages

    # wrap whatever translate entry the i18n module currently binds (real
    # provider chain, or a test stub) so memoization never bypasses it.
    real_translate = _i18n.translate_with_provenance
    memo: dict[tuple[str, str], tuple[str, str, bool]] = {}

    def _cached(text: str, target_lang: str, region: str = "US"):
        key = (text, target_lang)
        if key not in memo:
            memo[key] = real_translate(text, target_lang, region)
        return memo[key]

    from .recipe_i18n import allergen_ok

    def _meta_value(text: str | None, target_lang: str, region: str) -> str | None:
        """Translate one meta-bar value with the same allergen fail-safe as
        body lines. est_cost never reaches here (universal figure)."""
        if not text:
            return text
        out, _provider, _proven = _cached(text, target_lang, region)
        if out != text and not allergen_ok(text, out, target_lang):
            return text
        return out

    _i18n.translate_with_provenance = _cached  # type: ignore[method-assign]
    try:
        book: dict[str, dict[str, dict[str, dict]]] = {}
        labels: dict[str, dict[str, str]] = {}
        for market in sorted(markets):
            langs = [
                lang.get("translate_code", "")
                for lang in resolve_target_languages(market)
                if lang.get("translate_code", "") and lang.get("translate_code") != "en"
            ]
            if not langs:
                continue
            by_month: dict[str, dict[str, dict]] = {}
            for month in months:
                en_card = build_recipe_card_data(market, month=month)
                if not en_card.get("ingredient"):
                    continue  # no seeded ingredient — nothing to translate
                en_meta = en_card.get("meta") or {}
                per_lang: dict[str, dict] = {}
                for lang in langs:
                    card = build_recipe_card_data(market, month=month, lang=lang)
                    per_lang[lang] = {
                        "title": card.get("title"),
                        "ingredients": card.get("ingredients"),
                        "steps": card.get("steps"),
                        "meta": {
                            key: _meta_value(en_meta.get(key), lang, market)
                            for key in ("prep", "cook", "serves")
                        },
                        "translation": (card.get("provenance") or {}).get("translation"),
                    }
                    if lang not in labels:
                        labels[lang] = {
                            key: _cached(source, lang, market)[0]
                            for key, source in _META_LABEL_SOURCE
                        }
                if per_lang:
                    by_month[month] = per_lang
            if by_month:
                book[market] = by_month
    finally:
        _i18n.translate_with_provenance = real_translate  # type: ignore[method-assign]
    payload = json.dumps(book, ensure_ascii=False, indent=2, sort_keys=True)
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
    """
    from . import dam as _dam
    from .recipe_art import art_slug_candidates

    distinct: dict[str, list[str]] = {}
    filled_cells = 0
    for market in markets:
        for month in months:
            ingredient = _resolve_ingredient(market, month)
            if not ingredient:
                continue
            filled_cells += 1
            cands = art_slug_candidates(ingredient)
            distinct.setdefault(cands[0], cands)

    with_art = sum(
        1
        for cands in distinct.values()
        if any(_dam.recipe_art_exists(c, "raw_ingredient") for c in cands)
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
    """
    markets = all_seeded_markets()
    art = seed_recipe_art(markets, MONTHS_2026)
    path = emit_recipe_cards_js(markets, MONTHS_2026, art_by_slug=art)
    print(f"wrote {path} across {len(markets)} markets")


if __name__ == "__main__":
    main()
