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

# repo-root anchored so this works from any cwd (tests run from repo root)
PAIRS_PATH = (
    Path(__file__).parents[2] / "data" / "localization" / "retailer-frontier-pairs.json"
)


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
