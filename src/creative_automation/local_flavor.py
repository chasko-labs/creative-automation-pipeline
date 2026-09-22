"""Locale -> season -> local flavor lookup for the 'Local flavor' island.

Month-aware canonical source for the produce/source string that the frontend
currently hardcodes in a JS flavorMap. The DATA layer lives here + in
data/localization/local-flavor.json so the pipeline and the UI read one table
instead of drifting copies. The UI half (month-picker wiring) consumes the same
JSON via local_flavor_for(market_code, month).

Month convention: integers 1-12 (January=1). Windows are inclusive and may wrap
the year boundary (start 11, end 2 spans Nov-Feb); year-round entries carry all
twelve months. Unknown markets fall through to the seeded _default row rather
than raising, so a new frontier locale still renders something on-brand.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from functools import lru_cache
from pathlib import Path

# repo-root anchored so this resolves from any cwd (tests run from repo root)
FLAVOR_PATH = (
    Path(__file__).parents[2] / "data" / "localization" / "local-flavor.json"
)

DEFAULT_KEY = "_default"


@dataclass(frozen=True)
class ProduceItem:
    """One local ingredient with the inclusive month window it is in season."""

    name: str
    months: tuple[int, ...]
    peak: int | None = None

    def in_season(self, month: int) -> bool:
        return month in self.months


@dataclass(frozen=True)
class MarketFlavor:
    """One market's sourcing string plus its month-aware produce list."""

    market: str
    place: str
    source: str
    produce: tuple[ProduceItem, ...] = field(default_factory=tuple)

    def in_season(self, month: int) -> list[ProduceItem]:
        return [p for p in self.produce if p.in_season(month)]

    def all_months(self) -> list[int]:
        """Sorted union of every month any produce item covers."""
        return sorted({m for p in self.produce for m in p.months})


@lru_cache(maxsize=1)
def _load_raw(path: str | None = None) -> dict:
    p = Path(path) if path else FLAVOR_PATH
    with p.open(encoding="utf-8") as fh:
        return json.load(fh)


def _current_month() -> int:
    return datetime.now(UTC).month


def _coerce_market(key: str, entry: dict) -> MarketFlavor:
    items: list[ProduceItem] = []
    for raw in entry.get("produce", []):
        items.append(
            ProduceItem(
                name=raw["name"],
                months=tuple(int(m) for m in raw.get("months", [])),
                peak=raw.get("peak"),
            )
        )
    return MarketFlavor(
        market=key,
        place=entry.get("place", ""),
        source=entry.get("source", ""),
        produce=tuple(items),
    )


@lru_cache(maxsize=4)
def load_flavors(path: str | None = None) -> dict[str, MarketFlavor]:
    """Load all market flavor rows keyed by market code (includes _default)."""
    raw = _load_raw(path)
    out: dict[str, MarketFlavor] = {}
    for key, entry in raw.get("markets", {}).items():
        out[key] = _coerce_market(key, entry)
    return out


def resolve_flavor(market_code: str, path: str | None = None) -> MarketFlavor:
    """Resolve a market to its MarketFlavor, falling back to _default when unseeded."""
    flavors = load_flavors(path)
    return flavors.get(market_code) or flavors[DEFAULT_KEY]


def local_flavor_for(
    market_code: str, month: int | None = None, path: str | None = None
) -> dict:
    """Return the in-season local flavor for a market + month.

    Shape (the contract the frontend month-picker consumes):
        {
          "market": "US-SW-LASCRUCES",   # resolved market ("_default" if fell back)
          "matched": True,                # False when market was unknown
          "month": 9,                     # the month queried (1-12)
          "place": "...",
          "source": "...",                # where to get it
          "produce": ["Hatch green chile"],  # in-season names for this month
          "months": [8, 9]                # union of months any produce covers
        }

    When nothing is in season this month, produce is [] but source/place still
    resolve so the caller can render the sourcing line without a fabricated item.

    Layer contract: this is the SOURCING line (where to buy it), not the
    recipe ingredient — that comes from retailer-frontier-pairs via
    locales.resolve_this_month(). The two may name different produce for
    the same month by design; neither overrides the other.
    """
    m = month if month is not None else _current_month()
    if not 1 <= int(m) <= 12:
        raise ValueError(f"month must be 1-12, got {month!r}")
    m = int(m)
    flavors = load_flavors(path)
    matched = market_code in flavors and market_code != DEFAULT_KEY
    flavor = flavors.get(market_code) or flavors[DEFAULT_KEY]
    return {
        "market": flavor.market,
        "matched": matched,
        "month": m,
        "place": flavor.place,
        "source": flavor.source,
        "produce": [p.name for p in flavor.in_season(m)],
        "months": flavor.all_months(),
    }
