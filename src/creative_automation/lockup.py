"""Retailer-lockup compositor — the ONE sanctioned text-in-image path (cr-1 carve-out).

Kodiak imagery is text-free by rule (cr-1). This module is the single documented
exception: a retailer logo lockup with an optional local store address baked onto the
base image. It is an EXPLICIT overlay operation, never part of the default spin
(spin.py bakes no text; compose.py's message overlay is a separate template surface).

Resolution + degradation order for the logo mark:

1. SVG (preferred) — rasterized ONLY if `cairosvg` is already importable. cairosvg is
   NOT a project dependency and MUST NOT be added just for this op (it pulls a heavy
   native cairo stack). If it is absent we fall through — honestly, no silent failure.
2. PNG raster fallback — if a usable {retailer}.png exists, composite it directly.
3. text-only lockup band — if NEITHER a rasterizable SVG nor a PNG is usable (the
   current state: input_assets/retailer-logos/ is empty, retailers.missing_logos()
   lists all three), compose a clean band carrying the retailer NAME + store address
   as documented graceful degradation, with a warning telling the operator to drop
   the real vector at input_assets/retailer-logos/{retailer}.svg.

The store-address text placed here is the cr-1 carve-out — the only text this whole
pipeline is permitted to bake into an image.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

from .compose import _load_font
from .enhance import _hex
from .naming import build_iso_name
from .retailers import STORE_ADDRESS_SEEDS, RetailerLogo, normalize_retailer, resolve_retailer

# lockup band — bear-brown scrim, parchment text, blaze-orange hairline (brand tokens)
_BAND_BG = "#3B2316"
_BAND_TEXT = "#FFF8F0"
_BAND_ACCENT = "#E8530E"

# valid band positions
_POSITIONS = {"bottom", "top"}


def _seed_address(retailer_key: str, store_address: str | None) -> tuple[str | None, list[str]]:
    """Resolve the store-address line.

    Explicit store_address wins. Otherwise fall back to STORE_ADDRESS_SEEDS on a
    retailer:city key when exactly one seed matches the retailer; else no address line.
    """
    warnings: list[str] = []
    if store_address:
        return store_address, warnings
    prefix = f"{retailer_key}:"
    seeds = [v for k, v in STORE_ADDRESS_SEEDS.items() if k.startswith(prefix)]
    if len(seeds) == 1:
        return seeds[0], warnings
    if len(seeds) > 1:
        warnings.append(
            f"multiple seed addresses for {retailer_key!r}; pass store_address to disambiguate"
        )
        return None, warnings
    # no seed for this retailer — legitimate, just no address line
    return None, warnings


def _rasterize_svg(svg_path: Path, target_w: int) -> Image.Image | None:
    """Rasterize an SVG to RGBA at target width — only if cairosvg is already present.

    Returns None (never raises) when cairosvg is not importable or the render fails.
    cairosvg is deliberately NOT a dependency; this path is opportunistic.
    """
    try:
        import cairosvg  # type: ignore  # noqa: PLC0415 — optional, opportunistic import
    except ImportError:
        return None
    try:
        import io

        png_bytes = cairosvg.svg2png(url=str(svg_path), output_width=target_w)
        return Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    except Exception:  # noqa: BLE001 — any render failure falls through to PNG/text
        return None


def _load_logo(retailer: RetailerLogo, target_w: int) -> tuple[Image.Image | None, str, list[str]]:
    """Return (logo RGBA or None, logo_source label, warnings).

    logo_source is one of: svg | png | none. warnings capture missing/unusable assets.
    """
    warnings: list[str] = []

    if retailer.svg_exists:
        rendered = _rasterize_svg(retailer.svg_path, target_w)
        if rendered is not None:
            return rendered, "svg", warnings
        warnings.append(
            f"SVG present at {retailer.svg_path} but cairosvg is unavailable to "
            "rasterize it (not a project dep — Pillow cannot render SVG); "
            "falling back to PNG or text band"
        )

    if retailer.png_exists:
        try:
            logo = Image.open(retailer.png_path).convert("RGBA")
            return logo, "png", warnings
        except Exception as e:  # noqa: BLE001
            warnings.append(f"PNG at {retailer.png_path} unreadable ({e}); using text band")

    # nothing usable — the graceful-degradation path
    warnings.append(
        f"real logo asset MISSING for {retailer.name!r} — drop the vector at "
        f"{retailer.svg_path} (input_assets/retailer-logos/{retailer.name}.svg); "
        "composing a text-only lockup band as graceful degradation"
    )
    return None, "none", warnings


def _band_metrics(canvas_h: int) -> tuple[int, int, int]:
    """Return (band_height, name_font_px, addr_font_px) scaled to the canvas."""
    band_h = max(120, int(canvas_h * 0.16))
    name_px = max(28, int(band_h * 0.34))
    addr_px = max(20, int(band_h * 0.20))
    return band_h, name_px, addr_px


def compose_retailer_lockup(
    base_image: Path | str,
    retailer: str,
    *,
    store_address: str | None = None,
    out: Path | str | None = None,
    position: str = "bottom",
    logo_dir: Path | None = None,
) -> dict:
    """Composite a retailer lockup (logo + local store address) onto a base image.

    This is the cr-1 carve-out: the ONLY operation in the pipeline permitted to bake
    text (the store address) into an image. Everything else stays text-free.

    Flow:
      1. resolve_retailer() -> RetailerLogo. If store_address is None, fall back to
         STORE_ADDRESS_SEEDS by a retailer:city key when derivable, else no address.
      2. Composite the logo at `position` (default bottom band). SVG preferred and
         rasterized only if cairosvg is already importable; else PNG fallback; else a
         clean text-only band (retailer name + address) as graceful degradation.
      3. iso-name the output via naming.build_iso_name (channel "retailer-lockup").

    Returns dict: out_path, retailer, store_address, logo_source, warnings.
    """
    if position not in _POSITIONS:
        raise ValueError(f"unknown position {position!r}; expected one of {sorted(_POSITIONS)}")

    base_image = Path(base_image)
    if not base_image.exists():
        raise FileNotFoundError(f"base image not found: {base_image}")

    # 1. resolve retailer (raises cleanly on unknown retailer)
    key = normalize_retailer(retailer)
    address, warnings = _seed_address(key, store_address) if key else (store_address, [])
    resolved = resolve_retailer(retailer, store_address=address, logo_dir=logo_dir)

    base = Image.open(base_image).convert("RGBA")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")

    band_h, name_px, addr_px = _band_metrics(H)
    band_top = 0 if position == "top" else H - band_h
    band_bot = band_h if position == "top" else H

    # 2. resolve the logo mark (svg | png | none) — target width ~ 46% of canvas
    logo, logo_source, load_warnings = _load_logo(resolved, target_w=int(W * 0.46))
    warnings.extend(resolved.notes)
    warnings.extend(load_warnings)

    # scrim band behind whatever we place, for legibility on any base image
    draw.rectangle([0, band_top, W, band_bot], fill=(*_hex(_BAND_BG), 235))
    # blaze-orange hairline echoing the brand accent bar
    accent_y = band_bot - 6 if position == "bottom" else band_top
    draw.rectangle([0, accent_y, W, accent_y + 6], fill=(*_hex(_BAND_ACCENT), 255))

    pad = max(24, int(W * 0.03))

    if logo is not None:
        # scale logo to fit the band height (leave vertical breathing room)
        max_logo_h = int(band_h * 0.62)
        if logo.height > max_logo_h:
            scale = max_logo_h / logo.height
            logo = logo.resize((max(1, int(logo.width * scale)), max_logo_h), Image.BICUBIC)
        logo_y = band_top + (band_h - logo.height) // 2
        canvas.alpha_composite(logo, (pad, logo_y))
        # address text sits to the right of the logo when present
        addr_x = pad + logo.width + pad
        addr_font = _load_font(addr_px)
        if address:
            _draw_vcentered(draw, address, addr_font, addr_x, band_top, band_h, W - pad)
    else:
        # graceful degradation: text-only band — retailer NAME + address (cr-1 carve-out)
        name_font = _load_font(name_px)
        addr_font = _load_font(addr_px)
        name_text = resolved.name.upper()
        if address:
            name_y = band_top + int(band_h * 0.18)
            draw.text((pad, name_y), name_text, fill=_hex(_BAND_TEXT), font=name_font)
            addr_y = band_top + int(band_h * 0.56)
            draw.text((pad, addr_y), address, fill=_hex(_BAND_TEXT), font=addr_font)
        else:
            _draw_vcentered(draw, name_text, name_font, pad, band_top, band_h, W - pad)

    # 3. iso-name the output
    if out is None:
        name = build_iso_name(
            product="retailer-lockup",
            region="US",
            locality=resolved.name,
            channel="retailer-lockup",
            ratio=_nearest_ratio(W, H),
        )
        out_path = base_image.parent / name
    else:
        out_path = Path(out)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG")

    return {
        "out_path": out_path,
        "retailer": resolved.name,
        "store_address": address,
        "logo_source": logo_source,
        "warnings": warnings,
    }


def _draw_vcentered(draw, text, font, x, band_top, band_h, max_x) -> None:
    """Draw text vertically centered in the band, clipped to max_x horizontally."""
    bbox = draw.textbbox((0, 0), text, font=font)
    th = bbox[3] - bbox[1]
    y = band_top + (band_h - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=_hex(_BAND_TEXT), font=font)


def _nearest_ratio(w: int, h: int) -> str:
    """Map a pixel size to the closest canonical ratio token for iso-naming."""
    ar = w / h if h else 1.0
    candidates = {"1x1": 1.0, "9x16": 9 / 16, "16x9": 16 / 9}
    return min(candidates, key=lambda k: abs(candidates[k] - ar))
