"""Render-contract ratio suite: geometry, order, and the five-tile surface.

The backend delivers four photographic ratios (generate_hero_set, 1x1-first,
v2 DoD canvas sizes); the frontend preview surface adds the static blog tile
(TILE_ORDER = blog/1x1/16x9/4x5/9x16 in js/frontier-contracts.js). These pins
tie the two halves together: backend ratios land on the exact canvas pixels in
delivery order, and delivery ratios + blog cover the frontend tile order with
nothing extra on either side.
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

from creative_automation import generate as generate_mod

EXPECTED_CANVAS = {
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}


def _tile_order_from_frontend() -> list[str]:
    root = Path(__file__).resolve().parent.parent
    src = (
        root
        / "web"
        / "kodiak-posts-for-todays-frontier"
        / "js"
        / "frontier-contracts.js"
    ).read_text()
    match = re.search(r"TILE_ORDER\s*=\s*\[(.*?)\]", src, re.S)
    assert match, "TILE_ORDER missing from frontier-contracts.js"
    return re.findall(r"'([0-9a-z]+)'", match.group(1))


def test_canvas_sizes_match_v2_dod():
    assert dict(generate_mod._CANVAS) == EXPECTED_CANVAS


def test_delivery_ratios_are_1x1_first_cover_canvas():
    assert tuple(generate_mod._DELIVERY_RATIOS) == ("1x1", "4x5", "9x16", "16x9")
    assert set(generate_mod._DELIVERY_RATIOS) <= set(generate_mod._CANVAS)


def test_delivery_ratios_plus_blog_cover_frontend_tile_order():
    # The five-tile surface = the four backend photographic ratios + the
    # frontend-static blog tile. No ratio ships that the frontend cannot place,
    # and no frontend tile lacks a backend source (blog excepted: textless seed).
    tile_order = _tile_order_from_frontend()
    assert tile_order == ["blog", "1x1", "16x9", "4x5", "9x16"]
    assert set(tile_order) == set(generate_mod._DELIVERY_RATIOS) | {"blog"}


def _stub_base_hero(**kwargs):
    out = Path(kwargs["out_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1080, 1080), (10, 20, 30)).save(out, "PNG")
    prov = {"engine": "pillow-compose", "scene_prompt": "stub scene"}
    return out, "stub:base", prov


def test_hero_set_returns_four_ratios_in_order_on_canvas(tmp_path, monkeypatch):
    # Offline: stubbed base hero + headline, stability rung off so talls/wides
    # take the deterministic Pillow pad — the ratio loop itself is real.
    monkeypatch.setattr(generate_mod, "generate_hero", _stub_base_hero)
    monkeypatch.setattr(
        generate_mod, "_headline_for", lambda *a, **k: ("Stub Headline", "stub")
    )
    monkeypatch.setattr(generate_mod, "_STABILITY_RUNG_ON", False)

    renders, _source, prov = generate_mod.generate_hero_set(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="a bear eating pancakes",
        region="us",
        audience="active families",
        out_dir=tmp_path / "set",
        brand_overlay=False,
        layers={},
    )

    assert [r["ratio"] for r in renders] == list(generate_mod._DELIVERY_RATIOS)
    for render in renders:
        assert Path(render["path"]).exists()
        assert (render["w"], render["h"]) == EXPECTED_CANVAS[render["ratio"]]
        with Image.open(render["path"]) as im:
            assert im.size == EXPECTED_CANVAS[render["ratio"]]
    assert renders[0]["engine"] == "primary"
    assert renders[1]["engine"] == "pillow-outpaint-fallback"
    assert list(prov["ratios"]) == list(generate_mod._DELIVERY_RATIOS)
