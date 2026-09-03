"""Campaign fan-out — one brief -> the full multi-asset campaign (agentcore D1).

This is the capstone orchestrator: it turns ONE brief sentence into the whole
product x platform x language asset set the two north-star prompts describe. It does
NOT reimplement any generation unit — it composes the done ones and records a
structured, deterministic, offline-safe plan:

    build_context_pack (A2)  -> resolve market: retailers, frontier sister, in-season
                                ingredient, dialect considerations, top-N languages
    rewrite_headline   (B1)  -> per product x platform x language headline copy,
                                dialect-correct + safety-gated (its last hop)
    build_recipe_card  (B4)  -> one recipe card per requested language for the month
    resolve_retailer + STORE_ADDRESS_SEEDS (D2 inputs) -> a retailer-lockup PLAN entry
                                per named retailer (compose_retailer_lockup is the
                                executor; this unit resolves + plans, it does not render)

Generated vs planned — stated plainly in the return so a caller never confuses a plan
for a rendered pixel:

  - recipe_cards[]  are GENERATED: build_recipe_card composes a real PNG offline (its
    image layer is a text-free brand block when no hero is on disk).
  - assets[]        are PLANNED copy+naming: headline (real, via B1), iso_name (real),
    safety verdict (real). The pixel render is a follow-on that reuses run_pipeline /
    Nova Canvas; each asset carries generated=False and render_hint="run_pipeline".
  - lockups[]       are PLANNED: resolved retailer + store address + iso_name, marked
    executor="lockup.compose_retailer_lockup". No image is baked here.

Determinism + offline: no network boundary lives in this module. B1 falls back to its
documented mock path with no AWS creds; B4 composes a local card; the lockup plan is
pure resolution. CI stays green with no credentials.

Every emitted string (headlines, card text) passes safety because it flows through B1,
and the summary re-asserts a safety verdict over the aggregate so the campaign carries
one explicit clean/redaction record.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import naming, retailers, safety
from .context_pack import build_context_pack
from .recipe_card import build_recipe_card
from .retailers import STORE_ADDRESS_SEEDS
from .text_rewriter import rewrite_headline

_ROOT = Path(__file__).parents[2]
MARKET_LANGS_PATH = _ROOT / "data" / "localization" / "market-languages.json"
PAIRS_PATH = _ROOT / "data" / "localization" / "retailer-frontier-pairs.json"
DEFAULT_OUT_DIR = _ROOT / "output" / "campaigns"

# standard platform -> ratio(s) map. instagram runs feed (1x1) + story (9x16); the
# blog hero is 16x9. keep it small + explicit so the fan-out count is predictable.
STANDARD_PLATFORMS: dict[str, list[str]] = {
    "instagram": ["1x1", "9x16"],
    "blog": ["16x9"],
}

# fallback base campaign line when a brief carries no campaign_message
_DEFAULT_MESSAGE = "Protein-packed whole grains for your frontier."


def _coerce_market(brief) -> str | None:
    """Pull the market key from a CampaignBrief, a dict, or a bare string."""
    if isinstance(brief, str):
        return brief
    if isinstance(brief, dict):
        return (
            brief.get("market")
            or brief.get("target_market")
            or brief.get("target_region")
            or brief.get("region")
        )
    # CampaignBrief exposes .region (target_market or target_region)
    return getattr(brief, "region", None)


def _brief_products(brief) -> list[dict]:
    """Normalize the brief's products to plain dicts {id, name, description}."""
    if isinstance(brief, dict):
        out: list[dict] = []
        for p in brief.get("products", []) or []:
            if isinstance(p, dict):
                out.append(
                    {
                        "id": p.get("id") or naming.slugify(p.get("name", "product")),
                        "name": p.get("name", ""),
                        "description": p.get("description", ""),
                    }
                )
        return out
    products = getattr(brief, "products", None)
    if products:
        return [
            {"id": p.id, "name": p.name, "description": p.description or ""}
            for p in products
        ]
    return []


def _brief_message(brief) -> str:
    if isinstance(brief, dict):
        return brief.get("campaign_message") or _DEFAULT_MESSAGE
    return getattr(brief, "campaign_message", None) or _DEFAULT_MESSAGE


def _brief_retailers(brief, pack: dict) -> list[str]:
    """Retailers named on the brief, else the market's paired retailer set (A2 pack)."""
    named: list[str] = []
    if isinstance(brief, dict):
        named = list(brief.get("retailers", []) or [])
    else:
        named = list(getattr(brief, "retailers", []) or [])
    if named:
        return named
    return list(pack["retailers"].get("retailers") or [])


def _resolve_languages(
    market: str, pack: dict, explicit: list[str] | None
) -> list[str]:
    """EN + the market's top-N non-English languages, unless explicitly overridden.

    The context pack already carries dialect_considerations for the market's top
    non-English languages (from market-languages.json). We layer EN in front and dedup
    while preserving order so the fan-out language set is deterministic.
    """
    if explicit:
        seen: set[str] = set()
        out: list[str] = []
        for lc in explicit:
            if lc and lc not in seen:
                seen.add(lc)
                out.append(lc)
        return out
    langs = ["en"]
    for d in pack.get("dialect_considerations", []):
        code = d.get("lang_code")
        if code and code not in langs:
            langs.append(code)
    return langs


def _resolve_platforms(
    explicit: dict[str, list[str]] | list[str] | None,
) -> dict[str, list[str]]:
    """Platform -> ratio(s). Explicit dict wins; a bare list maps each to STANDARD; else
    the STANDARD set. Ratios are canonicalized through naming.canon_ratio."""
    if isinstance(explicit, dict):
        raw = explicit
    elif isinstance(explicit, list):
        raw = {p: STANDARD_PLATFORMS.get(p, ["1x1"]) for p in explicit}
    else:
        raw = STANDARD_PLATFORMS
    out: dict[str, list[str]] = {}
    for platform, ratios in raw.items():
        out[platform] = [naming.canon_ratio(r) for r in ratios]
    return out


def _asset_locality(pack: dict, lang: str) -> str:
    """Locality field for the iso name: frontier sister (or market), lang-suffixed for
    non-English so each variant name stays unique inside the standard's field rules."""
    base = pack["retailers"].get("frontier_sister") or pack["market"]
    locality = naming.slugify(base) or "national"
    return locality if lang == "en" else f"{locality}-{lang}"


def _plan_assets(
    products: list[dict],
    platforms: dict[str, list[str]],
    languages: list[str],
    market: str,
    base_message: str,
    pack: dict,
    month: str | None,
) -> tuple[list[dict], list[dict]]:
    """Fan out product x platform x ratio x language into planned asset entries.

    Each entry carries the B1 headline (real copy, safety-gated), the real iso name,
    the safety verdict, and generated=False (pixel render is a run_pipeline follow-on).
    Returns (assets, safety_redactions).
    """
    assets: list[dict] = []
    redactions: list[dict] = []
    for product in products:
        subject = {"name": product["name"], "description": product.get("description", "")}
        for lang in languages:
            # one rewrite per product+lang; reused across that product's ratios so the
            # copy is consistent and the B1 call count stays product x lang, not x ratio
            rewrite = rewrite_headline(
                base_message,
                market,
                product=subject,
                lang=lang,
                month=month,
            )
            headline = rewrite["text"]
            # B1 returns text that is ALREADY safe — if the base was flagged it was
            # redacted, so rewrite["safety"]["clean"] is True on the returned string.
            # The honest signal that a redaction happened is the [redacted] marker B1
            # leaves in place; record it so the campaign summary carries provenance.
            if safety.REDACTION_MARKER in headline:
                redactions.append(
                    {
                        "product": product["id"],
                        "lang": lang,
                        "headline": headline,
                    }
                )
            locality = _asset_locality(pack, lang)
            for platform, ratios in platforms.items():
                for ratio in ratios:
                    iso_name = naming.build_iso_name(
                        product=product["id"],
                        region=market,
                        locality=locality,
                        channel=platform,
                        ratio=ratio,
                    )
                    assets.append(
                        {
                            "product": product["id"],
                            "platform": platform,
                            "ratio": ratio,
                            "lang": lang,
                            "headline": headline,
                            "iso_name": iso_name,
                            "safety": rewrite["safety"],
                            "dialect_applied": rewrite["dialect_applied"],
                            "copy_source": rewrite["source"],
                            "generated": False,
                            "render_hint": "run_pipeline",
                        }
                    )
    return assets, redactions


def _plan_recipe_cards(
    market: str,
    languages: list[str],
    month: str | None,
    out_dir: Path,
) -> tuple[list[dict], list[str]]:
    """One recipe card per requested language via B4. Cards are GENERATED (real PNG).

    A month with no seeded ingredient yields B4's honest no-ingredient result, recorded
    as a warning rather than a fabricated card.
    """
    cards: list[dict] = []
    warnings: list[str] = []
    for lang in languages:
        res = build_recipe_card(market, month=month, lang=lang, out_dir=out_dir)
        if res.get("card_path"):
            cards.append(
                {
                    "lang": lang,
                    "card_path": res["card_path"],
                    "iso_name": Path(res["card_path"]).name,
                    "ingredient": res["ingredient"],
                    "recipe": res["recipe"],
                    "text_blocks": res["text_blocks"],
                    "safety": res["safety"],
                    "month": res.get("month"),
                    "generated": True,
                }
            )
        else:
            warnings.append(
                f"recipe card skipped ({lang}): {res.get('reason', 'no card produced')}"
            )
    return cards, warnings


def _metro_address_for(market: str, retailer_key: str) -> str | None:
    """Canonical store address for a retailer in a market.

    Prefer the retailer-frontier-pairs metro_location.address when its retailer matches
    the requested one (this is the campaign-canonical address, e.g. the Plaza Midtown
    Publix at 950 W Peachtree). Fall back to STORE_ADDRESS_SEEDS by retailer:city key.
    Never fabricated — returns None when nothing is on file.
    """
    if PAIRS_PATH.exists():
        try:
            raw = json.loads(PAIRS_PATH.read_text(encoding="utf-8"))
            for entry in raw.get("pairs", []):
                if entry.get("market") != market:
                    continue
                metro = entry.get("metro_location", {}) or {}
                metro_retailer = retailers.normalize_retailer(
                    str(metro.get("retailer", ""))
                )
                if metro_retailer == retailer_key and metro.get("address"):
                    return metro["address"]
        except (json.JSONDecodeError, OSError):
            pass
    # seed fallback: single matching retailer:city seed
    prefix = f"{retailer_key}:"
    seeds = [v for k, v in STORE_ADDRESS_SEEDS.items() if k.startswith(prefix)]
    if len(seeds) == 1:
        return seeds[0]
    return None


def _plan_lockups(
    brief_retailers: list[str],
    market: str,
    pack: dict,
) -> tuple[list[dict], list[str]]:
    """Retailer-lockup PLAN entries (D2). resolve_retailer + store address, no render.

    Unknown retailers (no logo lookup, e.g. Walmart/Kroger) are skipped with a warning
    rather than crashing. Each plan names lockup.compose_retailer_lockup as the executor
    and flags a missing logo asset so the operator knows what to drop in.
    """
    lockups: list[dict] = []
    warnings: list[str] = []
    for name in brief_retailers:
        key = retailers.normalize_retailer(name)
        if key is None:
            warnings.append(
                f"retailer {name!r} has no logo lookup — no lockup plan (known: "
                "costco, publix, target)"
            )
            continue
        address = _metro_address_for(market, key)
        try:
            resolved = retailers.resolve_retailer(name, store_address=address)
        except ValueError as e:  # unreachable given the normalize guard, kept honest
            warnings.append(str(e))
            continue
        locality = naming.slugify(
            pack["retailers"].get("frontier_sister") or resolved.name
        )
        iso_name = naming.build_iso_name(
            product="retailer-lockup",
            region=market,
            locality=locality or resolved.name,
            channel="retailer-lockup",
            ratio="1x1",
        )
        if address is None:
            warnings.append(
                f"no store address on file for {resolved.name!r} in {market}; "
                "lockup plan carries no address line"
            )
        if resolved.missing:
            warnings.append(
                f"retailer logo MISSING for {resolved.name!r} — drop {resolved.svg_path}"
            )
        lockups.append(
            {
                "retailer": resolved.name,
                "store_address": address,
                "iso_name": iso_name,
                "logo_asset": str(resolved.asset_path) if resolved.asset_path else None,
                "logo_missing": resolved.missing,
                "executor": "lockup.compose_retailer_lockup",
                "generated": False,
                "notes": list(resolved.notes),
            }
        )
    return lockups, warnings


def run_campaign(
    brief,
    *,
    out_dir: str | Path | None = None,
    month: str | None = None,
    platforms: dict[str, list[str]] | list[str] | None = None,
    languages: list[str] | None = None,
) -> dict:
    """Turn one brief into the full campaign plan (agentcore D1 — the capstone).

    Args:
        brief: a CampaignBrief, a loose brief dict, or a bare market-key string.
        out_dir: where recipe-card PNGs are written; defaults to output/campaigns/.
        month: ISO 'YYYY-MM' for the in-season ingredient; defaults to current month.
        platforms: explicit platform->ratio(s) dict, a bare platform-name list, or None
            for the STANDARD_PLATFORMS set (instagram 1x1/9x16, blog 16x9).
        languages: explicit language list, or None for EN + the market's top-N.

    Returns a structured dict:
        {
          campaign: {market, place, audience, message, month, languages, platforms,
                     retailers, frontier_sister, ingredient},
          assets:       [ planned copy+naming entries (generated=False) ],
          recipe_cards: [ generated card entries (generated=True) ],
          lockups:      [ planned retailer-lockup entries (generated=False) ],
          summary:      { counts, languages, safety_redactions, warnings, safety },
        }

    Composition-only: every asset headline + card text comes from B1/B4, so all emitted
    text is safety-gated. This unit adds no new model call and no network boundary.
    """
    market = _coerce_market(brief)
    if not market:
        raise ValueError("brief must resolve to a market key")

    products = _brief_products(brief)
    base_message = _brief_message(brief)
    out_root = Path(out_dir) if out_dir else DEFAULT_OUT_DIR / naming.slugify(market)

    # A2 — the RAG context pack for the market (drives languages, retailers, ingredient)
    pack = build_context_pack(brief, month=month)

    resolved_langs = _resolve_languages(market, pack, languages)
    resolved_platforms = _resolve_platforms(platforms)
    brief_retailers = _brief_retailers(brief, pack)

    # D1 fan-out — planned assets (B1 copy), generated cards (B4), planned lockups (D2)
    assets, asset_redactions = _plan_assets(
        products, resolved_platforms, resolved_langs, market, base_message, pack, month
    )
    recipe_cards, card_warnings = _plan_recipe_cards(
        market, resolved_langs, month, out_root
    )
    lockups, lockup_warnings = _plan_lockups(brief_retailers, market, pack)

    warnings: list[str] = [*card_warnings, *lockup_warnings]

    # aggregate safety over every emitted string — one explicit verdict for the campaign
    all_text_parts: list[str] = [a["headline"] for a in assets]
    for c in recipe_cards:
        tb = c.get("text_blocks", {})
        all_text_parts.append(tb.get("title", ""))
        all_text_parts.append(tb.get("ingredient_line", ""))
        all_text_parts.extend(tb.get("steps", []))
    aggregate_safety = safety.check_text(" ".join(p for p in all_text_parts if p))

    ingredient = pack["ingredient"].get("ingredient")
    if ingredient is None and pack["ingredient"].get("has_pair"):
        warnings.append(
            f"no in-season ingredient on file for {market} {pack['ingredient'].get('month')}"
        )

    campaign = {
        "market": market,
        "place": pack.get("place"),
        "audience": pack.get("audience"),
        "message": base_message,
        "month": pack["ingredient"].get("month") or month,
        "languages": resolved_langs,
        "platforms": resolved_platforms,
        "retailers": brief_retailers,
        "frontier_sister": pack["retailers"].get("frontier_sister"),
        "ingredient": ingredient,
    }

    summary = {
        "asset_count": len(assets),
        "recipe_card_count": len(recipe_cards),
        "lockup_count": len(lockups),
        "languages": resolved_langs,
        "platforms": list(resolved_platforms.keys()),
        "products": [p["id"] for p in products],
        "generated": {
            "recipe_cards": len(recipe_cards),
            "assets": 0,
            "lockups": 0,
        },
        "planned": {
            "assets": len(assets),
            "lockups": len(lockups),
            "recipe_cards": 0,
        },
        "safety_redactions": asset_redactions,
        "safety": aggregate_safety,
        "warnings": warnings,
    }

    return {
        "campaign": campaign,
        "assets": assets,
        "recipe_cards": recipe_cards,
        "lockups": lockups,
        "summary": summary,
    }
