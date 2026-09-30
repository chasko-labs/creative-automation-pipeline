"""Tests for recipe_video dwell segmentation (synthetic images, Pillow)."""

from PIL import Image, ImageDraw, ImageFilter

from creative_automation.recipe_video import (
    frame_motion,
    pick_best,
    score_frame,
    segment_dwells,
)


def _text_card(seed: int = 0, size: tuple = (640, 360)) -> Image.Image:
    img = Image.new("L", size, 235)
    d = ImageDraw.Draw(img)
    for y in range(20, size[1] - 10, 14):
        d.rectangle([30, y, size[0] - 30, y + 5], fill=30)
    return img


def test_sharp_beats_blur():
    sharp = _text_card()
    blur = sharp.filter(ImageFilter.GaussianBlur(8))
    assert score_frame(sharp)["sharp"] > score_frame(blur)["sharp"]


def test_glare_flags_washout():
    card = _text_card()
    washed = card.copy()
    d = ImageDraw.Draw(washed)
    d.rectangle([100, 100, 500, 260], fill=255)
    assert score_frame(washed)["glare"] > score_frame(card)["glare"]
    assert score_frame(washed)["glare"] > 0.1


def test_motion_zero_on_identical():
    card = _text_card()
    assert frame_motion(card, card) == 0.0


def test_motion_spikes_on_change():
    from PIL import ImageChops

    a = _text_card()
    shifted = ImageChops.offset(a, 0, 7)
    assert frame_motion(a, shifted) > 20.0


def test_segment_dwells_splits_on_spike():
    motions = [0.0, 1.0, 2.0, 1.5, 80.0, 2.0, 1.0, 0.5, 90.0, 1.0]
    assert segment_dwells(motions) == [(0, 3), (5, 7)]


def test_segment_dwells_drops_short_runs():
    motions = [0.0, 1.0, 80.0, 1.0, 2.0, 1.0, 0.5]
    assert segment_dwells(motions) == [(3, 6)]


def test_pick_best_takes_sharpest():
    scores = [{"sharp": 10.0}, {"sharp": 99.0}, {"sharp": 50.0}]
    assert pick_best(scores) == 1
