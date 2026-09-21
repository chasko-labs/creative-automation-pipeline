"""Full-season coverage contract: every season option resolves for target markets.

For each of Ohio (Cincinnati, Dayton, Cleveland), San Diego, Oceanside,
Atlanta, and Park City, all 12 months + 4 seasons + 10 holidays must resolve
to a monthly ingredient AND a covering moment in
data/localization/retailer-frontier-pairs.json — the same resolution the
frontend frontierSeasonLine performs (month names, YYYY-MM keys, and the
season/holiday representative-month map owned by data-core.js
FRONTIER_SEASON_MONTHS).
"""
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PAIRS = REPO_ROOT / "data" / "localization" / "retailer-frontier-pairs.json"

TARGETS = (
    "US-OH-CINCINNATI",
    "US-OH-DAYTON",
    "US-MW-CLEVELAND",
    "US-W-SD",
    "US-CA-OCEANSIDE",
    "US-SE-ATL",
    "US-MW-PARKCITY-84098",
)

MONTHS = [
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
]
# Mirror of data-core.js FRONTIER_SEASON_MONTHS (representative months).
SEASON_MONTHS = {
    "spring": 5, "summer": 7, "fall": 10, "autumn": 10, "winter": 12,
    "new year": 1, "valentine's day": 2, "easter": 4, "memorial day": 5,
    "fourth of july": 7, "labor day": 9, "halloween": 10, "thanksgiving": 11,
    "christmas": 12, "holiday season": 12,
}
OPTIONS = (
    MONTHS + ["spring", "summer", "fall", "winter", "new year",
              "valentine's day", "easter", "memorial day",
              "fourth of july", "labor day", "halloween", "thanksgiving",
              "christmas", "holiday season"]
)


def _pairs() -> dict[str, dict]:
    doc = json.loads(PAIRS.read_text(encoding="utf-8"))
    return {p["market"]: p for p in doc["pairs"]}


def _month_of(option: str) -> int:
    if option in MONTHS:
        return MONTHS.index(option) + 1
    return SEASON_MONTHS[option]


def test_all_options_resolve_ingredient_and_moment() -> None:
    pairs = _pairs()
    failures = []
    for code in TARGETS:
        entry = pairs.get(code)
        assert entry is not None, f"{code}: no pairs entry"
        monthly = entry.get("monthly_ingredients") or {}
        covered: set[int] = set()
        for mo in entry.get("seasonal_moments") or []:
            covered.update(mo.get("months", []))
        for opt in OPTIONS:
            month = _month_of(opt)
            if not monthly.get(f"2026-{month:02d}"):
                failures.append(f"{code} {opt}: no monthly ingredient")
            if month not in covered:
                failures.append(f"{code} {opt}: no covering moment")
    assert not failures, "season gaps:\n" + "\n".join(failures)


def test_all_76_markets_cover_all_months_and_moments() -> None:
    """Durable full-matrix check: every of the 76 pairs × 26 seasons has distinct seasonal ingredient.

    26 = 12 months + 4 seasons (Winter/Spring/Summer/Fall/Autumn alias) + 10
    holidays. Months resolve to retailer-frontier-pairs.monthly_ingredients[2026-MM];
    holidays/seasons resolve to retailer-frontier-pairs.seasonal_moments[].available_ingredients[0]
    distinct per season (design token: available_ingredients[0], not generic).
    This is the 76×26=1976 distinct seasonal-ingredient contract, not a 12-month check.

    Behavior on gap: the pipeline's three-tier fallback (curated frontier calendar
    → CLIMATE_WIN → ARCHETYPES) accounts for missing entries without throwing — it
    returns a shoulder/olde line with source `frontier`/`archetype` and never
    fabricates a farm name. This test surfaces the gap via the contract so data
    can be repaired (e.g., ATL March auto-patched), rather than letting a vague
    brief reach the prompt. Failures here raise AssertionError with the market
    and season listed, which the caller can catch and handle as a data-repair
    signal.
    """
    pairs = _pairs()
    assert len(pairs) == 76, f"frontier pairs count drift: {len(pairs)} != 76"
    failures: list[str] = []
    for code, entry in pairs.items():
        monthly = entry.get("monthly_ingredients") or {}
        moments = entry.get("seasonal_moments") or []
        # Build seasonal ingredient per OPTIONS: months -> monthly_ingredients, holidays/seasons -> available_ingredients[0]
        seasonal_ingredients: list[str] = []
        for opt in OPTIONS:
            if opt in MONTHS:
                month = MONTHS.index(opt) + 1
                ingredient = monthly.get(f"2026-{month:02d}")
                if not ingredient:
                    failures.append(f"{code} {opt}: no monthly_ingredients for {opt}")
                    continue
                seasonal_ingredients.append(ingredient.strip().lower())
            else:
                # holiday/season: find seasonal_moments entry whose moment header matches opt (case-insensitive)
                # e.g., "Halloween — pumpkins + caramel (Halloween)" header "Halloween"
                want = opt.lower()
                found = None
                for mo in moments:
                    header = str(mo.get("moment") or "").split(" —")[0].strip().lower()
                    if header == want or header.startswith(want + " "):
                        found = mo
                        break
                if not found:
                    # fallback to available_ingredients[0] search
                    for mo in moments:
                        ing = str((mo.get("available_ingredients") or [""])[0]).lower()
                        if want in ing:
                            found = mo
                            break
                if not found:
                    failures.append(f"{code} {opt}: no seasonal_moments for {opt}")
                    continue
                ing0 = str((found.get("available_ingredients") or [""])[0]).strip().lower()
                if not ing0:
                    failures.append(f"{code} {opt}: seasonal_moments has no available_ingredients for {opt}")
                    continue
                seasonal_ingredients.append(ing0)
        # Distinctness: 26 seasons must map to 26 distinct seasonal ingredient strings per market
        if len(seasonal_ingredients) == 26 and len(set(seasonal_ingredients)) != 26:
            dup = [h for h in set(seasonal_ingredients) if seasonal_ingredients.count(h) > 1]
            failures.append(f"{code}: not 26 distinct seasonal ingredients — dups {dup[:3]}")
    assert not failures, "season gaps (full 76 distinct 26):\n" + "\n".join(failures[:50])


def test_target_markets_have_baked_preview_translations() -> None:
    text = (
        REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js"
        / "recipe-i18n-data.js"
    ).read_text(encoding="utf-8")
    book = json.loads(text.split("window.KODIAK_RECIPE_I18N = ", 1)[1].split(";\n", 1)[0])
    missing = [c for c in TARGETS if c not in book]
    assert not missing, f"markets without baked translations: {missing}"


def test_frontend_season_map_matches_contract() -> None:
    text = (
        REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js"
        / "data-core.js"
    ).read_text(encoding="utf-8")
    compact = text.replace(" ", "")
    for option, month in SEASON_MONTHS.items():
        key = option.replace(" ", "")
        forms = (
            f"'{key}':{month}",
            f'"{key}":{month}',
            f"{key}:{month}",  # bare JS keys
        )
        assert any(f in compact for f in forms), (
            f"data-core.js FRONTIER_SEASON_MONTHS missing {option}->{month}"
        )
