"""Context-pack builder — the RAG spine primitive (agentcore backlog A2).

Assembles the few-hundred-word context pack every Nova generation call consumes,
stitched entirely from already-built local artifacts. No network, no new deps,
no model call — this is deterministic assembly of done data:

  - market + place + audience            (brief or market-languages.json)
  - retailer set + frontier sister        (locales.resolve_this_month)
  - this-month local ingredient           (locales — never fabricated; None -> honest note)
  - top-N languages + dialect traps        (market-languages.json + locales.load_dialect)
  - nearest food-subject cluster           (data/vectors/image-clusters.json, cr-2/cr-3)
  - relevant sample prompts                (blog-sample-prompts.jsonl, product/tag match)
  - brand rules summary                    (cr-1 no-in-image-text, Bear Brown, iso naming)
  - safety note                            (all emitted text must pass safety.check_text)

The returned dict carries a ``to_prompt_text()`` closure that flattens the pack to
the compact string suitable for prepending to a Nova prompt. Confidence is stated
honestly throughout: a weak cluster match is labelled low-confidence and returns the
full cluster list; a month with no seeded ingredient says so rather than inventing one.
"""
from __future__ import annotations

import json
import re

from . import locales
from ._datapaths import data_path
from .brief import CampaignBrief

# resolved at runtime so this works in a repo checkout AND the Lambda image (see
# _datapaths.data_root — parents[2]/data does not exist under site-packages).
CLUSTERS_PATH = data_path("vectors", "image-clusters.json")
MARKET_LANGS_PATH = data_path("localization", "market-languages.json")
SAMPLE_PROMPTS_PATH = data_path("prompts", "blog-sample-prompts.jsonl")

# brand rules that never vary — cr-1..cr-3 from docs/kodiak-image-standards.md
PALETTE_ANCHOR = "#3B2316"  # Bear Brown
BRAND_RULES = (
    "no text or logo inside the image (cr-1); palette anchor Bear Brown "
    f"{PALETTE_ANCHOR}, Blaze Orange #E8530E, Frontier Green #1A3C34; "
    "match an existing food-subject cluster above its cohesion floor (cr-2/cr-3); "
    "iso-name every asset KODIAK-CAKES-{product}-{region}-{locality}-{channel}-{ratio}-{date}-{version}.png"
)
SAFETY_NOTE = "all emitted text must pass safety.check_text (no profanity, political, slurs, off-brand corporate tone)"

# stop-words dropped before matching product/tag tokens against cluster terms
_STOP = frozenset(
    {
        "the", "and", "for", "with", "your", "kodiak", "cakes", "mix", "co",
        "course", "a", "of", "to", "in", "on", "power",  # 'power' co-occurs in nearly every cluster
    }
)


def _tokens(text: str) -> list[str]:
    """Lower-case alnum tokens over 2 chars, stop-words removed."""
    raw = re.split(r"[^a-z0-9]+", str(text).lower())
    return [t for t in raw if len(t) > 2 and t not in _STOP]


# --------------------------------------------------------------------------- #
# input coercion — accept a CampaignBrief, a market string, or a loose dict
# --------------------------------------------------------------------------- #
def _coerce(brief_or_market: CampaignBrief | dict | str) -> dict:
    """Normalize any accepted input into {market, place, audience, products, tags}."""
    if isinstance(brief_or_market, str):
        return {
            "market": brief_or_market,
            "place": None,
            "audience": None,
            "products": [],
            "tags": [],
            "campaign_message": None,
        }
    if isinstance(brief_or_market, CampaignBrief):
        b = brief_or_market
        products = [{"id": p.id, "name": p.name, "description": p.description} for p in b.products]
        return {
            "market": b.region,
            "place": None,
            "audience": b.target_audience,
            "products": products,
            "tags": [],
            "campaign_message": b.campaign_message,
        }
    if isinstance(brief_or_market, dict):
        d = brief_or_market
        market = d.get("market") or d.get("target_market") or d.get("target_region") or d.get("region")
        return {
            "market": market,
            "place": d.get("place"),
            "audience": d.get("audience") or d.get("target_audience"),
            "products": list(d.get("products", [])),
            "tags": list(d.get("tags", [])),
            "campaign_message": d.get("campaign_message"),
        }
    raise TypeError(f"unsupported brief_or_market type: {type(brief_or_market)!r}")


# --------------------------------------------------------------------------- #
# market languages + dialect considerations
# --------------------------------------------------------------------------- #
def _load_market_langs() -> dict[str, list[dict]]:
    if not MARKET_LANGS_PATH.exists():
        return {}
    raw = json.loads(MARKET_LANGS_PATH.read_text(encoding="utf-8"))
    return {m["market"]: m.get("top_languages", []) for m in raw.get("markets", [])}


def _place_for_market(market: str) -> str | None:
    if not MARKET_LANGS_PATH.exists():
        return None
    raw = json.loads(MARKET_LANGS_PATH.read_text(encoding="utf-8"))
    for m in raw.get("markets", []):
        if m.get("market") == market:
            return m.get("place")
    return None


def _dialect_considerations(market: str, langs: list[dict], top_n: int) -> list[dict]:
    """For each top non-English language, attach its trap terms (or an honest gap note).

    Atlanta's languages (es, ko) have no dialect KB seeded for the US-SE region, so
    the consideration records the language with an empty trap list and a note rather
    than silently pretending there is guidance. A market like the SW *does* resolve
    a KB via locales' loose region match and carries real trap terms (hotcakes, etc).
    """
    out: list[dict] = []
    for lang in langs[:top_n]:
        code = lang.get("lang_code")
        if not code or code == "en":
            continue
        traps = locales.dialect_traps(market, code)
        out.append(
            {
                "lang_code": code,
                "lang_name": lang.get("lang_name", code),
                "pct": lang.get("pct"),
                "traps": [
                    {
                        "term_standard": t.term_standard,
                        "term_local": t.term_local,
                        "usage_note": t.usage_note,
                    }
                    for t in traps
                ],
                "has_kb": bool(traps),
                "note": (
                    f"avoid the regional traps: swap {traps[0].term_standard} -> {traps[0].term_local}"
                    if traps
                    else f"no dialect trap KB seeded for {code} in {market}; translate straight, flag for review"
                ),
            }
        )
    return out


# --------------------------------------------------------------------------- #
# nearest food-subject cluster
# --------------------------------------------------------------------------- #
def _load_clusters() -> dict:
    if not CLUSTERS_PATH.exists():
        return {}
    return json.loads(CLUSTERS_PATH.read_text(encoding="utf-8"))


def _match_cluster(products: list[dict], tags: list[str]) -> dict:
    """Best-overlap cluster for the brief's product names + tags against common_terms.

    Overlap is the count of shared tokens between the brief's subject tokens and a
    cluster's common_terms. Confidence: high (>=3), medium (2), low (1), none (0).
    A none/low match returns the full cluster list so generation can decide, and the
    pack flags it plainly rather than committing to a shaky family.
    """
    clusters = _load_clusters()
    catalog = clusters.get("clusters", {})
    subject_tokens: set[str] = set()
    for p in products:
        subject_tokens.update(_tokens(p.get("name", "")))
        subject_tokens.update(_tokens(p.get("description", "")))
    for t in tags:
        subject_tokens.update(_tokens(t))

    scored: list[tuple[int, str, dict]] = []
    for cid, c in catalog.items():
        terms = set(c.get("common_terms", []))
        overlap = subject_tokens & terms
        scored.append((len(overlap), cid, {"overlap_terms": sorted(overlap), **c}))
    scored.sort(key=lambda x: (x[0], -float(x[2].get("cohesion", 0.0))), reverse=True)

    all_ids = sorted(catalog.keys(), key=lambda k: int(k))
    if not scored:
        return {"confidence": "none", "cluster": None, "all_clusters": all_ids, "subject_tokens": sorted(subject_tokens)}

    best_overlap, best_id, best = scored[0]
    if best_overlap >= 3:
        confidence = "high"
    elif best_overlap == 2:
        confidence = "medium"
    elif best_overlap == 1:
        confidence = "low"
    else:
        confidence = "none"

    label_terms = ", ".join(best.get("common_terms", [])[:4])
    # no overlap at all -> do not commit to a family; hand back the full list and flag none
    if confidence == "none":
        return {
            "confidence": "none",
            "cluster": None,
            "all_clusters": all_ids,
            "subject_tokens": sorted(subject_tokens),
        }

    result: dict = {
        "confidence": confidence,
        "cluster": {
            "id": best_id,
            "dominant_terms": best.get("common_terms", [])[:6],
            "cohesion_floor": round(float(best.get("cohesion", 0.0)), 4),
            "size": best.get("size"),
            "overlap_terms": best.get("overlap_terms", []),
            "label": label_terms,
        },
        "subject_tokens": sorted(subject_tokens),
    }
    # weak match: also hand back the whole family list so the caller is not boxed in
    if confidence == "low":
        result["all_clusters"] = [
            {
                "id": cid,
                "dominant_terms": c.get("common_terms", [])[:4],
                "cohesion_floor": round(float(c.get("cohesion", 0.0)), 4),
            }
            for cid, c in sorted(catalog.items(), key=lambda kv: int(kv[0]))
        ]
    return result


# --------------------------------------------------------------------------- #
# relevant sample prompts
# --------------------------------------------------------------------------- #
def _load_sample_prompts() -> list[dict]:
    if not SAMPLE_PROMPTS_PATH.exists():
        return []
    out: list[dict] = []
    for line in SAMPLE_PROMPTS_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def _match_sample_prompts(products: list[dict], tags: list[str], limit: int) -> list[dict]:
    """Top sample prompts by token overlap on product/recipe/tags/prompt text.

    Deterministic: ties break on the prompt id so the same brief always yields the
    same ordered set. These are the real Kodiak descriptions the generator steers toward.
    """
    prompts = _load_sample_prompts()
    if not prompts:
        return []
    subject_tokens: set[str] = set()
    for p in products:
        subject_tokens.update(_tokens(p.get("name", "")))
        subject_tokens.update(_tokens(p.get("description", "")))
    for t in tags:
        subject_tokens.update(_tokens(t))
    if not subject_tokens:
        return []

    scored: list[tuple[int, str, dict]] = []
    for row in prompts:
        hay = " ".join(
            str(row.get(k, "") or "")
            for k in ("product", "recipe", "prompt")
        )
        hay_tokens = set(_tokens(hay))
        hay_tokens.update(_tokens(" ".join(row.get("tags", []) or [])))
        overlap = len(subject_tokens & hay_tokens)
        if overlap > 0:
            scored.append((overlap, row.get("id", ""), row))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    picked = scored[:limit]
    return [
        {
            "id": r.get("id", ""),
            "product": r.get("product"),
            "recipe": r.get("recipe"),
            "prompt": r.get("prompt", ""),
            "overlap": ov,
        }
        for ov, _id, r in picked
    ]


# --------------------------------------------------------------------------- #
# render helper
# --------------------------------------------------------------------------- #
def _render(pack: dict) -> str:
    """Flatten the pack to a compact few-hundred-word prompt prefix (deterministic)."""
    lines: list[str] = []
    market = pack["market"]
    place = pack.get("place") or "(place unknown)"
    audience = pack.get("audience") or "(audience unspecified)"
    lines.append(f"MARKET: {market} — {place}")
    lines.append(f"AUDIENCE: {audience}")

    ret = pack["retailers"]
    if ret.get("frontier_sister"):
        lines.append(
            f"RETAILERS: {', '.join(ret.get('retailers') or []) or '(none on file)'}; "
            f"agricultural/market frontier sister (farm/orchard, not military): {ret['frontier_sister']}"
        )
    else:
        lines.append("RETAILERS: no retailer-frontier pair seeded for this market")

    ing = pack["ingredient"]
    if ing.get("has_pair") is False:
        lines.append(f"LOCAL INGREDIENT: no pair on file for {market}")
    elif ing.get("ingredient"):
        lines.append(f"LOCAL INGREDIENT ({ing['month']}): {ing['ingredient']}")
    else:
        lines.append(f"LOCAL INGREDIENT: no in-season ingredient on file for {ing['month']}")

    if pack["dialect_considerations"]:
        for d in pack["dialect_considerations"]:
            pct = f" {d['pct']}%" if d.get("pct") is not None else ""
            lines.append(f"DIALECT {d['lang_name']} ({d['lang_code']}{pct}): {d['note']}")

    cl = pack["cluster_match"]
    if cl.get("cluster"):
        c = cl["cluster"]
        lines.append(
            f"VISUAL FAMILY: cluster {c['id']} ({c['label']}) — {cl['confidence']} match, "
            f"cohesion floor {c['cohesion_floor']}"
        )
    else:
        lines.append(
            f"VISUAL FAMILY: {cl['confidence']} match — pick from clusters "
            f"{', '.join(str(x) for x in cl.get('all_clusters', []))}"
        )

    if pack["sample_prompts"]:
        lines.append("SAMPLE KODIAK COPY (steer toward, do not copy):")
        for sp in pack["sample_prompts"]:
            snippet = sp["prompt"].strip().replace("\n", " ")
            if len(snippet) > 160:
                snippet = snippet[:157].rstrip() + "..."
            lines.append(f"  - {snippet}")

    lines.append(f"BRAND RULES: {pack['brand_rules']}")
    lines.append(f"SAFETY: {pack['safety_note']}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# public entry point
# --------------------------------------------------------------------------- #
def build_context_pack(
    brief_or_market: CampaignBrief | dict | str,
    *,
    month: str | None = None,
    top_n_languages: int = 2,
    max_sample_prompts: int = 3,
) -> dict:
    """Assemble the offline context pack for a brief or market key.

    Args:
        brief_or_market: a CampaignBrief, a loose brief dict, or a market key string.
        month: ISO 'YYYY-MM' for the in-season ingredient; defaults to current month.
        top_n_languages: how many non-English languages to carry dialect notes for.
        max_sample_prompts: cap on retrieved real-Kodiak sample prompts.

    Returns a structured dict. The ``to_prompt_text`` key is a zero-arg callable that
    renders the compact prompt-prefix string; a top-level ``prompt_text`` string is
    also included so the pack is JSON-serializable after dropping the callable.
    """
    coerced = _coerce(brief_or_market)
    market = coerced["market"]
    if not market:
        raise ValueError("brief_or_market must resolve to a market key")

    langs_by_market = _load_market_langs()
    top_languages = langs_by_market.get(market, [])
    place = coerced["place"] or _place_for_market(market)

    # retailer set + frontier sister + this-month ingredient (never fabricated)
    resolved = locales.resolve_this_month(market, ym=month)
    if resolved is None:
        retailers = {"retailers": [], "frontier_sister": None, "has_pair": False}
        ingredient = {"month": month, "ingredient": None, "has_pair": False}
    else:
        retailers = {
            "retailers": resolved["retailers"],
            "frontier_sister": resolved["frontier_sister"],
            "farmers_market_url": resolved.get("farmers_market_url"),
            "has_pair": True,
        }
        ingredient = {
            "month": resolved["month"],
            "ingredient": resolved["ingredient"],
            "has_pair": True,
        }

    dialect = _dialect_considerations(market, top_languages, top_n_languages)
    cluster_match = _match_cluster(coerced["products"], coerced["tags"])
    sample_prompts = _match_sample_prompts(coerced["products"], coerced["tags"], max_sample_prompts)

    pack: dict = {
        "market": market,
        "place": place,
        "audience": coerced["audience"],
        "campaign_message": coerced.get("campaign_message"),
        "retailers": retailers,
        "ingredient": ingredient,
        "dialect_considerations": dialect,
        "cluster_match": cluster_match,
        "sample_prompts": sample_prompts,
        "brand_rules": BRAND_RULES,
        "palette_anchor": PALETTE_ANCHOR,
        "safety_note": SAFETY_NOTE,
        "sources": {
            "retailers_ingredient": "data/localization/retailer-frontier-pairs.json",
            "languages": "data/localization/market-languages.json",
            "dialect": "data/localization/dialect/*.jsonl",
            "clusters": "data/vectors/image-clusters.json",
            "sample_prompts": "data/prompts/blog-sample-prompts.jsonl",
        },
    }
    pack["prompt_text"] = _render(pack)
    pack["to_prompt_text"] = lambda: pack["prompt_text"]
    return pack
