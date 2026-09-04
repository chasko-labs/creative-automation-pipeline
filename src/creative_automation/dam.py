"""DAM lookup — S3-first with local input_assets fallback.

Priority:
1. explicit path (local or s3://)
2. S3 dam (if DAM_S3_BUCKET / DAM_S3_URI env set and boto3/creds available) — fetch to local cache
3. local dam_root fallback (input_assets/<product_id>/...)

Runbook sync (see docs/dam-runbook.md):
  # pull S3 -> local (preferred for offline / CI)
  aws s3 sync s3://$DAM_S3_BUCKET/dam input_assets --delete --only-show-errors
  # push local -> S3 (publish new assets)
  aws s3 sync input_assets s3://$DAM_S3_BUCKET/dam --delete --only-show-errors
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional — local-only mode still works
    boto3 = None  # type: ignore

ASSET_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
HERO_NAMES = {"hero", "main", "cover", "product"}
BRAND_NAMES = ("logo", "brand", "mark")


def _s3_bucket_and_prefix() -> tuple[Optional[str], str]:
    """Resolve bucket/prefix from DAM_S3_BUCKET + DAM_S3_PREFIX or DAM_S3_URI.

    Examples:
      DAM_S3_BUCKET=my-bucket DAM_S3_PREFIX=dam/  -> (my-bucket, dam/)
      DAM_S3_URI=s3://my-bucket/dam               -> (my-bucket, dam/)
    """
    uri = os.getenv("DAM_S3_URI", "").strip()
    if uri.startswith("s3://"):
        no_scheme = uri[5:]
        parts = no_scheme.split("/", 1)
        bucket = parts[0]
        prefix = (parts[1] + "/" if len(parts) > 1 and parts[1] else "")
        return bucket, prefix
    bucket = os.getenv("DAM_S3_BUCKET", "").strip() or None
    prefix = os.getenv("DAM_S3_PREFIX", "dam/")
    # normalize prefix to end with / if non-empty
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return bucket, prefix


def _s3_enabled() -> bool:
    bucket, _ = _s3_bucket_and_prefix()
    return bool(bucket and boto3 is not None)


def _s3_client():
    if not _s3_enabled():
        return None
    region = os.getenv("DAM_S3_REGION", os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1")))
    try:
        return boto3.client("s3", region_name=region)
    except Exception:
        return None


def _s3_download(bucket: str, key: str, dest: Path) -> bool:
    """Download single S3 key to dest. Returns True on success."""
    client = _s3_client()
    if client is None:
        return False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(bucket, key, str(dest))
        return dest.exists()
    except (ClientError, BotoCoreError, Exception) as e:
        print(f"[dam] s3 fetch miss s3://{bucket}/{key}: {e}")
        return False


def _s3_try_fetch_product_asset(product_id: str, dam_root: Path, explicit: Optional[str] = None) -> Optional[Path]:
    """Try to materialize hero asset from S3 into dam_root. Returns local path if fetched.

    Looks for s3://<bucket>/<prefix><product_id>/hero.* then any image under
    s3://<bucket>/<prefix><product_id>/ . Caches to dam_root/<product_id>/.
    """
    if not _s3_enabled():
        return None
    # if explicit is s3://, fetch that single key
    if explicit and explicit.startswith("s3://"):
        bucket, _ = _s3_bucket_and_prefix()
        # parse explicit s3 uri
        key = explicit[5:].split("/", 1)[1] if "/" in explicit[5:] else ""
        if not key:
            return None
        fname = Path(key).name
        dest = dam_root / product_id / fname
        if dest.exists():
            return dest
        if _s3_download(bucket, key, dest):  # type: ignore
            print(f"[dam] s3 hit {explicit} -> {dest}")
            return dest
        return None

    bucket, prefix = _s3_bucket_and_prefix()
    if not bucket:
        return None
    client = _s3_client()
    if client is None:
        return None
    base_prefix = f"{prefix}{product_id}/"

    # 1) hero.* candidates first
    for ext in ASSET_EXTS:
        for name in HERO_NAMES:
            key = f"{base_prefix}{name}{ext}"
            dest = dam_root / product_id / f"{name}{ext}"
            if dest.exists():
                return dest
            # need to check existence via HeadObject before download to avoid log noise?
            # try download optimistically
            if _s3_download(bucket, key, dest):
                print(f"[dam] s3 hit s3://{bucket}/{key}")
                return dest
            # remove empty file if download failed mid-way
            if dest.exists() and dest.stat().st_size == 0:
                try:
                    dest.unlink()
                except Exception:
                    pass

    # 2) any image under product prefix — list
    try:
        resp = client.list_objects_v2(Bucket=bucket, Prefix=base_prefix, MaxKeys=20)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if any(key.lower().endswith(ext) for ext in ASSET_EXTS):
                fname = Path(key).name
                dest = dam_root / product_id / fname
                if dest.exists():
                    return dest
                if _s3_download(bucket, key, dest):
                    print(f"[dam] s3 hit (list) s3://{bucket}/{key}")
                    return dest
    except (ClientError, BotoCoreError, Exception) as e:
        print(f"[dam] s3 list miss s3://{bucket}/{base_prefix}: {e}")
    return None


# Heroes live at a fixed brand path in the DAM, independent of the generic
# DAM_S3_PREFIX used for the dam/ style library. api.py, generate_lambda.py and
# the web mcp all cite s3://<bucket>/brands/kodiak/heroes/<product>/hero.png .
# Overridable for other brands / test buckets via DAM_HEROES_PREFIX.
def _heroes_prefix() -> str:
    prefix = os.getenv("DAM_HEROES_PREFIX", "brands/kodiak/heroes/").strip()
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


def fetch_hero_to_tmp(product_id: str, cache_root: Path = Path("/tmp/kodiak-assets")) -> Optional[Path]:  # noqa: S108 — Lambda only allows /tmp writes
    """Materialize a product hero from the S3 DAM into a Lambda-safe /tmp cache.

    Resolves s3://<DAM bucket>/<heroes prefix><product_id>/hero-real.png first
    (the retouched real asset), then hero.png. Downloads the first hit to
    cache_root/<product_id>/<name> and returns that local Path.

    Offline-safe: returns None when S3 is disabled (DAM_S3_BUCKET unset or boto3
    missing), when the client cannot init, or when neither key is present. Never
    raises — mirrors the graceful guards the rest of this module uses so local dev
    and CI (no S3 configured) fall through to the caller's local / mock path.
    """
    if not _s3_enabled():
        return None
    bucket, _ = _s3_bucket_and_prefix()
    if not bucket:
        return None
    base_prefix = f"{_heroes_prefix()}{product_id}/"
    # hero-real preferred over hero — matches _find_source_asset's local order
    for name in ("hero-real", "hero"):
        for ext in ASSET_EXTS:
            fname = f"{name}{ext}"
            key = f"{base_prefix}{fname}"
            dest = cache_root / product_id / fname
            if dest.exists() and dest.stat().st_size > 0:
                return dest
            if _s3_download(bucket, key, dest):
                print(f"[dam] hero s3 hit s3://{bucket}/{key} -> {dest}")
                return dest
            # _s3_download only creates the file on success, but guard against a
            # zero-byte partial from an interrupted transfer.
            if dest.exists() and dest.stat().st_size == 0:
                try:
                    dest.unlink()
                except Exception:
                    pass
    return None


def fetch_dam_key(key: str, dest: Path) -> Optional[Path]:
    """Download an EXPLICIT full DAM key to dest. Returns dest if fetched, else None.

    Unlike find_hero_asset / fetch_hero_to_tmp, the key is used VERBATIM against
    DAM_S3_BUCKET with NO prefix join — the sku-photo-map ships full keys under
    brands/kodiak/raw-ingest/... which are not under the dam/ DAM_S3_PREFIX. The
    bucket is resolved from _s3_bucket_and_prefix (bucket half only; prefix ignored).

    Offline-safe: returns None when S3 is disabled (DAM_S3_BUCKET unset or boto3
    missing), when the client cannot init, or when the object is absent. Never
    raises — mirrors the module's graceful guards so local dev / CI fall through.
    """
    if not key or not _s3_enabled():
        return None
    bucket, _ = _s3_bucket_and_prefix()
    if not bucket:
        return None
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    if _s3_download(bucket, key, dest):
        print(f"[dam] key s3 hit s3://{bucket}/{key} -> {dest}")
        return dest if dest.exists() else None
    # guard against a zero-byte partial from an interrupted transfer
    if dest.exists() and dest.stat().st_size == 0:
        try:
            dest.unlink()
        except Exception:
            pass
    return None


def _s3_try_fetch_brand_logo(dam_root: Path) -> Optional[Path]:
    if not _s3_enabled():
        return None
    bucket, prefix = _s3_bucket_and_prefix()
    if not bucket:
        return None
    client = _s3_client()
    if client is None:
        return None
    for sub in ("brand/", ""):
        base_prefix = f"{prefix}{sub}"
        # named candidates first
        for ext in ASSET_EXTS:
            for name in BRAND_NAMES:
                key = f"{base_prefix}{name}{ext}"
                # cache under dam_root/brand/ or dam_root/
                rel = f"brand/{name}{ext}" if sub == "brand/" else f"{name}{ext}"
                dest = dam_root / rel
                if dest.exists():
                    return dest
                if _s3_download(bucket, key, dest):
                    print(f"[dam] s3 hit s3://{bucket}/{key}")
                    return dest
                if dest.exists() and dest.stat().st_size == 0:
                    try:
                        dest.unlink()
                    except Exception:
                        pass
        # fallback list any image in that prefix
        try:
            resp = client.list_objects_v2(Bucket=bucket, Prefix=base_prefix, MaxKeys=20)
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if any(key.lower().endswith(ext) for ext in ASSET_EXTS):
                    fname = Path(key).name
                    rel_dir = "brand" if sub == "brand/" else ""
                    dest = dam_root / rel_dir / fname if rel_dir else dam_root / fname
                    if dest.exists():
                        return dest
                    if _s3_download(bucket, key, dest):
                        print(f"[dam] s3 hit (list) s3://{bucket}/{key}")
                        return dest
        except (ClientError, BotoCoreError, Exception) as e:
            print(f"[dam] s3 list miss s3://{bucket}/{base_prefix}: {e}")
    return None


# ------------------------------------------------------------------ local helpers
def _local_find_hero(product_id: str, dam_root: Path, explicit: Optional[str] = None) -> Optional[Path]:
    if explicit:
        p = Path(explicit)
        if p.is_absolute():
            if p.exists():
                return p
        else:
            # explicit may be relative to dam_root
            q = dam_root / p
            if q.exists():
                return q
            # also try as raw path (brief absolute/relative elsewhere)
            if p.exists():
                return p
    product_dir = dam_root / product_id
    if product_dir.is_dir():
        for ext in ASSET_EXTS:
            for name in HERO_NAMES:
                c = product_dir / f"{name}{ext}"
                if c.exists():
                    return c
        for ext in ASSET_EXTS:
            hits = list(product_dir.glob(f"*{ext}"))
            if hits:
                return sorted(hits)[0]
    return None


def _local_find_brand(dam_root: Path) -> Optional[Path]:
    for base in [dam_root / "brand", dam_root]:
        if base.is_dir():
            for ext in ASSET_EXTS:
                for name in BRAND_NAMES:
                    c = base / f"{name}{ext}"
                    if c.exists():
                        return c
            for ext in ASSET_EXTS:
                hits = list(base.glob(f"*{ext}"))
                if hits:
                    return hits[0]
    return None


# ------------------------------------------------------------------ public API (backward-compatible)
def find_hero_asset(product_id: str, dam_root: Path, explicit: Optional[str] = None) -> Optional[Path]:
    """Return hero image path if found, else None.

    Lookup order:
    1. explicit path if provided (local or s3:// — s3 fetched to cache)
    2. S3 dam: s3://$DAM_S3_BUCKET/$DAM_S3_PREFIX<product_id>/hero.* or any image (cached to dam_root)
    3. local dam_root / product_id / hero.* (any ext)
    4. local dam_root / product_id / any image

    Env:
      DAM_S3_BUCKET, DAM_S3_PREFIX (default dam/), DAM_S3_URI (alt s3://bucket/prefix),
      DAM_S3_REGION / BEDROCK_REGION / AWS_REGION, standard AWS credential chain.
    When S3 env not set or boto3 unavailable, steps 2 is skipped — pure local (existing tests pass).
    """
    # explicit s3:// handled inside s3 fetch
    if explicit and explicit.startswith("s3://"):
        hit = _s3_try_fetch_product_asset(product_id, dam_root, explicit)
        if hit:
            return hit
        # fall through to local explicit check

    # S3 first (cached) — keeps dam usable when input_assets empty but bucket populated
    s3_hit = _s3_try_fetch_product_asset(product_id, dam_root)
    if s3_hit:
        return s3_hit

    # local fallback
    return _local_find_hero(product_id, dam_root, explicit)


def find_brand_logo(dam_root: Path) -> Optional[Path]:
    """Return brand logo path if found, else None. S3-first, local fallback.

    Checks s3://$DAM_S3_BUCKET/$DAM_S3_PREFIX{brand/,}logo.* then local dam_root/brand/logo.* .
    """
    s3_hit = _s3_try_fetch_brand_logo(dam_root)
    if s3_hit:
        return s3_hit
    return _local_find_brand(dam_root)


def s3_upload_and_presign(local_path: Path, key: str, expires: int = 3600) -> Optional[str]:
    """Upload local_path to the DAM bucket under <prefix><key>, return a presigned GET url.

    Mirrors the module's graceful pattern: returns None when S3 is disabled (no
    DAM_S3_BUCKET / boto3 missing / client init fails) so callers fall back to a
    local path in offline / CI mode. The key is joined to the configured DAM prefix
    (same prefix _s3_bucket_and_prefix resolves for reads), so a caller passing
    "packs/foo.zip" lands at s3://<bucket>/<prefix>packs/foo.zip.
    """
    if not _s3_enabled():
        return None
    local_path = Path(local_path)
    if not local_path.exists():
        print(f"[dam] presign skipped — local artifact absent: {local_path}")
        return None
    bucket, prefix = _s3_bucket_and_prefix()
    client = _s3_client()
    if not bucket or client is None:
        return None
    full_key = f"{prefix}{key.lstrip('/')}"
    try:
        client.upload_file(str(local_path), bucket, full_key)
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": full_key},
            ExpiresIn=expires,
        )
        print(f"[dam] uploaded {local_path} -> s3://{bucket}/{full_key} (presigned {expires}s)")
        return url
    except (ClientError, BotoCoreError, Exception) as e:
        print(f"[dam] upload/presign failed s3://{bucket}/{full_key}: {e}")
        return None


def sync_dam_from_s3(dam_root: Path, delete: bool = False) -> bool:
    """Optional helper: bulk sync S3 prefix -> local dam_root via boto3.

    Prefer CLI `aws s3 sync` in runbook for large syncs; this is a lightweight
    boto3 fallback for lambda/agentcore where CLI not available.
    Returns True if any file synced.
    """
    if not _s3_enabled():
        print("[dam] sync skipped — DAM_S3_BUCKET not set or boto3 missing")
        return False
    bucket, prefix = _s3_bucket_and_prefix()
    client = _s3_client()
    if not bucket or client is None:
        return False
    try:
        paginator = client.get_paginator("list_objects_v2")
        synced = 0
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                rel = key[len(prefix):] if key.startswith(prefix) else key
                if not rel:
                    continue
                dest = dam_root / rel
                # simple mtime/size check — skip if exists and size matches
                if dest.exists() and dest.stat().st_size == obj.get("Size"):
                    continue
                if _s3_download(bucket, key, dest):
                    synced += 1
        print(f"[dam] sync s3://{bucket}/{prefix} -> {dam_root} synced={synced}")
        return synced > 0
    except (ClientError, BotoCoreError, Exception) as e:
        print(f"[dam] bulk sync failed: {e}")
        return False
