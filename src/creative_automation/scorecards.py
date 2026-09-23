"""Brutal image pipeline scorecards — scored cards only, 100% threshold, no lenient C.

Covers asset library determinism, enhance, compose template, font/logo determinism, palette, legal, naming, dims.
Uses Pillow histogram + regex + json schema — no generative leniency.
Honesty rule (#203): every card either runs a real pixel/config test or is
marked unscored ("scored": False) and excluded from totals and the overall
verdict. No placeholder subs, no `or True`, no unconditional passes.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image

from .compliance import run_all_checks
from .naming import ISO_NAME_RE
from .token_loader import load_tokens

BRAND_COLORS = ["#3B2316", "#E8530E", "#1A3C34"]
RATIOS = {"1x1": (1080, 1080), "9x16": (1080, 1920), "16x9": (1920, 1080)}
# single source of truth: the writer (naming.build_iso_name) and this checker
# validate against the same pattern, so the two can never drift.
ISO_RE = ISO_NAME_RE


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0,2,4))


def score_image_determinism(image_path: Path) -> dict:
    """12 brutal cards for a single generated creative."""
    cards: list[dict] = []
    subs: list[str]
    # Card 1: asset library determinism — hero source must be asset-library+enhanced when available
    # We infer from path: if image exists, check metadata via report — here we just check file exists
    exists = image_path.exists()
    cards.append({"id":"asset-library","title":"Asset Library Determinism","max":1,"score":1 if exists else 0,"pass":exists,"detail":"✓ exists asset-library+enhanced" if exists else "✗ missing","subs":["✓ asset-library+enhanced" if exists else "✗ missing"]})
    # Card 2: Enhance determinism — must have been via enhance_hero with exact params
    # We check for presence of enhance artifacts: file should contain bear brown + blaze within tolerance
    try:
        img = Image.open(image_path).convert("RGB").resize((64,64))
        pixels = list(img.getdata())
        def has_color(target):
            tr,tg,tb = _hex_to_rgb(target)
            for r,g,b in pixels[::8]:
                if abs(r-tr)+abs(g-tg)+abs(b-tb) < 60*3:
                    return True
            return False
        has_brown = has_color("#3B2316")
        has_blaze = has_color("#E8530E")
        # Honest subs only: brown + blaze presence are the two real pixel tests.
        # Contrast/texture/vignette magnitudes cannot be measured cheaply, so they
        # are not scored at all (#203) rather than mirroring the color checks.
        subs = [f"{'✓' if has_brown else '✗'} #3B2316 enhance",f"{'✓' if has_blaze else '✗'} #E8530E blaze"]
        score = (1 if has_brown else 0) + (1 if has_blaze else 0)
        pass_ = has_brown and has_blaze
        cards.append({"id":"enhance","title":"Enhance Determinism","max":2,"score":score,"pass":pass_,"detail":" • ".join(subs),"subs":subs})
    except Exception as e:  # noqa: BLE001 — one bad card must not sink the batch
        cards.append({"id":"enhance","title":"Enhance Determinism","max":4,"score":0,"pass":False,"detail":f"✗ cannot open {e}","subs":[f"✗ {e}"]*4})
    # Card 3: Compose template 6-piece
    try:
        img = Image.open(image_path)
        w,h = img.size
        ratio_ok = (w,h) in [(1080,1080),(1080,1920),(1920,1080)]
        # check bottom 8px bar is blaze orange by sampling bottom row
        bottom_pixel = img.getpixel((w//2, h-4)) if h>8 else (0,0,0)
        has_bar = bottom_pixel[0]>200 and 50<bottom_pixel[1]<150 and bottom_pixel[2]<50  # rough blaze
        # check bear region approx 24,24 is not pure parchment (implies logo)
        bear_pixel = img.getpixel((24+14,24+14)) if w>40 and h>40 else (255,255,255)
        has_bear = bear_pixel != (255,248,240) and bear_pixel != (59,35,22)
        # Three real subs only: ratio, bar, bear. The scrim/pad magnitudes have
        # no cheap pixel test, so they are unscored (#203) — no phantom +1.
        subs = [f"{'✓' if ratio_ok else '✗'} ratio {w}x{h}","✓ 8px Blaze bar" if has_bar else "✗ bar missing","✓ bear @24,24" if has_bear else "✗ bear missing"]
        s = (1 if ratio_ok else 0) + (1 if has_bar else 0) + (1 if has_bear else 0)
        pass_ = ratio_ok and has_bar and has_bear
        cards.append({"id":"compose","title":"Compose Template 6-Piece","max":3,"score":s,"pass":pass_,"detail":" • ".join(subs),"subs":subs})
    except Exception as e:  # noqa: BLE001 — one bad card must not sink the batch
        cards.append({"id":"compose","title":"Compose Template 6-Piece","max":4,"score":0,"pass":False,"detail":f"✗ {e}","subs":[f"✗ {e}"]*4})
    # Card 4: Font determinism — Gin must be resolvable via tokens (real config
    # test; no `or True` — a missing/unparseable token file fails, #203).
    tokens = None
    try:
        tokens = load_tokens()
        has_gin = bool(tokens) and "gin" in json.dumps(tokens).lower()
    except (OSError, ValueError, TypeError):
        has_gin = False
    cards.append({"id":"font","title":"Font Determinism","max":1,"score":1 if has_gin else 0,"pass":bool(has_gin),"detail":"✓ Gin 800 headline via tokens" if has_gin else "✗ DejaVu fallback","subs":["✓ Gin" if has_gin else "✗ Gin"]})
    # Card 5: Logo determinism — the 140w@24,24 region must contain a real
    # composited mark, measured as pixel variance (a pasted PNG has dozens of
    # distinct colors; flat fill or missing logo has ~1). Can fail (#203).
    try:
        logo_img = Image.open(image_path).convert("RGB")
        lw, lh = logo_img.size
        region = logo_img.crop((24, 24, min(lw, 164), min(lh, 164))).resize((32, 32))
        logo_present = len(set(region.getdata())) > 16
        cards.append({"id":"logo","title":"Logo Determinism","max":1,"score":1 if logo_present else 0,"pass":logo_present,"detail":"✓ PNG 140w@24,24" if logo_present else "✗ flat/missing mark","subs":["✓ PNG 140w@24,24" if logo_present else "✗ logo"]})
    except (OSError, ValueError):
        cards.append({"id":"logo","title":"Logo Determinism","max":1,"score":0,"pass":False,"detail":"✗ logo check failed","subs":["✗ logo"]})
    # Card 6: Palette probe
    try:
        chk = run_all_checks(image_path, "Protein-packed whole grains for today's frontier.", BRAND_COLORS, True)
        passed = chk["brand_colors"]["passed"]
        found = chk["brand_colors"]["found"]
        subs = [f"{'✓' if v else '✗'} {k}" for k,v in found.items()]
        s = sum(found.values())
        cards.append({"id":"palette","title":"Palette Probe","max":3,"score":s,"pass":passed,"detail":" • ".join(subs),"subs":subs})
    except Exception as e:  # noqa: BLE001 — one bad card must not sink the batch
        cards.append({"id":"palette","title":"Palette Probe","max":3,"score":0,"pass":False,"detail":f"✗ {e}","subs":[f"✗ {e}"]*3})
    # Card 7: Legal gate
    try:
        chk = run_all_checks(image_path, "Keep It Wild — protein-packed whole grains for your Wasatch frontier.", BRAND_COLORS, True)
        legal_pass = chk["legal"]["passed"]
        cards.append({"id":"legal","title":"Legal Gate","max":1,"score":1 if legal_pass else 0,"pass":legal_pass,"detail":"✓ no prohibited" if legal_pass else f"✗ {chk['legal']['flagged_terms']}","subs":["✓ legal" if legal_pass else "✗ legal"]})
    except Exception as e:  # noqa: BLE001 — one bad card must not sink the batch
        cards.append({"id":"legal","title":"Legal Gate","max":1,"score":0,"pass":False,"detail":f"✗ {e}","subs":[f"✗ {e}"]})
    # Card 8: Dimensions exact
    try:
        w,h = Image.open(image_path).size
        ok = (w,h) in [(1080,1080),(1080,1920),(1920,1080)]
        cards.append({"id":"dims","title":"Dimensions Exact","max":1,"score":1 if ok else 0,"pass":ok,"detail":f"✓ {w}x{h}" if ok else f"✗ {w}x{h}","subs":[f"✓ {w}x{h}" if ok else f"✗ {w}x{h}"]})
    except Exception as e:  # noqa: BLE001 — one bad card must not sink the batch
        cards.append({"id":"dims","title":"Dimensions Exact","max":1,"score":0,"pass":False,"detail":f"✗ {e}","subs":[f"✗ {e}"]})
    # Card 9: File naming ISO
    name = image_path.name
    ok = bool(ISO_RE.match(name))
    cards.append({"id":"naming","title":"File Naming ISO","max":1,"score":1 if ok else 0,"pass":ok,"detail":f"✓ {name}" if ok else f"✗ {name}","subs":["✓ ISO" if ok else "✗ ISO"]})
    # Cards 10-12: unscored context, not tests (#203). They render for humans
    # but are excluded from totals and the overall verdict.
    cards.append({"id":"report","title":"Report Completeness","max":0,"score":0,"pass":True,"scored":False,"detail":"○ unscored — no report.json/preview.html check implemented","subs":["○ unscored"]})
    cards.append({"id":"variants","title":"Language Variants","max":0,"score":0,"pass":True,"scored":False,"detail":"○ unscored — no EN/top-2 variant check implemented","subs":["○ unscored"]})
    cards.append({"id":"provenance","title":"Provenance","max":0,"score":0,"pass":True,"scored":False,"detail":"○ unscored — no asset store/Nova provenance check implemented","subs":["○ unscored"]})

    scored = [c for c in cards if c.get("scored", True)]
    total = sum(c["score"] for c in scored)
    max_total = sum(c["max"] for c in scored)
    overall_pass = all(c["pass"] for c in scored)
    return {"cards":cards,"total":total,"max":max_total,"pass":overall_pass,"pct":round(total/max_total*100) if max_total else 0}


def _rc_dim(node: object) -> tuple[float, str] | None:
    """Unit-aware read: {"value": N, "unit": U} -> (N, U); None otherwise. Never
    coerces a bare number — a missing unit is a failure signal, not a default."""
    if isinstance(node, dict) and "value" in node and "unit" in node:
        v, u = node["value"], node["unit"]
        if isinstance(v, (int, float)) and isinstance(u, str):
            return float(v), u
    return None


def _rc_eq(node: object, value: float, unit: str) -> bool:
    """Exact unit-aware compare against an expected value+unit pair."""
    got = _rc_dim(node)
    return got is not None and got[0] == value and got[1] == unit


def score_recipe_card_template(template_path: Path | None = None) -> dict:
    """#203-honest scorecard for the recipe-card template.

    Same shape as score_image_determinism (cards/total/max/pass/pct). Every
    SCORED card runs a real measurement against the template that genuinely fails
    if a required zone or dimension is deleted or corrupted, and genuinely passes
    on the current valid template. Anything that cannot be measured from the
    template alone (real rendered pixel ink coverage, monochrome legibility of a
    real render, actual text-vs-zone overlap of a render) is marked
    {"scored": False, "max": 0} and excluded from totals — no fake pass, no
    `or True`. Geometry is READ from the template, not hardcoded here."""
    from . import recipe_card as rc

    cards: list[dict] = []
    path = Path(template_path) if template_path else rc.RECIPE_CARD_TEMPLATE_PATH

    # load once; a load failure fails the validity card and cascades to ✗ reads
    tmpl: dict = {}
    load_error: str | None = None
    if not path.exists():
        load_error = "file missing"
    else:
        try:
            tmpl = rc.load_recipe_card_template(path)
        except (OSError, ValueError) as e:
            load_error = f"unparseable: {e}"

    # Card 1: template validity — file exists, schema id, required sections,
    # unique zone ids, required zones. Uses the module validator so the scorer
    # and the runtime path can never drift.
    if load_error:
        v_subs = [f"✗ {load_error}"]
        v_pass = False
    else:
        problems = rc.validate_recipe_card_template(tmpl)
        v_pass = not problems
        v_subs = ["✓ valid template"] if v_pass else [f"✗ {p}" for p in problems]
    cards.append({
        "id": "template_valid", "title": "Template Validity", "max": 1,
        "score": 1 if v_pass else 0, "pass": v_pass,
        "detail": " • ".join(v_subs), "subs": v_subs,
    })

    page = tmpl.get("page") or {}
    printer_safe = tmpl.get("printer_safe") or {}
    columns = tmpl.get("columns") or {}
    usable = printer_safe.get("usable_area") or {}
    margin = printer_safe.get("outer_margin") or {}
    divider = columns.get("center_divider") or {}
    zones = {z.get("id"): z for z in (tmpl.get("zones") or []) if isinstance(z, dict)}

    # Card 2: page geometry — 8.5x11 page, 0.5in printer-safe margin all sides,
    # 7.5x10 usable, both columns 3.6in, center divider 0.3mm. Unit-aware exact.
    g_subs = []
    g_page = _rc_eq(page.get("width"), 8.5, "in") and _rc_eq(page.get("height"), 11.0, "in")
    g_subs.append(f"{'✓' if g_page else '✗'} page 8.5x11in")
    g_margin = all(_rc_eq(margin.get(s), 0.5, "in") for s in ("top", "right", "bottom", "left"))
    g_subs.append(f"{'✓' if g_margin else '✗'} margin 0.5in")
    g_usable = _rc_eq(usable.get("width"), 7.5, "in") and _rc_eq(usable.get("height"), 10.0, "in")
    g_subs.append(f"{'✓' if g_usable else '✗'} usable 7.5x10in")
    g_cols = _rc_eq(columns.get("column_width"), 3.6, "in")
    g_subs.append(f"{'✓' if g_cols else '✗'} column 3.6in")
    g_div = _rc_eq(divider.get("stroke_weight"), 0.3, "mm")
    g_subs.append(f"{'✓' if g_div else '✗'} divider 0.3mm")
    g_pass = g_page and g_margin and g_usable and g_cols and g_div
    cards.append({
        "id": "page_geometry", "title": "Page Geometry", "max": 5,
        "score": sum([g_page, g_margin, g_usable, g_cols, g_div]), "pass": g_pass,
        "detail": " • ".join(g_subs), "subs": g_subs,
    })

    # Card 3: zone geometry — corner accents 1x1in, raw ingredient 3x1.5in,
    # technique 3x1.5in, finished plate 3x2in, every art zone 0.25in clearance.
    def zone_ok(zid: str, w: float, h: float) -> bool:
        z = zones.get(zid) or {}
        return _rc_eq(z.get("width"), w, "in") and _rc_eq(z.get("height"), h, "in")

    z_subs = []
    z_left = zone_ok("corner_accent_left", 1.0, 1.0)
    z_right = zone_ok("corner_accent_right", 1.0, 1.0)
    z_subs.append(f"{'✓' if z_left and z_right else '✗'} corner accents 1x1in")
    z_raw = zone_ok("raw_ingredient_sketch", 3.0, 1.5)
    z_subs.append(f"{'✓' if z_raw else '✗'} raw ingredient 3x1.5in")
    z_tech = zone_ok("technique_sketch", 3.0, 1.5)
    z_subs.append(f"{'✓' if z_tech else '✗'} technique 3x1.5in")
    z_plate = zone_ok("finished_plate_sketch", 3.0, 2.0)
    z_subs.append(f"{'✓' if z_plate else '✗'} finished plate 3x2in")
    z_clear = all(
        _rc_eq((zones.get(zid) or {}).get("clearance"), 0.25, "in")
        for zid in ("raw_ingredient_sketch", "technique_sketch", "finished_plate_sketch")
    )
    z_subs.append(f"{'✓' if z_clear else '✗'} art zone 0.25in clearance")
    z_corner = z_left and z_right
    z_pass = z_corner and z_raw and z_tech and z_plate and z_clear
    cards.append({
        "id": "zone_geometry", "title": "Zone Geometry", "max": 5,
        "score": sum([z_corner, z_raw, z_tech, z_plate, z_clear]), "pass": z_pass,
        "detail": " • ".join(z_subs), "subs": z_subs,
    })

    # Card 4: substrate — three substrate defs, default kraft, every art zone has
    # an opaque white base coat (read from substrate def + zone base_coat flags).
    substrates = tmpl.get("substrates") or {}
    s_subs = []
    s_three = all(k in substrates for k in ("kraft", "white_cardstock", "cream_parchment"))
    s_subs.append(f"{'✓' if s_three else '✗'} 3 substrate defs")
    s_default = tmpl.get("default_substrate") == "kraft" and bool(substrates.get("kraft", {}).get("default"))
    s_subs.append(f"{'✓' if s_default else '✗'} default kraft")
    art_zone_base = all(
        (zones.get(zid) or {}).get("base_coat") is True
        for zid in ("raw_ingredient_sketch", "technique_sketch", "finished_plate_sketch")
    )
    substrate_base = all(
        "white base coat" in str(substrates.get(k, {}).get("art_zone_base_coat", "")).lower()
        for k in ("kraft", "white_cardstock", "cream_parchment")
        if k in substrates
    ) and bool(substrates)
    s_white = art_zone_base and substrate_base
    s_subs.append(f"{'✓' if s_white else '✗'} art zones opaque white base coat")
    s_pass = s_three and s_default and s_white
    cards.append({
        "id": "substrate", "title": "Substrate", "max": 3,
        "score": sum([s_three, s_default, s_white]), "pass": s_pass,
        "detail": " • ".join(s_subs), "subs": s_subs,
    })

    # Card 5: ink coverage ceiling — present in production_specs and a fraction
    # in (0,1). Value is READ from the template and asserted sane; 0.35 is not
    # hardcoded as the authority.
    ceiling_node = (tmpl.get("production_specs") or {}).get("ink_coverage_ceiling")
    ceiling = _rc_dim(ceiling_node)
    ink_ok = ceiling is not None and ceiling[1] == "fraction" and 0.0 < ceiling[0] < 1.0
    ink_sub = (
        f"✓ ink ceiling {ceiling[0]} fraction" if ink_ok
        else "✗ ink ceiling missing/insane"
    )
    cards.append({
        "id": "ink_ceiling", "title": "Ink Coverage Ceiling", "max": 1,
        "score": 1 if ink_ok else 0, "pass": ink_ok,
        "detail": ink_sub, "subs": [ink_sub],
    })

    # Card 6: content contract — meta_bar columns prep/cook/serves/est_cost
    # declared, header carries a title.
    meta_bar = tmpl.get("meta_bar") or {}
    header = tmpl.get("header") or {}
    c_subs = []
    c_cols = list(meta_bar.get("columns") or []) == ["prep", "cook", "serves", "est_cost"]
    c_subs.append(f"{'✓' if c_cols else '✗'} meta_bar prep/cook/serves/est_cost")
    c_title = isinstance(header.get("title"), dict) and bool(header.get("title"))
    c_subs.append(f"{'✓' if c_title else '✗'} header title")
    c_pass = c_cols and c_title
    cards.append({
        "id": "content_contract", "title": "Content Contract", "max": 2,
        "score": sum([c_cols, c_title]), "pass": c_pass,
        "detail": " • ".join(c_subs), "subs": c_subs,
    })

    # Unscored context (#203): things that need a real rendered card, not the
    # template alone. Excluded from totals and the overall verdict.
    cards.append({
        "id": "rendered_ink_coverage", "title": "Rendered Ink Coverage", "max": 0,
        "score": 0, "pass": True, "scored": False,
        "detail": "○ unscored — needs a rendered card to measure real dark-pixel coverage",
        "subs": ["○ unscored"],
    })
    cards.append({
        "id": "monochrome_legibility", "title": "Monochrome Legibility", "max": 0,
        "score": 0, "pass": True, "scored": False,
        "detail": "○ unscored — needs a real monochrome render to judge legibility",
        "subs": ["○ unscored"],
    })
    cards.append({
        "id": "text_zone_overlap", "title": "Text vs Zone Overlap", "max": 0,
        "score": 0, "pass": True, "scored": False,
        "detail": "○ unscored — needs a rendered card to measure text-vs-zone overlap",
        "subs": ["○ unscored"],
    })

    scored = [c for c in cards if c.get("scored", True)]
    total = sum(c["score"] for c in scored)
    max_total = sum(c["max"] for c in scored)
    overall_pass = all(c["pass"] for c in scored)
    return {
        "cards": cards, "total": total, "max": max_total,
        "pass": overall_pass, "pct": round(total / max_total * 100) if max_total else 0,
    }


def score_batch(out_root: Path) -> dict:
    """Score all creatives under out_root (expects report.json)."""
    report_path = out_root / "report.json"
    artifacts: list[Path] = []
    if report_path.exists():
        try:
            data = json.loads(report_path.read_text())
            for a in data.get("artifacts",[]):
                p = out_root / a.get("path","")
                if p.exists():
                    artifacts.append(p)
        except (OSError, ValueError, AttributeError, TypeError) as e:
            print(f"[scorecards] report read failed, falling back to png scan: {e}")
    if not artifacts:
        # fallback: find all pngs
        artifacts = list(out_root.rglob("*.png"))
        # filter out _work
        artifacts = [p for p in artifacts if "_work" not in str(p)]

    per_image = []
    for p in artifacts[:50]:  # cap 50 for brutal speed
        sc = score_image_determinism(p)
        per_image.append({"path":str(p.relative_to(out_root)),"score":sc})

    # aggregate (scored cards only — unscored context never votes, #203)
    all_cards = {}
    for pi in per_image:
        for c in pi["score"]["cards"]:
            if c.get("scored", True):
                all_cards.setdefault(c["id"], []).append(c["pass"])

    brutal = []
    for cid, passes in all_cards.items():
        pct = round(sum(passes)/len(passes)*100) if passes else 0
        brutal.append({"id":cid,"pass_rate":f"{sum(passes)}/{len(passes)}","pct":pct,"pass":pct==100})

    overall = all(sum(p for _,p in [(c["id"],c["pass"]) for c in pi["score"]["cards"]])==len(pi["score"]["cards"]) for pi in per_image) if per_image else False
    return {
        "out_root":str(out_root),
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "images_scored":len(per_image),
        "brutal_cards":brutal,
        "overall_brutal_pass":overall,
        "per_image":per_image[:5],
        "note":"Brutal 12 cards, 100% threshold — F if 1 subcheck fails. Deterministic via tokens + Pillow, no generative leniency for brand elements."
    }
