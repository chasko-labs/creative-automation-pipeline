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


def test_unfilled_month_returns_no_ingredient_without_crashing(tmp_path):
    # Atlanta October has no seeded ingredient -> honest no-ingredient result
    result = build_recipe_card("US-SE-ATL", month="2026-10", out_dir=tmp_path)
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
