"""CLI entry point.

Subcommands:
  generate    run the localized creative pipeline (default / legacy flag form)
  newsletter  render the Real Breakfast Club MJML + HTML newsletter
  scorecards  score generated creatives (brutal 12-card determinism)
  recipes     query the seeded Kodiak recipe DB

Legacy compatibility: an invocation whose first argument starts with "--"
(e.g. `python -m creative_automation.cli --brief briefs/kodiak.yaml ...`)
is routed to the `generate` subcommand so existing docs keep working.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .brief import load_brief
from .pipeline import run_pipeline

RECIPES_PATH = Path(__file__).parents[2] / "data" / "recipes" / "kodiak-recipes.json"


def _add_generate_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--brief", required=True, help="path to brief YAML or JSON")
    p.add_argument("--assets", default="input_assets", help="dam root folder (local mock or s3-synced)")
    p.add_argument("--out", default="output", help="output root")
    p.add_argument("--ratios", nargs="*", default=["1x1", "9x16", "16x9"], help="aspect ratios")
    p.add_argument("--lang", default=None, help="override language e.g. fr, es, ja")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="creative_automation.cli",
        description="Creative Automation Pipeline — generate localized social creatives",
    )
    sub = p.add_subparsers(dest="command")

    gen = sub.add_parser("generate", help="run the localized creative pipeline")
    _add_generate_args(gen)

    nl = sub.add_parser("newsletter", help="render the Real Breakfast Club newsletter")
    nl.add_argument("--out", default="output/newsletter", help="output dir for .mjml + .html")
    nl.add_argument("--handles", nargs="*", default=None, help="product handles (default DEFAULT_CTA_HANDLES)")
    nl.add_argument("--discount-code", default="BRKFSTCLUB", help="pill discount code")

    sc = sub.add_parser("scorecards", help="score generated creatives (brutal 12-card)")
    sc.add_argument("--out", required=True, help="output root dir containing report.json / pngs")

    rc = sub.add_parser("recipes", help="query the seeded Kodiak recipe DB")
    rc.add_argument("--category", default=None, help="filter by category")
    rc.add_argument("--query", default=None, help="substring match against name/product")
    rc.add_argument("--limit", type=int, default=20, help="max recipes to show")
    rc.add_argument("--json", action="store_true", help="emit machine-readable JSON")

    return p


def cmd_generate(args: argparse.Namespace) -> int:
    brief = load_brief(args.brief)
    dam_root = Path(args.assets)
    out_root = Path(args.out)

    print(f"[brief] {brief.campaign_name} | {brief.brand} | region={brief.region} | products={len(brief.products)}")
    print(f"[dam] root={dam_root} exists={dam_root.exists()}")
    print(f"[out] {out_root} ratios={args.ratios} lang={args.lang or brief.language}")

    report = run_pipeline(brief, dam_root, out_root, ratios=args.ratios, lang=args.lang)

    print(f"[done] creatives={report['summary']['total_creatives']} pass={report['summary']['compliance_pass_rate']} elapsed={report['summary']['elapsed_sec']}s")
    print(f"[report] {out_root / 'report.json'}")
    print(f"[preview] {out_root / 'preview.html'} — open in browser")
    return 0


def cmd_newsletter(args: argparse.Namespace) -> int:
    from .newsletter import get_products_by_handles, save_newsletter

    out_dir = Path(args.out)
    products = get_products_by_handles(args.handles) if args.handles else None
    mjml_path = save_newsletter(out_dir, products=products, discount_code=args.discount_code)
    html_path = mjml_path.with_suffix(".html")
    print(f"[newsletter] mjml={mjml_path}")
    print(f"[newsletter] html={html_path}")
    return 0


def cmd_scorecards(args: argparse.Namespace) -> int:
    from .scorecards import score_batch

    out_root = Path(args.out)
    result = score_batch(out_root)
    dest = out_root / "scorecards.json"
    dest.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"[scorecards] images_scored={result['images_scored']}")
    print(f"[scorecards] overall_brutal_pass={result['overall_brutal_pass']}")
    for card in result["brutal_cards"]:
        print(f"[scorecards] {card['id']}: {card['pass_rate']} ({card['pct']}%) pass={card['pass']}")
    print(f"[scorecards] wrote {dest}")
    return 0


def _load_recipes() -> list[dict]:
    if not RECIPES_PATH.exists():
        return []
    return json.loads(RECIPES_PATH.read_text(encoding="utf-8"))


def cmd_recipes(args: argparse.Namespace) -> int:
    recipes = _load_recipes()
    matches = recipes
    if args.category:
        cat = args.category.lower()
        matches = [r for r in matches if str(r.get("category", "")).lower() == cat]
    if args.query:
        q = args.query.lower()
        matches = [
            r for r in matches
            if q in str(r.get("name", "")).lower() or q in str(r.get("product", "")).lower()
        ]
    limited = matches[: args.limit]

    if args.json:
        print(json.dumps(limited, indent=2))
        return 0

    print(f"[recipes] {len(matches)} match (showing {len(limited)}) of {len(recipes)} total")
    for r in limited:
        print(f"  {r.get('id', '')} | {r.get('name', '')} | {r.get('category', '')} | {r.get('kodiak_page', '')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # legacy compatibility: bare flag form routes to `generate`
    if argv and argv[0].startswith("--"):
        argv = ["generate", *argv]

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    dispatch = {
        "generate": cmd_generate,
        "newsletter": cmd_newsletter,
        "scorecards": cmd_scorecards,
        "recipes": cmd_recipes,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
