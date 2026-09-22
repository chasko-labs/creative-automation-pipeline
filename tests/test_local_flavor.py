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
    # Fargo January: deep winter, nothing scheduled yet — the honest empty
    # shape (was Las Cruces, then Boston January until each was seeded; the
    # contract is source + place resolve with produce []).
    got = local_flavor_for("US-MW-FARGO", month=1)
    assert got["matched"] is True
    assert got["produce"] == []
    # source + months still resolve so the UI can render the sourcing line
    assert got["source"]
    assert "Fargo" in got["place"]


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


def test_cincinnati_maple_march_window():
    # Ohio maple Feb-Mar — March (3) in season with Findlay Market source
    mar = local_flavor_for("US-OH-CINCINNATI", month=3)
    assert mar["matched"] is True
    assert "Ohio maple syrup" in mar["produce"]
    assert "Findlay Market" in mar["source"]
    # January is honey-only winter
    jan = local_flavor_for("US-OH-CINCINNATI", month=1)
    assert jan["produce"] == ["local honey"]


def test_dayton_shares_lebanon_belt_sweet_corn():
    # Dayton twins Cincinnati's Lebanon-belt calendar: sweet corn Jul-Aug
    aug = local_flavor_for("US-OH-DAYTON", month=8)
    assert "sweet corn" in aug["produce"]
    assert "tomatoes" in aug["produce"]


def test_oceanside_avocado_and_citrus_windows():
    # Coastal SoCal: avocados Apr-Aug, winter citrus Dec-Mar
    may = local_flavor_for("US-CA-OCEANSIDE", month=5)
    assert "avocados" in may["produce"]
    assert "Oceanside citrus" not in may["produce"]
    jan = local_flavor_for("US-CA-OCEANSIDE", month=1)
    assert "Oceanside citrus" in jan["produce"]
    assert "avocados" not in jan["produce"]


def test_wasatch_peaches_july_honey_december():
    # Wasatch Back: peaches Jul, storing honey carries December
    jul = local_flavor_for("US-MW-WASATCH", month=7)
    assert "peaches" in jul["produce"]
    dec = local_flavor_for("US-MW-WASATCH", month=12)
    assert dec["produce"] == ["local honey"]


def test_albuquerque_chile_august_pecans_december():
    # Rio Grande valley: green chile Aug-Sep, pecans close the year
    aug = local_flavor_for("US-SW-ALBQ", month=8)
    assert "green chile" in aug["produce"]
    dec = local_flavor_for("US-SW-ALBQ", month=12)
    assert "pecans" in dec["produce"]
    assert "green chile" not in dec["produce"]


def test_sacramento_mountains_honey_and_harvest():
    # Timberon honey runs year-round; Cloudcroft berries peak August
    assert "mountain honey" in local_flavor_for("US-SW-TIMBERON", month=1)["produce"]
    assert "pinon nuts" in local_flavor_for("US-SW-TIMBERON", month=11)["produce"]
    assert "u-pick berries" in local_flavor_for("US-SW-CLOUDCROFT", month=8)["produce"]
    assert "red chile ristras" in local_flavor_for("US-SW-CLOUDCROFT", month=12)["produce"]


def test_tularosa_pistachio_harvest_september():
    # Tularosa Basin pistachios peak Sep; cherries are May-Jun only
    sep = local_flavor_for("US-SW-TULAROSA", month=9)
    assert "pistachios" in sep["produce"]
    jun = local_flavor_for("US-SW-TULAROSA", month=6)
    assert "cherries" in jun["produce"]
    assert "pistachios" not in jun["produce"]


def test_jax_winter_strawberry_and_satsuma():
    # Florida winter growing season: strawberries Jan, satsuma Dec
    jan = local_flavor_for("US-SE-JAX", month=1)
    assert "strawberries" in jan["produce"]
    dec = local_flavor_for("US-SE-JAX", month=12)
    assert "satsuma citrus" in dec["produce"]


def test_las_cruces_onion_to_ristra_arc():
    # Upper Rio Grande arc: sweet onions May, dried red chile Dec
    may = local_flavor_for("US-SW-LASCRUCES", month=5)
    assert "sweet onions" in may["produce"]
    dec = local_flavor_for("US-SW-LASCRUCES", month=12)
    assert "dried red chile" in dec["produce"]


def test_twin_cities_maple_to_wild_rice():
    # Minnesota arc: maple Mar, wild rice Dec; summer berries in between
    assert "maple syrup" in local_flavor_for("US-MW-TC", month=3)["produce"]
    assert "wild rice" in local_flavor_for("US-MW-TC", month=12)["produce"]
    assert "raspberries" in local_flavor_for("US-MW-TC", month=7)["produce"]


def test_phoenix_desert_two_citrus_peaks():
    # Salt River desert: winter citrus both ends, dates through late summer
    assert "citrus (oranges and grapefruit)" in local_flavor_for("US-SW-PHX", month=1)["produce"]
    assert "dates" in local_flavor_for("US-SW-PHX", month=8)["produce"]
    assert "citrus (mandarins and grapefruit)" in local_flavor_for("US-SW-PHX", month=12)["produce"]


def test_boston_oysters_to_cranberries():
    # Massachusetts arc: aquaculture oysters Mar, cranberries Nov
    assert "oysters" in local_flavor_for("US-NE-BOS", month=3)["produce"]
    assert "cranberries" in local_flavor_for("US-NE-BOS", month=11)["produce"]
    assert "oysters" not in local_flavor_for("US-NE-BOS", month=11)["produce"]


def test_nyc_cherries_and_extended_onions():
    # Hudson Valley: sweet cherries Jun; black-dirt onions run Jul-Sep
    assert "sweet cherries" in local_flavor_for("US-NE-NYC", month=6)["produce"]
    assert "black-dirt onions" in local_flavor_for("US-NE-NYC", month=7)["produce"]
    assert "fresh cider" in local_flavor_for("US-NE-NYC", month=10)["produce"]


def test_asheville_ramps_and_sourwood():
    # Blue Ridge: ramps Apr, sourwood honey Jan storage and Jul fresh
    assert "ramps" in local_flavor_for("US-SE-ASHEVILLE", month=4)["produce"]
    jan = local_flavor_for("US-SE-ASHEVILLE", month=1)
    assert "sourwood honey" in jan["produce"]
    assert "mountain apples" not in jan["produce"]


def test_spokane_cherries_to_honey():
    # Inland NW: cherries Jun, Green Bluff peaches from Aug, honey Dec
    assert "cherries" in local_flavor_for("US-W-SPOKANE", month=6)["produce"]
    assert "peaches" in local_flavor_for("US-W-SPOKANE", month=8)["produce"]
    assert "local honey" in local_flavor_for("US-W-SPOKANE", month=12)["produce"]


def test_kc_blackberries_to_missouri_pecans():
    # Missouri arc: blackberries Jun, Missouri pecans Dec
    assert "blackberries" in local_flavor_for("US-MW-KC", month=6)["produce"]
    assert "pecans (Missouri)" in local_flavor_for("US-MW-KC", month=12)["produce"]
    assert "blackberries" not in local_flavor_for("US-MW-KC", month=12)["produce"]


def test_stl_asparagus_to_honey():
    # St Louis: asparagus Apr, honey Dec; Monroe produce covers high summer
    assert "asparagus" in local_flavor_for("US-MW-STL", month=4)["produce"]
    assert "local honey" in local_flavor_for("US-MW-STL", month=12)["produce"]


def test_milwaukee_cranberries_and_cheddar():
    # Wisconsin: cranberries Oct, aged cheddar Dec
    assert "cranberries" in local_flavor_for("US-MW-MILWAUKEE", month=10)["produce"]
    assert "aged cheddar" in local_flavor_for("US-MW-MILWAUKEE", month=12)["produce"]


def test_detroit_blueberries_to_dry_beans():
    # Michigan: blueberries Jul, dry beans Dec
    assert "blueberries" in local_flavor_for("US-MW-DETROIT", month=7)["produce"]
    assert "Michigan dry beans" in local_flavor_for("US-MW-DETROIT", month=12)["produce"]


def test_chicago_maple_to_cranberries():
    # Illinois arc: maple Mar, cranberries Dec
    assert "maple syrup" in local_flavor_for("US-MW-CHI", month=3)["produce"]
    assert "cranberries" in local_flavor_for("US-MW-CHI", month=12)["produce"]


def test_des_moines_rhubarb_to_honey():
    # Iowa: rhubarb Apr, honey Dec; Marion corn covers high summer
    assert "rhubarb" in local_flavor_for("US-MW-DESMOINES", month=4)["produce"]
    assert "local honey" in local_flavor_for("US-MW-DESMOINES", month=12)["produce"]


def test_indy_maple_to_popcorn():
    # Indiana: maple Mar, Indiana-grown popcorn Dec
    assert "maple syrup" in local_flavor_for("US-MW-INDY", month=3)["produce"]
    assert "popcorn (Indiana-grown)" in local_flavor_for("US-MW-INDY", month=12)["produce"]


def test_san_diego_citrus_to_cider():
    # Julian halo: lowland citrus Feb, apple cider Dec, peaches Jul peak
    assert "citrus (lowland)" in local_flavor_for("US-W-SD", month=2)["produce"]
    assert "peaches" in local_flavor_for("US-W-SD", month=7)["produce"]
    assert "apple cider" in local_flavor_for("US-W-SD", month=12)["produce"]


def test_santa_fe_pinon_to_ristras():
    # High desert follow-through: pinon Jan storage, ristras Dec
    assert "pinon" in local_flavor_for("US-SW-SANTA FE", month=1)["produce"]
    assert "red chile ristras" in local_flavor_for("US-SW-SANTA FE", month=12)["produce"]
    assert "pecans" in local_flavor_for("US-SW-SANTA FE", month=11)["produce"]


def test_lowcountry_okra_to_peanuts():
    # Lowcountry: okra Jul, boiled peanuts Oct, storage sweets to close
    assert "okra" in local_flavor_for("US-SE-COAST", month=7)["produce"]
    assert "boiled peanuts" in local_flavor_for("US-SE-COAST", month=10)["produce"]
    assert "sweet potatoes" in local_flavor_for("US-SE-COAST", month=12)["produce"]


def test_louisville_strawberries_to_ham():
    # Kentucky: strawberries May, country ham Dec
    assert "strawberries" in local_flavor_for("US-SE-LOU", month=5)["produce"]
    assert "country ham" in local_flavor_for("US-SE-LOU", month=12)["produce"]


def test_san_antonio_1015_to_citrus():
    # South Texas: 1015 onions Apr, citrus Dec, winter greens both ends
    assert "1015 Texas Sweet onions" in local_flavor_for("US-SC-SANANTONIO", month=4)["produce"]
    assert "citrus" in local_flavor_for("US-SC-SANANTONIO", month=12)["produce"]
    assert "winter greens" in local_flavor_for("US-SC-SANANTONIO", month=1)["produce"]
