"""Partner person-libraries: Zac Efron is a person, not a vibe.

No network. Asserts data/products/partner-libraries.json is well-formed
(person/role/photo_keys/theme/shot_list), every photo_key is a real DAM key
(brand-approved photography only — no scraped stills, no synthesis), and the
built theme map leads the person's theme with their approved photo.
"""
from __future__ import annotations

import json
import pathlib

LIBS_PATH = pathlib.Path("data/products/partner-libraries.json")
MAP_PATH = pathlib.Path("data/products/theme-asset-map.json")
_FIXTURE_KEYS = pathlib.Path(__file__).parent / "fixtures" / "dam-real-keys.txt"
_TMP_KEYS = pathlib.Path("/tmp/dam-real-keys.txt")
DAM_KEYS_PATH = _FIXTURE_KEYS if _FIXTURE_KEYS.exists() else _TMP_KEYS
DAM_PREFIX = "brands/kodiak/raw-ingest/kodiakcakes/images/"


def _load_libs() -> dict:
    assert LIBS_PATH.exists(), f"{LIBS_PATH} not found"
    return json.loads(LIBS_PATH.read_text(encoding="utf-8"))


def _load_real_keys() -> set[str]:
    assert DAM_KEYS_PATH.exists(), f"{DAM_KEYS_PATH} not found"
    return {line.strip() for line in DAM_KEYS_PATH.read_text().splitlines() if line.strip()}


def test_zac_efron_is_a_person_with_role():
    libs = _load_libs()
    zac = libs["partners"]["zac-efron"]
    assert zac["person"] == "Zac Efron"
    assert "Chief Brand Officer" in zac["role"]
    assert "board" in zac["role"]
    assert zac["since"] == "2022-06"
    assert zac["theme"] == "zac-efron"
    assert zac["photo_keys"], "person library with zero approved photos is a gap, not a library"
    slots = {s["slot"]: s["status"] for s in zac["shot_list"]}
    assert set(slots.values()) <= {"covered", "gap"}


def test_partner_keys_are_real_dam_keys():
    libs = _load_libs()
    real = _load_real_keys()
    for slug, person in libs["partners"].items():
        assert person["theme"], f"{slug} must name the theme it leads"
        for key in person["photo_keys"]:
            assert key.startswith(DAM_PREFIX), f"{slug}: {key} must be a DAM key"
            assert key[len(DAM_PREFIX):] in real, f"{slug}: {key} is not a real DAM key"


def test_theme_map_leads_with_the_person():
    themap = json.loads(MAP_PATH.read_text(encoding="utf-8"))["map"]
    libs = _load_libs()
    zac = libs["partners"]["zac-efron"]
    entry = themap["zac-efron"]
    assert entry.get("partner") == "Zac Efron"
    assert entry.get("partner_primary") is True
    assert entry["photo_key"] in zac["photo_keys"]
    assert entry["pool"][0] == entry["photo_key"]
