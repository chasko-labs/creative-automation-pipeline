"""Tests for the browse-depth backend: product-line facet + per-platform axis.

Covers dam_library's catalog join (sku-photo-map photo_key/fallbacks -> catalog
category), the always-present item keys, the x-amz-meta-platforms parse, and
dam.head_metadata's degrade-to-{} contract. No real AWS — S3 is faked.
"""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import dam
from creative_automation import dam_library


def _write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _fixtures(tmp_path: Path) -> tuple[Path, Path]:
    catalog = {
        "products": [
            {"handle": "buttermilk-power-cakes", "category": "flapjack-waffle-mix"},
            {"handle": "chocolate-chip-oatmeal", "category": "oatmeal"},
            {"handle": "chocolate-chip-cup", "category": "cups"},
            {"handle": "oatmeal-shared", "category": "oatmeal"},
            {"handle": "mystery-mix", "category": ""},
        ]
    }
    sku_map = {
        "map": {
            "buttermilk-power-cakes": {
                "photo_key": "brands/kodiak/raw-ingest/kodiakcakes/images/PC-Flapjack.jpg",
                "fallbacks": ["brands/kodiak/raw-ingest/kodiakcakes/images/PC-Flapjack-alt.jpg"],
                "matched": True,
            },
            "chocolate-chip-oatmeal": {
                "photo_key": "brands/kodiak/raw-ingest/kodiakcakes/images/Choc-Oat.jpg",
                "fallbacks": [
                    # fallback claim loses to buttermilk's photo claim on the same key
                    "brands/kodiak/raw-ingest/kodiakcakes/images/PC-Flapjack.jpg",
                ],
                "matched": True,
            },
            # shared photo_key, 2 cups claims vs 1 oatmeal claim -> cups by majority
            "chocolate-chip-cup": {
                "photo_key": "brands/kodiak/raw-ingest/kodiakcakes/images/Shared.jpg",
                "fallbacks": [],
                "matched": True,
            },
            # shared photo_key, cups vs oatmeal tie -> alphabetical cups wins
            "oatmeal-shared": {
                "photo_key": "brands/kodiak/raw-ingest/kodiakcakes/images/Shared.jpg",
                "fallbacks": [],
                "matched": True,
            },
            "ghost-handle": {
                "photo_key": "brands/kodiak/raw-ingest/kodiakcakes/images/Ghost.jpg",
                "fallbacks": [],
                "matched": False,
            },
        }
    }
    return (
        _write_json(tmp_path / "sku-photo-map.json", sku_map),
        _write_json(tmp_path / "kodiak-full-catalog.json", catalog),
    )


def test_index_maps_photo_key_and_fallbacks(tmp_path: Path) -> None:
    map_path, catalog_path = _fixtures(tmp_path)
    index = dam_library._load_product_line_index(map_path, catalog_path)
    assert index["brands/kodiak/raw-ingest/kodiakcakes/images/PC-Flapjack.jpg"] == (
        "flapjack-waffle-mix"
    )
    assert index["brands/kodiak/raw-ingest/kodiakcakes/images/PC-Flapjack-alt.jpg"] == (
        "flapjack-waffle-mix"
    )
    assert index["brands/kodiak/raw-ingest/kodiakcakes/images/Choc-Oat.jpg"] == "oatmeal"
    # photo claim outranks the oatmeal fallback claim on the same key
    assert index["brands/kodiak/raw-ingest/kodiakcakes/images/PC-Flapjack.jpg"] == (
        "flapjack-waffle-mix"
    )
    # shared photo_key tie (cups vs oatmeal) breaks alphabetically
    assert index["brands/kodiak/raw-ingest/kodiakcakes/images/Shared.jpg"] == "cups"
    # unknown catalog handle + empty-category product stay out of the index
    assert "brands/kodiak/raw-ingest/kodiakcakes/images/Ghost.jpg" not in index


def test_index_missing_files_soft_empty(tmp_path: Path) -> None:
    index = dam_library._load_product_line_index(
        tmp_path / "no-map.json", tmp_path / "no-catalog.json"
    )
    assert index == {}


def test_item_carries_product_line_on_classified_tabs(tmp_path: Path) -> None:
    map_path, catalog_path = _fixtures(tmp_path)
    index = dam_library._load_product_line_index(map_path, catalog_path)
    key = "brands/kodiak/raw-ingest/kodiakcakes/images/PC-Flapjack.jpg"
    for tab in ("products", "recipes", "lifestyle"):
        item = dam_library._item_for(key, tab, None, index)
        assert item["product_line"] == "flapjack-waffle-mix"
        assert item["platforms"] == []
    # unknown key: None, never fabricated
    item = dam_library._item_for("brands/kodiak/raw-ingest/kodiakcakes/images/Other.jpg",
                                 "products", None, index)
    assert item["product_line"] is None


def test_item_non_classified_tabs_carry_none_and_platforms() -> None:
    item = dam_library._item_for(
        "brands/kodiak/renders/abc123.png", "ideas", None, None, ["facebook", "blog"]
    )
    assert item["product_line"] is None
    assert item["platforms"] == ["facebook", "blog"]
    brand = dam_library._item_for("brands/kodiak/logos/mark.svg", "brand", None, None, None)
    assert brand["product_line"] is None
    assert brand["platforms"] == []


def test_platforms_from_meta_parses_and_degrades() -> None:
    assert dam_library._platforms_from_meta({"platforms": "facebook, instagram ,x"}) == [
        "facebook",
        "instagram",
        "x",
    ]
    assert dam_library._platforms_from_meta({"Platforms": "blog"}) == ["blog"]
    assert dam_library._platforms_from_meta({}) == []
    assert dam_library._platforms_from_meta({"other": "x"}) == []


class _FakeHeadClient:
    def __init__(self, meta: dict | None = None, fail: bool = False) -> None:
        self.meta = meta or {}
        self.fail = fail
        self.calls: list[dict] = []

    def head_object(self, **kwargs) -> dict:
        self.calls.append(kwargs)
        if self.fail:
            raise RuntimeError("boom")
        return {"Metadata": dict(self.meta)}


def test_head_metadata_returns_lowercased_tags(monkeypatch) -> None:
    fake = _FakeHeadClient({"Platforms": "facebook,blog"})
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setattr(dam, "_s3_bucket_and_prefix", lambda: ("bkt", ""))
    monkeypatch.setattr(dam, "_s3_client", lambda: fake)
    assert dam.head_metadata("brands/kodiak/renders/a.png") == {"platforms": "facebook,blog"}
    assert fake.calls[0]["Key"] == "brands/kodiak/renders/a.png"


def test_head_metadata_degrades_to_empty(monkeypatch) -> None:
    # s3 disabled
    monkeypatch.setattr(dam, "_s3_enabled", lambda: False)
    assert dam.head_metadata("k") == {}
    # head failure
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setattr(dam, "_s3_bucket_and_prefix", lambda: ("bkt", ""))
    monkeypatch.setattr(dam, "_s3_client", lambda: _FakeHeadClient(fail=True))
    assert dam.head_metadata("k") == {}
    # empty key never calls
    assert dam.head_metadata("") == {}


def test_real_committed_join_is_nonempty() -> None:
    """The shipped map + catalog must actually join: every matched photo_key
    resolves to a category claimed by one of its photo owners (photo-priority
    contract), and every catalog category appears on at least one tile."""
    repo = Path(__file__).resolve().parents[1]
    index = dam_library._load_product_line_index(
        repo / "data" / "products" / "sku-photo-map.json",
        repo / "data" / "products" / "kodiak-full-catalog.json",
    )
    assert len(index) > 100
    catalog = json.loads(
        (repo / "data" / "products" / "kodiak-full-catalog.json").read_text(encoding="utf-8")
    )
    categories = {p["handle"]: p["category"] for p in catalog["products"] if p.get("category")}
    sku_map = json.loads(
        (repo / "data" / "products" / "sku-photo-map.json").read_text(encoding="utf-8")
    )
    photo_owners: dict[str, set[str]] = {}
    for handle, entry in sku_map["map"].items():
        if handle in categories and entry.get("matched") and entry.get("photo_key"):
            photo_owners.setdefault(entry["photo_key"], set()).add(categories[handle])
    checked = 0
    for key, lines in photo_owners.items():
        assert index[key] in lines, f"{key} resolved outside its photo owners"
        checked += 1
    assert checked > 40
    assert set(index.values()) >= set(categories.values())
