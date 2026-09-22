"""Local flavor lookup — locale + month resolves to in-season produce + source."""
import pytest

from creative_automation.local_flavor import (
    MarketFlavor,
    load_flavors,
    local_flavor_for,
    resolve_flavor,
)


def test_known_market_in_season_month():
    # Hatch green chile is Aug-Sep; September (9) is in-season
    got = local_flavor_for("US-SW-LASCRUCES", month=9)
    assert got["matched"] is True
    assert got["market"] == "US-SW-LASCRUCES"
    assert got["month"] == 9
    assert "Hatch green chile" in got["produce"]
    assert "Albertsons Las Cruces" in got["source"]


def test_known_market_out_of_season_month():
    # January (1) is outside the Hatch green chile Aug-Sep window
    got = local_flavor_for("US-SW-LASCRUCES", month=1)
    assert got["matched"] is True
    assert got["produce"] == []
    # source + months still resolve so the UI can render the sourcing line
    assert got["source"]
    assert got["months"] == [8, 9]


def test_default_fallback_for_unknown_market():
    got = local_flavor_for("US-XX-NOWHERE", month=6)
    assert got["matched"] is False
    assert got["market"] == "_default"
    assert got["produce"] == ["seasonal frontier flavor"]


def test_pescadero_artichokes_spring_window():
    # Castroville artichokes Mar-Jun — April (4) in season, July (7) out
    apr = local_flavor_for("US-CA-PESCADERO", month=4)
    assert "Castroville artichokes" in apr["produce"]
    jul = local_flavor_for("US-CA-PESCADERO", month=7)
    assert "Castroville artichokes" not in jul["produce"]
    # strawberries carry July instead
    assert "strawberries" in jul["produce"]


def test_kamas_valley_year_round():
    # grass-fed beef is year-round — in season every month
    for month in (1, 6, 12):
        got = local_flavor_for("US-UT-KAMASVALLEY", month=month)
        assert "Oakley grass-fed beef" in got["produce"]


def test_neah_bay_huckleberry_single_month():
    aug = local_flavor_for("US-WA-NEAHBAY", month=8)
    assert "huckleberry" in aug["produce"]
    assert "Makah salmon" in aug["produce"]
    jul = local_flavor_for("US-WA-NEAHBAY", month=7)
    assert "huckleberry" not in jul["produce"]
    assert "Makah salmon" in jul["produce"]


def test_invalid_month_raises():
    with pytest.raises(ValueError):
        local_flavor_for("US-SW-LASCRUCES", month=0)
    with pytest.raises(ValueError):
        local_flavor_for("US-SW-LASCRUCES", month=13)


def test_resolve_flavor_returns_dataclass():
    flavor = resolve_flavor("US-MW-PARKCITY-84098")
    assert isinstance(flavor, MarketFlavor)
    assert flavor.place.startswith("Park City")
    assert any(p.name == "Jensen Farms peaches" for p in flavor.produce)


def test_load_flavors_includes_default_and_all_seeds():
    flavors = load_flavors()
    for key in (
        "US-CA-PESCADERO",
        "US-WA-NEAHBAY",
        "US-MW-PARKCITY-84098",
        "US-SW-LASCRUCES",
        "US-UT-KAMASVALLEY",
        "_default",
    ):
        assert key in flavors


def test_sandersville_pecans_in_season_november():
    # Georgia pecans Oct-Dec — November (11) in season, resolves source + place
    got = local_flavor_for("US-SE-SANDERSVILLE", month=11)
    assert got["matched"] is True
    assert got["market"] == "US-SE-SANDERSVILLE"
    assert got["month"] == 11
    assert "Georgia pecans" in got["produce"]
    assert got["source"]
    assert "Sandersville" in got["place"]
    # peaches (May-Aug) are out of the November window
    assert "Georgia peaches" not in got["produce"]


def test_sandersville_seasonal_windows():
    # peaches May-Aug: July (7) in, November (11) out
    jul = local_flavor_for("US-SE-SANDERSVILLE", month=7)
    assert "Georgia peaches" in jul["produce"]
    assert "Georgia pecans" not in jul["produce"]
    # sweet potatoes Sep-Nov: October (10) in season
    oct_ = local_flavor_for("US-SE-SANDERSVILLE", month=10)
    assert "sweet potatoes" in oct_["produce"]


def test_sandersville_registered_wherever_atlanta_is():
    # Atlanta's rural frontier sister must be a first-class market everywhere
    # Atlanta is registered. Parity check across the canonical market registries.
    import json
    from pathlib import Path

    data_dir = Path(__file__).parents[1] / "data" / "localization"
    for fname in ("market-languages.json", "store-finder-markets.json"):
        raw = json.loads((data_dir / fname).read_text(encoding="utf-8"))
        codes = {m["market"] for m in raw["markets"]}
        assert "US-SE-ATL" in codes, f"Atlanta missing from {fname}"
        assert "US-SE-SANDERSVILLE" in codes, f"Sandersville missing from {fname}"
    # local-flavor uses a keyed markets object
    flavor = json.loads(
        (data_dir / "local-flavor.json").read_text(encoding="utf-8")
    )
    assert "US-SE-SANDERSVILLE" in flavor["markets"]


def test_languages_match_shipped_frontend_copy():
    # src/creative_automation resolves the repo-root copy while the page
    # ships the web copy; entries must match or copy changes (like the Kamas
    # september voice) silently apply on only one surface.
    import json
    from pathlib import Path

    repo = Path(__file__).parents[1]
    root = json.loads(
        (repo / "data" / "localization" / "market-languages.json").read_text(
            encoding="utf-8"
        )
    )
    web = json.loads(
        (
            repo / "web" / "kodiak-posts-for-todays-frontier" / "data"
            / "localization" / "market-languages.json"
        ).read_text(encoding="utf-8")
    )
    assert root["markets"] == web["markets"]
