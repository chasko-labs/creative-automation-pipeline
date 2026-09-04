"""Per-platform campaign copy — one tailored message object per social network.

The one job: given a base campaign message + product + market, produce copy shaped for
each network's tone and length rules (X <=280, LinkedIn professional, Instagram hooky,
TikTok trend-casual, Facebook community, Pinterest keyword-rich, YouTube title+desc).

Transport boundary (named, not hidden): the headline layer reuses text_rewriter's ONE
Nova Micro Converse seam (context-pack-aware, safety-gated) exactly once per platform.
Everything downstream — length trimming, hashtag assembly, brand-mark enforcement,
YouTube title/description split — is deterministic local shaping, never a model call.

Offline is a documented path, mirroring rewrite_all: when no creds / no Nova, each
platform's copy is built from a deterministic on-brand template and tagged
source="fallback"; a live rewrite is tagged source="generated". A single platform that
raises never sinks the set — it degrades to its fallback template.

Brand discipline (docs/iso-naming-conventions.md): where a headline carries brand naming
the registered mark is enforced — a bare "Kodiak" is rewritten to "KODIAK(R)". The two
approved taglines are the only ones this module ever emits.
"""
from __future__ import annotations

import re
import sys

from . import text_rewriter
from .platforms import PLATFORMS, platform_label

# The two approved external taglines (docs/iso-naming-conventions.md section 2). Fixed
# words, fixed punctuation — no paraphrase. Ampersand form is the packaging tagline.
TAGLINE_EPIC = "Feeding Epic Days & Wilder Lives"
TAGLINE_FRONTIER = "Nourishment for Today's Frontier"

# Registered brand mark. The ascii-safe (R) is used in generated copy so the mark is
# never dropped and the file stays ascii (house rule); the frontend may render (R)->®.
BRAND_MARK = "KODIAK(R)"

# X hard character ceiling (headline + body + hashtags, one post).
X_MAX_CHARS = 280
# YouTube title ceiling.
YOUTUBE_TITLE_MAX = 70

# Per-platform tone/shape spec. `hashtags` is the target count (0 = none). `emoji`
# flags whether the platform's copy MAY carry emoji — default off; only instagram and
# tiktok opt in, and even then the deterministic fallback stays ascii/emoji-free so
# offline output never surprises. `kind` drives the YouTube title+description split.
PLATFORM_SPECS: dict[str, dict] = {
    "x": {"hashtags": 2, "emoji": False, "max_chars": X_MAX_CHARS, "kind": "short"},
    "linkedin": {"hashtags": 2, "emoji": False, "kind": "professional"},
    "instagram": {"hashtags": 4, "emoji": True, "kind": "hooky"},
    "tiktok": {"hashtags": 3, "emoji": True, "kind": "trend"},
    "facebook": {"hashtags": 2, "emoji": False, "kind": "community"},
    "pinterest": {"hashtags": 3, "emoji": False, "kind": "seo"},
    "youtube": {"hashtags": 3, "emoji": False, "kind": "video"},
}

# Deterministic hashtag pool per platform, keyed to Kodiak voice. Kept ascii, no emoji.
_BASE_HASHTAGS = ("KeepItWild", "KodiakCakes", "ProteinPacked", "WholeGrain", "FuelYourFrontier")


def _enforce_brand_mark(text: str) -> str:
    """Ensure a headline carrying the Kodiak name carries the registered mark.

    A bare 'Kodiak' (not already followed by the mark, not part of 'KodiakCakes' as a
    hashtag token) is rewritten to 'KODIAK(R)'. Case-insensitive on the word, but only
    the standalone brand word — the hashtag form '#KodiakCakes' is left untouched.
    """
    # skip replacement inside hashtag tokens (#Kodiak...) by only matching a Kodiak
    # word that is NOT preceded by '#' and NOT already carrying (R)/®.
    def _sub(m: re.Match) -> str:
        return BRAND_MARK

    # (?<![#\w]) — not part of a hashtag or a longer word; (?!\s*\(R\)|®) — not already marked
    pattern = re.compile(r"(?<![#\w])[Kk]odiak\b(?!\s*\(R\)|®|\s+CAKES\(R\))")
    return pattern.sub(_sub, text)


def _has_brand_naming(text: str) -> bool:
    """True when the headline references the brand by name (so the mark must be present)."""
    return bool(re.search(r"(?<!#)[Kk]odiak", text))


def _hashtags_for(platform: str, product_name: str, market: str | None, count: int) -> list[str]:
    """Deterministic hashtag list for a platform, product-and-market aware, no emoji.

    Leads with a product tag + a market tag when derivable, then fills from the base
    pool. Returns exactly `count` unique '#Tag' strings (fewer only if count is larger
    than the available pool, which never happens for our max of 5).
    """
    if count <= 0:
        return []
    tags: list[str] = []
    prod_tag = "".join(w.capitalize() for w in re.split(r"[^A-Za-z0-9]+", product_name) if w)
    if prod_tag:
        tags.append(prod_tag)
    if market:
        mkt_tag = "".join(w.capitalize() for w in re.split(r"[^A-Za-z0-9]+", str(market)) if w)
        if mkt_tag and mkt_tag not in tags:
            tags.append(mkt_tag)
    for base in _BASE_HASHTAGS:
        if len(tags) >= count:
            break
        if base not in tags:
            tags.append(base)
    return [f"#{t}" for t in tags[:count]]


def _fallback_headline(base_message: str, product_name: str, kind: str) -> str:
    """Deterministic on-brand headline per platform tone when no live rewrite is available.

    The base message leads; each tone prepends/adjusts a short frame so the offline copy
    still reads platform-appropriate rather than identical across networks. Always ascii.
    """
    base = base_message.strip()
    name = product_name.strip()
    if kind == "short":
        return f"{BRAND_MARK} {name}: {base}"
    if kind == "professional":
        return f"{BRAND_MARK} {name} — {base}. 100% whole grains, protein-packed."
    if kind == "hooky":
        return f"Fuel your frontier. {BRAND_MARK} {name} — {base}"
    if kind == "trend":
        return f"POV: your breakfast actually fuels the day. {BRAND_MARK} {name}."
    if kind == "community":
        return f"Gather the family around {BRAND_MARK} {name} — {base}"
    if kind == "seo":
        return f"{name} protein pancake and waffle mix — {base}, whole grain breakfast"
    if kind == "video":
        return f"{BRAND_MARK} {name}: {base}"
    return f"{BRAND_MARK} {name} — {base}"


def _body_for(kind: str, headline: str, product_name: str, market: str | None) -> str:
    """Deterministic body/description per tone. YouTube gets a full description paragraph."""
    place = f" in {market}" if market else ""
    if kind == "professional":
        return (
            f"{product_name} delivers 100% whole grains and protein in every serving. "
            f"Built for teams and families who want real food that keeps up. {TAGLINE_FRONTIER}."
        )
    if kind == "community":
        return (
            f"Weekend mornings just got better{place}. {product_name} brings the whole "
            f"family to the table with protein-packed whole grains. {TAGLINE_EPIC}."
        )
    if kind == "seo":
        return (
            f"{product_name} protein pancake mix made with 100% whole grains. High-protein "
            f"breakfast recipe idea for busy mornings, meal prep, and family brunch. "
            f"{TAGLINE_FRONTIER}."
        )
    if kind == "video":
        return (
            f"{product_name} is protein-packed whole-grain fuel for whatever your day holds"
            f"{place}. Watch how a real Kodiak breakfast comes together in minutes. "
            f"{TAGLINE_EPIC}."
        )
    if kind == "hooky":
        return f"Protein-packed whole grains, ready fast. {TAGLINE_EPIC}."
    if kind == "trend":
        return f"14g protein. 100% whole grain. No cap. {TAGLINE_EPIC}."
    # x / short: keep body empty — the single line carries the whole post.
    return ""


def _assemble_x(headline: str, hashtags: list[str]) -> str:
    """Compose the single X post (headline + hashtags) under X_MAX_CHARS, trimming safely.

    Hashtags are dropped first (right to left), then the headline is hard-truncated on a
    word boundary with an ellipsis, so the returned text is ALWAYS <= X_MAX_CHARS.
    """
    tags = list(hashtags)
    while True:
        tail = (" " + " ".join(tags)) if tags else ""
        post = f"{headline}{tail}"
        if len(post) <= X_MAX_CHARS:
            return post
        if tags:
            tags.pop()  # shed a hashtag and retry
            continue
        # no hashtags left — truncate the headline on a word boundary
        budget = X_MAX_CHARS - 1  # room for the ellipsis
        cut = headline[:budget]
        if " " in cut:
            cut = cut[: cut.rfind(" ")]
        return f"{cut}\u2026"[:X_MAX_CHARS]


def generate_platform_copy(
    base_message: str,
    product_name: str,
    market: str | None = None,
    platforms: list[str] | None = None,
    *,
    region: str | None = None,
) -> dict:
    """Generate platform-tailored campaign copy. Returns {platform: {headline, body, hashtags, source, ...}}.

    Args:
        base_message: the source campaign line to tailor per platform.
        product_name: display product name (e.g. "Power Cakes"); drives brand naming + tags.
        market: market key for context + hashtag localization (optional).
        platforms: subset of the seven sanctioned slugs; None => all seven.
        region: dialect region override passed to the rewrite seam (optional).

    Contract:
        - one entry per requested platform, keyed by the platform slug.
        - x copy (headline + hashtags) is always <= 280 chars.
        - youtube copy carries a title (<= 70 chars) AND a description.
        - source is "generated" when a live Nova rewrite produced the headline, else
          "fallback". A failing backend degrades to the deterministic template per
          platform and NEVER raises.
        - where the headline carries brand naming, the registered mark is enforced.
    """
    wanted = [p for p in (platforms or list(PLATFORMS)) if p in PLATFORM_SPECS]
    out: dict[str, dict] = {}

    for platform in wanted:
        spec = PLATFORM_SPECS[platform]
        kind = spec["kind"]
        try:
            # transport hop: one Nova Micro rewrite for the headline (or offline mock).
            res = text_rewriter.rewrite_headline(
                base_message, market or "us", lang="en", region=region
            )
            live = res.get("source") == "bedrock:nova-micro"
            if live:
                headline = res.get("text", base_message).strip()
                source = "generated"
            else:
                headline = _fallback_headline(base_message, product_name, kind)
                source = "fallback"
        except Exception as e:  # noqa: BLE001 — one bad platform never sinks the set
            print(f"[platform_copy] fallback for {platform}: {e}", file=sys.stderr)
            headline = _fallback_headline(base_message, product_name, kind)
            source = "fallback"

        # brand-mark enforcement — only meaningful when the headline names the brand.
        if _has_brand_naming(headline):
            headline = _enforce_brand_mark(headline)

        hashtags = _hashtags_for(platform, product_name, market, spec["hashtags"])
        entry: dict = {
            "platform": platform,
            "label": platform_label(platform),
            "source": source,
        }

        if platform == "youtube":
            # video: split into a <=70-char title + a description paragraph.
            title = headline
            if len(title) > YOUTUBE_TITLE_MAX:
                cut = title[: YOUTUBE_TITLE_MAX - 1]
                if " " in cut:
                    cut = cut[: cut.rfind(" ")]
                title = f"{cut}\u2026"
            entry["title"] = title
            entry["description"] = _body_for(kind, headline, product_name, market)
            entry["hashtags"] = hashtags
        elif platform == "x":
            # single post, hard <=280 including hashtags.
            entry["headline"] = headline
            entry["body"] = ""
            entry["hashtags"] = hashtags
            entry["post"] = _assemble_x(headline, hashtags)
        else:
            entry["headline"] = headline
            entry["body"] = _body_for(kind, headline, product_name, market)
            entry["hashtags"] = hashtags

        out[platform] = entry

    return out
