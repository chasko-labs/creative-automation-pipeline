"""Season dedupe rule: every month in a market gets a DIFFERENT featured
ingredient. Repeats make campaigns dull — running the same ingredient
every month is a content bug, not a harvest calendar.

Reads the source of truth (retailer-frontier-pairs.json monthly maps),
not the emitted JS. Currently FAILING on 61 markets (249 repeat cells
measured 2026-09-15, worst: US-W-LA, US-CA-CASTROVILLE, US-CA-PESCADERO).
Do not weaken this test — fix the data until it passes.
"""

import json
from collections import Counter
from pathlib import Path

PAIRS = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "localization"
    / "retailer-frontier-pairs.json"
)


def _monthly(market_entry):
    monthly = market_entry.get("monthly_ingredients") or {}
    if isinstance(monthly, dict):
        return {m: v for m, v in monthly.items() if v}
    out = {}
    for row in monthly:
        if isinstance(row, dict):
            m = row.get("month") or row.get("key")
            v = row.get("ingredient") or row.get("value")
            if m and v:
                out[m] = v
    return out


def test_no_repeated_ingredient_within_market_year():
    pairs = json.loads(PAIRS.read_text())["pairs"]
    offenders = {}
    for p in pairs:
        months = _monthly(p)
        if len(months) < 12:
            continue  # unseeded markets are a different (tracked) gap
        counts = Counter(months.values())
        dupes = {ing: sorted(mm for mm, v in months.items() if v == ing)
                 for ing, n in counts.items() if n > 1}
        if dupes:
            offenders[p.get("market")] = dupes
    assert not offenders, (
        "markets repeating an ingredient across months: "
        + "; ".join(f"{m}={d}" for m, d in sorted(offenders.items()))
    )
