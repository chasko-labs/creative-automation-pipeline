"""Staged-asset store seed_key wiring: frontend request -> handler -> seed order.

Covers the handler layer (generate_lambda preview + full), which had no
seed_key coverage: the request's ``seed_key`` must reach generate_hero /
generate_hero_set verbatim, staged-asset provenance must surface, and a
dead staged pick must fall through silently (200, never 503).
"""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import generate_lambda


class _FakeS3:
    """Stub s3 client capturing put_object and returning a canned presigned url."""

    def put_object(self, **kwargs) -> dict:
        return {}

    def generate_presigned_url(self, op, Params, ExpiresIn) -> str:
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def _fake_single_render(out_path: Path) -> None:
    from PIL import Image

    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), (200, 120, 40)).save(out_path, "PNG")


def _capture_hero(captured: dict, provenance: dict):
    def _stub(**kwargs):
        captured.update(kwargs)
        out_path = Path(kwargs["out_path"])
        _fake_single_render(out_path)
        return out_path, "bedrock:stability-control-structure", dict(provenance)

    return _stub


def test_preview_forwards_seed_key_to_generate_hero(monkeypatch) -> None:
    captured: dict = {}
    prov = {"seed_source": "past-hero", "seed_selection": "staged-asset", "engine": "x"}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured, prov))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {"body": json.dumps({"prompt": "wild mornings", "seed_key": "brands/kodiak/renders/past-hero.png"})}
    resp = generate_lambda.handler(event, None)

    assert resp["statusCode"] == 200
    assert resp["statusCode"] != 503
    assert captured["seed_key"] == "brands/kodiak/renders/past-hero.png"
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["provenance"]["seed_selection"] == "staged-asset"


def test_preview_without_seed_key_sends_none(monkeypatch) -> None:
    captured: dict = {}
    prov = {"seed_source": "power-cakes-hero", "seed_selection": "disk-asset", "engine": "x"}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured, prov))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    resp = generate_lambda.handler({"body": json.dumps({"prompt": "wild mornings"})}, None)

    assert resp["statusCode"] == 200
    assert captured["seed_key"] is None


def test_full_forwards_seed_key_to_generate_hero_set(monkeypatch, tmp_path: Path) -> None:
    captured: dict = {}

    def _spy(**kwargs):
        from PIL import Image

        captured.update(kwargs)
        out_dir = Path(kwargs.get("out_dir") or (tmp_path / "renders"))
        out_dir.mkdir(parents=True, exist_ok=True)
        renders = []
        for ratio, (w, h) in {"1x1": (1080, 1080), "4x5": (1080, 1350)}.items():
            p = out_dir / f"hero-{ratio}.png"
            Image.new("RGB", (16, 16), (200, 120, 40)).save(p, "PNG")
            renders.append({"ratio": ratio, "path": p, "w": w, "h": h})
        prov = {"seed_source": "past-hero", "seed_selection": "staged-asset", "engine": "x"}
        return renders, "bedrock:nova-pro", prov

    monkeypatch.setattr(generate_lambda, "generate_hero_set", _spy)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {
        "body": json.dumps(
            {"mode": "full", "prompt": "wild mornings", "seed_key": "brands/kodiak/renders/past-hero.png"}
        )
    }
    resp = generate_lambda.handler(event, None)

    assert resp["statusCode"] == 200
    assert resp["statusCode"] != 503
    assert captured["seed_key"] == "brands/kodiak/renders/past-hero.png"


def test_staged_fetch_none_falls_through_silently(monkeypatch, tmp_path: Path) -> None:
    # fetch_asset_key returning None (offline / missing object) must fall through
    # to disk resolution — real pixels, no raise, never a 503-shaped failure.
    from PIL import Image

    from creative_automation import asset_store
    from creative_automation import generate as generate_mod

    disk = tmp_path / "disk-seed.png"
    Image.new("RGB", (1024, 1024), (20, 120, 60)).save(disk, "PNG")

    monkeypatch.setattr(asset_store, "fetch_asset_key", lambda key, dest: None)
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: disk)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "hero.png"
    result, _source, prov = generate_mod.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        seed_key="brands/kodiak/renders/gone.png",
    )

    assert result.exists()
    assert prov["seed_selection"] == "disk-asset"
    assert "riff_on" not in prov
