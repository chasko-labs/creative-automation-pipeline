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

Brand discipline (docs/plans/2026-09-09-atlanta-shakedown-backlog.md standing law):
the word KODIAK never ships in generated copy (logo lockups only). A bare
"Kodiak"/"KODIAK" is rewritten to "Kodiak Cakes"; the only other allowed naming
is "Kodiak Park City". Social voice uses #KodiakCakes-style hashtags (untouched).
The two approved taglines are the only ones this module ever emits.
"""
from __future__ import annotations

import concurrent.futures
import os
import re
import sys
import time

from . import text_rewriter
from .platforms import platform_label

# The two approved external taglines (docs/iso-naming-conventions.md section 2). Fixed
# words, fixed punctuation — no paraphrase. Ampersand form is the packaging tagline.
TAGLINE_EPIC = "Feeding Epic Days & Wilder Lives"
TAGLINE_FRONTIER = "Nourishment for Today's Frontier"

# Allowed brand naming in generated copy (standing law: bare KODIAK never ships;
# logo lockups only). BRAND_MARK is kept as an alias so older callers/tests that
# import the name keep working — it now resolves to the allowed naming.
BRAND_NAME = "Kodiak Cakes"
BRAND_MARK = BRAND_NAME

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
    # publish targets from issue #201: copy lives with the post, never baked
    # into pixels. Homepage carries a hero line (no hashtags); blog carries a
    # photographic-editorial post (seo-shaped, per kodiakcakes.com/blogs/news).
    "homepage": {"hashtags": 0, "emoji": False, "kind": "homepage"},
    "blog": {"hashtags": 3, "emoji": False, "kind": "article"},
}

# The eight publish targets every generation must produce post copy for
# (issue #201). LinkedIn stays a supported explicit opt-in but is not a
# default publish target.
PUBLISH_TARGETS: tuple[str, ...] = (
    "homepage",
    "blog",
    "instagram",
    "facebook",
    "tiktok",
    "youtube",
    "pinterest",
    "x",
)


def _timeout_env(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


# The live endpoint runs outside the image-generation wall. Both limits are explicit so
# a slow Bedrock transport cannot hold the HTTP request indefinitely.
PLATFORM_COPY_PER_PLATFORM_TIMEOUT_S = _timeout_env(
    "PLATFORM_COPY_PER_PLATFORM_TIMEOUT_S", 4.0
)
PLATFORM_COPY_OVERALL_TIMEOUT_S = _timeout_env("PLATFORM_COPY_OVERALL_TIMEOUT_S", 18.0)


class PlatformCopyValidationError(ValueError):
    """Raised when the platform-copy request is not a supported JSON object."""


def normalize_platform_copy_request(body: object) -> dict[str, object]:
    """Validate the shared request contract used by FastAPI and the Lambda route."""
    if not isinstance(body, dict):
        raise PlatformCopyValidationError("expected a JSON object")

    raw_message = body.get("base_message")
    if raw_message is None:
        raw_message = body.get("headline")
    if not isinstance(raw_message, str) or not raw_message.strip():
        raise PlatformCopyValidationError("base_message or headline must be a non-empty string")

    product_name = body.get("product_name")
    if not isinstance(product_name, str) or not product_name.strip():
        raise PlatformCopyValidationError("product_name must be a non-empty string")

    market = body.get("market")
    if not isinstance(market, str) or not market.strip():
        raise PlatformCopyValidationError("market must be a non-empty string")

    languages = body.get("languages")
    if languages is not None and (
        not isinstance(languages, list)
        or any(not isinstance(language, str) or not language.strip() for language in languages)
    ):
        raise PlatformCopyValidationError("languages must be a list of non-empty strings")

    platforms = body.get("platforms")
    if platforms is not None and (
        not isinstance(platforms, list)
        or any(not isinstance(platform, str) or platform not in PLATFORM_SPECS for platform in platforms)
    ):
        raise PlatformCopyValidationError("platforms must contain supported platform slugs")

    return {
        "base_message": raw_message.strip(),
        "product_name": product_name.strip(),
        "market": market.strip(),
        "languages": list(languages or []),
        "platforms": list(platforms) if platforms else list(PUBLISH_TARGETS),
    }


# Deterministic hashtag pool per platform, keyed to Kodiak voice. Kept ascii, no emoji.
_BASE_HASHTAGS = ("KeepItWild", "KodiakCakes", "ProteinPacked", "WholeGrain", "FuelYourFrontier")


# Bare-brand matcher: the standalone word Kodiak/KODIAK in any case, except inside
# a hashtag token (#KodiakCakes) and except the two allowed namings ("Kodiak Cakes",
# "Kodiak Park City", case-insensitive on the trailing words). A legacy (R)/® mark
# after the word is consumed too, normalizing old "KODIAK(R)" copy to the allowed form.
_BARE_BRAND_RE = re.compile(
    r"(?<![#\w])[Kk][Oo][Dd][Ii][Aa][Kk]\b"
    r"(?!\s+(Cakes?|Park\s+City))",
    re.IGNORECASE,
)
_LEGACY_MARK_RE = re.compile(r"\s*(\(R\)|®)")


def clean_brand_copy(text: str) -> str:
    """Rewrite every bare Kodiak/KODIAK to the allowed "Kodiak Cakes" naming.

    Hashtag tokens (#KodiakCakes), "Kodiak Cakes", and "Kodiak Park City" pass
    through untouched; surrounding words are never reworded. Idempotent.
    """
    if not text:
        return text
    out: list[str] = []
    pos = 0
    for m in _BARE_BRAND_RE.finditer(text):
        out.append(text[pos:m.start()])
        out.append(BRAND_NAME)
        pos = m.end()
        mark = _LEGACY_MARK_RE.match(text, pos)
        if mark:
            pos = mark.end()
    out.append(text[pos:])
    return "".join(out)


def _enforce_brand_mark(text: str) -> str:
    """Legacy name — now the standing-law cleaner (bare brand -> "Kodiak Cakes")."""
    return clean_brand_copy(text)


def _has_brand_naming(text: str) -> bool:
    """True when the text references the brand by name (bare or allowed form)."""
    return bool(re.search(r"(?<!#)[Kk]odiak", text, re.IGNORECASE))


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
        return f"{BRAND_NAME} {name}: {base}"
    if kind == "homepage":
        return f"{BRAND_MARK} {name} — {base}"
    if kind == "article":
        return f"{name}: a photographic-editorial Kodiak Cakes breakfast — {base}"
    return f"{BRAND_NAME} {name} — {base}"


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
            f"{place}. Watch how a real Kodiak Cakes breakfast comes together in minutes. "
            f"{TAGLINE_EPIC}."
        )
    if kind == "hooky":
        return f"Protein-packed whole grains, ready fast. {TAGLINE_EPIC}."
    if kind == "trend":
        return f"14g protein. 100% whole grain. No cap. {TAGLINE_EPIC}."
    if kind == "homepage":
        return (
            f"{product_name} — protein-packed 100% whole grains for the whole "
            f"family{place}. {TAGLINE_FRONTIER}."
        )
    if kind == "article":
        return (
            f"A photographic-editorial Kodiak Cakes breakfast{place}: {product_name} "
            f"in-scene, lifestyle, product-in-use. Whole-grain protein for slow "
            f"mornings and big days. {TAGLINE_EPIC}."
        )
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


def _generate_platform_entry(
    base_message: str,
    product_name: str,
    market: str | None,
    platform: str,
    *,
    region: str | None = None,
) -> dict:
    """Generate one platform entry, degrading only that platform on failure."""
    spec = PLATFORM_SPECS[platform]
    kind = spec["kind"]
    try:
        # transport hop: one Nova Micro rewrite for the headline (or offline mock).
        res = text_rewriter.rewrite_headline(
            base_message, market or "us", lang="en", region=region
        )
        rewritten = res.get("text") if isinstance(res, dict) else None
        live = (
            isinstance(rewritten, str)
            and bool(rewritten.strip())
            and res.get("source") == "bedrock:nova-micro"
        )
        if live:
            headline = rewritten.strip()
            source = "generated"
        else:
            headline = _fallback_headline(base_message, product_name, kind)
            source = "fallback"
    except Exception as e:  # noqa: BLE001 — one bad platform never sinks the set
        print(f"[platform_copy] fallback for {platform}: {e}", file=sys.stderr)
        headline = _fallback_headline(base_message, product_name, kind)
        source = "fallback"

    headline = clean_brand_copy(headline)
    hashtags = _hashtags_for(platform, product_name, market, spec["hashtags"])
    entry: dict = {
        "platform": platform,
        "label": platform_label(platform),
        "source": source,
    }

    if platform == "youtube":
        title = headline
        if len(title) > YOUTUBE_TITLE_MAX:
            cut = title[: YOUTUBE_TITLE_MAX - 1]
            if " " in cut:
                cut = cut[: cut.rfind(" ")]
            title = f"{cut}\u2026"
        entry["title"] = clean_brand_copy(title)
        entry["description"] = clean_brand_copy(_body_for(kind, headline, product_name, market))
        entry["hashtags"] = hashtags
    elif platform == "x":
        entry["headline"] = headline
        entry["body"] = ""
        entry["hashtags"] = hashtags
        entry["post"] = clean_brand_copy(_assemble_x(headline, hashtags))
    else:
        entry["headline"] = headline
        entry["body"] = clean_brand_copy(_body_for(kind, headline, product_name, market))
        entry["hashtags"] = hashtags

    return entry


def _bounded_platform_copy(
    base_message: str,
    product_name: str,
    market: str | None,
    platforms: list[str],
    *,
    region: str | None,
    per_platform_timeout_s: float,
    overall_timeout_s: float,
) -> dict[str, dict]:
    """Fan out live rewrites with per-platform and whole-request deadlines."""
    if not platforms:
        return {}
    fallback = fallback_platform_copy(base_message, product_name, market, platforms)
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(platforms))
    started = time.monotonic()
    futures: dict[str, concurrent.futures.Future] = {}
    submitted: dict[str, float] = {}
    for platform in platforms:
        submitted[platform] = time.monotonic()
        futures[platform] = executor.submit(
            _generate_platform_entry,
            base_message,
            product_name,
            market,
            platform,
            region=region,
        )
    out: dict[str, dict] = {}
    overall_expired = False
    try:
        for platform in platforms:
            elapsed = time.monotonic() - started
            remaining_overall = overall_timeout_s - elapsed
            remaining_platform = per_platform_timeout_s - (
                time.monotonic() - submitted[platform]
            )
            if remaining_overall <= 0:
                overall_expired = True
                break
            if remaining_platform <= 0:
                out[platform] = fallback[platform]
                continue
            try:
                out[platform] = futures[platform].result(
                    timeout=min(remaining_platform, remaining_overall)
                )
            except concurrent.futures.TimeoutError:
                out[platform] = fallback[platform]
            except Exception as e:  # noqa: BLE001 — deterministic per-platform fallback
                print(f"[platform_copy] fallback for {platform}: {e}", file=sys.stderr)
                out[platform] = fallback[platform]
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if overall_expired:
        return fallback
    return {platform: out.get(platform, fallback[platform]) for platform in platforms}


def generate_platform_copy(
    base_message: str,
    product_name: str,
    market: str | None = None,
    platforms: list[str] | None = None,
    *,
    region: str | None = None,
    per_platform_timeout_s: float | None = None,
    overall_timeout_s: float | None = None,
) -> dict:
    """Generate platform-tailored copy, optionally within explicit live deadlines.

    The default path preserves the original synchronous contract. Supplying either
    timeout enables parallel live rewrites with deterministic fallback entries.
    """
    wanted = [p for p in (platforms or list(PUBLISH_TARGETS)) if p in PLATFORM_SPECS]
    if per_platform_timeout_s is not None or overall_timeout_s is not None:
        return _bounded_platform_copy(
            base_message,
            product_name,
            market,
            wanted,
            region=region,
            per_platform_timeout_s=per_platform_timeout_s or PLATFORM_COPY_PER_PLATFORM_TIMEOUT_S,
            overall_timeout_s=overall_timeout_s or PLATFORM_COPY_OVERALL_TIMEOUT_S,
        )

    return {
        platform: _generate_platform_entry(
            base_message,
            product_name,
            market,
            platform,
            region=region,
        )
        for platform in wanted
    }


def build_platform_copy_response(body: object) -> dict[str, dict[str, dict]]:
    """Validate a request, run bounded copy generation, and always return its envelope."""
    request = normalize_platform_copy_request(body)
    try:
        copy = generate_platform_copy(
            request["base_message"],
            request["product_name"],
            request["market"],
            platforms=request["platforms"],
            per_platform_timeout_s=PLATFORM_COPY_PER_PLATFORM_TIMEOUT_S,
            overall_timeout_s=PLATFORM_COPY_OVERALL_TIMEOUT_S,
        )
    except Exception as e:  # noqa: BLE001 — offline contract never raises
        print(f"[platform_copy] complete fallback set: {e}", file=sys.stderr)
        copy = fallback_platform_copy(
            request["base_message"],
            request["product_name"],
            request["market"],
            request["platforms"],
        )
    return {"platform_copy": copy}


def fallback_platform_copy(
    base_message: str,
    product_name: str,
    market: str | None = None,
    platforms: list[str] | None = None,
) -> dict:
    """Deterministic offline platform copy with no model calls.

    Same shape as generate_platform_copy's fallback branch for every platform
    (headline/body/hashtags + X post + YouTube title/description, all
    standing-law cleaned), tagged source="fallback". Used by the preview/pack
    response builders when live copy remains frontend-owned.
    """
    cleaned = clean_brand_copy(base_message)
    wanted = [p for p in (platforms or list(PUBLISH_TARGETS)) if p in PLATFORM_SPECS]
    out: dict[str, dict] = {}
    for platform in wanted:
        spec = PLATFORM_SPECS[platform]
        kind = spec["kind"]
        headline = _fallback_headline(cleaned, product_name, kind)
        hashtags = _hashtags_for(platform, product_name, market, spec["hashtags"])
        entry: dict = {
            "platform": platform,
            "label": platform_label(platform),
            "source": "fallback",
        }
        if platform == "youtube":
            title = headline
            if len(title) > YOUTUBE_TITLE_MAX:
                cut = title[: YOUTUBE_TITLE_MAX - 1]
                if " " in cut:
                    cut = cut[: cut.rfind(" ")]
                title = f"{cut}\u2026"
            entry["title"] = clean_brand_copy(title)
            entry["description"] = clean_brand_copy(
                _body_for(kind, headline, product_name, market))
            entry["hashtags"] = hashtags
        elif platform == "x":
            entry["headline"] = headline
            entry["body"] = ""
            entry["hashtags"] = hashtags
            entry["post"] = clean_brand_copy(_assemble_x(headline, hashtags))
        else:
            entry["headline"] = headline
            entry["body"] = clean_brand_copy(
                _body_for(kind, headline, product_name, market))
            entry["hashtags"] = hashtags
        out[platform] = entry
    return out
