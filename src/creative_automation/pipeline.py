"""Orchestrator — brief -> dam -> generate -> compose -> compliance -> report."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

from .brief import CampaignBrief
from .compose import RATIOS, compose_creative
from .compliance import run_all_checks
from .dam import find_brand_logo, find_hero_asset
from .generate import generate_hero
from .localize import localize_message


def run_pipeline(
    brief: CampaignBrief,
    dam_root: Path,
    out_root: Path,
    ratios: List[str] | None = None,
    lang: str | None = None,
) -> Dict:
    t0 = time.time()
    ratios = ratios or ["1x1", "9x16", "16x9"]
    # normalize ratio keys
    ratios = [r.strip() for r in ratios]
    lang = lang or brief.language
    out_root.mkdir(parents=True, exist_ok=True)

    brand_logo = find_brand_logo(dam_root)

    report: Dict = {
        "campaign": brief.campaign_name,
        "brand": brief.brand,
        "region": brief.region,
        "audience": brief.target_audience,
        "language": lang,
        "ratios": ratios,
        "products": [],
        "artifacts": [],
        "compliance_summary": {},
    }

    total_creatives = 0
    overall_pass = 0

    for idx, product in enumerate(brief.products):
        hero = find_hero_asset(product.id, dam_root, product.hero_asset)
        hero_source = "dam"
        # stage hero to a working path if reused, or generate
        work_hero = out_root / "_work" / f"{product.id}_hero.png"
        work_hero.parent.mkdir(parents=True, exist_ok=True)

        if hero and hero.exists():
            # copy to work
            import shutil

            shutil.copy2(hero, work_hero)
        else:
            # generate
            _, hero_source = generate_hero(
                product_id=product.id,
                product_name=product.name,
                brief_msg=brief.campaign_message,
                region=brief.region,
                audience=brief.target_audience,
                out_path=work_hero,
                idx=idx,
            )
            hero = work_hero

        # localize message per product/region
        msg, loc_source = localize_message(brief.campaign_message, lang, brief.region, brief.localized_messages)

        product_entry = {
            "id": product.id,
            "name": product.name,
            "hero_asset": str(hero),
            "hero_source": hero_source,
            "localized_message": msg,
            "localization_source": loc_source,
            "creatives": [],
        }

        for ratio in ratios:
            # canonical folder name
            folder_ratio = ratio.replace(":", "x") if ":" in ratio else ratio
            # ensure canonical 3 forms
            if folder_ratio in ("1:1", "1x1"):
                folder_ratio = "1x1"
            elif folder_ratio in ("9:16", "9x16"):
                folder_ratio = "9x16"
            elif folder_ratio in ("16:9", "16x9"):
                folder_ratio = "16x9"

            out_path = out_root / product.id / folder_ratio / f"{product.id}_{folder_ratio}.png"
            compose_creative(
                hero_path=work_hero,
                out_path=out_path,
                message=msg,
                ratio_key=ratio,
                brand_logo=brand_logo,
                brand_colors=brief.brand_colors,
            )

            checks = run_all_checks(out_path, msg, brief.brand_colors, brand_logo is not None)
            product_entry["creatives"].append(
                {
                    "ratio": folder_ratio,
                    "path": str(out_path.relative_to(out_root)),
                    "absolute": str(out_path),
                    "compliance": checks,
                }
            )
            report["artifacts"].append(
                {
                    "product": product.id,
                    "ratio": folder_ratio,
                    "path": str(out_path.relative_to(out_root)),
                    "message": msg,
                    "hero_source": hero_source,
                    "compliance_passed": checks["overall_passed"],
                }
            )
            total_creatives += 1
            if checks["overall_passed"]:
                overall_pass += 1

        report["products"].append(product_entry)

    report["summary"] = {
        "total_creatives": total_creatives,
        "compliance_pass_rate": f"{overall_pass}/{total_creatives}",
        "elapsed_sec": round(time.time() - t0, 2),
    }

    # write report.json
    (out_root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    # write report.jsonl for logging/analytics
    with open(out_root / "report.jsonl", "w", encoding="utf-8") as f:
        for a in report["artifacts"]:
            f.write(json.dumps(a) + "\n")

    # preview html
    _write_preview(report, out_root)

    return report


def _write_preview(report: Dict, out_root: Path):
    html = """<!doctype html>
<html><head><meta charset="utf-8"><title>Creative Automation — Preview</title>
<style>
body{font-family:system-ui,-apple-system,sans-serif;margin:0;background:#0B1220;color:#E6EDF3}
header{padding:28px 24px;border-bottom:1px solid #1F2A44}
h1{margin:0;font-size:22px}
.meta{color:#9AA4B2;font-size:13px;margin-top:6px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px;padding:20px}
.card{background:#111B2F;border:1px solid #1F2A44;border-radius:14px;overflow:hidden}
.card img{width:100%;display:block;background:#0B1220}
.card .body{padding:12px 14px}
.badge{display:inline-block;font-size:11px;padding:3px 8px;border-radius:999px;margin-right:6px}
.pass{background:#065F46;color:#A7F3D0}
.fail{background:#7F1D1D;color:#FECACA}
.muted{color:#9AA4B2;font-size:12px}
</style></head><body>
<header>
<h1>__CAMPAIGN__ — __REGION__</h1>
<div class="meta">brand __BRAND__ · audience __AUDIENCE__ · lang __LANG__ · __COUNT__ creatives · __PASS__ pass</div>
</header>
<div class="grid">
__CARDS__
</div>
</body></html>
"""
    cards = []
    for a in report["artifacts"]:
        prod = a["product"]
        ratio = a["ratio"]
        path = a["path"]
        msg = a["message"]
        passed = a["compliance_passed"]
        badge = '<span class="badge pass">PASS</span>' if passed else '<span class="badge fail">FAIL</span>'
        src = a["hero_source"]
        cards.append(f"""
<div class="card">
<img src="{path}" alt="{prod} {ratio}">
<div class="body">
<div>{badge}<span class="muted">{prod} · {ratio} · hero:{src}</span></div>
<div style="margin-top:8px;font-weight:600;">{msg}</div>
</div>
</div>""")

    filled = (
        html.replace("__CAMPAIGN__", report["campaign"])
        .replace("__REGION__", report["region"])
        .replace("__BRAND__", report["brand"])
        .replace("__AUDIENCE__", report["audience"])
        .replace("__LANG__", report["language"])
        .replace("__COUNT__", str(report["summary"]["total_creatives"]))
        .replace("__PASS__", report["summary"]["compliance_pass_rate"])
        .replace("__CARDS__", "\n".join(cards))
    )
    (out_root / "preview.html").write_text(filled, encoding="utf-8")
