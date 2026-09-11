"""Read-only DAM asset browser — the ONE implementation of the marketer-facing picker.

Both surfaces call list_library(category, limit, offset):
  - api.py's GET /assets/library (dev/local FastAPI)
  - generate_lambda.py's _handle_assets_library (deployed production path dispatcher)

Six marketer-facing tabs replace the old 4-prefix model:
  products | recipes | lifestyle | ideas | themes | brand

The DAM bucket is fully private, so every item carries a presigned GET url (public urls
403). Bucket is resolved from dam._s3_bucket_and_prefix() — never hardcoded. Keys are
presigned VERBATIM via dam.presign_get (no prefix join — matches fetch_dam_key contract).

PERF: products/recipes/lifestyle all read the SAME raw-ingest prefix. It is listed ONCE,
every key classified in a single pass, then routed into the three buckets — never
paginated three times.

PAGINATION: the FULL ordered key list is gathered per category first (total = len), then
ONLY keys[offset:offset+limit] are presigned. No presign is ever minted outside the
window.

Offline / CI path (dam._s3_enabled() False) and per-category failures both degrade to the
SAME shape (total=0, offset=0, count=0, has_more=false, next_offset=null, items=[]) so the
frontend never branches on shape.
"""
from __future__ import annotations

import json
import os
import pathlib
import re
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

from . import dam
from ._datapaths import data_path

# ---------------------------------------------------------------- category model
# raw-ingest holds the seed photography that products/recipes/lifestyle all draw from —
# one prefix, classified per-key into three tabs. The other tabs read fixed brand paths.
_RAW_INGEST_PREFIX = "brands/kodiak/raw-ingest/kodiakcakes/images/"

# theme-asset-map resolves via the shared data-root resolver so the same code works in a
# repo checkout (data/ beside src/) and in the Lambda image (/var/task/data).
_THEME_MAP_PATH = data_path("products", "theme-asset-map.json")

# product-line facet: the catalog (handle -> category) joined to raw-ingest S3 keys
# via the sku-photo-map (handle -> photo_key + fallbacks). Same resolver story.
_SKU_MAP_PATH = data_path("products", "sku-photo-map.json")
_CATALOG_PATH = data_path("products", "kodiak-full-catalog.json")

# module-cached key -> category index; None means "not loaded yet" (Lambda reuse).
_PRODUCT_LINE_CACHE: dict[str, str] | None = None

# ---------------------------------------------------------------- thumbnails
# Grid tiles must never pull full files: list_library mints a presigned thumb
# url per item when a cached 320px derivative exists under _THUMB_PREFIX.
# Derivatives are filled by scripts/build-thumb-cache.py (never generated
# inline — a cold 40-tile grid would blow the Lambda wall). Missing thumb ->
# thumb=None and the frontend falls back to the full url for that tile.
_THUMB_PREFIX = "thumbs/"
_THUMB_WIDTH = 320


def _thumb_key(key: str) -> str:
    return f"{_THUMB_PREFIX}{key}.thumb.jpg"


def thumb_url(key: str, client, bucket: str) -> str | None:
    """Presigned GET for the cached thumb derivative, or None when absent.

    HEAD-hit only — never generates, never throws. The frontend falls back
    to the full url on None, so a cold thumb cache only costs speed.
    """
    try:
        if not key or client is None or not bucket:
            return None
        client.head_object(Bucket=bucket, Key=_thumb_key(key))
    except Exception:
        return None
    try:
        return dam.presign_get(_thumb_key(key))
    except Exception:
        return None


# ---------------------------------------------------------------- curation
# data/dam/curation.json (optional): {"strength": {key: number}, "omit": [key]}.
# Ideas tab ranks strongest-first; omitted keys (mock-hero slop) never list.
# Unrated keys keep listing order behind rated ones. Missing file -> no-op.
_CURATION_PATH = data_path("dam", "curation.json")
_CURATION_CACHE: dict | None = None


def _curation() -> dict:
    global _CURATION_CACHE
    if _CURATION_CACHE is None:
        try:
            import json as _json

            _CURATION_CACHE = _json.loads(_CURATION_PATH.read_text())
            if not isinstance(_CURATION_CACHE, dict):
                _CURATION_CACHE = {}
        except Exception:
            _CURATION_CACHE = {}
    return _CURATION_CACHE


def _apply_curation(keys: list[str]) -> list[str]:
    cur = _curation()
    if not cur:
        return keys
    omit = set(cur.get("omit") or [])
    strength = cur.get("strength") or {}
    kept = [k for k in keys if k not in omit]
    if not isinstance(strength, dict) or not strength:
        return kept
    rated = sorted(
        [k for k in kept if k in strength],
        key=lambda k: (-float(strength[k]), kept.index(k)),
    )
    unrated = [k for k in kept if k not in strength]
    return rated + unrated

# Each category declares a source strategy the gatherer dispatches on:
#   classified -> read _RAW_INGEST_PREFIX once, keep keys whose class matches; recipes may
#                 append extra fixed prefixes.
#   prefix     -> list one or more fixed prefixes verbatim.
#   themes     -> union the pools in theme-asset-map.json.
#   merge      -> ordered members, each (prefix, nested, tag) for brand labelling.
_CATEGORIES: dict[str, dict] = {
    "products": {"source": "classified", "prefix": _RAW_INGEST_PREFIX, "class": "products"},
    "recipes": {
        "source": "classified",
        "prefix": _RAW_INGEST_PREFIX,
        "class": "recipes",
        "extra_prefixes": ("brands/kodiak/recipes/",),
    },
    "food": {"source": "classified", "prefix": _RAW_INGEST_PREFIX, "class": "food"},
    "lifestyle": {"source": "classified", "prefix": _RAW_INGEST_PREFIX, "class": "lifestyle"},
    "ideas": {"source": "prefix", "prefixes": ("brands/kodiak/renders/",)},
    "themes": {"source": "themes", "map_path": _THEME_MAP_PATH},
    "brand": {
        "source": "merge",
        "members": (
            ("brands/kodiak/heroes/", True, "hero"),
            ("brands/kodiak/logos/", False, "logo"),
            ("brands/kodiak/references/", False, "reference"),
        ),
    },
}

_VIDEO_EXTS = {".mp4", ".mov", ".webm"}

# ---------------------------------------------------------------- classifier
# Precedence recipes -> food -> lifestyle -> products, fallback products. A key
# is NEVER dropped. "recipes" is reserved for real recipe cards (recipe-named
# assets + brands/kodiak/recipes/); food photography lives in "food".
_RECIPE_KEYWORDS = (
    "recipe", "recipes", "stack-cake",
)
_FOOD_KEYWORDS = (
    "stack", "plated", "plate", "syrup", "drizzle", "topped", "topping",
    "breakfast-spread", "spread", "bowl", "served", "serving", "batter",
    "cooked", "cooking", "griddle", "fresh-off", "brunch", "meal", "dish",
    "prepared", "table", "kitchen", "food",
)
_PRODUCT_KEYWORDS = (
    "flapjack", "waffle", "waffles", "power-waffle", "power-waffles", "pancake", "cup",
    "cups", "oatmeal", "oat", "bar", "bars", "granola", "frozen", "muffin", "muffins",
    "baking", "mix", "protein-ball", "protein-balls", "trail", "chewy", "crunchy",
    "breakfast-bar", "french-toast", "toaster", "brownie", "quick-bread", "front", "pack",
    "packet", "packets", "box", "carton", "nfp", "infographic", "main-image", "mainimage",
    "hero-alt", "sku", "705599",
)
_LIFESTYLE_KEYWORDS = (
    "lifestyle", "outdoor", "outdoors", "trail-run", "hike", "hiking", "mountain",
    "mountains", "camp", "camping", "kitchen", "family", "athlete", "gym", "workout",
    "run", "running", "ski", "snow", "frontier", "adventure", "portrait", "person",
    "people", "hand", "morning", "sunrise", "lifestyle-shot", "in-use", "action",
)


def classify_raw_ingest(key: str) -> str:
    """Classify a raw-ingest key into recipes | food | lifestyle | products.

    Precedence recipes -> food -> lifestyle -> products; fallback products.
    Matches keyword substrings against the lowercased filename stem so a key
    is never dropped.
    """
    stem = pathlib.Path(key).stem.lower()
    if any(kw in stem for kw in _RECIPE_KEYWORDS):
        return "recipes"
    if any(kw in stem for kw in _FOOD_KEYWORDS):
        return "food"
    if any(kw in stem for kw in _LIFESTYLE_KEYWORDS):
        return "lifestyle"
    if any(kw in stem for kw in _PRODUCT_KEYWORDS):
        return "products"
    return "products"


# ---------------------------------------------------------------- label transform
# noise tokens dropped in step 6 (case-insensitive)
_LABEL_NOISE = {
    "kodiak", "cakes", "mainimage", "main", "image", "alt", "hero", "front", "nfp",
    "infographic",
}
_HEX_LEAD = re.compile(r"^[0-9a-f]{6,}--")
_HEX_TAIL_UNDERSCORE = re.compile(r"_[0-9a-f]{6}$")
_HEX_TAIL_DASH = re.compile(r"-[0-9a-f]{6,}$")
_SKU_LEAD = re.compile(r"^[0-9]{6,}[-_]")
_DATE_LEAD = re.compile(r"^[0-9]{8}[-_]")
_WS = re.compile(r"\s+")
_NUMERIC = re.compile(r"^[0-9]+$")
# CamelCase / PascalCase run split: "CrunchyGranolaBars" -> "Crunchy Granola Bars".
# Splits a lower/digit->upper boundary (fooBar) and an acronym->word boundary (HTMLParser).
_CAMEL = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def _label(key: str) -> str:
    """Marketer-facing label from a DAM key. Seven ordered steps; empty -> "" (caller
    falls back). See module tests for worked examples."""
    # 1. stem
    stem = pathlib.Path(key).stem
    # 2. drop through first "--" when stem opens with a hex hash
    if _HEX_LEAD.match(stem):
        stem = stem.split("--", 1)[1]
    # 3. strip trailing hex tokens (_abc123 then -abc123def)
    stem = _HEX_TAIL_UNDERSCORE.sub("", stem)
    stem = _HEX_TAIL_DASH.sub("", stem)
    # 4. strip leading SKU (>=6 digits) then leading YYYYMMDD (8 digits)
    stem = _SKU_LEAD.sub("", stem)
    stem = _DATE_LEAD.sub("", stem)
    # 5. camelCase runs -> spaced words, then separators -> space, collapse whitespace
    stem = _CAMEL.sub(" ", stem)
    stem = _WS.sub(" ", stem.replace("-", " ").replace("_", " ")).strip()
    # 6. drop noise tokens, pure-numeric tokens, and <=2-char leftovers (case-insensitive)
    kept = [
        tok for tok in stem.split(" ")
        if tok
        and tok.lower() not in _LABEL_NOISE
        and not _NUMERIC.match(tok)
        and len(tok) > 2
    ]
    if not kept:
        return ""
    # 7. title-case remaining
    return " ".join(kept).title()


def _label_fallback(key: str, tab: str) -> str:
    """Deterministic fallback when _label yields empty (e.g. renders UUIDs)."""
    short = pathlib.Path(key).stem[:8]
    prefix = "concept" if tab == "ideas" else "asset"
    return f"{prefix} {short}"


def _label_brand(key: str, nested: bool, tag: str) -> str:
    """Brand-member label. hero+nested reads the product path segment; others decorate
    the base _label per member tag."""
    if tag == "hero" and nested:
        parts = [p for p in key.split("/") if p]
        product = parts[-2] if len(parts) >= 2 else pathlib.Path(key).stem
        return f"{product} hero"
    base = _label(key)
    if tag == "logo":
        return f"{base} logo" if base else _label_fallback(key, "brand")
    if tag == "reference":
        return f"{base} reference" if base else _label_fallback(key, "brand")
    return base or _label_fallback(key, "brand")


def _kind(key: str) -> str:
    return "video" if pathlib.Path(key).suffix.lower() in _VIDEO_EXTS else "image"


# ---------------------------------------------------------------- key gatherers
def _list_prefix(client, bucket: str, prefix: str) -> list[str]:
    """All non-placeholder keys under a prefix, in listing order. Raises on S3 error."""
    paginator = client.get_paginator("list_objects_v2")
    keys: list[str] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/"):
                continue  # directory placeholder
            keys.append(key)
    return keys


def _gather_themes(map_path) -> list[str]:
    """Union every theme pool into one deduped, first-appearance-ordered key list.

    Handles the shipped shape {"map": {theme: {"pool": [...]}}} plus the tolerant
    {theme: {"assets": [...]}} and {theme: [...]} forms. Missing/unreadable map -> [].
    """
    try:
        data = json.loads(pathlib.Path(map_path).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — absent/unreadable map is a soft-empty tab
        print(f"[dam_library] theme map load skipped {map_path}: {e}")
        return []
    # unwrap a top-level "map" envelope when present (the shipped shape)
    themes = data.get("map", data) if isinstance(data, dict) else {}
    if not isinstance(themes, dict):
        return []
    seen: set[str] = set()
    ordered: list[str] = []
    for _theme, entry in themes.items():
        if isinstance(entry, dict):
            pool = entry.get("assets") or entry.get("pool") or []
        elif isinstance(entry, list):
            pool = entry
        else:
            pool = []
        for key in pool:
            if isinstance(key, str) and key and key not in seen:
                seen.add(key)
                ordered.append(key)
    return ordered


def _gather_keys(name: str, cfg: dict, client, bucket: str, classified_cache: dict) -> list[str]:
    """Return the FULL ordered key list for one category. classified_cache memoizes the
    single raw-ingest pass so products/recipes/lifestyle share it."""
    source = cfg["source"]

    if source == "classified":
        prefix = cfg["prefix"]
        if prefix not in classified_cache:
            buckets: dict[str, list[str]] = {"products": [], "recipes": [], "food": [], "lifestyle": []}
            for key in _list_prefix(client, bucket, prefix):
                buckets[classify_raw_ingest(key)].append(key)
            classified_cache[prefix] = buckets
        keys = list(classified_cache[prefix][cfg["class"]])
        for extra in cfg.get("extra_prefixes", ()):  # e.g. recipes' brand recipe folder
            keys.extend(_list_prefix(client, bucket, extra))
        return keys

    if source == "prefix":
        keys: list[str] = []
        for prefix in cfg["prefixes"]:
            keys.extend(_list_prefix(client, bucket, prefix))
        return keys

    if source == "themes":
        return _gather_themes(cfg["map_path"])

    if source == "merge":
        keys = []
        for prefix, _nested, _tag in cfg["members"]:
            keys.extend(_list_prefix(client, bucket, prefix))
        return keys

    return []


def _brand_label_index(cfg: dict, client, bucket: str) -> dict[str, tuple[bool, str]]:
    """Map each brand key -> (nested, tag) so _label_brand can decorate it. Members are
    listed in declared order; first-writer wins on the rare cross-prefix collision."""
    index: dict[str, tuple[bool, str]] = {}
    for prefix, nested, tag in cfg["members"]:
        for key in _list_prefix(client, bucket, prefix):
            index.setdefault(key, (nested, tag))
    return index


def _load_product_line_index(map_path=_SKU_MAP_PATH, catalog_path=_CATALOG_PATH) -> dict[str, str]:
    """Invert the sku-photo-map into raw-ingest-key -> catalog category (product line).

    One DAM photo routinely serves several products (and even several product
    lines), so photo_key claims (the map's authoritative depiction) outrank
    fallback claims, and within each tier the most-claimed category wins with
    an alphabetical tiebreak. Fully deterministic: map iteration order never
    affects the result. Missing/unreadable files -> {} (soft-empty: tiles
    carry product_line=None, never fabricated). Explicit paths are the test
    seam; production uses the resolved defaults.
    """
    try:
        sku_map = json.loads(pathlib.Path(map_path).read_text(encoding="utf-8"))
        catalog = json.loads(pathlib.Path(catalog_path).read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001 — absent/unreadable data is a soft-empty tab
        print(f"[dam_library] product-line index skipped: {e}")
        return {}
    by_handle: dict[str, str] = {}
    products = catalog.get("products", []) if isinstance(catalog, dict) else []
    for p in products:
        if isinstance(p, dict) and p.get("handle") and p.get("category"):
            by_handle[p["handle"]] = p["category"]
    # photo claims (the map's authoritative depiction) and fallback claims are
    # tracked separately: a photo claim always outranks any number of fallback
    # claims. Within each tier the most-claimed category wins, alphabetical
    # tiebreak — fully deterministic, independent of map iteration order.
    photo_claims: dict[str, list[str]] = {}
    fallback_claims: dict[str, list[str]] = {}
    entries = sku_map.get("map", {}) if isinstance(sku_map, dict) else {}
    for handle, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        line = by_handle.get(handle)
        if not line:
            continue
        photo_key = entry.get("photo_key")
        if isinstance(photo_key, str) and photo_key:
            photo_claims.setdefault(photo_key, []).append(line)
        for fb in entry.get("fallbacks") or []:
            if isinstance(fb, str) and fb:
                fallback_claims.setdefault(fb, []).append(line)
    index: dict[str, str] = {}
    for key in set(photo_claims) | set(fallback_claims):
        lines = photo_claims.get(key) or fallback_claims.get(key, [])
        counts = Counter(lines)
        top = max(counts.values())
        index[key] = sorted(c for c, n in counts.items() if n == top)[0]
    return index


def _product_line_index() -> dict[str, str]:
    """Module-cached product-line index (one JSON parse per Lambda container)."""
    global _PRODUCT_LINE_CACHE
    if _PRODUCT_LINE_CACHE is None:
        _PRODUCT_LINE_CACHE = _load_product_line_index()
    return _PRODUCT_LINE_CACHE


def _platforms_from_meta(meta: dict) -> list[str]:
    """Parse the x-amz-meta-platforms tag value into a slug list. [] when absent."""
    raw = ""
    if isinstance(meta, dict):
        for k, v in meta.items():
            if str(k).lower() == "platforms" and isinstance(v, str):
                raw = v
                break
    return [p.strip().lower() for p in raw.split(",") if p.strip()]


# tabs whose tiles draw from the classified raw-ingest pass (product-line join applies)
_CLASSIFIED_TABS = {"products", "recipes", "food", "lifestyle"}


def _item_for(
    key: str,
    name: str,
    brand_index: dict | None,
    product_index: dict[str, str] | None = None,
    platforms: list[str] | None = None,
) -> dict:
    """Build one item dict (pre-url). ratio is OMITTED — future work; never fabricated.

    product_line carries the catalog category for classified-tab tiles whose key
    the sku-photo-map knows, else None (never fabricated). platforms carries the
    publish-time x-amz-meta-platforms slugs (ideas tab), else []. Both keys are
    ALWAYS present so the frontend never branches on shape.
    """
    if name == "brand" and brand_index is not None and key in brand_index:
        nested, tag = brand_index[key]
        label = _label_brand(key, nested, tag)
    else:
        label = _label(key) or _label_fallback(key, name)
    item = {"key": key, "label": label, "kind": _kind(key)}
    if name in _CLASSIFIED_TABS:
        idx = product_index if product_index is not None else _product_line_index()
        item["product_line"] = idx.get(key)
    else:
        item["product_line"] = None
    item["platforms"] = list(platforms) if platforms else []
    return item


# Per-item url/thumb/meta resolution is the request-latency floor: each window key
# fires a synchronous S3 HEAD in thumb_url (thumb-cache gate) and, on the ideas tab, a
# second HEAD in head_metadata. Serial, a 24-tile window = up to 48 serial HEAD round
# trips before the Lambda responds — on a cold container that blows the 12s client abort
# (see web/.../prompt-chips.js DAM_TIMEOUT_MS). presign_get itself is CPU-only (no round
# trip), so the HEADs are the whole cost. Fanning the per-item work across a bounded
# thread pool collapses N serial HEADs into ~1-2 round-trip-times. botocore's low-level
# client is thread-safe for these independent read calls (head_object / generate_presigned
# _url share no mutable state across calls). Bound the pool so a large page cannot spawn
# an unbounded thread storm; default 16, override via DAM_LIBRARY_MAX_WORKERS.
_DAM_LIBRARY_MAX_WORKERS = max(1, int(os.getenv("DAM_LIBRARY_MAX_WORKERS", "16")))


def _resolve_window_items(
    window: list[str],
    name: str,
    brand_index: dict | None,
    product_index: dict[str, str] | None,
    client,
    bucket: str,
) -> list[dict]:
    """Build the per-key item dicts for one page window, fanned across a bounded pool.

    Preserves window (listing) order regardless of completion order — the executor.map
    contract yields results positionally. Each task does exactly the work the old serial
    loop did per key: the ideas-tab platforms HEAD, presign_get, and the thumb_url HEAD +
    presign. Every task is self-contained and swallows its own S3 errors via the same
    graceful helpers (presign_get / thumb_url / head_metadata all degrade, never throw),
    so one slow or failing key cannot sink the page — it lands with url/thumb None exactly
    as the serial path produced.
    """
    def _one(key: str) -> dict:
        plats = (
            _platforms_from_meta(dam.head_metadata(key)) if name == "ideas" else None
        )
        item = _item_for(key, name, brand_index, product_index, plats)
        item["url"] = dam.presign_get(key)
        # grid tiles use thumb (cached 320px derivative) and fall back to the full
        # url when no derivative exists yet — thumb_url returns None on a HEAD miss.
        item["thumb"] = thumb_url(key, client, bucket)
        return item

    if not window:
        return []
    # cap workers at the window size — never spin more threads than there is work.
    workers = min(_DAM_LIBRARY_MAX_WORKERS, len(window))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_one, window))


def _empty_page(offset: int) -> dict:
    """The shape every degrade path returns so the frontend never branches on shape."""
    return {
        "total": 0,
        "offset": max(0, offset),
        "count": 0,
        "has_more": False,
        "next_offset": None,
        "items": [],
    }


# ---------------------------------------------------------------- public API
def list_library(category: str | None = None, limit: int = 60, offset: int = 0) -> dict:
    """List a marketer-facing DAM tab (or all seven) with presigned GET urls, paginated.

    category: products|recipes|food|lifestyle|ideas|themes|brand; all seven when
    absent/unknown.
    limit:    max presigned URLs minted per category this page (default 60, clamped 1..200).
    offset:   0-based window start into the category's FULL ordered key list (default 0).

    Backward-tolerant: existing callers pass (category, limit) only — offset defaults 0.

    Returns {"enabled": bool, "bucket": str|None, "categories": {name: page}} where each
    page is {total, offset, count, has_more, next_offset,
    items[{key,label,kind,url,thumb,product_line,platforms}]}. thumb is the cached
    320px derivative presign (None until scripts/build-thumb-cache.py fills it —
    the grid falls back to url). product_line is the catalog category for
    classified-tab tiles the sku-photo-map knows (else None); platforms is the
    publish-time x-amz-meta-platforms slugs for ideas tiles (else []).
    data/dam/curation.json optionally omits keys and ranks ideas strongest-first.
    Never raises — S3-disabled and per-category failures both degrade to _empty_page.
    """
    cap = max(1, min(int(limit), 200))
    off = max(0, int(offset))
    wanted = [category] if category in _CATEGORIES else list(_CATEGORIES)

    if not dam._s3_enabled():
        return {
            "enabled": False,
            "bucket": None,
            "categories": {name: _empty_page(off) for name in wanted},
            "note": "DAM S3 not configured — set DAM_S3_BUCKET",
        }

    bucket, _ = dam._s3_bucket_and_prefix()
    client = dam._s3_client()
    categories: dict[str, dict] = {}
    # memoize the single raw-ingest classification pass across products/recipes/lifestyle
    classified_cache: dict[str, dict] = {}

    # one product-line index build shared across the classified tabs
    product_index = (
        _product_line_index() if any(n in _CLASSIFIED_TABS for n in wanted) else None
    )

    for name in wanted:
        cfg = _CATEGORIES[name]
        try:
            if client is None:
                raise RuntimeError("s3 client init failed")
            keys = _gather_keys(name, cfg, client, bucket, classified_cache)
            keys = _apply_curation(keys)
            total = len(keys)
            brand_index = (
                _brand_label_index(cfg, client, bucket) if cfg["source"] == "merge" else None
            )
            # presign ONLY the window — never mint a url outside keys[off:off+cap].
            # the ideas-tab HEADs follow the same bound: one metadata read per
            # window key, never for keys outside the page. Per-key resolution
            # (presign + thumb HEAD, plus the ideas platforms HEAD) is fanned
            # across a bounded thread pool so N keys resolve in ~1-2 round-trip
            # times instead of N serial HEADs — the serial fan-out blew the 12s
            # client abort on a cold container. Window order is preserved.
            window = keys[off:off + cap]
            items = _resolve_window_items(
                window, name, brand_index, product_index, client, bucket
            )
            count = len(items)
            has_more = (off + count) < total
            categories[name] = {
                "total": total,
                "offset": off,
                "count": count,
                "has_more": has_more,
                "next_offset": (off + count) if has_more else None,
                "items": items,
            }
        except Exception as e:  # noqa: BLE001 — one bad tab must not sink the listing
            print(f"[dam_library] category {name} failed: {e}")
            page = _empty_page(off)
            page["error"] = str(e)
            categories[name] = page

    return {"enabled": True, "bucket": bucket, "categories": categories}
