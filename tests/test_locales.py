"""Retailer-frontier pairing loader — market resolves to pair + monthly ingredient."""
from creative_automation.locales import (
    FrontierPair,
    load_pairs,
    resolve_pair,
    resolve_target_languages,
    resolve_this_month,
)


def test_atlanta_pair_fully_populated():
    pair = resolve_pair("US-SE-ATL")
    assert isinstance(pair, FrontierPair)
    assert pair.metro_location["retailer"] == "Publix"
    assert "950 W Peachtree St NW" in pair.metro_location["address"]
    assert pair.metro_location["phone"] == "(404) 253-3544"
    assert pair.frontier_sister["place"] == "Senoia, GA"
    assert pair.frontier_sister["market"] == "US-GA-SENOIA"
    assert pair.frontier_sister["farmers_market_url"] is None
    assert "Publix" in pair.retailers
    assert pair.research_todo is False


def test_atlanta_september_ingredient():
    got = resolve_this_month("US-SE-ATL", ym="2026-09")
    assert got is not None
    assert got["ingredient"] == "muscadine grapes"
    assert got["frontier_sister"] == "Senoia, GA"


def test_pairs_and_flavor_layers_answer_different_questions():
    # Layer contract (see resolve_this_month / local_flavor_for docstrings):
    # Atlanta May cooks Vidalia onions (recipe ingredient) while the
    # sourcing line lists Coweta peaches/butterbeans. Different answers
    # by design — neither layer overrides the other.
    from creative_automation.local_flavor import local_flavor_for

    got = resolve_this_month("US-SE-ATL", ym="2026-05")
    assert got is not None
    assert got["ingredient"] == "Vidalia onions"
    flavor = local_flavor_for("US-SE-ATL", month=5)
    assert flavor["matched"] is True
    assert "Coweta peaches" in flavor["produce"]
    assert "Vidalia onions" not in flavor["produce"]


def test_unfilled_month_is_none_not_fabricated():
    pair = resolve_pair("US-SE-ATL")
    # October 2026 was backfilled to pecans; 2027 has no authored months, so an
    # unfilled month must resolve to None, not a guess
    assert pair.ingredient_for("2027-10") is None


def test_sf_and_pescadero_pairs_present_and_mapped():
    # Both pairs confirmed present in repo. US-W-SF has been its own market
    # since the 2026-09-15 reassignment (frontier sister Castroville) — it is
    # no longer an alias of the Pescadero pair.
    pescadero = resolve_pair("US-CA-PESCADERO")
    sf = resolve_pair("US-W-SF")
    assert pescadero is not None and sf is not None
    assert sf is not pescadero
    assert sf.market == "US-W-SF"
    assert sf.frontier_sister["place"] == "Castroville, CA"
    assert pescadero.frontier_sister["place"] == "Pescadero, CA 94060"
    # mapped from the confirmed seasonal matrix, not fabricated
    assert sf.ingredient_for("2026-04") == "artichokes"


def test_next_year_unfilled_month_degrades_gracefully():
    # pairs data is authored per calendar year; a future year with no authored
    # months keeps the pair but yields no ingredient — callers fall back,
    # nothing raises.
    got = resolve_this_month("US-SE-ATL", ym="2027-09")
    assert got is not None
    assert got["market"] == "US-SE-ATL"
    assert got["month"] == "2027-09"
    assert got["ingredient"] is None


def test_unseeded_retailers_normalize_to_empty_list():
    # Austin's pair seeds no retailers (null in JSON); callers get [] rather
    # than None so iteration never needs a guard.
    got = resolve_this_month("US-SC-AUSTIN", ym="2026-09")
    assert got is not None
    assert got["retailers"] == []


def test_unknown_market_returns_none():
    assert resolve_pair("US-XX-NOWHERE") is None
    assert resolve_this_month("US-XX-NOWHERE") is None


def test_load_pairs_indexes_by_market():
    pairs = load_pairs()
    assert "US-SE-ATL" in pairs
    assert "US-CA-PESCADERO" in pairs


def test_known_market_never_invents_a_language():
    codes = [lang["lang_code"] for lang in resolve_target_languages("US-NE-MANHATTAN")]
    assert codes[0] == "en"
    assert "pt" not in codes  # Manhattan lists Spanish only — no Portuguese fill


def test_brooklyn_resolves_spanish_and_chinese():
    codes = [lang["lang_code"] for lang in resolve_target_languages("US-NE-BROOKLYN")]
    assert codes == ["en", "es", "zh"]


def test_unknown_market_keeps_default_fill():
    codes = [lang["lang_code"] for lang in resolve_target_languages("US-XX-NOWHERE")]
    assert codes == ["en", "es", "pt"]
