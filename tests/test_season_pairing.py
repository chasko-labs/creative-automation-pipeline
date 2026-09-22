"""Season pairing (sprint) — structured season request, season-indexed pairing
table with static default as last resort, pairing reason in provenance.

Contract under test:
  - CampaignBrief.season is the ONLY season input (structured request field).
    Free brief text (campaign_message) is display-only and never steers pairing.
  - No ingredient match -> season-indexed table hit; no season either ->
    static default. Ingredient honesty (featured_for / overlap / rotation) wins
    over season whenever it matches.
  - Every pairing carries its reason in card provenance.
"""
import pytest

from creative_automation import season_pairing as sp
from creative_automation.brief import CampaignBrief


def _brief(**overrides):
    base = {
        "campaign_name": "Season Test",
        "brand": "KODIAK",
        "target_region": "US",
        "target_market": "US-SE-ATL",
        "target_audience": "families",
        "campaign_message": "Protein-packed whole grains for your frontier.",
        "products": [
            {"id": "power-cakes", "name": "Buttermilk Power Cakes", "description": "flapjack mix"},
            {"id": "oatmeal-cup", "name": "Protein Oatmeal Cup", "description": "oatmeal cup"},
        ],
    }
    base.update(overrides)
    return CampaignBrief.model_validate(base)


# --------------------------------------------------------------------------- #
# structured season request field (brief)
# --------------------------------------------------------------------------- #

def test_brief_season_defaults_to_none():
    assert _brief().season is None


def test_brief_season_normalizes_case_and_autumn():
    assert _brief(season="Summer").season == "summer"
    assert _brief(season="AUTUMN").season == "fall"
    assert _brief(season="  Fall ").season == "fall"


def test_brief_season_blank_stays_none():
    assert _brief(season="").season is None


def test_brief_season_rejects_unknown_values():
    with pytest.raises(ValueError):
        _brief(season="monsoon")


# --------------------------------------------------------------------------- #
# season_pairing unit behavior
# --------------------------------------------------------------------------- #

def test_normalize_season():
    assert sp.normalize_season("Spring") == "spring"
    assert sp.normalize_season("autumn") == "fall"
    assert sp.normalize_season(None) is None
    assert sp.normalize_season("") is None
    assert sp.normalize_season("monsoon") is None


def test_normalize_holiday_accepts_dash_form():
    # campaign art dirs + offline index use fourth-of-july; the table key has spaces.
    assert sp.normalize_holiday("fourth-of-july") == "fourth of july"
    assert sp.normalize_holiday("Fourth-Of-July") == "fourth of july"
    assert sp.normalize_holiday("funday") is None


def test_season_for_month_maps_meteorological_seasons():
    assert sp.season_for_month("2026-01") == "winter"
    assert sp.season_for_month("2026-02") == "winter"
    assert sp.season_for_month("2026-03") == "spring"
    assert sp.season_for_month("2026-05") == "spring"
    assert sp.season_for_month("2026-06") == "summer"
    assert sp.season_for_month("2026-08") == "summer"
    assert sp.season_for_month("2026-09") == "fall"
    assert sp.season_for_month("2026-11") == "fall"
    assert sp.season_for_month("2026-12") == "winter"
    assert sp.season_for_month("not-a-month") is None
    assert sp.season_for_month(None) is None
    assert sp.season_for_month("2026-13") is None


def test_resolve_season_structured_request_beats_month():
    assert sp.resolve_season("summer", "2026-01") == {"season": "summer", "source": "brief"}
    assert sp.resolve_season(None, "2026-01") == {"season": "winter", "source": "month"}
    assert sp.resolve_season(None, None) == {"season": None, "source": None}
    assert sp.resolve_season("monsoon", "2026-04") == {"season": "spring", "source": "month"}


def test_pairing_table_covers_all_seasons_with_reasons():
    for season in ("spring", "summer", "fall", "winter"):
        pairing = sp.pairing_for_season(season)
        assert pairing["source"] == "season-table"
        assert pairing["recipe_id"]
        assert pairing["reason"], f"no pairing reason for {season}"


def test_pairing_table_entries_are_distinct_and_default_is_last_resort():
    ids = {sp.pairing_for_season(s)["recipe_id"] for s in ("spring", "summer", "fall", "winter")}
    assert len(ids) == 4, f"season pairings are not distinct: {ids}"
    default = sp.pairing_for_season(None)
    assert default["source"] == "static-default"
    assert default["recipe_id"] == sp.DEFAULT_PAIRING["recipe_id"]
    assert default["reason"]
    assert sp.pairing_for_season("monsoon") == default


def test_strip_season_words_removes_only_whole_words():
    assert sp.strip_season_words("Winter wonderland sale, summery vibes") == "wonderland sale, summery vibes"
    assert sp.strip_season_words("no summer here") == "no here"
    assert sp.strip_season_words("SPRING") == ""
    assert sp.strip_season_words("in season now") == "in season now"


# --------------------------------------------------------------------------- #
# picking: ingredient honesty wins, season table is the fallback
# --------------------------------------------------------------------------- #

def test_ingredient_match_beats_structured_season():
    # muscadine grapes genuinely match the grape topper; even a conflicting
    # structured season must not reroute the pick — only the season LABEL rides along.
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance(
        "muscadine grapes", "Buttermilk Power Cakes",
        market="US-SE-ATL", month="2026-09", season="winter",
    )
    assert recipe["id"] == "roasted-grape-flapjack-topper-draft"
    assert pairing["season"] == "winter"
    assert pairing["source"] in ("ingredient-featured", "ingredient-overlap", "ingredient-rotation")
    assert pairing["recipe_id"] == recipe["id"]
    assert pairing["reason"]


def test_featured_curation_source_label():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("sweet cherries", None)
    assert recipe["id"] == "cherry-pie-bars"
    assert pairing["source"] == "ingredient-featured"
    assert pairing["recipe_id"] == "cherry-pie-bars"
    assert pairing["reason"]


def test_overlap_source_label_without_market_context():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("strawberries", None)
    assert recipe["id"] == "yogurt-pie"
    assert pairing["source"] == "ingredient-overlap"
    assert pairing["recipe_id"] == "yogurt-pie"
    assert pairing["reason"]


def test_rotation_source_label_with_market_context():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance(
        "winter squash", "Buttermilk Power Cakes",
        market="US-MW-BOISE", month="2026-10",
    )
    assert pairing["source"] == "ingredient-rotation"
    assert pairing["recipe_id"] == recipe["id"]
    assert pairing["reason"]


def test_season_table_serves_unmatched_ingredient():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("zzqx unobtanium", None, season="fall")
    assert recipe["id"] == "pumpkin-oat-muffins"
    assert pairing == {
        "season": "fall",
        "source": "season-table",
        "recipe_id": "pumpkin-oat-muffins",
        "reason": sp.SEASON_RECIPE_PAIRINGS["fall"]["reason"],
    }


def test_month_derived_season_serves_unmatched_ingredient():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("zzqx unobtanium", None, month="2026-01")
    assert recipe["id"] == "pear-spice-muffins-draft"
    assert pairing["season"] == "winter"
    assert pairing["source"] == "season-table"


def test_static_default_is_last_resort():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("zzqx unobtanium", None)
    assert recipe["id"] == sp.DEFAULT_PAIRING["recipe_id"]
    assert pairing["source"] == "static-default"
    assert pairing["season"] is None
    assert pairing["reason"] == sp.DEFAULT_PAIRING["reason"]


def test_pick_recipe_keeps_legacy_winners():
    # backward-compat: the season kwarg defaults off and changes nothing for
    # ingredient matches (mirrors the committed lottery/rotation expectations).
    from creative_automation.recipe_card import _pick_recipe

    assert _pick_recipe("Half Moon Bay pumpkin", None)["id"] == "pumpkin-oat-muffins"
    assert _pick_recipe("muscadine grapes", None)["id"] == "roasted-grape-flapjack-topper-draft"
    assert _pick_recipe("zzqx unobtanium", None)["id"] == sp.DEFAULT_PAIRING["recipe_id"]


# --------------------------------------------------------------------------- #
# provenance carries the pairing reason
# --------------------------------------------------------------------------- #

def test_card_data_provenance_carries_pairing_reason():
    from creative_automation.recipe_card import build_recipe_card_data

    card = build_recipe_card_data("US-SE-ATL", month="2026-09")
    pairing = card["provenance"]["pairing"]
    assert pairing["recipe_id"] == card["recipe"]["id"]
    assert pairing["reason"]
    assert pairing["season"] == "fall"  # month-derived when no structured request
    assert pairing["source"] in (
        "ingredient-featured", "ingredient-overlap", "ingredient-rotation",
    )


def test_card_meta_provenance_carries_pairing_reason(tmp_path):
    from creative_automation.recipe_card import build_recipe_card

    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    pairing = result["meta"]["provenance"]["pairing"]
    assert pairing["recipe_id"] == result["recipe"]["id"]
    assert pairing["reason"]


def test_empty_card_shapes_carry_honest_pairing(tmp_path):
    from creative_automation.recipe_card import build_recipe_card, build_recipe_card_data

    result = build_recipe_card("US-XX-NOWHERE", month="2026-09", out_dir=tmp_path)
    pairing = result["meta"]["provenance"]["pairing"]
    assert pairing["source"] == "none"
    assert pairing["recipe_id"] is None
    assert pairing["reason"]

    data = build_recipe_card_data("US-XX-NOWHERE", month="2026-09")
    assert data["provenance"]["pairing"]["source"] == "none"


# --------------------------------------------------------------------------- #
# brief-text leak: campaign_message is display-only, never a pairing input
# --------------------------------------------------------------------------- #

def test_brief_season_reader_ignores_message_text():
    from creative_automation.campaign import _brief_season

    # "winter" leaks in the free text but no structured request exists -> None
    assert _brief_season({"campaign_message": "our winter wonderland sale"}) is None
    # structured request wins even when the message disagrees
    assert _brief_season({"season": "summer", "campaign_message": "winter sale"}) == "summer"
    # loose dict junk degrades to None, never raises
    assert _brief_season({"season": "monsoon"}) is None
    assert _brief_season("US-SE-ATL") is None


def test_message_season_word_does_not_reroute_campaign_pairing(tmp_path):
    from creative_automation.campaign import run_campaign

    brief = {
        "market": "US-SE-ATL",
        "season": "summer",
        "campaign_message": "Our winter wonderland breakfast sale.",
        "products": [
            {"id": "power-cakes", "name": "Buttermilk Power Cakes", "description": "flapjack mix"},
        ],
        "retailers": [],
    }
    result = run_campaign(
        brief, out_dir=tmp_path, month="2026-09",
        platforms={"instagram": ["1x1"]}, languages=["en"],
    )
    assert result["campaign"]["season"] == "summer"
    assert result["recipe_cards"]
    card = result["recipe_cards"][0]
    # the genuine September ingredient still wins (message "winter" ignored)...
    assert card["ingredient"] == "muscadine grapes"
    assert card["recipe"]["id"] == "roasted-grape-flapjack-topper-draft"
    # ...while the structured season rides the pairing label
    assert card["pairing"]["season"] == "summer"
    assert card["pairing"]["reason"]


# --------------------------------------------------------------------------- #
# sprint-2 items 8+9: full ISO dates; empty product+season serves season table
# --------------------------------------------------------------------------- #

def test_season_for_month_accepts_full_iso_dates():
    assert sp.season_for_month("2026-01-15") == "winter"
    assert sp.season_for_month("2026-02-28") == "winter"
    assert sp.season_for_month("2026-03-01") == "spring"
    assert sp.season_for_month("2026-05-31") == "spring"
    assert sp.season_for_month("2026-07-04") == "summer"
    assert sp.season_for_month("2026-08-31") == "summer"
    assert sp.season_for_month("2026-09-15") == "fall"
    assert sp.season_for_month("2026-11-30") == "fall"
    assert sp.season_for_month("2026-12-25") == "winter"
    # YYYY-MM keeps working alongside the full date
    assert sp.season_for_month("2026-09") == "fall"


def test_season_for_month_rejects_bad_full_dates():
    assert sp.season_for_month("2026-13-01") is None
    assert sp.season_for_month("2026-01-00") is None
    assert sp.season_for_month("2026-01-32") is None
    assert sp.season_for_month("2026-01-15-extra") is None
    assert sp.season_for_month("not-a-month") is None
    assert sp.season_for_month("") is None
    assert sp.season_for_month(202609) is None


def test_resolve_season_accepts_full_iso_month():
    assert sp.resolve_season(None, "2026-09-15") == {"season": "fall", "source": "month"}
    assert sp.resolve_season(None, "2026-01-20") == {"season": "winter", "source": "month"}
    assert sp.resolve_season("summer", "2026-01-20") == {"season": "summer", "source": "brief"}
    assert sp.resolve_season(None, "2026-13-01") == {"season": None, "source": None}


def test_empty_subject_with_season_serves_season_table():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("", None, season="fall")
    assert recipe["id"] == "pumpkin-oat-muffins"
    assert pairing == {
        "season": "fall",
        "source": "season-table",
        "recipe_id": "pumpkin-oat-muffins",
        "reason": sp.SEASON_RECIPE_PAIRINGS["fall"]["reason"],
    }


def test_empty_subject_with_full_date_month_serves_season_table():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("", "", month="2026-01-20")
    assert recipe["id"] == "pear-spice-muffins-draft"
    assert pairing["season"] == "winter"
    assert pairing["source"] == "season-table"
    assert pairing["recipe_id"] == recipe["id"]
    assert pairing["reason"]


def test_empty_subject_explicit_season_beats_month():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance(
        "", None, month="2026-01-20", season="summer"
    )
    assert recipe["id"] == "cherry-pie-bars"
    assert pairing["season"] == "summer"
    assert pairing["source"] == "season-table"


def test_empty_subject_without_season_stays_none():
    from creative_automation.recipe_card import pick_recipe_with_provenance

    recipe, pairing = pick_recipe_with_provenance("", None)
    assert recipe is None
    assert pairing["source"] == "none"
    assert pairing["recipe_id"] is None
    assert pairing["season"] is None

    # stop-words-only input has no pairing subject either
    recipe, pairing = pick_recipe_with_provenance("the and", "mix")
    assert recipe is None
    assert pairing["source"] == "none"


def test_empty_subject_legacy_picker_serves_season_table():
    from creative_automation.recipe_card import _pick_recipe

    assert _pick_recipe("", None, season="fall")["id"] == "pumpkin-oat-muffins"
    assert _pick_recipe("", None) is None
