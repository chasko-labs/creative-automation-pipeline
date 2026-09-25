"""Brief grounding: the user's campaign idea steers scene, seed, and copy.

Regression cover for the "sea otters -> poached egg" report: the brief's
free-text idea used to reach nothing — seed selection never consulted it,
the scene lost it in Nova compression, copy rewrote only the image caption,
and the cider record could never pair. All offline, no network.
"""
from __future__ import annotations

from creative_automation import generate
from creative_automation.recipe_card import _pick_recipe_detail


def test_brief_idea_strips_suffix() -> None:
    brief = "sea otters — season: September · market: Park City · products: power-cakes"
    assert generate._brief_idea(brief) == "sea otters"


def test_brief_idea_markers_only_is_empty() -> None:
    assert generate._brief_idea("season: September · market: Park City") == ""
    assert generate._brief_idea(None) == ""
    assert generate._brief_idea("") == ""


def test_brief_idea_keeps_free_text_with_ecology() -> None:
    brief = "surfboard at sunset · ecology: coastal stack · in-season: apple cider (apple, cider)"
    assert generate._brief_idea(brief) == "surfboard at sunset"


def test_brief_idea_strips_parenthetical_markers() -> None:
    brief = "wild mornings (frontier: Lebanon, OH - US-OH-CINCINNATI market, september picks)"
    assert generate._brief_idea(brief) == "wild mornings"


def test_subject_clause_names_idea() -> None:
    clause = generate._brief_subject_clause("sea otters — season: September")
    assert "sea otters" in clause
    assert "MUST feature" in clause


def test_subject_clause_empty_without_idea() -> None:
    assert generate._brief_subject_clause("season: September") == ""
    assert generate._brief_subject_clause(None) == ""


def test_subject_clause_scrubs_adversary() -> None:
    clause = generate._brief_subject_clause("Zac Efron eating pancakes — season: September")
    assert "Zac Efron" not in clause


def test_seed_pick_matches_caption_word() -> None:
    cands = [
        ("brands/kitchen.jpg", "woman eating poached egg"),
        ("brands/tacos.jpg", "breakfast tacos party"),
    ]
    assert generate._brief_seed_pick("peach tacos", cands) == "brands/tacos.jpg"


def test_seed_pick_no_overlap_returns_none() -> None:
    cands = [("brands/kitchen.jpg", "woman eating poached egg")]
    assert generate._brief_seed_pick("sea otters", cands) is None
    assert generate._brief_seed_pick("", cands) is None


def test_default_scene_prompt_carries_subject() -> None:
    scene = generate._default_scene_prompt(
        "Power Cakes", "sea otters — season: September", "us", "families",
        None, None, None, "US-MW-PARKCITY-84098", "September",
    )
    assert "sea otters" in scene
    assert "MUST feature" in scene


def test_blend_idea_base_leads_with_idea() -> None:
    base = generate._blend_idea_base(
        "Keep It Wild — September aspen gold", "sea otters — season: September"
    )
    assert base.startswith("sea otters — ")
    assert len(base) <= 80


def test_blend_idea_base_skips_when_present() -> None:
    base = generate._blend_idea_base("sea otters at dawn", "sea otters")
    assert base == "sea otters at dawn"


def test_cider_ingredient_pairs_cider_donuts() -> None:
    recipe, pairing = _pick_recipe_detail(
        "apple cider", None, market="US-W-SD", month="2026-12"
    )
    assert recipe is not None
    assert recipe.get("id") == "apple-cider-donuts"
    assert pairing["source"] == "ingredient-featured"
