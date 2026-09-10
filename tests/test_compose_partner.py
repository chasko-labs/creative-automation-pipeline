"""Partner-person composite layer: licensed cutouts pasted verbatim, never synthesized.

Uses synthetic RGBA stand-ins (no likeness) to prove the mechanics: thirds-left
placement, verbatim pixels, alpha required, and byte-identical output when no
cutout is supplied.
"""
from __future__ import annotations

import pathlib

import pytest
from PIL import Image

from creative_automation.compose import compose_creative, compose_partner_cutout

TMP = pathlib.Path("/tmp/partner-cutout-tests")
TMP.mkdir(exist_ok=True)


def _bg() -> Image.Image:
    return Image.new("RGB", (1080, 1080), (30, 40, 35))


def _cutout() -> pathlib.Path:
    # synthetic stand-in: solid red disc on transparency (NOT a person)
    img = Image.new("RGBA", (200, 300), (0, 0, 0, 0))
    px = img.load()
    for y in range(300):
        for x in range(200):
            if (x - 100) ** 2 + (y - 150) ** 2 < 90**2:
                px[x, y] = (255, 0, 0, 255)
    p = TMP / "standin-cutout.png"
    img.save(p)
    return p


def _hero() -> pathlib.Path:
    p = TMP / "hero.png"
    Image.new("RGB", (800, 800), (60, 50, 40)).save(p)
    return p


def test_cutout_lands_left_third_verbatim():
    out = compose_partner_cutout(_bg(), _cutout(), side="left")
    assert out.size == (1080, 1080)
    # left-third region carries the red disc pixels verbatim
    left = out.crop((0, 0, 540, 1080))
    reds = sum(1 for px in left.getdata() if px[0] > 200 and px[1] < 80 and px[2] < 80)
    assert reds > 1000
    # right-third region is untouched background
    right = out.crop((700, 100, 1000, 400))
    assert {px for px in right.getdata()} == {(30, 40, 35)}


def test_cutout_requires_alpha():
    flat = TMP / "flat.png"
    Image.new("RGB", (100, 100), (255, 0, 0)).save(flat)
    with pytest.raises(ValueError, match="transparency"):
        compose_partner_cutout(_bg(), flat)


def test_no_cutout_keeps_existing_callers_byte_identical():
    a = TMP / "a.png"
    b = TMP / "b.png"
    compose_creative(_hero(), a, "Keep It Wild", "1x1")
    compose_creative(_hero(), b, "Keep It Wild", "1x1", partner_cutout=None)
    assert a.read_bytes() == b.read_bytes()


def test_creative_with_cutout():
    out = TMP / "with-cutout.png"
    compose_creative(_hero(), out, "Keep It Wild", "1x1", partner_cutout=_cutout())
    assert out.exists()
    img = Image.open(out)
    reds = sum(1 for px in img.getdata() if px[0] > 200 and px[1] < 80 and px[2] < 80)
    assert reds > 1000
