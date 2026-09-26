"""Recipe-card compose cluster — extracted from generate.py.

Pillow card assembly: canvas table, kraft base, headline slab, zone drawing.
generate.py imports only what it calls; this module owns the code.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


# Canvas sizes per ISO ratio (social-3ratio.json). The real lifestyle photo fills
# each frame as the cover background — no ellipse, no solid-color-only path.
_CANVAS = {
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
    # Delivery ratios (pinned v2 DoD): 4x5 portrait feed, 9x16 vertical, 16x9
    # landscape, all cover-fit from the photographic base in full mode.
    "4x5": (1080, 1350),
}


# Per-ratio headline slab size (C06: 56/64/72).
_HEADLINE_PX = {"1x1": 56, "9x16": 64, "16x9": 72, "4x5": 60}


_scrim_hex = "#1A1110CC"  # tokens kodiak.color.semantic.overlay.scrim (warm ink)


_accent_hex = "#E8530E"  # tokens kodiak.color.brand.blazeOrange


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --------------------------------------------------------------- kraft-paper texture
# PART D — a deterministic brown-paper-bag grain baked into every final render at ~2%.
# Pillow-only (numpy is not a core dependency), fixed-seed so output is byte-reproducible
# and testable. Warm kraft base ~#C8A97E + low-amplitude per-pixel noise + sparse fibrous
# specks. To dump a reusable 512x512 tile for the web side to load, run:
#     python -c "from creative_automation.generate import _kraft_texture; \
#                _kraft_texture(512, 512).save('kraft-512.png')"
_KRAFT_BASE = (200, 169, 126)  # ~#C8A97E warm kraft


def _wrap_headline(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Word-wrap headline to fit max_w, capped at 3 lines (C04)."""
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
        if len(lines) == 3:
            break
    if cur and len(lines) < 3:
        lines.append(cur)
    return lines[:3]


def _compose_recipe_card(
    hero_img_path: Path,
    title: str,
    ratio: str,
    out_path: Path,
    recipe_fields: dict | None = None,
) -> Path:
    """Deterministic Pillow recipe-card: GenAI hero in a fixed image slot + brand card.

    The whole point: the card STRUCTURE is composed deterministically in Pillow
    (typography, title bar, ingredient/step zones, accent bar, safe-area), and the
    generative hero image is PLACED into a defined image slot rather than the model
    inventing the layout. Layout:

      - top ~55% : the GenAI hero, cover-fit into the image slot (ImageOps.fit BICUBIC)
      - title bar: a scrim-ink band straddling the hero/card seam, title in headline font
      - lower ~45%: token-brand card on a warm kraft base — an ingredients column and a
        steps column drawn in the body font, inside a safe-area pad
      - C03 8px Blaze Orange accent bar pinned to the very bottom

    Deterministic: same inputs -> same bytes (fonts + palette are fixed; the only
    randomness in the pipeline is the already-seeded kraft texture applied later by
    _finalize_render). Reuses generate.py palette constants (_scrim_hex, _accent_hex),
    _CANVAS dims, _HEADLINE_PX, and _wrap_headline — no new hardcoded hex.
    """
    W, H = _CANVAS.get(ratio, _CANVAS["1x1"])
    fields = recipe_fields or {}
    ingredients = [str(x) for x in fields.get("ingredients", []) if str(x).strip()]
    steps = [str(x) for x in fields.get("steps", []) if str(x).strip()]

    # image slot = top 55% of the canvas; the GenAI hero cover-fits it (stays the hero).
    slot_h = int(H * 0.55)
    hero = Image.open(hero_img_path).convert("RGB")
    hero_fit = ImageOps.fit(hero, (W, slot_h), method=Image.BICUBIC, centering=(0.5, 0.4))

    # card base: warm kraft ink for the lower region so it reads as a paper card.
    card = Image.new("RGB", (W, H), _KRAFT_BASE)
    card.paste(hero_fit, (0, 0))
    canvas = card.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    pad = 48  # C03 safe-area pad, shared with _apply_brand_overlay

    # title bar: a scrim-ink band across the hero/card seam, title centered in it.
    title_h = int(H * 0.14)
    title_top = slot_h - title_h // 2
    bar = Image.new("RGBA", (W, title_h), (*_hex_to_rgb(_scrim_hex), 220))
    canvas.alpha_composite(bar, (0, title_top))
    if title:
        px = _HEADLINE_PX.get(ratio, 56)
        try:
            tfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", px)
        except OSError:
            tfont = ImageFont.load_default()
        lines = _wrap_headline(draw, title, tfont, W - 2 * pad)
        line_h = int(px * 1.15)
        block_h = line_h * len(lines)
        ty = title_top + (title_h - block_h) // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=tfont)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((W - tw) / 2, ty), line, fill="white", font=tfont,
                stroke_width=2, stroke_fill=(0, 0, 0, 180),
            )
            ty += line_h

    # body zones: ingredients (left) + steps (right) in the kraft card region.
    body_px = max(20, int(_HEADLINE_PX.get(ratio, 56) * 0.42))
    try:
        hfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", body_px)
        bfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", body_px)
    except OSError:
        hfont = ImageFont.load_default()
        bfont = hfont
    ink = _hex_to_rgb(_scrim_hex)
    body_top = title_top + title_h + pad // 2
    line_gap = int(body_px * 1.4)
    col_x = {"left": pad, "right": W // 2 + pad // 2}

    # Legibility floor: body text must end above the accent bar. Each column
    # fits what fits — items that would cross the floor are dropped, so a
    # long LLM-authored list can never bleed off the card or under the bar.
    floor_y = H - 8 - line_gap
    capacity = max(0, (floor_y - body_top - line_gap) // line_gap)

    def _draw_zone(x: int, heading: str, items: list[str]) -> int:
        y = body_top
        draw.text((x, y), heading, fill=(*ink, 255), font=hfont)
        y += line_gap
        drawn = 0
        for item in items[:capacity]:
            draw.text((x, y), f"- {item}", fill=(*ink, 255), font=bfont)
            y += line_gap
            drawn += 1
        return drawn

    _draw_zone(col_x["left"], "Ingredients", ingredients)
    _draw_zone(col_x["right"], "Steps", steps)

    # C03 — 8px Blaze Orange accent bar at the very bottom.
    accent = _hex_to_rgb(_accent_hex)
    draw.rectangle([0, H - 8, W, H], fill=(*accent, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path

