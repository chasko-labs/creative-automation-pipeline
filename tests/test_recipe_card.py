"""Recipe-card generator (agentcore B4) — offline path.

Atlanta US-SE-ATL September resolves to muscadine grapes (locales, never fabricated).
The card's text blocks flow through B1 so they are safety-gated + dialect-correct, and
the image layer stays text-free (cr-1) — text lives only in the layout panel. An
unfilled month must return the no-ingredient result without crashing.
"""
from pathlib import Path

from creative_automation import naming
from creative_automation.recipe_card import build_recipe_card


def test_atlanta_september_card_references_muscadine(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    assert result["ingredient"] == "muscadine grapes"
    # the ingredient surfaces in the card text (title or ingredient line)
    blob = (result["text_blocks"]["title"] + " " + result["text_blocks"]["ingredient_line"]).lower()
    assert "muscadine" in blob


def test_atlanta_card_text_blocks_pass_safety(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    assert result["safety"]["clean"] is True
    assert result["text_blocks"]["title"]
    assert result["text_blocks"]["steps"]


def test_atlanta_card_file_exists_and_is_iso_named(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    path = Path(result["card_path"])
    assert path.exists()
    assert naming.ISO_NAME_RE.match(path.name), f"not iso-named: {path.name}"
    # channel field is recipe-card per the B4 spec
    assert "recipe-card" in path.name


def test_atlanta_card_matched_a_recipe(tmp_path):
    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    assert result["recipe"] is not None
    assert result["recipe"]["id"]


def test_backfilled_january_resolves_to_turnips(tmp_path):
    # Atlanta January was backfilled to true 12/12 (all 73 markets now resolve
    # every 2026 month) -> resolves turnips with a written card, not a gap.
    result = build_recipe_card("US-SE-ATL", month="2026-01", out_dir=tmp_path)
    assert result["ingredient"] == "turnips"
    assert Path(result["card_path"]).exists()


def test_unseeded_month_returns_no_ingredient_without_crashing(tmp_path):
    # the honest-empty path must still work for months outside seeded data.
    result = build_recipe_card("US-SE-ATL", month="2027-01", out_dir=tmp_path)
    assert result["ingredient"] is None
    assert result["card_path"] is None
    assert "no in-season ingredient" in result["reason"]


def test_unknown_market_returns_no_pair_without_crashing(tmp_path):
    result = build_recipe_card("US-XX-NOWHERE", month="2026-09", out_dir=tmp_path)
    assert result["ingredient"] is None
    assert result["card_path"] is None
    assert "no retailer-frontier pair" in result["reason"]


def test_card_text_blocks_carry_no_bare_kodiak(tmp_path):
    import re

    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    blocks = [result["text_blocks"]["title"], result["text_blocks"]["ingredient_line"]]
    blocks.extend(result["text_blocks"]["steps"])
    for text in blocks:
        assert not re.search(r"(?<![#\w])[Kk][Oo][Dd][Ii][Aa][Kk]\b(?!\s+(Cakes?|Park\s+City))", text), text


def test_publish_offline_returns_none_key(tmp_path):
    result = build_recipe_card(
        "US-SE-ATL", month="2026-09", out_dir=tmp_path, publish=True
    )
    # asset store unconfigured in CI: card still composes, asset_key degrades to None.
    assert Path(result["card_path"]).exists()
    assert result["asset_key"] is None


def test_publish_card_never_throws_without_asset_store(tmp_path):
    from creative_automation.recipe_card import publish_card

    assert publish_card(tmp_path / "nope.jpg") is None


def test_featured_for_beats_overlap_lottery():
    from creative_automation.recipe_card import _pick_recipe

    assert _pick_recipe("Half Moon Bay pumpkin", None)["id"] == "pumpkin-oat-muffins"
    assert _pick_recipe("spinach", None)["id"] == "savory-greens-fritters-draft"
    assert _pick_recipe("rainbow chard", None)["id"] == "savory-greens-fritters-draft"
    # uncurated months keep overlap behavior (no silent reshuffle)
    assert _pick_recipe("strawberries", None)["id"] == "yogurt-pie"
    assert _pick_recipe("muscadine grapes", None)["id"] == "roasted-grape-flapjack-topper-draft"


def test_fresh_noise_never_outvotes_real_food_token():
    # QA sweep (82 markets x 26 seasons): "fresh cider" tied apple-cider-donuts
    # ("cider") with summer-vegetable-tostada (via "fresh microgreens") and the
    # id tiebreak served the summer tostada in October. "fresh" is stopword
    # noise, so the true food token must win outright.
    from creative_automation.recipe_card import _pick_recipe

    assert _pick_recipe("fresh cider", None)["id"] == "apple-cider-donuts"


def test_curated_pairings_route_to_honest_recipes():
    from creative_automation.recipe_card import _pick_recipe

    assert _pick_recipe("sweet cherries", None)["id"] == "cherry-pie-bars"
    assert _pick_recipe("avocado (florida)", None)["id"] == "avocado-pancakes"
    assert _pick_recipe("meyer lemon", None)["id"] == "single-serve-lemon-ricotta-flapjack-cup"
    # "green and red chile" names green chile across the conjunction, so the
    # green-chile draft (lowest id among the honest curators) wins the
    # no-context tiebreak; market+month context rotates the two (sweep).
    assert _pick_recipe("green and red chile", None)["id"] == "green-chile-cheddar-bake-draft"
    assert _pick_recipe("boiled peanuts", None)["id"] == "boiled-peanut-oat-bites-draft"
    assert _pick_recipe("huckleberries", None)["id"] == "huckleberry-flapjack-topper-draft"
    assert _pick_recipe("celery", None)["id"] == "celery-parmesan-pancakes-draft"
    assert _pick_recipe("cremini mushrooms", None)["id"] == "mushroom-cheddar-muffins-draft"
    assert _pick_recipe("pears (storage)", None)["id"] == "pear-spice-muffins-draft"


def test_new_drafts_have_honest_nulls_and_verb_first_steps():
    from creative_automation.recipe_card import build_recipe_card_data

    c = build_recipe_card_data("US-SE-ATL", month="2026-09")
    assert c.get("title") == "Roasted Grape Flapjack Topper"
    c2 = build_recipe_card_data("US-CA-CASTROVILLE", month="2026-03")
    assert c2["meta"]["est_cost"] is None
    import json
    from pathlib import Path as _P

    catalog = json.loads(_P("data/recipes/kodiak-recipes.json").read_text())
    wanted = {
        "snap-pea-herb-fritters-draft", "mushroom-cheddar-muffins-draft",
        "huckleberry-flapjack-topper-draft", "fig-honey-muffins-draft",
        "pear-spice-muffins-draft", "wild-rice-cheddar-pancakes-draft",
        "persimmon-spice-muffins-draft", "green-bean-parmesan-fritters-draft",
        "celery-parmesan-pancakes-draft", "date-oat-breakfast-cookies-draft",
        "boiled-peanut-oat-bites-draft"}
    drafts = [r for r in catalog if r["id"] in wanted]
    assert len(drafts) == 11
    for r in drafts:
        assert r.get("prepTime") in (None, ""), r["id"]
        assert r.get("cookTime") in (None, ""), r["id"]
        assert r.get("yield") in (None, ""), r["id"]
        assert r["instructions"], r["id"]
        for step in r["instructions"]:
            assert not step.rstrip().endswith("!"), (r["id"], step)


def test_card_title_and_steps_are_real_content():
    from creative_automation.recipe_card import build_recipe_card_data

    c = build_recipe_card_data("US-CA-CASTROVILLE", month="2026-03")
    assert c.get("title") == "Broccoli Cauliflower Cheddar Fritters"
    assert c.get("recipe", {}).get("name") == c.get("title")
    assert c.get("steps"), "no exclamatory ad copy: steps are the real instructions"
    assert not any(s.rstrip().endswith("!") for s in c["steps"])
    assert c["steps"][0].startswith("STEAM")


def test_winter_squash_muffins_carry_verified_costs():
    from creative_automation.recipe_card import build_recipe_card_data

    # rotation sends Missoula (not Boise) to the muffins in Oct 2026;
    # the muffins keep their verified $8.40 cost record wherever they land.
    c = build_recipe_card_data("US-MW-MISSOULA", month="2026-10")
    assert c.get("title") == "Winter Squash Morning Muffins"
    assert [i["price"] for i in c["ingredients"]] == [
        "$2.75",
        "$2.00",
        "$0.70",
        "$0.30",
        "$1.65",
        "$0.75",
        "$0.20",
        "$0.05",
    ]
    assert c["meta"]["est_cost"] == "$8.40"
    assert "prices" not in c["provenance"]["values_unknown"]


def test_boise_october_rotates_to_griddle_cakes_with_costs():
    from creative_automation.recipe_card import build_recipe_card_data

    c = build_recipe_card_data("US-MW-BOISE", month="2026-10")
    assert c.get("title") == "Winter Squash Griddle Cakes"
    assert [i["price"] for i in c["ingredients"]] == [
        "$1.40",
        "$1.50",
        "$0.35",
        "$0.30",
        "$0.25",
        "$0.30",
        "$0.10",
        "$0.05",
    ]
    assert c["meta"]["est_cost"] == "$4.25"
    assert "prices" not in c["provenance"]["values_unknown"]


def test_market_seeded_rotation_spreads_shared_ingredients():
    from creative_automation.recipe_card import _pick_recipe

    # no market context keeps the legacy best-overlap winner exactly.
    assert (
        _pick_recipe("winter squash", None)["id"]
        == "winter-squash-morning-muffins-draft"
    )
    # same market+month is deterministic.
    first = _pick_recipe(
        "winter squash",
        "Buttermilk Power Cakes",
        market="US-MW-BOISE",
        month="2026-10",
    )["id"]
    second = _pick_recipe(
        "winter squash",
        "Buttermilk Power Cakes",
        market="US-MW-BOISE",
        month="2026-10",
    )["id"]
    assert first == second == "winter-squash-griddle-cakes-draft"
    # the nine markets sharing winter squash in Oct 2026 do not all show
    # the same card — both drafts appear, and every pick names the ingredient.
    oct_markets = [
        "US-MW-BOISE",
        "US-MW-DEN",
        "US-MW-JACKSONHOLE",
        "US-MW-MISSOULA",
        "US-MW-WASATCH",
        "US-MW-WASATCH-SLC",
        "US-UT-KAMASVALLEY",
        "US-W-BOULDER",
        "US-W-SACRAMENTO",
    ]
    winners = {
        _pick_recipe(
            "winter squash",
            "Buttermilk Power Cakes",
            market=m,
            month="2026-10",
        )["id"]
        for m in oct_markets
    }
    assert winners == {
        "winter-squash-griddle-cakes-draft",
        "winter-squash-morning-muffins-draft",
    }


def test_recipe_card_v1_schema_doc_matches_module_contract():
    # gh #304: the committed JSON Schema doc is the versioned contract; the
    # module's markers must agree with it (variant enum single-sourced here
    # until gh #303 lands the full taxonomy).
    import json
    from pathlib import Path as _P

    from creative_automation import recipe_card as _rc

    schema = json.loads(
        _P("data/recipes/recipe-card-v1.schema.json").read_text()
    )
    assert schema["$id"] == "https://kodiakcakes.com/schema/recipe-card-v1.json"
    assert _rc.RECIPE_CARD_DATA_SCHEMA == "recipe-card@v1"
    assert schema["properties"]["schema"]["const"] == _rc.RECIPE_CARD_DATA_SCHEMA
    assert schema["properties"]["variant"]["enum"] == list(_rc.RECIPE_CARD_VARIANTS)
    assert _rc.RECIPE_CARD_VARIANTS == ("hero-plus-layout",)
    assert _rc.RECIPE_CARD_V1_SCHEMA_PATH.exists()


def test_card_data_emits_v1_contract_fields():
    from creative_automation.recipe_card import build_recipe_card_data

    c = build_recipe_card_data("US-SE-ATL", month="2026-09")
    assert c["schema"] == "recipe-card@v1"
    assert c["variant"] == "hero-plus-layout"
    assert c["market"] == "US-SE-ATL"
    assert c["frontier_market"] == "US-GA-SENOIA"
    assert c["month"] == "2026-09"
    assert c["lang"] == "en"
    assert c["render"]["canvas"] == {"width": 1080, "height": 1080, "unit": "px"}
    assert c["render"]["hero_region"] == {"height": 560, "text_free": True}
    assert "hero" in c["render"]["text_free_regions"]


def test_card_data_objects_validate_against_v1():
    from creative_automation.recipe_card import (
        build_recipe_card_data,
        validate_recipe_card_v1,
    )

    filled = build_recipe_card_data("US-SE-ATL", month="2026-09")
    assert validate_recipe_card_v1(filled) == []
    empty = build_recipe_card_data("US-SE-ATL", month="2027-01")
    assert empty["ingredient"] is None
    assert empty["reason"]
    assert validate_recipe_card_v1(empty) == []


def test_validator_rejects_fabricated_and_malformed_cards():
    from creative_automation.recipe_card import (
        build_recipe_card_data,
        validate_recipe_card_v1,
    )

    good = build_recipe_card_data("US-SE-ATL", month="2026-09")
    bad_variant = dict(good, variant="pop-up-book")
    assert any("variant" in p for p in validate_recipe_card_v1(bad_variant))
    # no-ingredient result must not smuggle a recipe or title
    bad_empty = dict(good, ingredient=None, reason="no pick")
    assert any("recipe" in p for p in validate_recipe_card_v1(bad_empty))
    bad_lang = dict(good, lang="fr")
    assert any("lang" in p for p in validate_recipe_card_v1(bad_lang))
    assert validate_recipe_card_v1({}) != []


def test_card_data_round_trips_object_to_render(tmp_path):
    # gh #304 acceptance: build -> object -> render with no fabrication.
    from pathlib import Path

    from creative_automation import naming
    from creative_automation.recipe_card import (
        build_recipe_card_data,
        render_recipe_card_data,
        validate_recipe_card_v1,
    )

    card = build_recipe_card_data("US-SE-ATL", month="2026-09")
    assert validate_recipe_card_v1(card) == []
    path = Path(render_recipe_card_data(card, out_dir=tmp_path))
    assert path.exists()
    assert naming.ISO_NAME_RE.match(path.name)
    assert "recipe-card" in path.name
    # the honest empty state renders nothing, explicitly
    empty = build_recipe_card_data("US-SE-ATL", month="2027-01")
    assert render_recipe_card_data(empty, out_dir=tmp_path) is None


def test_build_recipe_card_marks_v1_contract(tmp_path):
    from creative_automation.recipe_card import build_recipe_card

    result = build_recipe_card("US-SE-ATL", month="2026-09", out_dir=tmp_path)
    assert result["schema"] == "recipe-card@v1"
    assert result["variant"] == "hero-plus-layout"


def test_recipe_art_overlay_prefers_published_zones(monkeypatch):
    import creative_automation.asset_store as asset_store
    from creative_automation.recipe_card import _overlay_recipe_art

    monkeypatch.setattr(
        asset_store,
        "recipe_art_exists",
        lambda slug, zone: slug == "winter-squash-griddle-cakes"
        and zone in ("technique", "finished_plate"),
    )
    base = {
        "raw_ingredient": "/recipe-art/winter-squash/raw_ingredient.png",
        "technique": "/recipe-art/winter-squash/technique.png",
        "finished_plate": "/recipe-art/winter-squash/finished_plate.png",
    }
    out = _overlay_recipe_art(base, {"art_slug": "winter-squash-griddle-cakes"})
    assert out["technique"] == "/recipe-art/winter-squash-griddle-cakes/technique.png"
    assert (
        out["finished_plate"]
        == "/recipe-art/winter-squash-griddle-cakes/finished_plate.png"
    )
    assert out["raw_ingredient"] == "/recipe-art/winter-squash/raw_ingredient.png"
    assert _overlay_recipe_art(base, {}) == base
