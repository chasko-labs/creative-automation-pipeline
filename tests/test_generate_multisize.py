"""Multi-size delivery, provenance transparency, brand + kraft overlays — no real AWS.

Covers PART A (provenance object shape + JSON-serializable), PART B (three delivery
ratios from one generate_hero_set call with correct dims + outpaint/fallback engines),
PART C (_apply_brand_overlay draws over an existing background without resizing), and
PART D (_kraft_texture determinism + _apply_paper_overlay ~2% same-size, near-identical).
All Bedrock calls are monkeypatched — nothing hits AWS.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from creative_automation import generate


def _png_bytes(size: tuple[int, int] = (1080, 1080), color=(180, 90, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _make_seed(path: Path, size: tuple[int, int] = (1080, 1080)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_bytes(size))
    return path


# --------------------------------------------------------------- PART A: provenance
def test_provenance_shape_and_json_serializable(tmp_path: Path, monkeypatch) -> None:
    # a stability run yields a provenance dict with every required key, all values
    # JSON-serializable (no Path objects).
    seed = _make_seed(tmp_path / "seed.png")
    canned = base64.b64encode(_png_bytes(color=(10, 200, 120))).decode("ascii")

    class _Fake:
        def invoke_model(self, **kwargs):
            payload = json.dumps({"images": [canned]}).encode("utf-8")
            return {"body": io.BytesIO(payload)}

        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": "Keep It Wild\nLAYOUT: center"}]}}}

    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: _Fake())

    out = tmp_path / "hero.png"
    _result, source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings on the frontier",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert source == generate.STABILITY_SOURCE
    required = {
        "seed_source",
        "seed_selection",
        "engine",
        "scene_prompt",
        "control_strength",
        "model",
        "incoming_prompt",
        "headline",
        "overlay_applied",
        "paper_overlay",
    }
    assert required.issubset(prov.keys())
    assert prov["seed_selection"] == "disk-asset"
    assert prov["seed_source"] == "seed"  # readable label (stem), not a /tmp path
    assert prov["engine"] == "stability-control-structure"
    assert prov["control_strength"] == generate.STABILITY_CONTROL_STRENGTH
    assert prov["model"] == generate.STABILITY_CONTROL_MODEL
    assert prov["incoming_prompt"] == "wild mornings on the frontier"
    assert prov["overlay_applied"] is True
    assert prov["paper_overlay"] is True
    # fully JSON-serializable — no Path objects leaked in
    json.dumps(prov)


def test_provenance_pillow_path_records_headline_and_engine(tmp_path: Path, monkeypatch) -> None:
    # Stability unavailable -> pillow-compose engine; headline recorded, control_strength
    # stays None (only set on the stability path).
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate, "_stability_control_hero", lambda s, p, o: None)
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: "Trail Fuel\nLAYOUT: left")

    out = tmp_path / "hero.png"
    _result, source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild",
        region="us",
        audience="families",
        out_path=out,
    )
    assert source == "bedrock:nova-pro"
    assert prov["engine"] == "pillow-compose"
    assert prov["control_strength"] is None
    assert prov["headline"] == "Trail Fuel"
    json.dumps(prov)


# --------------------------------------------------------------- PART B: three sizes
def test_generate_hero_set_three_ratios_via_outpaint(tmp_path: Path, monkeypatch) -> None:
    # one control-structure hero + two outpaint extends -> 3 renders with correct dims.
    seed = _make_seed(tmp_path / "seed.png")
    hero_b64 = base64.b64encode(_png_bytes((1080, 1080), color=(30, 60, 200))).decode("ascii")

    invoked: list[str] = []

    class _Fake:
        def invoke_model(self, **kwargs):
            invoked.append(kwargs["modelId"])
            # both control-structure and outpaint return a single base64 image
            payload = json.dumps({"images": [hero_b64]}).encode("utf-8")
            return {"body": io.BytesIO(payload)}

        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": "Keep It Wild\nLAYOUT: center"}]}}}

    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: _Fake())

    renders, source, prov = generate.generate_hero_set(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_dir=tmp_path / "set",
    )
    assert source == generate.STABILITY_SOURCE
    assert [r["ratio"] for r in renders] == ["1x1", "4x5", "2x3"]
    dims = {r["ratio"]: (r["w"], r["h"]) for r in renders}
    assert dims == {"1x1": (1080, 1080), "4x5": (1080, 1350), "2x3": (1000, 1500)}
    for r in renders:
        assert r["path"].exists()
        with Image.open(r["path"]) as im:
            assert im.size == (r["w"], r["h"])
    # one control-structure call + two outpaint calls were made
    assert generate.STABILITY_CONTROL_MODEL in invoked
    assert invoked.count(generate.STABILITY_OUTPAINT_MODEL) == 2
    # provenance notes which ratios came from outpaint
    assert prov["ratios"]["4x5"] == "stability-outpaint"
    assert prov["ratios"]["2x3"] == "stability-outpaint"
    json.dumps(prov)


def test_generate_hero_set_pillow_outpaint_fallback(tmp_path: Path, monkeypatch) -> None:
    # outpaint unavailable (helper -> None) -> the taller ratios cover-pad from the 1x1
    # primary and provenance marks the engine "pillow-outpaint-fallback".
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    # primary hero via stability succeeds; outpaint fails -> pillow fallback
    def _fake_control(seed_path, prompt, out):
        out.write_bytes(_png_bytes())
        return out

    monkeypatch.setattr(generate, "_stability_control_hero", _fake_control)
    monkeypatch.setattr(generate, "_stability_outpaint", lambda *a, **k: None)
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)

    renders, _source, prov = generate.generate_hero_set(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild",
        region="us",
        audience="families",
        out_dir=tmp_path / "set",
    )
    dims = {r["ratio"]: (r["w"], r["h"]) for r in renders}
    assert dims == {"1x1": (1080, 1080), "4x5": (1080, 1350), "2x3": (1000, 1500)}
    assert prov["ratios"]["4x5"] == "pillow-outpaint-fallback"
    assert prov["ratios"]["2x3"] == "pillow-outpaint-fallback"


# --------------------------------------------------------------- PART C: brand overlay
def test_apply_brand_overlay_draws_without_resizing(tmp_path: Path) -> None:
    # brand overlay draws the message bar + accent bar over an existing background and
    # returns an image the SAME size as the input (no resize).
    bg = tmp_path / "bg.png"
    Image.new("RGB", (800, 1000), (40, 80, 120)).save(bg, "PNG")
    out = tmp_path / "branded.png"
    result = generate._apply_brand_overlay(bg, "Wild Protein Mornings", "4x5", out)
    assert result.exists()
    with Image.open(result) as img:
        assert img.size == (800, 1000)  # unchanged from the background
        # the Blaze Orange accent bar is present along the very bottom row
        accent = generate._hex_to_rgb(generate._accent_hex)
        bottom = img.convert("RGB").getpixel((400, 999))
        assert abs(bottom[0] - accent[0]) < 30
        assert abs(bottom[1] - accent[1]) < 30


# --------------------------------------------------------------- PART D: kraft texture
def test_kraft_texture_deterministic() -> None:
    # same (w, h) -> byte-identical output (fixed seed), so it is reproducible/testable.
    a = generate._kraft_texture(128, 96)
    b = generate._kraft_texture(128, 96)
    assert a.size == (128, 96)
    buf_a, buf_b = io.BytesIO(), io.BytesIO()
    a.save(buf_a, "PNG")
    b.save(buf_b, "PNG")
    assert buf_a.getvalue() == buf_b.getvalue()


def test_apply_paper_overlay_same_size_and_subtle() -> None:
    # the overlay returns an image the same size as input, and at ~2% opacity the mean
    # per-pixel delta is small — proving "very slight, like 2% visible", not a heavy wash.
    base = Image.new("RGB", (200, 200), (128, 128, 128))
    out = generate._apply_paper_overlay(base, opacity=0.02)
    assert out.size == base.size
    # mean absolute delta across all channels
    bp = list(base.getdata())
    op = list(out.getdata())
    total = 0
    for (br, bg, bb), (orr, og, ob) in zip(bp, op):
        total += abs(br - orr) + abs(bg - og) + abs(bb - ob)
    mean_delta = total / (len(bp) * 3)
    # at 2% blend against a ~#C8A97E kraft base the shift is a few luminance levels, not tens
    assert mean_delta < 6.0


def test_apply_paper_overlay_heavier_opacity_shifts_more() -> None:
    # sanity: a heavier opacity moves pixels further than the ~2% default, confirming the
    # opacity knob actually controls visibility.
    base = Image.new("RGB", (100, 100), (128, 128, 128))
    light = generate._apply_paper_overlay(base, opacity=0.02)
    heavy = generate._apply_paper_overlay(base, opacity=0.30)

    def _mean_delta(a: Image.Image) -> float:
        ap = list(a.getdata())
        bp = list(base.getdata())
        t = sum(
            abs(ar - br) + abs(ag - bg) + abs(ab - bb)
            for (ar, ag, ab), (br, bg, bb) in zip(ap, bp)
        )
        return t / (len(bp) * 3)

    assert _mean_delta(heavy) > _mean_delta(light)
