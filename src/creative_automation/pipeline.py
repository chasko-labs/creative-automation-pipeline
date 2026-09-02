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
from .enhance import enhance_hero
from .generate import generate_hero
from .localize import localize_message


def run_pipeline(
    brief: CampaignBrief,
    dam_root: Path,
    out_root: Path,
    ratios: List[str] | None = None,
    lang: str | None = None,
    enhance: bool = True,
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
            # copy to work then optionally enhance (contrast/texture/framing/watermark)
            import shutil

            shutil.copy2(hero, work_hero)
            if enhance:
                try:
                    enhance_hero(work_hero, work_hero, contrast=1.08, brightness=1.02, sharpness=1.12, texture=True, frame=False, watermark=False, vignette=True)
                    hero_source = f"{hero_source}+enhanced"
                except Exception as e:
                    print(f"[pipeline] enhance skip {product.id}: {e}")
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
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Creative Automation \u2014 Preview</title>
<style>
:root{--bear:#3B2316;--blaze:#E8530E;--forest:#1A3C34;--parchment:#FFF8F0;--oatmeal:#F4EDE6;--stone:#D9CFC6;--stone-light:#E8DDD3;--canyon:#6B5A53;--taupe:#8C7A70;--ink:#1A1110}
*{box-sizing:border-box}
body{margin:0;background:var(--parchment);color:var(--bear);font-family:Inter,"Helvetica Neue",Arial,system-ui,-apple-system,sans-serif;-webkit-font-smoothing:antialiased}
header{background:var(--bear);color:var(--parchment);padding:36px 28px 28px;position:relative;border-bottom:6px solid var(--blaze);overflow:hidden}
header::after{content:"";position:absolute;inset:0;opacity:0.045;background:repeating-linear-gradient(90deg,transparent,transparent 44px,rgba(255,255,255,0.9) 44px,rgba(255,255,255,0.9) 45px);pointer-events:none}
header>*{position:relative}
.eyebrow{font-size:10px;letter-spacing:0.14em;text-transform:uppercase;color:var(--blaze);font-weight:800;margin:0 0 8px}
h1{margin:0;font-family:Rockwell,Clarendon,"American Typewriter",Georgia,serif;font-weight:800;font-size:28px;letter-spacing:-0.02em;line-height:1.08}
.meta{color:rgba(255,248,240,0.84);font-size:13px;margin-top:10px;line-height:1.5}
.meta strong{color:var(--parchment);font-weight:700}
.header-accent{margin-top:14px;display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.dot{width:8px;height:8px;border-radius:50%;background:var(--blaze);display:inline-block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:22px;padding:28px;max-width:1440px;margin:0 auto}
.card{background:#fff;border:1px solid var(--stone);border-radius:16px;overflow:hidden;box-shadow:0 2px 8px rgba(26,17,16,0.07),0 12px 28px rgba(59,35,22,0.08);transition:transform 0.18s ease,box-shadow 0.18s ease;display:flex;flex-direction:column;position:relative}
.card::before{content:"";height:3px;background:var(--blaze);display:block}
.card:hover{transform:translateY(-3px);box-shadow:0 8px 22px rgba(26,17,16,0.13),0 18px 42px rgba(59,35,22,0.11)}
.card img{width:100%;display:block;background:var(--oatmeal);object-fit:cover;border-bottom:1px solid var(--stone-light)}
.card .body{padding:14px 16px 16px;flex:1;display:flex;flex-direction:column;gap:10px}
.top-row{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.badge{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:800;letter-spacing:0.08em;text-transform:uppercase;padding:4px 10px;border-radius:999px;line-height:1}
.pass{background:var(--forest);color:#FFF8F0;border:1px solid rgba(255,255,255,0.14)}
.fail{background:#7F1D1D;color:#FECACA}
.muted{color:var(--canyon);font-size:11px;letter-spacing:0.04em;text-transform:uppercase;font-weight:700}
.ratio-chip{display:inline-flex;align-items:center;font-size:10px;font-weight:800;letter-spacing:0.06em;padding:4px 9px;border-radius:999px;background:var(--oatmeal);color:var(--bear);border:1px solid var(--stone-light)}
.dims{color:var(--taupe);font-size:11px;font-weight:500;letter-spacing:0.02em}
.message{font-family:Rockwell,Clarendon,Georgia,serif;font-weight:700;font-size:15.5px;line-height:1.35;color:var(--bear);letter-spacing:-0.01em}
.card-footer{margin-top:auto;padding-top:10px;border-top:1px dashed var(--stone-light);display:flex;justify-content:space-between;align-items:center;gap:8px}
.hero-src{font-size:11px;color:var(--taupe)}
.hero-src strong{color:var(--canyon);text-transform:uppercase;letter-spacing:0.05em;font-size:10px}
footer.page{max-width:1440px;margin:0 auto;padding:0 28px 28px;color:var(--taupe);font-size:11px;letter-spacing:0.04em}
footer.page span{color:var(--blaze);font-weight:800}
@media(max-width:640px){h1{font-size:22px}.grid{padding:18px;grid-template-columns:1fr}}
</style></head><body>
<header>
<p class="eyebrow">Kodiak \u2014 Keep It Wild &bull; Frontier Breakfast</p>
<h1>__CAMPAIGN__ \u2014 __REGION__</h1>
<div class="meta"><strong>__BRAND__</strong> &middot; __AUDIENCE__ &middot; lang __LANG__ &middot; __COUNT__ creatives &middot; <span style="color:#A7F3D0;font-weight:800">__PASS__ pass</span></div>
<div class="header-accent"><span class="dot"></span><span style="font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:rgba(255,248,240,0.7);font-weight:700">Parchment &amp; Bear Brown \u2014 Blaze Orange Frontier System</span></div>
</header>
<div class="grid">
__CARDS__
</div>
<footer class="page">Built with Kodiak tokens &mdash; <span>Bear Brown #3B2316</span> &middot; <span>Blaze Orange #E8530E</span> &middot; <span>Frontier Green #1A3C34</span> &middot; Parchment #FFF8F0 &middot; 3 products &times; 3 ratios = 9 cards</footer>
</body></html>
"""
    dims_map = {"1x1": "1080&times;1080", "9x16": "1080&times;1920", "16x9": "1920&times;1080"}
    cards = []
    for a in report["artifacts"]:
        prod = a["product"]
        ratio = a["ratio"]
        path = a["path"]
        msg = a["message"]
        passed = a["compliance_passed"]
        badge = '<span class="badge pass">PASS</span>' if passed else '<span class="badge fail">FAIL</span>'
        src = a["hero_source"]
        dims = dims_map.get(ratio, ratio)
        cards.append(f"""
<div class="card">
<img src="{path}" alt="{prod} {ratio} \u2014 {dims}" loading="lazy">
<div class="body">
<div class="top-row">{badge}<span class="ratio-chip">{ratio}</span><span class="dims">{dims}</span></div>
<div class="muted">{prod} &middot; hero:{src}</div>
<div class="message">{msg}</div>
<div class="card-footer"><span class="hero-src">source <strong>{src}</strong></span><span class="dims">{ratio}</span></div>
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
