"""Season-indexed recipe pairing table (sprint: season pairing).

Structured season requests pair to a curated recipe per season; a static default
covers months with no season and ingredients with no match. Pairing inputs are
STRUCTURED data only (the brief's ``season`` field, the resolved month) — free
brief text (``campaign_message``) is display-only and never inspected here, so a
season word leaking into marketing copy ("winter wonderland sale") cannot hijack
the pairing. ``strip_season_words`` is provided for callers that need a
season-neutral string; the pairing path itself simply never reads free text.
"""
from __future__ import annotations

import re

#: Canonical season keys. "autumn" normalizes to "fall" (see SEASON_ALIASES).
SEASONS: tuple[str, ...] = ("spring", "summer", "fall", "winter")

#: Alias -> canonical season (applied by normalize_season, before validation).
SEASON_ALIASES: dict[str, str] = {"autumn": "fall"}

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
        "recipe_id": "pear-spice-muffins-draft",
        "reason": "winter storage-fruit pairing: pears (storage) are the winter-curated ingredient",
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
    """Return the pairing entry for a season, or the static default as last resort.

    Return shape: {"recipe_id": ..., "reason": ..., "source": "season-table"|"static-default"}.
    Unknown/None seasons land on DEFAULT_PAIRING with source "static-default".
    """
    key = normalize_season(season)
    if key is not None and key in SEASON_RECIPE_PAIRINGS:
        entry = SEASON_RECIPE_PAIRINGS[key]
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
