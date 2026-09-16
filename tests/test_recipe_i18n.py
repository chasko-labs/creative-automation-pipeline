"""Machine-translated recipe cards — offline-safe tests with a stub provider.

The real provider chain (AWS Translate -> Nova Micro -> dictionary ->
passthrough) is stubbed at recipe_i18n.translate_with_provenance so these
tests never touch the network and assert OUR logic: glossary pass/fail,
English fallback direction, provenance shape, and untouched prices/meta.
"""
import creative_automation.recipe_i18n as i18n
from creative_automation.recipe_i18n import allergen_ok, translate_recipe_texts


def _stub_provider(text, lang, market="US"):
    return ("T-" + text, "stub", True)


def test_english_passes_through_untouched():
    out = translate_recipe_texts("T", ["1/2 cup milk"], ["HEAT it."], "en")
    assert out["title"] == "T"
    assert out["ingredients"] == ["1/2 cup milk"]
    assert out["steps"] == ["HEAT it."]
    prov = out["provenance"]
    assert prov["machine_translated"] is False
    assert prov["allergen_fallback_lines"] == []


def test_glossary_pass_and_fail():
    assert allergen_ok("1/2 cup milk", "1/2 taza de leche", "es") is True
    assert allergen_ok("2 large eggs", "2 huevos grandes", "es") is True
    assert allergen_ok("1/2 cup milk", "1/2 cup milk", "es") is False
    assert allergen_ok("1 tsp cinnamon", "1 cucharadita de canela", "es") is True
    # unsupported glossary language fails closed on allergen lines only
    assert allergen_ok("1/2 cup milk", "anything", "xx") is False
    assert allergen_ok("1 tsp cinnamon", "anything", "xx") is True


def test_allergen_lines_fall_back_to_english(monkeypatch):
    monkeypatch.setattr(i18n, "translate_with_provenance", _stub_provider)
    out = translate_recipe_texts(
        "Winter Squash Morning Muffins",
        ["2 large eggs", "1 teaspoon cinnamon"],
        ["HEAT the oven."],
        "es",
    )
    assert out["ingredients"][0] == "2 large eggs"
    assert out["ingredients"][1] == "T-1 teaspoon cinnamon"
    assert out["steps"] == ["T-HEAT the oven."]
    assert out["title"] == "T-Winter Squash Morning Muffins"
    prov = out["provenance"]
    assert prov["machine_translated"] is True
    assert prov["human_reviewed"] is False
    assert prov["allergen_fallback_lines"] == ["ingredient:1"]
    assert prov["providers"] == ["stub"]


def test_card_data_carries_translation_per_language(monkeypatch):
    from creative_automation.recipe_card import build_recipe_card_data

    monkeypatch.setattr(i18n, "translate_with_provenance", _stub_provider)
    c = build_recipe_card_data("US-MW-BOISE", month="2026-10", lang="es")
    assert c["title"].startswith("T-")
    # English allergen lines fall back; prices and meta ride along untouched
    assert c["ingredients"][2] == {"qty_name": "2 large eggs", "price": "$0.70"}
    assert c["meta"]["est_cost"] == "$8.40"
    assert c["recipe"]["name"] == "Winter Squash Morning Muffins"
    tprov = c["provenance"]["translation"]
    assert tprov["lang"] == "es"
    assert tprov["machine_translated"] is True
    assert tprov["human_reviewed"] is False
    assert "ingredient:3" in tprov["allergen_fallback_lines"]


def test_card_data_english_unchanged():
    from creative_automation.recipe_card import build_recipe_card_data

    c = build_recipe_card_data("US-MW-BOISE", month="2026-10")
    assert c["title"] == "Winter Squash Morning Muffins"
    assert c["ingredients"][0]["price"] == "$2.75"
    assert "translation" not in c["provenance"]
