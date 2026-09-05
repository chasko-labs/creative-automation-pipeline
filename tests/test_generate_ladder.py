"""Never-fail degradation ladder A->B->C->D on the /generate seam.

GOVERNING PRINCIPLE (Bryan): there is NO situation where a well-formed POST /generate
fails to produce a real campaign. A well-formed POST returns 200 with REAL Kodiak pixels
100% of the time; only a genuinely malformed request body is a 4xx; 503 is unreachable.

These tests exercise generate_hero's ladder offline (no AWS):
  a) a mapped SKU composites the verbatim box on rung A
  b) a Bedrock ReadTimeoutError on rung B falls THROUGH to rung C (pillow-compose) and
     returns real pixels + provenance rung=C fallthrough_reason=bedrock-timeout — NOT a
     raise, NOT a 503
  c) no seed + no packshot lands on rung D (brand-floor): real pixels, never raises
  d) a malformed request body is the ONLY non-200 (a 400) through the handler

Rung B's Bedrock client is the fail-fast one (_bedrock_failfast_client); here invoke_model
is monkeypatched to raise the timeout so no network is touched and CI stays deterministic.
"""
from __future__ import annotations

import json
from pathlib import Path

from botocore.exceptions import ReadTimeoutError
from PIL import Image

from creative_automation import dam
from creative_automation import generate as generate_mod


def _make_box_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (400, 600), (200, 120, 40, 255)).save(path, "PNG")
    return path


def _local_box_fetch(_tmp: Path):
    def _fetch(key: str, dest: Path):
        if key and "705599" in key.rsplit("/", 1)[-1]:
            return _make_box_png(Path(dest))
        return None

    return _fetch


def _distinct_colors(path: Path) -> int:
    """A cheap 'real pixels' assertion — a composited render is never a single flat fill."""
    with Image.open(path) as img:
        colors = img.convert("RGB").getcolors(maxcolors=200000)
    return len(colors) if colors else 1


# --------------------------------------------------------------------------- #
# (a) mapped SKU -> rung A (packshot-composite)
# --------------------------------------------------------------------------- #
def test_mapped_sku_returns_rung_a(tmp_path, monkeypatch):
    monkeypatch.setattr(dam, "fetch_dam_key", _local_box_fetch(tmp_path))
    # isolate the packshot branch from seed resolution — no theme/sku/disk seed.
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    # rung B must never even be considered for a mapped SKU.
    stability_calls = {"n": 0}
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero",
        lambda s, p, o: stability_calls.__setitem__("n", stability_calls["n"] + 1) or None,
    )

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="banana-muffin-quick-bread-mix",
        product_name="Banana Muffin and Quick Bread Mix",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )

    assert result.exists()
    assert _distinct_colors(result) > 20  # real composited pixels, not a flat fill
    assert source == generate_mod.PACKSHOT_SOURCE == "dam:packshot-composite"
    assert prov["rung"] == "A"
    assert prov["engine"] == "packshot-composite"
    assert prov["packshot"] is not None and "705599" in prov["packshot"]
    assert isinstance(prov["elapsed_ms"], int)
    # rung A is one-directional: a higher rung (B) is never retried below it.
    assert stability_calls["n"] == 0


# --------------------------------------------------------------------------- #
# (b) Bedrock ReadTimeoutError on rung B -> falls through to rung C, NOT a 503
# --------------------------------------------------------------------------- #
def test_bedrock_read_timeout_falls_through_to_rung_c(tmp_path, monkeypatch):
    # a real seed resolves so rung B is attempted; the fail-fast Bedrock client raises a
    # ReadTimeoutError inside invoke_model — the ladder must CONTINUE to rung C, return
    # real pixels, and record rung=C fallthrough_reason=bedrock-timeout. No exception, no 503.
    seed = tmp_path / "seed.png"
    seed.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1024), (180, 90, 30)).save(seed, "PNG")
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: seed)
    # no packshot -> the ladder reaches the B/C seam
    monkeypatch.setattr(dam, "resolve_packshot", lambda pid, dam_root=None: None)
    # deterministic prompt/caption — no live Nova Pro
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    # the fail-fast Bedrock client's invoke_model raises a ReadTimeoutError (12s cap hit).
    class _TimeoutClient:
        def invoke_model(self, **kwargs):
            raise ReadTimeoutError(endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com")

    monkeypatch.setattr(generate_mod.boto3, "client", lambda *a, **k: _TimeoutClient())

    out = tmp_path / "hero.png"
    # must NOT raise
    result, source, prov = generate_mod.generate_hero(
        product_id="totally-made-up-sku-xyz",
        product_name="Made Up",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )

    assert result.exists()
    assert _distinct_colors(result) > 20  # rung C composited real pixels on the seed
    # rung C is the guaranteed-real workhorse below B
    assert source == "bedrock:nova-pro"
    assert prov["rung"] == "C"
    assert prov["engine"] == "pillow-compose"
    assert prov["fallthrough_reason"] == "bedrock-timeout"
    # never a 503 / error string
    assert source != "503" and "503" not in str(source)


# --------------------------------------------------------------------------- #
# (c) no seed + no packshot -> rung D (brand-floor), real pixels, never raises
# --------------------------------------------------------------------------- #
def test_no_seed_no_packshot_lands_rung_d(tmp_path, monkeypatch):
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(dam, "resolve_packshot", lambda pid, dam_root=None: None)
    # rung B must never run with no seed
    stability_calls = {"n": 0}
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero",
        lambda s, p, o: stability_calls.__setitem__("n", stability_calls["n"] + 1) or None,
    )

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="no-such-sku",
        product_name="No Such Product",
        brief_msg="frontier trail energy",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )

    assert result.exists()
    assert _distinct_colors(result) > 5  # brand-floor composite: logo + wordmark + accent bar
    assert source == generate_mod.BRAND_FLOOR_SOURCE == "brand-floor"
    assert prov["rung"] == "D"
    assert prov["engine"] == "brand-floor"
    assert "mock" not in source and "preview" not in source
    assert stability_calls["n"] == 0


def test_rung_d_survives_missing_bundled_asset(tmp_path, monkeypatch):
    # rung D cannot fail — even if the bundled brand asset is somehow absent, the canvas
    # + wordmark + accent bar are still real Kodiak pixels. No raise, no fallthrough.
    monkeypatch.setattr(generate_mod, "_BRAND_FLOOR_ASSET", tmp_path / "does-not-exist.png")
    out = tmp_path / "floor.png"
    result = generate_mod._brand_floor("Power Cakes", "1x1", out)
    assert result.exists()
    with Image.open(result) as img:
        assert img.size == (1080, 1080)


# --------------------------------------------------------------------------- #
# (d) malformed request is the ONLY 4xx; a well-formed POST is 200 real pixels
# --------------------------------------------------------------------------- #
class _FakeS3:
    """Captures put_object and hands back a fake presigned URL — no AWS."""

    def put_object(self, **kwargs):
        return {}

    def generate_presigned_url(self, *a, **k):
        return "https://example.test/render.png"


def _install_handler_stubs(monkeypatch, tmp_path):
    from creative_automation import generate_lambda

    monkeypatch.setattr(generate_lambda, "_s3_client", lambda: _FakeS3())
    # keep the handler fast + offline: stub generate_hero to a real on-disk floor render.
    def _stub_hero(*, product_id, product_name, brief_msg, region, audience, out_path,
                   idx=0, ratio="1x1", theme=None, brand_overlay=True, paper_overlay=True):
        p = Path(out_path)
        generate_mod._brand_floor(product_name, ratio, p)
        return p, generate_mod.BRAND_FLOOR_SOURCE, {"rung": "D", "engine": "brand-floor"}

    monkeypatch.setattr(generate_lambda, "generate_hero", _stub_hero)
    return generate_lambda


def test_malformed_body_is_the_only_4xx(tmp_path, monkeypatch):
    generate_lambda = _install_handler_stubs(monkeypatch, tmp_path)
    # unparseable JSON body -> 400 (the ONLY non-200 a well-formed contract allows)
    resp = generate_lambda.handler({"body": "{not json at all"})
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["ok"] is False
    assert "malformed" in body["error"].lower()


def test_well_formed_post_is_200_real_pixels(tmp_path, monkeypatch):
    generate_lambda = _install_handler_stubs(monkeypatch, tmp_path)
    # a well-formed POST — even one that reaches the floor rung — is a 200, never a 503.
    resp = generate_lambda.handler(
        {"body": json.dumps({"prompt": "Keep It Wild", "product": "no-such-sku"})}
    )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["image_url"]
    assert body["statusCode"] != 503 if "statusCode" in body else True
    # the source is real-pixel brand-floor, never a 503 string
    assert body["source"] == "brand-floor"


def test_empty_prompt_is_still_200_not_4xx(tmp_path, monkeypatch):
    # a missing prompt is NOT malformed — the handler supplies a default brand line and
    # still returns 200 real pixels. Only an unparseable body is a 4xx.
    generate_lambda = _install_handler_stubs(monkeypatch, tmp_path)
    resp = generate_lambda.handler({"body": json.dumps({"product": "power-cakes"})})
    assert resp["statusCode"] == 200
