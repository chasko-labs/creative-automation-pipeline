"""Offline validation of the theme-asset-map artifact.

No network. Asserts the committed data/products/theme-asset-map.json is
well-formed, covers all chip themes, resolves only real DAM keys, and that
the thematic routing landed on-theme (wild-grizzly-bears -> wild-habitat
set, not an obvious captive-bear close-up).
"""
from __future__ import annotations

import json
import pathlib
import re

MAP_PATH = pathlib.Path("data/products/theme-asset-map.json")
# Committed fixture is the source of truth in CI (no /tmp scratch there);
# fall back to the legacy /tmp scratch path only if the fixture is absent.
_FIXTURE_KEYS = pathlib.Path(__file__).parent / "fixtures" / "dam-real-keys.txt"
_TMP_KEYS = pathlib.Path("/tmp/dam-real-keys.txt")
DAM_KEYS_PATH = _FIXTURE_KEYS if _FIXTURE_KEYS.exists() else _TMP_KEYS
DAM_PREFIX = "brands/kodiak/raw-ingest/kodiakcakes/images/"
VARIANT_SUFFIX_RE = re.compile(r"_\d+x\d+(?=\.[a-z0-9]+$)", re.IGNORECASE)

EXPECTED_THEMES = {
    "wild-grizzly-bears",
    "recipe-cards",
    "localized-costco",
    "localized-publix",
    "localized-target",
    "kodiak-subscription",
    "riff-on-past-content",
    "us-ski-snowboard",
}

# on-theme evidence tokens for the unified wild angle (wild-habitat set)
WILD_TOKENS = (
    "grizzly",
    "wild",
    "meadow",
    "trail",
    "habitat",
    "corridor",
    "vital",
    "frontier",
    "wasatch",
)

# captive-bear-closeup cues that the bears theme must not obviously land on
CAPTIVE_BEAR_TOKENS = ("captive", "zoo", "enclosure", "cage", "petting", "handler")


def _load_map() -> dict:
    assert MAP_PATH.exists(), f"{MAP_PATH} not found — build it first"
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


def _load_real_keys() -> set[str]:
    assert DAM_KEYS_PATH.exists(), f"{DAM_KEYS_PATH} not found — needed to verify real keys"
    return {line.strip() for line in DAM_KEYS_PATH.read_text().splitlines() if line.strip()}


def test_json_loads_and_has_map():
    data = _load_map()
    assert isinstance(data, dict)
    assert "map" in data and isinstance(data["map"], dict)
    assert "metadata" in data


def test_all_theme_slugs_present():
    data = _load_map()
    assert set(data["map"].keys()) == EXPECTED_THEMES


def test_every_photo_key_is_real_dam_path_no_variant_suffix():
    data = _load_map()
    for slug, entry in data["map"].items():
        pk = entry["photo_key"]
        assert pk.startswith(DAM_PREFIX), f"{slug}: photo_key not a DAM path: {pk}"
        base = pk[len(DAM_PREFIX):]
        # no unstripped _NNNNxNNNN variant suffix survives in a chosen key.
        # (native-suffix real keys are allowed, but those exist verbatim in the
        # real-key set — checked separately in the real-key test.)
        assert VARIANT_SUFFIX_RE.search(base) is None or base in _load_real_keys(), (
            f"{slug}: photo_key carries a variant suffix and is not a real key: {pk}"
        )


def test_every_entry_resolves_and_is_never_null():
    data = _load_map()
    for slug, entry in data["map"].items():
        assert entry.get("photo_key"), f"{slug}: null/empty photo_key"
        assert entry.get("image_file"), f"{slug}: null/empty image_file"


def test_every_pool_entry_is_a_real_dam_path():
    data = _load_map()
    real = _load_real_keys()
    for slug, entry in data["map"].items():
        pool = entry.get("pool", [])
        assert pool, f"{slug}: empty pool"
        for pk in pool:
            assert pk.startswith(DAM_PREFIX), f"{slug}: pool entry not a DAM path: {pk}"
            base = pk[len(DAM_PREFIX):]
            assert base in real, f"{slug}: pool entry not a real DAM key: {base}"
        # primary photo_key must be the head of the pool
        assert entry["photo_key"] == pool[0], f"{slug}: photo_key is not pool[0]"


def test_all_primaries_are_distinct_photo_keys():
    # FLAG 2 de-dup guarantee: no two themes may share the same primary
    # photo_key. Pools may overlap; primaries must be globally unique.
    data = _load_map()
    primaries = [entry["photo_key"] for entry in data["map"].values()]
    expected = len(EXPECTED_THEMES)
    assert len(primaries) == expected, f"expected {expected} primaries, got {len(primaries)}"
    assert len(set(primaries)) == expected, (
        f"primary photo_keys are not all distinct: {sorted(primaries)}"
    )


def test_wild_grizzly_bears_lands_on_habitat_set():
    # unified wild angle: the primary must read as wild-habitat, and must not
    # obviously be a captive-bear close-up. Guardrail documented on the entry.
    data = _load_map()
    entry = data["map"]["wild-grizzly-bears"]
    blob = (entry["image_file"] + " " + (entry.get("caption") or "")).lower()
    assert any(tok in blob for tok in WILD_TOKENS), (
        f"wild-grizzly-bears primary is not from the wild-habitat set: {blob!r}"
    )
    for tok in CAPTIVE_BEAR_TOKENS:
        assert tok not in blob, (
            f"wild-grizzly-bears asset looks like a captive-bear closeup ({tok!r}): {blob!r}"
        )
    assert "guardrail" in entry, "wild-grizzly-bears entry must document its guardrail"


def test_retired_slugs_are_gone():
    # zac-efron (named-person angle, removed) and the two pre-unification wild
    # slugs must not resurface in the map.
    data = _load_map()
    for slug in ("zac-efron", "bears", "keep-it-wild-program"):
        assert slug not in data["map"], f"retired slug still present: {slug}"
