"""Market-to-featured-frontier mapping contract (issue #257).

Every market in the 74-market registry resolves one featured frontier with
place + ingredients + seasons + farmers-market context as data
(data/localization/market-featured-frontiers.json). The web runtime mirrors
that file inline in js/data-core.js and generate.js resolves its hint from
the mapping — no hardcoded market checks.
"""
import json
import re
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

FRONTIERS = {
    "US-CA-PESCADERO",
    "US-WA-NEAHBAY",
    "US-SE-SANDERSVILLE",
    "US-SW-TIMBERON",
}


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def test_mapping_covers_every_registry_market() -> None:
    registry = {m["market"] for m in _load(REGISTRY)["markets"]}
    mapping = _load(MAPPING)["markets"]
    assert set(mapping) == registry, (
        f"only_registry={sorted(registry - set(mapping))} "
        f"only_mapping={sorted(set(mapping) - registry)}"
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
    assert not failures, "mapping gaps:\n" + "\n".join(failures)


def test_frontier_targets_are_real_and_self_resolve() -> None:
    mapping = _load(MAPPING)["markets"]
    for code, entry in mapping.items():
        assert entry["frontier_market"] in FRONTIERS, (
            f"{code} points at unknown frontier {entry['frontier_market']}"
        )
    for frontier in FRONTIERS:
        assert mapping[frontier]["frontier_market"] == frontier, (
            f"{frontier} does not self-resolve"
        )


def test_sf_bay_links_castroville_artichokes_mar_jun_via_own_entry() -> None:
    entry = _load(MAPPING)["markets"]["US-W-SF"]
    assert entry["frontier_market"] == "US-CA-PESCADERO"
    artichokes = [i for i in entry["ingredients"] if "artichoke" in i["name"].lower()]
    assert artichokes, "US-W-SF entry carries no artichokes"
    assert artichokes[0]["months"] == [3, 4, 5, 6]
    assert "Mar-Jun" in entry["seasons"]
    assert "Pescadero" in entry["place"]
    assert entry["farmers_market"]


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
