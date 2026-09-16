"""POST /assets/upload — browser photo INTO the pipeline (issue #38), OFFLINE + cred-free.

This is the unblocker for #39: /pipeline/run and /suggest/run take a filesystem PATH,
so a browser-local photo could never enter. This endpoint accepts the bytes, writes
input_assets/{product}/hero.{ext}, registers the copy in the DAM, and hands back an
asset id + presigned url (null offline).

Every assertion runs with no S3 and no boto3 creds: dam.s3_upload_and_presign returns
None when DAM_S3_BUCKET is unset, so the endpoint takes its local-write fallback. The
FastAPI TestClient cases skip under bare python (no fastapi / no python-multipart),
matching how test_asset_pack.py exercises the no-FastAPI graceful path. Uploads are
redirected to tmp_path via the CAP_INPUT_ASSETS_ROOT env override so the real
input_assets/ dir is never touched.
"""
import io

import pytest

try:
    from creative_automation.api import HAS_FASTAPI, app
except ImportError:  # pragma: no cover - import guard
    HAS_FASTAPI = False
    app = None

# python-multipart is required for Form/File parsing; without it the TestClient cases
# cannot run even when fastapi imports. Treat its absence the same as no-FastAPI.
try:
    import multipart  # noqa: F401  (python-multipart)

    HAS_MULTIPART = True
except ImportError:  # pragma: no cover - import guard
    HAS_MULTIPART = False

try:
    from PIL import Image

    HAS_PIL = True
except ImportError:  # pragma: no cover - import guard
    HAS_PIL = False

_CAN_RUN = HAS_FASTAPI and HAS_MULTIPART and HAS_PIL
_SKIP_REASON = "needs fastapi + python-multipart + pillow (bare-python run skips by design)"


def _png_bytes(size: int = 8) -> bytes:
    """A tiny real PNG built in memory — no fixture file on disk."""
    buf = io.BytesIO()
    Image.new("RGB", (size, size), (59, 35, 22)).save(buf, format="PNG")  # Bear Brown #3B2316
    return buf.getvalue()


def _client(monkeypatch, tmp_path):
    """A TestClient with S3 disabled and input_assets redirected under tmp_path."""
    from fastapi.testclient import TestClient

    monkeypatch.delenv("DAM_S3_BUCKET", raising=False)
    monkeypatch.delenv("DAM_S3_URI", raising=False)
    monkeypatch.setenv("CAP_INPUT_ASSETS_ROOT", str(tmp_path / "input_assets"))
    return TestClient(app)


@pytest.mark.skipif(not _CAN_RUN, reason=_SKIP_REASON)
def test_upload_png_returns_200_and_writes_hero(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    resp = client.post(
        "/assets/upload",
        files={"file": ("frontier.png", _png_bytes(), "image/png")},
        data={"product": "Power Cakes", "market": "US-SW-LASCRUCES"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["asset_id"].startswith("power-cakes-")
    assert body["product"] == "power-cakes"
    assert body["market"] == "US-SW-LASCRUCES"
    assert body["content_type"] == "image/png"
    assert body["bytes"] > 0
    # the hero file is really on disk under the redirected root
    hero = tmp_path / "input_assets" / "power-cakes" / "hero.png"
    assert hero.exists()
    assert hero.read_bytes() == _png_bytes()


@pytest.mark.skipif(not _CAN_RUN, reason=_SKIP_REASON)
def test_upload_jpeg_maps_to_jpg_extension(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (232, 83, 14)).save(buf, format="JPEG")  # Blaze Orange
    resp = client.post(
        "/assets/upload",
        files={"file": ("frontier.jpeg", buf.getvalue(), "image/jpeg")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # image/jpeg -> hero.jpg (not .jpeg)
    assert body["hero_path"].endswith("hero.jpg")
    assert (tmp_path / "input_assets" / "power-cakes" / "hero.jpg").exists()


@pytest.mark.skipif(not _CAN_RUN, reason=_SKIP_REASON)
def test_non_image_content_type_rejected_400(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    resp = client.post(
        "/assets/upload",
        files={"file": ("notes.txt", b"not an image", "text/plain")},
    )
    assert resp.status_code == 400
    assert "unsupported content type" in resp.json()["detail"]


@pytest.mark.skipif(not _CAN_RUN, reason=_SKIP_REASON)
def test_oversize_upload_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    # 15 MB + 1 byte of PNG-typed payload — over the cap, rejected before any disk write
    oversize = b"\x89PNG\r\n\x1a\n" + b"\x00" * (15 * 1024 * 1024 + 1)
    resp = client.post(
        "/assets/upload",
        files={"file": ("huge.png", oversize, "image/png")},
    )
    assert resp.status_code == 413
    assert "cap" in resp.json()["detail"]
    # nothing was written for the rejected upload
    assert not (tmp_path / "input_assets" / "power-cakes").exists()


@pytest.mark.skipif(not _CAN_RUN, reason=_SKIP_REASON)
def test_empty_file_rejected_400(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    resp = client.post(
        "/assets/upload",
        files={"file": ("empty.png", b"", "image/png")},
    )
    assert resp.status_code == 400
    assert "empty file" in resp.json()["detail"]


@pytest.mark.skipif(not _CAN_RUN, reason=_SKIP_REASON)
def test_offline_branch_presigned_url_is_null_file_still_written(monkeypatch, tmp_path):
    # S3 disabled (bucket env deleted in _client) -> presigned_url null, local file present
    client = _client(monkeypatch, tmp_path)
    resp = client.post(
        "/assets/upload",
        files={"file": ("frontier.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["presigned_url"] is None
    assert body["note"] and "DAM_S3_BUCKET" in body["note"]
    assert (tmp_path / "input_assets" / "power-cakes" / "hero.png").exists()


@pytest.mark.skipif(not _CAN_RUN, reason=_SKIP_REASON)
def test_reupload_keeps_id_suffixed_copy_no_data_loss(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    first = client.post(
        "/assets/upload",
        files={"file": ("one.png", _png_bytes(8), "image/png")},
    ).json()
    second = client.post(
        "/assets/upload",
        files={"file": ("two.png", _png_bytes(16), "image/png")},
    ).json()

    product_dir = tmp_path / "input_assets" / "power-cakes"
    # canonical hero reflects the latest upload
    assert (product_dir / "hero.png").read_bytes() == _png_bytes(16)
    # both id-suffixed archive copies survive — earlier upload is recoverable
    assert first["asset_id"] != second["asset_id"]
    archives = sorted(product_dir.glob("hero-*.png"))
    assert len(archives) == 2
    kept = {p.read_bytes() for p in archives}
    assert _png_bytes(8) in kept
    assert _png_bytes(16) in kept


def test_upload_route_registered_when_fastapi_present():
    """Bare-python-safe: when FastAPI is present the route exists; otherwise skip cleanly."""
    if not HAS_FASTAPI:
        pytest.skip("FastAPI not installed — endpoint tests skip by design")
    paths = {getattr(r, "path", "") for r in app.routes}
    assert "/assets/upload" in paths
