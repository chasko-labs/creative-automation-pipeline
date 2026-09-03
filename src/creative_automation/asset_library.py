"""AssetLibrary — first DAM write-path: classify, dedup, put object + sidecar, browse/select.

Typed, dependency-injected S3 client + Observer so it is unit-testable offline (inject a fake
client) and degrades gracefully when boto3/creds are absent (mirrors dam.py's _s3_enabled pattern).
"""
from __future__ import annotations

import hashlib
import io
import json
import mimetypes
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

try:
    import boto3  # type: ignore

    HAS_BOTO3 = True
except ImportError:  # boto3 optional — degraded no-s3 mode still classifies + hashes
    boto3 = None  # type: ignore
    HAS_BOTO3 = False

try:
    from pydantic import BaseModel  # type: ignore

    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

from .naming import slugify
from .observability import Observer, get_observer


class AssetKind(str, Enum):
    """Library asset kinds — the single classifier target set."""

    RASTER = "raster"
    VECTOR = "vector"
    DOC = "doc"
    COPY = "copy"


_EXT_TO_KIND: dict[str, AssetKind] = {
    ".png": AssetKind.RASTER,
    ".jpg": AssetKind.RASTER,
    ".jpeg": AssetKind.RASTER,
    ".webp": AssetKind.RASTER,
    ".svg": AssetKind.VECTOR,
    ".pdf": AssetKind.DOC,
    ".txt": AssetKind.COPY,
    ".md": AssetKind.COPY,
}

_EXT_TO_CONTENT_TYPE: dict[str, str] = {
    ".svg": "image/svg+xml",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}


class UnsupportedAssetKind(ValueError):
    """Raised when a filename extension maps to no known AssetKind."""


class AssetNotSelectable(ValueError):
    """Raised when an asset cannot be used to build/riff a campaign."""


def classify(filename: str) -> AssetKind:
    """Map a filename extension to its AssetKind — the single classifier source."""
    suffix = Path(filename).suffix.lower()
    kind = _EXT_TO_KIND.get(suffix)
    if kind is None:
        raise UnsupportedAssetKind(f"unsupported extension {suffix!r} for {filename!r}")
    return kind


def content_type_for(filename: str) -> str:
    """Best-effort MIME type with sensible fallbacks for svg/pdf/md."""
    suffix = Path(filename).suffix.lower()
    if suffix in _EXT_TO_CONTENT_TYPE:
        return _EXT_TO_CONTENT_TYPE[suffix]
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


if HAS_PYDANTIC:

    class AssetRef(BaseModel):  # type: ignore
        """Stable seam contract browse/select returns and the pipeline consumes."""

        asset_id: str
        kind: AssetKind | str
        filename: str
        s3_uri: str
        s3_key: str
        content_type: str
        size_bytes: int
        sha256: str
        added_at: str
        added_by: str = "anonymous"
        tags: list[str] = []
        width: int | None = None
        height: int | None = None
        source: str = "user-upload"

        def to_dict(self) -> dict[str, Any]:
            data = self.model_dump()
            if isinstance(data.get("kind"), AssetKind):
                data["kind"] = data["kind"].value
            return data

else:

    @dataclass(frozen=True)
    class AssetRef:  # type: ignore
        """Frozen-dataclass fallback when pydantic is absent — same field set."""

        asset_id: str
        kind: AssetKind | str
        filename: str
        s3_uri: str
        s3_key: str
        content_type: str
        size_bytes: int
        sha256: str
        added_at: str
        added_by: str = "anonymous"
        tags: list[str] = field(default_factory=list)
        width: int | None = None
        height: int | None = None
        source: str = "user-upload"

        def to_dict(self) -> dict[str, Any]:
            kind = self.kind.value if isinstance(self.kind, AssetKind) else self.kind
            return {
                "asset_id": self.asset_id,
                "kind": kind,
                "filename": self.filename,
                "s3_uri": self.s3_uri,
                "s3_key": self.s3_key,
                "content_type": self.content_type,
                "size_bytes": self.size_bytes,
                "sha256": self.sha256,
                "added_at": self.added_at,
                "added_by": self.added_by,
                "tags": list(self.tags),
                "width": self.width,
                "height": self.height,
                "source": self.source,
            }


@dataclass
class AssetPage:
    """A page of browse results plus an opaque cursor for the next page."""

    items: list[AssetRef]
    next_cursor: str | None


def _selectable_kinds() -> set[AssetKind]:
    return {AssetKind.RASTER, AssetKind.VECTOR}


class AssetLibrary:
    """Storage + metadata service for user-contributed source assets under the DAM library prefix."""

    def __init__(
        self,
        bucket: str,
        prefix: str = "brands/kodiak/library/",
        s3_client: Any = None,
        obs: Observer | None = None,
    ) -> None:
        self.bucket = bucket
        self.prefix = prefix if prefix.endswith("/") else prefix + "/"
        self.obs = obs or get_observer()
        self._s3 = s3_client if s3_client is not None else self._build_s3_client()

    # ------------------------------------------------------------------ s3 wiring
    def _build_s3_client(self) -> Any:
        """Lazily build a boto3 S3 client (us-east-1), guarded like dam.py; None if absent."""
        if not HAS_BOTO3:
            return None
        region = os.getenv(
            "DAM_S3_REGION", os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
        )
        try:
            return boto3.client("s3", region_name=region)
        except Exception:
            return None

    @property
    def s3_enabled(self) -> bool:
        return self._s3 is not None

    def _require_s3(self) -> Any:
        if self._s3 is None:
            raise RuntimeError("AssetLibrary is in no-s3 mode: boto3/creds unavailable, writes disabled")
        return self._s3

    # ------------------------------------------------------------------ add
    def add_asset(
        self,
        *,
        data: bytes,
        filename: str,
        added_by: str = "anonymous",
        tags: list[str] | None = None,
        source: str = "user-upload",
    ) -> AssetRef:
        """Classify -> hash -> dedup -> put object + sidecar -> emit log + trace. Idempotent on sha256."""
        try:
            kind = classify(filename)
        except UnsupportedAssetKind:
            self.obs.log_event("asset.reject", level="warn", filename=filename, reason="unsupported_kind")
            raise

        sha256 = hashlib.sha256(data).hexdigest()
        existing = self._find_by_sha256(sha256)
        if existing is not None:
            self.obs.log_event(
                "asset.dedup_hit", asset_id=existing.asset_id, sha256=sha256, filename=filename
            )
            return existing

        client = self._require_s3()
        asset_id = uuid.uuid4().hex  # uuid4 hex: no ulid dep pulled in; time-sort deferred to DynamoDB
        norm_tags = [slugify(t) for t in (tags or []) if slugify(t)]
        ctype = content_type_for(filename)
        object_key = f"{self.prefix}{asset_id}/{filename}"
        sidecar_key = f"{self.prefix}{asset_id}/asset.json"

        width, height = self._raster_dims(data) if kind == AssetKind.RASTER else (None, None)

        added_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        ref = AssetRef(
            asset_id=asset_id,
            kind=kind,
            filename=filename,
            s3_uri=f"s3://{self.bucket}/{object_key}",
            s3_key=object_key,
            content_type=ctype,
            size_bytes=len(data),
            sha256=sha256,
            added_at=added_at,
            added_by=added_by,
            tags=norm_tags,
            width=width,
            height=height,
            source=source,
        )

        with self.obs.trace("asset.add", kind=kind.value, asset_id=asset_id, source=source):
            with self.obs.trace("s3.put_object"):
                client.put_object(Bucket=self.bucket, Key=object_key, Body=data, ContentType=ctype)
            sidecar = json.dumps(ref.to_dict()).encode("utf-8")
            client.put_object(
                Bucket=self.bucket, Key=sidecar_key, Body=sidecar, ContentType="application/json"
            )

        self.obs.log_event(
            "asset.add",
            asset_id=asset_id,
            kind=kind.value,
            filename=filename,
            size_bytes=len(data),
            sha256=sha256,
            source=source,
        )
        return ref

    def add_asset_from_path(self, path: str | Path, **kw: Any) -> AssetRef:
        """Read bytes from a local path, infer filename, delegate to add_asset."""
        p = Path(path)
        return self.add_asset(data=p.read_bytes(), filename=p.name, **kw)

    def _raster_dims(self, data: bytes) -> tuple[int | None, int | None]:
        """Read raster width/height via pillow when available; graceful degrade to (None, None)."""
        try:
            from PIL import Image  # type: ignore
        except ImportError:
            return (None, None)
        try:
            with Image.open(io.BytesIO(data)) as img:
                return (int(img.width), int(img.height))
        except Exception:
            return (None, None)

    # ------------------------------------------------------------------ browse / select
    def list_assets(
        self,
        *,
        kind: AssetKind | None = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> AssetPage:
        """Paginated browse over asset_id dirs; reads each asset.json sidecar. Degrades to empty."""
        if self._s3 is None:
            self.obs.log_event("asset.list", count=0, s3_enabled=False)
            return AssetPage(items=[], next_cursor=None)

        params: dict[str, Any] = {
            "Bucket": self.bucket,
            "Prefix": self.prefix,
            "Delimiter": "/",
            "MaxKeys": limit,
        }
        if cursor:
            params["ContinuationToken"] = cursor
        resp = self._s3.list_objects_v2(**params)

        items: list[AssetRef] = []
        for cp in resp.get("CommonPrefixes", []):
            asset_id = cp["Prefix"][len(self.prefix):].strip("/")
            if not asset_id:
                continue
            ref = self.get_asset(asset_id)
            if ref is None:
                continue
            if kind is not None and self._ref_kind(ref) != kind:
                continue
            items.append(ref)

        next_cursor = resp.get("NextContinuationToken") if resp.get("IsTruncated") else None
        self.obs.log_event("asset.list", count=len(items), s3_enabled=True)
        return AssetPage(items=items, next_cursor=next_cursor)

    def get_asset(self, asset_id: str) -> AssetRef | None:
        """Read one AssetRef from its sidecar; None if absent or on client error."""
        if self._s3 is None:
            return None
        sidecar_key = f"{self.prefix}{asset_id}/asset.json"
        try:
            resp = self._s3.get_object(Bucket=self.bucket, Key=sidecar_key)
        except Exception:
            return None
        body = resp["Body"].read()
        payload = json.loads(body)
        return _ref_from_dict(payload)

    def select_for_campaign(self, asset_id: str) -> AssetRef:
        """Resolve + validate an asset is campaign-usable (raster/vector); else AssetNotSelectable."""
        ref = self.get_asset(asset_id)
        if ref is None:
            raise AssetNotSelectable(f"asset {asset_id!r} not found")
        kind = self._ref_kind(ref)
        if kind not in _selectable_kinds():
            raise AssetNotSelectable(f"{kind.value if kind else ref.kind} is reference-only")
        self.obs.log_event("asset.select", asset_id=asset_id, kind=kind.value)
        return ref

    def _find_by_sha256(self, sha256: str) -> AssetRef | None:
        """Dedup scan over sidecars — O(list) for v1; DynamoDB index is the future optimization."""
        if self._s3 is None:
            return None
        try:
            resp = self._s3.list_objects_v2(Bucket=self.bucket, Prefix=self.prefix, Delimiter="/")
        except Exception:
            return None
        for cp in resp.get("CommonPrefixes", []):
            asset_id = cp["Prefix"][len(self.prefix):].strip("/")
            if not asset_id:
                continue
            ref = self.get_asset(asset_id)
            if ref is not None and ref.sha256 == sha256:
                return ref
        return None

    def _ref_kind(self, ref: AssetRef) -> AssetKind | None:
        """Coerce an AssetRef.kind (enum or str) back to AssetKind, None if unrecognized."""
        if isinstance(ref.kind, AssetKind):
            return ref.kind
        try:
            return AssetKind(ref.kind)
        except ValueError:
            return None

    def health(self) -> dict[str, Any]:
        """Liveness + a cheap count of library assets."""
        count = len(self.list_assets(limit=1000).items) if self._s3 is not None else 0
        return {
            "ok": True,
            "bucket": self.bucket,
            "prefix": self.prefix,
            "count": count,
            "s3_enabled": self.s3_enabled,
        }


def _ref_from_dict(payload: dict[str, Any]) -> AssetRef:
    """Rebuild an AssetRef from a parsed sidecar under either pydantic or dataclass mode."""
    if HAS_PYDANTIC:
        return AssetRef(**payload)  # type: ignore[arg-type]
    return AssetRef(  # type: ignore[call-arg]
        asset_id=payload["asset_id"],
        kind=payload["kind"],
        filename=payload["filename"],
        s3_uri=payload["s3_uri"],
        s3_key=payload["s3_key"],
        content_type=payload["content_type"],
        size_bytes=payload["size_bytes"],
        sha256=payload["sha256"],
        added_at=payload["added_at"],
        added_by=payload.get("added_by", "anonymous"),
        tags=list(payload.get("tags", [])),
        width=payload.get("width"),
        height=payload.get("height"),
        source=payload.get("source", "user-upload"),
    )
