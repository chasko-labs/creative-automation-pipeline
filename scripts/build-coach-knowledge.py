"""Build coach/knowledge.md from committed repo sources (deterministic).

Reads data/products/theme-asset-map.json (theme briefs) plus the retailer copy
framings, appends coach/knowledge-static.md (how-to-steer recipes). A test
asserts the committed knowledge.md regenerates byte-identical, so grounding can
never drift from the shipped themes.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).parents[1]
MAP = ROOT / "data" / "products" / "theme-asset-map.json"
STATIC = ROOT / "coach" / "knowledge-static.md"
OUT = ROOT / "coach" / "knowledge.md"

# Retailer copy framings, mirrored from _THEME_COPY_HINT in generate.py.
COPY_HINTS = {
    "localized-costco": "bulk Family Size value — warehouse-club aisle, stock-up trip",
    "localized-publix": "neighborhood warmth — southern family table",
    "localized-target": "everyday-family aisle — one-trip basket, modern everyday value",
    "kodiak-subscription": "subscription cadence — front-door delivery, pantry always stocked",
}


def build() -> str:
    data = json.loads(MAP.read_text(encoding="utf-8"))["map"]
    lines = ["# Kodiak campaign creator — coach knowledge", ""]
    lines.append("## Themes (chip slug: brief)")
    for slug in sorted(data):
        brief = re.sub(r"\s+", " ", str(data[slug].get("brief", ""))).strip()
        lines.append(f"- {slug}: {brief}")
    lines += ["", "## Retailer copy framings (ship in the copy sidecar)"]
    for slug in sorted(COPY_HINTS):
        lines.append(f"- {slug}: {COPY_HINTS[slug]}")
    lines += ["", STATIC.read_text(encoding="utf-8").rstrip(), ""]
    return "\n".join(lines)


def main() -> None:
    OUT.write_text(build(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
