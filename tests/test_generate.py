"""Bedrock Stability control-structure seam for mode-3 hero generation.

No real AWS: the bedrock-runtime client is a fake that captures invoke_model kwargs
and returns a canned base64 image. Asserts the Stability request schema (NOT Nova's
taskType), the inference-profile modelId, base64 decode-to-out_path, the
bedrock:stability-control-structure source tag, and the full fallback chain
(Stability raises -> Pillow compose; no seed -> placeholder). Map-resolution assertions
run against the committed fixture tests/fixtures/dam-real-keys.txt (not /tmp).
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from creative_automation import generate

_FIXTURE = Path(__file__).parent / "fixtures" / "dam-real-keys.txt"


def _png_bytes(size: tuple[int, int] = (1024, 1024), color=(180, 90, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _make_seed(path: Path, size: tuple[int, int] = (1024, 1024)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_bytes(size))
    return path


class _FakeBedrockBody:
    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return self._payload


class _FakeBedrockClient:
    """Captures invoke_model kwargs; returns a canned Stability images[0] payload."""

    def __init__(self, image_b64: str) -> None:
        self.image_b64 = image_b64
        self.last_invoke: dict = {}

    def invoke_model(self, **kwargs) -> dict:
        self.last_invoke = kwargs
        payload = json.dumps({"images": [self.image_b64]}).encode("utf-8")
        return {"body": _FakeBedrockBody(payload)}

    # generate_hero's scene-prompt art-director ask goes through converse; keep it
    # deterministic and network-free here.
    def converse(self, **kwargs) -> dict:
        return {"output": {"message": {"content": [{"text": "wild frontier restyle"}]}}}


# --------------------------------------------------------------- Stability invoke schema
def test_stability_control_hero_request_shape_and_write(tmp_path: Path, monkeypatch) -> None:
    seed = _make_seed(tmp_path / "seed.png")
    canned = base64.b64encode(_png_bytes(color=(10, 200, 120))).decode("ascii")
    fake = _FakeBedrockClient(canned)
    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: fake)

    out = tmp_path / "styled.png"
    result = generate._stability_control_hero(seed, "restyle to wild frontier", out)

    assert result is not None and result.exists()
    # the written file is the DECODED canned image, not the seed
    assert out.read_bytes() == base64.b64decode(canned)

    # modelId is the inference-profile id, never the bare stability.* id
    assert fake.last_invoke["modelId"] == "us.stability.stable-image-control-structure-v1:0"
    assert fake.last_invoke["modelId"].startswith("us.stability.")
    assert fake.last_invoke["contentType"] == "application/json"

    body = json.loads(fake.last_invoke["body"])
    # Stability schema — NOT Nova's taskType/textToImageParams
    assert set(body) == {"prompt", "image", "control_strength", "seed", "output_format"}
    assert "taskType" not in body
    assert "textToImageParams" not in body
    assert body["prompt"] == generate._style_sandwich("restyle to wild frontier")
    assert body["output_format"] == "png"
    assert body["control_strength"] == generate.STABILITY_CONTROL_STRENGTH
    # seed carried as base64 that decodes back to a PNG
    assert base64.b64decode(body["image"])[:4] == b"\x89PNG"


def test_stability_upscales_below_floor_seed(tmp_path: Path, monkeypatch) -> None:
    # a seed below the 64px floor must be upscaled before encode (else ValidationException)
    tiny = _make_seed(tmp_path / "tiny.png", size=(32, 32))
    b64 = generate._seed_b64_for_stability(tiny)
    with Image.open(io.BytesIO(base64.b64decode(b64))) as img:
        assert min(img.size) >= generate._STABILITY_MIN_DIM


def test_stability_returns_none_on_client_error(tmp_path: Path, monkeypatch) -> None:
    # invoke_model raising a ClientError (e.g. AccessDenied) surfaces None, not a raise;
    # the exact code is logged (asserted by no exception escaping + None return).
    from botocore.exceptions import ClientError

    seed = _make_seed(tmp_path / "seed.png")

    class _DenyClient:
        def invoke_model(self, **kwargs):
            raise ClientError({"Error": {"Code": "AccessDeniedException", "Message": "no"}}, "InvokeModel")

    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: _DenyClient())
    assert generate._stability_control_hero(seed, "p", tmp_path / "o.png") is None


# --------------------------------------------------------------- persona sanitization
def test_safe_theme_text_maps_celebrity_to_name_free_persona() -> None:
    # a named-person slug maps to its filter-safe persona; the raw name is gone.
    persona = generate._safe_theme_text("zac-efron")
    assert persona == generate._THEME_PERSONA_MAP["zac-efron"]
    assert "zac" not in persona.lower()
    assert "efron" not in persona.lower()
    # an ordinary slug falls through to the plain slug-to-words form
    assert generate._safe_theme_text("wild-frontier") == "wild frontier"


def test_default_scene_prompt_omits_raw_celebrity_token(monkeypatch) -> None:
    # with boto3 unavailable the deterministic default prompt is built directly — the
    # raw celebrity token must NOT appear; the persona text must.
    monkeypatch.setattr(generate, "boto3", None)
    prompt = generate._nova_pro_scene_prompt(
        Path("seed.png"), "Power Cakes", "wild mornings", "us", "active families", "zac-efron"
    )
    assert "zac" not in prompt.lower()
    assert "efron" not in prompt.lower()
    assert generate._THEME_PERSONA_MAP["zac-efron"] in prompt


def test_safe_prompt_text_rewrites_incoming_celebrity_name() -> None:
    # a client-built prompt embedding a real name is rewritten name-free, persona in,
    # and the rest of the brief survives intact.
    out = generate._safe_prompt_text(
        "Zac Efron athletic-morning energy — high-protein pre-trail fuel, "
        "aspirational active lifestyle. Keep It Wild."
    )
    assert "zac" not in out.lower()
    assert "efron" not in out.lower()
    assert generate._THEME_PERSONA_MAP["zac-efron"] in out
    assert "Keep It Wild." in out
    assert "pre-trail fuel" in out


def test_safe_prompt_text_passes_through_when_no_celebrity() -> None:
    # a prompt with no named person is returned unchanged.
    brief = "wild mornings on the frontier — high-protein fuel. Keep It Wild."
    assert generate._safe_prompt_text(brief) == brief


# --------------------------------------------------------------- generate_hero seam
def test_generate_hero_stability_primary_on_disk_seed(tmp_path: Path, monkeypatch) -> None:
    # a real disk seed + Stability success -> source is the stability tag, and the
    # written hero is the decoded Stability image.
    seed = _make_seed(tmp_path / "disk-seed.png")
    canned = base64.b64encode(_png_bytes(color=(5, 5, 200))).decode("ascii")
    fake = _FakeBedrockClient(canned)

    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: fake)

    out = tmp_path / "hero.png"
    # overlays OFF here so the written hero is the verbatim decoded Stability image —
    # PART C/D (brand + kraft) are covered separately in test_generate_multisize.py.
    result, source, _prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        brand_overlay=False,
        paper_overlay=False,
    )
    assert result.exists()
    assert source == generate.STABILITY_SOURCE
    assert source == "bedrock:stability-control-structure"
    assert out.read_bytes() == base64.b64decode(canned)
    # seed carried into the invoke body
    body = json.loads(fake.last_invoke["body"])
    assert set(body) == {"prompt", "image", "control_strength", "seed", "output_format"}


def test_generate_hero_falls_back_to_compose_when_stability_fails(tmp_path: Path, monkeypatch) -> None:
    # Stability unavailable (helper -> None) but a real seed exists -> Pillow compose,
    # source bedrock:nova-pro. This is the documented fallback chain step 2.
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate, "_stability_control_hero", lambda s, p, o: None)
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "hero.png"
    result, source, _prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert source == "bedrock:nova-pro"


def test_generate_hero_no_seed_returns_brand_floor(tmp_path: Path, monkeypatch) -> None:
    # no theme, no sku photo, no disk asset, no packshot -> Stability never runs, the
    # ladder ends at rung D (brand-floor): real Kodiak pixels, zero network, non-lying label.
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: None)
    import creative_automation.dam as dam

    monkeypatch.setattr(dam, "resolve_packshot", lambda pid, dam_root=None: None)
    called = {"stability": 0}
    monkeypatch.setattr(
        generate, "_stability_control_hero",
        lambda s, p, o: called.__setitem__("stability", called["stability"] + 1) or None,
    )

    out = tmp_path / "hero.png"
    result, source, prov = generate.generate_hero(
        product_id="nonexistent-sku",
        product_name="Nonexistent",
        brief_msg="x",
        region="us",
        audience="families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert source == generate.BRAND_FLOOR_SOURCE == "brand-floor"
    assert "mock" not in source
    # rung D is reached; the image engine (rung B) is never invoked with no seed
    assert prov["rung"] == "D"
    assert prov["engine"] == "brand-floor"
    assert called["stability"] == 0


def test_generate_hero_theme_seed_wins_and_conditions(tmp_path: Path, monkeypatch) -> None:
    # theme resolves to a DAM key, fetch returns a real seed -> Stability conditions
    # that thematic seed -> stability tag. Theme drives the pixels.
    seed = _make_seed(tmp_path / "theme-seed.png")
    canned = base64.b64encode(_png_bytes(color=(120, 30, 200))).decode("ascii")
    fake = _FakeBedrockClient(canned)
    import creative_automation.dam as dam

    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: "brands/kodiak/raw-ingest/theme.jpg")
    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: seed)
    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: fake)

    out = tmp_path / "hero.png"
    result, source, _prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="athletic mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        theme="zac-efron",
    )
    assert result.exists()
    assert source == generate.STABILITY_SOURCE


# --------------------------------------------------------------- map resolution vs fixture
# tests/fixtures/dam-real-keys.txt is the committed real-DAM-key set (one basename per
# line, no prefix) — the same fixture test_theme_asset_map.py validates pools against.
_DAM_PREFIX = "brands/kodiak/raw-ingest/kodiakcakes/images/"


def _real_key_basenames() -> set[str]:
    return {ln.strip() for ln in _FIXTURE.read_text(encoding="utf-8").splitlines() if ln.strip()}


def test_theme_resolver_returns_real_committed_key() -> None:
    # a known chip theme resolves to a full DAM key whose basename is in the committed
    # real-key fixture — the resolved seed is a real asset, not a fabricated path.
    real = _real_key_basenames()
    key = generate._resolve_theme_photo("bears")
    assert key is not None and key.startswith(_DAM_PREFIX)
    assert key[len(_DAM_PREFIX):] in real


def test_sku_resolver_returns_real_committed_key() -> None:
    real = _real_key_basenames()
    key = generate._resolve_dam_photo("apple-cinnamon-oatmeal-packets")
    assert key is not None and key.startswith(_DAM_PREFIX)
    assert key[len(_DAM_PREFIX):] in real
