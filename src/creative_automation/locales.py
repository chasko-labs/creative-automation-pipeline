"""Retailer-frontier pairing loader.

Resolves a market key to its confirmed retailer-frontier pair and the local
ingredient in season for a given month. Data source is a static JSON registry
(data/localization/retailer-frontier-pairs.json) so there is no network boundary
here \u2014 pure file read + in-memory lookup. The month->ingredient map is authored
per pair; months not yet filled resolve to None so callers can fall back rather
than emit a fabricated ingredient.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

from ._datapaths import data_path

# resolved at runtime so it works in a repo checkout AND the Lambda image (see
# _datapaths.data_root — parents[2]/data does not exist under site-packages).
PAIRS_PATH = data_path("localization", "retailer-frontier-pairs.json")


@dataclass(frozen=True)
class FrontierPair:
    """One metro location paired with its frontier sister + monthly ingredients."""

    market: str
    metro_location: dict
    frontier_sister: dict
    retailers: list[str]
    monthly_ingredients: dict[str, str | None]
    research_todo: bool

    def ingredient_for(self, ym: str) -> str | None:
        """Return the in-season local ingredient for an ISO month 'YYYY-MM', or None."""
        return self.monthly_ingredients.get(ym)


@lru_cache(maxsize=1)
def _load_raw(path: str | None = None) -> dict:
    p = Path(path) if path else PAIRS_PATH
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def _current_ym() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


@lru_cache(maxsize=4)
def load_pairs(path: str | None = None) -> dict[str, FrontierPair]:
    """Load all pairs keyed by market. Also indexes legacy_market when present."""
    raw = _load_raw(path)
    out: dict[str, FrontierPair] = {}
    for entry in raw.get("pairs", []):
        pair = FrontierPair(
            market=entry["market"],
            metro_location=entry["metro_location"],
            frontier_sister=entry["frontier_sister"],
            retailers=list(entry.get("retailers", [])),
            monthly_ingredients=dict(entry.get("monthly_ingredients", {})),
            research_todo=bool(entry.get("research_todo", False)),
        )
        out[pair.market] = pair
        legacy = entry.get("legacy_market")
        if legacy and legacy not in out:
            out[legacy] = pair
    return out


def resolve_pair(market: str, path: str | None = None) -> FrontierPair | None:
    """Resolve a market key to its FrontierPair, or None if no pair is seeded."""
    return load_pairs(path).get(market)


def resolve_this_month(
    market: str, ym: str | None = None, path: str | None = None
) -> dict | None:
    """Resolve a market to {pair, month, ingredient} for the given (or current) month.

    Returns None when the market has no seeded pair. When the month has no
    ingredient filled yet, ingredient is None (caller decides fallback).
    """
    pair = resolve_pair(market, path)
    if pair is None:
        return None
    month = ym or _current_ym()
    return {
        "market": pair.market,
        "month": month,
        "ingredient": pair.ingredient_for(month),
        "frontier_sister": pair.frontier_sister.get("place"),
        "farmers_market_url": pair.frontier_sister.get("farmers_market_url"),
        "retailers": pair.retailers,
        "pair": pair,
    }



# --------------------------------------------------------------------------- #
# market target-language resolution (server-side localization)
#
# market-languages.json lists the top-2 NON-English languages per market (ACS 2022,
# each entry carrying lang_code/translate_code/pct_home). English is implicit and
# always shipped. The delivery goal is the top-3 most-spoken languages per market:
# English + that market's top-2. When the market is unknown or lists fewer than 2
# non-English languages, the default set [en, es, pt] fills to three. English is
# always first and never dropped.
# --------------------------------------------------------------------------- #

MARKET_LANGUAGES_PATH = data_path("localization", "market-languages.json")

# The always-on default when a market is unknown or under-specified. English first,
# then Spanish + Portuguese per Bryan's EN/ES/PT default.
DEFAULT_TARGET_LANGUAGES: list[dict] = [
    {"lang_code": "en", "translate_code": "en", "lang_name": "English"},
    {"lang_code": "es", "translate_code": "es", "lang_name": "Spanish"},
    {"lang_code": "pt", "translate_code": "pt", "lang_name": "Portuguese"},
]


@lru_cache(maxsize=1)
def _load_market_languages(path: str | None = None) -> dict[str, dict]:
    """Load market-languages.json keyed by market code, or {} if the file is absent."""
    p = Path(path) if path else MARKET_LANGUAGES_PATH
    if not p.exists():
        return {}
    with p.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    return {m["market"]: m for m in raw.get("markets", []) if m.get("market")}


def resolve_target_languages(
    market: str | None, path: str | None = None
) -> list[dict]:
    """Resolve a market to its top-3 target languages: English + market top-2.

    Always returns exactly 3 entries with English first. Each entry is
    {lang_code, translate_code, lang_name}. Unknown market or a market listing fewer
    than 2 non-English languages falls back to the [en, es, pt] default to fill to
    three (English is never dropped, duplicates are de-duped by lang_code).
    """
    english = {"lang_code": "en", "translate_code": "en", "lang_name": "English"}
    out: list[dict] = [english]
    seen = {"en"}

    entry = _load_market_languages(path).get(market or "")
    if entry:
        for lang in entry.get("top_languages", []):
            code = lang.get("lang_code")
            if not code or code in seen:
                continue
            out.append(
                {
                    "lang_code": code,
                    "translate_code": lang.get("translate_code", code),
                    "lang_name": lang.get("lang_name", code),
                }
            )
            seen.add(code)
            if len(out) == 3:
                break

    # fill to three from the EN/ES/PT default when the market gave us fewer than 2
    # non-English languages (or was unknown entirely).
    for lang in DEFAULT_TARGET_LANGUAGES:
        if len(out) == 3:
            break
        if lang["lang_code"] in seen:
            continue
        out.append(dict(lang))
        seen.add(lang["lang_code"])

    return out[:3]


# --------------------------------------------------------------------------- #
# dialect knowledge bases
#
# Per-region+language term tables live at data/localization/dialect/*.jsonl.
# One JSONL row per term: {region, lang_code, term_local, term_standard,
# usage_note, category, confidence}. category=="trap" rows are the highest-value
# regional inversions (es-SW "hotcakes" vs es-FL-Cuban "panqueque"; fr-VT
# "dejeuner"==breakfast). Files are UTF-8 with diacritics intact — a tone mark or
# enye is meaning, not cosmetic, so this loader never normalizes or strips them.
# --------------------------------------------------------------------------- #

DIALECT_DIR = data_path("localization", "dialect")

# (lang_code, region) -> filename. region kept loose so callers can pass either
# the exact region tag or a looser market hint; lookup falls back on lang+substr.
_DIALECT_FILES: dict[tuple[str, str], str] = {
    ("es", "US-SW"): "dialect-es-sw.jsonl",
    ("es", "US-FL-CUBAN"): "dialect-es-fl-cuban.jsonl",
    ("ht", "US-FL"): "dialect-ht-fl.jsonl",
    ("vi", "US-SEATTLE"): "dialect-vi-seattle.jsonl",
    ("fr", "US-VT"): "dialect-fr-vt.jsonl",
    ("pt", "US-PARKCITY"): "dialect-pt-parkcity.jsonl",
}


@dataclass(frozen=True)
class DialectTerm:
    """One regional term mapping (local usage vs the standard-language form)."""

    region: str
    lang_code: str
    term_local: str
    term_standard: str
    usage_note: str
    category: str  # food | breakfast | cooking | trap | register
    confidence: str  # high | medium | low

    @property
    def is_trap(self) -> bool:
        return self.category == "trap"


def _dialect_filename(region: str, lang_code: str) -> str | None:
    """Resolve (region, lang) to a dialect filename, tolerant of loose region hints."""
    key = (lang_code, region)
    if key in _DIALECT_FILES:
        return _DIALECT_FILES[key]
    # loose match: same lang, and the registered region is a prefix/substring of
    # the requested one (or vice versa) — lets a broad "US-FL" hint still miss the
    # Cuban file unless explicitly asked, while "US-FL-CUBAN" resolves exactly.
    r = region.upper()
    for (lang, reg), fname in _DIALECT_FILES.items():
        if lang != lang_code:
            continue
        if reg == r or reg in r or r in reg:
            return fname
    return None


@lru_cache(maxsize=16)
def load_dialect(region: str, lang_code: str) -> list[DialectTerm]:
    """Load the dialect term list for a region+language, or [] if none is seeded.

    Reads UTF-8 with diacritics preserved exactly — no normalization. Unknown
    (region, lang) returns an empty list rather than raising so callers can fall
    back to the standard language.
    """
    fname = _dialect_filename(region, lang_code)
    if not fname:
        return []
    path = DIALECT_DIR / fname
    if not path.exists():
        return []
    out: list[DialectTerm] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            out.append(
                DialectTerm(
                    region=row["region"],
                    lang_code=row["lang_code"],
                    term_local=row["term_local"],
                    term_standard=row["term_standard"],
                    usage_note=row.get("usage_note", ""),
                    category=row.get("category", ""),
                    confidence=row.get("confidence", ""),
                )
            )
    return out


def dialect_traps(region: str, lang_code: str) -> list[DialectTerm]:
    """Just the category=='trap' rows — the regional inversions worth guarding."""
    return [t for t in load_dialect(region, lang_code) if t.is_trap]


def resolve_dialect_terms(text: str, region: str, lang_code: str) -> list[dict]:
    """Flag standard-language terms in `text` that have a regional variant.

    Scans for each term's standard form (word-ish, case-insensitive) and returns
    a suggestion to swap it for the local form. Trap rows sort first because they
    are the highest-value corrections. Match is on term_standard so an engineer
    can lint English/standard copy before it ships to a regional market; when the
    local and standard forms are identical the row is skipped (nothing to swap).
    """
    terms = load_dialect(region, lang_code)
    if not terms:
        return []
    haystack = text.casefold()
    hits: list[dict] = []
    for t in terms:
        std = t.term_standard.casefold()
        if not std or t.term_standard == t.term_local:
            continue
        if std in haystack:
            hits.append(
                {
                    "matched_standard": t.term_standard,
                    "suggest_local": t.term_local,
                    "category": t.category,
                    "confidence": t.confidence,
                    "usage_note": t.usage_note,
                    "is_trap": t.is_trap,
                }
            )
    hits.sort(key=lambda h: (not h["is_trap"], h["matched_standard"]))
    return hits
