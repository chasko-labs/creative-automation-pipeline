"""/library/* routes mounted on the MAIN api.py app — the frontend origin reaches them.

The frontend POSTs to the main-API origin (port 8182), not the standalone asset_api (8183). These
tests prove mount_library_routes wired the same routes onto the main app and that a POST returns 201
with the AssetRef dict plus an embed_status. All offline: a FakeS3 is injected into the shared
AssetLibrary instance so add_asset commits in-memory, and the embeddings module is stubbed so no
Bedrock / S3 Vectors is touched. TestClient cases skip cleanly under bare python (no fastapi).
"""
from __future__ import annotations

import io

import pytest

try:
    from creative_automation.api import HAS_FASTAPI, app
    from creative_automation import asset_api, asset_ingest as ingest

    IMPORT_OK = True
except Exception:  # pragma: no cover - import guard
    HAS_FASTAPI = False
    app = None
    IMPORT_OK = False

_SKIP_REASON = "needs fastapi (bare-python run skips by design)"


class FakeS3:
    """In-memory S3 stub mirroring test_asset_library.py's FakeS3."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str = "") -> dict:
        self.store[Key] = Body if isinstance(Body, bytes) else bytes(Body)
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        if Key not in self.store:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.store[Key])}

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str = "",
        Delimiter: str | None = None,
        MaxKeys: int = 1000,
        ContinuationToken: str | None = None,
    ) -> dict:
        keys = sorted(k for k in self.store if k.startswith(Prefix))
        if Delimiter:
            prefixes: list[str] = []
            seen: set[str] = set()
            for k in keys:
                rest = k[len(Prefix):]
                head = rest.split(Delimiter, 1)[0]
                cp = f"{Prefix}{head}{Delimiter}"
                if cp not in seen:
                    seen.add(cp)
                    prefixes.append(cp)
            return {"CommonPrefixes": [{"Prefix": p} for p in prefixes], "IsTruncated": False}
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}


def test_library_routes_mounted_on_main_app():
    """Bare-python-safe: when FastAPI is present the /library routes exist on the MAIN app."""
    if not (IMPORT_OK and HAS_FASTAPI):
        pytest.skip(_SKIP_REASON)
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/library/assets" in paths
    assert "/library/assets/{asset_id}" in paths
    assert "/library/assets/{asset_id}/select" in paths
    assert "/library/health" in paths


def _stub_embed_offline(monkeypatch):
    """No-op embeddings: vector absent, put succeeds — deterministic, no AWS."""
    monkeypatch.setattr(ingest.embeddings, "vector_exists", lambda key, **kw: False)
    monkeypatch.setattr(
        ingest.embeddings, "embed_image", lambda p, text_hint=None, dim=1024: ([0.1, 0.2], "mock")
    )
    monkeypatch.setattr(ingest.embeddings, "put_vector", lambda vec, key, metadata=None, **kw: True)


def test_mounted_post_returns_201_and_asset_ref(monkeypatch):
    if not (IMPORT_OK and HAS_FASTAPI):
        pytest.skip(_SKIP_REASON)
    from fastapi.testclient import TestClient

    # inject FakeS3 into the shared library instance the main app mounted, so add_asset commits
    fake = FakeS3()
    monkeypatch.setattr(asset_api.library, "_s3", fake)
    _stub_embed_offline(monkeypatch)

    client = TestClient(app)
    resp = client.post(
        "/library/assets",
        params={"filename": "hero.png", "tags": "brand,mark"},
        content=b"png-bytes",
        headers={"content-type": "application/octet-stream"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # AssetRef dict shape
    assert body["kind"] == "raster"
    assert body["filename"] == "hero.png"
    assert body["sha256"]
    assert body["s3_key"].endswith("/hero.png")
    assert body["tags"] == ["brand", "mark"]
    # embed-on-ingest indicator travels back
    assert body["embed_status"] == ingest.EMBED_EMBEDDED
    # the object + sidecar landed in the injected FakeS3
    assert body["s3_key"] in fake.store


def test_mounted_post_embed_pending_still_201(monkeypatch):
    """put_vector failing degrades to embed_pending but the asset still persists at 201."""
    if not (IMPORT_OK and HAS_FASTAPI):
        pytest.skip(_SKIP_REASON)
    from fastapi.testclient import TestClient

    fake = FakeS3()
    monkeypatch.setattr(asset_api.library, "_s3", fake)
    monkeypatch.setattr(ingest.embeddings, "vector_exists", lambda key, **kw: False)
    monkeypatch.setattr(
        ingest.embeddings, "embed_image", lambda p, text_hint=None, dim=1024: ([0.1], "mock")
    )
    monkeypatch.setattr(ingest.embeddings, "put_vector", lambda vec, key, metadata=None, **kw: False)

    client = TestClient(app)
    resp = client.post(
        "/library/assets",
        params={"filename": "hero.png"},
        content=b"png-bytes-2",
        headers={"content-type": "application/octet-stream"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["embed_status"] == ingest.EMBED_PENDING
    assert body["s3_key"] in fake.store


def test_mounted_post_unsupported_kind_415(monkeypatch):
    if not (IMPORT_OK and HAS_FASTAPI):
        pytest.skip(_SKIP_REASON)
    from fastapi.testclient import TestClient

    fake = FakeS3()
    monkeypatch.setattr(asset_api.library, "_s3", fake)
    _stub_embed_offline(monkeypatch)

    client = TestClient(app)
    resp = client.post(
        "/library/assets",
        params={"filename": "malware.exe"},
        content=b"x",
        headers={"content-type": "application/octet-stream"},
    )
    assert resp.status_code == 415
