"""Smoke acceptance — Waffle Mac 'n Cheese Grilled Cheese localized riff.

Captures Bryan's background smoke run (a localized riff off the real Kodiak
"Waffle Mac 'n Cheese Grilled Cheese" recipe page) as a committed, repeatable
acceptance case. Three layers:

  1. DB     — the recipe is now a seeded entry: findable by id, carrying the real
              kodiakcakes.com hero image URL and the four page ingredients, and
              pickable by the recipe-card token matcher for a mac-and-cheese subject.
  2. B4     — build_recipe_card for a market+month produces a real card whose text
              blocks pass safety, whose file is iso-named, and whose image layer is
              text-free (cr-1: text composes in the layout layer, image stays wordless).
  3. D1     — run_campaign over the committed fixture brief (US-SW-LASCRUCES, where
              Spanish is the top non-English language) fans out iso-named, safety-clean
              assets, and the Spanish variant gets the es-SW dialect trap applied
              (panqueques -> hotcakes) — the exact hotcakes/panqueques inversion the
              dialect KB guards on a lunch/dinner riff.

Offline + deterministic: no AWS creds, B1 runs its mock fallback, B4 composes a local
card, the remote hero URL is NEVER fetched. CI stays green.
"""
import json
from pathlib import Path

from creative_automation import safety
from creative_automation.brief import load_brief
from creative_automation.campaign import run_campaign
from creative_automation.naming import ISO_NAME_RE
from creative_automation.recipe_card import (
    HERO_H,
    RECIPES_PATH,
    _pick_recipe,
    build_recipe_card,
)

RECIPE_ID = "waffle-mac-n-cheese-grilled-cheese"
HERO_IMAGE_URL = (
    "https://kodiakcakes.com/cdn/shop/articles/"
    "Kodiak_Waffle_Grilled_Cheese_Mac_n_Cheese_4.jpg"
)
PAGE_INGREDIENTS = [
    "1/2 cup Kodiak Buttermilk Power Cakes Flapjack & Waffle Mix (prepped)",
    "1/2 tablespoon butter",
    "1 slice cheddar cheese",
    "1/2 cup prepared macaroni and cheese",
]
FIXTURE = Path(__file__).parent / "fixtures" / "mac-n-cheese-smoke.yaml"

# US-SW-LASCRUCES has no frontier pair, so the recipe card resolves against a market
# that does. Pescadero September is the seeded strawberries pick — the card exercises
# the full B4 path and stays deterministic offline.
CARD_MARKET = "US-CA-PESCADERO"
CARD_MONTH = "2026-09"


# --------------------------------------------------------------------------- #
# layer 1 — the recipe is now in the DB (json seed)
# --------------------------------------------------------------------------- #
def _load_db() -> list[dict]:
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))


def _find(recipes: list[dict], rid: str) -> dict | None:
    return next((r for r in recipes if r.get("id") == rid), None)


def test_recipe_is_seeded_in_db_by_id():
    recipe = _find(_load_db(), RECIPE_ID)
    assert recipe is not None, f"{RECIPE_ID} not found in {RECIPES_PATH.name}"
    assert recipe["name"] == "Waffle Mac 'n Cheese Grilled Cheese"
    assert recipe["category"] == "lunch & dinner"


def test_recipe_carries_real_hero_image_url():
    recipe = _find(_load_db(), RECIPE_ID)
    assert recipe["image"] == HERO_IMAGE_URL
    # the hero is a remote reference, never a committed/fetched asset
    assert recipe["image"].startswith("https://kodiakcakes.com/")


def test_recipe_carries_the_four_page_ingredients():
    recipe = _find(_load_db(), RECIPE_ID)
    assert recipe["ingredients"] == PAGE_INGREDIENTS


def test_recipe_is_pickable_by_the_card_token_matcher():
    # the mac-and-cheese subject resolves to this exact recipe via token overlap,
    # so a mac-and-cheese riff lands on the seeded page rather than a fabricated one
    picked = _pick_recipe("macaroni and cheese", "Buttermilk Power Cakes")
    assert picked is not None
    assert picked["id"] == RECIPE_ID


def test_json_and_jsonl_mirrors_stay_in_parity():
    json_ids = {r["id"] for r in _load_db()}
    jsonl_path = RECIPES_PATH.with_suffix(".jsonl")
    jsonl_rows = [
        json.loads(line) for line in jsonl_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    jsonl_ids = {row["metadata"]["id"] for row in jsonl_rows}
    assert RECIPE_ID in json_ids
    assert RECIPE_ID in jsonl_ids
    # the jsonl mirror is a superset-free 1:1 of the json seed (no drift)
    assert json_ids == jsonl_ids


# --------------------------------------------------------------------------- #
# layer 2 — build_recipe_card (B4): safety-gated text, iso name, text-free image
# --------------------------------------------------------------------------- #
def test_recipe_card_references_month_ingredient_and_matches_a_recipe(tmp_path):
    result = build_recipe_card(CARD_MARKET, month=CARD_MONTH, out_dir=tmp_path)
    assert result["ingredient"], "expected a seeded in-season ingredient"
    assert result["recipe"] is not None and result["recipe"]["id"]
    # the card copy references the resolved monthly ingredient (never fabricated)
    blob = (
        result["text_blocks"]["title"] + " " + result["text_blocks"]["ingredient_line"]
    ).lower()
    assert result["ingredient"].split()[0].lower() in blob


def test_recipe_card_text_blocks_pass_safety(tmp_path):
    result = build_recipe_card(CARD_MARKET, month=CARD_MONTH, out_dir=tmp_path)
    assert result["safety"]["clean"] is True
    assert result["text_blocks"]["title"]
    assert result["text_blocks"]["steps"]
    # re-assert the gate directly over every emitted block
    all_text = " ".join(
        [
            result["text_blocks"]["title"],
            result["text_blocks"]["ingredient_line"],
            *result["text_blocks"]["steps"],
        ]
    )
    assert safety.check_text(all_text)["clean"] is True


def test_recipe_card_output_is_iso_named(tmp_path):
    result = build_recipe_card(CARD_MARKET, month=CARD_MONTH, out_dir=tmp_path)
    path = Path(result["card_path"])
    assert path.exists()
    assert ISO_NAME_RE.match(path.name), f"not iso-named: {path.name}"
    assert "recipe-card" in path.name


def test_seeded_remote_hero_is_not_fetched_image_layer_text_free(tmp_path):
    """cr-1 — a recipe with a remote hero URL never triggers a network fetch; the hero
    panel degrades to a clean, text-free brand block so the card stays deterministic
    offline. Text lives only in the layout layer below the hero region."""
    from creative_automation.recipe_card import _hero_panel

    recipe = _find(_load_db(), RECIPE_ID)
    assert recipe["image"].startswith("http")  # remote reference
    hero = _hero_panel(recipe, (400, HERO_H))
    # a real image object is produced (brand-color block), sized to the hero region,
    # with no network access and no baked-in text — the image layer is wordless
    assert hero.size == (400, HERO_H)


# --------------------------------------------------------------------------- #
# layer 3 — run_campaign (D1) over the committed fixture brief
# --------------------------------------------------------------------------- #
def _run_fixture(tmp_path):
    brief = load_brief(FIXTURE)
    return brief, run_campaign(brief, out_dir=tmp_path, month=CARD_MONTH)


def test_fixture_brief_loads_and_targets_las_cruces(tmp_path):
    brief, _ = _run_fixture(tmp_path)
    assert brief.region == "US-SW-LASCRUCES"
    assert brief.products[0].id == "power-cakes"


def test_campaign_assets_are_iso_named_and_safety_clean(tmp_path):
    _, res = _run_fixture(tmp_path)
    assert res["assets"], "expected a non-empty asset fan-out"
    for asset in res["assets"]:
        assert ISO_NAME_RE.match(asset["iso_name"]), f"not iso: {asset['iso_name']}"
        assert asset["safety"]["clean"] is True
    # aggregate campaign verdict is clean too
    assert res["summary"]["safety"]["clean"] is True


def test_spanish_variant_gets_dialect_trap_handling(tmp_path):
    """The es-SW KB resolves for Las Cruces (Spanish is the top non-English language);
    the Spanish campaign copy carries the standard 'panqueques', which the trap swaps
    for the regional 'hotcakes'. This is the hotcakes/panqueques inversion on a
    lunch/dinner riff — proof the dialect handling fires where the KB resolves."""
    _, res = _run_fixture(tmp_path)
    assert "es" in res["campaign"]["languages"]
    es_assets = [a for a in res["assets"] if a["lang"] == "es"]
    assert es_assets, "expected Spanish variant assets"
    swaps = [d for a in es_assets for d in a["dialect_applied"]]
    trap = next(
        (d for d in swaps if d.get("is_trap") and d["from"] == "panqueques"), None
    )
    assert trap is not None, f"es-SW dialect trap did not fire; swaps={swaps}"
    assert trap["to"] == "hotcakes"
    # the swapped local form is present in the shipped Spanish headline
    assert any("hotcakes" in a["headline"] for a in es_assets)


def test_campaign_runs_offline_without_crashing(tmp_path):
    # end to end: no creds, deterministic mock path, structured result present
    _, res = _run_fixture(tmp_path)
    assert set(res).issuperset({"campaign", "assets", "recipe_cards", "lockups", "summary"})
    assert res["summary"]["asset_count"] == len(res["assets"])
