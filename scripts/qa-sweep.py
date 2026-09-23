#!/usr/bin/env python3
"""Product-owner QA sweep harness: markets x seasons matrix.

For every market in retailer-frontier-pairs.json and every one of the 26
seasonal dropdown options (4 seasons + 12 month names + 10 holidays), resolve
the season pairing and join it to the recipe catalog. Records per cell:
pairing source, recipe id, dish name, whether the dish is still a stub
(no ingredients), and the pairing reason.

Also probes edge cases: unknown market, garbage/None/empty season requests,
case variants, and ISO month inputs.

Usage:
  uv run python scripts/qa-sweep.py --out output/qa-shots/qa-matrix.json
  uv run python scripts/qa-sweep.py --markets US-NE-NYC,US-SE-ATL --out /tmp/x.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from creative_automation import season_pairing as sp
from creative_automation.recipe_card import frontier_market_for

ROOT = Path(__file__).resolve().parent.parent

MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
SEASON_OPTIONS: tuple[str, ...] = tuple(sp.SEASONS) + MONTHS + tuple(sp.HOLIDAYS)

EDGE_SEASONS = (
    None, "", "  ", "garbage-season", "SUMMER", "  Fall ", "AUTUMN",
    "new-year", "NEW-YEAR", "valentines day", "2026-10", "2026-13",
    "october ", 123, ["summer"],
)


def _catalog_by_id() -> dict:
    recs = json.loads((ROOT / "data" / "recipes" / "kodiak-recipes.json").read_text())
    return {str(r.get("id")): r for r in recs if isinstance(r, dict)}


def _pairs() -> list[dict]:
    return json.loads(
        (ROOT / "data" / "localization" / "retailer-frontier-pairs.json").read_text()
    )["pairs"]


def sweep(markets: list[str] | None) -> dict:
    catalog = _catalog_by_id()
    pairs = _pairs()
    if markets:
        want = set(markets)
        pairs = [p for p in pairs if p["market"] in want]
    cells: list[dict] = []
    for p in pairs:
        market = p["market"]
        resolves = frontier_market_for(market) is not None
        for season in SEASON_OPTIONS:
            try:
                pairing = sp.pairing_for_season(season)
                err = None
            except Exception as exc:  # failure point, not a crash
                pairing, err = {}, f"{type(exc).__name__}: {exc}"
            rid = (pairing or {}).get("recipe_id")
            rec = catalog.get(str(rid)) if rid else None
            cells.append({
                "market": market,
                "market_resolves": resolves,
                "season": season,
                "source": (pairing or {}).get("source"),
                "recipe_id": rid,
                "dish": (rec or {}).get("dish") or (rec or {}).get("name"),
                "stub": bool(rec is None or not rec.get("ingredients")),
                "reason": (pairing or {}).get("reason"),
                "error": err,
            })
    edges: list[dict] = []
    for season in EDGE_SEASONS:
        try:
            pairing = sp.pairing_for_season(season)
            edges.append({"input": repr(season), "source": pairing.get("source"),
                          "recipe_id": pairing.get("recipe_id"), "error": None})
        except Exception as exc:
            edges.append({"input": repr(season), "source": None,
                          "recipe_id": None, "error": f"{type(exc).__name__}: {exc}"})
    for market in ("US-XX-NOWHERE", "", None):
        try:
            edges.append({"input": f"market={market!r}",
                          "resolves": frontier_market_for(market) is not None,
                          "error": None})
        except Exception as exc:
            edges.append({"input": f"market={market!r}", "resolves": False,
                          "error": f"{type(exc).__name__}: {exc}"})
    return {
        "season_options": list(SEASON_OPTIONS),
        "market_count": len(pairs),
        "cell_count": len(cells),
        "cells": cells,
        "edge_cases": edges,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--markets", default="")
    args = ap.parse_args()
    markets = [m for m in args.markets.split(",") if m] or None
    result = sweep(markets)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"markets={result['market_count']} cells={result['cell_count']} -> {out}")


if __name__ == "__main__":
    main()
