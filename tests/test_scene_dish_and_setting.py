"""Scene prompt carries place, season, and dish for ANY market — not just Cincinnati.

North star: a Manhattan/October brief must reach Bedrock naming Warwick/Applefest/
fresh cider AND the paired dish (Baked Halloween Doughnuts), so the pixels match
the recipe card instead of rendering a generic bowl. Cincinnati/September keeps its
pawpaw depth through the same generic marker path (no per-market special cases).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from creative_automation.generate import (
    _default_scene_prompt,
    _scene_prompt_source,
)
from creative_automation.scene_prompts import _brief_setting_clause
from creative_automation.generate_lambda import _preview_dish_name

MANHATTAN_BRIEF = (
    "cozy fall mornings ◇ market: Manhattan, New York · season: halloween · "
    "ecology: Bodega coffee, oatmeal cup on the uptown platform · "
    "frontier: Warwick, NY (Hudson Valley, apples/onions/black dirt) — "
    "Warwick Applefest + Hudson Valley apple harvest (Sep-Oct) · "
    "in-season: fresh cider · products: Buttermilk Power Cakes"
)

CINCY_BRIEF = (
    "wild pawpaw morning ◇ market: Cincinnati, Ohio · season: september · "
    "ecology: Brick market halls, humid river valley — trillium and bluebells spring · "
    "frontier: Lebanon, OH — Pawpaw season (Sep) · "
    "in-season: pawpaws (pawpaw, tropical custard) · products: Buttermilk Power Cakes"
)


def test_setting_clause_distills_manhattan_october():
    clause = _brief_setting_clause(MANHATTAN_BRIEF)
    assert "Warwick" in clause, f"place missing: {clause}"
    assert "Applefest" in clause, f"moment missing: {clause}"
    assert "fresh cider" in clause, f"seasonal feature missing: {clause}"


def test_setting_clause_empty_without_markers():
    assert _brief_setting_clause("just a plain vibe, no markers") == ""
    assert _brief_setting_clause("") == ""
    assert _brief_setting_clause(None) == ""


def test_scene_names_dish_and_setting_for_manhattan():
    scene = _default_scene_prompt(
        "Power Cakes", MANHATTAN_BRIEF, "us", "active families",
        None, None, "Baked Halloween Doughnuts",
    )
    assert "Baked Halloween Doughnuts" in scene, f"dish missing: {scene}"
    assert "Warwick" in scene, f"place missing: {scene}"
    assert "fresh cider" in scene, f"season missing: {scene}"


def test_scene_keeps_cincy_depth_without_special_case():
    scene = _default_scene_prompt(
        "Power Cakes", CINCY_BRIEF, "us", "active families", None, None, "Pawpaw Stack",
    )
    assert "trillium" in scene, f"cincy ecology lost: {scene}"
    assert "Pawpaw Stack" in scene, f"dish missing: {scene}"
    assert "Lebanon" in scene, f"frontier place missing: {scene}"


def test_scene_without_dish_or_markers_unchanged():
    scene = _default_scene_prompt("Power Cakes", "plain morning vibe", "us", "families", None)
    assert "Setting:" not in scene
    assert "Featuring a serving" not in scene
    assert "plain morning vibe" in scene


def test_dish_matches_displayed_season_pairing():
    # halloween displays Baked Halloween Doughnuts (prov recipe), not the tease default
    assert _preview_dish_name({"season": "halloween"}, "Power Cakes") == "Baked Halloween Doughnuts"
    assert _preview_dish_name({"season": "october"}, "Power Cakes") == "Pumpkin Oat Muffins"


def test_dish_explicit_recipe_wins():
    data = {
        "season": "halloween",
        "recipe_fields": {
            "title": "Cider Donut Stack",
            "ingredients": ["mix", "cider"],
            "steps": ["whisk", "cook"],
        },
    }
    assert _preview_dish_name(data, "Power Cakes") == "Cider Donut Stack"


def test_dish_falls_back_without_raising():
    assert _preview_dish_name({}, "Power Cakes") == "Power Cakes Trail Stack"
    # unknown season + junk recipe: still a real dish name (static pairing), never raises, never blank
    garbage = _preview_dish_name({"season": "blorpt", "recipe_fields": "junk"}, "Power Cakes")
    assert isinstance(garbage, str) and garbage.strip(), f"dish must stay real: {garbage!r}"
    assert _preview_dish_name(None, "Power Cakes") is None


def test_scene_source_parity_with_dish():
    scene = _default_scene_prompt(
        "Power Cakes", MANHATTAN_BRIEF, "us", "active families",
        None, None, "Baked Halloween Doughnuts",
    )
    assert _scene_prompt_source(scene, "Power Cakes", MANHATTAN_BRIEF, "us", "active families", None, "Baked Halloween Doughnuts") == "default"
    assert _scene_prompt_source("something else entirely", "Power Cakes", MANHATTAN_BRIEF, "us", "active families", None, "Baked Halloween Doughnuts") == "nova"
