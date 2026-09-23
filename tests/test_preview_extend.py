"""Extend endpoint: one tall/wide tile from a rendered 1x1 hero. Offline."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import generate_lambda as gl


def _hero(tmp_path: Path) -> Path:
    p = tmp_path / "hero.png"
    Image.new("RGB", (1080, 1080), (200, 120, 60)).save(p, "PNG")
    return p


def test_extend_rejects_unknown_ratio() -> None:
    resp = gl._handle_extend({"ratio": "1x1", "hero_s3_uri": "x"}, "prompt")
    assert resp["ok"] is False


def test_extend_rejects_foreign_bucket() -> None:
    resp = gl._handle_extend(
        {"ratio": "9x16", "hero_s3_uri": "s3://other-bucket/key.png"}, "prompt"
    )
    assert resp["ok"] is False


def test_extend_rejects_unreadable_hero(tmp_path: Path, monkeypatch) -> None:
    class DeadS3:
        def get_object(self, **kw):
            raise RuntimeError("nope")

    monkeypatch.setattr(gl, "_s3_client", lambda: DeadS3())
    resp = gl._handle_extend(
        {"ratio": "9x16", "hero_s3_uri": f"s3://{gl.ASSET_STORE_S3_BUCKET}/missing.png"},
        "prompt",
    )
    assert resp["ok"] is False
    assert "download failed" in resp["error"]


def test_extend_rejects_garbage_bytes(tmp_path: Path, monkeypatch) -> None:
    class S3:
        def get_object(self, **kw):
            return {"Body": _Body(b"not-an-image")}

    class _Body:
        def __init__(self, b: bytes):
            self._b = b

        def read(self) -> bytes:
            return self._b

    monkeypatch.setattr(gl, "_s3_client", lambda: S3())
    resp = gl._handle_extend(
        {"ratio": "9x16", "hero_s3_uri": f"s3://{gl.ASSET_STORE_S3_BUCKET}/junk.png"},
        "prompt",
    )
    assert resp["ok"] is False


def test_extend_falls_back_to_pad(tmp_path: Path, monkeypatch) -> None:
    hero = _hero(tmp_path)

    class S3:
        def get_object(self, **kw):
            return {"Body": _Body(hero.read_bytes())}

        def put_object(self, **kw):
            return {}

        def generate_presigned_url(self, op, Params=None, ExpiresIn=None):
            return "https://example/signed.png"

    class _Body:
        def __init__(self, b: bytes):
            self._b = b

        def read(self) -> bytes:
            return self._b

    monkeypatch.setattr(gl, "_s3_client", lambda: S3())
    monkeypatch.setattr(gl, "_stability_outpaint", lambda *a: None)
    resp = gl._handle_extend(
        {"ratio": "9x16", "hero_s3_uri": f"s3://{gl.ASSET_STORE_S3_BUCKET}/hero.png"},
        "prompt",
    )
    assert resp["ok"] is True
    assert resp["ratio"] == "9x16"
    assert resp["engine"] == "pillow-outpaint-fallback"
    assert (resp["w"], resp["h"]) == (1080, 1920)


def test_extend_mode_routes_through_handler(monkeypatch) -> None:
    seen: dict = {}

    def fake_extend(data, prompt):
        seen.update(data)
        return {"ok": True, "ratio": "9x16"}

    monkeypatch.setattr(gl, "_handle_extend", fake_extend)
    event = {"body": '{"mode": "extend", "ratio": "9x16"}'}
    resp = gl.handler(event)
    assert resp["statusCode"] == 200
    assert seen["ratio"] == "9x16"
