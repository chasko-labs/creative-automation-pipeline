#!/usr/bin/env python3
"""Regenerate the full market x season grid inside pipeline.html.

Reads data/localization/local-flavor.json (months are the source of truth)
and rewrites the rows between the GRID-GENERATED markers in
web/kodiak-posts-for-todays-frontier/pipeline.html. The page stays static
so it renders over file:// with no fetch.

Cell rule: a season lists every produce whose months overlap that season,
annotated with the overlapping month range, e.g. "Hatch green chile
(Aug-Sep)". A season with nothing in season renders an em-dash.
Seasons are the reading aid: spring Mar-May, summer Jun-Aug, fall Sep-Nov,
winter Dec-Feb.

Usage: uv run python scripts/build-pipeline-page.py
"""

import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FLAVOR = ROOT / "data" / "localization" / "local-flavor.json"
PAGE = ROOT / "web" / "kodiak-posts-for-todays-frontier" / "pipeline.html"

SEASONS = [
    ("Spring", [3, 4, 5]),
    ("Summer", [6, 7, 8]),
    ("Fall", [9, 10, 11]),
    ("Winter", [12, 1, 2]),
]
MONTH_ABBR = {
    1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun",
    7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec",
}

START = "<!-- GRID-GENERATED-START -->"
END = "<!-- GRID-GENERATED-END -->"


def month_range(months: list[int]) -> str:
    if len(months) == 1:
        return MONTH_ABBR[months[0]]
    return f"{MONTH_ABBR[months[0]]}\u2013{MONTH_ABBR[months[-1]]}"


def cell(produce: list[dict], season_months: list[int]) -> str:
    items = []
    for p in produce:
        overlap = [m for m in season_months if m in set(p.get("months", []))]
        if overlap:
            items.append(f"{p['name']} ({month_range(overlap)})")
    if not items:
        return "&mdash;"
    return html.escape(", ".join(items))


def build_rows(markets: dict) -> str:
    lines = []
    codes = [c for c in markets if not c.startswith("_")]  # skip template fallbacks
    for code in sorted(codes, key=lambda c: markets[c].get("place", c).lower()):
        m = markets[code]
        place = html.escape(m.get("place", code))
        tds = "".join(f"<td>{cell(m.get('produce', []), sm)}</td>" for _, sm in SEASONS)
        lines.append(
            f"<tr><td><b>{place}</b><br>"
            f"<span style=\"color:#6B5A53;font-size:11.5px\">{html.escape(code)}</span></td>{tds}</tr>"
        )
    return "\n".join(lines)


def main() -> None:
    flavor = json.loads(FLAVOR.read_text(encoding="utf-8"))
    markets = flavor["markets"]
    rows = build_rows(markets)
    header = (
        "<tr><th scope=\"col\">Market</th>"
        + "".join(f"<th scope=\"col\">{name}</th>" for name, _ in SEASONS)
        + "</tr>"
    )
    block = f"{START}\n{header}\n{rows}\n{END}"
    text = PAGE.read_text(encoding="utf-8")
    pattern = re.compile(re.escape(START) + r".*?" + re.escape(END), re.DOTALL)
    if not pattern.search(text):
        print(f"markers missing in {PAGE}", file=sys.stderr)
        raise SystemExit(1)
    PAGE.write_text(pattern.sub(block, text), encoding="utf-8")
    n_rows = block.count("<tr><td><b>")
    print(f"{n_rows} market rows from {len(markets)} flavor entries -> {PAGE}")


if __name__ == "__main__":
    main()
