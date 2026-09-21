"""Ohio frontier seeding contract: Cincinnati + Dayton resolve to Lebanon.

Both markets carry a full 12-month pairs calendar (with a confirmed October
Halloween moment), 12 emitted recipe cards each, and a season-aware frontend
line — so the brief, the frontier row, and the gallery never fall back to
static cues or empty states for these markets.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAIRS = REPO_ROOT / "data" / "localization" / "retailer-frontier-pairs.json"
FRONTEND_DATA = (
    REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js" / "data-core.js"
)
CARDS_JS = (
    REPO_ROOT
    / "web"
    / "kodiak-posts-for-todays-frontier"
    / "js"
    / "recipe-cards-data.js"
)
WEB_PAIRS_JS = (
    REPO_ROOT
    / "web"
    / "kodiak-posts-for-todays-frontier"
    / "js"
    / "recipes-frontier-pairs.js"
)

OHIO_MARKETS = ("US-OH-CINCINNATI", "US-OH-DAYTON")


def _pairs() -> dict[str, dict]:
    doc = json.loads(PAIRS.read_text(encoding="utf-8"))
    return {p["market"]: p for p in doc["pairs"]}


def test_ohio_pairs_cover_all_twelve_months() -> None:
    pairs = _pairs()
    for code in OHIO_MARKETS:
        months = pairs[code]["monthly_ingredients"]
        assert len(months) == 12, f"{code}: {len(months)} months"
        assert {m.split("-")[1] for m in months} == {f"{i:02d}" for i in range(1, 13)}


def test_ohio_halloween_moment_covers_october() -> None:
    pairs = _pairs()
    for code in OHIO_MARKETS:
        october = [
            mo["moment"]
            for mo in pairs[code]["seasonal_moments"]
            if 10 in mo.get("months", [])
        ]
        assert any("halloween" in m.lower() for m in october), (
            f"{code} October moments: {october}"
        )


def test_ohio_web_pairs_emit_in_sync() -> None:
    text = WEB_PAIRS_JS.read_text(encoding="utf-8")
    for code in OHIO_MARKETS:
        assert f'"market": "{code}"' in text, f"{code} missing from web pairs"
        assert "Halloween cider + pumpkin-patch weekends (Oct)" in text


def test_ohio_recipe_cards_emitted_per_market() -> None:
    text = CARDS_JS.read_text(encoding="utf-8")
    for code in OHIO_MARKETS:
        assert f'"{code}"' in text, f"{code} missing from cards book"


def test_dayton_cue_has_no_daylight_hour_claim() -> None:
    text = FRONTEND_DATA.read_text(encoding="utf-8")
    assert "15-hour" not in text
