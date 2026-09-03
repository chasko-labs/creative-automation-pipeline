"""Image enhancement — institutionalize KODIAK branding via contrast, texture, framing, watermark.

Inspired by Linda Mohamed's AI Film Crew pipeline (Builder Center 3FuJ4):
- intake -> analysis (MediaConvert downsizing, Rekognition/BDA visual timeline) -> creative (Agent crew)
  We apply the same layered discipline to still imagery: normalize intake, analyze histogram,
  then creatively grade + texture + frame + watermark as editorial decisions.

All ops are Pillow-only, deterministic, offline. Toggleable via `enhance_hero`.
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageOps

try:
    from .token_loader import load_tokens
    _tok = load_tokens()
except Exception:
    _tok = None

# Optional Rust accelerator (cargo build in rust/kodiak-local, maturin develop).
# Falls back to pure-Python Pillow when extension is absent.
# maturin installs the ext at the nested path when built from the workspace
# pyproject ([tool.maturin] module-name), but at the bare _kodiak_local name when
# built with `maturin develop -m rust/kodiak-local/Cargo.toml`. Accept either so
# the Rust dispatch path is reachable regardless of build invocation.
try:
    import creative_automation._kodiak_local as _rust  # type: ignore
except ImportError:
    try:
        import _kodiak_local as _rust  # type: ignore
    except ImportError:
        _rust = None  # type: ignore


def _use_rust() -> bool:
    """Opt-in Rust dispatch gate.

    Requires BOTH the compiled extension present AND KODIAK_RUST=1. Default off so
    CI (which runs pytest without the compiled ext) always takes the Pillow path.
    """
    return _rust is not None and os.getenv("KODIAK_RUST") == "1"

BEAR_BROWN = "#3B2316"
BLAZE_ORANGE = "#E8530E"
STONE = "#D9CFC6"
PARCHMENT = "#FFF8F0"


def _hex(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore


def _kraft_texture(size: tuple[int, int], opacity: float = 0.06) -> Image.Image:
    """Subtle kraft paper texture — horizontal hairlines at 6 percent, matches --kraft CSS."""
    w, h = size
    tex = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(tex)
    # hairlines every 20 px (like SVG var --kraft)
    y = 0
    while y < h:
        draw.line([(0, y), (w, y)], fill=(*_hex("#624E42"), int(255 * opacity)))
        y += 20
    return tex


def enhance_hero(
    src: Path,
    dst: Path | None = None,
    *,
    contrast: float = 1.08,
    brightness: float = 1.02,
    sharpness: float = 1.12,
    texture: bool = True,
    frame: bool = True,
    watermark: bool = True,
    vignette: bool = True,
) -> Path:
    """Enhance an existing hero image and write to dst (or overwrite src if None).

    - contrast/brightness/sharpness via PIL ImageEnhance (gentle, product-safe)
    - kraft texture overlay (horizontal hairlines, 6 percent)
    - framing: double border — 1 px stone inner, 6 px bear-brown outer, rounded via ImageOps
    - watermark: Bear silhouette proxy at 24,24 (14 px radius orange circle + BEAR label)
    - vignette: very gentle 0.06 radial darken at edges
    Returns path to enhanced file.
    """
    out = dst or src
    img = Image.open(src).convert("RGBA")
    # Auto-contrast normalize first (histogram stretch mild) — RGB only, preserve alpha
    if _use_rust():
        w, h = img.size
        buf = _rust.autocontrast(img.tobytes(), w, h, 0.5)
        img = Image.frombytes("RGBA", (w, h), bytes(buf))
    else:
        r, g, b, a = img.split()
        rgb = Image.merge("RGB", (r, g, b))
        rgb = ImageOps.autocontrast(rgb, cutoff=0.5)
        r, g, b = rgb.split()
        img = Image.merge("RGBA", (r, g, b, a))
    # Enhance chain
    if contrast != 1.0:
        img = ImageEnhance.Contrast(img).enhance(contrast)
    if brightness != 1.0:
        img = ImageEnhance.Brightness(img).enhance(brightness)
    if sharpness != 1.0:
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
    # Gentle color bump — keep within KODIAK brown fidelity
    img = ImageEnhance.Color(img).enhance(1.04)

    # Texture
    if texture:
        tex = _kraft_texture(img.size, opacity=0.06)
        img = Image.alpha_composite(img, tex)

    # Vignette — radial darken edges 6 percent
    if vignette:
        if _use_rust():
            w, h = img.size
            buf = _rust.vignette(img.tobytes(), w, h)
            img = Image.frombytes("RGBA", (w, h), bytes(buf))
        else:
            w, h = img.size
            vign = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            vd = ImageDraw.Draw(vign)
            # approximate vignette via concentric rects with increasing alpha
            for i in range(12):
                alpha = int(i * 1.2)  # max ~14
                inset = i * (min(w, h) // 90)
                vd.rectangle([inset, inset, w - inset, h - inset], outline=(0, 0, 0, alpha))
            img = Image.alpha_composite(img, vign)

    # Framing — double border
    if frame:
        if _use_rust():
            w, h = img.size
            buf, fw, fh = _rust.framing(img.tobytes(), w, h)
            img = Image.frombytes("RGBA", (fw, fh), bytes(buf))
        else:
            # inner 1 px stone
            img = ImageOps.expand(img, border=1, fill=_hex(STONE))
            # outer 6 px bear brown
            img = ImageOps.expand(img, border=6, fill=_hex(BEAR_BROWN))
            # also add thin Blaze Orange hairline at bottom 2 px to echo accent bar
            draw = ImageDraw.Draw(img)
            w, h = img.size
            draw.rectangle([0, h - 2, w, h], fill=_hex(BLAZE_ORANGE))

    # Watermark — bear mark at 24,24 — same placement as compose template
    if watermark:
        draw = ImageDraw.Draw(img)
        cx, cy, r = 24 + 18, 24 + 18, 14
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=_hex(BLAZE_ORANGE))
        # label
        try:
            from PIL import ImageFont

            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 9)
        except Exception:
            font = None
        draw.text((42 - 10, 42 - 3), "BEAR", fill=_hex(BEAR_BROWN), font=font, anchor="mm" if font else None)

    # Flatten to RGB for pipeline consistency (keep alpha if caller wants PNG)
    # Save as PNG to preserve framing
    out.parent.mkdir(parents=True, exist_ok=True)
    # Convert back to RGB if needed for downstream compose (which expects RGB)
    rgb = Image.new("RGB", img.size, (255, 255, 255))
    rgb.paste(img, mask=img.split()[3] if img.mode == "RGBA" else None)
    # But keep PNG with alpha for richness; pipeline's compose will handle RGB conversion
    img.save(out, "PNG")
    return out


def enhance_existing_heroes(input_assets: Path, out_dir: Path | None = None) -> list[Path]:
    """Batch enhance every hero.png under input_assets/* / hero.*.

    Returns list of enhanced paths (written alongside originals as hero.enhanced.png
    or into out_dir if provided).
    """
    heroes: list[Path] = []
    for hero in input_assets.rglob("hero.*"):
        if hero.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        dst = (out_dir / hero.relative_to(input_assets).with_suffix("")).with_suffix(".enhanced.png") if out_dir else hero.with_suffix(".enhanced.png")
        # also support hero.enhanced.png naming
        if out_dir is None:
            dst = hero.parent / "hero.enhanced.png"
        try:
            enhance_hero(hero, dst)
            heroes.append(dst)
        except Exception as e:
            print(f"[enhance] skip {hero}: {e}")
    return heroes
