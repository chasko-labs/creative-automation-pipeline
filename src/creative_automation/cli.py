"""CLI entry point."""
from __future__ import annotations

import argparse
from pathlib import Path

from .brief import load_brief
from .pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Creative Automation Pipeline — generate localized social creatives")
    p.add_argument("--brief", required=True, help="path to brief YAML or JSON")
    p.add_argument("--assets", default="input_assets", help="dam root folder (local mock or s3-synced)")
    p.add_argument("--out", default="output", help="output root")
    p.add_argument("--ratios", nargs="*", default=["1x1", "9x16", "16x9"], help="aspect ratios")
    p.add_argument("--lang", default=None, help="override language e.g. fr, es, ja")
    return p


def main():
    parser = build_parser()
    args = parser.parse_args()

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


if __name__ == "__main__":
    main()
