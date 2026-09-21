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
