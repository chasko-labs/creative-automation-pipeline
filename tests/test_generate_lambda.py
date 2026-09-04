"""Tests for the brief-to-hero Lambda handler — no real AWS."""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import generate_lambda


class _FakeS3:
    """Stub s3 client capturing put_object and returning a canned presigned url."""

    def put_object(self, **kwargs) -> dict:
        self.last_put = kwargs
        return {}

    def generate_presigned_url(self, op, Params, ExpiresIn) -> str:  # noqa: N803 — boto3 kwarg name
        self.last_presign_params = Params
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def test_handler_returns_200_with_image_url(monkeypatch, tmp_path: Path) -> None:
    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(
        generate_lambda,
        "generate_hero",
        lambda **kwargs: (fake_png, "bedrock:nova-pro"),
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


def test_handler_empty_prompt_defaults_to_brand_tagline(monkeypatch, tmp_path: Path) -> None:
    # empty or missing prompt must never 400 — it defaults to the brand tagline
    # and generation proceeds normally, always producing a real hero.
    fake_png = tmp_path / "default.png"
    fake_png.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(
        generate_lambda,
        "generate_hero",
        lambda **kwargs: (fake_png, "bedrock:nova-pro"),
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
    # true last-resort path: generate_hero never returns "mock"/"preview" — the
    # non-shaming fallback label is what reaches the handler and the UI.
    fake_png = tmp_path / "fallback.png"
    fake_png.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(
        generate_lambda,
        "generate_hero",
        lambda **kwargs: (fake_png, "bedrock:nova-pro-fallback"),
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


def test_presigned_url_signed_with_attachment_disposition(monkeypatch, tmp_path: Path) -> None:
    # cross-origin presigned GET must be signed with Content-Disposition: attachment
    # so the browser saves (not inline-opens) with a sensible .png filename.
    fake_png = tmp_path / "hero.png"
    fake_png.write_bytes(b"\x89PNG\r\n")
    fake_s3 = _FakeS3()
    monkeypatch.setattr(
        generate_lambda,
        "generate_hero",
        lambda **kwargs: (fake_png, "bedrock:nova-pro"),
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: fake_s3)

    event = {"body": json.dumps({"product": "power-cakes", "region": "us"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200

    disposition = fake_s3.last_presign_params["ResponseContentDisposition"]
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
