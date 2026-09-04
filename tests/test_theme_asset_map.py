"""Offline validation of the theme-asset-map artifact.

No network. Asserts the committed data/products/theme-asset-map.json is
well-formed, covers all 6 chip themes, resolves only real DAM keys, and that
the thematic routing landed on-theme (zac-efron -> athlete/lifestyle set;
bears -> not an obvious captive-bear close-up).
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
    "zac-efron",
    "bears",
    "recipe-cards",
    "localized-costco",
    "riff-on-past-content",
    "keep-it-wild-program",
}

# on-theme evidence tokens for the zac-efron chip (real athlete/lifestyle set)
ZAC_TOKENS = (
    "athlete",
    "zac",
    "cooking",
    "lifestyle",
    "olson",
    "harrington",
    "schweizer",
    "watson",
    "lichter",
    "outdoor",
    "family",
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


def test_all_six_theme_slugs_present():
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


def test_all_six_primaries_are_distinct_photo_keys():
    # FLAG 2 de-dup guarantee: no two themes may share the same primary
    # photo_key. Pools may overlap; primaries must be globally unique.
    data = _load_map()
    primaries = [entry["photo_key"] for entry in data["map"].values()]
    assert len(primaries) == 6, f"expected 6 primaries, got {len(primaries)}"
    assert len(set(primaries)) == 6, (
        f"primary photo_keys are not all distinct: {sorted(primaries)}"
    )


# athlete/lifestyle signal regex the zac-efron primary image_file must match
# (FLAG 1 filename boost lands a real licensed brand-athlete/lifestyle asset).
ZAC_SIGNAL_RE = re.compile(
    r"athlete|schweizer|harrington|olson|watson|lichter|"
    r"cooking-with-zac|cooking_with_zac|outdoor-cooking-family|"
    r"family-lifestyle|climbing-lifestyle|athlete_image|zac|efron",
    re.IGNORECASE,
)


def test_zac_efron_primary_image_file_matches_athlete_signal():
    # FLAG 1: zac-efron primary must be a real named-athlete / lifestyle file,
    # not a generic food shot. Assert on the image_file basename specifically.
    data = _load_map()
    image_file = data["map"]["zac-efron"]["image_file"]
    assert ZAC_SIGNAL_RE.search(image_file), (
        f"zac-efron primary image_file is not an athlete/lifestyle asset: {image_file!r}"
    )


def test_zac_efron_lands_on_athlete_lifestyle_set():
    data = _load_map()
    entry = data["map"]["zac-efron"]
    blob = (entry["image_file"] + " " + (entry.get("caption") or "")).lower()
    assert any(tok in blob for tok in ZAC_TOKENS), (
        f"zac-efron chosen asset is not from the athlete/lifestyle set: {blob!r}"
    )


def test_bears_not_obvious_captive_bear_closeup():
    # best-effort guardrail assert: the chosen bears asset caption must not
    # obviously read as a captive-bear close-up.
    data = _load_map()
    entry = data["map"]["bears"]
    blob = (entry["image_file"] + " " + (entry.get("caption") or "")).lower()
    for tok in CAPTIVE_BEAR_TOKENS:
        assert tok not in blob, f"bears asset looks like a captive-bear closeup ({tok!r}): {blob!r}"
    assert "guardrail" in entry, "bears entry must document its guardrail"
