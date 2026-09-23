"""Season-26 coverage (gh #313): all 26 seasonal dropdown options resolve to
real catalog pairings; garbage stays quiet.

The dropdown offers 12 months + 4 seasons + 10 holidays. Months map to their
meteorological season key; holidays carry dedicated pairings; everything else
lands on the static default without raising. Covered in BOTH the recipe-card
path (pick_recipe_with_provenance) and the preview Lambda path
(_season_pairing), plus a dropdown audit that parses market-disclosure.js and
asserts every offered option resolves to season-table (i.e. the prune set is
empty).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from creative_automation import season_pairing as sp

# Frontend display strings, exactly as built in market-disclosure.js.
MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]
SEASONS = ["Spring", "Summer", "Fall", "Winter"]
HOLIDAYS = [
    "New Year", "Valentine\u2019s Day", "Easter", "Memorial Day",
    "Fourth of July", "Labor Day", "Halloween", "Thanksgiving",
    "Christmas", "Holiday season",
]

MONTH_TO_SEASON_KEY = {
    "January": "winter", "February": "winter", "March": "spring",
    "April": "spring", "May": "spring", "June": "summer",
    "July": "summer", "August": "summer", "September": "fall",
    "October": "fall", "November": "fall", "December": "winter",
}
SEASON_RECIPE = {
    "spring": "single-serve-lemon-ricotta-flapjack-cup",
    "summer": "cherry-pie-bars",
    "fall": "pumpkin-oat-muffins",
    "winter": "campfire-baked-apple-oats",
}
HOLIDAY_RECIPE = {
    "Christmas": "christmas-tree-waffles",
    "Holiday season": "holiday-sugar-cookies",
    "Halloween": "baked-halloween-doughnuts",
    "Easter": "easter-egg-pancakes",
    "Thanksgiving": "pumpkin-pie",
    "Fourth of July": "smores-brookies",
    "Memorial Day": "grilled-peaches-and-granola",
    "Labor Day": "single-serve-s-mores-brownie",
    "Valentine\u2019s Day": "berry-chia-pudding",
    "New Year": "apple-cider-donuts",
}

ALL_26 = MONTHS + SEASONS + HOLIDAYS


def _catalog_ids() -> set[str]:
    from creative_automation.recipe_card import RECIPES_PATH

    return {r.get("id") for r in json.loads(Path(RECIPES_PATH).read_text(encoding="utf-8"))}


# --------------------------------------------------------------------------- #
# pairing table: every option resolves season-table
# --------------------------------------------------------------------------- #

def test_all_26_options_resolve_season_table():
    assert len(ALL_26) == 26
    for opt in ALL_26:
        pairing = sp.pairing_for_season(opt)
        assert pairing["source"] == "season-table", f"{opt!r} lands on static-default"
        assert pairing["recipe_id"]
        assert pairing["reason"], f"no pairing reason for {opt!r}"


def test_months_map_to_season_keys():
    for month, season in MONTH_TO_SEASON_KEY.items():
        pairing = sp.pairing_for_season(month)
        assert pairing["recipe_id"] == SEASON_RECIPE[season], month
        assert sp.pairing_season_label(month) == season, month


def test_seasons_resolve_their_records():
    for display, season in zip(SEASONS, ("spring", "summer", "fall", "winter")):
        pairing = sp.pairing_for_season(display)
        assert pairing["recipe_id"] == SEASON_RECIPE[season], display


def test_holidays_resolve_dedicated_records():
    for holiday, recipe_id in HOLIDAY_RECIPE.items():
        pairing = sp.pairing_for_season(holiday)
        assert pairing["recipe_id"] == recipe_id, holiday
        assert pairing["source"] == "season-table"
        assert pairing["reason"], f"no pairing reason for {holiday!r}"


def test_holiday_normalization_variants():
    assert sp.normalize_holiday("Valentine\u2019s Day") == "valentine's day"
    assert sp.normalize_holiday("valentine's day") == "valentine's day"
    assert sp.normalize_holiday("VALENTINES DAY") == "valentine's day"
    assert sp.normalize_holiday("  Christmas  ") == "christmas"
    assert sp.normalize_holiday("HOLIDAY SEASON") == "holiday season"
    assert sp.pairing_for_season("valentines day")["recipe_id"] == "berry-chia-pudding"


def test_every_paired_id_is_a_real_catalog_record():
    ids = _catalog_ids()
    for opt in ALL_26:
        recipe_id = sp.pairing_for_season(opt)["recipe_id"]
        assert recipe_id in ids, f"{opt!r} pairs to missing record {recipe_id!r}"
    assert sp.DEFAULT_PAIRING["recipe_id"] in ids


# --------------------------------------------------------------------------- #
# garbage stays quiet
# --------------------------------------------------------------------------- #

_GARBAGE = [None, "", "   ", "monsoon", "not-a-season", 123, 4.5, {}, [], "2026-13"]


@pytest.mark.parametrize("bad", _GARBAGE)
def test_garbage_lands_on_static_default_quietly(bad):
    pairing = sp.pairing_for_season(bad)
    assert pairing["source"] == "static-default"
    assert pairing["recipe_id"] == sp.DEFAULT_PAIRING["recipe_id"]
    assert pairing["reason"] == sp.DEFAULT_PAIRING["reason"]
    assert sp.normalize_holiday(bad) is None
    assert sp.pairing_season_label(bad) is None
    req = sp.resolve_request(bad)
    assert req == {"kind": None, "key": None, "season": None}


# --------------------------------------------------------------------------- #
# recipe-card path: unmatched ingredient serves the table for all 26
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("opt", ALL_26)
def test_recipe_card_path_serves_table_for_every_option(opt):
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("zzqx unobtanium", None, season=opt)
    assert pairing["source"] == "season-table", opt
    assert recipe is not None, opt
    assert recipe["id"] == pairing["recipe_id"] == sp.pairing_for_season(opt)["recipe_id"], opt
    assert pairing["season"] == sp.pairing_season_label(opt), opt
    assert pairing["reason"]


@pytest.mark.parametrize("opt", ALL_26)
def test_empty_subject_serves_table_for_every_option(opt):
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("", None, season=opt)
    assert pairing["source"] == "season-table", opt
    assert recipe is not None, opt
    assert recipe["id"] == sp.pairing_for_season(opt)["recipe_id"], opt


# --------------------------------------------------------------------------- #
# preview Lambda path: _season_pairing names the record for all 26
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("opt", ALL_26)
def test_lambda_preview_path_names_pairing_for_every_option(opt):
    import creative_automation.generate_lambda as gl

    rec, meta = gl._season_pairing(opt)
    assert rec is not None, opt
    assert meta.get("source") == "season-table", opt
    assert meta.get("recipe_id") == rec.get("id") == sp.pairing_for_season(opt)["recipe_id"], opt
    assert isinstance(meta.get("name"), str) and meta["name"].strip(), opt
    assert meta.get("reason")


@pytest.mark.parametrize("bad", _GARBAGE)
def test_lambda_preview_path_garbage_stays_quiet(bad):
    import creative_automation.generate_lambda as gl

    rec, meta = gl._season_pairing(bad)
    # Garbage never raises and never claims a table hit: either unpaired or
    # the static default (the preview panel only names season-table hits).
    assert meta.get("source") in (None, "static-default")


def test_lambda_preview_panel_names_holiday_pairing():
    import creative_automation.generate_lambda as gl

    prov: dict = {}
    data = {"product": "power-cakes", "market": "us", "season": "Christmas"}
    campaign = gl._preview_campaign_data(data, "christmas brief", prov)
    # Full catalog records never truncate into the tease shape ...
    assert campaign["recipe_fields"]["title"] == gl._recipe_card_defaults("Power Cakes")["title"]
    # ... but the panel names the real pairing with table traceability.
    assert prov["recipe"] == "Christmas Tree Waffles"
    assert prov["recipe_pairing"]["recipe_id"] == "christmas-tree-waffles"
    assert prov["recipe_pairing"]["source"] == "season-table"


# --------------------------------------------------------------------------- #
# campaign path: brief season threads months + holidays
# --------------------------------------------------------------------------- #

def test_brief_season_threads_months_and_holidays():
    from creative_automation.campaign import _brief_season

    assert _brief_season({"season": "summer"}) == "summer"
    assert _brief_season({"season": "January"}) == "winter"
    assert _brief_season({"season": "Christmas"}) == "christmas"
    assert _brief_season({"season": "Valentine\u2019s Day"}) == "valentine's day"
    assert _brief_season({"season": "monsoon"}) is None
    assert _brief_season({"campaign_message": "our winter wonderland sale"}) is None


# --------------------------------------------------------------------------- #
# dropdown audit: every offered option resolves, or it must be pruned
# --------------------------------------------------------------------------- #

def _dropdown_options() -> list[str]:
    root = Path(__file__).parents[1]
    js = (root / "web" / "kodiak-posts-for-todays-frontier" / "js" / "market-disclosure.js").read_text(
        encoding="utf-8"
    )

    def _array(name: str) -> list[str]:
        m = re.search(r"var %s = \[(.*?)\];" % name, js, re.DOTALL)
        assert m, f"{name} array not found in market-disclosure.js"
        raw = re.findall(r"'((?:[^'\\]|\\.)*)'", m.group(1))
        return [r.replace("\\u2019", "\u2019").replace("\\u2018", "\u2018") for r in raw]

    return _array("months") + _array("seasons") + _array("holidays")


def test_dropdown_audit_every_option_resolves_or_is_pruned():
    options = _dropdown_options()
    assert len(options) == 26, f"dropdown offers {len(options)} options, expected 26"
    unpairable = [
        opt for opt in options if sp.pairing_for_season(opt)["source"] != "season-table"
    ]
    assert unpairable == [], f"options landing on static-default must be pruned: {unpairable}"


# --------------------------------------------------------------------------- #
# geo fallback: every picker market resolves offline ("my location")
# --------------------------------------------------------------------------- #

def test_every_place_has_offline_geo_fallback():
    # market-disclosure.js seeds GEO_FALLBACK for offline/file:// use; the
    # finder JSON enriches it when online. A picker market without built-in
    # coords can never win "my location" offline.
    root = Path(__file__).parents[1]
    web = root / "web" / "kodiak-posts-for-todays-frontier"
    disclosure = (web / "js" / "market-disclosure.js").read_text(encoding="utf-8")
    have = set(re.findall(r"'(US-[^']+)':\{lat:", disclosure))
    core = (web / "js" / "data-core.js").read_text(encoding="utf-8")
    places = set(re.findall(r'\{market:"([^"]*)"', core))
    missing = sorted(places - have)
    assert not missing, f"picker markets without offline geo fallback: {missing}"
