"""Season-indexed recipe pairing table (sprint: season pairing; gh #313: 26 options).

Structured season requests pair to a curated recipe per season; month names map
to their season key; the 10 dropdown holidays pair to dedicated records
(HOLIDAY_RECIPE_PAIRINGS). A static default covers garbage/empty requests and
ingredients with no match. Pairing inputs are STRUCTURED data only (the brief's
``season`` field, the resolved month) — free brief text (``campaign_message``)
is display-only and never inspected here, so a season word leaking into
marketing copy ("winter wonderland sale") cannot hijack the pairing.
``strip_season_words`` is provided for callers that need a season-neutral
string; the pairing path itself simply never reads free text.
"""
from __future__ import annotations

import re

#: Canonical season keys. "autumn" normalizes to "fall" (see SEASON_ALIASES).
SEASONS: tuple[str, ...] = ("spring", "summer", "fall", "winter")

#: Alias -> canonical season (applied by normalize_season, before validation).
SEASON_ALIASES: dict[str, str] = {"autumn": "fall"}

#: Dropdown month name (lowercase) -> season key. The seasonal dropdown offers
#: month names; each maps mechanically to its meteorological season key, so a
#: month request reuses that season's table entry (gh #313).
MONTH_TO_SEASON: dict[str, str] = {
    "january": "winter",
    "february": "winter",
    "march": "spring",
    "april": "spring",
    "may": "spring",
    "june": "summer",
    "july": "summer",
    "august": "summer",
    "september": "fall",
    "october": "fall",
    "november": "fall",
    "december": "winter",
}

#: Canonical holiday keys (lowercase, straight apostrophe). These are the 10
#: holiday options in the seasonal dropdown (gh #313).
HOLIDAYS: tuple[str, ...] = (
    "new year",
    "valentine's day",
    "easter",
    "memorial day",
    "fourth of july",
    "labor day",
    "halloween",
    "thanksgiving",
    "christmas",
    "holiday season",
)

#: Alias -> canonical holiday (applied by normalize_holiday, before validation).
#: Covers the frontend's curly-apostrophe "Valentine\u2019s Day" and the
#: apostrophe-less spelling; anything else must match a HOLIDAYS key exactly.
HOLIDAY_ALIASES: dict[str, str] = {
    "valentine\u2019s day": "valentine's day",
    "valentine\u2018s day": "valentine's day",
    "valentines day": "valentine's day",
    # dash form used by campaign art dirs + the offline art index.
    "fourth-of-july": "fourth of july",
}

#: Whole-word season tokens treated as free-text leaks (display-only, never pairing
#: inputs). Plurals included; matching is whole-word so "summery" is left alone.
SEASON_WORDS: frozenset[str] = frozenset(
    {"spring", "springs", "summer", "summers", "fall", "falls", "autumn", "autumns", "winter", "winters"}
)

_SEASON_WORD_RE = re.compile(
    r"\b(springs?|summers?|falls?|autumns?|winters?)\b", re.IGNORECASE
)

_WS_RE = re.compile(r"\s+")

# Season -> curated recipe pairing. Each recipe id must exist in
# data/recipes/kodiak-recipes.json; the reason is surfaced in card provenance.
# Placement decision (owner scribe): this table lives HERE, next to the pairing
# logic, not in recipe_card.py (which owns picking mechanics) and not in the
# recipes catalog JSON (which owns recipe records, not request routing).
SEASON_RECIPE_PAIRINGS: dict[str, dict[str, str]] = {
    "spring": {
        "recipe_id": "single-serve-lemon-ricotta-flapjack-cup",
        "reason": "spring citrus pairing: meyer lemon is the spring-curated ingredient",
    },
    "summer": {
        "recipe_id": "cherry-pie-bars",
        "reason": "summer stone-fruit pairing: sweet cherries are the summer-curated ingredient",
    },
    "fall": {
        "recipe_id": "pumpkin-oat-muffins",
        "reason": "fall harvest pairing: pumpkin is the fall-curated ingredient",
    },
    "winter": {
        "recipe_id": "campfire-baked-apple-oats",
        "reason": "winter storage-fruit pairing: honeycrisp apples (storage) with cinnamon are the winter-curated ingredients",
    },
}

#: Holiday -> curated recipe pairing (gh #313). Each recipe id is a real record
#: in data/recipes/kodiak-recipes.json; each reason cites the record by name
#: plus the occasion judgment behind the pairing (no fabricated ingredients —
#: several of these records carry only a name/category, so reasons stay
#: name-based rather than inventing contents).
HOLIDAY_RECIPE_PAIRINGS: dict[str, dict[str, str]] = {
    "christmas": {
        "recipe_id": "christmas-tree-waffles",
        "reason": "holiday pairing: Christmas Tree Waffles is the catalog's Christmas-named waffle record",
    },
    "holiday season": {
        "recipe_id": "holiday-sugar-cookies",
        "reason": "holiday pairing: Holiday Sugar Cookies is the catalog's holiday-named cookie record",
    },
    "halloween": {
        "recipe_id": "baked-halloween-doughnuts",
        "reason": "holiday pairing: Baked Halloween Doughnuts is the catalog's Halloween-named record",
    },
    "easter": {
        "recipe_id": "easter-egg-pancakes",
        "reason": "holiday pairing: Easter Egg Pancakes is the catalog's Easter-named pancake record",
    },
    "thanksgiving": {
        "recipe_id": "pumpkin-pie",
        "reason": "holiday pairing: Pumpkin Pie is the catalog's harvest pie for the Thanksgiving table",
    },
    "fourth of july": {
        "recipe_id": "smores-brookies",
        "reason": "holiday pairing: S'mores Brookies is the catalog's campfire cookout record for the Fourth of July",
    },
    "memorial day": {
        "recipe_id": "grilled-peaches-and-granola",
        "reason": "holiday pairing: Grilled Peaches & Granola is the catalog's grill-out record for Memorial Day",
    },
    "labor day": {
        "recipe_id": "single-serve-s-mores-brownie",
        "reason": "holiday pairing: Single-Serve S'mores Brownie is the catalog's campfire record for the Labor Day cookout",
    },
    "valentine's day": {
        "recipe_id": "berry-chia-pudding",
        "reason": "holiday pairing: Berry Chia Pudding is the catalog's berry breakfast record for Valentine's Day",
    },
    "new year": {
        "recipe_id": "apple-cider-donuts",
        "reason": "holiday pairing: Apple Cider Donuts is the catalog's cider record for the New Year toast",
    },
}

#: Last-resort pairing when no season resolves or the table has no entry.
#: A year-round, fully-specified catalog record (real image + verified
#: prep/cook/yield), so the fallback card carries honest non-null meta.
DEFAULT_PAIRING: dict[str, str] = {
    "recipe_id": "apple-cinnamon-compote",
    "reason": "static default: year-round recipe used when no season or ingredient match applies",
}


def normalize_season(value: object) -> str | None:
    """Normalize a structured season request to a canonical key, or None.

    Case-insensitive; "autumn" maps to "fall"; blank/None stays None (no season
    requested). Any other value returns None rather than raising so loose brief
    dicts degrade to the default pairing instead of crashing the card.
    """
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    text = SEASON_ALIASES.get(text, text)
    return text if text in SEASONS else None


def normalize_holiday(value: object) -> str | None:
    """Normalize a holiday request to a canonical HOLIDAYS key, or None.

    Case-insensitive; surrounding whitespace collapsed; curly apostrophes and
    the apostrophe-less "valentines day" map via HOLIDAY_ALIASES. Blank/None
    stays None. Any other value returns None rather than raising so loose
    brief dicts degrade to the default pairing instead of crashing the card.
    """
    if value is None:
        return None
    text = _WS_RE.sub(" ", str(value).strip().lower())
    if not text:
        return None
    text = HOLIDAY_ALIASES.get(text, text)
    return text if text in HOLIDAYS else None


def resolve_request(value: object) -> dict:
    """Classify one dropdown-style pairing request (gh #313).

    Returns {"kind", "key", "season"} where kind is "season" (4 season keys),
    "month" (12 month names, mapped to season keys), "holiday" (10 holidays),
    or None for garbage. "key" is the canonical request key; "season" is the
    pairing label downstream surfaces — the season key for seasons and months,
    the holiday key for holidays. Never raises: garbage yields all-None.
    """
    season = normalize_season(value)
    if season is not None:
        return {"kind": "season", "key": season, "season": season}
    if value is not None:
        month_key = _WS_RE.sub(" ", str(value).strip().lower())
        if month_key in MONTH_TO_SEASON:
            return {
                "kind": "month",
                "key": month_key,
                "season": MONTH_TO_SEASON[month_key],
            }
    holiday = normalize_holiday(value)
    if holiday is not None:
        return {"kind": "holiday", "key": holiday, "season": holiday}
    return {"kind": None, "key": None, "season": None}


def pairing_season_label(value: object) -> str | None:
    """Pairing label for a dropdown-style request: the season key for seasons
    and months (months map to season keys), the holiday key for holidays, None
    for garbage. Never raises."""
    try:
        return resolve_request(value)["season"]
    except Exception:  # noqa: BLE001 — labels never break pairing
        return None


def season_for_month(ym: str | None) -> str | None:
    """Meteorological season for an ISO 'YYYY-MM' month or full 'YYYY-MM-DD'
    date, or None when unparseable.

    12/01/02 winter, 03-05 spring, 06-08 summer, 09-11 fall. Never raises: a bad
    month string yields None (caller falls back to the static default). A day
    part, when present, must be 1-31 (calendar-validity beyond that is the
    caller's business); anything else yields None.
    """
    if not ym or not isinstance(ym, str):
        return None
    parts = ym.strip().split("-")
    try:
        if len(parts) == 1:
            month = int(parts[0])
        elif len(parts) == 2:
            int(parts[0])  # year must be numeric, like the YYYY-MM contract
            month = int(parts[1])
        elif len(parts) == 3:
            int(parts[0])  # year must be numeric, like the YYYY-MM-DD contract
            month = int(parts[1])
            day = int(parts[2])
            if not 1 <= day <= 31:
                return None
        else:
            return None
    except (ValueError, IndexError):
        return None
    if month in (12, 1, 2):
        return "winter"
    if month in (3, 4, 5):
        return "spring"
    if month in (6, 7, 8):
        return "summer"
    if month in (9, 10, 11):
        return "fall"
    return None


def resolve_season(structured: object = None, month: str | None = None) -> dict:
    """Resolve the effective season: explicit structured request wins, else the month.

    Returns {"season": <key|None>, "source": "brief"|"month"|None}. Free brief text
    is intentionally NOT an input — it is display-only (see module docstring).
    """
    season = normalize_season(structured)
    if season is not None:
        return {"season": season, "source": "brief"}
    season = season_for_month(month)
    if season is not None:
        return {"season": season, "source": "month"}
    return {"season": None, "source": None}


def pairing_for_season(season: object) -> dict:
    """Return the pairing entry for a dropdown-style request, or the static
    default as last resort (gh #313: all 26 seasonal options resolve here).

    Seasons hit SEASON_RECIPE_PAIRINGS; month names map to their season key
    first (January -> winter's entry); holidays hit HOLIDAY_RECIPE_PAIRINGS.
    Return shape: {"recipe_id": ..., "reason": ..., "source":
    "season-table"|"static-default"}. Unknown/None/garbage lands on
    DEFAULT_PAIRING with source "static-default" — quiet, never raises.
    """
    req = resolve_request(season)
    kind, key = req["kind"], req["key"]
    if kind == "season" and key in SEASON_RECIPE_PAIRINGS:
        entry = SEASON_RECIPE_PAIRINGS[key]
        return {"recipe_id": entry["recipe_id"], "reason": entry["reason"], "source": "season-table"}
    if kind == "month" and req["season"] in SEASON_RECIPE_PAIRINGS:
        entry = SEASON_RECIPE_PAIRINGS[req["season"]]
        return {"recipe_id": entry["recipe_id"], "reason": entry["reason"], "source": "season-table"}
    if kind == "holiday" and key in HOLIDAY_RECIPE_PAIRINGS:
        entry = HOLIDAY_RECIPE_PAIRINGS[key]
        return {"recipe_id": entry["recipe_id"], "reason": entry["reason"], "source": "season-table"}
    return {
        "recipe_id": DEFAULT_PAIRING["recipe_id"],
        "reason": DEFAULT_PAIRING["reason"],
        "source": "static-default",
    }


def strip_season_words(text: str) -> str:
    """Remove whole-word season tokens from free text (display-string helper).

    Case-insensitive, whole-word only ("summery" survives); whitespace collapsed
    and stripped. Used where a season-neutral string is needed — the pairing path
    itself never reads free text, so this is for display callers, not routing.
    """
    return _WS_RE.sub(" ", _SEASON_WORD_RE.sub("", str(text))).strip()
