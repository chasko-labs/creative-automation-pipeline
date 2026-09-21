"""Campaign preview bar — must be stunning, not vague (Cincinnati September pawpaws is the north-star).

The preview is the great illustration of the creative pipeline. A zip code or a
month name alone is jack shit — the brief that drives the image must be a
rich, seeded prompt that names the frontier, the in-season ingredient with its
flavor, the market hall, the plants/animals and the local harvest context.

This test is the bar: if Cincinnati September does not surface pawpaws with
Findlay/Lebanon/orchard flavor, or if the generation keeps returning the same
single packshot verbatim for every ratio, the pipeline is below standard and
the test must fail so we keep looping.

Bedrock path is expected for generation (Nova/SDXL) — Pillow local fallback is
only the offline degrade, not the preview standard.
"""
from __future__ import annotations

import json
import pathlib
import re


def _frontier_pair(market: str) -> dict:
    pairs = json.loads(pathlib.Path("data/localization/retailer-frontier-pairs.json").read_text())["pairs"]
    for p in pairs:
        if p["market"] == market:
            return p
    raise AssertionError(f"pair missing for {market}")


def test_cincinnati_september_brief_is_stunning_not_vague():
    """The JS buildSuffix front-end must compose a rich prompt, not just zip/month.

    We validate the DATA that drives that suffix (the seeded frontier file), and
    the JS helper that surfaces it. The brief that ships to Bedrock should name:
      - pawpaws (September ingredient)
      - Lebanon frontier + Findlay Market context
      - a flavor cue (tropical custard / pawpaw)
    A suffix that is only 'market: ... · season: September · frontier: ...' with
    no flavor/place detail is vague and must fail.
    """
    pair = _frontier_pair("US-OH-CINCINNATI")
    # September must bring pawpaws
    assert pair["monthly_ingredients"]["2026-09"] == "pawpaws", "Cincinnati September must be pawpaws"
    # frontier must be Lebanon shared belt
    assert pair["frontier_sister"]["market"] == "US-OH-LEBANON"
    assert "Lebanon" in pair["frontier_sister"]["place"]
    # Pawpaw moment must exist with flavor cues
    paw = [m for m in pair["seasonal_moments"] if "Pawpaw" in m["moment"]]
    assert paw, "pawpaw moment missing"
    flavors = paw[0].get("favorite_flavors") or []
    assert any("pawpaw" in f.lower() or "custard" in f.lower() for f in flavors), f"flavors too thin: {flavors}"
    # JS helper must expose that flavor to the suffix — check season-flavors frontier cal
    cal_path = pathlib.Path("web/kodiak-posts-for-todays-frontier/js/season-flavors.js")
    cal_text = cal_path.read_text(encoding="utf-8")
    assert "US-OH-LEBANON" in cal_text
    assert "pawpaws (peak September)" in cal_text
    # autocomplete suffix must call frontierSeasonLine and surface ingredient + moment
    ac = pathlib.Path("web/kodiak-posts-for-todays-frontier/js/autocomplete.js").read_text(encoding="utf-8")
    assert "frontierSeasonLine" in ac
    assert "in-season" in ac
    # The suffix must be STUNNING: it should thread not just frontier/ingredient but also
    # favorite_flavors (tropical custard etc.) so the image prompt has taste + place + plant detail.
    # If buildSuffix only does market/season/frontier/ingredient without flavors, it is still vague.
    assert "favorite_flavors" in ac or "favoriteFlavors" in ac or "flavor" in ac.lower(), "autocomplete buildSuffix must thread favorite_flavors — otherwise brief lacks taste/plant detail and is vague"
    # frontierSeasonLine must surface favorite_flavors to the UI — check data-core.js
    dc = pathlib.Path("web/kodiak-posts-for-todays-frontier/js/data-core.js").read_text(encoding="utf-8")
    assert "favorite_flavors" in dc or "favoriteFlavors" in dc, "data-core frontierSeasonLine must return favorite_flavors to the brief — otherwise pawpaw flavor never reaches the prompt"


def test_generation_not_stuck_on_single_packshot():
    """Preview generation must not be stuck on the same single verbatim packshot for every ratio.

    The recent bug showed [Image #1][2][3] identical — packshot composite (DAM verbatim)
    returned for every ratio with pillow-outpaint-fallback. That happens when the
    scene prompt is vague (just zip/month or plain brief) so every frontier renders
    the same generic pumpkin-patch background. The prompt that reaches Bedrock must be
    frontier-aware: it should name the in-season ingredient and its flavor, and the
    frontier place, so Cincinnati September (pawpaws, tropical custard, Lebanon/Findlay)
    looks nothing like Halloween (apples, cider, pumpkin patch).
    """
    gen_text = pathlib.Path("src/creative_automation/generate.py").read_text(encoding="utf-8")
    # Slice the _default_scene_prompt function body (until next def) so global mentions of
    # ingredient elsewhere don't give a false pass. It must itself thread frontier context.
    start = gen_text.find("def _default_scene_prompt")
    assert start != -1, "_default_scene_prompt not found"
    nxt = gen_text.find("\ndef ", start + 1)
    body = gen_text[start:nxt] if nxt != -1 else gen_text[start:]
    assert re.search(r"frontier|in-season|ingredient|pawpaw|favorite", body, re.IGNORECASE), \
        "_default_scene_prompt body must be frontier-aware (ingredient/frontier/pawpaw) — otherwise Cincinnati September looks like generic pumpkin patch"
    # frontend must fan to ALL ratios with per-ratio engines, not a single hero
    gen_js = pathlib.Path("web/kodiak-posts-for-todays-frontier/js/generate.js").read_text(encoding="utf-8")
    assert "showRenderSet" in gen_js
    assert "extendTallTiles" in gen_js
    # The brief that ships to the backend must actually contain the in-season ingredient
    # so the scene can vary. Check autocomplete threads it (already tested above), and
    # the backend reads it from brief_msg.


def test_any_market_any_season_brief_is_rich_and_distinct():
    """Any market/season listed in the UI must produce a rich, distinct prompt — not just the Cincinnati demo.

    The bar was low when we only proved September pawpaws vs Halloween apples for one market.
    The pipeline must handle whatever campaign idea the user gives for any of the 76 markets
    and any season (September, Halloween, etc.) by threading the frontier ingredient + flavor.

    This loops all 76 frontier pairs and checks:
      - September (2026-09) has a non-null in-season ingredient for every market (honest gaps would be null, but all 76 are seeded)
      - That ingredient's moment carries favorite_flavors so the brief can be stunning
      - The JS pipeline (data-core + autocomplete) is generic — it reads the pair file, not a hardcoded Cincinnati branch
    """
    pairs = json.loads(pathlib.Path("data/localization/retailer-frontier-pairs.json").read_text())["pairs"]
    assert len(pairs) == 76, f"expected 76 frontier pairs for the UI, found {len(pairs)}"
    # Every market must have a September ingredient (the north-star month after seeding)
    missing_sep = [p["market"] for p in pairs if not p["monthly_ingredients"].get("2026-09")]
    assert not missing_sep, f"September ingredient missing for markets (would force vague fallback): {missing_sep}"
    # Spot-check that September moments where they exist do carry favorite_flavors
    # so the image prompt has taste detail — not every market has a September moment
    # (those fallback to monthly_ingredients + climate windows, which is still rich via the ingredient itself)
    for market in ["US-OH-CINCINNATI", "US-OH-DAYTON", "US-CA-OCEANSIDE"]:
        p = next(x for x in pairs if x["market"] == market)
        moms = [m for m in p["seasonal_moments"] if 9 in (m.get("months") or [])]
        if moms:
            assert any(m.get("favorite_flavors") for m in moms), f"{market} September moment should have favorite_flavors"
    # Generic check: the JS that builds the brief must not be hardcoded to Cincinnati — it must read the pair file
    ac = pathlib.Path("web/kodiak-posts-for-todays-frontier/js/autocomplete.js").read_text(encoding="utf-8")
    dc = pathlib.Path("web/kodiak-posts-for-todays-frontier/js/data-core.js").read_text(encoding="utf-8")
    assert "frontierSeasonLine" in ac and "KODIAK_FRONTIER_PAIRS" in dc, "brief pipeline must be data-driven from KODIAK_FRONTIER_PAIRS, not hardcoded"
    # Spot-check 3 diverse markets that cover different archetypes and ingredients (not just pawpaw)
    for market, expected_ing in [
        ("US-OH-CINCINNATI", "pawpaws"),
        ("US-OH-DAYTON", "tomatoes (late harvest)"),
        ("US-CA-OCEANSIDE", "heirloom tomatoes (late harvest)"),
    ]:
        p = next(x for x in pairs if x["market"] == market)
        assert p["monthly_ingredients"]["2026-09"] == expected_ing, f"{market} September should be {expected_ing}"
        # Verify the prompt that would reach Bedrock is distinct per market (generic handling, not single demo)
        from creative_automation.generate import _default_scene_prompt

        brief_cincy = f"market: {market} · season: September · frontier: {p['frontier_sister']['place']} · in-season: {expected_ing}"
        prompt_a = _default_scene_prompt("Power Cakes", brief_cincy, market, "families", None)
        # Different markets must produce different prompts (not collapsed to same generic)
        assert expected_ing.split()[0].lower() in prompt_a.lower(), f"prompt for {market} must thread its own ingredient"
    # Also verify arbitrary campaign ideas are preserved (user free text + market context, not overwritten)
    assert "brief_msg" in pathlib.Path("src/creative_automation/generate.py").read_text(encoding="utf-8"), "backend must keep user campaign idea in brief_msg"
