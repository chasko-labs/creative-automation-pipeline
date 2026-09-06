"""Read-only DAM asset browser — the ONE implementation of the curated picker listing.

Both surfaces call list_library(category, limit):
  - api.py's GET /assets/library (dev/local FastAPI)
  - generate_lambda.py's _handle_assets_library (deployed production path dispatcher)

The DAM bucket is fully private, so every item carries a presigned GET url (public urls
403). Bucket is resolved from dam._s3_bucket_and_prefix() — never hardcoded. raw-ingest/
is deliberately excluded (pipeline seed data, not picker assets).

Offline / CI path (dam._s3_enabled() False): returns {"enabled": False, "bucket": None,
"categories": {...empty...}, "note": ...} — mirrors the graceful S3-disabled fallback the
other /assets routes use, never raises.

Per-category errors (list or presign failure) degrade to that category's items=[] plus an
"error" note rather than failing the whole listing.
"""
from __future__ import annotations

import pathlib

from . import dam

# curated picker prefixes — raw-ingest/ deliberately excluded; heroes is nested
_LIBRARY_PREFIXES = {
    "zac-efron": ("brands/kodiak/zac-efron/", False),
    "renders": ("brands/kodiak/renders/", False),
    "heroes": ("brands/kodiak/heroes/", True),
    "logos": ("brands/kodiak/logos/", False),
}
_VIDEO_EXTS = {".mp4", ".mov", ".webm"}


def _kind(key: str) -> str:
    return "video" if pathlib.Path(key).suffix.lower() in _VIDEO_EXTS else "image"


def _label(key: str, name: str, nested: bool) -> str:
    if nested:
        # heroes: label from the MIDDLE product segment, not the filename
        parts = [p for p in key.split("/") if p]
        product = parts[-2] if len(parts) >= 2 else pathlib.Path(key).stem
        return f"{product} hero"
    stem = pathlib.Path(key).stem
    if name == "renders":
        return f"render {stem[:8]}"
    return stem.replace("-", " ").replace("_", " ").strip()


def list_library(category: str | None = None, limit: int = 60) -> dict:
    """List curated DAM picker prefixes with presigned GET urls.

    category: one of zac-efron|renders|heroes|logos; all four when absent/unknown.
    limit:    max presigned URLs minted per category (default 60, clamped to 1..200).

    Returns {"enabled": bool, "bucket": str|None, "categories": {name: {total, items[]}}}.
    Never raises — S3-disabled and per-category failures both degrade gracefully.
    """
    cap = max(1, min(int(limit), 200))
    wanted = [category] if category in _LIBRARY_PREFIXES else list(_LIBRARY_PREFIXES)

    if not dam._s3_enabled():
        return {
            "enabled": False,
            "bucket": None,
            "categories": {name: {"total": 0, "items": []} for name in wanted},
            "note": "DAM S3 not configured — set DAM_S3_BUCKET",
        }

    bucket, _ = dam._s3_bucket_and_prefix()
    client = dam._s3_client()
    categories: dict[str, dict] = {}

    for name in wanted:
        prefix, nested = _LIBRARY_PREFIXES[name]
        try:
            if client is None:
                raise RuntimeError("s3 client init failed")
            # list with a paginator; collect keys up to cap, but count the TRUE total
            paginator = client.get_paginator("list_objects_v2")
            total = 0
            keys: list[str] = []
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue  # skip directory placeholder objects
                    total += 1
                    if len(keys) < cap:
                        keys.append(key)
            items = []
            for key in keys:
                url = dam.presign_get(key)
                items.append({
                    "key": key,
                    "label": _label(key, name, nested),
                    "kind": _kind(key),
                    "url": url,
                })
            categories[name] = {"total": total, "items": items}
        except Exception as e:  # noqa: BLE001 — one bad category must not sink the listing
            print(f"[dam_library] category {name} failed s3://{bucket}/{prefix}: {e}")
            categories[name] = {"total": 0, "items": [], "error": str(e)}

    return {"enabled": True, "bucket": bucket, "categories": categories}
