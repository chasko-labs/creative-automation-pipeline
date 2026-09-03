"""Tests for the prompt-to-image Lambda handler — no real AWS."""
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
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def _patch_deps(monkeypatch, tmp_path: Path) -> None:
    fake_png = tmp_path / "fake.png"
    fake_png.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(
        generate_lambda,
        "_try_bedrock_nova_canvas",
        lambda prompt, out_path, width, height: fake_png,
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())


def test_handler_returns_200_with_image_url(monkeypatch, tmp_path: Path) -> None:
    _patch_deps(monkeypatch, tmp_path)
    event = {"body": json.dumps({"prompt": "a bear eating pancakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["image_url"].startswith("https://presigned.example/")
    assert body["source"] == "bedrock:nova-canvas"
    assert body["prompt"] == "a bear eating pancakes"


def test_handler_falls_back_to_mock(monkeypatch, tmp_path: Path) -> None:
    fake_png = tmp_path / "mock.png"
    fake_png.write_bytes(b"\x89PNG\r\n")
    monkeypatch.setattr(
        generate_lambda,
        "_try_bedrock_nova_canvas",
        lambda prompt, out_path, width, height: None,
    )
    monkeypatch.setattr(
        generate_lambda,
        "_mock_hero",
        lambda product, prompt, region, out_path, idx: fake_png,
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    resp = generate_lambda.handler({"prompt": "x"}, None)
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    assert body["source"] == "mock"


def test_options_preflight_returns_200(monkeypatch) -> None:
    event = {"requestContext": {"http": {"method": "OPTIONS"}}}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    assert resp["headers"]["Access-Control-Allow-Origin"] == "*"
    assert resp["body"] == ""
