"""Scenic backgrounds: text-to-image hero seeds for ideas no pool photo can show.

All offline: the Bedrock client and the asset store are stubbed. Covers the
scene-text builder, the Core invoke wrapper (success / blocked / no-creds),
the store key helpers, and the lambda mode handler's seeded + no-idea paths.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from creative_automation import asset_store
from creative_automation import generate
from creative_automation import generate_lambda


def _tiny_png_b64() -> str:
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), (10, 120, 200)).save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


class _FakeBody:
    def __init__(self, payload: dict):
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload).encode()


class _FakeClient:
    def __init__(self, payload: dict):
        self._payload = payload
        self.calls: list[dict] = []

    def invoke_model(self, modelId: str, body: str) -> dict:
        self.calls.append({"modelId": modelId, "body": json.loads(body)})
        return {"body": _FakeBody(self._payload)}


def test_scenic_scene_text_leads_with_idea() -> None:
    scene = generate._scenic_scene_text(
        "sea otters — season: September", "US-MW-PARKCITY-84098", "September"
    )
    assert scene.startswith("Photorealistic advertising photograph: sea otters")
    assert "Park City" in scene


def test_scenic_scene_text_empty_without_idea() -> None:
    assert generate._scenic_scene_text("season: September") == ""
    assert generate._scenic_scene_text(None) == ""


def test_scenic_scene_text_scrubs_adversary() -> None:
    scene = generate._scenic_scene_text("Zac Efron eating pancakes")
    assert "Zac Efron" not in scene


def test_scenic_background_success(monkeypatch, tmp_path: Path) -> None:
    payload = {"finish_reasons": [None], "images": [_tiny_png_b64()]}
    monkeypatch.setattr(
        "creative_automation.spin._bedrock_client",
        lambda *a, **k: _FakeClient(payload),
    )
    out = tmp_path / "hero.png"
    got = generate._scenic_background("sea otters at dawn", out, request_seed=7)
    assert got is not None and Path(got).exists()
    with Image.open(got) as img:
        assert img.size == (8, 8)


def test_scenic_background_blocked_is_none(monkeypatch, tmp_path: Path) -> None:
    payload = {"finish_reasons": ["CONTENT_FILTERED"], "images": []}
    monkeypatch.setattr(
        "creative_automation.spin._bedrock_client",
        lambda *a, **k: _FakeClient(payload),
    )
    assert generate._scenic_background("sea otters", tmp_path / "h.png") is None


def test_scenic_background_no_creds_is_none(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "creative_automation.spin._bedrock_client", lambda *a, **k: None
    )
    assert generate._scenic_background("sea otters", tmp_path / "h.png") is None
    assert generate._scenic_background("", tmp_path / "h.png") is None


def test_scenic_store_helpers() -> None:
    assert asset_store.scenic_slug("Sea Otters!") == "sea-otters"
    assert asset_store.scenic_slug("") == "scene"
    assert asset_store.scenic_key("sea-otters").endswith("sea-otters/hero-1x1.png")
    assert asset_store.scenic_site_url("sea-otters") == "/scenic-bg/sea-otters/hero-1x1.png"


def test_handle_scenic_bg_seeded(monkeypatch) -> None:
    monkeypatch.setattr(asset_store, "scenic_exists", lambda slug: True)
    res = generate_lambda._handle_scenic_bg(
        {"prompt": "sea otters — season: September", "market": "US-MW-PARKCITY-84098"}
    )
    assert res["ok"] is True and res["seeded"] is True
    assert res["key"].endswith("sea-otters/hero-1x1.png")
    assert res["idea"] == "sea otters"


def test_handle_scenic_bg_no_idea() -> None:
    res = generate_lambda._handle_scenic_bg({"prompt": "season: September"})
    assert res["ok"] is False
