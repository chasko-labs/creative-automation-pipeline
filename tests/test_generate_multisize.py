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



# ------------------------------------------------- recipe-card template (deterministic)
def _make_hero(path: Path, size: tuple[int, int] = (1080, 1080)) -> Path:
    # a non-uniform hero so the image-slot content is detectably present after composing.
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, (30, 90, 160))
    for x in range(0, size[0], 8):
        for y in range(0, size[1], 8):
            img.putpixel((x, y), (220, 140, 40))
    img.save(path, "PNG")
    return path


def test_compose_recipe_card_deterministic_same_bytes(tmp_path: Path) -> None:
    # same inputs -> byte-identical card (fixed fonts + palette, no randomness here).
    hero = _make_hero(tmp_path / "hero.png")
    fields = {"ingredients": ["2 cups mix", "1 cup milk"], "steps": ["whisk", "cook"]}
    a = generate._compose_recipe_card(hero, "Trail Stack", "4x5", tmp_path / "a.png", fields)
    b = generate._compose_recipe_card(hero, "Trail Stack", "4x5", tmp_path / "b.png", fields)
    assert a.read_bytes() == b.read_bytes()


def test_compose_recipe_card_dims_and_hero_slot_present(tmp_path: Path) -> None:
    # the card is at the requested _CANVAS ratio dims and the GenAI hero region (top slot)
    # carries non-uniform pixels — the generative image is really placed in the slot.
    hero = _make_hero(tmp_path / "hero.png")
    out = generate._compose_recipe_card(hero, "Wild Protein Stack", "2x3", tmp_path / "card.png")
    w, h = generate._CANVAS["2x3"]
    with Image.open(out) as im:
        assert im.size == (w, h)
        rgb = im.convert("RGB")
        # sample the top-slot image region (~top 40% is inside the 55% hero slot)
        samples = {
            rgb.getpixel((x, y))
            for x in range(0, w, w // 8)
            for y in range(0, int(h * 0.40), max(1, int(h * 0.40) // 8))
        }
        assert len(samples) > 1  # non-uniform -> the hero is present, not a flat fill
        # C03 Blaze Orange accent bar pinned to the bottom row
        accent = generate._hex_to_rgb(generate._accent_hex)
        bottom = rgb.getpixel((w // 2, h - 1))
        assert abs(bottom[0] - accent[0]) < 30 and abs(bottom[1] - accent[1]) < 30


def _seeded_hero_set(tmp_path: Path, monkeypatch) -> None:
    """Wire generate_hero_set so a stability hero is produced offline (no AWS)."""
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)

    def _fake_control(seed_path, prompt, out):
        out.write_bytes(_png_bytes())
        return out

    monkeypatch.setattr(generate, "_stability_control_hero", _fake_control)
    monkeypatch.setattr(generate, "_stability_outpaint", lambda *a, **k: None)
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: "Keep It Wild\nLAYOUT: center")


def test_recipe_cards_theme_runs_card_template(tmp_path: Path, monkeypatch) -> None:
    # theme "recipe-cards" -> the card template runs; provenance marks card_template True
    # and each ratio engine notes the recipe-card-template step.
    _seeded_hero_set(tmp_path, monkeypatch)
    called: list[str] = []
    real_card = generate._compose_recipe_card

    def _spy(hero, title, ratio, out, recipe_fields=None):
        called.append(ratio)
        return real_card(hero, title, ratio, out, recipe_fields)

    monkeypatch.setattr(generate, "_compose_recipe_card", _spy)

    renders, _source, prov = generate.generate_hero_set(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_dir=tmp_path / "set",
        theme="recipe-cards",
    )
    assert prov.get("card_template") is True
    assert set(called) == {"1x1", "4x5", "2x3"}
    assert all("recipe-card-template" in prov["ratios"][r] for r in ("1x1", "4x5", "2x3"))
    dims = {r["ratio"]: (r["w"], r["h"]) for r in renders}
    assert dims == {"1x1": (1080, 1080), "4x5": (1080, 1350), "2x3": (1000, 1500)}


def test_non_recipe_theme_skips_card_template(tmp_path: Path, monkeypatch) -> None:
    # a non-recipe theme keeps the plain brand-overlay path — the card template never runs.
    _seeded_hero_set(tmp_path, monkeypatch)
    called: list[str] = []
    monkeypatch.setattr(
        generate, "_compose_recipe_card",
        lambda *a, **k: called.append("x"),  # would record if wrongly invoked
    )

    _renders, _source, prov = generate.generate_hero_set(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild",
        region="us",
        audience="families",
        out_dir=tmp_path / "set",
        theme="green-chile",
    )
    assert called == []
    assert "card_template" not in prov
    assert all("recipe-card-template" not in prov["ratios"][r] for r in ("1x1", "4x5", "2x3"))
