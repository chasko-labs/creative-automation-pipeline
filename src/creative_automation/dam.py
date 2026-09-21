"""DAM lookup — S3-first with local input_assets fallback.

Priority:
1. explicit path (local or s3://)
2. S3 dam (if DAM_S3_BUCKET / DAM_S3_URI env set and boto3/creds available) — fetch to local cache
3. local dam_root fallback (input_assets/<product_id>/...)

Runbook sync (see docs/asset-library-runbook.md):
  # pull S3 -> local (preferred for offline / CI)
  aws s3 sync s3://$DAM_S3_BUCKET/dam input_assets --delete --only-show-errors
  # push local -> S3 (publish new assets)
  aws s3 sync input_assets s3://$DAM_S3_BUCKET/dam --delete --only-show-errors
"""
from __future__ import annotations

import json
import os
from pathlib import Path

try:
    import boto3
    from botocore.config import Config as _BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional — local-only mode still works
    boto3 = None  # type: ignore
    _BotoConfig = None  # type: ignore

ASSET_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
HERO_NAMES = {"hero", "main", "cover", "product"}
BRAND_NAMES = ("logo", "brand", "mark")

# LOOP-LEVEL DEADLINE FLOOR: the probe functions accept an optional deadline callback
# (a zero-arg callable returning remaining budget in ms, threaded from generate.py's
# remaining_ms). A probe loop ABANDONS the moment remaining drops below this floor, so a
# fan-out of ~50 serial S3 misses cannot run to the full ~37s even with the per-call
# botocore timeout — it bails mid-loop and the caller drops to rung C/D (no-seed). Reuse
# the rung-C reservation idea: stop probing while ~3s of budget still remains.
DAM_PROBE_FLOOR_MS = int(os.getenv("DAM_PROBE_FLOOR_MS", "3000"))


def _deadline_exceeded(deadline_ms) -> bool:
    """True when a deadline callback is supplied AND remaining budget < the floor.

    deadline_ms is a zero-arg callable returning remaining milliseconds (generate.py's
    remaining_ms). None means no deadline threaded (offline / test / CLI) — never abandons.
    """
    if deadline_ms is None:
        return False
    try:
        return deadline_ms() < DAM_PROBE_FLOOR_MS
    except Exception:  # noqa: BLE001 — deadline probe must never raise; assume time remains
        return False

# The S3-fetch cache must land on a WRITABLE fs. Lambda mounts /var/task read-only
# and only guarantees /tmp is writable, so caching under the relative input_assets
# root (which resolves under /var/task on Lambda) raises Errno 30 on the dest.mkdir
# for every candidate key — the ~16-candidate retry loop then blows the 30s API
# Gateway budget -> 503. /tmp/kodiak-assets is always writable on Lambda AND locally,
# and mirrors the convention resolve_packshot / fetch_hero_to_tmp already use. Env
# override (DAM_CACHE_ROOT) wins for callers that need a bespoke cache location.
_DEFAULT_CACHE_ROOT = "/tmp/kodiak-assets"


def _dam_cache_root() -> Path:
    """Writable root for S3-fetch downloads: $DAM_CACHE_ROOT, else /tmp/kodiak-assets.

    Never returns the read-only relative input_assets. Local reads still hit the
    caller-supplied dam_root; only the fetched-asset WRITE destination moves here.
    """
    return Path(os.getenv("DAM_CACHE_ROOT", "").strip() or _DEFAULT_CACHE_ROOT)


def _s3_bucket_and_prefix() -> tuple[str | None, str]:
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
        # FAIL-FAST config: an unmapped-SKU probe fans out ~50 SERIAL HeadObject/GetObject
        # misses. A bare client (no timeouts, default 3-retry mode) lets those misses run
        # unbounded to ~37s and 503 at the 30s API Gateway edge. Bound every call to a few
        # seconds worst case and kill the retry multiplier so ~50 misses cannot exceed the
        # budget. Same class of fix already applied to the Bedrock client in generate.py.
        read_timeout = int(os.getenv("DAM_S3_READ_TIMEOUT_S", "2"))
        connect_timeout = int(os.getenv("DAM_S3_CONNECT_TIMEOUT_S", "1"))
        cfg = None
        if _BotoConfig is not None:
            cfg = _BotoConfig(
                signature_version="s3v4",
                connect_timeout=connect_timeout,
                read_timeout=read_timeout,
                retries={"max_attempts": 1, "mode": "standard"},
            )
        return boto3.client("s3", region_name=region, config=cfg)
    except Exception:  # noqa: BLE001 — client init is optional; None means offline S3
        return None


def _s3_download(bucket: str, key: str, dest: Path) -> bool:
    """Download single S3 key to dest via bounded get_object + body.read(). True on success.

    OUTER-WALL PREREQUISITE (#118): boto3 client.download_file() drives the S3 Transfer
    manager, which spins its OWN worker thread pool. The botocore read_timeout on the
    _s3_client() Config bounds a SINGLE socket read, NOT the overall transfer — a stalled
    warm-container connection can therefore hang ~33s inside the Transfer manager despite
    the 2s read_timeout, and the abandoned-thread leak the handler wall relies on would be
    a whole Transfer thread pool, not a single socket. get_object has no Transfer-manager
    threading: it is one bounded HTTP GET whose body.read() we drain inline under the SAME
    fail-fast Config (connect 1s / read 2s / max_attempts 1) the client already carries.
    An abandoned thread on this path is therefore a single safe socket read — that is what
    makes the handler-level outer wall's leaked-thread abandonment safe.
    """
    client = _s3_client()
    if client is None:
        return False
    try:
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            # Read-only fs (Errno 30) or perms — degrade gracefully rather than raise
            # and blow the retry-loop time budget. Caller falls through to the next
            # candidate / local path. The writable _dam_cache_root default should keep
            # this from firing on Lambda, but the guard is the belt to that suspenders.
            print(f"[dam] s3 cache dir unwritable {dest.parent}: {e}")
            return False
        # get_object (no Transfer manager) + explicit body.read(), then write the bytes
        # to dest — preserves the write-to-dest contract download_file provided. The read
        # is bounded by the client Config's read_timeout; a stalled read raises and falls
        # to the miss path rather than hanging a Transfer worker pool for ~33s.
        resp = client.get_object(Bucket=bucket, Key=key)
        body = resp["Body"].read()
        with open(dest, "wb") as fh:
            fh.write(body)
        return dest.exists()
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — any fetch miss degrades to local
        print(f"[dam] s3 fetch miss s3://{bucket}/{key}: {e}")
        return False


def _s3_try_fetch_product_asset(product_id: str, dam_root: Path, explicit: str | None = None, deadline_ms=None) -> Path | None:
    """Try to materialize hero asset from S3 into a writable cache. Returns local path if fetched.

    Looks for s3://<bucket>/<prefix><product_id>/hero.* then any image under
    s3://<bucket>/<prefix><product_id>/ . A pre-synced hit under dam_root/<product_id>/
    is honored first (local read), but fetched downloads are written to
    _dam_cache_root()/<product_id>/ — never the (possibly read-only) dam_root — so the
    Lambda /var/task read-only fs cannot break the fetch.

    deadline_ms (optional zero-arg callable -> remaining ms) bounds the ASSET_EXTS x
    HERO_NAMES fan-out: the loop ABANDONS once remaining < DAM_PROBE_FLOOR_MS.
    """
    if not _s3_enabled():
        return None
    cache_root = _dam_cache_root()
    # if explicit is s3://, fetch that single key
    if explicit and explicit.startswith("s3://"):
        bucket, _ = _s3_bucket_and_prefix()
        # parse explicit s3 uri
        key = explicit[5:].split("/", 1)[1] if "/" in explicit[5:] else ""
        if not key:
            return None
        fname = Path(key).name
        # honor a pre-synced local copy under dam_root, else download to the cache root
        local_pre = dam_root / product_id / fname
        if local_pre.exists():
            return local_pre
        dest = cache_root / product_id / fname
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
            if _deadline_exceeded(deadline_ms):
                print(f"[dam] product probe abandoned mid-fan-out (budget floor) s3://{bucket}/{base_prefix}")
                return None
            key = f"{base_prefix}{name}{ext}"
            # pre-synced local copy under dam_root wins (offline / CI), else cache root
            local_pre = dam_root / product_id / f"{name}{ext}"
            if local_pre.exists():
                return local_pre
            dest = cache_root / product_id / f"{name}{ext}"
            if dest.exists():
                return dest
            # try download optimistically
            if _s3_download(bucket, key, dest):
                print(f"[dam] s3 hit s3://{bucket}/{key}")
                return dest
            # remove empty file if download failed mid-way
            if dest.exists() and dest.stat().st_size == 0:
                try:
                    dest.unlink()
                except OSError as e:
                    print(f"[dam] partial cleanup unlink failed {dest}: {e}")

    # 2) any image under product prefix — list
    if _deadline_exceeded(deadline_ms):
        print(f"[dam] product list probe skipped (budget floor) s3://{bucket}/{base_prefix}")
        return None
    try:
        resp = client.list_objects_v2(Bucket=bucket, Prefix=base_prefix, MaxKeys=20)
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            if any(key.lower().endswith(ext) for ext in ASSET_EXTS):
                fname = Path(key).name
                local_pre = dam_root / product_id / fname
                if local_pre.exists():
                    return local_pre
                dest = cache_root / product_id / fname
                if dest.exists():
                    return dest
                if _s3_download(bucket, key, dest):
                    print(f"[dam] s3 hit (list) s3://{bucket}/{key}")
                    return dest
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — any list miss falls to serial probes
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


# Deterministic hero preference: retouched hero-real before hero, lossless
# .png before lossy exts. ASSET_EXTS is a set (no stable order), so ranking is
# explicit here — the serial fallback below iterates this same order.
_HERO_FILE_RANK = (
    "hero-real.png",
    "hero-real.jpg",
    "hero-real.jpeg",
    "hero-real.webp",
    "hero.png",
    "hero.jpg",
    "hero.jpeg",
    "hero.webp",
)


def _rank_hero_key(key: str) -> tuple[int, int]:
    """Sort key for hero candidates: hero-real before hero, .png first.

    Unknown names sort last (never dropped — a key is still downloadable).
    """
    fname = Path(key).name.lower()
    try:
        return (0, _HERO_FILE_RANK.index(fname))
    except ValueError:
        stem = Path(fname).stem
        return (0 if stem == "hero-real" else 1, len(_HERO_FILE_RANK))


def fetch_hero_to_tmp(product_id: str, cache_root: Path = Path("/tmp/kodiak-assets"), deadline_ms=None) -> Path | None:
    """Materialize a product hero from the S3 DAM into a Lambda-safe /tmp cache.

    Resolves s3://<DAM bucket>/<heroes prefix><product_id>/hero-real.png first
    (the retouched real asset), then hero.png. Downloads the first hit to
    cache_root/<product_id>/<name> and returns that local Path.

    LIST-FIRST (wall repair): one list_objects_v2 on the product prefix resolves
    or misses the whole directory in a single round trip. The old serial loop
    issued up to 8 GETs (hero-real/hero x 4 exts) — on a total miss that was 8
    failed round trips against the 22s handler wall, PROVEN IN PROD (8x
    NoSuchKey immediately before wall-timeout fallthrough). The serial loop is
    kept ONLY as a fallback for narrow IAM without ListBucket.

    Offline-safe: returns None when S3 is disabled (DAM_S3_BUCKET unset or boto3
    missing), when the client cannot init, or when neither key is present. Never
    raises — mirrors the graceful guards the rest of this module uses so local dev
    and CI (no S3 configured) fall through to the caller's local / mock path.

    deadline_ms (optional zero-arg callable -> remaining ms) bounds the fan-out:
    the probe ABANDONS once remaining < DAM_PROBE_FLOOR_MS, returning None so the
    ladder drops to rung C/D instead of blowing the 30s edge.
    """
    if not _s3_enabled():
        return None
    bucket, _ = _s3_bucket_and_prefix()
    if not bucket:
        return None
    base_prefix = f"{_heroes_prefix()}{product_id}/"
    # warm-container cache first — no S3 round trip at all, deterministic order.
    for fname in _HERO_FILE_RANK:
        dest = cache_root / product_id / fname
        try:
            if dest.exists() and dest.stat().st_size > 0:
                return dest
        except OSError:
            pass
    if _deadline_exceeded(deadline_ms):
        print(f"[dam] hero probe abandoned (budget floor) s3://{bucket}/{base_prefix}")
        return None
    # list-first: one round trip resolves-or-misses the whole product dir.
    try:
        client = _s3_client()
        if client is not None:
            resp = client.list_objects_v2(Bucket=bucket, Prefix=base_prefix, MaxKeys=32)
            keys = sorted(
                (
                    obj["Key"]
                    for obj in resp.get("Contents", [])
                    if obj.get("Key", "").lower().endswith(tuple(sorted(ASSET_EXTS)))
                ),
                key=_rank_hero_key,
            )
            for key in keys:
                if _deadline_exceeded(deadline_ms):
                    print(f"[dam] hero probe abandoned mid-list (budget floor) s3://{bucket}/{base_prefix}")
                    return None
                dest = cache_root / product_id / Path(key).name
                try:
                    if dest.exists() and dest.stat().st_size > 0:
                        return dest
                except OSError:
                    pass
                if _s3_download(bucket, key, dest):
                    print(f"[dam] hero s3 hit (list) s3://{bucket}/{key} -> {dest}")
                    return dest
                if dest.exists() and dest.stat().st_size == 0:
                    try:
                        dest.unlink()
                    except OSError as e:
                        print(f"[dam] partial cleanup unlink failed {dest}: {e}")
            # listed authoritatively: nothing usable under the prefix — a miss
            # costs exactly 1 LIST and 0 GETs. No serial fan-out.
            print(f"[dam] hero list miss s3://{bucket}/{base_prefix}")
            return None
    except Exception as e:  # noqa: BLE001 — narrow IAM (no ListBucket) etc.
        print(f"[dam] hero list unavailable, serial fallback s3://{bucket}/{base_prefix}: {e}")
    # serial fallback — hero-real preferred over hero, deterministic ext order.
    for fname in _HERO_FILE_RANK:
        if _deadline_exceeded(deadline_ms):
            print(f"[dam] hero probe abandoned mid-fan-out (budget floor) s3://{bucket}/{base_prefix}")
            return None
        key = f"{base_prefix}{fname}"
        dest = cache_root / product_id / fname
        try:
            if dest.exists() and dest.stat().st_size > 0:
                return dest
        except OSError:
            pass
        if _s3_download(bucket, key, dest):
            print(f"[dam] hero s3 hit s3://{bucket}/{key} -> {dest}")
            return dest
        # _s3_download only creates the file on success, but guard against a
        # zero-byte partial from an interrupted transfer.
        if dest.exists() and dest.stat().st_size == 0:
            try:
                dest.unlink()
            except OSError as e:
                print(f"[dam] partial cleanup unlink failed {dest}: {e}")
    return None


def fetch_dam_key(key: str, dest: Path) -> Path | None:
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
        except OSError as e:
            print(f"[dam] partial cleanup unlink failed {dest}: {e}")
    return None


# --------------------------------------------------------- SKU -> packshot resolver
# The packshot manifest maps sku-id -> the REAL product-box image (705599* UPC key).
# Resolving it BEFORE any generative step is the compose-fix root-cause repair: a pasted
# real box cannot render as bread or candy. Manifest lives at the committed contract path
# by default; $SKU_PACKSHOT_MAP_PATH overrides for Lambda / test layouts. See
# docs/architecture/compose-fix/compose-fix-spec.md.
_SKU_PACKSHOT_MAP_PATH = (
    Path(__file__).parents[2] / "docs" / "architecture" / "compose-fix" / "sku-packshot-map.json"
)
_SKU_PACKSHOT_MAP_CACHE: dict | None = None


def _resolve_packshot_map_path() -> Path:
    """First existing packshot-manifest path; env override wins, else committed doc, else packaged."""
    candidates: list[Path] = []
    env = os.getenv("SKU_PACKSHOT_MAP_PATH")
    if env:
        candidates.append(Path(env))
    candidates.append(_SKU_PACKSHOT_MAP_PATH)
    candidates.append(Path(__file__).parent / "data" / "sku-packshot-map.json")
    for c in candidates:
        if c.exists():
            return c
    return _SKU_PACKSHOT_MAP_PATH


def _load_packshot_map() -> dict:
    """Load the packshot manifest once -> {handle: entry}. Empty dict on any failure."""
    global _SKU_PACKSHOT_MAP_CACHE
    if _SKU_PACKSHOT_MAP_CACHE is not None:
        return _SKU_PACKSHOT_MAP_CACHE
    try:
        data = json.loads(_resolve_packshot_map_path().read_text(encoding="utf-8"))
        _SKU_PACKSHOT_MAP_CACHE = data.get("map", {}) if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001 — missing/unreadable manifest -> generative fallback
        print(f"[dam] sku-packshot-map load skipped: {e}")
        _SKU_PACKSHOT_MAP_CACHE = {}
    return _SKU_PACKSHOT_MAP_CACHE


def _norm_handle(product_id: str) -> str:
    """Normalize a product_id to the map handle: lowercase, spaces -> hyphens, trimmed."""
    return "-".join(str(product_id).strip().lower().split()).strip("-")


def _packshot_entry_for(product_id: str) -> dict | None:
    """Match a product_id to a manifest entry: exact handle, then normalized, then longest-prefix."""
    m = _load_packshot_map()
    if not m:
        return None
    if product_id in m and isinstance(m[product_id], dict):
        return m[product_id]
    norm = _norm_handle(product_id)
    if norm in m and isinstance(m[norm], dict):
        return m[norm]
    # longest-prefix match so "chocolate-fudge" matches "chocolate-fudge-brownie-mix"
    best_key: str | None = None
    for k in m:
        kn = _norm_handle(k)
        if ((norm.startswith(kn) or kn.startswith(norm)) and isinstance(m[k], dict)
                and (best_key is None or len(kn) > len(_norm_handle(best_key)))):
            best_key = k
    return m[best_key] if best_key else None


def _looks_like_box(key: str) -> bool:
    """Heuristic: a real product-BOX key carries the 705599* UPC prefix in its filename."""
    name = key.rsplit("/", 1)[-1]
    return "705599" in name


def resolve_packshot(product_id: str, dam_root: Path | None = None, deadline_ms=None) -> Path | None:
    """Return a local path to the REAL product-box packshot for a SKU, else None.

    Manifest-first (unlike find_hero_asset). Resolution chain, in order:
      1. manifest packshot_key      -> fetch_dam_key verbatim (no prefix join)
      2. manifest fallbacks[] boxes -> fetch_dam_key per 705599* candidate
      3. fuzzy find_hero_asset      -> S3 prefix + local glob
      4. none                       -> return None (caller falls to generated-scene)

    Offline-safe: fetch_dam_key returns None when S3 is disabled, so local dev / CI
    fall straight through to step 3 (local glob) or None. Never raises.

    deadline_ms (optional zero-arg callable -> remaining ms) is threaded into step 3's
    find_hero_asset fan-out so an unmapped-SKU probe abandons mid-loop past the floor.
    """
    cache_dir = Path("/tmp/kodiak-assets/packshot")
    entry = _packshot_entry_for(product_id)
    if isinstance(entry, dict):
        # 1) explicit packshot box
        pk = entry.get("packshot_key")
        if isinstance(pk, str) and pk.strip():
            dest = cache_dir / pk.rsplit("/", 1)[-1]
            hit = fetch_dam_key(pk, dest)
            if hit is not None:
                return hit
        # 2) box-like fallbacks / lifestyle_keys that carry the UPC prefix
        for cand in (entry.get("fallbacks") or []) + (entry.get("lifestyle_keys") or []):
            if isinstance(cand, str) and cand.strip() and _looks_like_box(cand):
                dest = cache_dir / cand.rsplit("/", 1)[-1]
                hit = fetch_dam_key(cand, dest)
                if hit is not None:
                    return hit
    # 3) fuzzy glob — reuse the existing S3-prefix + local-glob primitive
    root = dam_root or Path("input_assets")
    fuzzy = find_hero_asset(product_id, root, deadline_ms=deadline_ms)
    if fuzzy is not None and _looks_like_box(str(fuzzy)):
        return fuzzy
    # 4) nothing box-like resolved
    return None


def _s3_try_fetch_brand_logo(dam_root: Path) -> Path | None:
    if not _s3_enabled():
        return None
    bucket, prefix = _s3_bucket_and_prefix()
    if not bucket:
        return None
    client = _s3_client()
    if client is None:
        return None
    cache_root = _dam_cache_root()
    for sub in ("brand/", ""):
        base_prefix = f"{prefix}{sub}"
        # named candidates first
        for ext in ASSET_EXTS:
            for name in BRAND_NAMES:
                key = f"{base_prefix}{name}{ext}"
                # cache under brand/ or root; check pre-synced dam_root first, write to cache_root
                rel = f"brand/{name}{ext}" if sub == "brand/" else f"{name}{ext}"
                local_pre = dam_root / rel
                if local_pre.exists():
                    return local_pre
                dest = cache_root / rel
                if dest.exists():
                    return dest
                if _s3_download(bucket, key, dest):
                    print(f"[dam] s3 hit s3://{bucket}/{key}")
                    return dest
                if dest.exists() and dest.stat().st_size == 0:
                    try:
                        dest.unlink()
                    except OSError as e:
                        print(f"[dam] partial cleanup unlink failed {dest}: {e}")
        # fallback list any image in that prefix
        try:
            resp = client.list_objects_v2(Bucket=bucket, Prefix=base_prefix, MaxKeys=20)
            for obj in resp.get("Contents", []):
                key = obj["Key"]
                if any(key.lower().endswith(ext) for ext in ASSET_EXTS):
                    fname = Path(key).name
                    rel_dir = "brand" if sub == "brand/" else ""
                    local_pre = dam_root / rel_dir / fname if rel_dir else dam_root / fname
                    if local_pre.exists():
                        return local_pre
                    dest = cache_root / rel_dir / fname if rel_dir else cache_root / fname
                    if dest.exists():
                        return dest
                    if _s3_download(bucket, key, dest):
                        print(f"[dam] s3 hit (list) s3://{bucket}/{key}")
                        return dest
        except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — any list miss degrades to local
            print(f"[dam] s3 list miss s3://{bucket}/{base_prefix}: {e}")
    return None


# ------------------------------------------------------------------ local helpers
def _local_find_hero(product_id: str, dam_root: Path, explicit: str | None = None) -> Path | None:
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
                return min(hits)
    return None


def _local_find_brand(dam_root: Path) -> Path | None:
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
def find_hero_asset(product_id: str, dam_root: Path, explicit: str | None = None, deadline_ms=None) -> Path | None:
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

    deadline_ms (optional zero-arg callable -> remaining ms) threads through the S3
    fan-out so the probe abandons mid-loop once remaining < DAM_PROBE_FLOOR_MS.
    """
    # explicit s3:// handled inside s3 fetch
    if explicit and explicit.startswith("s3://"):
        hit = _s3_try_fetch_product_asset(product_id, dam_root, explicit, deadline_ms)
        if hit:
            return hit
        # fall through to local explicit check

    # S3 first (cached) — keeps dam usable when input_assets empty but bucket populated
    s3_hit = _s3_try_fetch_product_asset(product_id, dam_root, deadline_ms=deadline_ms)
    if s3_hit:
        return s3_hit

    # local fallback
    return _local_find_hero(product_id, dam_root, explicit)


def find_brand_logo(dam_root: Path) -> Path | None:
    """Return brand logo path if found, else None. S3-first, local fallback.

    Checks s3://$DAM_S3_BUCKET/$DAM_S3_PREFIX{brand/,}logo.* then local dam_root/brand/logo.* .
    """
    s3_hit = _s3_try_fetch_brand_logo(dam_root)
    if s3_hit:
        return s3_hit
    return _local_find_brand(dam_root)


def s3_upload_and_presign(local_path: Path, key: str, expires: int = 3600) -> str | None:
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
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — upload failure returns None
        print(f"[dam] upload/presign failed s3://{bucket}/{full_key}: {e}")
        return None


def presign_get(key: str, expires: int = 3600) -> str | None:
    """Presign a GET for an EXISTING DAM key. Returns url, or None when S3 disabled.

    Read-only companion to s3_upload_and_presign (which uploads then presigns). The
    key is used VERBATIM against the DAM bucket with NO prefix join — the asset
    browser passes full keys (brands/kodiak/...) that are not under DAM_S3_PREFIX,
    same contract as fetch_dam_key. Offline-safe: returns None when S3 is disabled
    (no DAM_S3_BUCKET / boto3 missing / client init fails) so callers degrade to a
    null url rather than raising. Never throws.
    """
    if not key or not _s3_enabled():
        return None
    bucket, _ = _s3_bucket_and_prefix()
    client = _s3_client()
    if not bucket or client is None:
        return None
    try:
        return client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — presign failure returns None
        print(f"[dam] presign_get failed s3://{bucket}/{key}: {e}")
        return None


def head_metadata(key: str) -> dict:
    """HEAD one DAM key and return its user metadata (x-amz-meta-*) lowercased.

    Read side of the publish-time platform tags the generate Lambda stamps at
    upload (_upload_render Metadata={"platforms": ...}). Returns {} when S3 is
    disabled, the key is missing, or any error occurs. Never throws.
    """
    if not key or not _s3_enabled():
        return {}
    bucket, _ = _s3_bucket_and_prefix()
    client = _s3_client()
    if not bucket or client is None:
        return {}
    try:
        resp = client.head_object(Bucket=bucket, Key=key)
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — metadata miss returns {}
        print(f"[dam] head_metadata failed s3://{bucket}/{key}: {e}")
        return {}
    meta = resp.get("Metadata") or {}
    return {str(k).lower(): v for k, v in meta.items()}


# ------------------------------------------------------------------ recipe-art
# Recipe-card sketch-zone art lives at a fixed brand path, sibling to recipes/ and
# heroes/. Full key: brands/kodiak/recipe-art/<subject_slug>/<zone>.png . These assets
# live in account 946179428633 (bryanchasko-kiro), same DAM bucket as the rest of the
# kodiak brand. Overridable via DAM_RECIPE_ART_PREFIX for other brands / test buckets.
def _recipe_art_prefix() -> str:
    prefix = os.getenv("DAM_RECIPE_ART_PREFIX", "brands/kodiak/recipe-art/").strip()
    if prefix and not prefix.endswith("/"):
        prefix += "/"
    return prefix


def recipe_art_key(subject_slug: str, zone: str) -> str:
    """Full DAM key for a recipe-art asset: <prefix><subject_slug>/<zone>.png."""
    return f"{_recipe_art_prefix()}{subject_slug}/{zone}.png"


def recipe_art_exists(subject_slug: str, zone: str) -> bool:
    """HEAD the recipe-art key — True when the object already exists in the DAM.

    Lets the seeder skip regeneration (and re-billing) when the drawing is already
    published. Returns False when S3 is disabled, the key is absent, or any error
    occurs. Never throws.
    """
    key = recipe_art_key(subject_slug, zone)
    if not _s3_enabled():
        return False
    bucket, _ = _s3_bucket_and_prefix()
    client = _s3_client()
    if not bucket or client is None:
        return False
    try:
        client.head_object(Bucket=bucket, Key=key)
        return True
    except (ClientError, BotoCoreError, Exception):  # noqa: BLE001 — miss => False
        return False


def recipe_art_site_url(subject_slug: str, zone: str) -> str:
    """Permanent site URL for a recipe-art asset: /recipe-art/<slug>/<zone>.png.

    Root-absolute (the recipes page also serves from the /recipes/ prefix, so a
    relative url would resolve wrong there). The deploy script mirrors the DAM
    recipe-art prefix into the site's recipe-art/ dir, so this url never expires —
    unlike presigned urls, which die with the signing session (ASIA creds) no
    matter what ExpiresIn is set to.
    """
    return f"/recipe-art/{subject_slug}/{zone}.png"


def upload_recipe_art(local_png: Path, subject_slug: str, zone: str) -> str | None:
    """Upload a recipe-art PNG to brands/kodiak/recipe-art/<slug>/<zone>.png.

    Returns the PERMANENT site url on success, else None (S3 disabled, missing
    file, or upload failure) so callers degrade to a null art url and the
    frontend falls back to its SVG placeholder. Never throws.

    Deliberately not a presigned url: recipe-cards-data.js is a precomputed
    artifact served for weeks, and presigns made with session credentials expire
    with the session (ExpiredToken) regardless of ExpiresIn.

    Mirrors publish_card: the full key is relativized against the configured DAM
    prefix before handing to s3_upload_and_presign (which re-joins the prefix), so
    the object lands at the exact recipe_art_key path and reads back verbatim.
    The presigned url it returns is discarded in favor of recipe_art_site_url.
    """
    local_png = Path(local_png)
    if not local_png.exists():
        print(f"[dam] recipe-art upload skipped — local png absent: {local_png}")
        return None
    full = recipe_art_key(subject_slug, zone)
    _, prefix = _s3_bucket_and_prefix()
    rel = full[len(prefix):] if prefix and full.startswith(prefix) else full.lstrip("/")
    if s3_upload_and_presign(str(local_png), rel, expires=604800) is None:
        return None
    return recipe_art_site_url(subject_slug, zone)


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
                rel = key.removeprefix(prefix)
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
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — sync failure returns False
        print(f"[dam] bulk sync failed: {e}")
        return False
