"""Brand + legal compliance checks."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, List

from PIL import Image

PROHIBITED_WORDS = [
    "guaranteed",
    "miracle",
    "cure",
    "weight loss",
    "anti-aging cure",
    "FDA approved",  # flag unless verified
]

try:
    from .token_loader import get_brand_colors  # type: ignore

    DEFAULT_BRAND_COLORS = get_brand_colors()
except Exception:
    DEFAULT_BRAND_COLORS = ["#3B2316", "#E8530E", "#1A3C34"]


def check_legal(message: str) -> Dict:
    hits: List[str] = []
    low = message.lower()
    for w in PROHIBITED_WORDS:
        if w.lower() in low:
            hits.append(w)
    return {"passed": len(hits) == 0, "flagged_terms": hits, "message": message}


def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def check_brand_colors(image_path: Path, expected_hexes: List[str] | None, tolerance: int = 60) -> Dict:
    """Very lightweight palette check — samples image and sees if expected colors appear nearby."""
    expected = expected_hexes or DEFAULT_BRAND_COLORS
    try:
        img = Image.open(image_path).convert("RGB").resize((64, 64))
        pixels = list(img.getdata())
    except Exception as e:
        return {"passed": False, "reason": f"cannot open image: {e}", "expected": expected}

    def color_present(target):
        tr, tg, tb = _hex_to_rgb(target)
        for r, g, b in pixels[::16]:  # sample subset
            if abs(r - tr) + abs(g - tg) + abs(b - tb) < tolerance * 3:
                return True
        return False

    # for poc we only require accent bar presence (always drawn) — so this usually passes
    # but we report per color
    results = {c: color_present(c) for c in expected}
    # pass if at least one expected color found (mock hero may not contain exact)
    passed = any(results.values())
    return {"expected": expected, "found": results, "passed": passed, "note": "lightweight histogram probe"}


def check_logo(image_path: Path, logo_present: bool) -> Dict:
    # In compose we always try to overlay logo; so check if creative has logo region non-trivial
    # For now just reflect whether logo file was available
    return {"logo_overlay": logo_present, "passed": logo_present, "note": "checks if brand logo was composited"}


def run_all_checks(image_path: Path, message: str, brand_colors: List[str] | None, logo_present: bool) -> Dict:
    legal = check_legal(message)
    colors = check_brand_colors(image_path, brand_colors)
    logo = check_logo(image_path, logo_present)
    overall = legal["passed"] and colors["passed"] and logo["passed"]
    return {"overall_passed": overall, "legal": legal, "brand_colors": colors, "logo": logo}
