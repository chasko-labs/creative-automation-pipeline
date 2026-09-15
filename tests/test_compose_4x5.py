"""4x5 is a first-class compose ratio.

Guards the naming/compose contract for the fourth customer delivery ratio (1x1, 4x5,
9x16, 16x9): the RATIOS map sizes 4x5 at 1080x1350, CANONICAL folds both spellings to
4x5, and compose_creative renders a real 1080x1350 png for "4x5" and "4:5". No network,
no AWS — Pillow only.
"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from creative_automation import compose


def _make_hero(path: Path, size: tuple[int, int] = (1024, 1024)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    Image.new("RGB", size, (180, 90, 30)).save(buf, "PNG")
    path.write_bytes(buf.getvalue())
    return path


def test_ratios_and_canonical_carry_4x5():
    # both spellings size to the 1080x1350 portrait canvas
    assert compose.RATIOS["4x5"] == (1080, 1350)
    assert compose.RATIOS["4:5"] == (1080, 1350)
    # canonicalization folds either spelling to the standard 4x5 token
    assert compose.CANONICAL["4x5"] == "4x5"
    assert compose.CANONICAL["4:5"] == "4x5"


def test_compose_creative_renders_4x5_at_1080x1350(tmp_path: Path):
    hero = _make_hero(tmp_path / "hero.png")
    for ratio_key in ("4x5", "4:5"):
        out = tmp_path / f"creative-{ratio_key.replace(':', 'x')}.png"
        compose.compose_creative(
            hero_path=hero,
            out_path=out,
            message="Fuel Wild Mornings",
            ratio_key=ratio_key,
            bare=True,
        )
        with Image.open(out) as im:
            assert im.size == (1080, 1350), f"{ratio_key} rendered {im.size}, expected (1080, 1350)"
