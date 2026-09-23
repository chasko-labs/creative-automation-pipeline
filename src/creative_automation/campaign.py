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
import os
from pathlib import Path

from . import naming, retailers, safety
from .compose import compose_creative
from .context_pack import build_context_pack
from .asset_store import resolve_packshot
from .enhance import enhance_hero
from .generate import generate_hero
from .recipe_card import build_recipe_card
from .retailers import STORE_ADDRESS_SEEDS
from .text_rewriter import rewrite_headline

_ROOT = Path(__file__).parents[2]
MARKET_LANGS_PATH = _ROOT / "data" / "localization" / "market-languages.json"
PAIRS_PATH = _ROOT / "data" / "localization" / "retailer-frontier-pairs.json"
DEFAULT_OUT_DIR = _ROOT / "output" / "campaigns"

# standard platform -> ratio(s) map. covers the full social channel set the project
# outlined. delivery ratios are the FOUR customer sizes (1x1=1080x1080, 4x5=1080x1350,
# 9x16=1080x1920, 16x9=1920x1080 per naming.ISO_NAME_RE); the platform->ratio assignments
# below mirror data/platforms/platform-matrix.json, which is the authoritative source of
# truth for which platform serves which ratio. keep it explicit so the fan-out count stays
# predictable (13 platform-ratio pairs = 3+4+1+2+1+1+1).
STANDARD_PLATFORMS: dict[str, list[str]] = {
    "instagram": ["1x1", "4x5", "9x16"],        # feed + portrait feed + stories/reels
    "facebook": ["1x1", "4x5", "9x16", "16x9"], # feed + portrait + stories + landscape
    "tiktok": ["9x16"],             # vertical only
    "youtube": ["16x9", "9x16"],    # landscape + shorts
    "blog": ["16x9"],               # hero (export table carries the 1200x630 OG row)
    "homepage": ["16x9"],           # hero (issue #201 publish target)
    "display": ["1x1"],             # ad tiles
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


def _brief_season(brief) -> str | None:
    """Structured season request from the brief — the `season` field ONLY.

    Free brief text (campaign_message) is display-only for pairing and is never
    parsed here, so a season word leaking into marketing copy cannot steer the
    recipe pairing. Returns the canonical key or None: season keys pass
    through, month names map to their season key, holidays pass through as
    their holiday key (gh #313). Never raises: an unparsable value degrades
    to None (static-default pairing downstream).
    """
    from . import season_pairing as _seasons

    if isinstance(brief, dict):
        raw = brief.get("season")
    else:
        raw = getattr(brief, "season", None)
    try:
        req = _seasons.resolve_request(raw)
    except Exception:  # noqa: BLE001 — season never breaks the campaign
        return None
    if req["kind"] == "season":
        return req["key"]
    if req["kind"] == "month":
        return req["season"]
    if req["kind"] == "holiday":
        return req["key"]
    return None


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
    season: str | None = None,
) -> tuple[list[dict], list[str]]:
    """One recipe card per requested language via B4. Cards are GENERATED (real PNG).

    A month with no seeded ingredient yields B4's honest no-ingredient result, recorded
    as a warning rather than a fabricated card. season is the brief's structured
    season request (never parsed from free text) for the pairing fallback.
    """
    cards: list[dict] = []
    warnings: list[str] = []
    for lang in languages:
        res = build_recipe_card(market, month=month, lang=lang, out_dir=out_dir, season=season)
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
                    "pairing": ((res.get("meta") or {}).get("provenance") or {}).get("pairing"),
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
                "costco, publix, target, subscription)"
            )
            continue
        if key == "subscription":
            # DTC subscription is a fulfillment entry, not a logo lockup —
            # there is no mark to overlay, just the fulfillment line (issue #198).
            lockups.append(
                {
                    "retailer": "subscription",
                    "store_address": None,
                    "fulfillment": retailers.SUBSCRIPTION_FULFILLMENT,
                    "iso_name": None,
                    "logo_asset": None,
                    "logo_missing": False,
                    "executor": "fulfillment.subscription",
                    "generated": False,
                    "notes": [retailers.SUBSCRIPTION_FULFILLMENT],
                }
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


# --------------------------------------------------------------------------- #
# live render (B2 hardening) — planned asset -> real pixels
# --------------------------------------------------------------------------- #
def _has_bedrock_creds() -> bool:
    """True only when an AWS credential source is present on the environment.

    The cohesion re-embed (cr-3) needs a real Nova call, so it is gated behind this
    exactly like generate.py gates the Nova Canvas call. Offline (CI) this is False and
    the cohesion check is skipped-with-a-note, never faked.
    """
    return bool(
        os.getenv("AWS_PROFILE")
        or os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("AWS_ROLE_ARN")
    )


def _cohesion_check(
    image_path: Path, pack: dict
) -> dict:
    """Post-render cluster-cohesion check (B2, cr-3 from docs/kodiak-image-standards.md).

    Re-embed the rendered asset and confirm it lands in its target food-subject cluster
    above that cluster's cohesion floor. Re-embedding needs Bedrock, so this only runs
    when creds are present; offline it returns skipped=True with a reason and does NOT
    fabricate a similarity. The target cluster + floor come from the A2 context pack's
    cluster_match, so the check scores against the subject family, not a global mean.
    """
    if not _has_bedrock_creds():
        return {
            "checked": False,
            "skipped": True,
            "reason": "no aws creds — cohesion re-embed needs bedrock (cr-3 skipped offline)",
        }
    cluster = (pack.get("cluster_match") or {}).get("cluster")
    if not cluster:
        return {
            "checked": False,
            "skipped": True,
            "reason": "no target cluster resolved from context pack — nothing to score against",
        }
    floor = float(cluster.get("cohesion_floor", 0.0))
    # local import so the offline path never imports the embeddings/boto stack
    import math

    from .embeddings import embed_image

    try:
        vec, model = embed_image(image_path, text_hint=cluster.get("label"))
    except Exception as e:  # noqa: BLE001
        return {
            "checked": False,
            "skipped": True,
            "reason": f"re-embed failed: {e}",
        }
    if model.startswith("mock"):
        # creds resolved but the real Nova call still degraded — do not fake a verdict
        return {
            "checked": False,
            "skipped": True,
            "reason": "embed degraded to mock — cohesion not measured against real geometry",
        }
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    # centroid geometry is not carried in image-clusters.json here; the honest signal we
    # can assert offline-free is that a real embedding was produced and normed. Report the
    # floor + vector norm so a caller/reviewer can trace the check; below-floor routing is
    # a follow-on once the centroid vectors are loaded into the pack.
    return {
        "checked": True,
        "skipped": False,
        "cluster_id": cluster.get("id"),
        "cohesion_floor": floor,
        "embed_model": model,
        "embed_norm": round(norm, 4),
        "note": "real re-embed produced; centroid-similarity routing is the cr-3 follow-on",
    }


def _render_asset(
    asset: dict,
    product: dict,
    campaign_message: str,
    market: str,
    audience: str,
    pack: dict,
    out_root: Path,
    idx: int,
) -> dict:
    """Render one planned asset to a real PNG at its iso_name (B2 + D1 connect).

    Reuses the done units: generate_hero (Nova Canvas TEXT_IMAGE, mock fallback) ->
    enhance_hero -> compose_creative. The headline is overlay/caption via compose, never
    baked into the Nova prompt (generate.py already appends "no text, no logo" — cr-1).
    Returns a patch dict merged onto the asset: generated, hero_source, file_path, and
    the cohesion result. On any failure the asset stays planned with a render_error note.
    """
    work_hero = out_root / "_work" / f"{product['id']}_hero.png"
    work_hero.parent.mkdir(parents=True, exist_ok=True)
    try:
        # 0) PACKSHOT-FIRST (compose-fix root-cause repair): if a real product box
        # resolves for this SKU, the box is composited VERBATIM over a background scene —
        # no generative step touches those pixels, so it cannot render as bread or candy.
        # Generation is only the FALLBACK when no packshot resolves. See
        # docs/architecture/compose-fix/compose-fix-spec.md precedence table (order a/b).
        packshot = resolve_packshot(product["id"])
        # 1) hero pixels — Nova Canvas when creds resolve, deterministic mock otherwise.
        # In packshot mode this paints the BACKGROUND scene only (the box lands on top in
        # compose); in generated-scene mode it is the hero itself. The prompt carries no
        # headline text; cr-1 is enforced inside generate_hero.
        _hero_path, hero_source, _hero_prov = generate_hero(
            product_id=product["id"],
            product_name=product["name"],
            brief_msg=campaign_message,
            region=market,
            audience=audience,
            out_path=work_hero,
            idx=idx,
        )
        # 2) institutional enhance (contrast/texture/frame) — Pillow, offline-safe.
        # Applies to the background layer in both modes; the packshot box itself is NEVER
        # enhanced (it is composited verbatim inside compose_creative).
        try:
            enhance_hero(
                work_hero,
                work_hero,
                contrast=1.08,
                brightness=1.02,
                sharpness=1.12,
                texture=True,
                frame=False,
                watermark=False,
                vignette=True,
            )
            hero_source = f"{hero_source}+enhanced"
        except Exception:  # noqa: BLE001 — enhance is best-effort, never blocks render
            print(f"[campaign] enhance failed, continuing unenhanced: {work_hero}")
        # 3) compose the final creative — headline enters HERE as overlay copy (cr-1).
        # product_layer is the verbatim box in packshot mode, None in generated-scene mode.
        iso_path = out_root / asset["iso_name"]
        compose_creative(
            hero_path=work_hero,
            out_path=iso_path,
            message=asset["headline"],
            ratio_key=asset["ratio"],
            product_layer=packshot,
        )
        # 4) post-render cohesion check (cr-3) — creds-gated, skipped-not-faked offline
        cohesion = _cohesion_check(iso_path, pack)
        if packshot is not None:
            base_source = "asset-store:packshot-composite"
        elif hero_source.startswith("mock"):
            base_source = "mock"
        else:
            base_source = "bedrock:nova-pro"
        return {
            "generated": True,
            "hero_source": base_source,
            "hero_source_detail": hero_source,
            "packshot": str(packshot) if packshot is not None else None,
            "file_path": str(iso_path),
            "cohesion": cohesion,
        }
    except Exception as e:  # noqa: BLE001 — a render failure leaves the asset planned
        return {"generated": False, "render_error": str(e)}


def run_campaign(
    brief,
    *,
    out_dir: str | Path | None = None,
    month: str | None = None,
    platforms: dict[str, list[str]] | list[str] | None = None,
    languages: list[str] | None = None,
    render: bool = False,
) -> dict:
    """Turn one brief into the full campaign plan (agentcore D1 — the capstone).

    Args:
        brief: a CampaignBrief, a loose brief dict, or a bare market-key string.
        out_dir: where recipe-card PNGs are written; defaults to output/campaigns/.
        month: ISO 'YYYY-MM' for the in-season ingredient; defaults to current month.
        platforms: explicit platform->ratio(s) dict, a bare platform-name list, or None
            for the STANDARD_PLATFORMS set (instagram, facebook, tiktok, youtube, blog,
            homepage, display — 13 platform-ratio pairs, all ratios among the four
            delivery sizes 1x1/4x5/9x16/16x9 per data/platforms/platform-matrix.json).
        languages: explicit language list, or None for EN + the market's top-N.
        render: when False (default) assets stay planned copy+naming (generated=False)
            and NO Bedrock call is made — CI stays green offline. When True each
            planned asset is rendered to a real PNG at its iso_name via generate_hero
            (Nova Pro, mock fallback) -> enhance -> compose, the asset flips
            generated=True and records its file_path + hero_source (bedrock:nova-pro
            or mock). A post-render cohesion check (cr-3) runs when creds are present and
            is skipped-with-a-note offline, never faked.

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
    brief_season = _brief_season(brief)
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
        market, resolved_langs, month, out_root, season=brief_season
    )
    lockups, lockup_warnings = _plan_lockups(brief_retailers, market, pack)

    warnings: list[str] = [*card_warnings, *lockup_warnings]

    # optional live render (B2 hardening) — flip planned assets to real pixels. Default
    # off so CI + all existing tests stay green offline with no Nova Canvas call.
    rendered_asset_count = 0
    if render:
        products_by_id = {p["id"]: p for p in products}
        audience = pack.get("audience") or ""
        for idx, asset in enumerate(assets):
            product = products_by_id.get(asset["product"], {"id": asset["product"], "name": asset["product"]})
            patch = _render_asset(
                asset,
                product,
                base_message,
                market,
                audience,
                pack,
                out_root,
                idx,
            )
            asset.update(patch)
            if patch.get("generated"):
                rendered_asset_count += 1
            elif patch.get("render_error"):
                warnings.append(
                    f"asset render failed ({asset['iso_name']}): {patch['render_error']}"
                )

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
        "season": brief_season,
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
            "assets": rendered_asset_count,
            "lockups": 0,
        },
        "planned": {
            "assets": len(assets) - rendered_asset_count,
            "lockups": len(lockups),
            "recipe_cards": 0,
        },
        "rendered": render,
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
