"""art-slug candidate fallback (paren-qualified ingredients share base art).

Monthly values carry parenthetical qualifiers (storage / varietal / venue notes)
that are display truth on the card but must not fork the S3 art library per
qualifier. Candidates resolve most-specific first so every previously published
object keeps resolving exactly as before.
"""
from pathlib import Path

from PIL import Image

from creative_automation import recipe_art
from creative_automation.recipe_art import art_slug_candidates, slugify


def test_plain_ingredient_yields_single_slug():
    assert art_slug_candidates("pumpkins") == ["pumpkins"]


def test_venue_note_falls_back_to_base_ingredient():
    assert art_slug_candidates("pumpkins (corn maze)") == [
        "pumpkins-corn-maze",
        "pumpkins",
    ]


def test_storage_qualifier_falls_back_to_base():
    candidates = art_slug_candidates("apples (storage)")
    assert candidates[0] == "apples-storage"
    assert candidates[-1] == "apples"


def test_compound_with_harvest_note_strips_parens_only():
    candidates = art_slug_candidates("Waialua coffee (harvest) and papaya")
    assert candidates[0] == slugify("Waialua coffee (harvest) and papaya")
    assert candidates[-1] == "waialua-coffee-and-papaya"


def test_parens_only_input_stays_namespaced():
    # "(storage)" must not publish under the generic "subject" fallback slug.
    assert art_slug_candidates("(storage)") == ["storage"]


def test_full_slug_first_preserves_existing_objects():
    # the first candidate is always today's slugify, so all 271 published
    # objects keep resolving before any fallback is consulted.
    assert art_slug_candidates("olive oil (fall press)")[0] == slugify(
        "olive oil (fall press)"
    )


def _mixed(dark_frac: float, size: int = 10) -> Image.Image:
    # coverage is the fraction of pixels darker than mid-grey: exactly dark_frac.
    img = Image.new("RGB", (size, size), (255, 255, 255))
    px = img.load()
    n = int(size * size * dark_frac)
    for i in range(n):
        px[i % size, i // size] = (0, 0, 0)
    return img


def test_all_attempts_over_ceiling_returns_best_not_none(monkeypatch, tmp_path: Path) -> None:
    # the Apple Cider Donuts incident: every attempt marginally over the 0.37
    # ceiling returned None and the card shipped no plate art. Best-of-N keeps
    # the closest drawing instead of the SVG placeholder.
    calls: list = []

    def fake_invoke(client, subject, zone, *, seed, negative, extra_clause=""):
        calls.append(seed)
        # all over the ceiling; the middle attempt is closest to it.
        frac = {0: 0.90, 1: 0.45, 2: 0.70}[len(calls) - 1]
        return _mixed(frac)

    monkeypatch.setattr(recipe_art, "_bedrock_client", lambda *a, **k: object())
    monkeypatch.setattr(recipe_art, "_invoke_image", fake_invoke)
    out = recipe_art.generate_recipe_art(
        "Apple Cider Donuts", "finished_plate", seed=7, out_dir=tmp_path
    )
    assert out is not None
    assert Path(out).exists()
    assert len(calls) == recipe_art._MAX_ATTEMPTS
    # best-of-3 kept the lightest attempt (seed+1), not the last one.
    assert calls[1] == 8
    saved = Image.open(Path(out))
    assert abs(recipe_art._dark_coverage(saved) - 0.45) < 0.01


def test_invoke_failure_after_partial_keeps_best(monkeypatch, tmp_path: Path) -> None:
    # a blocked/error invoke mid-escalation must not discard an earlier drawing.
    seq = iter([_mixed(0.90), None, _mixed(0.70)])
    monkeypatch.setattr(recipe_art, "_bedrock_client", lambda *a, **k: object())
    monkeypatch.setattr(
        recipe_art, "_invoke_image", lambda *a, **k: next(seq)
    )
    out = recipe_art.generate_recipe_art(
        "Apple Cider Donuts", "finished_plate", seed=7, out_dir=tmp_path
    )
    assert out is not None
    assert Path(out).exists()
