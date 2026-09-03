"""North-star acceptance tests (agentcore D3) — the capstone definition of done.

Two PO prompts, encoded end to end over run_campaign (D1):

  A) SF BAY — power-cakes for bay-area retailers + a frontier subscription variant.
     Market US-CA-PESCADERO (legacy US-W-SF). September in-season pick is strawberries;
     retailers include Costco. Asserts multi-platform + multi-language fan-out, recipe
     cards referencing the Pescadero September ingredient, and a subscription variant.

  B) ATLANTA — Publix (Plaza Midtown, 950 W Peachtree St NW) + Sandersville frontier
     sister. Market US-SE-ATL, month 2026-09. Asserts recipe cards reference muscadine
     grapes, a Publix retailer-lockup PLAN entry exists carrying the Atlanta store
     address, and assets are iso-named + safety-clean.

Plus the general invariants the whole pipeline lane must hold: every emitted string is
safety-clean, every asset is iso-named (ISO_NAME_RE), non-English variants get dialect
handling where a KB exists, and an unknown/unpaired market degrades without crashing.

Offline + deterministic: B1 runs its mock fallback with no AWS creds, B4 composes local
cards, the lockup step is pure resolution. No network, no credentials.
"""
from pathlib import Path

from creative_automation.campaign import run_campaign
from creative_automation.naming import ISO_NAME_RE


# --------------------------------------------------------------------------- #
# fixtures — the two north-star briefs
# --------------------------------------------------------------------------- #
def _sf_brief() -> dict:
    return {
        "campaign_name": "Power Cakes — Bay Area Frontier",
        "brand": "KODIAK",
        "market": "US-CA-PESCADERO",
        "target_region": "US",
        "audience": "Bay Area families + frontier no-cal subscription seekers",
        "campaign_message": "Power-cakes fuel for the Pescadero frontier.",
        "products": [
            {
                "id": "power-cakes",
                "name": "Buttermilk Power Cakes",
                "description": "14g protein whole grain flapjack and waffle mix",
            }
        ],
        "retailers": ["Costco", "Safeway"],
    }


def _atlanta_brief() -> dict:
    return {
        "campaign_name": "Frontier Breakfast — Atlanta Publix",
        "brand": "KODIAK",
        "market": "US-SE-ATL",
        "target_region": "US",
        "audience": "Southeast families 28-45, Publix shoppers, porch-breakfast",
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
        "retailers": ["Publix", "Walmart", "Kroger"],
    }


# --------------------------------------------------------------------------- #
# A) SF BAY north star
# --------------------------------------------------------------------------- #
def test_sf_campaign_fans_out_across_platforms_and_languages(tmp_path):
    result = run_campaign(_sf_brief(), out_dir=tmp_path, month="2026-09")
    campaign = result["campaign"]
    assert campaign["market"] == "US-CA-PESCADERO"

    # multiple platforms: instagram (1x1 + 9x16) + blog (16x9)
    platforms = {a["platform"] for a in result["assets"]}
    ratios = {a["ratio"] for a in result["assets"]}
    assert len(platforms) >= 2, f"expected multi-platform, got {platforms}"
    assert {"1x1", "9x16", "16x9"}.issubset(ratios)

    # multiple languages: EN + the Bay Area top-N (es, zh) from market-languages.json
    langs = {a["lang"] for a in result["assets"]}
    assert "en" in langs
    assert len(langs) >= 2, f"expected multi-language, got {langs}"
    # 1 product x 3 platform-ratios x 3 languages = 9 planned assets
    assert result["summary"]["asset_count"] == 9


def test_sf_recipe_cards_reference_pescadero_september_ingredient(tmp_path):
    result = run_campaign(_sf_brief(), out_dir=tmp_path, month="2026-09")
    assert result["campaign"]["ingredient"] == "strawberries"
    assert result["recipe_cards"], "expected at least one recipe card"
    # every generated card is tied to the real September Pescadero pick, not fabricated
    for card in result["recipe_cards"]:
        assert card["ingredient"] == "strawberries"
    # the ingredient surfaces in the English card copy
    en_cards = [c for c in result["recipe_cards"] if c["lang"] == "en"]
    assert en_cards
    blob = (
        en_cards[0]["text_blocks"]["title"]
        + " "
        + en_cards[0]["text_blocks"]["ingredient_line"]
    ).lower()
    assert "strawberr" in blob


def test_sf_subscription_variant_is_representable(tmp_path):
    # the frontier no-cal subscription variant: an explicit subscription channel plus
    # the standard instagram feed. The fan-out represents it as its own asset set.
    result = run_campaign(
        _sf_brief(),
        out_dir=tmp_path,
        month="2026-09",
        platforms={"subscription-email": ["16x9"], "instagram": ["1x1"]},
    )
    sub_assets = [a for a in result["assets"] if a["platform"] == "subscription-email"]
    assert sub_assets, "subscription variant not representable in the fan-out"
    # subscription assets are still iso-named + safety-clean like every other asset
    for a in sub_assets:
        assert ISO_NAME_RE.match(a["iso_name"]), f"not iso-named: {a['iso_name']}"
        assert a["safety"]["clean"] is True
        assert "subscription-email" in a["iso_name"]


def test_sf_costco_lockup_plan_carries_bay_area_address(tmp_path):
    result = run_campaign(_sf_brief(), out_dir=tmp_path, month="2026-09")
    costco = [lk for lk in result["lockups"] if lk["retailer"] == "costco"]
    assert costco, "expected a Costco retailer-lockup plan entry"
    assert costco[0]["store_address"] is not None
    assert "San Francisco" in costco[0]["store_address"]
    # it is a PLAN, not a render — the executor is the D2 compositor
    assert costco[0]["generated"] is False
    assert costco[0]["executor"] == "lockup.compose_retailer_lockup"


# --------------------------------------------------------------------------- #
# B) ATLANTA north star
# --------------------------------------------------------------------------- #
def test_atlanta_recipe_cards_reference_muscadine_grapes(tmp_path):
    result = run_campaign(_atlanta_brief(), out_dir=tmp_path, month="2026-09")
    assert result["campaign"]["ingredient"] == "muscadine grapes"
    assert result["recipe_cards"]
    for card in result["recipe_cards"]:
        assert card["ingredient"] == "muscadine grapes"
    en_cards = [c for c in result["recipe_cards"] if c["lang"] == "en"]
    blob = (
        en_cards[0]["text_blocks"]["title"]
        + " "
        + en_cards[0]["text_blocks"]["ingredient_line"]
    ).lower()
    assert "muscadine" in blob


def test_atlanta_publix_lockup_plan_has_plaza_midtown_address(tmp_path):
    result = run_campaign(_atlanta_brief(), out_dir=tmp_path, month="2026-09")
    publix = [lk for lk in result["lockups"] if lk["retailer"] == "publix"]
    assert publix, "expected a Publix retailer-lockup plan entry"
    # canonical Plaza Midtown address from the retailer-frontier pair metro_location
    assert publix[0]["store_address"] == "950 W Peachtree St NW, Atlanta, GA 30309"
    assert ISO_NAME_RE.match(publix[0]["iso_name"])


def test_atlanta_assets_are_iso_named_and_safety_clean(tmp_path):
    result = run_campaign(_atlanta_brief(), out_dir=tmp_path, month="2026-09")
    assert result["assets"]
    for a in result["assets"]:
        assert ISO_NAME_RE.match(a["iso_name"]), f"not iso-named: {a['iso_name']}"
        assert a["safety"]["clean"] is True
    # 2 products x 3 platform-ratios x 3 languages (en, es, ko) = 18 assets
    assert result["summary"]["asset_count"] == 18


def test_atlanta_unknown_retailers_skipped_without_crashing(tmp_path):
    result = run_campaign(_atlanta_brief(), out_dir=tmp_path, month="2026-09")
    # Walmart + Kroger have no logo lookup -> no lockup plan, only Publix survives
    retailers = {lk["retailer"] for lk in result["lockups"]}
    assert retailers == {"publix"}
    assert any("Walmart" in w for w in result["summary"]["warnings"])
    assert any("Kroger" in w for w in result["summary"]["warnings"])


# --------------------------------------------------------------------------- #
# general invariants across any campaign
# --------------------------------------------------------------------------- #
def test_every_emitted_string_is_safety_clean(tmp_path):
    for brief in (_sf_brief(), _atlanta_brief()):
        result = run_campaign(brief, out_dir=tmp_path, month="2026-09")
        assert result["summary"]["safety"]["clean"] is True
        for a in result["assets"]:
            assert a["safety"]["clean"] is True
        for c in result["recipe_cards"]:
            assert c["safety"]["clean"] is True


def test_profanity_in_brief_message_is_redacted_not_emitted(tmp_path):
    brief = _atlanta_brief()
    brief["campaign_message"] = "This damn breakfast is the best, no bullshit."
    result = run_campaign(brief, out_dir=tmp_path, month="2026-09")
    for a in result["assets"]:
        assert "damn" not in a["headline"].lower()
        assert "bullshit" not in a["headline"].lower()
        assert a["safety"]["clean"] is True
    # the aggregate campaign verdict stays clean and the redaction is recorded
    assert result["summary"]["safety"]["clean"] is True
    assert result["summary"]["safety_redactions"], "redaction not recorded on summary"


def test_every_asset_is_iso_named(tmp_path):
    for brief in (_sf_brief(), _atlanta_brief()):
        result = run_campaign(brief, out_dir=tmp_path, month="2026-09")
        for a in result["assets"]:
            assert ISO_NAME_RE.match(a["iso_name"]), f"not iso: {a['iso_name']}"
        for c in result["recipe_cards"]:
            assert ISO_NAME_RE.match(Path(c["card_path"]).name)


def test_non_english_variants_get_dialect_handling_where_kb_exists(tmp_path):
    # Las Cruces Spanish (US-SW) resolves the es dialect KB via the loose region match
    # in locales, so a Spanish campaign there carries dialect handling on its non-English
    # assets. The base copy's standard-Spanish "panqueques" swaps to the border-region
    # local form "hotcakes" — the pipeline resolving dialect through the market key with
    # no region override. A market with no KB simply records no swaps rather than faking.
    brief = {
        "market": "US-SW-LASCRUCES",
        "campaign_message": "Panqueques con proteína para la frontera.",
        "products": [
            {"id": "power-cakes", "name": "Buttermilk Power Cakes", "description": "flapjack waffle mix"}
        ],
        "retailers": [],
    }
    result = run_campaign(brief, out_dir=tmp_path, month="2026-09", languages=["es"])
    es_assets = [a for a in result["assets"] if a["lang"] == "es"]
    assert es_assets
    # the es-SW trap panqueques -> hotcakes fires on the Spanish copy
    swapped = any(
        ("panqueques", "hotcakes") in {(s["from"], s["to"]) for s in a["dialect_applied"]}
        for a in es_assets
    )
    assert swapped, "es-SW dialect swap did not fire where a KB exists"
    assert all("panqueques" not in a["headline"].lower() for a in es_assets)


def test_unknown_market_degrades_without_crashing(tmp_path):
    result = run_campaign("US-XX-NOWHERE", out_dir=tmp_path, month="2026-09")
    # no pair -> no ingredient, no cards, no lockups, en-only, but no crash
    assert result["campaign"]["ingredient"] is None
    assert result["summary"]["recipe_card_count"] == 0
    assert result["summary"]["lockup_count"] == 0
    assert result["campaign"]["languages"] == ["en"]
    # still returns a well-formed structure
    assert result["summary"]["safety"]["clean"] is True
    assert any("no retailer-frontier pair" in w for w in result["summary"]["warnings"])


def test_generated_vs_planned_is_explicit_in_return(tmp_path):
    result = run_campaign(_atlanta_brief(), out_dir=tmp_path, month="2026-09")
    # recipe cards are the only GENERATED artifacts (real PNG on disk)
    for c in result["recipe_cards"]:
        assert c["generated"] is True
        assert Path(c["card_path"]).exists()
    # assets + lockups are PLANNED (copy + naming + resolution, no pixel render)
    for a in result["assets"]:
        assert a["generated"] is False
        assert a["render_hint"] == "run_pipeline"
    for lk in result["lockups"]:
        assert lk["generated"] is False
    # summary mirrors the split
    assert result["summary"]["generated"]["recipe_cards"] == len(result["recipe_cards"])
    assert result["summary"]["planned"]["assets"] == len(result["assets"])
    assert result["summary"]["planned"]["lockups"] == len(result["lockups"])


def test_accepts_campaign_brief_object(tmp_path):
    from creative_automation.brief import CampaignBrief

    brief = CampaignBrief.model_validate(
        {
            "campaign_name": "Atlanta",
            "brand": "KODIAK",
            "target_region": "US",
            "target_market": "US-SE-ATL",
            "target_audience": "families",
            "campaign_message": "Protein-packed whole grains for your frontier.",
            "products": [
                {"id": "power-cakes", "name": "Buttermilk Power Cakes", "description": "flapjack waffle mix"},
                {"id": "oatmeal-cup", "name": "Protein Oatmeal Cup", "description": "maple oatmeal cup"},
            ],
        }
    )
    result = run_campaign(brief, out_dir=tmp_path, month="2026-09")
    assert result["campaign"]["market"] == "US-SE-ATL"
    assert result["summary"]["asset_count"] > 0
    assert result["campaign"]["ingredient"] == "muscadine grapes"



# --------------------------------------------------------------------------- #
# UNIT 1 — live render wiring (B2 hardening + D1 planned -> real pixels)
# --------------------------------------------------------------------------- #
def _tiny_render_brief() -> dict:
    # one product, one platform/ratio, EN only -> a single asset so the offline mock
    # render (nova mock + enhance + compose) stays fast enough for CI
    return {
        "market": "US-SE-ATL",
        "campaign_message": "Protein-packed whole grains for your frontier.",
        "products": [
            {
                "id": "power-cakes",
                "name": "Buttermilk Power Cakes",
                "description": "14g protein flapjack and waffle mix",
            }
        ],
        "retailers": [],
    }


def test_render_false_leaves_assets_planned(tmp_path):
    # default behavior: no render flag -> assets stay planned copy+naming, no PNGs
    result = run_campaign(_atlanta_brief(), out_dir=tmp_path, month="2026-09")
    assert result["summary"]["rendered"] is False
    for a in result["assets"]:
        assert a["generated"] is False
        assert a["render_hint"] == "run_pipeline"
        assert "file_path" not in a
    assert result["summary"]["generated"]["assets"] == 0
    assert result["summary"]["planned"]["assets"] == len(result["assets"])


def test_render_true_produces_real_iso_named_pngs_offline(tmp_path):
    # render=True, offline (no creds) -> real PNGs via the mock hero path, iso-named,
    # each asset flips generated=True with hero_source="mock"
    result = run_campaign(
        _tiny_render_brief(),
        out_dir=tmp_path,
        month="2026-09",
        platforms={"instagram": ["1x1"]},
        languages=["en"],
        render=True,
    )
    assert result["summary"]["rendered"] is True
    assert result["assets"]
    for a in result["assets"]:
        assert a["generated"] is True, f"asset not flipped generated: {a['iso_name']}"
        assert a["hero_source"] == "mock", f"expected mock offline, got {a['hero_source']}"
        # the recorded file path is the iso-named PNG and it exists on disk
        fp = Path(a["file_path"])
        assert fp.exists(), f"rendered png missing: {fp}"
        assert fp.name == a["iso_name"]
        assert ISO_NAME_RE.match(fp.name), f"not iso-named: {fp.name}"
    # summary counts mirror the flip
    assert result["summary"]["generated"]["assets"] == len(result["assets"])
    assert result["summary"]["planned"]["assets"] == 0


def test_render_true_png_has_expected_ratio_dimensions(tmp_path):
    from PIL import Image

    result = run_campaign(
        _tiny_render_brief(),
        out_dir=tmp_path,
        month="2026-09",
        platforms={"instagram": ["1x1"]},
        languages=["en"],
        render=True,
    )
    a = result["assets"][0]
    img = Image.open(a["file_path"])
    assert img.size == (1080, 1080), f"{a['iso_name']} wrong size {img.size}"


def test_render_true_cohesion_check_skipped_offline_not_faked(tmp_path):
    # cr-3 cohesion re-embed needs bedrock; offline it must be skipped-with-a-reason,
    # never a fabricated similarity verdict
    result = run_campaign(
        _tiny_render_brief(),
        out_dir=tmp_path,
        month="2026-09",
        platforms={"instagram": ["1x1"]},
        languages=["en"],
        render=True,
    )
    for a in result["assets"]:
        cohesion = a["cohesion"]
        assert cohesion["checked"] is False
        assert cohesion["skipped"] is True
        assert "reason" in cohesion and cohesion["reason"]
        # no faked score
        assert "embed_norm" not in cohesion


def test_render_true_keeps_headline_as_overlay_and_safety_clean(tmp_path):
    # cr-1: the headline is overlay copy via compose, never the Nova prompt. The planned
    # headline still travels on the asset (compose receives it) and the asset renders —
    # the no-text-in-prompt guarantee lives in generate.py.
    result = run_campaign(
        _tiny_render_brief(),
        out_dir=tmp_path,
        month="2026-09",
        platforms={"instagram": ["1x1"]},
        languages=["en"],
        render=True,
    )
    for a in result["assets"]:
        assert a["headline"]
        assert a["safety"]["clean"] is True
        assert Path(a["file_path"]).exists()
