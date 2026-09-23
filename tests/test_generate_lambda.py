"""Tests for the brief-to-hero Lambda handler — no real AWS."""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import generate_lambda


class _FakeS3Error(Exception):
    """Module-local stub error so fakes never raise vanilla Exception (TRY002)."""


class _FakeS3:
    """Stub s3 client capturing put_object and returning a canned presigned url."""

    def __init__(self, objects: dict | None = None) -> None:
        self.puts: list[dict] = []
        self.presign_calls: list[dict] = []
        self.objects = objects or {}

    def put_object(self, **kwargs) -> dict:
        self.last_put = kwargs
        self.puts.append(kwargs)
        return {}

    def get_object(self, Bucket, Key) -> dict:
        import io as _io

        if Key not in self.objects:
            raise _FakeS3Error(f"NoSuchKey: {Key}")
        return {"Body": _io.BytesIO(self.objects[Key])}

    def generate_presigned_url(self, op, Params, ExpiresIn) -> str:
        self.last_presign_params = Params
        self.presign_calls.append(Params)
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def _fake_renders(out_dir: Path) -> list[dict]:
    """Build a 4-ratio renders[] list with real tiny PNGs on disk (handler reads bytes)."""
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    dims = {"1x1": (1080, 1080), "4x5": (1080, 1350), "9x16": (1080, 1920), "16x9": (1920, 1080)}
    renders = []
    for ratio, (w, h) in dims.items():
        p = out_dir / f"hero-{ratio}.png"
        Image.new("RGB", (16, 16), (200, 120, 40)).save(p, "PNG")
        renders.append({"ratio": ratio, "path": p, "w": w, "h": h, "engine": "stability-outpaint"})
    return renders


def _stub_hero_set(source: str, tmp_path: Path, provenance: dict | None = None):
    """Return a generate_hero_set stub that yields 4 fake renders + source + provenance."""

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
            "ratios": {"1x1": "primary", "4x5": "pillow-outpaint-fallback", "9x16": "pillow-outpaint-fallback", "16x9": "pillow-outpaint-fallback"},
        }
        return _fake_renders(Path(out_dir)), source, prov

    return _stub


def test_handler_returns_200_with_image_url(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        generate_lambda, "generate_hero_set", _stub_hero_set("bedrock:nova-pro", tmp_path)
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {"body": json.dumps({"mode": "full", "prompt": "a bear eating pancakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["image_url"].startswith("https://presigned.example/")
    assert body["source"] == "bedrock:nova-pro"
    assert body["prompt"] == "a bear eating pancakes"
    # PART B — four renders delivered from one call, 1x1 first, correct dims.
    assert [r["ratio"] for r in body["renders"]] == ["1x1", "4x5", "9x16", "16x9"]
    dims = {r["ratio"]: (r["w"], r["h"]) for r in body["renders"]}
    assert dims == {"1x1": (1080, 1080), "4x5": (1080, 1350), "9x16": (1080, 1920), "16x9": (1920, 1080)}
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

    # missing prompt entirely (full mode exercises the stubbed generate_hero_set source)
    resp = generate_lambda.handler({"body": json.dumps({"mode": "full"})}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["image_url"].startswith("https://presigned.example/")
    assert body["source"] == "bedrock:nova-pro"
    assert body["prompt"] == "KODIAK - Nourishment for Today's Frontier. Keep It Wild."

    # empty/whitespace prompt
    resp = generate_lambda.handler({"body": json.dumps({"mode": "full", "prompt": "   "})}, None)
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

    resp = generate_lambda.handler({"mode": "full", "prompt": "x"}, None)
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
                "mode": "full",
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

    event = {"body": json.dumps({"mode": "full", "product": "power-cakes", "region": "us"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200

    # all three renders were uploaded + presigned with an attachment .png disposition
    assert len(fake_s3.presign_calls) == 4
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



# --------------------------------------------------------------------------- #
# preview vs full mode (emergency fix: API Gateway hard 30s timeout)
#
# The interactive /generate call is fronted by API Gateway with a HARD 30s integration
# timeout. The full generate_hero_set chain (control-structure hero + 2 serial outpaint
# extends + 3 localization rewrites + platform copy) runs ~35s and trips a 503, so the
# frontend falls back to the local Pillow placeholder. PREVIEW mode (the new default)
# returns the ONE 1x1 control-structure hero plus four server-side derived tiles
# (4x5, 9x16, 16x9, blog) — one model call for the hero, 9x16/16x9 attempt ONE live
# outpaint extend each behind the preview budget gate (item 11) with Pillow pads as
# the fallback, no live localization, well under 30s. FULL mode preserves the
# composed set for the async download-pack builder.
# --------------------------------------------------------------------------- #


def _fake_single_render(out_path: Path):
    """Write a real tiny PNG at out_path (the handler reads bytes + size from it)."""
    from PIL import Image

    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), (200, 120, 40)).save(out_path, "PNG")
    return out_path


def _stub_generate_hero(source: str, provenance: dict | None = None):
    """generate_hero stub: writes the requested out_path and returns (path, source, provenance)."""

    def _stub(**kwargs):
        out_path = Path(kwargs["out_path"])
        _fake_single_render(out_path)
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
        }
        return out_path, source, dict(prov)

    return _stub


def test_preview_mode_is_default_five_tiles_gated_outpaint_pads_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    # default (no "mode") is preview: FIVE renders (the 1x1 hero + four server-side
    # derived tiles: 4x5, 9x16, 16x9, blog), top-level image_url set, source +
    # provenance present. 9x16/16x9 attempt ONE live outpaint extend each behind the
    # preview budget gate (item 11) — here the extend helper reports unavailable,
    # so both tiles ship their Pillow pads with honest degrade reasons — while the
    # LIVE localization rewrite chain is never invoked (those rows come from the
    # offline chain). The spy patches generate_lambda's own outpaint binding (the
    # name _handle_preview actually calls), not generate's module attribute.
    monkeypatch.setattr(
        generate_lambda, "generate_hero", _stub_generate_hero("bedrock:stability-control-structure")
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    # the outpaint gate runs on the preview path (item 11): the instant stub hero
    # leaves budget, so both extends are attempted and degrade honestly when the
    # helper reports unavailable — pads stay the fallback, never an error.
    outpaint_calls: list = []

    def _unavailable(*a, **k):
        outpaint_calls.append(a)
        return None

    monkeypatch.setattr(generate_lambda, "_stability_outpaint", _unavailable)
    # spy the localization seam — it must NOT be called on the sync preview path
    localize_calls: list = []
    monkeypatch.setattr(
        generate_lambda, "_build_localizations", lambda *a, **k: localize_calls.append(a) or ([], [])
    )

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    assert body["ok"] is True
    assert body["mode"] == "preview"
    # five tiles: the 1x1 primary first, then the server-side pillow pads
    assert [r["ratio"] for r in body["renders"]] == ["1x1", "4x5", "9x16", "16x9", "blog"]
    # pad dims match the platform-matrix export table (blog is the 1200x630 OG hero);
    # the 1x1 keeps the hero's native size (the stub writes 16x16, prod 1080x1080)
    from creative_automation.platforms import RATIO_DIMS

    for r in body["renders"]:
        if r["ratio"] != "1x1":
            assert (r["w"], r["h"]) == RATIO_DIMS[r["ratio"]]
        assert r["image_url"].startswith("https://presigned.example/")
        assert r["s3_uri"].startswith("s3://")
    # top-level image_url set and == the 1x1 primary url (front-end back-compat)
    assert body["image_url"].startswith("https://presigned.example/")
    assert body["image_url"] == body["renders"][0]["image_url"]
    assert body["s3_uri"] == body["renders"][0]["s3_uri"]
    # real GenAI source preserved, provenance present + flagged preview
    assert body["source"] == "bedrock:stability-control-structure"
    assert body["provenance"]["engine"] == "stability-control-structure"
    assert body["provenance"]["ratios"] == {
        "1x1": "primary",
        "4x5": "pillow-outpaint-fallback",
        "9x16": "pillow-outpaint-fallback",
        "16x9": "pillow-outpaint-fallback",
        "blog": "pillow-outpaint-fallback",
    }
    # nothing deferred anymore: the preview ships every tile; 9x16/16x9 attempted
    # the live extend behind the gate and fell back to pads on unavailability.
    assert "deferred" not in body["provenance"]
    assert body["provenance"]["mode"] == "preview"
    # Atlanta D/E/H: deterministic campaign messaging ships IN the preview —
    # full platform copy + top-3 localizations + recipe tease (offline chain,
    # zero model calls) alongside all five tiles.
    assert [loc["lang_code"] for loc in body["localizations"]] == ["en", "es", "pt"]
    from creative_automation.platform_copy import PUBLISH_TARGETS
    assert set(body["platform_copy"].keys()) == set(PUBLISH_TARGETS)
    assert body["provenance"]["copy_owner"] == "backend-preview-fallback"
    assert body["retailer"] is None
    assert body["recipe_fields"]["title"]
    assert "recipe.title" in body["copy_sidecar"]["csv"]
    # the gate was exercised, not skipped: both extends attempted exactly once,
    # both degraded honestly to pads with per-ratio measurement recorded; the
    # LIVE localization chain never ran (preview rows come from the offline chain).
    assert len(outpaint_calls) == 2
    assert body["provenance"]["outpaint_degraded"] == {
        "9x16": "outpaint-unavailable",
        "16x9": "outpaint-unavailable",
    }
    assert set(body["provenance"]["outpaint_latency_ms"]) == {"9x16", "16x9"}
    assert set(body["provenance"]["outpaint_remaining_ms"]) == {"9x16", "16x9"}
    assert localize_calls == []


def test_preview_pads_upload_real_pngs_at_matrix_dims(monkeypatch, tmp_path: Path) -> None:
    # Independent pixel oracle: decode the actual bytes the handler PUT to S3 and
    # assert each tile's real dims equal the platform-matrix export table. The
    # handler's w/h claims are not trusted here — PIL re-opens the uploaded bytes.
    import io

    from PIL import Image

    from creative_automation.platforms import RATIO_DIMS

    monkeypatch.setattr(
        generate_lambda, "generate_hero", _stub_generate_hero("bedrock:stability-control-structure")
    )
    fake_s3 = _FakeS3()
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: fake_s3)

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200

    assert len(fake_s3.puts) == 5
    keys = [p["Key"] for p in fake_s3.puts]
    assert len(set(keys)) == 5  # every tile persists under its own asset key
    for put in fake_s3.puts:
        assert put["ContentType"] == "image/png"
        with Image.open(io.BytesIO(put["Body"])) as im:
            real_w, real_h = im.size
    body = json.loads(resp["body"])
    by_ratio = {r["ratio"]: r for r in body["renders"]}
    assert set(by_ratio) == set(RATIO_DIMS)
    # each response entry's claimed dims match the uploaded bytes; pads match the
    # matrix (the stubbed 1x1 is 16x16 native, prod 1080x1080)
    png_by_size = sorted(Image.open(io.BytesIO(p["Body"])).size for p in fake_s3.puts)
    claimed = sorted((r["w"], r["h"]) for r in body["renders"])
    assert png_by_size == claimed
    for ratio, dims in RATIO_DIMS.items():
        if ratio == "1x1":
            continue
        assert (by_ratio[ratio]["w"], by_ratio[ratio]["h"]) == dims


def test_preview_mode_sanitizes_celebrity_name_before_brief_msg(monkeypatch, tmp_path: Path) -> None:
    # the celebrity sanitizer must still run on the preview path: the raw name must not
    # reach generate_hero as brief_msg (it drives the Stability/Nova prompt).
    captured: dict = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        _fake_single_render(Path(kwargs["out_path"]))
        return Path(kwargs["out_path"]), "bedrock:stability-control-structure", {"engine": "x"}

    monkeypatch.setattr(generate_lambda, "generate_hero", _capture)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {
        "body": json.dumps(
            {"prompt": "Zac Efron morning energy. Keep It Wild.", "theme": "zac-efron"}
        )
    }
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    brief_msg = captured["brief_msg"]
    assert "zac" not in brief_msg.lower()
    assert "efron" not in brief_msg.lower()
    assert "Keep It Wild." in brief_msg


def test_full_mode_still_produces_3size_set_localization_platform_copy(
    monkeypatch, tmp_path: Path
) -> None:
    # mode="full" preserves the complete async-pack behavior: the 3-size set, the
    # localizations[] block, and per-platform copy.
    monkeypatch.setattr(
        generate_lambda, "generate_hero_set", _stub_hero_set("bedrock:stability-control-structure", tmp_path)
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {"body": json.dumps({"mode": "full", "prompt": "a bear eating pancakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])

    assert body["mode"] == "full"
    # four renders from one call, 1x1 first
    assert [r["ratio"] for r in body["renders"]] == ["1x1", "4x5", "9x16", "16x9"]
    # Atlanta H: the pack ships true campaign messaging — deterministic fallback
    # copy + localizations + recipe + retailer in the response AND the sidecars
    # (live rewrites would cost ~8-10s against the wall, so they stay frontend).
    assert [loc["lang_code"] for loc in body["localizations"]] == ["en", "es", "pt"]
    from creative_automation.platform_copy import PUBLISH_TARGETS
    assert set(body["platform_copy"].keys()) == set(PUBLISH_TARGETS)
    assert body["provenance"]["copy_owner"] == "backend-pack-fallback"
    assert "retailer" in body["copy_sidecar"]["csv"] or "retailer_framing" in body["copy_sidecar"]["csv"] \
        or "recipe.title" in body["copy_sidecar"]["csv"]



# --------------------------------------------------------------------------- #
# OUTER-DEADLINE WALL (#118): a structural guarantee that no internal stall can
# push the handler past the API Gateway 30s edge. When the generate ladder hangs
# past GENERATE_WALL_TIMEOUT_S, the handler thread composites the zero-I/O rung-D
# brand floor and returns 200 real pixels — never a 503, never an exception.
# --------------------------------------------------------------------------- #


def test_wall_fires_returns_200_rungD_wall_timeout_real_pixels(monkeypatch, tmp_path: Path) -> None:
    # simulate the generate work HANGING past the wall: the submitted callable sleeps
    # well beyond GENERATE_WALL_TIMEOUT_S. The handler must NOT wait it out, NOT raise,
    # NOT 503 — it returns 200 with rung=D wall-timeout REAL pixels from _brand_floor.
    import time as _time

    # shrink the wall so the test is fast; behavior is identical at the 22s default
    monkeypatch.setattr(generate_lambda, "GENERATE_WALL_TIMEOUT_S", 0.3)

    def _hang(**kwargs):
        _time.sleep(30)  # far past the wall — this thread is abandoned
        raise AssertionError("wall did not abandon the hung worker")

    # both mode paths call through generate_hero / generate_hero_set; stub both to hang
    monkeypatch.setattr(generate_lambda, "generate_hero", _hang)
    monkeypatch.setattr(generate_lambda, "generate_hero_set", _hang)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)

    assert resp["statusCode"] == 200  # NOT 503, NOT 500
    body = json.loads(resp["body"])
    assert body["ok"] is True
    # real pixels persisted + presigned (the floor put ran)
    assert body["image_url"].startswith("https://presigned.example/")
    assert body["renders"][0]["ratio"] == "1x1"
    assert body["renders"][0]["w"] > 0 and body["renders"][0]["h"] > 0
    # rung-D wall-timeout provenance
    assert body["provenance"]["rung"] == "D"
    assert body["provenance"]["fallthrough_reason"] == "wall-timeout"
    assert body["source"] == "brand-floor:wall-timeout"
    assert "mock" not in body["source"]


def test_wall_does_not_fire_when_work_completes_in_time(monkeypatch, tmp_path: Path) -> None:
    # the wall is last-resort ONLY: when the ladder returns inside the wall, the normal
    # preview payload flows through untouched (no rung-D fallthrough).
    monkeypatch.setattr(
        generate_lambda, "generate_hero", _stub_generate_hero("bedrock:stability-control-structure")
    )
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["source"] == "bedrock:stability-control-structure"
    # normal preview provenance — NOT the wall-timeout floor
    assert body["provenance"].get("fallthrough_reason") != "wall-timeout"



# --------------------------------------------------------------------------- #
# ART-DIRECTOR INNER TIMEOUT (T1): the art-director voice step (dark by default)
# is bounded on its own inner timeout well inside the outer wall. A cold/scale-to-
# zero model whose 4x28s retry loop blocks must degrade VOICE-OFF (original prompt),
# NOT to the rung-D wall floor. The prompt that reaches generate_hero as brief_msg
# is the observable — voice-off means brief_msg == the original input.
# --------------------------------------------------------------------------- #


def _capture_hero(captured: dict, source: str = "bedrock:stability-control-structure"):
    """generate_hero stub that captures kwargs (brief_msg) and writes a real tiny PNG."""

    def _stub(**kwargs):
        captured.update(kwargs)
        _fake_single_render(Path(kwargs["out_path"]))
        return Path(kwargs["out_path"]), source, {"engine": "stability-control-structure"}

    return _stub


def test_art_director_inner_timeout_degrades_voice_off_not_wall_floor(
    monkeypatch, tmp_path: Path
) -> None:
    # art-director ENABLED + the invoke hangs past the inner timeout: the response is a
    # NORMAL hero (source is NOT brand-floor:wall-timeout) and the prompt used equals the
    # ORIGINAL input (voice-off fallback) — the inner timeout must fire long before the
    # outer wall, so hero composition still runs.
    import time as _time

    captured: dict = {}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    # turn the voice step on and shrink the inner timeout so the test is fast; behavior is
    # identical at the 6s default. The outer wall stays at its default so we prove the INNER
    # bound fires (not the wall).
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_TIMEOUT_S", 0.3)

    def _hang_art_direct(prompt, voice):
        _time.sleep(30)  # far past the inner timeout — this worker is abandoned
        raise AssertionError("inner timeout did not abandon the hung art-director invoke")

    from creative_automation import art_director as _ad

    monkeypatch.setattr(_ad, "art_direct", _hang_art_direct)

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    # voice-off degrade, NOT the rung-D wall floor
    assert body["source"] != "brand-floor:wall-timeout"
    assert body["provenance"].get("fallthrough_reason") != "wall-timeout"
    # the prompt that reached hero composition is the ORIGINAL input (voice-off)
    assert captured["brief_msg"] == "a bear eating pancakes"
    assert body["prompt"] == "a bear eating pancakes"


def test_art_director_flag_off_by_default_never_invokes(monkeypatch, tmp_path: Path) -> None:
    # default (flag off): the art-director path is not taken — art_direct is never called
    # and the prompt flows through byte-for-byte as the brief_msg.
    captured: dict = {}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    # do NOT set ART_DIRECTOR_ENABLED — assert it is off by default in this env
    assert generate_lambda.ART_DIRECTOR_ENABLED is False

    from creative_automation import art_director as _ad

    calls: list = []
    monkeypatch.setattr(_ad, "art_direct", lambda *a, **k: calls.append(a) or {"text": "brand line"})

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    # art-director was never invoked and the original prompt passed through unchanged
    assert calls == []
    assert captured["brief_msg"] == "a bear eating pancakes"
    assert body["prompt"] == "a bear eating pancakes"


def test_art_director_flag_on_fast_return_uses_art_director_line(
    monkeypatch, tmp_path: Path
) -> None:
    # art-director ENABLED + a fast return: pixels still compose from the ORIGINAL
    # brief (post-render upgrade, Unit 1) while the voice line lands in provenance.
    captured: dict = {}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)

    from creative_automation import art_director as _ad

    monkeypatch.setattr(
        _ad, "art_direct", lambda prompt, voice: {"text": "Keep It Wild — Frontier Fuel"}
    )

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    # pixels compose from the original brief; the voice line upgrades provenance
    assert captured["brief_msg"] == "a bear eating pancakes"
    assert body["prompt"] == "a bear eating pancakes"
    assert body["provenance"].get("art_headline") == "Keep It Wild — Frontier Fuel"



# --------------------------------------------------------------------------- #
# PUBLISH-TIME PLATFORM TAGS: renders ship x-amz-meta-platforms so the asset store
# browser can filter by platform. No real AWS — _FakeS3 captures put_object.
# --------------------------------------------------------------------------- #


def _tiny_render(tmp_path: Path) -> dict:
    from PIL import Image

    p = tmp_path / "hero-1x1.png"
    Image.new("RGB", (16, 16), (200, 120, 40)).save(p, "PNG")
    return {"ratio": "1x1", "path": p, "w": 1080, "h": 1080}


def test_upload_render_writes_platform_metadata(tmp_path: Path) -> None:
    s3 = _FakeS3()
    entry = generate_lambda._upload_render(
        s3, _tiny_render(tmp_path), "KODIAK-CAKES-X.png", ["facebook", "Insta", "x"]
    )
    put = s3.last_put
    assert put["Metadata"] == {"platforms": "facebook,instagram,x"}
    assert entry["platforms"] == ["facebook", "instagram", "x"]
    assert put["Key"].startswith("brands/kodiak/renders/")
    assert put["ContentType"] == "image/png"


def test_upload_render_omits_metadata_when_untagged(tmp_path: Path) -> None:
    s3 = _FakeS3()
    entry = generate_lambda._upload_render(s3, _tiny_render(tmp_path), "KODIAK-CAKES-X.png")
    assert "Metadata" not in s3.last_put
    assert entry["platforms"] == []


def test_normalize_platform_tags_dedupes_and_drops_junk() -> None:
    norm = generate_lambda._normalize_platform_tags
    assert norm(["Facebook", "facebook", "insta", "blog"]) == ["facebook", "instagram", "blog"]
    assert norm(None) == []
    assert norm([]) == []
    # S3-unsafe values can never corrupt object metadata
    assert norm(["ok-tag", "has space", "semi;colon", "", "x" * 33]) == ["ok-tag"]


# ----------------------------------------------- #204 ISO asset-pack zip
def _pack_event(payload: dict) -> dict:
    return {"rawPath": "/assets/pack", "body": json.dumps(payload)}


def _pack_s3() -> _FakeS3:
    return _FakeS3(objects={
        "brands/kodiak/renders/a1.png": b"PNG-A",
        "brands/kodiak/renders/b2.png": b"PNG-B",
    })


def _pack_body(monkeypatch, payload: dict) -> dict:
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _pack_s3())
    resp = generate_lambda.handler(_pack_event(payload), None)
    return resp, json.loads(resp["body"])


def test_pack_zips_renders_with_iso_names(monkeypatch) -> None:
    import io as _io
    import zipfile as _zf

    s3 = _pack_s3()
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: s3)
    resp = generate_lambda.handler(_pack_event({
        "files": [
            {"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/brands/kodiak/renders/a1.png", "ratio": "1x1"},
            {"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/brands/kodiak/renders/b2.png", "ratio": "9x16"},
        ],
        "product": "blueberry-muffin-mix",
        "region": "US-UT",
        "locality": "park-city-84098",
        "channel": "retailers",
    }), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True and body["count"] == 2
    assert body["zip_name"].startswith(
        "KODIAK-CAKES-blueberry-muffin-mix-US-UT-park-city-84098-retailers-multi-"
    ) and body["zip_name"].endswith("-v01.zip")
    assert body["s3_uri"].endswith(f"brands/kodiak/packs/{body['zip_name']}")
    assert body["zip_url"].startswith("https://presigned.example/")
    put = s3.last_put
    assert put["ContentType"] == "application/zip"
    with _zf.ZipFile(_io.BytesIO(put["Body"])) as zf:
        assert sorted(zf.namelist()) == sorted(body["files"])
        assert zf.read(body["files"][0]) == b"PNG-A"
    # presign carries attachment disposition so the browser saves the ISO name
    assert body["zip_name"] in s3.last_presign_params["ResponseContentDisposition"]


def test_pack_rejects_non_render_keys(monkeypatch) -> None:
    resp, body = _pack_body(monkeypatch, {"files": [
        {"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/brands/kodiak/tokens/secret.json", "ratio": "1x1"},
    ]})
    assert resp["statusCode"] == 400
    assert body["ok"] is False


def test_pack_rejects_foreign_bucket(monkeypatch) -> None:
    resp, body = _pack_body(monkeypatch, {"files": [
        {"s3_uri": "s3://someone-else/evil.png", "ratio": "1x1"},
    ]})
    assert resp["statusCode"] == 400
    assert body["ok"] is False


def test_pack_missing_member_is_400_not_partial(monkeypatch) -> None:
    resp, body = _pack_body(monkeypatch, {"files": [
        {"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/brands/kodiak/renders/nope.png", "ratio": "1x1"},
    ]})
    assert resp["statusCode"] == 400
    assert "nope.png" in body["error"]


def test_pack_requires_files(monkeypatch) -> None:
    resp, body = _pack_body(monkeypatch, {"product": "x"})
    assert resp["statusCode"] == 400
    assert body["ok"] is False


def test_pack_includes_text_extras(monkeypatch) -> None:
    import io as _io
    import zipfile as _zf

    s3 = _pack_s3()
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: s3)
    resp = generate_lambda.handler(_pack_event({
        "files": [
            {"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/brands/kodiak/renders/a1.png", "ratio": "1x1"},
        ],
        "extras": [
            {"name": "copy.txt", "text": "Keep It Wild"},
            {"name": "copy.csv", "text": "ratio,headline\n1x1,Keep It Wild\n"},
        ],
        "product": "blueberry-muffin-mix",
    }), None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["count"] == 3
    with _zf.ZipFile(_io.BytesIO(s3.last_put["Body"])) as zf:
        assert zf.read("blueberry-muffin-mix-copy.txt") == b"Keep It Wild"


def test_pack_rejects_bad_extra_name(monkeypatch) -> None:
    resp, body = _pack_body(monkeypatch, {"files": [
        {"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/brands/kodiak/renders/a1.png", "ratio": "1x1"},
    ], "extras": [{"name": "../evil.sh", "text": "x"}]})
    assert resp["statusCode"] == 400
    assert body["ok"] is False


def test_pack_rejects_oversize_extra(monkeypatch) -> None:
    resp, body = _pack_body(monkeypatch, {"files": [
        {"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/brands/kodiak/renders/a1.png", "ratio": "1x1"},
    ], "extras": [{"name": "big.txt", "text": "x" * 70000}]})
    assert resp["statusCode"] == 400
    assert body["ok"] is False


def test_art_upgrade_records_headline_post_render_without_rewriting_brief(
    monkeypatch, tmp_path: Path
) -> None:
    # voice ENABLED + real line: the brief driving pixels stays ORIGINAL, and the
    # voice line lands in provenance + sidecar (post-render upgrade, never gating).
    captured: dict = {}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)

    from creative_automation import art_director as _ad

    monkeypatch.setattr(
        _ad, "art_direct",
        lambda *a, **k: {"text": "Lace up. Keep it wild.", "source": "bedrock:kodiak-artdirector"},
    )

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert captured["brief_msg"] == "a bear eating pancakes"
    assert body["prompt"] == "a bear eating pancakes"
    assert body["provenance"].get("art_headline") == "Lace up. Keep it wild."
    assert "art-director voice: Lace up. Keep it wild." in body["copy_sidecar"]["txt"]


def test_art_upgrade_records_nothing_when_voice_off(monkeypatch, tmp_path: Path) -> None:
    # flag off: no art_headline key at all, brief byte-identical.
    captured: dict = {}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    assert generate_lambda.ART_DIRECTOR_ENABLED is False

    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert "art_headline" not in body["provenance"]
    assert "art-director voice:" not in body["copy_sidecar"]["txt"]


def test_warm_ping_never_touches_ladder(monkeypatch) -> None:
    # {"warm": "art-director"} short-circuits before body validation/ladder.
    def _boom(*a, **k):
        raise AssertionError("ladder must not run on a warm ping")

    monkeypatch.setattr(generate_lambda, "generate_hero", _boom)
    monkeypatch.setattr(generate_lambda, "generate_hero_set", _boom)

    event = {"body": json.dumps({"warm": "art-director"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["warmed"] is False  # voice flag off in this env — nothing to warm
    assert body["reason"] == "voice-off"


def test_warm_ping_reports_live_voice(monkeypatch) -> None:
    # flag on + live voice source: warmed True.
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    from creative_automation import art_director as _ad

    monkeypatch.setattr(
        _ad, "art_direct",
        lambda *a, **k: {"text": "Lace up.", "source": "bedrock:kodiak-artdirector"},
    )
    event = {"body": json.dumps({"warm": "art-director"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["warmed"] is True


# --------------------------------------------------------------------------- #
# Concurrent voice (wall repair): _kick_voice overlaps hero composition, and
# _apply_art_upgrade_future collects with a short grace wait. A slow voice can
# never gate the render and finished pixels are never discarded for a headline.
# --------------------------------------------------------------------------- #

def test_kick_voice_dark_resolves_prompt_instantly() -> None:
    import concurrent.futures as _fut

    assert generate_lambda.ART_DIRECTOR_ENABLED is False
    fut = generate_lambda._kick_voice({"product": "power-cakes"}, "wild mornings")
    assert isinstance(fut, _fut.Future)
    assert fut.result(timeout=5) == "wild mornings"


def test_apply_future_records_real_headline() -> None:
    import concurrent.futures as _fut

    fut = _fut.Future()
    fut.set_result("Lace up for the Wasatch dawn")
    prov: dict = {}
    generate_lambda._apply_art_upgrade_future(fut, {}, "wild mornings", prov)
    assert prov.get("art_headline") == "Lace up for the Wasatch dawn"


def test_apply_future_fallback_text_records_nothing() -> None:
    import concurrent.futures as _fut

    fut = _fut.Future()
    fut.set_result("wild mornings")  # voice-off: same as the prompt
    prov: dict = {}
    generate_lambda._apply_art_upgrade_future(fut, {}, "wild mornings", prov)
    assert "art_headline" not in prov


def test_apply_future_slow_voice_returns_instantly_without_raise() -> None:
    import concurrent.futures as _fut
    import time as _time

    pool = _fut.ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(_time.sleep, 30)  # cold-model worker, abandoned
        prov: dict = {}
        start = _time.monotonic()
        generate_lambda._apply_art_upgrade_future(fut, {}, "wild mornings", prov, timeout_s=0.2)
        assert _time.monotonic() - start < 5
        assert "art_headline" not in prov
    finally:
        pool.shutdown(wait=False)


def test_apply_future_none_and_nondict_never_raise() -> None:
    import concurrent.futures as _fut

    fut = _fut.Future()
    fut.set_result("Lace up.")
    generate_lambda._apply_art_upgrade_future(None, {}, "p", {})
    generate_lambda._apply_art_upgrade_future(fut, {}, "p", None)
    generate_lambda._apply_art_upgrade_future(fut, {}, "p", "not-a-dict")


def test_concurrent_voice_hang_costs_no_wall(monkeypatch, tmp_path: Path) -> None:
    # Discriminating test for the repair: hanging voice + instant hero must
    # return a NORMAL hero in ~collect-grace time, not inner-timeout + pixels.
    # Serial order at the 6s default would take 6s+; concurrent takes ~2s.
    import time as _time

    captured: dict = {}
    monkeypatch.setattr(generate_lambda, "generate_hero", _capture_hero(captured))
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    assert generate_lambda.ART_DIRECTOR_TIMEOUT_S == 6  # default, not squeezed

    def _hang_art_direct(prompt, voice):
        _time.sleep(7)  # past the 6s inner bound — worker abandoned, harmless
        return {"text": "too late", "source": "bedrock:kodiak-artdirector"}

    from creative_automation import art_director as _ad

    monkeypatch.setattr(_ad, "art_direct", _hang_art_direct)

    start = _time.monotonic()
    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    elapsed = _time.monotonic() - start
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["source"] != "brand-floor:wall-timeout"
    assert captured["brief_msg"] == "a bear eating pancakes"  # voice-off pixels
    assert elapsed < 5, f"voice gated the render — {elapsed:.1f}s (want ~2s collect grace)"
