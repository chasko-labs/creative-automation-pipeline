"""art-slug candidate fallback (paren-qualified ingredients share base art).

Monthly values carry parenthetical qualifiers (storage / varietal / venue notes)
that are display truth on the card but must not fork the S3 art library per
qualifier. Candidates resolve most-specific first so every previously published
object keeps resolving exactly as before.
"""
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
