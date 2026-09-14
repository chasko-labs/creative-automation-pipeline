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
from pathlib import Path

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
# resolve_this_month maps to the Pescadero pair.
PROBE_MARKETS = ("US-SE-ATL", "US-W-SF", "US-MW-PARKCITY-84098")
MONTHS_2026 = tuple(f"2026-{m:02d}" for m in range(1, 13))


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
    from .recipe_art import generate_recipe_art, slugify

    art_by_slug: dict[str, dict[str, str | None]] = {}
    for market in markets:
        for month in months:
            ingredient = _resolve_ingredient(market, month)
            if not ingredient:
                continue
            slug = slugify(ingredient)
            if slug in art_by_slug:
                continue  # already handled this ingredient this run
            zone_urls: dict[str, str | None] = {}
            seed = _ingredient_seed(slug)
            for zone in zones:
                # idempotent skip: reuse an already-published object (no re-bill)
                if _dam.recipe_art_exists(slug, zone):
                    url = _dam.presign_get(_dam.recipe_art_key(slug, zone), expires=604800)
                    if url:
                        print(f"[seed] reuse existing s3 recipe-art {slug}/{zone}")
                        zone_urls[zone] = url
                        continue
                local = generate_recipe_art(ingredient, zone, seed=seed)
                if local is None:
                    zone_urls[zone] = None
                    continue
                url = _dam.upload_recipe_art(local, slug, zone)
                zone_urls[zone] = url
            art_by_slug[slug] = zone_urls
    return art_by_slug


def _load_seeded_art(
    markets: tuple[str, ...] | list[str],
    months: tuple[str, ...] | list[str],
) -> dict[str, dict[str, str | None]]:
    """Best-effort: presign already-published recipe-art for every distinct
    ingredient in the grid WITHOUT generating (no Bedrock spend). Used by
    emit_recipe_cards_js so an emit-only run still embeds urls for art seeded
    earlier. Missing objects yield an empty map -> null art -> SVG fallback."""
    from . import dam as _dam
    from .recipe_art import ZONES, slugify

    art_by_slug: dict[str, dict[str, str | None]] = {}
    for market in markets:
        for month in months:
            ingredient = _resolve_ingredient(market, month)
            if not ingredient:
                continue
            slug = slugify(ingredient)
            if slug in art_by_slug:
                continue
            zone_urls: dict[str, str | None] = {}
            for zone in ZONES:
                if _dam.recipe_art_exists(slug, zone):
                    zone_urls[zone] = _dam.presign_get(
                        _dam.recipe_art_key(slug, zone), expires=604800
                    )
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


def main() -> None:
    """Seed recipe-art for the probe markets, then emit the JS across all 12 months."""
    art = seed_recipe_art(PROBE_MARKETS, MONTHS_2026)
    path = emit_recipe_cards_js(PROBE_MARKETS, MONTHS_2026, art_by_slug=art)
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
