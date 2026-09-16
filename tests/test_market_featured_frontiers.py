"""Market-to-featured-frontier mapping contract (issue #257, 1:1 model).

Every registry market resolves its OWN nearby frontier (no shared frontiers)
with place + ingredients + seasons + farmers-market context as data
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
    assert not shared, f"shared frontiers are back: {shared}"


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
    assert "pecan" not in atl_ings.lower() or "Senoia" in atl_ings, (
        "Atlanta kept its old Georgia-frontier ingredients after the Senoia re-point"
    )
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
