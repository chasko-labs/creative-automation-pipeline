"""Market-to-featured-frontier mapping contract (issue #257).

Every registry market resolves its nearby frontier (only the declared
Cincinnati+Dayton share of Lebanon is shared) with place + ingredients +
seasons + farmers-market context as data
(data/localization/market-featured-frontiers.json). That JSON is GENERATED from
web/kodiak-posts-for-todays-frontier/js/data-core.js via
scripts/build-frontier-mapping.py `--check` pins the agreement — data-core.js
is the single source of truth, the JSON is its mirror.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data" / "localization"
MAPPING = DATA / "market-featured-frontiers.json"
REGISTRY = DATA / "store-finder-markets.json"
FRONTEND_DATA = (
    REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js" / "data-core.js"
)
GENERATE_JS = (
    REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js" / "generate.js"
)
BUILDER = REPO_ROOT / "scripts" / "build-frontier-mapping.py"


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_mapping_covers_every_registry_market() -> None:
    registry = {m["market"] for m in _load(REGISTRY)["markets"]}
    mapping = _load(MAPPING)["markets"]
    assert not (registry - set(mapping)), (
        f"registry markets without a frontier: {sorted(registry - set(mapping))}"
    )


def test_every_entry_has_place_ingredients_seasons_market_context() -> None:
    failures = []
    for code, entry in _load(MAPPING)["markets"].items():
        for field in ("place", "seasons", "farmers_market", "frontier_market", "link_note"):
            if not entry.get(field):
                failures.append(f"{code}: empty {field}")
        ingredients = entry.get("ingredients") or []
        if not ingredients:
            failures.append(f"{code}: no ingredients")
        for ing in ingredients:
            if not ing.get("name"):
                failures.append(f"{code}: ingredient without name")
            months = ing.get("months")
            if months is not None:
                bad = [m for m in months if not 1 <= int(m) <= 12]
                if bad:
                    failures.append(f"{code}: months out of 1-12: {bad}")
    assert not failures, "mapping gaps:\n" + "\n".join(failures)


ALLOWED_SHARES = {"US-OH-LEBANON": {"US-OH-CINCINNATI", "US-OH-DAYTON"}}


def test_no_shared_frontiers_every_target_self_resolves() -> None:
    mapping = _load(MAPPING)["markets"]
    served: dict[str, list[str]] = {}
    for code, entry in mapping.items():
        fk = entry["frontier_market"]
        assert fk in mapping, f"{code} points at unknown frontier {fk}"
        assert mapping[fk]["frontier_market"] == fk, (
            f"frontier {fk} does not self-resolve"
        )
        if code != fk:
            served.setdefault(fk, []).append(code)
    shared = {k: v for k, v in served.items() if len(v) > 1}
    unexpected = {
        k: v for k, v in shared.items() if set(v) != ALLOWED_SHARES.get(k, set())
    }
    assert not unexpected, f"shared frontiers are back: {unexpected}"


def test_ohio_metro_pair_shares_lebanon_frontier() -> None:
    # Lebanon is Cincinnati's + Dayton's featured frontier — never its own
    # selectable market, and Dayton never self-resolves.
    mapping = _load(MAPPING)["markets"]
    for code in ("US-OH-CINCINNATI", "US-OH-DAYTON"):
        entry = mapping[code]
        assert entry["frontier_market"] == "US-OH-LEBANON", code
        assert "Lebanon" in entry["place"], code
    assert mapping["US-OH-LEBANON"]["frontier_market"] == "US-OH-LEBANON"
    text = FRONTEND_DATA.read_text(encoding="utf-8")
    places = re.findall(r'\{market:"(US-[A-Z0-9 -]+)"', text)
    assert "US-OH-LEBANON" not in places, "Lebanon is selectable in the picker"
    assert "US-OH-CINCINNATI" in places and "US-OH-DAYTON" in places
    assert '"US-OH-DAYTON": "US-OH-LEBANON"' in text


def test_sf_bay_links_bolinas_goat_cheese_via_own_entry() -> None:
    entry = _load(MAPPING)["markets"]["US-W-SF"]
    assert entry["frontier_market"] == "US-CA-BOLINAS"
    cheese = [i for i in entry["ingredients"] if "goat cheese" in i["name"].lower()]
    assert cheese, "US-W-SF entry carries no goat cheese"
    assert cheese[0]["months"] == [2, 3, 4, 5, 6]
    assert "Bolinas" in entry["place"]
    assert entry["farmers_market"]


def test_repointed_markets_keep_no_stale_ingredients() -> None:
    mapping = _load(MAPPING)["markets"]
    atl_ings = " ".join(i["name"] for i in mapping["US-SE-ATL"]["ingredients"])
    assert "Sandersville" not in mapping["US-SE-ATL"]["place"]
    # gh #305: pecans are now a deliberately seeded Senoia calendar entry
    # (Oct-Nov), not a stale Sandersville leftover.
    assert "pecan" in atl_ings.lower()
    sf_ings = " ".join(i["name"] for i in mapping["US-W-SF"]["ingredients"])
    assert "artichoke" not in sf_ings.lower(), (
        "SF kept Pescadero artichokes after the Bolinas re-point"
    )


def test_generate_js_has_no_hardcoded_market_hint() -> None:
    text = GENERATE_JS.read_text(encoding="utf-8")
    for code in ("US-W-SF", "US-W-SEA", "US-WA-NEAHBAY", "US-CA-PESCADERO"):
        assert f".includes('{code}')" not in text, (
            f"generate.js still hardcodes {code}"
        )
    assert "featuredFrontierFor" in text, (
        "generate.js does not resolve its hint from the mapping"
    )


def test_inline_mirror_covers_every_frontend_market() -> None:
    text = FRONTEND_DATA.read_text(encoding="utf-8")
    codes = re.findall(r'market:"(US-[A-Z]{1,3}-[A-Z0-9 -]+)"', text)
    frontend = list(dict.fromkeys(codes))
    for marker in (
        "// #257 mapping start",
        "featuredFrontierFor",
        "marketFeaturedFrontier",
    ):
        assert marker in text, f"data-core.js missing {marker}"
    mirror = dict(
        re.findall(r'"(US-[A-Z0-9 -]+)": "(US-[A-Z0-9 -]+)"', text)
    )
    missing = [c for c in frontend if c not in mirror]
    assert not missing, f"inline mirror missing frontend markets: {missing}"
    # spot-check: the inline SF Bay entry agrees with the canonical JSON
    mapping = _load(MAPPING)["markets"]["US-W-SF"]
    assert mirror["US-W-SF"] == mapping["frontier_market"]
    assert mapping["place"] in text
    assert mapping["seasons"] in text


def test_committed_json_regenerates_from_data_core() -> None:
    proc = subprocess.run(
        [sys.executable, str(BUILDER), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, (
        "backend mapping JSON drifted from data-core.js — "
        f"run scripts/build-frontier-mapping.py\n{proc.stdout}{proc.stderr}"
    )


def _covering(entry: dict, month: int) -> list[dict]:
    """Ingredients whose months include `month` (null-month entries excluded —
    they cannot resolve a peak month)."""
    return [
        i
        for i in entry.get("ingredients") or []
        if isinstance(i.get("months"), list) and month in i["months"]
    ]


def test_sf_seed_expansion_apples_pears_september_squash_fall() -> None:
    # gh #305 sourced calendar: SF Bay Area apples/pears Sep, squash Oct-Nov,
    # year-round markets. Generic "coastal produce" placeholder is gone.
    mapping = _load(MAPPING)["markets"]
    for code in ("US-W-SF", "US-CA-BOLINAS"):
        entry = mapping[code]
        names = [i["name"] for i in entry["ingredients"]]
        assert "coastal produce" not in [n.lower() for n in names]
        sept = {i["name"] for i in _covering(entry, 9)}
        assert {"apples", "pears"} <= sept, f"{code} Sep: {sorted(sept)}"
        for name in ("apples", "pears"):
            ing = next(i for i in entry["ingredients"] if i["name"] == name)
            assert ing["months"] == [9] and ing.get("peak") == 9, (code, ing)
        squash = next(i for i in entry["ingredients"] if i["name"] == "squash")
        assert squash["months"] == [10, 11], (code, squash)
        assert "year-round" in entry["farmers_market"].lower(), code


def test_atl_seed_expansion_peach_peak_pecans_collards_flagged() -> None:
    # gh #305 sourced calendar: Georgia peaches May-Aug peak Jul, pecans
    # Oct-Nov, collards post-frost (frost timing unconfirmed — research
    # dispatch, never presented as fact).
    mapping = _load(MAPPING)["markets"]
    for code in ("US-SE-ATL", "US-GA-SENOIA"):
        entry = mapping[code]
        july = {i["name"] for i in _covering(entry, 7)}
        assert "Coweta peaches" in july, f"{code} Jul: {sorted(july)}"
        peach = next(
            i for i in entry["ingredients"] if i["name"] == "Coweta peaches"
        )
        assert peach["months"] == [5, 6, 7, 8] and peach.get("peak") == 7, (
            code,
            peach,
        )
        october = {i["name"] for i in _covering(entry, 10)}
        assert "pecans" in october, f"{code} Oct: {sorted(october)}"
        pecan = next(i for i in entry["ingredients"] if i["name"] == "pecans")
        assert pecan["months"] == [10, 11], (code, pecan)
        collards = next(
            i for i in entry["ingredients"] if i["name"] == "collards"
        )
        assert collards["months"] is None, (code, collards)
        assert "research dispatch" in (collards.get("note") or ""), (
            code,
            collards,
        )


def test_parkcity_seed_expansion_cherries_to_tomatoes() -> None:
    # gh #305 sourced calendar: tart cherries Jul, peaches Aug-Sep, apples
    # Sep-Oct, corn/tomatoes mid-Jul to late Sep. Null-month/generic
    # placeholders (Splendor Valley, Rodeo Grounds farm stands) are gone.
    mapping = _load(MAPPING)["markets"]
    for code in ("US-MW-PARKCITY-84098", "US-UT-OAKLEY"):
        entry = mapping[code]
        names = [i["name"] for i in entry["ingredients"]]
        assert not any("splendor" in n.lower() for n in names), (code, names)
        assert not any("farm stands" in n.lower() for n in names), (code, names)
        assert all(
            isinstance(i.get("months"), list) for i in entry["ingredients"]
        ), (code, names)
        july = {i["name"] for i in _covering(entry, 7)}
        assert {"tart cherries", "sweet corn", "tomatoes"} <= july, (
            code,
            sorted(july),
        )
        cherry = next(
            i for i in entry["ingredients"] if i["name"] == "tart cherries"
        )
        assert cherry["months"] == [7] and cherry.get("peak") == 7, (
            code,
            cherry,
        )
        sept = {i["name"] for i in _covering(entry, 9)}
        assert {"peaches", "apples", "sweet corn", "tomatoes"} <= sept, (
            code,
            sorted(sept),
        )
        assert next(
            i for i in entry["ingredients"] if i["name"] == "peaches"
        )["months"] == [8, 9]
        assert next(
            i for i in entry["ingredients"] if i["name"] == "apples"
        )["months"] == [9, 10]


JULIAN_MARKET_LINE = (
    "Julian Certified Farmers Market, Sundays 11-4 year-round, "
    "4470 Julian Rd Hwy 78"
)
JULIAN_FARMS = ["Julian Farm and Orchard", "Volcan Valley Apple Farm"]


def test_julian_row_uses_certified_market_with_farms() -> None:
    # gh #280 acceptance: the Julian entry is complete per the example —
    # certified market line plus the two named farms. No coop is confirmed,
    # so no coops key is presented as fact.
    mapping = _load(MAPPING)["markets"]
    for code in ("US-W-SD", "US-CA-JULIAN"):
        entry = mapping[code]
        assert entry["frontier_market"] == "US-CA-JULIAN", code
        assert entry["farmers_market"] == JULIAN_MARKET_LINE, code
        assert "research dispatch" not in entry["farmers_market"].lower(), code
        assert entry.get("farms") == JULIAN_FARMS, code
        assert "coops" not in entry, code


def test_frontier_schema_supports_farms_coops() -> None:
    # gh #280: farms[]/coops[] ride from data-core.js detail entries into the
    # JSON rows verbatim; rows without them carry no such keys.
    import importlib.util as _ilu

    spec = _ilu.spec_from_file_location("build_frontier_mapping", str(BUILDER))
    assert spec and spec.loader
    build = _ilu.module_from_spec(spec)
    spec.loader.exec_module(build)
    detail = build.parse_detail_block(FRONTEND_DATA.read_text(encoding="utf-8"))
    assert detail["US-CA-JULIAN"]["farms"] == JULIAN_FARMS
    assert detail["US-CA-JULIAN"]["coops"] is None
    assert detail["US-CA-PESCADERO"]["farms"] is None
    assert detail["US-CA-PESCADERO"]["coops"] is None
    mapping = _load(MAPPING)["markets"]
    assert mapping["US-CA-JULIAN"]["farms"] == JULIAN_FARMS
    assert "coops" not in mapping["US-CA-JULIAN"]
    assert "farms" not in mapping["US-CA-PESCADERO"]
    assert "farms" not in mapping["US-CA-CASTROVILLE"]
    assert "coops" not in mapping["US-CA-PESCADERO"]


def test_pescadero_castroville_rows_stay_frozen() -> None:
    # gh #280 directive: Pescadero (coastal farm stands, goat cheese,
    # berries) and Castroville (artichoke capital) are first-class concrete
    # examples — their rows must not drift under this sprint.
    mapping = _load(MAPPING)["markets"]
    pesc = mapping["US-CA-PESCADERO"]
    assert pesc["farmers_market"] == (
        "Half Moon Bay Farmers Market (Saturdays) + Harley Farms Goat Dairy "
        "farm stand, Pescadero"
    )
    assert [i["name"] for i in pesc["ingredients"]] == [
        "Castroville artichokes",
        "Marin goat cheese",
        "strawberries",
        "Brussels sprouts",
        "olive oil (fall press)",
    ]
    cast = mapping["US-CA-CASTROVILLE"]
    assert cast["farmers_market"] == (
        "Castroville artichoke stands + Monterey Bay farmers markets "
        "(standalone URL unconfirmed \u2014 research dispatch)"
    )
    assert [i["name"] for i in cast["ingredients"]] == [
        "Castroville artichokes",
        "strawberries",
        "Brussels sprouts",
    ]
