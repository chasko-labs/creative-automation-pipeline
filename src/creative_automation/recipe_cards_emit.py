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

# The three probe markets and the full 2026 calendar. US-W-SF is the legacy alias
# resolve_this_month maps to the Pescadero pair. PROBE_MARKETS stays a named constant
# for targeted probe runs; the full universe comes from all_seeded_markets().
PROBE_MARKETS = ("US-SE-ATL", "US-W-SF", "US-MW-PARKCITY-84098")
MONTHS_2026 = tuple(f"2026-{m:02d}" for m in range(1, 13))


def all_seeded_markets() -> tuple[str, ...]:
    """The real market universe: every canonical market with >=1 non-null monthly
    ingredient. DYNAMIC — reads the retailer-frontier-pairs registry via the
    locales loader (never a hardcoded market list, never re-opening the JSON with a
    hardcoded path), so it grows as seeding continues.

    Dedup via canonical .market: locales.load_pairs indexes both `market` and
    `legacy_market` to the same FrontierPair, so iterating keys would double-count.
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
