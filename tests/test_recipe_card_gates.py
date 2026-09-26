"""Issue 307 merge gates: the recipe-card acceptance checks that run in pytest.

Mechanical, not eyeballed: hero text-free (cr-1), legibility floor (type size
+ contrast, the OCR proxy), font scale sanity. The uncertainty-marker gate is
NOT here yet — the v1 contract (#304) has no marker field and the renderer
draws none, so that gate lands with the #306 provenance-marker design rather
than as a permanent red.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from creative_automation import recipe_card as rc


def _blocks() -> dict:
    return {
        "title": "Muscadine Griddle Cakes",
        "ingredient_line": "Local pick: muscadine grapes",
        "steps": ["Mash the grapes", "Fold into batter", "Griddle until golden"],
    }


def _png_bytes(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()


def _luminance(rgb: tuple[int, int, int]) -> float:
    def _lin(c: int) -> float:
        v = c / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    r, g, b = (_lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(fg: tuple[int, int, int], bg: tuple[int, int, int] = (255, 255, 255)) -> float:
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_hero_band_is_pixel_identical_to_input(tmp_path: Path) -> None:
    # cr-1: compose pastes the hero verbatim and draws text ONLY below HERO_H.
    # Any glyph intruding into the hero band changes pixels -> gate fails.
    hero = Image.new("RGB", (rc.CARD_W, rc.HERO_H), (10, 20, 30))
    out = tmp_path / "card.png"
    rc._compose_card(hero, _blocks(), out)
    band = Image.open(out).convert("RGB").crop((0, 0, rc.CARD_W, rc.HERO_H))
    assert _png_bytes(band) == _png_bytes(hero)


def test_layout_type_and_contrast_floor() -> None:
    # OCR readability proxy: every layout size at/above the floor, every fill
    # at/above its WCAG floor on the white panel (ingredient line is large
    # text, so the 3.0 large-text floor applies to the brand orange).
    assert min(rc.TITLE_PX, rc.ING_PX, rc.STEP_PX) >= rc.MIN_TYPE_PX
    assert _contrast(rc.BEAR_BROWN) >= rc.MIN_CONTRAST
    assert _contrast(rc.STEP_FILL) >= rc.MIN_CONTRAST
    assert rc.ING_PX >= rc.MIN_TYPE_PX
    assert _contrast(rc.BLAZE_ORANGE) >= rc.MIN_CONTRAST_LARGE


def test_loaded_fonts_scale_with_requested_size() -> None:
    # A bitmap-fallback font ignores size and shrinks all type silently —
    # the loaded fonts must actually scale, with a sane floor at title size.
    sizes = {}
    for px in (rc.TITLE_PX, rc.ING_PX, rc.STEP_PX):
        box = rc._load_font(px).getbbox("Ag")
        assert box is not None
        sizes[px] = box[3] - box[1]
    assert sizes[rc.TITLE_PX] > sizes[rc.ING_PX] > sizes[rc.STEP_PX]
    assert sizes[rc.TITLE_PX] >= 20
