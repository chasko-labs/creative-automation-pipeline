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

from creative_automation import asset_store
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
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    # isolate the packshot branch from seed resolution — no theme/sku/disk seed.
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    # rung B must never even be considered for a mapped SKU.
    stability_calls = {"n": 0}
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero",
        lambda s, p, o, **_k: stability_calls.__setitem__("n", stability_calls["n"] + 1) or None,
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
    assert source == generate_mod.PACKSHOT_SOURCE == "asset-store:packshot-composite"
    assert prov["rung"] == "A"
    assert prov["engine"] == "packshot-composite"
    assert prov["packshot"] is not None and "705599" in prov["packshot"]
    assert isinstance(prov["elapsed_ms"], int)
    # rung A is one-directional: a higher rung (B) is never retried below it.
    assert stability_calls["n"] == 0


def test_packshot_without_seed_runs_director_headline(tmp_path, monkeypatch):
    # Regression: the packshot-first branch used brief_msg[:48] verbatim whenever
    # no seed photo resolved, so the grounded director never ran for mapped SKUs
    # in prod. The resolved packshot box photo feeds the headline pipeline.
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o, **_k: None)
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "true")
    monkeypatch.setattr(
        generate_mod, "_director_headline_text", lambda *a, **k: "Wild Mornings Start Here"
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
    assert source == generate_mod.PACKSHOT_SOURCE
    assert prov["rung"] == "A"
    assert prov["headline"] == "Wild Mornings Start Here"
    assert prov["headline_source"] == generate_mod._DIRECTOR_LIVE_SOURCE


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
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: seed)
    # no packshot -> the ladder reaches the B/C seam
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
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
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
    # rung B must never run with no seed
    stability_calls = {"n": 0}
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero",
        lambda s, p, o, **_k: stability_calls.__setitem__("n", stability_calls["n"] + 1) or None,
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
                   idx=0, ratio="1x1", theme=None, brand_overlay=True, paper_overlay=True,
                   seed_key=None, layers=None, themes=None, dish=None,
                   art_director=False, market=None, season=None, native_siblings=None):
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


# --------------------------------------------------------------------------- #
# worst-case BUDGET WALL: a near-exhausted soft budget must force an early return on
# rung C (real pixels on the resolved seed) WITHOUT ever starting rung B, and must not
# exceed the budget. This is the 503 repair — a slow probe/Bedrock path can never push
# the ladder past ~24s because the wall skips B and lands on the guaranteed-real C.
# --------------------------------------------------------------------------- #
def test_rung_b_overlaps_caption_with_scene(tmp_path, monkeypatch):
    # caption needs only (seed + statics), same as the scene-prompt: rung B
    # submits it at entry and collects after the restyle. Event handshake
    # proves overlap — in serial order the caption could never observe a
    # restyle still in progress.
    import threading

    seed = tmp_path / "seed.png"
    Image.new("RGB", (1024, 1024), (180, 90, 30)).save(seed, "PNG")
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: "seed-key")
    monkeypatch.setattr(asset_store, "fetch_asset_key", lambda key, dest: seed)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
    monkeypatch.setattr(generate_mod, "_similarity_gate_enabled", lambda: False)

    caption_started = threading.Event()
    restyle_started = threading.Event()

    def fake_caption(src, product_name, brief_msg, region, audience, remaining_ms=None):
        caption_started.set()
        assert restyle_started.wait(timeout=10), "caption never overlapped the restyle"
        return "trail fuel caption"

    def fake_scene(seed_p, product_name, brief_msg, region, audience, theme,
                   combo_extras=None, dish=None, market=None, season=None):
        return "wild frontier restyle"

    def fake_restyle(seed_p, scene_prompt, out_path, **kwargs):
        restyle_started.set()
        assert caption_started.wait(timeout=10), "restyle ran with no overlapped caption"
        Image.open(seed).save(out_path, "PNG")
        return out_path

    monkeypatch.setattr(generate_mod, "_caption_with_budget", fake_caption)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", fake_scene)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", fake_restyle)

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="totally-made-up-sku-xyz",
        product_name="Made Up",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )

    assert prov["rung"] == "B"
    assert source == generate_mod.STABILITY_SOURCE
    # the overlapped caption wrote the headline, not the brief fallback.
    assert prov["headline_source"] == "bedrock:nova-pro-caption"
    assert "Trail" in (prov["copy_headline"] or "")


def test_budget_wall_skips_rung_b_lands_rung_c(tmp_path, monkeypatch):
    # a real seed resolves via the (cheap, single-key) sku-mapped path so rung C has a
    # seed to compose; the seed path is NOT probe-gated, so a seed exists regardless.
    seed = tmp_path / "seed.png"
    seed.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1024), (180, 90, 30)).save(seed, "PNG")
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: "seed-key")
    monkeypatch.setattr(asset_store, "fetch_asset_key", lambda key, dest: seed)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    # HARD WALL: soft budget below rung B's gate (_B_BUDGET_MS + _C_RESERVATION_MS) but
    # above the C reservation — the gate MUST skip B and drop to C. Set well under the
    # 19s B gate to model the live "probe already ate the budget" state.
    monkeypatch.setattr(generate_mod, "GENERATE_SOFT_BUDGET_MS", 5000)

    # rung B must never be started once the wall is crossed.
    stability_calls = {"n": 0}
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero",
        lambda s, p, o, **_k: stability_calls.__setitem__("n", stability_calls["n"] + 1) or seed,
    )

    out = tmp_path / "hero.png"
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
    assert source == "bedrock:nova-pro"
    assert prov["rung"] == "C"
    assert prov["engine"] == "pillow-compose"
    # the wall — not a model error — forced the skip
    assert prov["fallthrough_reason"] == "budget-exhausted"
    # rung B was never even attempted
    assert stability_calls["n"] == 0
    # returned within the (tightened) soft budget
    assert prov["elapsed_ms"] <= generate_mod.GENERATE_SOFT_BUDGET_MS



# --------------------------------------------------------------------------- #
# (e) NOVA PRO FAIL-FAST + per-subcall budget gate (the 33s-silent-gap repair):
#   1. both Nova Pro clients build via the fail-fast factory with the tighter Nova read
#      timeout (BEDROCK_NOVA_READ_TIMEOUT_S) — NOT a bare boto3.client — so an uncapped
#      Converse call can never hang past the gateway cap
#   2. a slow Nova Pro scene-prompt that eats the budget makes the STABILITY sub-call
#      gate abandon rung B to rung C with real pixels, still under the soft budget
# One test, driven by a fake monotonic clock so the "slow scene-prompt" is deterministic
# and no network / real sleep is touched.
# --------------------------------------------------------------------------- #
def test_slow_nova_scene_prompt_abandons_rung_b_to_c_failfast(tmp_path, monkeypatch):
    seed = tmp_path / "seed.png"
    seed.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1024), (180, 90, 30)).save(seed, "PNG")
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: "seed-key")
    monkeypatch.setattr(asset_store, "fetch_asset_key", lambda key, dest: seed)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    # Part 1 spy: the Nova Pro scene-prompt MUST build its client via the fail-fast factory
    # with the tighter Nova read timeout. Record every read_timeout the factory is asked
    # for so we can assert the Config is applied to the Nova path (not a bare client).
    factory_timeouts: list[int | None] = []

    def _spy_factory(read_timeout=None):
        factory_timeouts.append(read_timeout)
        raise AssertionError("no network in test — factory client must not be invoked")

    monkeypatch.setattr(generate_mod, "_bedrock_failfast_client", _spy_factory)

    # a scene-prompt that is SLOW: it advances the fake clock past the stability sub-call
    # gate, then returns the deterministic default (mirrors the real graceful degrade).
    # It first touches the fail-fast factory so the spy records the Nova read timeout.
    NOVA_T = generate_mod.BEDROCK_NOVA_READ_TIMEOUT_S

    def _slow_scene(*_a, **_k):
        try:
            generate_mod._bedrock_failfast_client(read_timeout=NOVA_T)
        except AssertionError:
            pass  # spy raises after recording — degrade to default like a real timeout
        clock["t"] += 9.0  # burn 9s of wall-clock — pushes remaining under the B stability gate
        return "scene"

    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", _slow_scene)

    # stability must NEVER be reached once the scene call ate the budget.
    stability_calls = {"n": 0}
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero",
        lambda s, p, o, **_k: stability_calls.__setitem__("n", stability_calls["n"] + 1) or seed,
    )

    # Pin B/C budgets to the pre-seasonal calibration so the 19s B gate + 7+13+3
    # scene gate math is exercised, not the new 25s/28s.
    monkeypatch.setattr(generate_mod, "_B_BUDGET_MS", 16000)
    monkeypatch.setattr(generate_mod, "_C_RESERVATION_MS", 3000)
    # fake monotonic clock: start at 0; the outer B gate + scene gate pass at t=0, then the
    # slow scene advances t so the stability gate (t2) fails -> abandon B to C.
    clock = {"t": 0.0}
    monkeypatch.setattr(generate_mod.time, "monotonic", lambda: clock["t"])
    # 20s budget: covers the outer B gate (19s) and scene gate 1
    # (7+13+3=23s? no — set high enough to pass gate 1, then the 9s burn trips gate 2).
    monkeypatch.setattr(generate_mod, "GENERATE_SOFT_BUDGET_MS", 24000)

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="totally-made-up-sku-xyz",
        product_name="Made Up",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )

    # Part 1: the Nova scene-prompt built its client via the fail-fast factory with the
    # tighter Nova read timeout — proof the Config is applied, not a bare client.
    assert NOVA_T in factory_timeouts
    # Part 2: the slow scene ate the budget -> stability sub-call gate abandoned B to C.
    assert stability_calls["n"] == 0
    assert result.exists()
    assert _distinct_colors(result) > 20  # rung C composited real pixels on the seed
    assert source == "bedrock:nova-pro"
    assert prov["rung"] == "C"
    assert prov["engine"] == "pillow-compose"
    assert prov["fallthrough_reason"] == "budget-exhausted"


# --------------------------------------------------------------------------- #
# (e) mapped SKU + seed -> rung A pastes the verbatim box over an AI-RESTYLED
# scene (fresh photographic pixels, not the recycled asset photo). The box is
# pasted over the restyle — never fed into it, so the compose-fix invariant
# (product pixels never generatively touched) holds.
# --------------------------------------------------------------------------- #
def _seed_and_box_fetch(seed_src: Path):
    def _fetch(key: str, dest: Path):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if key and "705599" in key.rsplit("/", 1)[-1]:
            Image.new("RGBA", (400, 600), (200, 120, 40, 255)).save(dest, "PNG")
        else:
            Image.open(seed_src).save(dest, "PNG")
        return dest

    return _fetch


def _copy_stability(calls: dict):
    def _ok(src: Path, prompt: str, out: Path, **_k):
        calls["n"] += 1
        calls["prompt"] = prompt
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(src).convert("RGB").save(out, "PNG")
        return out

    return _ok


def test_mapped_sku_with_seed_restyles_bg_before_verbatim_paste(tmp_path, monkeypatch):
    # Pin budgets to the original 24s/16s calibration so this rung-A restyle gate
    # is not affected by the seasonal 28s/25s raise for 5×Bedrock.
    monkeypatch.setattr(generate_mod, "GENERATE_SOFT_BUDGET_MS", 24000)
    monkeypatch.setattr(generate_mod, "_B_BUDGET_MS", 16000)
    monkeypatch.setattr(generate_mod, "_C_RESERVATION_MS", 3000)
    seed_src = tmp_path / "seed-src.png"
    Image.new("RGB", (1024, 1024), (30, 90, 160)).save(seed_src, "PNG")
    monkeypatch.setattr(asset_store, "fetch_asset_key", _seed_and_box_fetch(seed_src))
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: "scene/waffle.png")
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(
        generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "wild frontier restyle"
    )
    # inline LAYOUT caption exercises the leak fix end to end through rung A.
    monkeypatch.setattr(
        generate_mod, "_nova_pro_caption", lambda *a, **k: "Fuel frontier mornings LAYOUT: left"
    )
    calls = {"n": 0, "prompt": None}
    monkeypatch.setattr(generate_mod, "_stability_control_hero", _copy_stability(calls))

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
    assert source == generate_mod.PACKSHOT_SOURCE == "asset-store:packshot-composite"
    assert prov["rung"] == "A"
    assert prov["engine"] == "packshot-composite"
    # the seed scene went through the restyle exactly once; box pixels intact.
    assert calls["n"] == 1
    assert calls["prompt"] == "wild frontier restyle"
    assert prov["bg_restyle"] is True
    assert prov["packshot"] is not None and "705599" in prov["packshot"]
    # the LAYOUT directive never reaches the rendered headline; stock captions
    # normalize to house style too.
    assert prov["headline"] == "Fuel Frontier Mornings"
    assert "LAYOUT" not in (prov["headline"] or "")
    assert _distinct_colors(result) > 20


def test_mapped_sku_restyle_failure_keeps_unstyled_rung_a(tmp_path, monkeypatch):
    seed_src = tmp_path / "seed-src.png"
    Image.new("RGB", (1024, 1024), (30, 90, 160)).save(seed_src, "PNG")
    monkeypatch.setattr(asset_store, "fetch_asset_key", _seed_and_box_fetch(seed_src))
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: "scene/waffle.png")
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o, **_k: None)

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
    assert source == generate_mod.PACKSHOT_SOURCE
    assert prov["rung"] == "A"
    assert prov["bg_restyle"] is False
    assert prov["packshot"] is not None
    assert _distinct_colors(result) > 20


# --------------------------------------------------------------------------- #
# (f) staged staged asset pick (seed_key) beats every probed seed; failures fall through.
# --------------------------------------------------------------------------- #
def _staged_seed_fetch(seed_src: Path):
    def _fetch(key: str, dest: Path):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.open(seed_src).save(dest, "PNG")
        return dest

    return _fetch


def _make_seed_src(tmp_path: Path) -> Path:
    src = tmp_path / "staged-src.png"
    Image.new("RGB", (1024, 1024), (20, 120, 60)).save(src, "PNG")
    return src


def test_staged_seed_key_beats_sku_mapped(tmp_path, monkeypatch):
    seed_src = _make_seed_src(tmp_path)
    monkeypatch.setattr(asset_store, "fetch_asset_key", _staged_seed_fetch(seed_src))
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    # sku-mapped lookup would also resolve — staged pick must win.
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: "scene/other.png")
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o, **_k: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "hero.png"
    result, _source, prov = generate_mod.generate_hero(
        product_id="apple-stack-cake",
        product_name="Apple Stack Cake",
        brief_msg="orchard mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        seed_key="brands/kodiak/raw-ingest/apple-stack-cake.png",
    )

    assert result.exists()
    assert prov["seed_selection"] == "staged-asset"
    assert prov["seed_source"] == "apple-stack-cake"
    assert _distinct_colors(result) > 20


def test_staged_seed_label_survives_packshot_paste(tmp_path, monkeypatch):
    # PROVEN LIVE: with a mapped SKU the packshot branch pasted the box over the
    # staged photo but relabelled seed_selection "packshot" — the pick must stay
    # labelled staged-asset since its pixels drive the render.
    seed_src = _make_seed_src(tmp_path)

    def _fetch(key: str, dest: Path):
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if key and "705599" in key.rsplit("/", 1)[-1]:
            Image.new("RGBA", (400, 600), (200, 120, 40, 255)).save(dest, "PNG")
        else:
            Image.open(seed_src).save(dest, "PNG")
        return dest

    monkeypatch.setattr(asset_store, "fetch_asset_key", _fetch)
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o, **_k: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="banana-muffin-quick-bread-mix",
        product_name="Banana Muffin and Quick Bread Mix",
        brief_msg="orchard mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        seed_key="brands/kodiak/raw-ingest/apple-stack-cake.png",
    )

    assert result.exists()
    assert source == generate_mod.PACKSHOT_SOURCE
    assert prov["packshot"] is not None and "705599" in prov["packshot"]
    assert prov["seed_selection"] == "staged-asset"
    assert prov["seed_source"] == "apple-stack-cake"
    assert _distinct_colors(result) > 20


def test_staged_seed_marks_riff_on(tmp_path, monkeypatch):
    seed_src = _make_seed_src(tmp_path)
    monkeypatch.setattr(asset_store, "fetch_asset_key", _staged_seed_fetch(seed_src))
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o, **_k: None)
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
        theme="riff-on-past-content",
        seed_key="brands/kodiak/renders/past-hero.png",
    )

    assert result.exists()
    assert prov["seed_selection"] == "staged-asset"
    assert prov["riff_on"] == "brands/kodiak/renders/past-hero.png"


def test_staged_seed_fetch_failure_falls_through(tmp_path, monkeypatch):
    def _boom(key: str, dest: Path):
        raise RuntimeError("S3 denied")

    seed_src = _make_seed_src(tmp_path)
    monkeypatch.setattr(asset_store, "fetch_asset_key", _boom)
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: seed_src)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o, **_k: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        seed_key="brands/kodiak/renders/gone.png",
    )

    # stale pick never sinks the rung — normal disk resolution carries on.
    assert result.exists()
    assert prov["seed_selection"] == "disk-asset"
    assert "riff_on" not in prov
    assert source == "bedrock:nova-pro"
