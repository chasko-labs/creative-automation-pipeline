"""Offline validation of the platform matrix data file + platforms.py loader.

No network, no AWS. Asserts the committed data/platforms/platform-matrix.json is
well-formed, carries all seven platforms and four ratios with the correct pixel dims,
and that the loader's derived views (ratios<->platforms, dims, union) agree with the
authoritative mapping.
"""
from __future__ import annotations

import json
import pathlib

from creative_automation import platforms

MATRIX_PATH = pathlib.Path("data/platforms/platform-matrix.json")

EXPECTED_PLATFORMS = {"facebook", "instagram", "x", "linkedin", "pinterest", "tiktok", "youtube"}
EXPECTED_RATIO_DIMS = {
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}


def _load() -> dict:
    return json.loads(MATRIX_PATH.read_text(encoding="utf-8"))


def test_matrix_file_loads_and_has_both_views():
    data = _load()
    assert isinstance(data, dict)
    assert set(data["ratios"].keys()) == set(EXPECTED_RATIO_DIMS)
    assert set(data["platforms"].keys()) == EXPECTED_PLATFORMS


def test_all_seven_platforms_present_with_labels_and_ratios():
    data = _load()
    for slug in EXPECTED_PLATFORMS:
        entry = data["platforms"][slug]
        assert entry.get("label"), f"{slug}: missing label"
        assert entry.get("ratios"), f"{slug}: missing ratios"


def test_all_four_ratios_have_correct_dims():
    data = _load()
    for ratio, (w, h) in EXPECTED_RATIO_DIMS.items():
        entry = data["ratios"][ratio]
        assert (entry["w"], entry["h"]) == (w, h), f"{ratio}: wrong dims"
    # the specific spot-check the task calls out
    assert (data["ratios"]["1x1"]["w"], data["ratios"]["1x1"]["h"]) == (1080, 1080)
    assert (data["ratios"]["16x9"]["w"], data["ratios"]["16x9"]["h"]) == (1920, 1080)


def test_ratio_platform_bidirectional_consistency():
    # every platform listed under a ratio must list that ratio, and vice versa.
    data = _load()
    for ratio, rentry in data["ratios"].items():
        for plat in rentry["platforms"]:
            assert ratio in data["platforms"][plat]["ratios"], (
                f"{plat} consumes {ratio} in ratios[] but not in platforms[]"
            )
    for plat, pentry in data["platforms"].items():
        for ratio in pentry["ratios"]:
            assert plat in data["ratios"][ratio]["platforms"], (
                f"{ratio} lists {plat} in platforms[] but not in ratios[]"
            )


def test_authoritative_mapping_matches_task_spec():
    data = _load()
    assert set(data["ratios"]["1x1"]["platforms"]) == {
        "facebook", "instagram", "x", "linkedin", "pinterest"
    }
    assert set(data["ratios"]["4x5"]["platforms"]) == {"instagram", "facebook"}
    assert set(data["ratios"]["9x16"]["platforms"]) == {
        "instagram", "facebook", "tiktok", "youtube", "pinterest"
    }
    assert set(data["ratios"]["16x9"]["platforms"]) == {
        "youtube", "linkedin", "x", "facebook"
    }


# --------------------------------------------------------------- loader views
def test_loader_platforms_tuple_and_dims():
    assert set(platforms.PLATFORMS) == EXPECTED_PLATFORMS
    for ratio, dims in EXPECTED_RATIO_DIMS.items():
        assert platforms.ratio_dims(ratio) == dims


def test_loader_ratios_for_platform():
    assert set(platforms.ratios_for_platform("tiktok")) == {"9x16"}
    assert set(platforms.ratios_for_platform("facebook")) == {"1x1", "4x5", "9x16", "16x9"}


def test_loader_platforms_for_ratio():
    assert set(platforms.platforms_for_ratio("4x5")) == {"instagram", "facebook"}


def test_loader_union_and_map():
    union = platforms.ratios_for_platforms(["tiktok", "linkedin"])
    assert set(union) == {"9x16", "1x1", "16x9"}
    m = platforms.ratio_to_platforms_map(["tiktok"])
    assert set(m.keys()) == {"9x16"}
    assert m["9x16"]["platforms"] == ["tiktok"]
    assert (m["9x16"]["w"], m["9x16"]["h"]) == (1080, 1920)


def test_loader_offline_fallback_on_missing_file(tmp_path):
    # a non-existent path forces the embedded fallback matrix (never raises).
    missing = tmp_path / "nope.json"
    m = platforms.load_matrix(path=missing)
    assert set(m["platforms"].keys()) == EXPECTED_PLATFORMS
