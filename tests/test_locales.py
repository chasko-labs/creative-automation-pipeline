"""Retailer-frontier pairing loader — market resolves to pair + monthly ingredient."""
from creative_automation.locales import (
    FrontierPair,
    load_pairs,
    resolve_pair,
    resolve_this_month,
)


def test_atlanta_pair_fully_populated():
    pair = resolve_pair("US-SE-ATL")
    assert isinstance(pair, FrontierPair)
    assert pair.metro_location["retailer"] == "Publix"
    assert "950 W Peachtree St NW" in pair.metro_location["address"]
    assert pair.metro_location["phone"] == "(404) 253-3544"
    assert pair.frontier_sister["place"] == "Sandersville, GA"
    assert "sandersvillega.org" in pair.frontier_sister["farmers_market_url"]
    assert "Publix" in pair.retailers
    assert pair.research_todo is False


def test_atlanta_september_ingredient():
    got = resolve_this_month("US-SE-ATL", ym="2026-09")
    assert got is not None
    assert got["ingredient"] == "muscadine grapes"
    assert got["frontier_sister"] == "Sandersville, GA"


def test_unfilled_month_is_none_not_fabricated():
    pair = resolve_pair("US-SE-ATL")
    # October is a research-dispatch placeholder — must resolve to None, not a guess
    assert pair.ingredient_for("2026-10") is None


def test_sf_pescadero_pair_present_and_mapped():
    # SF/bay-area pair confirmed present in repo; indexed by both keys
    by_new = resolve_pair("US-CA-PESCADERO")
    by_legacy = resolve_pair("US-W-SF")
    assert by_new is not None
    assert by_legacy is by_new
    assert by_new.frontier_sister["place"] == "Pescadero, CA 94060"
    # mapped from existing confirmed seasonal_matrix, not fabricated
    assert by_new.ingredient_for("2027-04") == "artichokes"


def test_unknown_market_returns_none():
    assert resolve_pair("US-XX-NOWHERE") is None
    assert resolve_this_month("US-XX-NOWHERE") is None


def test_load_pairs_indexes_by_market():
    pairs = load_pairs()
    assert "US-SE-ATL" in pairs
    assert "US-CA-PESCADERO" in pairs
