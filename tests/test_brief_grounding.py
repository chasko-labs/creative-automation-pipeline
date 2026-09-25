"""Brief grounding: the user's campaign idea steers scene, seed, and copy.

Regression cover for the "sea otters -> poached egg" report: the brief's
free-text idea used to reach nothing — seed selection never consulted it,
the scene lost it in Nova compression, copy rewrote only the image caption,
and the cider record could never pair. All offline, no network.
"""
from __future__ import annotations

from pathlib import Path

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


def test_is_scenic_seed() -> None:
    assert generate._is_scenic_seed("brands/kodiak/scenic-bg/sea-otters/hero-1x1.png") is True
    assert generate._is_scenic_seed("brands/kodiak/raw-ingest/kodiakcakes/images/kitchen.jpg") is False
    assert generate._is_scenic_seed(None) is False
    assert generate._is_scenic_seed("") is False


def test_staged_dest_unique_per_key() -> None:
    # Regression: every scenic hero-1x1.png shared one /tmp dest, so a second
    # idea restyled the first idea's file (bears for christmas cats).
    a = generate._staged_dest("brands/kodiak/scenic-bg/sea-otters/hero-1x1.png")
    b = generate._staged_dest("brands/kodiak/scenic-bg/christmas-cats/hero-1x1.png")
    assert a != b
    assert a.name.endswith("hero-1x1.png")
    assert generate._staged_dest("k") == generate._staged_dest("k")


def test_nova_output_reattaches_dropped_idea(monkeypatch, tmp_path: Path) -> None:
    # Nova returns a scene without the idea -> deterministic re-attach.
    class _FakeNova:
        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": "Rustic wood table, warm glow"}]}}}

    monkeypatch.setattr(
        generate, "_bedrock_failfast_client", lambda **kwargs: _FakeNova()
    )
    seed = tmp_path / "seed.png"
    seed.write_bytes(b"fakepng")
    monkeypatch.setattr(generate, "_seed_small_for_nova", lambda src: (b"x", "png"))
    scene = generate._nova_pro_scene_prompt(
        seed, "Power Cakes", "christmas cats — season: Christmas", "us",
        "families", None, None, None, "US-MW-PARKCITY-84098", "Christmas",
    )
    assert "christmas cats" in scene.lower()


def test_nova_output_keeps_idea_without_dup(monkeypatch, tmp_path: Path) -> None:
    class _FakeNova:
        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": "Christmas cats in snow"}]}}}

    monkeypatch.setattr(
        generate, "_bedrock_failfast_client", lambda **kwargs: _FakeNova()
    )
    seed = tmp_path / "seed.png"
    seed.write_bytes(b"fakepng")
    monkeypatch.setattr(generate, "_seed_small_for_nova", lambda src: (b"x", "png"))
    scene = generate._nova_pro_scene_prompt(
        seed, "Power Cakes", "christmas cats", "us", "families",
        None, None, None, None, None,
    )
    assert scene.lower().count("christmas cats") == 1


def test_cider_ingredient_pairs_cider_donuts() -> None:
    recipe, pairing = _pick_recipe_detail(
        "apple cider", None, market="US-W-SD", month="2026-12"
    )
    assert recipe is not None
    assert recipe.get("id") == "apple-cider-donuts"
    assert pairing["source"] == "ingredient-featured"
