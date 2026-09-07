"""Asset library API + MCP surface — browse/select/add for the DAM library prefix.

Mirrors reference_api.py: HAS_FASTAPI graceful degrade, module-level `app`, __main__ uvicorn runner.
Upload uses a raw request body + filename query param (no python-multipart dependency); a multipart
variant is a follow-up if python-multipart is added.

Run locally:
  uv run python -m creative_automation.asset_api  # FastAPI at http://127.0.0.1:8183
  curl "http://127.0.0.1:8183/library/health"
"""
from __future__ import annotations

import os
from typing import Any

try:
    from fastapi import Body, FastAPI, HTTPException, Query  # type: ignore
    from fastapi.responses import JSONResponse  # type: ignore

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from .asset_library import (
    AssetKind,
    AssetLibrary,
    AssetNotSelectable,
    UnsupportedAssetKind,
)
from .asset_ingest import ingest_asset
from .observability import get_observer

DAM_S3_BUCKET = os.getenv("DAM_S3_BUCKET", "chasko-creative-dam-946179428633-us-east-1")
LIBRARY_PREFIX = "brands/kodiak/library/"

library = AssetLibrary(bucket=DAM_S3_BUCKET, prefix=LIBRARY_PREFIX)
obs = get_observer()


def mount_library_routes(app: Any, lib: AssetLibrary, *, obs: Any = None) -> None:
    """Register the /library/* routes on `app`, bound to `lib`.

    The ONE registration both the standalone asset_api app and the main api.py app call, so the
    frontend hitting the main-API origin reaches the same routes/logic as the standalone :8183
    surface with no drift. add_asset logic is never duplicated — the POST path calls ingest_asset,
    which itself calls lib.add_asset then embeds on ingest. No-op when FastAPI is unavailable.
    """
    if not HAS_FASTAPI or app is None:
        return
    _obs = obs or get_observer()

    @app.post("/library/assets", status_code=201)  # type: ignore
    def add_asset_api(
        filename: str = Query(..., description="Original filename incl. extension"),
        added_by: str = Query("anonymous"),
        tags: str | None = Query(None, description="Comma-separated tags"),
        body: bytes = Body(..., media_type="application/octet-stream"),
    ):
        tag_list = [t.strip() for t in tags.split(",")] if tags else None
        try:
            # embed-on-ingest: add_asset persists (S3 object + sidecar), then a RASTER/VECTOR is
            # embedded into S3 Vectors. embed is best-effort — embed_status carries the outcome and
            # a failure degrades to embed_pending without failing the ingest.
            ref, embed_status = ingest_asset(
                lib, data=body, filename=filename, added_by=added_by, tags=tag_list
            )
        except UnsupportedAssetKind as exc:
            raise HTTPException(status_code=415, detail=str(exc))
        payload = ref.to_dict()
        payload["embed_status"] = embed_status
        return payload

    @app.get("/library/assets")  # type: ignore
    def list_assets_api(
        kind: str | None = Query(None),
        limit: int = Query(100),
        cursor: str | None = Query(None),
    ):
        kind_enum = AssetKind(kind) if kind else None
        page = lib.list_assets(kind=kind_enum, limit=limit, cursor=cursor)
        return {"items": [ref.to_dict() for ref in page.items], "next_cursor": page.next_cursor}

    @app.get("/library/assets/{asset_id}")  # type: ignore
    def get_asset_api(asset_id: str):
        ref = lib.get_asset(asset_id)
        if ref is None:
            raise HTTPException(status_code=404, detail=f"asset {asset_id} not found")
        return ref.to_dict()

    @app.post("/library/assets/{asset_id}/select")  # type: ignore
    def select_asset_api(asset_id: str):
        try:
            ref = lib.select_for_campaign(asset_id)
        except AssetNotSelectable as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        return ref.to_dict()

    @app.get("/library/health")  # type: ignore
    def health_api():
        return lib.health()

    @app.get("/library/report")  # type: ignore
    def report_api():
        return JSONResponse(
            {
                "service": _obs.service,
                "recent": [r.as_dict() for r in _obs.recent()],
                "counts": _obs.counts(),
            }
        )


app = FastAPI(title="Kodiak Asset Library", version="1.0.0") if HAS_FASTAPI else None  # type: ignore

if HAS_FASTAPI:
    mount_library_routes(app, library, obs=obs)


if __name__ == "__main__":
    import uvicorn  # type: ignore

    print("Kodiak Asset Library at http://127.0.0.1:8183 — docs at /docs (FastAPI)")
    print("Try: curl 'http://127.0.0.1:8183/library/health'")
    print(
        "Add:  curl -X POST --data-binary @logo.png "
        "'http://127.0.0.1:8183/library/assets?filename=logo.png&tags=brand,mark'"
    )
    uvicorn.run(app, host="127.0.0.1", port=8183)
