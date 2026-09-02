"""Compose final creatives — resize/pad hero to ratios + overlay message + logo."""
from __future__ import annotations

from pathlib import Path
from typing import Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

RATIOS: dict[str, Tuple[int, int]] = {
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
    # aliases
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}

CANONICAL = {"1x1": "1x1", "1:1": "1x1", "9x16": "9x16", "9:16": "9x16", "16x9": "16x9", "16:9": "16x9"}


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

    # text area — bottom 32%
    pad = 48
    text_max_w = W - pad * 2
    # font size responsive to ratio
    font_size = 56 if W >= 1080 else 42
    font = _load_font(font_size)
    small_font = _load_font(max(22, font_size - 22))

    # semi-transparent bar for contrast
    bar_top = int(H * 0.68)
    draw.rectangle([0, bar_top, W, H], fill=(0, 0, 0, 140))

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

    # brand/footer
    footer = "AURA  •  aura.example.com"
    bbox = draw.textbbox((0, 0), footer, font=small_font)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, H - 44), footer, fill=(255, 255, 255, 200), font=small_font)

    # logo overlay if available
    if brand_logo and brand_logo.exists():
        try:
            logo = Image.open(brand_logo).convert("RGBA")
            # scale logo to ~120px wide
            lw = 140
            lh = int(logo.height * (lw / logo.width))
            logo = logo.resize((lw, lh), Image.BICUBIC)
            # paste top-left with padding
            bg.paste(logo, (24, 24), logo)
        except Exception as e:
            print(f"[compose] logo overlay failed: {e}")

    # subtle brand color accent bar at bottom
    if brand_colors:
        try:
            hexv = brand_colors[0].lstrip("#")
            rgb = tuple(int(hexv[i : i + 2], 16) for i in (0, 2, 4))
            draw.rectangle([0, H - 8, W, H], fill=rgb)
        except Exception:
            pass

    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out_path, "PNG")
    return out_path
