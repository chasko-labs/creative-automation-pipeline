"""Tests for DAM grid speed + ranking: thumb derivatives, curation, food taxonomy.

Covers dam_library.thumb_url (HEAD-hit presign, None-safe, never throws),
_apply_curation (omit + strongest-first, missing file no-op), the food class
(food photography out of recipes), and the seven-category table. No real AWS.
"""
from __future__ import annotations

from creative_automation import dam_library


class _HeadHit:
    def head_object(self, Bucket, Key):
        return {}


class _HeadMiss:
    def head_object(self, Bucket, Key):
        raise RuntimeError("404")


def test_thumb_key_shape() -> None:
    assert (
        dam_library._thumb_key("brands/kodiak/renders/abc.png")
        == "thumbs/brands/kodiak/renders/abc.png.thumb.jpg"
    )


def test_thumb_url_none_safe() -> None:
    assert dam_library.thumb_url("", _HeadHit(), "b") is None
    assert dam_library.thumb_url("k", None, "b") is None
    assert dam_library.thumb_url("k", _HeadHit(), "") is None


def test_thumb_url_miss_returns_none() -> None:
    assert dam_library.thumb_url("k", _HeadMiss(), "b") is None


def test_thumb_url_hit_presigns(monkeypatch) -> None:
    monkeypatch.setattr(
        dam_library.dam, "presign_get", lambda key: f"https://cdn/{key}"
    )
    assert (
        dam_library.thumb_url("a/b.png", _HeadHit(), "bucket")
        == "https://cdn/thumbs/a/b.png.thumb.jpg"
    )


def test_classify_food_photography() -> None:
    p = "brands/kodiak/raw-ingest/kodiakcakes/images/"
    for stem in ("x-pancake-stack-01", "y-plated-brunch-02", "z-syrup-bowl-03",
                 "w-table-spread-04", "v-kitchen-food-05"):
        assert dam_library.classify_raw_ingest(p + stem + ".jpg") == "food", stem
    assert (
        dam_library.classify_raw_ingest(p + "my-recipe-card-01.jpg") == "recipes"
    )
    assert (
        dam_library.classify_raw_ingest(p + "PC-Flapjack.jpg") == "products"
    )


def test_seven_categories() -> None:
    assert set(dam_library._CATEGORIES) == {
        "products", "recipes", "food", "lifestyle", "ideas", "themes", "brand",
    }
    assert "food" in dam_library._CLASSIFIED_TABS


def test_curation_omit_and_rank(monkeypatch) -> None:
    monkeypatch.setattr(
        dam_library, "_CURATION_CACHE",
        {"strength": {"b": 9, "a": 3}, "omit": ["slop"]},
    )
    assert dam_library._apply_curation(["slop", "a", "b", "c"]) == ["b", "a", "c"]


def test_curation_missing_file_is_noop(monkeypatch) -> None:
    monkeypatch.setattr(dam_library, "_CURATION_CACHE", {})
    keys = ["x", "y"]
    assert dam_library._apply_curation(keys) == keys
