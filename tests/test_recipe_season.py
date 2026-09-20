"""Recipe-season linkage: cards follow the market x month harvest map.

A recipe card resolves its ingredient from the market's monthly_ingredients map
(retailer-frontier-pairs.json, the source of truth) and matches a recipe naming
that in-season ingredient. Markets sharing an in-season staple resolve the SAME
ingredient — shared monthly staples across markets are legitimate overlap, not
dupes, and must never be "fixed" away by cross-market dedupe. The variety
rotation in _pick_recipe spreads the CARDS (same staple -> different recipes per
market when several genuinely match), never the ingredient.
"""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation.recipe_card import _pick_recipe, build_recipe_card

PAIRS = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "localization"
    / "retailer-frontier-pairs.json"
)


def _monthly_map(market: str) -> dict:
    pairs = json.loads(PAIRS.read_text())["pairs"]
    entry = next(p for p in pairs if p.get("market") == market)
    monthly = entry.get("monthly_ingredients") or {}
    if isinstance(monthly, dict):
        return {m: v for m, v in monthly.items() if v}
    return {
        (row.get("month") or row.get("key")): (row.get("ingredient") or row.get("value"))
        for row in monthly
        if isinstance(row, dict) and (row.get("month") or row.get("key"))
    }


def test_shared_monthly_staple_across_markets_is_legitimate_overlap():
    # January storage apples are on the map for many markets at once. That
    # overlap is the harvest calendar working (a shared staple), not a content
    # bug — no dedupe may span markets to remove it.
    pairs = json.loads(PAIRS.read_text())["pairs"]
    holders = [
        p.get("market") for p in pairs
        if isinstance(p.get("monthly_ingredients"), dict)
        and (p.get("monthly_ingredients") or {}).get("2026-01") == "storage apples"
    ]
    assert len(holders) > 1, "expected a shared January staple across markets"
    assert "US-SE-LOU" in holders and "US-MW-CHI" in holders


def test_sharing_markets_resolve_the_same_staple(tmp_path):
    # Louisville + Chicago both carry storage apples in 2026-01: both cards
    # resolve that same staple with a matched recipe. Same ingredient, same
    # month, two markets — legitimate, both served.
    for market in ("US-SE-LOU", "US-MW-CHI"):
        result = build_recipe_card(market, month="2026-01", out_dir=tmp_path)
        assert result["month"] == "2026-01"
        assert result["ingredient"] == "storage apples"
        assert result["recipe"] is not None
        assert result["recipe"]["id"]


def test_card_ingredient_matches_monthly_map(tmp_path):
    # The card never invents produce: its ingredient is the map's ingredient for
    # that market + month.
    for market, month in (("US-SE-ATL", "2026-09"), ("US-SE-ATL", "2026-01")):
        result = build_recipe_card(market, month=month, out_dir=tmp_path)
        assert result["ingredient"] == _monthly_map(market)[month]


def test_shared_ingredient_rotates_cards_across_markets():
    # Maple syrup is March in Atlanta AND Burlington: the rotation spreads the
    # cards (different recipes per market) while staying deterministic per
    # market+month — rerunning Atlanta picks the same card again.
    atl = _pick_recipe(
        "maple syrup", "Buttermilk Power Cakes",
        market="US-SE-ATL", month="2026-03",
    )
    burlington = _pick_recipe(
        "maple syrup", "Buttermilk Power Cakes",
        market="US-NE-BURLINGTON", month="2026-03",
    )
    atl_again = _pick_recipe(
        "maple syrup", "Buttermilk Power Cakes",
        market="US-SE-ATL", month="2026-03",
    )
    assert atl and burlington and atl_again
    assert atl["id"] == atl_again["id"]
    assert atl["id"] != burlington["id"]
