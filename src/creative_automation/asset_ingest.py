"""Asset ingest — thin embed-on-ingest wrapper over AssetLibrary.add_asset.

add_asset already does classify -> sha256 -> exact dedup -> S3 put + sidecar -> observability
and is idempotent on sha256. This module adds ONE additive step for the api path: after a
RASTER/VECTOR asset is committed, compute an embedding and write it to the S3 Vectors index
so kodiak-vectors is populated. add_asset's signature is untouched — current callers/tests are
unaffected; only the api routes opt into embed-on-ingest through ingest_asset.

Ordering matters: the S3 object + sidecar are the source of truth and are already committed by
add_asset before we ever touch embeddings. Every embed failure (vector_exists probe, embed_image,
put_vector returning False, or any raised exception) degrades to embed_status="embed_pending" and
NEVER loses the asset or fails the ingest. A background re-embed sweep can later find pending keys
via the same vector_exists gate.

embeddings is referenced by attribute (embeddings.embed_image / .vector_exists / .put_vector) so
tests can monkeypatch the module for an offline, no-Bedrock, no-S3-Vectors run.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

from . import embeddings
from .asset_library import AssetKind, AssetLibrary, AssetRef

# kinds worth a vector: raster art and vector marks are retrievable; docs/copy are not embedded here
_EMBEDDABLE_KINDS = {AssetKind.RASTER, AssetKind.VECTOR}

# embed_status values the route surfaces so a caller/frontend can tell what happened
EMBED_EMBEDDED = "embedded"
EMBED_SKIPPED_DEDUP = "skipped_dedup"
EMBED_PENDING = "embed_pending"
EMBED_NOT_EMBEDDABLE = "not_embeddable"
EMBED_DISABLED = "disabled"


def _ref_kind(ref: AssetRef) -> AssetKind | None:
    """Coerce AssetRef.kind (enum or str from a rebuilt sidecar) to AssetKind, None if unknown."""
    if isinstance(ref.kind, AssetKind):
        return ref.kind
    try:
        return AssetKind(ref.kind)
    except ValueError:
        return None


def embed_and_store(
    *,
    data: bytes,
    ref: AssetRef,
    obs: Any = None,
) -> str:
    """Embed one already-committed asset and write it to S3 Vectors. Returns an embed_status.

    Never raises. vector_exists(asset_id) is the dedup-skip gate; a True short-circuits to
    skipped_dedup so a known key is not re-embedded. On any failure the status is embed_pending
    and the asset (already persisted by add_asset) is untouched.
    """
    kind = _ref_kind(ref)
    if kind not in _EMBEDDABLE_KINDS:
        return EMBED_NOT_EMBEDDABLE

    key = ref.asset_id
    # dedup-skip gate — vector_exists never raises, returns False when offline/unconfigured
    try:
        if embeddings.vector_exists(key):
            if obs is not None:
                obs.log_event("asset.embed_skip", asset_id=key, reason="vector_exists")
            return EMBED_SKIPPED_DEDUP
    except Exception:  # noqa: BLE001 — defensive: probe must never break ingest
        print(f"[asset-ingest] dedup probe failed, embedding anyway: {key}")

    tmp_path: str | None = None
    try:
        # embed_image needs a real path (reads bytes off disk); write the committed bytes to a
        # temp file preserving the extension so the format map keys correctly (png/jpeg/webp/svg)
        suffix = Path(ref.filename).suffix or ""
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)

        vector, model = embeddings.embed_image(tmp_path, text_hint=ref.filename)
        metadata = {
            "asset_id": ref.asset_id,
            "filename": ref.filename,
            "kind": kind.value,
            "sha256": ref.sha256,
            "source": ref.source,
            "model": model,
        }
        ok = embeddings.put_vector(vector, key=key, metadata=metadata)
        if not ok:
            if obs is not None:
                obs.log_event("asset.embed_pending", level="warn", asset_id=key, reason="put_vector_false")
            return EMBED_PENDING
        if obs is not None:
            obs.log_event("asset.embed", asset_id=key, kind=kind.value, model=model)
        return EMBED_EMBEDDED
    except Exception as exc:  # noqa: BLE001 — embed failure must never lose the asset
        if obs is not None:
            obs.log_event("asset.embed_pending", level="warn", asset_id=key, reason=str(exc))
        return EMBED_PENDING
    finally:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def ingest_asset(
    library: AssetLibrary,
    *,
    data: bytes,
    filename: str,
    added_by: str = "anonymous",
    tags: list[str] | None = None,
    source: str = "user-upload",
    embed: bool = True,
) -> tuple[AssetRef, str]:
    """Add an asset then (opt-in) embed-on-ingest. Returns (AssetRef, embed_status).

    add_asset stays authoritative for classify/dedup/persist and is idempotent on sha256, so an
    exact-duplicate upload returns the existing ref. When that duplicate already carries a vector,
    the vector_exists gate inside embed_and_store returns skipped_dedup — no second embed. Embed is
    additive and best-effort: a failure yields embed_pending, never an exception, and the persisted
    asset is unaffected.
    """
    ref = library.add_asset(
        data=data,
        filename=filename,
        added_by=added_by,
        tags=tags,
        source=source,
    )
    if not embed:
        return ref, EMBED_DISABLED
    status = embed_and_store(data=data, ref=ref, obs=library.obs)
    return ref, status
