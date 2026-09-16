"""Recipe-card generator (agentcore B4) — offline path.

Atlanta US-SE-ATL September resolves to muscadine grapes (locales, never fabricated).
The card's text blocks flow through B1 so they are safety-gated + dialect-correct, and
the image layer stays text-free (cr-1) — text lives only in the layout panel. An
unfilled month must return the no-ingredient result without crashing.
"""
from pathlib import Path

from creative_automation import naming
from creative_automation.recipe_card import build_recipe_card


def test_atlanta_september_card_references_muscadine(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    assert result["ingredient"] == "muscadine grapes"
    # the ingredient surfaces in the card text (title or ingredient line)
    blob = (result["text_blocks"]["title"] + " " + result["text_blocks"]["ingredient_line"]).lower()
    assert "muscadine" in blob


def test_atlanta_card_text_blocks_pass_safety(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    assert result["safety"]["clean"] is True
    assert result["text_blocks"]["title"]
    assert result["text_blocks"]["steps"]


def test_atlanta_card_file_exists_and_is_iso_named(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    path = Path(result["card_path"])
    assert path.exists()
    assert naming.ISO_NAME_RE.match(path.name), f"not iso-named: {path.name}"
    # channel field is recipe-card per the B4 spec
    assert "recipe-card" in path.name


def test_atlanta_card_matched_a_recipe(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    assert result["recipe"] is not None
    assert result["recipe"]["id"]


def test_backfilled_january_resolves_to_turnips(tmp_path):
    # Atlanta January was backfilled to true 12/12 (all 73 markets now resolve
    # every 2026 month) -> resolves turnips with a written card, not a gap.
    result = build_recipe_card("US-SE-ATL", month="2026-01", out_dir=tmp_path)
    assert result["ingredient"] == "turnips"
    assert Path(result["card_path"]).exists()


def test_unseeded_month_returns_no_ingredient_without_crashing(tmp_path):
    # the honest-empty path must still work for months outside seeded data.
    result = build_recipe_card("US-SE-ATL", month="2027-01", out_dir=tmp_path)
    assert result["ingredient"] is None
    assert result["card_path"] is None
    assert "no in-season ingredient" in result["reason"]


def test_unknown_market_returns_no_pair_without_crashing(tmp_path):
    result = build_recipe_card("US-XX-NOWHERE", month="2026-09", out_dir=tmp_path)
    assert result["ingredient"] is None
    assert result["card_path"] is None
    assert "no retailer-frontier pair" in result["reason"]


def test_card_text_blocks_carry_no_bare_kodiak(tmp_path):
    import re

    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    blocks = [result["text_blocks"]["title"], result["text_blocks"]["ingredient_line"]]
    blocks.extend(result["text_blocks"]["steps"])
    for text in blocks:
        assert not re.search(r"(?<![#\w])[Kk][Oo][Dd][Ii][Aa][Kk]\b(?!\s+(Cakes?|Park\s+City))", text), text


def test_publish_offline_returns_none_key(tmp_path):
    result = build_recipe_card(
        "US-SE-ATL", month="2026-09", out_dir=tmp_path, publish=True
    )
    # DAM unconfigured in CI: card still composes, dam_key degrades to None.
    assert Path(result["card_path"]).exists()
    assert result["dam_key"] is None


def test_publish_card_never_throws_without_dam(tmp_path):
    from creative_automation.recipe_card import publish_card

    assert publish_card(tmp_path / "nope.jpg") is None


def test_featured_for_beats_overlap_lottery():
    from creative_automation.recipe_card import _pick_recipe

    assert _pick_recipe("Half Moon Bay pumpkin", None)["id"] == "pumpkin-oat-muffins"
    assert _pick_recipe("spinach", None)["id"] == "savory-greens-fritters-draft"
    assert _pick_recipe("rainbow chard", None)["id"] == "savory-greens-fritters-draft"
    # uncurated months keep overlap behavior (no silent reshuffle)
    assert _pick_recipe("strawberries", None)["id"] == "yogurt-pie"
    assert _pick_recipe("muscadine grapes", None)["id"] == "roasted-grape-flapjack-topper-draft"


def test_curated_pairings_route_to_honest_recipes():
    from creative_automation.recipe_card import _pick_recipe

    assert _pick_recipe("sweet cherries", None)["id"] == "cherry-pie-bars"
    assert _pick_recipe("avocado (florida)", None)["id"] == "avocado-pancakes"
    assert _pick_recipe("meyer lemon", None)["id"] == "single-serve-lemon-ricotta-flapjack-cup"
    assert _pick_recipe("green and red chile", None)["id"] == "red-chile-cornbread-muffins-draft"
    assert _pick_recipe("boiled peanuts", None)["id"] == "boiled-peanut-oat-bites-draft"
    assert _pick_recipe("huckleberries", None)["id"] == "huckleberry-flapjack-topper-draft"
    assert _pick_recipe("celery", None)["id"] == "celery-parmesan-pancakes-draft"
    assert _pick_recipe("cremini mushrooms", None)["id"] == "mushroom-cheddar-muffins-draft"
    assert _pick_recipe("pears (storage)", None)["id"] == "pear-spice-muffins-draft"


def test_new_drafts_have_honest_nulls_and_verb_first_steps():
    from creative_automation.recipe_card import build_recipe_card_data

    c = build_recipe_card_data("US-SE-ATL", month="2026-09")
    assert c.get("title") == "Roasted Grape Flapjack Topper"
    c2 = build_recipe_card_data("US-CA-CASTROVILLE", month="2026-03")
    assert c2["meta"]["est_cost"] is None
    import json
    from pathlib import Path as _P

    catalog = json.loads(_P("data/recipes/kodiak-recipes.json").read_text())
    wanted = {
        "snap-pea-herb-fritters-draft", "mushroom-cheddar-muffins-draft",
        "huckleberry-flapjack-topper-draft", "fig-honey-muffins-draft",
        "pear-spice-muffins-draft", "wild-rice-cheddar-pancakes-draft",
        "persimmon-spice-muffins-draft", "green-bean-parmesan-fritters-draft",
        "celery-parmesan-pancakes-draft", "date-oat-breakfast-cookies-draft",
        "boiled-peanut-oat-bites-draft"}
    drafts = [r for r in catalog if r["id"] in wanted]
    assert len(drafts) == 11
    for r in drafts:
        assert r.get("prepTime") in (None, ""), r["id"]
        assert r.get("cookTime") in (None, ""), r["id"]
        assert r.get("yield") in (None, ""), r["id"]
        assert r["instructions"], r["id"]
        for step in r["instructions"]:
            assert not step.rstrip().endswith("!"), (r["id"], step)


def test_card_title_and_steps_are_real_content():
    from creative_automation.recipe_card import build_recipe_card_data

    c = build_recipe_card_data("US-CA-CASTROVILLE", month="2026-03")
    assert c.get("title") == "Broccoli Cauliflower Cheddar Fritters"
    assert c.get("recipe", {}).get("name") == c.get("title")
    assert c.get("steps"), "no exclamatory ad copy: steps are the real instructions"
    assert not any(s.rstrip().endswith("!") for s in c["steps"])
    assert c["steps"][0].startswith("STEAM")
