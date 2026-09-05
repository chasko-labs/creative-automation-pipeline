"""Prompt/photo in -> customized branded image out (issue #39 core loop).

POST /campaigns/from-photo (alias /campaigns/from-prompt) takes a single hero source
and returns rendered, branded creative. Two entry paths, one output:

  - hero_path / asset_id given: use that already-ingested photo as the hero
    (asset_id maps to input_assets/{product}/hero.* the way #38's /assets/upload wrote it)
  - prompt only: generate a hero via generate.generate_hero (Nova Canvas, mock fallback)

The hero is then framed into the branded 1x1 (1080x1080) output via compose.compose_creative
-- the same VariantSpec/compose path suggest.py uses -- plus 9x16 and 16x9, which are the
same call with a different ratio key.

This is the tight core loop only. The 3-language / retail-lockup / recipe fan-out that the
full #39 capstone envisions is a follow-up; it is deliberately not wired here.

Offline-safe end to end: generate_hero falls back to a mock hero with no creds, compose.py
renders locally, and no AWS / live Bedrock is required. Paths returned are local.

Orchestration lives here (importable under bare python, no FastAPI); api.py carries only the
thin JSON route, mirroring how asset_pack.py splits logic from its route.
"""
from __future__ import annotations

import json
from pathlib import Path

from .compose import compose_creative
from .generate import generate_hero
from .naming import build_iso_name, slugify

# A market-less request resolves to the locked Publix market, Atlanta. The exact key is
# the one in data/localization/market-languages.json.
DEFAULT_MARKET = "US-SE-ATL"
DEFAULT_PRODUCT = "power-cakes"

# 1x1 is the goal-meeting minimum; 9x16 and 16x9 are the same compose call re-issued.
RATIOS = ["1x1", "9x16", "16x9"]

# EN base message baked onto the creative (suggest.py's fallback brand voice).
BASE_MESSAGE = (
    "KODIAK CAKES\u00ae \u2014 Feeding Epic Days & Wilder Lives. "
    "Nourishment for Today's Frontier"
)

_MARKET_LANGS = (
    Path(__file__).parents[2] / "data" / "localization" / "market-languages.json"
)


def _load_markets() -> list[dict]:
    if not _MARKET_LANGS.exists():
        return []
    try:
        return json.loads(_MARKET_LANGS.read_text(encoding="utf-8")).get("markets", [])
    except Exception:
        return []


def _market_entry(market: str) -> dict | None:
    """Exact-key lookup of a market record in market-languages.json."""
    for m in _load_markets():
        if m.get("market") == market:
            return m
    return None


def resolve_hero(
    asset_id: str | None,
    hero_path: str | None,
    product: str,
    input_assets_root: Path,
) -> Path | None:
    """Resolve the hero photo to an existing file, or None if neither input resolves.

    hero_path wins when it points at an existing file. Otherwise an asset_id is mapped
    to input_assets/{product}/hero.* the same way #38's POST /assets/upload wrote it
    (canonical hero.{ext} in the product dir, then an id-suffixed archive copy).
    """
    if hero_path:
        p = Path(hero_path)
        if not p.is_absolute():
            # accept repo-relative and input-assets-relative spellings
            for cand in (p, Path(input_assets_root).parent / p, input_assets_root / p):
                if cand.exists():
                    return cand
        elif p.exists():
            return p

    if asset_id:
        product_slug = slugify(product) or DEFAULT_PRODUCT
        product_dir = Path(input_assets_root) / product_slug
        for ext in ("png", "jpg", "jpeg", "webp"):
            cand = product_dir / f"hero.{ext}"
            if cand.exists():
                return cand
        for ext in ("png", "jpg", "jpeg", "webp"):
            cand = product_dir / f"hero-{asset_id}.{ext}"
            if cand.exists():
                return cand

    return None


def build_image_from_photo(
    *,
    asset_id: str | None,
    hero_path: str | None,
    prompt: str | None,
    market: str | None,
    product: str | None,
    input_assets_root: Path,
    out_root: Path,
    ratios: list[str] | None = None,
) -> dict | None:
    """Core loop: resolve-or-generate a hero, frame it into branded creative.

    Returns {image_path, images[], pack_url_or_local, manifest} on success, or None
    when neither a usable hero nor a prompt is supplied (caller turns None into a 400).

    out_root is a staging dir the caller owns. No AWS / live Bedrock required: an absent
    hero with a prompt generates a mock hero offline, and compose.py renders locally, so
    pack_url_or_local is always a local path in the offline path.
    """
    market = market or DEFAULT_MARKET
    product_slug = slugify(product or DEFAULT_PRODUCT) or DEFAULT_PRODUCT
    out_root = Path(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    ratios = ratios or RATIOS

    market_entry = _market_entry(market)
    place = (market_entry or {}).get("place", market)
    locality = slugify(place) or "national"

    notes: list[str] = []
    hero_source = "existing-photo"

    # --- resolve the hero: uploaded photo first, else generate from the prompt ---- #
    hero = resolve_hero(asset_id, hero_path, product_slug, input_assets_root)

    if hero is None:
        if not (prompt and prompt.strip()):
            # neither a resolvable hero nor a prompt -> caller returns 400
            return None
        hero_out = out_root / "hero" / f"hero-{product_slug}.png"
        generated, gen_source, _prov = generate_hero(
            product_id=product_slug,
            product_name=product_slug.replace("-", " ").title(),
            brief_msg=prompt.strip(),
            region=market,
            audience="frontier households",
            out_path=hero_out,
        )
        hero = generated
        hero_source = f"generated:{gen_source}"
        if gen_source == "mock":
            notes.append(
                "hero generated by the offline mock (no Bedrock creds) -- set AWS creds "
                "for a live Nova Canvas hero"
            )

    if not hero.exists():
        return None

    # --- frame the hero into branded creative at each ratio ----------------------- #
    images: list[dict] = []
    social_dir = out_root / "social"
    for ratio in ratios:
        iso_name = build_iso_name(
            product=product_slug,
            region=market,
            locality=locality,
            channel="instagram",
            ratio=ratio,
        )
        out_path = social_dir / iso_name
        compose_creative(
            hero_path=hero,
            out_path=out_path,
            message=BASE_MESSAGE,
            ratio_key=ratio,
        )
        images.append(
            {"ratio": ratio, "iso_name": iso_name, "image_path": str(out_path)}
        )

    manifest = {
        "market": market,
        "market_key": market_entry.get("market") if market_entry else market,
        "market_known": market_entry is not None,
        "place": place,
        "product": product_slug,
        "hero": str(hero),
        "hero_source": hero_source,
        "ratios": [img["ratio"] for img in images],
        "iso_names": [img["iso_name"] for img in images],
        "notes": notes,
    }

    return {
        "image_path": images[0]["image_path"],
        "images": images,
        # offline core loop returns a local pack root (dir holding the rendered images);
        # no S3 upload in this pass -- the DAM pack/presign is the follow-up fan-out
        "pack_url_or_local": str(social_dir),
        "manifest": manifest,
    }
