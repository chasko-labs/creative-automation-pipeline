"""Season threading into the preview campaign data: data.season drives the
recipe default via the season pairing table; garbage season keeps the static
default. Never raises, never fabricates."""

from __future__ import annotations

import creative_automation.generate_lambda as gl


def test_seasonal_default_none_without_season() -> None:
    assert gl._seasonal_recipe_default(None, "Power Cakes") is None
    assert gl._seasonal_recipe_default("", "Power Cakes") is None
    assert gl._seasonal_recipe_default("   ", "Power Cakes") is None


def test_seasonal_default_garbage_season_keeps_static_default() -> None:
    got = gl._seasonal_recipe_default("not-a-season-at-all", "Power Cakes")
    static = gl._recipe_card_defaults("Power Cakes")
    # Unknown seasons land on the static-default pairing or fail validation —
    # either way the caller keeps serving the static default, never an error.
    assert got is None or got["title"] == static["title"]


def test_seasonal_default_uses_valid_season_record(monkeypatch) -> None:
    fake = {
        "title": "Fall Harvest Stack",
        "ingredients": ["2 cups mix", "1 cup cider", "1 tbsp maple"],
        "steps": ["Whisk it", "Cook it", "Stack it"],
    }
    monkeypatch.setattr(
        "creative_automation.recipe_card._season_fallback_recipe",
        lambda season, month="": fake,
    )
    assert gl._seasonal_recipe_default("Fall", "Power Cakes") == fake


def test_seasonal_default_rejects_invalid_record(monkeypatch) -> None:
    monkeypatch.setattr(
        "creative_automation.recipe_card._season_fallback_recipe",
        lambda season, month="": {"title": "", "ingredients": [], "steps": []},
    )
    assert gl._seasonal_recipe_default("Fall", "Power Cakes") is None


def test_preview_campaign_data_prefers_season_over_static(monkeypatch) -> None:
    fake = {
        "title": "Summer Berry Stack",
        "ingredients": ["2 cups mix", "1 cup berries", "1 tbsp honey"],
        "steps": ["Whisk it", "Cook it", "Top it"],
    }
    monkeypatch.setattr(
        "creative_automation.recipe_card._season_fallback_recipe",
        lambda season, month="": fake,
    )
    data = {"product": "power-cakes", "market": "us", "season": "Summer"}
    campaign = gl._preview_campaign_data(data, "summer brief", {})
    assert campaign["recipe_fields"]["title"] == "Summer Berry Stack"


def test_preview_campaign_data_no_season_keeps_static_default() -> None:
    data = {"product": "power-cakes", "market": "us"}
    campaign = gl._preview_campaign_data(data, "plain brief", {})
    assert (
        campaign["recipe_fields"]["title"]
        == gl._recipe_card_defaults("Power Cakes")["title"]
    )
