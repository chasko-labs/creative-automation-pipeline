"""Contract tests for the committed data/products/sku-photo-map.json.

Guards the invariants the live generator relies on: every catalog SKU has an
entry, every entry points at a real asset photo (never a solid-color placeholder),
and channels come from the known set.
"""
from __future__ import annotations

import json
import pathlib
import re

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
MAP_PATH = REPO / "data" / "products" / "sku-photo-map.json"
CATALOG_PATH = REPO / "data" / "products" / "kodiak-full-catalog.json"

ASSET_STORE_PREFIX = "brands/kodiak/raw-ingest/"
KNOWN_CHANNELS = {"blog", "instagram", "tiktok", "amazon", "catalog"}

# a rendered size variant suffix ("_1200x1200") before the extension. embeddings
# metadata carries it, real asset store object keys (mostly) do not. reconciliation in
# scripts/build-sku-photo-map.py must strip it so keys resolve — this regex guards
# the committed artifact against that regression returning.
VARIANT_SUFFIX_RE = re.compile(r"_\d+x\d+\.[a-z0-9]+$", re.IGNORECASE)

# the three real keys that legitimately carry a native size suffix. exact-match
# reconciliation keeps these as-is, so they are allowlisted from the guard.
NATIVE_SIZE_SUFFIX_KEYS = {
    "Blueberry-Lemon_Muffin_6.3-NFP_480x480.jpg",
    "GlutenFree_4x_3f181721-a438-4b2d-b3ae-0bb5331bc76e_100x100.png",
}


@pytest.fixture(scope="module")
def sku_map() -> dict:
    return json.loads(MAP_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def catalog_handles() -> set[str]:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return {p["handle"] for p in catalog["products"]}


def test_json_loads(sku_map: dict) -> None:
    assert "map" in sku_map
    assert "metadata" in sku_map
    assert isinstance(sku_map["map"], dict)


def test_every_catalog_handle_has_entry(sku_map: dict, catalog_handles: set[str]) -> None:
    missing = catalog_handles - set(sku_map["map"])
    assert not missing, f"catalog handles absent from map: {sorted(missing)}"


def test_photo_keys_are_asset_store_paths(sku_map: dict) -> None:
    for handle, entry in sku_map["map"].items():
        key = entry.get("photo_key")
        assert key, f"{handle} has empty photo_key"
        assert key.startswith(ASSET_STORE_PREFIX), f"{handle} photo_key not in asset store: {key}"


def test_no_empty_photo_key(sku_map: dict) -> None:
    for handle, entry in sku_map["map"].items():
        assert entry.get("photo_key"), f"{handle} maps to empty/None photo_key"


def test_channels_from_known_set(sku_map: dict) -> None:
    for handle, entry in sku_map["map"].items():
        chan = entry.get("channel")
        assert chan in KNOWN_CHANNELS, f"{handle} has unknown channel: {chan}"


def test_fallbacks_are_asset_store_paths(sku_map: dict) -> None:
    for handle, entry in sku_map["map"].items():
        for fb in entry.get("fallbacks", []):
            assert fb.startswith(ASSET_STORE_PREFIX), f"{handle} fallback not in asset store: {fb}"


def test_metadata_totals_match(sku_map: dict, catalog_handles: set[str]) -> None:
    assert sku_map["metadata"]["total_skus"] == len(catalog_handles)
    assert len(sku_map["map"]) == len(catalog_handles)


def test_no_variant_suffix_in_photo_keys(sku_map: dict) -> None:
    """Regression guard: reconciliation must strip rendered "_NNNNxNNNN" variant
    suffixes so photo_key references a real asset store object. Only the handful of real
    keys that carry a native size suffix are allowed to keep it (exact match).
    Static check on the committed artifact — no network.
    """
    offenders = []
    for handle, entry in sku_map["map"].items():
        base = entry["photo_key"].split("/")[-1]
        if VARIANT_SUFFIX_RE.search(base) and base not in NATIVE_SIZE_SUFFIX_KEYS:
            offenders.append(f"{handle}: {base}")
    assert not offenders, f"photo_key still carries a variant suffix: {offenders}"


def test_no_variant_suffix_in_fallbacks(sku_map: dict) -> None:
    """Same variant-suffix guard applied to every fallback key."""
    offenders = []
    for handle, entry in sku_map["map"].items():
        for fb in entry.get("fallbacks", []):
            base = fb.split("/")[-1]
            if VARIANT_SUFFIX_RE.search(base) and base not in NATIVE_SIZE_SUFFIX_KEYS:
                offenders.append(f"{handle}: {base}")
    assert not offenders, f"fallback still carries a variant suffix: {offenders}"


def test_image_file_matches_photo_key_basename(sku_map: dict) -> None:
    """The image_file field must be the reconciled basename of photo_key."""
    for handle, entry in sku_map["map"].items():
        assert entry["photo_key"].split("/")[-1] == entry["image_file"], (
            f"{handle}: image_file != photo_key basename"
        )
