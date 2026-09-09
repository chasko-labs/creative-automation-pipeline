"""Regenerate data/localization/market-featured-frontiers.json from the web runtime.

Single source of truth is web/kodiak-posts-for-todays-frontier/js/data-core.js
(places[] + featuredFrontierDetail + marketFeaturedFrontier). The backend JSON
is a generated mirror so the two can never drift: every market resolves its own
nearby frontier (1:1, no shared frontiers), every frontier target self-resolves.

Ingredient months are integers 1-12 parsed from each entry's own seasons text;
entries whose seasons are unconfirmed keep months:null + a research-dispatch
note (never a guess). Entries that already carry researched months in the
committed JSON keep them verbatim.

Usage:
  python3 scripts/build-frontier-mapping.py           # rewrite the JSON
  python3 scripts/build-frontier-mapping.py --check  # exit 1 on drift
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parents[1]
DATA_CORE = (
    ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js" / "data-core.js"
)
OUT = ROOT / "data" / "localization" / "market-featured-frontiers.json"
FLAVOR_OUT = ROOT / "data" / "localization" / "local-flavor.json"

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12,
    "dec": 12,
}
SEASON_WORDS = {
    "spring": [3, 4, 5], "summer": [6, 7, 8], "fall": [9, 10, 11],
    "autumn": [9, 10, 11], "winter": [12, 1, 2],
}
RANGE_RE = re.compile(r"([A-Za-z]+)\s*[-\u2013]\s*([A-Za-z]+)")


def month_range(a: int, b: int) -> list[int]:
    out, m = [], a
    while True:
        out.append(m)
        if m == b:
            return out
        m = m % 12 + 1


def parse_months(text: str) -> list[int] | None:
    """Month ints named by a seasons string, or None when unconfirmed/vague."""
    low = text.lower()
    if "unconfirmed" in low or "research dispatch" in low:
        return None
    if "year-round" in low or "year round" in low:
        return list(range(1, 13))
    found: list[int] = []
    for m1, m2 in RANGE_RE.findall(text):
        a, b = MONTHS.get(m1.lower()), MONTHS.get(m2.lower())
        if a and b:
            for m in month_range(a, b):
                if m not in found:
                    found.append(m)
    for word, months in SEASON_WORDS.items():
        if re.search(r"\b" + word + r"\b", low):
            for m in months:
                if m not in found:
                    found.append(m)
    for name, num in MONTHS.items():
        if re.search(r"\b" + name + r"\b", low) and len(name) > 3:
            if num not in found:
                found.append(num)
    return sorted(found) if found else None


def parse_peak(text: str) -> int | None:
    m = re.search(r"\(peak\s+([A-Za-z]+)\)", text, re.IGNORECASE)
    return MONTHS.get(m.group(1).lower()) if m else None


def clause_months(item: str, seasons: str) -> list[int] | None:
    """Months from the seasons clause naming this item, else the union."""
    if "unconfirmed" in seasons.lower():
        return None
    words = [w.lower() for w in re.findall(r"[A-Za-z]+", item) if len(w) > 3]
    clauses = [c.strip() for c in seasons.split(";")]
    matched: list[int] = []
    for clause in clauses:
        cl = clause.lower()
        if any(w in cl for w in words):
            months = parse_months(clause)
            if months:
                for m in months:
                    if m not in matched:
                        matched.append(m)
    if matched:
        return sorted(matched)
    return parse_months(seasons)


def parse_detail_block(src: str) -> dict:
    body = src[src.index("const featuredFrontierDetail = {"):]
    body = body[: body.index("};") + 1]
    out: dict = {}
    for m in re.finditer(
        r'"(US-[A-Z0-9\-]+)": \{place:"((?:[^"\\]|\\.)*)", items:\[(.*?)\], '
        r'seasons:"((?:[^"\\]|\\.)*)", farmersMarket:"((?:[^"\\]|\\.)*)"\}',
        body,
    ):
        key = m.group(1)
        items = re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(3))
        out[key] = {
            "place": m.group(2),
            "items": items,
            "seasons": m.group(4),
            "farmersMarket": m.group(5),
        }
    return out


def parse_mapping(src: str) -> dict:
    body = src[src.index("const marketFeaturedFrontier = {"):]
    body = body[: body.index("};") + 1]
    return dict(re.findall(r'"(US-[A-Z0-9\- ]+)": "(US-[A-Z0-9\-]+)"', body))


def parse_places(src: str) -> dict:
    return dict(
        re.findall(r'\{market:"([^"]+)", place:"([^"]+)"', src)
    )


def short_place(place: str) -> str:
    return place.split(" \u2014 ")[0]


def build() -> dict:
    src = DATA_CORE.read_text(encoding="utf-8")
    detail = parse_detail_block(src)
    mapping = parse_mapping(src)
    places = parse_places(src)
    old = json.loads(OUT.read_text(encoding="utf-8"))
    old_markets = old.get("markets", {})

    # researched ingredients survive verbatim (months + urls we confirmed),
    # but only when the entry still points at the same frontier — a re-pointed
    # market must never keep its old frontier's ingredients.
    old_frontier = {
        key: entry.get("frontier_market")
        for key, entry in old_markets.items()
    }
    keep_ingredients: dict = {}
    for key, entry in old_markets.items():
        ings = entry.get("ingredients") or []
        if any(i.get("months") for i in ings):
            keep_ingredients[key] = ings

    markets: dict = {}
    for market, fk in mapping.items():
        d = detail[fk]
        if market in keep_ingredients and old_frontier.get(market) == fk:
            ingredients = keep_ingredients[market]
        elif fk in keep_ingredients and market == fk:
            ingredients = keep_ingredients[fk]
        else:
            ingredients = []
            for item in d["items"]:
                months = clause_months(item, d["seasons"])
                ing: dict = {"name": item, "months": months}
                peak = parse_peak(d["seasons"])
                if peak and months and peak in months:
                    ing["peak"] = peak
                if months is None:
                    ing["note"] = (
                        "seasons unconfirmed \u2014 research dispatch"
                    )
                ingredients.append(ing)
        if market == fk:
            link = "Self-frontier market; no-retail gap served by subscription."
        else:
            link = (
                f"Nearby rural counterpart to "
                f"{short_place(places.get(market, market))}; "
                f"subscription-credible."
            )
        markets[market] = {
            "market": market,
            "frontier_market": fk,
            "place": d["place"],
            "ingredients": ingredients,
            "seasons": d["seasons"],
            "farmers_market": d["farmersMarket"],
            "farmers_market_url": old_markets.get(market, {}).get(
                "farmers_market_url"
            ),
            "link_note": link,
        }

    # frontier self-entries for targets that are not markets themselves
    for fk, d in detail.items():
        if fk in markets:
            continue
        if fk in keep_ingredients:
            ingredients = keep_ingredients[fk]
        else:
            ingredients = []
            for item in d["items"]:
                months = clause_months(item, d["seasons"])
                ing = {"name": item, "months": months}
                if months is None:
                    ing["note"] = "seasons unconfirmed \u2014 research dispatch"
                ingredients.append(ing)
        markets[fk] = {
            "market": fk,
            "frontier_market": fk,
            "place": d["place"],
            "ingredients": ingredients,
            "seasons": d["seasons"],
            "farmers_market": d["farmersMarket"],
            "farmers_market_url": old_markets.get(fk, {}).get(
                "farmers_market_url"
            ),
            "link_note": "Frontier self-entry; no-retail gap served by subscription.",
        }

    shared = {}
    for code, entry in markets.items():
        if code != entry["frontier_market"]:
            shared.setdefault(entry["frontier_market"], []).append(code)
    dupes = {k: v for k, v in shared.items() if len(v) > 1}
    assert not dupes, f"shared frontiers slipped back in: {dupes}"

    # deterministic stamp: data-core.js mtime, so committed output regenerates
    # byte-identical until the source actually changes.
    stamp = datetime.fromtimestamp(
        DATA_CORE.stat().st_mtime, tz=timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "$schema": old.get("$schema"),
        "metadata": {
            "generated": stamp,
            "source": "generated from web/kodiak-posts-for-todays-frontier/js/data-core.js "
            "via scripts/build-frontier-mapping.py \u2014 do not hand-edit",
            "markets": len([k for k in markets if k in mapping]),
            "frontier_self_entries": len([k for k in markets if k not in mapping]),
            "model": "1:1 \u2014 every market resolves its own nearby frontier; "
            "no shared frontiers",
        },
        "markets": markets,
    }


def build_flavor_rows(markets: dict, places: dict) -> dict:
    """One local-flavor row per mapping market: frontier produce + source.

    Existing rows stay verbatim. New rows carry the frontier's parsed produce
    (unconfirmed items excluded — they cannot be scheduled); markets whose
    frontier seasons are entirely unconfirmed get produce:[] with the sourcing
    line, matching the loader's honest out-of-season shape.
    """
    old = json.loads(FLAVOR_OUT.read_text(encoding="utf-8"))
    rows: dict = dict(old.get("markets", {}))
    for market, entry in markets.items():
        if market in rows:
            continue  # curated rows stay verbatim
        if market not in places:
            continue  # frontier self-entries are not lookup markets
        town = short_place(entry["place"])
        produce = [
            {"name": i["name"], "months": i["months"]}
            for i in entry["ingredients"]
            if i.get("months")
        ]
        rows[market] = {
            "place": places[market],
            "source": f"{town} \u2014 {entry['farmers_market']}",
            "produce": produce,
        }
    return {
        "$schema": old.get("$schema"),
        "metadata": {
            **old.get("metadata", {}),
            "markets": len(rows),
            "model": "1:1 \u2014 every market carries its own frontier produce; "
            "unconfirmed seasons stay unscheduled (produce:[]) with the "
            "sourcing line intact",
        },
        "markets": rows,
    }


def main() -> None:
    check = "--check" in sys.argv
    doc = build()
    src = DATA_CORE.read_text(encoding="utf-8")
    flavor_doc = build_flavor_rows(doc["markets"], parse_places(src))
    rendered = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    rendered_flavor = json.dumps(flavor_doc, indent=2, ensure_ascii=False) + "\n"
    if check:
        drift = []
        if OUT.read_text(encoding="utf-8") != rendered:
            drift.append("market-featured-frontiers.json")
        if FLAVOR_OUT.read_text(encoding="utf-8") != rendered_flavor:
            drift.append("local-flavor.json")
        if drift:
            print(f"drift: {', '.join(drift)} disagree with data-core.js")
            sys.exit(1)
        print("backend flavor JSONs agree with data-core.js")
        return
    OUT.write_text(rendered, encoding="utf-8")
    print(f"wrote {OUT} ({len(doc['markets'])} keys)")
    FLAVOR_OUT.write_text(rendered_flavor, encoding="utf-8")
    print(f"wrote {FLAVOR_OUT} ({len(flavor_doc['markets'])} rows)")


if __name__ == "__main__":
    main()
