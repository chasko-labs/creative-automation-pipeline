"""Emit web/kodiak-posts-for-todays-frontier/js/recipes-frontier-pairs.js.

Single source of truth is data/localization/retailer-frontier-pairs.json.
The web file is a deterministic flattening consumed as window.KODIAK_FRONTIER_PAIRS
(frontierSeasonLine, recipe gallery). Replaces the one-off /tmp/gen_pairs.py so
the derivation is checked in and re-runnable.

Usage:
  python3 scripts/emit_frontier_pairs_js.py           # rewrite the JS
  python3 scripts/emit_frontier_pairs_js.py --check  # exit 1 on drift
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
SRC = ROOT / "data" / "localization" / "retailer-frontier-pairs.json"
OUT = (
    ROOT
    / "web"
    / "kodiak-posts-for-todays-frontier"
    / "js"
    / "recipes-frontier-pairs.js"
)

HEADER = (
    "// Frontier pairing data for the recipes brainstorm page (recipes.html).\n"
    "// Derived from data/localization/retailer-frontier-pairs.json + market-languages.json\n"
    "// \u2014 do not edit by hand, re-run scripts/emit_frontier_pairs_js.py. Offline-safe static data.\n"
)


def flatten(entry: dict) -> dict:
    metro = entry.get("metro_location") or {}
    sister = entry.get("frontier_sister") or {}
    moments = []
    for mo in entry.get("seasonal_moments") or []:
        moments.append(
            {
                "moment": mo.get("moment"),
                "status": mo.get("status"),
                "available": mo.get("available_ingredients", []),
                "seasons": mo.get("seasons", []),
                "months": mo.get("months", []),
            }
        )
    return {
        "market": entry.get("market"),
        "metro": {
            "market": metro.get("market"),
            "retailer": metro.get("retailer"),
            "name": metro.get("name"),
            "address": metro.get("address"),
        },
        "retailers": entry.get("retailers", []),
        "frontier": {
            "place": sister.get("place"),
            "market": sister.get("market"),
            "url": sister.get("farmers_market_url"),
        },
        "monthly": entry.get("monthly_ingredients", {}),
        "moments": moments,
    }


def render() -> str:
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    flat = [flatten(p) for p in doc["pairs"]]
    payload = json.dumps(flat, ensure_ascii=True)
    return HEADER + "window.KODIAK_FRONTIER_PAIRS = " + payload + ";\n"


def main() -> int:
    body = render()
    if "--check" in sys.argv[1:]:
        current = OUT.read_text(encoding="utf-8")
        if current != body:
            print("drift: recipes-frontier-pairs.js != pairs JSON; re-run emit")
            return 1
        print("pairs JS in sync")
        return 0
    OUT.write_text(body, encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
