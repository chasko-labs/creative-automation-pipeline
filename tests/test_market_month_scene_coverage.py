"""Every market-month brief carries place, season, and flavor — end to end.

Locks in the QA image-sweep invariant against the SHIPPED artifact (the
emitted recipes-frontier-pairs.js the browser actually reads), not just the
source JSON: builds the frontend-style brief suffix for all 82 markets x 12
months from the emitted payload + market cues, and asserts the scene builder
distills a setting clause every time and the in-season segment keeps its
flavors parenthetical wherever a confirmed moment names flavors.

Runs the full 984-cell grid in ~seconds (offline, deterministic).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from creative_automation.scene_prompts import _brief_setting_clause

REPO = Path(__file__).resolve().parents[1]
MONTHS = [f"2026-{m:02d}" for m in range(1, 13)]


def _load():
    markets = json.load(open(REPO / "data/localization/store-finder-markets.json"))
    mkts = markets if isinstance(markets, list) else markets.get("markets", [])
    raw = (REPO / "web/kodiak-posts-for-todays-frontier/js/recipes-frontier-pairs.js").read_text()
    payload = raw.split("window.KODIAK_FRONTIER_PAIRS = ", 1)[1].strip().rstrip(";")
    pairs = {p["market"]: p for p in json.loads(payload)}
    return mkts, pairs


def _suffix(mkt, pair, month):
    """Python mirror of autocomplete.js buildSuffix (markers + separators)."""
    mnum = int(month.split("-")[1])
    parts = [f"market: {mkt.get('place')}"]
    if mkt.get("cue"):
        parts.append(f"ecology: {mkt['cue']}")
    moment_pick = None
    if pair is not None:
        for mo in pair.get("moments") or []:
            if mnum in (mo.get("months") or []) and mo.get("status") == "confirmed" and mo.get("moment"):
                if moment_pick is None or (
                    moment_pick.get("status") != "confirmed" and mo.get("status") == "confirmed"
                ):
                    moment_pick = mo
        place = (pair.get("frontier") or {}).get("place") or ""
        if place:
            parts.append(f"frontier: {place}" + (f" -- {moment_pick['moment']}" if moment_pick else ""))
        ingredient = (pair.get("monthly") or {}).get(month) or ""
        if ingredient:
            flav = moment_pick.get("favorite_flavors") if moment_pick else None
            tail = f" ({', '.join(flav)})" if flav else ""
            parts.append(f"in-season: {ingredient}{tail}")
    return " \u00b7 ".join(parts)


def test_every_market_month_brief_distills_setting():
    mkts, pairs = _load()
    assert len(mkts) >= 70
    bare = []
    for mkt in mkts:
        pair = pairs.get(mkt["market"])
        for month in MONTHS:
            if not _brief_setting_clause("base \u25c7 " + _suffix(mkt, pair, month)):
                bare.append((mkt["market"], month))
    assert not bare, f"{len(bare)} market-months with no place/season setting: {bare[:10]}"


def test_flavors_survive_where_moments_name_them():
    mkts, pairs = _load()
    missing = []
    for mkt in mkts:
        pair = pairs.get(mkt["market"])
        if pair is None:
            continue
        for month in MONTHS:
            mnum = int(month.split("-")[1])
            wants = any(
                (mo.get("favorite_flavors") and mnum in (mo.get("months") or [])
                 and mo.get("status") == "confirmed" and mo.get("moment"))
                for mo in pair.get("moments") or []
            )
            if wants and "(" not in _suffix(mkt, pair, month):
                missing.append((mkt["market"], month))
    assert not missing, f"{len(missing)} briefs dropped flavors: {missing[:10]}"


def test_manhattan_october_spot():
    mkts, pairs = _load()
    mkt = next(m for m in mkts if m["market"] == "US-NE-MANHATTAN")
    brief = _suffix(mkt, pairs["US-NE-MANHATTAN"], "2026-10")
    for token in ("Warwick", "cider", "apple cinnamon"):
        assert token.lower() in brief.lower(), f"{token} missing: {brief}"
