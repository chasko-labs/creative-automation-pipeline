"""Persona-aware asset pack assembler — OFFLINE, stdlib only.

No network, no AWS. Feeds build_asset_pack sample renders (small on-disk PNGs), a
platform-copy map, and localizations, then asserts the produced zip carries the four
metadata artifacts + one image per ratio named per docs/iso-naming-conventions.md, that
the manifest maps ratios -> platforms and carries the persona index, and that the same
inputs produce the same file set (deterministic-ish).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from PIL import Image

from creative_automation.persona_pack import build_asset_pack, build_pack_image_name


def _png(path: Path, size: tuple[int, int]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (30, 50, 70)).save(path, "PNG")
    return path


def _sample_renders(tmp_path: Path) -> list[dict]:
    return [
        {"ratio": "1x1", "path": _png(tmp_path / "r1.png", (1080, 1080)), "w": 1080, "h": 1080,
         "engine": "primary"},
        {"ratio": "4x5", "path": _png(tmp_path / "r2.png", (1080, 1350)), "w": 1080, "h": 1350,
         "engine": "stability-outpaint"},
        {"ratio": "9x16", "path": _png(tmp_path / "r3.png", (1080, 1920)), "w": 1080, "h": 1920,
         "engine": "stability-outpaint"},
    ]


_PLATFORM_COPY = {
    "instagram": {"platform": "instagram", "headline": "KODIAK(R) Power Cakes", "body": "x",
                  "hashtags": ["#PowerCakes"], "source": "fallback"},
    "x": {"platform": "x", "headline": "KODIAK(R) Power Cakes", "post": "hi", "hashtags": [],
          "source": "fallback"},
}
_LOCALIZATIONS = [
    {"lang_code": "en", "headline": "Fuel your frontier"},
    {"lang_code": "es", "headline": "Alimenta tu frontera"},
    {"lang_code": "pt", "headline": "Abasteca sua fronteira"},
]
_PROVENANCE = {"theme": "us-ski-snowboard", "headline": "Fuel your frontier",
               "ratios": {"1x1": "primary"}, "overlay_applied": True}


def test_pack_image_name_follows_convention_and_allows_4x5():
    name = build_pack_image_name("power-cakes", "US-UT", "park-city", "4x5",
                                 date="20260903", version="v01")
    assert name == "KODIAK-CAKES-power-cakes-US-UT-park-city-social-4x5-20260903-v01.png"


def test_build_asset_pack_produces_valid_zip_with_all_artifacts(tmp_path):
    renders = _sample_renders(tmp_path)
    out_dir = tmp_path / "out"
    zip_path = build_asset_pack(
        renders, _PLATFORM_COPY, _LOCALIZATIONS, _PROVENANCE,
        market="US-UT", product="power-cakes", out_dir=out_dir,
        locality="park-city", date="20260903",
    )
    assert zip_path.exists()
    assert zip_path.name.endswith(".zip")
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        # the four required metadata artifacts
        assert "manifest.json" in names
        assert "platform-copy.json" in names
        assert "localizations.json" in names
        assert "README.txt" in names
        # one image per ratio, named per convention, under images/{ratio}/
        img_names = [n for n in names if n.startswith("images/")]
        assert len(img_names) == 3
        assert "images/1x1/KODIAK-CAKES-power-cakes-US-UT-park-city-social-1x1-20260903-v01.png" in names
        assert "images/4x5/KODIAK-CAKES-power-cakes-US-UT-park-city-social-4x5-20260903-v01.png" in names
        assert "images/9x16/KODIAK-CAKES-power-cakes-US-UT-park-city-social-9x16-20260903-v01.png" in names


def test_manifest_maps_ratios_to_platforms_and_carries_persona_index(tmp_path):
    renders = _sample_renders(tmp_path)
    zip_path = build_asset_pack(
        renders, _PLATFORM_COPY, _LOCALIZATIONS, _PROVENANCE,
        market="US-UT", product="power-cakes", out_dir=tmp_path / "out",
        locality="park-city", date="20260903",
    )
    with zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
    # ratio -> platforms mapping
    assert set(manifest["matrix"].keys()) == {"1x1", "4x5", "9x16"}
    assert set(manifest["matrix"]["4x5"]["platforms"]) == {"instagram", "facebook"}
    assert (manifest["matrix"]["1x1"]["w"], manifest["matrix"]["1x1"]["h"]) == (1080, 1080)
    # persona index present with the three personas
    personas = manifest["personas"]
    assert set(personas.keys()) == {"maya", "diego", "priya"}
    assert personas["maya"]["deliverable"] == "launch-ready set"
    assert personas["diego"]["ratio"] == "9x16"  # territory story
    assert personas["priya"]["master_ratio"] == "1x1"  # master
    # per-region rollup line for Priya
    assert manifest["rollup"]["market"] == "US-UT"
    assert manifest["provenance"]["theme"] == "us-ski-snowboard"


def test_build_asset_pack_deterministic_file_set(tmp_path):
    renders = _sample_renders(tmp_path)
    z1 = build_asset_pack(renders, _PLATFORM_COPY, _LOCALIZATIONS, _PROVENANCE,
                          market="US-UT", product="power-cakes", out_dir=tmp_path / "a",
                          locality="park-city", date="20260903")
    z2 = build_asset_pack(renders, _PLATFORM_COPY, _LOCALIZATIONS, _PROVENANCE,
                          market="US-UT", product="power-cakes", out_dir=tmp_path / "b",
                          locality="park-city", date="20260903")
    with zipfile.ZipFile(z1) as f1, zipfile.ZipFile(z2) as f2:
        assert sorted(f1.namelist()) == sorted(f2.namelist())
        # manifest bytes identical (sort_keys) given identical inputs
        assert f1.read("manifest.json") == f2.read("manifest.json")


def test_missing_render_recorded_not_written(tmp_path):
    # a render whose path does not exist is recorded in manifest.missing, not zipped.
    renders = [
        {"ratio": "1x1", "path": _png(tmp_path / "ok.png", (1080, 1080)), "w": 1080, "h": 1080},
        {"ratio": "16x9", "path": tmp_path / "absent.png", "w": 1920, "h": 1080},
    ]
    zip_path = build_asset_pack(renders, _PLATFORM_COPY, _LOCALIZATIONS, _PROVENANCE,
                                market="US-UT", product="power-cakes", out_dir=tmp_path / "out",
                                locality="park-city", date="20260903")
    with zipfile.ZipFile(zip_path) as zf:
        manifest = json.loads(zf.read("manifest.json"))
        img_names = [n for n in zf.namelist() if n.startswith("images/")]
    assert len(manifest["missing"]) == 1
    assert len(img_names) == 1  # only the present 1x1 render is written
