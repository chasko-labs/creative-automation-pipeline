"""Suggested posts — remix existing heroes into every shape.

Like Linda's film crew VariantsSpec (Director/Editor/Cinematographer agents
picking clips for 16:9, 9:16, 1:1), we treat each existing hero as a source
clip and generate a variant per aspect ratio with localized messaging.

Pipeline: scan dam_root for hero.* → enhance → compose ×3 ratios → preview sheet.
No new GenAI needed; reuses what the brand already shot.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from .compose import compose_creative
from .compliance import run_all_checks
from .dam import find_brand_logo
from .enhance import enhance_hero


def suggest_variants(
    dam_root: Path,
    out_root: Path,
    ratios: list[str] | None = None,
    messages: list[str] | None = None,
    brand_colors: list[str] | None = None,
    limit: int | None = None,
) -> dict:
    """Generate suggested posts from existing heroes.

    - dam_root: input_assets (contains product-id/hero.*)
    - out_root: where to write suggested/ hierarchy
    - ratios: defaults to 1x1, 9x16, 16x9
    - messages: list of headline strings to cycle through; falls back to product name
    - brand_colors: forwarded to compose
    - limit: cap number of source heroes scanned
    """
    t0 = time.time()
    ratios = ratios or ["1x1", "9x16", "16x9"]
    brand_colors = brand_colors or ["#3B2316", "#E8530E", "#1A3C34"]
    messages = messages or []
    brand_logo = find_brand_logo(dam_root)

    # Find all hero assets under dam_root/*/hero.* plus hero.enhanced.*
    heroes: list[Path] = []
    for p in sorted(dam_root.rglob("hero.*")):
        if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        # skip generated enhanced duplicates as primary source — we enhance on the fly
        if p.name == "hero.enhanced.png":
            continue
        heroes.append(p)
    if limit:
        heroes = heroes[:limit]

    out_root.mkdir(parents=True, exist_ok=True)
    artifacts: list[dict] = []
    total = 0
    passed = 0

    for hero in heroes:
        product_id = hero.parent.name
        # work copy
        work = out_root / "_work" / f"{product_id}_hero.png"
        work.parent.mkdir(parents=True, exist_ok=True)
        import shutil

        shutil.copy2(hero, work)
        # enhance (contrast/texture/vignette; framing/watermark handled in compose to avoid double-frame)
        try:
            enhance_hero(work, work, contrast=1.08, brightness=1.02, sharpness=1.12, texture=True, frame=False, watermark=False, vignette=True)
            hero_source = "dam+enhanced"
        except Exception:
            hero_source = "dam"

        # Pick message for this hero: cycle messages or fallback
        msg_idx = heroes.index(hero) % max(1, len(messages)) if messages else 0
        msg = messages[msg_idx] if messages else f"KODIAK® {product_id} — Feeding Epic Days & Wilder Lives"

        for ratio in ratios:
            folder = ratio.replace(":", "x")
            if folder in ("1:1",):
                folder = "1x1"
            elif folder in ("9:16",):
                folder = "9x16"
            elif folder in ("16:9",):
                folder = "16x9"
            # sanitize ratio key for filename
            iso_date = time.strftime("%Y%m%d")
            fname = f"KODIAK-CAKES-{product_id}-suggested-{folder}-{iso_date}-v01.png"
            out_path = out_root / product_id / folder / fname
            compose_creative(
                hero_path=work,
                out_path=out_path,
                message=msg,
                ratio_key=ratio,
                brand_logo=brand_logo,
                brand_colors=brand_colors,
            )
            checks = run_all_checks(out_path, msg, brand_colors, brand_logo is not None)
            artifacts.append(
                {
                    "product": product_id,
                    "ratio": folder,
                    "path": str(out_path.relative_to(out_root)),
                    "absolute": str(out_path),
                    "message": msg,
                    "hero_source": hero_source,
                    "hero_original": str(hero),
                    "compliance_passed": checks["overall_passed"],
                }
            )
            total += 1
            if checks["overall_passed"]:
                passed += 1

    report = {
        "kind": "suggested",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "heroes_found": len(heroes),
        "ratios": ratios,
        "total_creatives": total,
        "compliance_pass_rate": f"{passed}/{total}" if total else "0/0",
        "elapsed_sec": round(time.time() - t0, 2),
        "artifacts": artifacts,
        "notes": "Remixed from existing heroes — no new shoot, 3 shapes per source (inspired by Linda Mohamed AI Film Crew VariantSpec across 16:9/9:16/1:1). Enhancements: contrast + texture + vignette institutionalizing KODIAK brown fidelity; framing + watermark in compose.",
    }
    (out_root / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with open(out_root / "report.jsonl", "w", encoding="utf-8") as f:
        for a in artifacts:
            f.write(json.dumps(a) + "\n")

    _write_preview(report, out_root)
    return report


def _write_preview(report: dict, out_root: Path):
    html = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Suggested Posts — KODIAK</title>
<style>:root{--bear:#3B2316;--blaze:#E8530E;--forest:#1A3C34;--parch:#FFF8F0;--oat:#F4EDE6;--stone:#D9CFC6;--stoneL:#E8DDD3;--taupe:#8C7A70;--ink:#1A1110}
*{box-sizing:border-box}body{margin:0;background:var(--parch);color:var(--bear);font-family:Inter,system-ui,Arial,sans-serif}
header{background:var(--bear);color:var(--parch);padding:28px;border-bottom:6px solid var(--blaze)}
h1{margin:0;font-family:Rockwell,Georgia,serif;font-weight:800;font-size:22px}
.meta{color:rgba(255,248,240,.82);font-size:12px;margin-top:8px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:18px;padding:22px;max-width:1440px;margin:0 auto}
.card{background:#fff;border:1px solid var(--stone);border-radius:14px;overflow:hidden;box-shadow:0 2px 8px rgba(26,17,16,.07)}
.card::before{content:"";height:3px;background:var(--blaze);display:block}
.card img{width:100%;display:block;background:var(--oat)}
.body{padding:12px 14px}
.badge{display:inline-flex;font-size:10px;font-weight:800;letter-spacing:.06em;padding:3px 8px;border-radius:999px}
.pass{background:var(--forest);color:#FFF8F0}.fail{background:#7F1D1D;color:#FECACA}
.msg{font-family:Rockwell,Georgia,serif;font-weight:700;font-size:14px;line-height:1.35;margin-top:6px}
.small{color:var(--taupe);font-size:11px}</style></head><body>
<header><div style="letter-spacing:.12em;text-transform:uppercase;color:var(--blaze);font-size:10px;font-weight:800">Suggested Posts — Remix What Exists</div>
<h1>KODIAK® Posts for Today's Frontier — Suggested</h1><div class="meta">__META__</div></header>
<div class="grid">__CARDS__</div></body></html>"""
    dims_map = {"1x1": "1080×1080", "9x16": "1080×1920", "16x9": "1920×1080"}
    cards = []
    for a in report["artifacts"]:
        badge = '<span class="badge pass">PASS</span>' if a["compliance_passed"] else '<span class="badge fail">FAIL</span>'
        dims = dims_map.get(a["ratio"], a["ratio"])
        cards.append(f"""<div class="card"><img src="{a["path"]}" alt="{a["product"]} {a["ratio"]}" loading="lazy"><div class="body"><div class="small">{badge} {a["ratio"]} · {dims} · {a["hero_source"]}</div><div class="msg">{a["message"]}</div><div class="small">{a["product"]} — {a["path"]}</div></div></div>""")
    meta = f"{report['heroes_found']} heroes → {report['total_creatives']} creatives · {report['compliance_pass_rate']} pass · {report['elapsed_sec']}s"
    filled = html.replace("__META__", meta).replace("__CARDS__", "\n".join(cards))
    (out_root / "preview.html").write_text(filled, encoding="utf-8")
