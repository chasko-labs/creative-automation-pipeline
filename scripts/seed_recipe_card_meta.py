"""Seed recipe-card meta fields (prepTime/cookTime/yield) for the stub recipes.

Only 7 of the 36 registry recipes that cards resolve to lack time/yield fields,
covering 113 of 876 cards (73 markets x 12 months). Six of those seven are
sitemap stubs whose kodiak_page points at a real Kodiak recipe blog page; the
values below were read off those pages on 2026-09-15 from BOTH the Recipe
JSON-LD block and the visible Prep/Cook/SERVES labels (the two routes agreed;
a local model re-read the visible labels as a third check). est_cost is
intentionally untouched: no price source exists anywhere, and prices are never
fabricated.

The seventh stub, flapjacks-buttermilk (28 cards), links to a PRODUCT page
(products/buttermilk-power-cakes-flapjack-waffle-mix), not a recipe, so it has
no source for times/serves and stays null with its reason recorded here.

Method: span-scoped text surgery, not a full rewrite -- the registry file uses
a compact style (short arrays on one line) that json.dump would reformat, so
this locates each entry's exact character span via JSONDecoder.raw_decode and
inserts only the new key lines. Everything else stays byte-identical.
Idempotent: re-running changes nothing once applied.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).parents[1]
RECIPES_PATH = _ROOT / "data" / "recipes" / "kodiak-recipes.json"

# recipe id -> (prepTime, cookTime, yield, source page, verbatim page evidence).
# values use the registry's existing conventions ("N mins" strings; bare-number
# strings where the source gives bare numbers, e.g. oatmeal "5"/"1"/"1").
# winter-beef-stew cook: page JSON-LD says "2 hrs", visible label says
# "120 Minutes"; "120 mins" matches the registry's existing mins convention
# (already present as a prepTime value) and the visible label verbatim.
SOURCES: dict[str, dict[str, str]] = {
    "apple-cider-donuts": {
        "prepTime": "10 mins",
        "cookTime": "12 mins",
        "yield": "12",
        "source": "https://kodiakcakes.com/blogs/recipes/apple-cider-donuts",
        "evidence": 'LD: prepTime "10 mins", cookTime "12 mins", recipeYield "12"; '
                    'visible: "Prep Time 10 Minutes Cook Time 12 Minutes Serves 12"',
    },
    "asparagus-and-goat-cheese-frittata": {
        "prepTime": "15 mins",
        "cookTime": "40 mins",
        "yield": "4",
        "source": "https://kodiakcakes.com/blogs/recipes/asparagus-and-goat-cheese-frittata",
        "evidence": 'LD: prepTime "15 mins", cookTime "40 mins", recipeYield "4"; '
                    'visible: "Prep Time 15 Minutes Cook Time 40 Minutes Serves 4"',
    },
    "bbq-chicken-salad": {
        "prepTime": "30 mins",
        "cookTime": "60 mins",
        "yield": "6",
        "source": "https://kodiakcakes.com/blogs/recipes/bbq-chicken-salad",
        "evidence": 'LD: prepTime "30 mins", cookTime "60 mins", recipeYield "6"; '
                    'visible: "Prep Time 30 Minutes Cook Time 60 Minutes Serves 6"',
    },
    "cinnamon-coffee-cake-1": {
        "prepTime": "30 mins",
        "cookTime": "45 mins",
        "yield": "12",
        "source": "https://kodiakcakes.com/blogs/recipes/cinnamon-coffee-cake-1",
        "evidence": 'LD: prepTime "30 mins", cookTime "45 mins", recipeYield "12"; '
                    'visible: "Prep Time 30 Minutes Cook Time 45 Minutes Serves 12"',
    },
    "savory-bacon-butternut-squash-oatmeal": {
        "prepTime": "5",
        "cookTime": "1",
        "yield": "1",
        "source": "https://kodiakcakes.com/blogs/recipes/savory-bacon-butternut-squash-oatmeal",
        "evidence": 'LD: prepTime "5", cookTime "1", recipeYield "1" (single-serve '
                    'oatmeal cup, microwave ~1 min); '
                    'visible: "Prep Time 5 Minutes Cook Time 1 Minutes Serves 1"',
    },
    "winter-beef-stew": {
        "prepTime": "15 mins",
        "cookTime": "120 mins",
        "yield": "6",
        "source": "https://kodiakcakes.com/blogs/recipes/winter-beef-stew",
        "evidence": 'LD: prepTime "15 mins", cookTime "2 hrs", recipeYield "6"; '
                    'visible: "Prep Time 15 Minutes Cook Time 120 Minutes Serves 6"',
    },
}

# Stays null: product page, not a recipe page -- no times/serves source exists.
STAYS_NULL = {
    "flapjacks-buttermilk": "kodiak_page is a product page "
    "(products/buttermilk-power-cakes-flapjack-waffle-mix), not a recipe; "
    "no prep/cook/yield source exists. 28 cards keep null meta.",
}


def _entry_spans(raw: str) -> dict[str, tuple[int, int]]:
    """Map recipe id -> (start, end) char span of its top-level object."""
    dec = json.JSONDecoder()
    pos = raw.index("[") + 1
    spans: dict[str, tuple[int, int]] = {}
    while True:
        pos = raw.find("{", pos)
        if pos < 0:
            return spans
        try:
            obj, end = dec.raw_decode(raw, pos)
        except json.JSONDecodeError:
            pos += 1
            continue
        if isinstance(obj, dict) and obj.get("id"):
            spans[obj["id"]] = (pos, end)
        pos = end


def _insert_lines(span: str, spec: dict[str, str]) -> str:
    """Insert yield/prepTime/cookTime lines before the entry's closing brace.

    Field order matches the enriched entries (yield, prepTime, cookTime).
    Raises ValueError if the entry already has any of the fields (never
    overwrites a real value) or if the tail anchor is missing.
    """
    for field in ("yield", "prepTime", "cookTime"):
        if f'"{field}"' in span:
            raise ValueError(f"entry already carries {field}; refusing to overwrite")
    addition = (
        ",\n"
        f'    "yield": "{spec["yield"]}",\n'
        f'    "prepTime": "{spec["prepTime"]}",\n'
        f'    "cookTime": "{spec["cookTime"]}"'
    )
    tail = span.rstrip()
    if not tail.endswith("}"):
        raise ValueError("entry span does not end with }")
    body = tail[:-1].rstrip()  # drop the closing brace + its indent line
    addition = (
        ",\n"
        f'    "yield": "{spec["yield"]}",\n'
        f'    "prepTime": "{spec["prepTime"]}",\n'
        f'    "cookTime": "{spec["cookTime"]}"'
    )
    return body + addition + "\n  }"


def main() -> int:
    raw = RECIPES_PATH.read_text(encoding="utf-8")
    before = json.loads(raw)
    by_id = {r["id"]: r for r in before}
    spans = _entry_spans(raw)
    edits: list[tuple[int, int, str]] = []
    for rid, spec in SOURCES.items():
        if rid not in spans:
            print(f"SKIP {rid}: not in registry")
            continue
        entry = by_id[rid]
        current = {f: entry.get(f) for f in ("yield", "prepTime", "cookTime")}
        if all(current[f] == spec[f] for f in current):
            print(f"already seeded: {rid}")
            continue
        if any(v not in (None, "") for v in current.values()):
            raise SystemExit(
                f"CONFLICT {rid}: registry={current} sourced="
                f"{ {f: spec[f] for f in current} } -- refusing to overwrite"
            )
        start, end = spans[rid]
        edits.append((start, end, _insert_lines(raw[start:end], spec)))
    # apply back-to-front so earlier spans are unaffected
    for start, end, new_span in sorted(edits, reverse=True):
        raw = raw[:start] + new_span + raw[end:]
    after = json.loads(raw)  # must stay valid JSON
    assert len(after) == len(before) == 445, (len(after), len(before))
    by_id = {r["id"]: r for r in after}
    for rid, spec in SOURCES.items():
        entry = by_id[rid]
        for field in ("yield", "prepTime", "cookTime"):
            assert entry[field] == spec[field], (rid, field, entry.get(field))
    RECIPES_PATH.write_text(raw, encoding="utf-8")
    print(f"seeded {3 * len(edits)} fields across {len(edits)} recipes")
    for rid, reason in STAYS_NULL.items():
        print(f"null (recorded): {rid}: {reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
