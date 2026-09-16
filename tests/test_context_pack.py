"""Context-pack builder (agentcore A2) — offline RAG assembly from done artifacts.

Atlanta (US-SE-ATL) is the reference market: Publix + Sandersville frontier sister +
September muscadine grapes, es/ko languages, a food-subject cluster match, and real
Kodiak sample prompts. Every assertion here is a contract the generation units (B1/B4)
lean on, so a regression in any stitched source fails loudly.
"""
from creative_automation.brief import CampaignBrief
from creative_automation.context_pack import build_context_pack


def _atlanta_brief() -> CampaignBrief:
    return CampaignBrief.model_validate(
        {
            "campaign_name": "Frontier Breakfast — Atlanta Publix",
            "brand": "KODIAK",
            "target_region": "US",
            "target_market": "US-SE-ATL",
            "target_audience": "Southeast families 28-45, Publix shoppers, porch-breakfast",
            "campaign_message": "Protein-packed whole grains for your family's frontier.",
            "products": [
                {
                    "id": "power-cakes",
                    "name": "Buttermilk Power Cakes",
                    "description": "14g protein flapjack and waffle mix, whole grain buttermilk pancakes",
                },
                {
                    "id": "oatmeal-cup",
                    "name": "Protein Oatmeal Cup",
                    "description": "maple oatmeal breakfast cup",
                },
            ],
        }
    )


def test_atlanta_pack_stitches_retailer_and_frontier():
    pack = build_context_pack(_atlanta_brief(), month="2026-09")
    assert pack["market"] == "US-SE-ATL"
    assert "Publix" in pack["retailers"]["retailers"]
    assert pack["retailers"]["frontier_sister"] == "Sandersville, GA"


def test_atlanta_september_ingredient_not_fabricated():
    pack = build_context_pack(_atlanta_brief(), month="2026-09")
    assert pack["ingredient"]["ingredient"] == "muscadine grapes"
    assert pack["ingredient"]["month"] == "2026-09"


def test_atlanta_unfilled_month_says_none_not_a_guess():
    # October 2026 was backfilled to pecans; 2027 has no authored months, so the
    # honest-empty path must say None, not a guess
    pack = build_context_pack(_atlanta_brief(), month="2027-10")
    assert pack["ingredient"]["ingredient"] is None
    assert "no in-season ingredient on file for 2027-10" in pack["prompt_text"]


def test_atlanta_has_dialect_consideration_for_non_english_langs():
    pack = build_context_pack(_atlanta_brief(), month="2026-09")
    # Atlanta languages are es + ko; both are non-English so both get a consideration
    codes = {d["lang_code"] for d in pack["dialect_considerations"]}
    assert len(pack["dialect_considerations"]) >= 1
    assert "es" in codes
    # Atlanta (US-SE) has no seeded dialect KB — the pack must say so, not fake traps
    for d in pack["dialect_considerations"]:
        if not d["has_kb"]:
            assert "no dialect trap KB seeded" in d["note"]


def test_atlanta_matches_a_food_subject_cluster():
    pack = build_context_pack(_atlanta_brief(), month="2026-09")
    cm = pack["cluster_match"]
    assert cm["confidence"] in ("high", "medium", "low", "none")
    # power cakes / flapjack / waffle / oatmeal overlaps real cluster common_terms
    assert cm["confidence"] in ("high", "medium")
    assert cm["cluster"] is not None
    assert cm["cluster"]["cohesion_floor"] > 0.0
    assert cm["cluster"]["overlap_terms"]


def test_atlanta_pulls_real_sample_prompts():
    pack = build_context_pack(_atlanta_brief(), month="2026-09")
    assert len(pack["sample_prompts"]) >= 1
    assert all(sp["prompt"] for sp in pack["sample_prompts"])


def test_brand_rules_and_safety_note_present():
    pack = build_context_pack(_atlanta_brief(), month="2026-09")
    assert "#3B2316" in pack["brand_rules"]
    assert "cr-1" in pack["brand_rules"]
    assert "safety.check_text" in pack["safety_note"]
    assert pack["palette_anchor"] == "#3B2316"


def test_to_prompt_text_is_nonempty_and_compact():
    pack = build_context_pack(_atlanta_brief(), month="2026-09")
    text = pack["to_prompt_text"]()
    assert text
    assert text == pack["prompt_text"]
    # few-hundred-word pack — keep the prefix under ~2000 chars
    assert len(text) < 2000
    assert "US-SE-ATL" in text
    assert "Publix" in text
    assert "muscadine grapes" in text


def test_accepts_bare_market_string():
    pack = build_context_pack("US-SE-ATL", month="2026-09")
    assert pack["market"] == "US-SE-ATL"
    assert pack["place"] == "Atlanta, Georgia"
    # no products -> no cluster subject tokens -> honest 'none' with full list
    assert pack["cluster_match"]["confidence"] == "none"
    assert pack["cluster_match"]["cluster"] is None
    assert pack["cluster_match"]["all_clusters"]


def test_unknown_market_degrades_gracefully():
    pack = build_context_pack("US-XX-NOWHERE", month="2026-09")
    assert pack["retailers"]["has_pair"] is False
    assert pack["ingredient"]["has_pair"] is False
    assert pack["dialect_considerations"] == []
    text = pack["to_prompt_text"]()
    assert text  # still renders, no crash
    assert "no retailer-frontier pair seeded" in text


def test_dict_brief_input_supported():
    pack = build_context_pack(
        {
            "market": "US-SE-ATL",
            "audience": "families",
            "products": [{"name": "Buttermilk Power Cakes", "description": "flapjack waffle"}],
            "tags": ["breakfast"],
        },
        month="2026-09",
    )
    assert pack["market"] == "US-SE-ATL"
    assert pack["audience"] == "families"
    assert pack["cluster_match"]["cluster"] is not None
