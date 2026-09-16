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
# No named-person themes ship; the map stays empty and every slug falls through
# to the plain slug-to-words form. The mechanism is pinned with a synthetic entry
# so a future partner theme cannot regress into a filter trip.
def test_safe_theme_text_falls_through_with_empty_persona_map() -> None:
    assert generate._THEME_PERSONA_MAP == {}
    assert generate._safe_theme_text("wild-grizzly-bears") == "wild grizzly bears"
    assert generate._safe_theme_text("wild-frontier") == "wild frontier"


def test_persona_mechanism_still_sanitizes_when_populated(monkeypatch) -> None:
    # synthetic entry only — proves the filter-safe indirection works if a
    # named-person theme ever returns; no real person ships in the map.
    monkeypatch.setitem(
        generate._THEME_PERSONA_MAP, "example-person", "filter-safe persona text"
    )
    assert generate._safe_theme_text("example-person") == "filter-safe persona text"
    out = generate._safe_prompt_text("Example Person morning energy. Keep It Wild.")
    assert "example person" not in out.lower()
    assert "filter-safe persona text" in out
    assert "Keep It Wild." in out


def test_default_scene_prompt_carries_wild_dispatch(monkeypatch) -> None:
    # with boto3 unavailable the deterministic default prompt is built directly —
    # the unified wild dispatch must be present, palette spelled out.
    monkeypatch.setattr(generate, "boto3", None)
    prompt = generate._nova_pro_scene_prompt(
        Path("seed.png"),
        "Power Cakes",
        "wild mornings",
        "us",
        "active families",
        "wild-grizzly-bears",
    )
    assert "wild grizzly bears" in prompt.lower()
    assert "frontier-green" in prompt.lower()
    assert "on-brand Kodiak" not in prompt


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


def test_generate_hero_dev_flag_skips_stability_uses_nova_pro_pillow(tmp_path: Path, monkeypatch) -> None:
    # dev/prod image-engine split: KODIAK_ENABLE_STABILITY_RUNG=0 makes generate_hero
    # skip ALL generative Stability calls and render deterministically via the
    # Nova-Pro-art-directed Pillow path (rung C). Nova Pro (the art director) must still
    # run — the headline/scene-prompt path is unaffected by the flag.
    #
    # _STABILITY_RUNG_ON is read once at import, so setting the env alone will not flip
    # the already-bound module constant — patch the constant directly (this is exactly
    # the value the env would produce) and set the env too for good measure.
    monkeypatch.setenv("KODIAK_ENABLE_STABILITY_RUNG", "0")
    monkeypatch.setattr(generate, "_STABILITY_RUNG_ON", False)

    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)

    # tripwire: if the generative rung is honored, this must NEVER be called in dev.
    called = {"stability": 0}
    monkeypatch.setattr(
        generate, "_stability_control_hero",
        lambda s, p, o: called.__setitem__("stability", called["stability"] + 1) or None,
    )
    # Nova Pro art-direction still runs in dev: the director is offline (no creds -> None),
    # so the headline resolves via the stock Nova caption path. Feed it a known line and
    # assert it surfaces in provenance — proof the Nova-Pro headline path executed.
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: "Fuel Wild Mornings")

    out = tmp_path / "hero.png"
    result, source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    # deterministic Nova-Pro-art-directed Pillow render, NOT a Stability restyle
    assert source == "bedrock:nova-pro"
    assert prov["rung"] == "C"
    # zero generative Stability invocations in dev
    assert called["stability"] == 0, "stability rung ran despite KODIAK_ENABLE_STABILITY_RUNG=0"
    # provenance stays honest: the flag caused the skip, distinct from budget-exhausted
    assert prov["fallthrough_reason"] == "stability-rung-disabled"
    # the Nova Pro headline path still ran and its line is recorded
    assert prov.get("copy_headline"), "Nova-Pro headline path did not run in dev"
    assert prov["copy_headline"] == "Fuel Wild Mornings"


def test_generate_hero_no_seed_returns_brand_floor(tmp_path: Path, monkeypatch) -> None:
    # no theme, no sku photo, no disk asset, no packshot -> Stability never runs, the
    # ladder ends at rung D (brand-floor): real Kodiak pixels, zero network, non-lying label.
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: None)
    from creative_automation import dam

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
    from creative_automation import dam

    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: "brands/kodiak/raw-ingest/theme.jpg")
    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: seed)
    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: fake)

    out = tmp_path / "hero.png"
    result, source, _prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        theme="wild-grizzly-bears",
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
    key = generate._resolve_theme_photo("wild-grizzly-bears")
    assert key is not None and key.startswith(_DAM_PREFIX)
    assert key[len(_DAM_PREFIX):] in real


def test_sku_resolver_returns_real_committed_key() -> None:
    real = _real_key_basenames()
    key = generate._resolve_dam_photo("apple-cinnamon-oatmeal-packets")
    assert key is not None and key.startswith(_DAM_PREFIX)
    assert key[len(_DAM_PREFIX):] in real


# ------------------------------------------------------- _parse_layout LAYOUT hygiene
def test_parse_layout_strips_inline_layout_suffix() -> None:
    # the live bug: Nova Pro returned headline + LAYOUT on ONE line and the
    # directive leaked into the rendered headline.
    headline, side = generate._parse_layout("Power up family mornings! LAYOUT: right")
    assert headline == "Power up family mornings!"
    assert side == "right"


def test_parse_layout_keeps_two_line_form() -> None:
    headline, side = generate._parse_layout("Fuel Your Adventure\nLAYOUT: left")
    assert headline == "Fuel Your Adventure"
    assert side == "left"


def test_parse_layout_inline_is_case_insensitive_and_unquoted() -> None:
    headline, side = generate._parse_layout('"Wild mornings" layout: center')
    assert headline == "Wild mornings"
    assert side == "center"


def test_parse_layout_invalid_side_line_never_becomes_headline() -> None:
    headline, side = generate._parse_layout("LAYOUT: bottom")
    assert headline == ""
    assert side == "center"


# --------------------------------------------------------------- mascot lock (Unit 2)
def test_style_sandwich_default_has_no_mascot_block(monkeypatch) -> None:
    # lock OFF (default): existing renders are byte-identical, no descriptor injected.
    monkeypatch.delenv("KODIAK_MASCOT_LOCK", raising=False)
    out = generate._style_sandwich("wild frontier restyle")
    assert out == f"{generate.STYLE_HEAD}wild frontier restyle{generate.STYLE_TAIL}"
    assert generate.MASCOT_DESCRIPTOR_BLOCK not in out


def test_style_sandwich_mascot_lock_pins_frozen_block(monkeypatch) -> None:
    # lock ON: the frozen descriptor lands in the SUBJECT slot ahead of the scene,
    # inside the frozen style ends; repeated wrapping is idempotent (one block only).
    monkeypatch.setenv("KODIAK_MASCOT_LOCK", "1")
    once = generate._style_sandwich("log cabin at dawn")
    assert once.startswith(generate.STYLE_HEAD)
    assert once.endswith(generate.STYLE_TAIL)
    # brand scrub: the bear-identity words survive but the brand token never
    # reaches the image model, even inside the frozen mascot block.
    assert "kodiak" not in once.lower()
    scrubbed_block = generate._BRAND_SCRUB_RE.sub(
        "", generate.MASCOT_DESCRIPTOR_BLOCK
    ).strip()
    assert scrubbed_block in once
    assert once.index(scrubbed_block) < once.index("log cabin at dawn")
    twice = generate._style_sandwich(once)
    assert twice == once


def test_style_sandwich_scrubs_brand_token() -> None:
    # proven 2026-09-10: any brand word in the stability prompt renders as
    # hallucinated pack copy ("KODA CAKTS"). the scrub removes the token and
    # its "on-brand" prefix; brand identity ships via composited DAM art.
    p = generate._style_sandwich(
        "Buttermilk Power Cakes family breakfast, Kodiak Cakes subscription, "
        "on-brand Kodiak"
    )
    assert "kodiak" not in p.lower()
    assert "on-brand ." not in p
    assert "Buttermilk Power Cakes family breakfast" in p
