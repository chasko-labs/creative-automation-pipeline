"""Preview coherence: the NYC-September class of failures, generically covered.

Raw brief scaffolding must never become copy; the recipe panel must agree
with the card picker via the in-season ingredient; image prompts lead with
the finished dish. No per-market special cases — every assertion runs through
the shared registries and helpers.
"""
from __future__ import annotations

import creative_automation.generate_lambda as gl
from creative_automation.platform_copy import build_platform_copy_response
from creative_automation.scene_prompts import (
    _holiday_icon_clause,
    _scenic_scene_text,
    copy_base_from_brief,
)
from creative_automation.generate import _default_scene_prompt
from creative_automation.season_pairing import month_number_for_request

NYC_BRIEF = (
    "\u2014 market: New York City \u00b7 season: September \u00b7 ecology: Bodega coffee, "
    "oatmeal cup on subway platform \u00b7 frontier: Warwick, NY "
    "(Hudson Valley, apples/onions/black dirt) \u2014 Black-dirt onion season (Jul-Sep) "
    "\u00b7 in-season: apples (savory onion cheddar bakes, sweet corn)"
)


def test_copy_base_humanizes_pure_scaffolding() -> None:
    base = copy_base_from_brief(NYC_BRIEF)
    assert "market:" not in base
    assert "frontier:" not in base
    assert "Black-dirt onion season" not in base
    assert "Bodega coffee" in base
    assert "apples" in base


def test_copy_base_passes_human_text_through() -> None:
    assert copy_base_from_brief("Bodega mornings fuel the hustle") == \
        "Bodega mornings fuel the hustle"


def test_copy_base_keeps_user_idea_ahead_of_suffix() -> None:
    base = copy_base_from_brief("sea otters \u00b7 market: Cincinnati")
    assert "sea otters" in base
    assert "market:" not in base


def test_copy_base_empty_without_grounding() -> None:
    assert copy_base_from_brief("market: X \u00b7 season: Fall") == ""
    assert copy_base_from_brief(None) == ""
    assert copy_base_from_brief("") == ""


def test_month_number_for_request() -> None:
    assert month_number_for_request("September") == 9
    assert month_number_for_request("2026-09") == 9
    assert month_number_for_request("9") == 9
    assert month_number_for_request("Fall") is None
    assert month_number_for_request("Christmas") is None
    assert month_number_for_request("blorpt") is None
    assert month_number_for_request(None) is None


def test_pairing_nyc_september_names_apple_recipe() -> None:
    rec, meta = gl._season_pairing(
        "September",
        market="US-NE-NYC",
        month_ym="2026-09",
        product_name="Buttermilk Power Cakes Flapjack & Waffle Mix",
    )
    assert rec is not None
    assert rec.get("id") == "apple-cinnamon-compote"
    assert meta.get("source", "").startswith("ingredient")
    assert meta.get("name") == "Apple Cinnamon Compote"


def test_pairing_year_rollover_reuses_same_month() -> None:
    from creative_automation.recipe_card import _names_ingredient

    rec, meta = gl._season_pairing(
        "September", market="US-NE-NYC", month_ym="2099-09",
        product_name="Power Cakes",
    )
    # The rotation winner varies by month string by design; what matters is
    # the rollover still serves an apple-naming recipe, never the pumpkin.
    assert rec is not None and _names_ingredient(rec, "apples")
    assert meta.get("source", "").startswith("ingredient")
    assert rec.get("id") != "pumpkin-oat-muffins"


def test_pairing_legacy_paths_unchanged() -> None:
    # No market: the season table still serves pumpkin for September.
    rec, meta = gl._season_pairing("September")
    assert rec is not None and rec.get("id") == "pumpkin-oat-muffins"
    assert meta.get("source") == "season-table"
    # Seasons and holidays never consult the ingredient picker.
    assert gl._season_pairing("Fall", market="US-NE-NYC")[1].get("source") == "season-table"
    rec_xmas, meta_xmas = gl._season_pairing("Christmas", market="US-NE-NYC")
    assert rec_xmas is not None and rec_xmas.get("id") == "christmas-tree-waffles"
    assert meta_xmas.get("source") == "season-table"
    # Garbage stays quiet.
    rec_bad, meta_bad = gl._season_pairing("blorpt", market="US-NE-NYC")
    assert meta_bad.get("source") in (None, "static-default")


def test_preview_campaign_data_names_apple_for_nyc_september() -> None:
    prov: dict = {}
    data = {
        "product": "buttermilk-power-cakes-flapjack-waffle-mix",
        "market": "US-NE-NYC",
        "season": "September",
    }
    gl._preview_campaign_data(data, NYC_BRIEF, prov)
    assert prov.get("recipe") == "Apple Cinnamon Compote"
    assert prov["recipe_pairing"]["source"].startswith("ingredient")


def test_monthly_ingredient_unifies_registries() -> None:
    from creative_automation.locales import monthly_ingredient_for

    assert monthly_ingredient_for("US-NE-NYC", 9) == "apples"
    assert monthly_ingredient_for("US-NE-NYC", 9, year=2099) == "apples"
    assert monthly_ingredient_for("US-NE-NYC", 13) is None
    assert monthly_ingredient_for("NOPE-NOT-A-MARKET", 9) is None
    assert monthly_ingredient_for(None, 9) is None


def test_market_scene_clause_cooks_what_the_panel_pairs() -> None:
    from creative_automation.scene_prompts import _market_scene_clause

    clause = _market_scene_clause("US-NE-NYC", "September")
    assert "apples in season" in clause
    assert "onion" not in clause.lower()
    # Unpaired markets keep the flavor-registry fallback, never a raw code.
    assert "US-NE-" not in _market_scene_clause("NOPE-NOT-A-MARKET", "September")


def test_preview_dish_matches_recipe_panel() -> None:
    dish = gl._preview_dish_name(
        {"season": "September", "market": "US-NE-NYC"},
        "Buttermilk Power Cakes Flapjack & Waffle Mix",
    )
    assert dish == "Apple Cinnamon Compote"


def test_sharpen_response_never_ships_scaffolding() -> None:
    resp = build_platform_copy_response(
        {
            "base_message": NYC_BRIEF,
            "product_name": "Buttermilk Power Cakes Flapjack & Waffle Mix",
            "market": "US-NE-NYC",
            "season": "September",
        }
    )
    copy = resp["platform_copy"]
    assert set(copy) >= {"homepage", "instagram", "x"}
    for platform, entry in copy.items():
        for key in ("headline", "title", "post", "body"):
            text = entry.get(key)
            if not text:
                continue
            assert "market:" not in text, (platform, key, text)
            assert "Black-dirt onion season" not in text, (platform, key, text)


def test_default_scene_prompt_leads_with_dish() -> None:
    scene = _default_scene_prompt(
        "Buttermilk Power Cakes", NYC_BRIEF, "us", "active families", None,
        dish="Apple Cinnamon Compote", market="US-NE-NYC", season="September",
    )
    assert scene.startswith("A serving of Apple Cinnamon Compote.")
    assert scene.index("Apple Cinnamon Compote") < scene.index("Warwick")


def test_holiday_icons_named_by_structured_request_only() -> None:
    assert "pumpkins" in _holiday_icon_clause("Halloween")
    assert "santa" in _holiday_icon_clause("Christmas")
    assert _holiday_icon_clause("September") == ""
    assert _holiday_icon_clause("Fall") == ""
    assert _holiday_icon_clause("blorpt") == ""
    scene = _default_scene_prompt(
        "Power Cakes", NYC_BRIEF, "us", "families", None,
        dish="Baked Halloween Doughnuts", market="US-NE-NYC", season="Halloween",
    )
    assert scene.startswith("A serving of Baked Halloween Doughnuts.")
    assert "pumpkins" in scene


def test_history_endpoint_projects_shared_ledger() -> None:
    import json as _json

    from creative_automation import asset_store as _store

    real_list = _store.list_preview_attempts
    real_presign = _store.presign_s3_uri
    _store.list_preview_attempts = lambda limit=20: [
        {
            "recorded_at": "2026-09-28T13:00:00+00:00",
            "brief": NYC_BRIEF,
            "market": "US-NE-NYC",
            "season": "September",
            "product": "power-cakes",
            "dish": "Apple Cinnamon Compote",
            "scene_prompt": "A serving of Apple Cinnamon Compote. orchard light",
            "headline": "Apple Cinnamon Power",
            "recipe": "Apple Cinnamon Compote",
            "source": "bedrock:stability-control-structure",
            "renders": [{"ratio": "1x1", "s3_uri": "s3://bucket/key.png"}],
        },
        "not-a-record",
    ]
    _store.presign_s3_uri = lambda uri, expires_s=604800: "https://img/thumb.png"
    try:
        resp = gl._handle_history({"queryStringParameters": {}})
    finally:
        _store.list_preview_attempts = real_list
        _store.presign_s3_uri = real_presign
    assert resp["statusCode"] == 200
    body = _json.loads(resp["body"])
    assert body["ok"] is True
    assert len(body["entries"]) == 1
    entry = body["entries"][0]
    assert entry["dish"] == "Apple Cinnamon Compote"
    assert entry["renders"][0]["image_url"] == "https://img/thumb.png"
    assert "market:" not in entry["base"]
    assert "Bodega coffee" in entry["base"]


def test_history_endpoint_never_breaks_the_page() -> None:
    import json as _json

    from creative_automation import asset_store as _store

    real_list = _store.list_preview_attempts
    _store.list_preview_attempts = lambda limit=20: []
    try:
        resp = gl._handle_history({"queryStringParameters": {"limit": "garbage"}})
        resp_boom = gl._handle_history(None)
    finally:
        _store.list_preview_attempts = real_list
    assert resp["statusCode"] == 200
    assert _json.loads(resp["body"]) == {"ok": True, "entries": []}
    assert _json.loads(resp_boom["body"]) == {"ok": True, "entries": []}


def test_scenic_text_leads_with_dish() -> None:
    scene = _scenic_scene_text(
        NYC_BRIEF, market="US-NE-NYC", season="September",
        dish="Apple Cinnamon Compote",
    )
    assert scene.index("a serving of Apple Cinnamon Compote") < scene.index("Warwick")
