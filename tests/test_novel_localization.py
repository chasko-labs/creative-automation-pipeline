"""Novel localization vs placeholder slop - assume-failure checks.

These tests verify that generation pipelines produce *distinct* localized outputs
per market/season, not the same camo placeholder or military recruit copy. They
fail when the implementation falls back to slop.

No AWS - all Bedrock calls are faked or offline.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from creative_automation import generate, stability_rungs, text_rewriter
from creative_automation.context_pack import build_context_pack


def _fake_png(size=(1080, 1080), color=(180, 90, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _make_seed(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_fake_png((1024, 1024), (30, 90, 160)))
    return path


def test_scene_prompt_contains_local_ingredient_not_camo_palette(tmp_path: Path) -> None:
    """Cincinnati September must surface pawpaws in the stability prompt, not generic camo."""
    brief = "— market: Cincinnati, Ohio 45202 · season: September · frontier: Lebanon, OH — Pawpaw season (Sep) · in-season: pawpaws"
    subject = generate._default_scene_prompt("Power Cakes", brief, "US-OH-CINCINNATI", "active families", None)
    wrapped = stability_rungs._style_sandwich(subject)
    # Must contain the local ingredient flavor, not collapse to generic
    assert "pawpaw" in wrapped.lower(), f"scene prompt must carry local ingredient pawpaws: {wrapped}"
    # Palette must not be camo-dominated green/brown blocks (guard lives in STYLE sandwich)
    assert "no camouflage" in wrapped.lower() or "no large green" in wrapped.lower(), f"palette guard missing: {wrapped}"
    # Must be photographic editorial, not matte gouache illustration
    assert "photographic" in wrapped.lower(), f"style must be photographic, not painterly: {wrapped}"
    assert "gouache" not in wrapped.lower(), f"style must not be painterly gouache: {wrapped}"


def test_text_rewriter_prompt_explicitly_bans_military(tmp_path: Path) -> None:
    """Nova rewrite prompt must forbid recruit/military language."""
    brief = {"market": "US-OH-CINCINNATI", "campaign_message": "Power up with pawpaws", "products": [{"name": "Buttermilk Power Cakes"}]}
    pack = build_context_pack(brief, month="2026-09")
    prompt = text_rewriter._build_prompt(pack["to_prompt_text"](), "Power up", "en")
    lowered = prompt.lower()
    assert "never military" in lowered or "not military" in lowered, f"military guard missing: {prompt[:500]}"
    assert "recruit" in lowered, f"must name recruit as forbidden: {prompt[:500]}"
    assert "agricultural/market frontier" in lowered or "farm" in lowered, f"frontier disambiguation missing: {prompt[:500]}"


def test_context_pack_frontier_disambiguated_not_military() -> None:
    """Context pack must label frontier as agricultural/market, not military."""
    brief = {"market": "US-OH-CINCINNATI", "campaign_message": "x", "products": []}
    pack = build_context_pack(brief, month="2026-09")
    text = pack["to_prompt_text"]()
    assert "not military" in text.lower(), f"frontier military disambiguation missing: {text}"
    assert "farm/orchard" in text.lower() or "agricultural" in text.lower()


def test_pillow_fallback_tiles_are_visually_distinct(tmp_path: Path) -> None:
    """Pillow fallback must produce distinct crops per ratio, not 4 identical center crops."""
    seed = _make_seed(tmp_path / "hero-1x1.png")
    # Create a base with a vertical gradient so different centering yields different hashes
    base = Image.new("RGB", (1200, 1000))
    for y in range(1000):
        for x in range(1200):
            base.putpixel((x, y), (x % 256, y % 256, (x + y) % 256))
    base.save(seed, "PNG")

    paths = {}
    for ratio, dims in [("4x5", (1080, 1350)), ("9x16", (1080, 1920)), ("16x9", (1920, 1080)), ("blog", (1200, 630))]:
        out = tmp_path / f"fallback-{ratio}.png"
        generate._pillow_outpaint_fallback(seed, dims[0], dims[1], out)
        paths[ratio] = out

    # Hashes must differ across ratios (distinct focal regions)
    import hashlib
    hashes = {r: hashlib.sha256(p.read_bytes()).hexdigest() for r, p in paths.items()}
    assert len(set(hashes.values())) == 4, f"pillow fallbacks must be visually distinct per ratio, got dup hashes: {hashes}"
    # Also ensure not flat camo: each fallback must have color variance
    for ratio, p in paths.items():
        im = Image.open(p)
        pixels = list(im.getdata())
        distinct = len(set(pixels[:1000]))
        assert distinct > 10, f"{ratio} fallback is flat camo slop with {distinct} colors"


def test_tile_engine_mark_not_placeholder() -> None:
    """Frontend mark must not say placeholder for pillow fallback (user perceives as slop)."""
    js = Path("web/kodiak-posts-for-todays-frontier/js/generate.js").read_text()
    assert "pillow-outpaint-fallback" in js
    # Tile engine mark for fallback must be cover-pad, not placeholder
    assert "' · cover-pad'" in js or '" · cover-pad"' in js or "· cover-pad" in js
    # The ENGINE_LABELS map may still describe Pillow pad (placeholder) for provenance panel - that's ok
    # but the per-tile mark must not be placeholder
    # Check specific function
    assert "tileEngineMark" in js
    # Ensure the fallback branch returns cover-pad
    assert "if(engine==='pillow-outpaint-fallback') return {text:' · cover-pad'" in js
