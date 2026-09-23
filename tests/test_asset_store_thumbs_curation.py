"""Tests for asset store grid speed + ranking: thumb derivatives, curation, food taxonomy.

Covers asset_browser.thumb_url (HEAD-hit presign, None-safe, never throws),
_apply_curation (omit + strongest-first, missing file no-op), the food class
(food photography out of recipes), and the seven-category table. No real AWS.
"""
from __future__ import annotations

from creative_automation import asset_browser


class _HeadHit:
    def head_object(self, Bucket, Key):
        return {}


class _HeadMiss:
    def head_object(self, Bucket, Key):
        raise RuntimeError("404")


def test_thumb_key_shape() -> None:
    assert (
        asset_browser._thumb_key("brands/kodiak/renders/abc.png")
        == "thumbs/brands/kodiak/renders/abc.png.thumb.jpg"
    )


def test_thumb_url_none_safe() -> None:
    assert asset_browser.thumb_url("", _HeadHit(), "b") is None
    assert asset_browser.thumb_url("k", None, "b") is None
    assert asset_browser.thumb_url("k", _HeadHit(), "") is None


def test_thumb_url_miss_returns_none() -> None:
    assert asset_browser.thumb_url("k", _HeadMiss(), "b") is None


def test_thumb_url_hit_presigns(monkeypatch) -> None:
    monkeypatch.setattr(
        asset_browser.asset_store, "presign_get", lambda key: f"https://cdn/{key}"
    )
    assert (
        asset_browser.thumb_url("a/b.png", _HeadHit(), "bucket")
        == "https://cdn/thumbs/a/b.png.thumb.jpg"
    )


def test_classify_food_photography() -> None:
    p = "brands/kodiak/raw-ingest/kodiakcakes/images/"
    for stem in ("x-pancake-stack-01", "y-plated-brunch-02", "z-syrup-bowl-03",
                 "w-table-spread-04", "v-kitchen-food-05"):
        assert asset_browser.classify_raw_ingest(p + stem + ".jpg") == "food", stem
    assert (
        asset_browser.classify_raw_ingest(p + "my-recipe-card-01.jpg") == "recipes"
    )
    assert (
        asset_browser.classify_raw_ingest(p + "PC-Flapjack.jpg") == "products"
    )


def test_seven_categories() -> None:
    assert set(asset_browser._CATEGORIES) == {
        "products", "recipes", "food", "lifestyle", "ideas", "themes", "brand",
    }
    assert "food" in asset_browser._CLASSIFIED_TABS


def test_curation_omit_and_rank(monkeypatch) -> None:
    monkeypatch.setattr(
        asset_browser, "_CURATION_CACHE",
        {"strength": {"b": 9, "a": 3}, "omit": ["slop"]},
    )
    assert asset_browser._apply_curation(["slop", "a", "b", "c"]) == ["b", "a", "c"]


def test_curation_missing_file_is_noop(monkeypatch) -> None:
    monkeypatch.setattr(asset_browser, "_CURATION_CACHE", {})
    keys = ["x", "y"]
    assert asset_browser._apply_curation(keys) == keys
