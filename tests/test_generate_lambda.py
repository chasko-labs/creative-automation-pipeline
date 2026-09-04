"""Tests for the brief-to-hero Lambda handler — no real AWS."""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import generate_lambda


class _FakeS3:
    """Stub s3 client capturing put_object and returning a canned presigned url."""

    def __init__(self) -> None:
        self.puts: list[dict] = []
        self.presign_calls: list[dict] = []

    def put_object(self, **kwargs) -> dict:
        self.last_put = kwargs
        self.puts.append(kwargs)
        return {}

    def generate_presigned_url(self, op, Params, ExpiresIn) -> str:  # noqa: N803 — boto3 kwarg name
        self.last_presign_params = Params
        self.presign_calls.append(Params)
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def _fake_renders(out_dir: Path) -> list[dict]:
    """Build a 3-ratio renders[] list with real tiny PNGs on disk (handler reads bytes)."""
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    dims = {"1x1": (1080, 1080), "4x5": (1080, 1350), "2x3": (1000, 1500)}
    renders = []
    for ratio, (w, h) in dims.items():
        p = out_dir / f"hero-{ratio}.png"
        Image.new("RGB", (16, 16), (200, 120, 40)).save(p, "PNG")
        renders.append({"ratio": ratio, "path": p, "w": w, "h": h, "engine": "stability-outpaint"})
    return renders


def _stub_hero_set(source: str, tmp_path: Path, provenance: dict | None = None):
    """Return a generate_hero_set stub that yields 3 fake renders + source + provenance."""

    def _stub(**kwargs):
        out_dir = kwargs.get("out_dir") or (tmp_path / "renders")
        prov = provenance or {
            "seed_source": "power-cakes-hero",
            "seed_selection": "disk-asset",
            "engine": "stability-control-structure",
            "scene_prompt": "wild frontier restyle",
            "control_strength": 0.7,
            "model": "us.stability.stable-image-control-structure-v1:0",
            "incoming_prompt": kwargs.get("brief_msg", ""),
            "headline": "Keep It Wild",
            "overlay_applied": True,
            "paper_overlay": True,
            "ratios": {"1x1": "primary", "4x5": "stability-outpaint", "2x3": "stability-outpaint"},
        }
        return _fake_renders(Path(out_dir)), source, prov

    return _stub


def test_handler_returns_200_with_image_url(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        generate_lambda, "generate_hero_set", _stub_hero_set("bedrock:nova-pro", tmp_path)
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {"body": json.dumps({"prompt": "a bear eating pancakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["image_url"].startswith("https://presigned.example/")
    assert body["source"] == "bedrock:nova-pro"
    assert body["prompt"] == "a bear eating pancakes"
    # PART B — three renders delivered from one call, 1x1 first, correct dims.
    assert [r["ratio"] for r in body["renders"]] == ["1x1", "4x5", "2x3"]
    dims = {r["ratio"]: (r["w"], r["h"]) for r in body["renders"]}
    assert dims == {"1x1": (1080, 1080), "4x5": (1080, 1350), "2x3": (1000, 1500)}
    # back-compat: top-level image_url == the 1x1 render url
    primary = next(r for r in body["renders"] if r["ratio"] == "1x1")
    assert body["image_url"] == primary["image_url"]
    assert body["s3_uri"] == primary["s3_uri"]
    # PART A — provenance surfaced
    assert body["provenance"]["engine"] == "stability-control-structure"


def test_handler_empty_prompt_defaults_to_brand_tagline(monkeypatch, tmp_path: Path) -> None:
    # empty or missing prompt must never 400 — it defaults to the brand tagline
    # and generation proceeds normally, always producing a real hero.
    monkeypatch.setattr(
        generate_lambda, "generate_hero_set", _stub_hero_set("bedrock:nova-pro", tmp_path)
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    # missing prompt entirely
    resp = generate_lambda.handler({"body": json.dumps({})}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["image_url"].startswith("https://presigned.example/")
    assert body["source"] == "bedrock:nova-pro"
    assert body["prompt"] == "KODIAK - Nourishment for Today's Frontier. Keep It Wild."

    # empty/whitespace prompt
    resp = generate_lambda.handler({"body": json.dumps({"prompt": "   "})}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["prompt"] == "KODIAK - Nourishment for Today's Frontier. Keep It Wild."


def test_handler_falls_back_to_default_hero_label(monkeypatch, tmp_path: Path) -> None:
    # true last-resort path: generate_hero_set never returns "mock"/"preview" — the
    # non-shaming fallback label is what reaches the handler and the UI.
    monkeypatch.setattr(
        generate_lambda,
        "generate_hero_set",
        _stub_hero_set("bedrock:nova-pro-fallback", tmp_path),
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    resp = generate_lambda.handler({"prompt": "x"}, None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["source"] == "bedrock:nova-pro-fallback"
    assert "mock" not in body["source"]


def test_options_preflight_returns_200(monkeypatch) -> None:
    event = {"requestContext": {"http": {"method": "OPTIONS"}}}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    assert resp["body"] == ""


def test_handler_sanitizes_celebrity_name_before_brief_msg(monkeypatch, tmp_path: Path) -> None:
    # a client-built prompt naming a real person must be rewritten name-free BEFORE it
    # reaches generate_hero_set as brief_msg — that string drives every Nova Pro/Stability
    # prompt, so the raw name must never flow past the handler.
    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        out_dir = kwargs.get("out_dir") or (tmp_path / "renders")
        return _fake_renders(Path(out_dir)), "bedrock:nova-pro", {"engine": "pillow-compose"}

    monkeypatch.setattr(generate_lambda, "generate_hero_set", _capture)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {
        "body": json.dumps(
            {
                "prompt": "Zac Efron athletic-morning energy — high-protein pre-trail fuel, "
                "aspirational active lifestyle. Keep It Wild.",
                "theme": "zac-efron",
            }
        )
    }
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    brief_msg = captured["brief_msg"]
    assert "zac" not in brief_msg.lower()
    assert "efron" not in brief_msg.lower()
    assert "Keep It Wild." in brief_msg


def test_presigned_url_signed_with_attachment_disposition(monkeypatch, tmp_path: Path) -> None:
    # cross-origin presigned GET must be signed with Content-Disposition: attachment
    # so the browser saves (not inline-opens) with a sensible .png filename. Every one
    # of the three renders is signed this way.
    fake_s3 = _FakeS3()
    monkeypatch.setattr(
        generate_lambda, "generate_hero_set", _stub_hero_set("bedrock:nova-pro", tmp_path)
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: fake_s3)

    event = {"body": json.dumps({"product": "power-cakes", "region": "us"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200

    # all three renders were uploaded + presigned with an attachment .png disposition
    assert len(fake_s3.presign_calls) == 3
    for params in fake_s3.presign_calls:
        disposition = params["ResponseContentDisposition"]
        assert disposition.startswith("attachment; filename=")
        assert disposition.endswith('.png"')


def test_download_filename_sanitizes_and_falls_back() -> None:
    assert generate_lambda._download_filename("power-cakes", "us", None) == (
        "KODIAK-CAKES-POWER-CAKES-US.png"
    )
    # theme wins over product for the image, so it also names the download
    assert generate_lambda._download_filename("power-cakes", "us", "green chile") == (
        "KODIAK-CAKES-GREEN-CHILE-US.png"
    )
    # empty inputs still yield a stable, safe name
    assert generate_lambda._download_filename("", "", None) == "KODIAK-CAKES-CAMPAIGN-ASSET.png"
