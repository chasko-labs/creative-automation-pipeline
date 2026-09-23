"""New York borough markets (goal: Alvaro visit) — Brooklyn, Manhattan, Bronx
resolve end-to-end like every other market: 12 months of locale + flavor +
picks, frontend rows present, generated pairs JS in sync.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).parents[1]

BOROUGHS = ["US-NE-BROOKLYN", "US-NE-MANHATTAN", "US-NE-BRONX"]
MONTHS = [f"2026-{m:02d}" for m in range(1, 13)]


def _markets():
    return json.loads((ROOT / "data/localization/store-finder-markets.json").read_text())["markets"]


def test_borough_market_rows_exist():
    ids = {m["market"] for m in _markets()}
    for b in BOROUGHS:
        assert b in ids, b
    assert len(_markets()) == 82


def test_borough_pairs_and_flavor_registered():
    pairs = json.loads((ROOT / "data/localization/retailer-frontier-pairs.json").read_text())["pairs"]
    pair_ids = {p["market"] for p in pairs}
    flavor = json.loads((ROOT / "data/localization/local-flavor.json").read_text())["markets"]
    langs = json.loads((ROOT / "data/localization/market-languages.json").read_text())["markets"]
    lang_ids = {m["market"] for m in langs}
    for b in BOROUGHS:
        assert b in pair_ids, b
        assert b in flavor, b
        assert b in lang_ids, b


def test_borough_frontend_rows_present():
    core = (ROOT / "web/kodiak-posts-for-todays-frontier/js/data-core.js").read_text()
    disclosure = (ROOT / "web/kodiak-posts-for-todays-frontier/js/market-disclosure.js").read_text()
    pairs_js = (ROOT / "web/kodiak-posts-for-todays-frontier/js/recipes-frontier-pairs.js").read_text()
    for b in BOROUGHS:
        assert b in core, b
        assert b in disclosure, b
        assert b in pairs_js, b


def test_boroughs_resolve_twelve_months():
    from creative_automation import locales, local_flavor
    from creative_automation.recipe_card import pick_recipe_with_provenance

    for b in BOROUGHS:
        for ym in MONTHS:
            loc = locales.resolve_this_month(b, ym)
            ing = loc.ingredient if hasattr(loc, "ingredient") else loc.get("ingredient")
            assert ing, (b, ym)
            fl = local_flavor.local_flavor_for(b, int(ym.split("-")[1]))
            prod = fl.get("produce") if isinstance(fl, dict) else getattr(fl, "produce", None)
            assert prod, (b, ym)
            recipe, pairing = pick_recipe_with_provenance(ing, None, b, month=ym, season=None)
            assert recipe is not None, (b, ym)
            assert pairing.get("source") != "static-default" or not ing, (b, ym)


def test_metro_entry_has_unambiguous_display_name():
    markets = _markets()
    by_id = {m["market"]: m for m in markets}
    assert by_id["US-NE-NYC"]["place"] == "New York City"
    # filtering the picker for "Manhattan" must match exactly one market —
    # the metro entry must not shadow the borough entry.
    hits = [m["market"] for m in markets if "manhattan" in m["place"].lower()]
    assert hits == ["US-NE-MANHATTAN"], hits
    # web copy + picker seed carry the same display name (single source of truth per file).
    web = json.loads((ROOT / "web/kodiak-posts-for-todays-frontier/data/localization/store-finder-markets.json").read_text())["markets"]
    assert {m["market"]: m for m in web}["US-NE-NYC"]["place"] == "New York City"
    core = (ROOT / "web/kodiak-posts-for-todays-frontier/js/data-core.js").read_text()
    assert 'place:"New York City"' in core
    assert "Brooklyn + Manhattan" not in core
