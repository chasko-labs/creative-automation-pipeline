"""Compose final creatives — S3-backed tokens + local fallback."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .token_loader import get_brand_colors, get_canvas_dims, load_tokens

# tokens are S3-aware with local fallback (design/tokens/kodiak.json)
_tokens = None
try:
    _tokens = load_tokens()
except Exception:
    _tokens = None

# canvas dims from tokens (fallback to legacy)
try:
    _dims = get_canvas_dims(_tokens)
    RATIOS: dict[str, Tuple[int, int]] = {
        "1x1": _dims.get("1x1", (1080, 1080)),
        "9x16": _dims.get("9x16", (1080, 1920)),
        "16x9": _dims.get("16x9", (1920, 1080)),
        "1:1": _dims.get("1x1", (1080, 1080)),
        "9:16": _dims.get("9x16", (1080, 1920)),
        "16:9": _dims.get("16x9", (1920, 1080)),
    }
except Exception:
    RATIOS: dict[str, Tuple[int, int]] = {
        "1x1": (1080, 1080),
        "9x16": (1080, 1920),
        "16x9": (1920, 1080),
        "1:1": (1080, 1080),
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
    }

CANONICAL = {"1x1": "1x1", "1:1": "1x1", "9x16": "9x16", "9:16": "9x16", "16x9": "16x9", "16:9": "16x9"}

# token-driven defaults
try:
    _default_brand = get_brand_colors(_tokens)
    _brand_accent = _default_brand[1] if len(_default_brand) > 1 else "#E8530E"
    _scrim = _tokens["kodiak"]["color"]["semantic"]["overlay"]["scrim"]["$value"] if _tokens else "#1A1110CC"
except Exception:
    _default_brand = ["#3B2316", "#E8530E", "#1A3C34"]
    _brand_accent = "#E8530E"
    _scrim = "#1A1110CC"


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        test = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def compose_creative(
    hero_path: Path,
    out_path: Path,
    message: str,
    ratio_key: str,
    brand_logo: Path | None = None,
    brand_colors: list[str] | None = None,
    retailer_logo: Path | None = None,
) -> Path:
    """Produce a social creative at the requested ratio with message overlay."""
    key = CANONICAL.get(ratio_key, ratio_key)
    if key not in RATIOS and ratio_key not in RATIOS:
        raise ValueError(f"unknown ratio {ratio_key}, expected one of {list(CANONICAL.keys())}")
    W, H = RATIOS.get(key, RATIOS.get(ratio_key, (1080, 1080)))

    # load hero and cover to target with padding (preserve aspect, add blurred background)
    hero = Image.open(hero_path).convert("RGB")

    # create background by resizing hero to fill then blur-ish (just scaled)
    bg = hero.copy()
    bg = ImageOps.fit(bg, (W, H), method=Image.BICUBIC, bleed=0.0, centering=(0.5, 0.5))
    # darken bg slightly for text legibility
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.18)

    # foreground hero centered, contain
    # compute contain size: keep hero fully visible in safe area
    scale = min(W * 0.82 / hero.width, H * 0.58 / hero.height)
    fw, fh = int(hero.width * scale), int(hero.height * scale)
    fg = hero.resize((fw, fh), Image.BICUBIC)
    # paste fg centered upper
    bg.paste(fg, ((W - fw) // 2, int(H * 0.08)))

    draw = ImageDraw.Draw(bg, "RGBA")

    # text area — bottom 32% — token-driven
    try:
        pad = _tokens["kodiak"]["spacing"]["canvasPad"]["$value"] if _tokens else 48
        bar_pct = float(str(_tokens["kodiak"]["spacing"]["messageBarTop"]["$value"]).strip("%")) / 100 if _tokens and "messageBarTop" in _tokens["kodiak"]["spacing"] else 0.68
        # headline size per ratio from tokens
        if _tokens and ratio_key in _tokens["kodiak"]["typography"]["headline"]:
            font_size = int(_tokens["kodiak"]["typography"]["headline"][ratio_key]["$value"]["fontSize"].replace("px",""))
        else:
            # fallback per canvas width
            font_size = 72 if ratio_key == "16x9" else (64 if ratio_key == "9x16" else 56)
        caption_size = int(_tokens["kodiak"]["typography"]["caption"][ratio_key]["$value"]["fontSize"].replace("px","")) if _tokens and ratio_key in _tokens["kodiak"]["typography"]["caption"] else max(22, font_size - 22)
    except Exception:
        pad, bar_pct, font_size, caption_size = 48, 0.68, (56 if W >= 1080 else 42), max(22, (56 if W >= 1080 else 42) - 22)
    text_max_w = W - pad * 2
    font = _load_font(font_size)
    small_font = _load_font(caption_size)

    # semi-transparent bar for contrast — token scrim
    bar_top = int(H * bar_pct)
    # parse scrim #RRGGBBAA or #RRGGBB
    try:
        scrim_hex = _scrim.lstrip("#")
        if len(scrim_hex) == 8:
            r, g, b, a = (int(scrim_hex[i:i+2],16) for i in (0,2,4,6))
            fill = (r,g,b,a)
        else:
            fill = (0,0,0,140)
    except Exception:
        fill = (0,0,0,140)
    draw.rectangle([0, bar_top, W, H], fill=fill)

    # message — wrap
    y = bar_top + 28
    lines = _wrap_text(draw, message, font, text_max_w)
    # limit to 3 lines
    lines = lines[:3]
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        draw.text(((W - tw) / 2, y), line, fill="white", font=font, stroke_width=2, stroke_fill=(0, 0, 0))
        y += th + 10

    # brand/footer — token caption
    footer = "KODIAK  •  kodiakcakes.com  •  Keep It Wild"
    bbox = draw.textbbox((0, 0), footer, font=small_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, H - 44), footer, fill=(255, 255, 255, 200), font=small_font)

    # logo overlay if available — token clearSpace (KODIAK Bear top-left)
    if brand_logo and brand_logo.exists():
        try:
            logo = Image.open(brand_logo).convert("RGBA")
            try:
                logo_offset = _tokens["kodiak"]["spacing"]["logoOffset"]["$value"] if _tokens else 24
                min_w = 80
                default_w = 140
            except Exception:
                logo_offset, default_w, min_w = 24, 140, 80
            lw = max(min_w, default_w)
            # scale logo to token width, preserve aspect
            if logo.width != lw:
                lh = int(logo.height * (lw / logo.width))
                logo = logo.resize((lw, lh), Image.BICUBIC)
            bg.paste(logo, (logo_offset, logo_offset), logo)
        except Exception as e:
            print(f"[compose] logo overlay failed: {e}", file=sys.stderr)

    # retailer logo — channel partner badge (Costco, Target etc) — bottom-right, small, only when not direct/subscriber variant
    if retailer_logo and retailer_logo.exists():
        try:
            rlogo = Image.open(retailer_logo).convert("RGBA")
            # scale to ~18% width, bottom-right with 24px padding
            rw = int(W * 0.18)
            rh = int(rlogo.height * (rw / rlogo.width))
            # don't obscure message bar: place just above orange bar
            rx = W - rw - 24
            ry = H - rh - 24
            # ensure not overlapping scrim text: keep inside bar_top..H-8
            if ry < bar_top + 20:
                ry = bar_top + 20
            # subtle white backing for retailer mark
            pad = 6
            bg2 = Image.new("RGBA", (rw + pad*2, rh + pad*2), (255, 255, 255, 220))
            bg.paste(bg2, (rx - pad, ry - pad), bg2)
            bg.paste(rlogo.resize((rw, rh), Image.BICUBIC), (rx, ry), rlogo.resize((rw, rh), Image.BICUBIC))
        except Exception as e:
            print(f"[compose] retailer logo failed: {e}", file=sys.stderr)

    # brand color accent bar — token-driven
    colors = brand_colors or _default_brand
    if colors:
        try:
            hexv = (colors[1] if len(colors) > 1 else colors[0]).lstrip("#")  # blaze orange accent
            rgb = tuple(int(hexv[i : i + 2], 16) for i in (0, 2, 4))
            try:
                bar_h = _tokens["kodiak"]["spacing"]["accentBar"]["$value"] if _tokens else 8
            except Exception:
                bar_h = 8
            draw.rectangle([0, H - bar_h, W, H], fill=rgb)
        except Exception:
            pass

    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out_path, "PNG")
    return out_path
