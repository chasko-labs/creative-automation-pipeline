"""Metro-over-retailer hierarchy for the recipes brainstorm band 2.

The metro side must lead with the MARKET place ("Atlanta"), never the
retailer store name ("Publix Super Market at The Plaza Midtown"). The
retailer renders subordinate ("Publix · address"). Halo anchors carry an
explicit metro market code so the header resolves to a real place.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAIRS = ROOT / "data" / "localization" / "retailer-frontier-pairs.json"
LANG = ROOT / "web" / "kodiak-posts-for-todays-frontier" / "data" / "localization" / "market-languages.json"


def _places():
    return {m["market"]: m.get("place") or m["market"]
            for m in json.loads(LANG.read_text())["markets"]}


def test_metro_header_resolves_to_place():
    places = _places()
    pairs = json.loads(PAIRS.read_text())["pairs"]
    assert len(pairs) == 76
    for p in pairs:
        metro = p.get("metro_location") or {}
        code = metro.get("market") or p["market"]
        assert code in places, f"{p['market']}: header code {code} has no place"
        assert places[code] != code, f"{p['market']}: header falls back to raw code"


def test_halo_anchors_have_metro_market():
    pairs = {p["market"]: p for p in json.loads(PAIRS.read_text())["pairs"]}
    assert pairs["US-CA-PESCADERO"]["metro_location"]["market"] == "US-W-SANJOSE"
    assert pairs["US-CA-CASTROVILLE"]["metro_location"]["market"] == "US-W-SF"
    places = _places()
    assert places["US-W-SANJOSE"] != "US-W-SANJOSE"
    assert places["US-W-SF"] != "US-W-SF"


def test_js_header_uses_market_not_store_name():
    js = (ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js" / "recipes.js").read_text()
    assert "function placeFor(market)" in js
    assert "metro.name || metro.retailer || pair.market" not in js
