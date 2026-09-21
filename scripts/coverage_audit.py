#!/usr/bin/env python3
"""Four-axis coverage audit: markets / seasons / ingredients / recipes.

Reads embedded ComfyUI prompt metadata across every PNG in the box output
dir + repo pool dirs, and reports which axis values actually appear in
rendered prompts vs the full axis sets.

Usage: python scripts/coverage_audit.py [--out docs/coverage-matrix.md]
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOX_OUT = Path("/home/hs-shannon/ComfyUI/output")
POOL_DIRS = [ROOT / "input_assets" / "blog",
             ROOT / "input_assets" / "sprint2-ingredients"]

DISHES = ["pancake", "flapjack", "waffle", "muffin", "oatmeal", "brownie",
          "cookie", "granola", "quick bread", "bars", "sandwich"]


def axis_markets() -> list[str]:
    core = (ROOT / "web/kodiak-posts-for-todays-frontier/js/data-core.js").read_text()
    return sorted(set(re.findall(r'market:"(US-[A-Z\-]+)"', core)))


def axis_seasons() -> list[str]:
    months = ["January", "February", "March", "April", "May", "June", "July",
              "August", "September", "October", "November", "December"]
    seasons = ["Spring", "Summer", "Fall", "Winter"]
    holidays = ["New Year", "Valentine", "Easter", "Memorial Day",
                "Fourth of July", "Labor Day", "Halloween", "Thanksgiving",
                "Christmas", "Holiday season"]
    return months + seasons + holidays


def axis_recipes() -> list[str]:
    recs = json.loads((ROOT / "data/recipes/kodiak-recipes.json").read_text())
    return [r.get("id", r.get("name", "?")) for r in recs]


def axis_ingredients() -> list[str]:
    core = (ROOT / "web/kodiak-posts-for-todays-frontier/js/data-core.js").read_text()
    items: set[str] = set()
    for m in re.finditer(r'items:\[([^\]]*)\]', core):
        for q in re.findall(r'"([^"]+)"', m.group(1)):
            items.add(q.strip().lower())
    return sorted(items)


def prompts_in(png: Path) -> str:
    try:
        from PIL import Image
        im = Image.open(png)
        pr = im.info.get("prompt")
        if not pr:
            return ""
        d = json.loads(pr)
        out = []
        for v in d.values():
            if isinstance(v, dict) and v.get("class_type") == "CLIPTextEncode":
                out.append(str(v["inputs"].get("text", "")))
        return "\n".join(out).lower()
    except Exception:
        return ""


def main() -> None:
    files: list[Path] = []
    if BOX_OUT.is_dir():
        files += sorted(BOX_OUT.glob("*.png"))
    for d in POOL_DIRS:
        if d.is_dir():
            files += sorted(d.glob("*.png"))
    print(f"scanning {len(files)} pngs", flush=True)

    dish_hits: Counter = Counter()
    market_hits: Counter = Counter()
    season_hits: Counter = Counter()
    recipe_hits: Counter = Counter()
    ing_hits: Counter = Counter()
    with_prompts = 0

    import re as _re

    def _hit(phrase: str, p: str) -> bool:
        phrase = phrase.lower()
        cands = {phrase, phrase + "s", phrase + "es"}
        if phrase.endswith("es"):
            cands.add(phrase[:-2])
        if phrase.endswith("s"):
            cands.add(phrase[:-1])
        return any(
            _re.search(r"\b" + _re.escape(c) + r"\b", p) is not None
            for c in cands
        )

    markets = axis_markets()
    seasons = axis_seasons()
    recipes = axis_recipes()
    ingredients = axis_ingredients()
    market_names = {}
    for m in markets:
        parts = m.replace("US-", "").replace("-", " ").lower().split()
        market_names[m] = parts[-1]  # last token: wasatch, oceanside, atl ...

    for f in files:
        p = prompts_in(f)
        if not p:
            continue
        with_prompts += 1
        for dish in DISHES:
            if _hit(dish, p):
                dish_hits[dish] += 1
        for m, name in market_names.items():
            if _hit(name, p) or _hit(m.lower(), p):
                market_hits[m] += 1
        for s in seasons:
            if _hit(s.lower(), p):
                season_hits[s] += 1
        for r in recipes:
            if isinstance(r, str) and len(r) > 3 and _hit(r.lower(), p):
                recipe_hits[r] += 1
        for ing in ingredients:
            if ing and _hit(ing, p):
                ing_hits[ing] += 1

    lines = ["# coverage matrix — markets / seasons / ingredients / recipes",
             "",
             f"scanned {len(files)} pngs, {with_prompts} with embedded prompts.",
             "",
             "## dishes (what the plate shows)"]
    for dish, n in dish_hits.most_common():
        lines.append(f"- {dish}: {n}")
    lines += ["",
              f"## markets ({len(market_hits)}/{len(markets)} covered)"]
    missing = [m for m in markets if m not in market_hits]
    lines.append(f"missing {len(missing)}: " + ", ".join(missing[:40]))
    lines += ["",
              f"## seasons ({len(season_hits)}/{len(seasons)} named)"]
    lines.append("named: " + ", ".join(sorted(season_hits)))
    lines += ["",
              f"## recipes ({len(recipe_hits)}/{len(recipes)} named in prompts)"]
    lines.append("top: " + ", ".join(f"{r}({n})" for r, n in recipe_hits.most_common(10)))
    import re as _re2
    pair_src = (ROOT / "src/creative_automation/season_pairing.py").read_text()
    wired = sorted(set(_re2.findall(r'"([a-z0-9]+(?:-[a-z0-9]+)+)"', pair_src))
                    - {"season-table", "static-default"})
    lines.append(f"season-table wired: {len(wired)}/{len(recipes)} catalog recipes")
    lines.append("wired: " + ", ".join(wired))
    lines += ["",
              f"## ingredients ({len(ing_hits)}/{len(ingredients)} named)"]
    lines.append("top: " + ", ".join(f"{r}({n})" for r, n in ing_hits.most_common(15)))

    out = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else None
    text = "\n".join(lines) + "\n"
    if out:
        (ROOT / out).write_text(text)
        print(f"wrote {out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
