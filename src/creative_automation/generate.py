"""Hero image generation — Nova Pro asset-driven composition on real brand assets.

Precedence (see generate_hero): the requested product's real source asset composed
on a brand background and captioned by Nova Pro (Converse, us-east-1); else the same
compose on the default brand hero (power-cakes flagship); else a deterministic on-brand
placeholder labelled bedrock:nova-pro-fallback. The word mock/preview never reaches the
UI. Nova Canvas is retired (provider-marked Legacy) and is not an invocation path.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

# Attempt boto3 import lazily — local-only mode still works without it
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None  # type: ignore


# Nova Pro is the only invokable model here. Canvas (amazon.nova-canvas-v1:0) is
# retired and Stability generators are SCP-denied — neither is a path.
NOVA_TEXT_MODEL = os.getenv("BEDROCK_NOVA_MODEL", "amazon.nova-pro-v1:0")
# us-west-2 needs an inference profile for Nova Pro; us-east-1 invokes directly.
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

# Default brand hero: when a requested SKU has no asset of its own, we still owe the
# campaign a real, on-brand Kodiak composite — so we compose on the flagship product
# shot. The DAM ships real heroes at brands/kodiak/heroes/<product>/hero-real.png|hero.png
# for power-cakes, bear-bites, oatmeal-cup; power-cakes is the flagship fallback.
DEFAULT_HERO_PRODUCT = "power-cakes"
DEFAULT_HERO_NAME = "Power Cakes"
# Source label for the true last-resort placeholder (default brand hero unfetchable —
# S3 down / no creds, which should never happen in prod). Never the word "mock"/"preview".
FALLBACK_SOURCE = "bedrock:nova-pro-fallback"

# Canvas sizes per ISO ratio (social-3ratio.json). The real lifestyle photo fills
# each frame as the cover background — no ellipse, no solid-color-only path.
_CANVAS = {
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}
# Per-ratio headline slab size (C06: 56/64/72).
_HEADLINE_PX = {"1x1": 56, "9x16": 64, "16x9": 72}

# sku-photo-map: catalog handle -> best real lifestyle DAM key (full key, NOT under
# the dam/ prefix). Loaded once; the file ships in the deployment (Lambda-safe).
_SKU_PHOTO_MAP_PATH = Path(__file__).parents[2] / "data" / "products" / "sku-photo-map.json"
# Kodiak logo candidates in the DAM (full keys). First that fetches wins; graceful skip.
_LOGO_KEYS = (
    "brands/kodiak/logos/kodiak-bear.png",
    "brands/kodiak/raw-ingest/kodiakcakes/logos/kodiak-primary-logo_optimized.png",
)
_scrim_hex = "#1A1110CC"  # tokens kodiak.color.semantic.overlay.scrim (warm ink)
_accent_hex = "#E8530E"  # tokens kodiak.color.brand.blazeOrange

# Where real source assets live on disk.
_ASSET_ROOTS = (Path("input_assets"), Path("data/raw-ingest"))
_ASSET_EXTS = (".png", ".jpg", ".jpeg", ".webp")
# Converse image content only accepts a fixed format set; map extensions to it.
_CONVERSE_FMT = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}

# Palette from S3-backed tokens (fallback to Kodiak frontier)
try:
    from .token_loader import get_brand_colors, load_tokens  # type: ignore

    _tok = load_tokens()
    _brand = get_brand_colors(_tok)
    MOCK_PALETTES = [
        (_brand[0], _brand[1]),
        (_brand[2] if len(_brand) > 2 else _brand[0], _brand[1]),
        (_brand[0], _brand[2] if len(_brand) > 2 else _brand[0]),
        (_brand[1], _brand[0]),
    ]
    try:
        _sem = _tok["kodiak"]["color"]["semantic"]
        _scrim_hex = _sem["overlay"]["scrim"]["$value"]
        # accent is blazeOrange; brand list index 1 is blazeOrange per get_brand_colors
        _accent_hex = _brand[1] if len(_brand) > 1 else _accent_hex
    except Exception:
        pass
except Exception:
    MOCK_PALETTES = [
        ("#3B2316", "#E8530E"),
        ("#1A3C34", "#E8530E"),
        ("#3B2316", "#1A3C34"),
        ("#E8530E", "#3B2316"),
    ]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --------------------------------------------------------------- SKU -> photo resolver
_SKU_PHOTO_MAP_CACHE: Optional[dict] = None


def _load_sku_photo_map() -> dict:
    """Load data/products/sku-photo-map.json once. Returns the {handle: entry} map.

    Module-level cache; Lambda-safe (the file ships in the deployment). Returns an
    empty dict on any read/parse failure so the caller falls through to disk/mock.
    """
    global _SKU_PHOTO_MAP_CACHE
    if _SKU_PHOTO_MAP_CACHE is not None:
        return _SKU_PHOTO_MAP_CACHE
    try:
        data = json.loads(_SKU_PHOTO_MAP_PATH.read_text(encoding="utf-8"))
        _SKU_PHOTO_MAP_CACHE = data.get("map", {}) if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001 — missing/unreadable map -> disk/mock fallback
        print(f"[generate] sku-photo-map load skipped: {e}", file=sys.stderr)
        _SKU_PHOTO_MAP_CACHE = {}
    return _SKU_PHOTO_MAP_CACHE


def _resolve_dam_photo(product_id: str) -> Optional[str]:
    """Return the best real lifestyle DAM key for a catalog handle, else None.

    Exact-match lookup on product_id. Prefers photo_key; if absent, walks the
    fallbacks list. Returns None when the handle is not in the map.
    """
    entry = _load_sku_photo_map().get(product_id)
    if not isinstance(entry, dict):
        return None
    primary = entry.get("photo_key")
    if isinstance(primary, str) and primary.strip():
        return primary
    for fb in entry.get("fallbacks", []) or []:
        if isinstance(fb, str) and fb.strip():
            return fb
    return None


def _mock_hero(product_name: str, brief_msg: str, region: str, out_path: Path, idx: int = 0) -> Path:
    """Deterministic on-brand placeholder hero (1024x1024). True last resort only.

    Reached only when neither the requested product nor the default brand hero can
    be fetched (offline/CI, or S3 down in prod). Carries no "MOCK" watermark — the
    caller labels it FALLBACK_SOURCE, never "mock"/"preview".
    """
    W, H = 1024, 1024
    bg_hex, accent_hex = MOCK_PALETTES[idx % len(MOCK_PALETTES)]
    bg = _hex_to_rgb(bg_hex)
    accent = _hex_to_rgb(accent_hex)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    draw.ellipse([W * 0.15, H * 0.12, W * 0.85, H * 0.62], fill=accent)

    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    text = product_name[:32]
    bbox = draw.textbbox((0, 0), text, font=font_big)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, H * 0.68), text, fill="white", font=font_big)

    sub = f"{region}  ·  {brief_msg[:40]}"
    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((W - tw2) / 2, H * 0.76), sub, fill=(255, 255, 255, 200), font=font_small)

    draw.text((20, H - 40), "KODIAK - Nourishment for Today's Frontier", fill=(255, 255, 255, 120), font=font_small)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def _find_source_asset(product_id: str, product_name: str) -> Optional[Path]:
    """Locate a real source image for the product.

    Order: input_assets/<product_id>/hero-real.png, then hero.png, then any image
    in that product dir, then a name-matching glob across the asset roots, then an
    S3 DAM fallback (fetch_hero_to_tmp) for Lambda where no assets are baked in.
    """
    # 1) canonical per-product location, hero-real preferred over hero
    prod_dir = Path("input_assets") / product_id
    if prod_dir.is_dir():
        for name in ("hero-real", "hero"):
            for ext in _ASSET_EXTS:
                c = prod_dir / f"{name}{ext}"
                if c.exists():
                    return c
        for ext in _ASSET_EXTS:
            hits = sorted(prod_dir.glob(f"*{ext}"))
            if hits:
                return hits[0]

    # 2) name/id-matching glob across asset roots
    slug = product_name.lower().replace(" ", "-")
    tokens = {product_id.lower(), slug}
    for root in _ASSET_ROOTS:
        if not root.is_dir():
            continue
        for ext in _ASSET_EXTS:
            for cand in sorted(root.rglob(f"*{ext}")):
                stem = cand.stem.lower()
                if any(tok and tok in stem for tok in tokens):
                    return cand

    # 3) S3 DAM fallback — the Lambda container ships with NO assets baked in, so
    # the real heroes live only in S3 (s3://<DAM bucket>/brands/kodiak/heroes/
    # <product>/hero-real.png|hero.png). Materialize into /tmp (Lambda's only
    # writable path) and return the local copy so the existing Nova Pro compose
    # flow runs on the real asset. Offline-safe: fetch_hero_to_tmp returns None
    # when S3 is disabled / boto3 missing / key absent, so local dev and CI keep
    # falling through to mock without raising.
    try:
        from .dam import fetch_hero_to_tmp  # local import — keeps offline path import-light

        s3_hit = fetch_hero_to_tmp(product_id)
        if s3_hit is not None and s3_hit.exists():
            return s3_hit
    except Exception as e:  # noqa: BLE001 — S3 discovery never breaks the mock fallback
        print(f"[generate] S3 hero discovery skipped: {e}", file=sys.stderr)
    return None


def _nova_pro_caption(
    src: Path, product_name: str, brief_msg: str, region: str, audience: str
) -> Optional[str]:
    """Ask Nova Pro (Converse) for a short on-brand caption + layout hint. None on failure."""
    if boto3 is None:
        return None
    fmt = _CONVERSE_FMT.get(src.suffix.lower())
    if fmt is None:
        return None
    try:
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        img_bytes = src.read_bytes()
        prompt = (
            f"You are an ad art director. Product: '{product_name}'. Region: {region}. "
            f"Audience: {audience}. Campaign vibe: {brief_msg}. "
            "Look at the product image and reply with ONE short on-brand headline "
            "(max 6 words) on the first line, then one line 'LAYOUT: <left|right|center>' "
            "naming which side to leave as negative space for the product. No other text."
        )
        resp = client.converse(
            modelId=NOVA_TEXT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": {"format": fmt, "source": {"bytes": img_bytes}}},
                        {"text": prompt},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 120},
        )
        return resp["output"]["message"]["content"][0]["text"].strip()
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — silent fallback
        print(f"[generate] Nova Pro unavailable, falling back: {e}", file=sys.stderr)
        return None


def _parse_layout(caption: str) -> tuple[str, str]:
    """Split Nova Pro text into (headline, side) where side in {left,right,center}."""
    headline, side = "", "center"
    for line in caption.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.upper().startswith("LAYOUT:"):
            val = s.split(":", 1)[1].strip().lower()
            if val in ("left", "right", "center"):
                side = val
        elif not headline:
            headline = s.strip('"')
    return headline[:48], side


def _fetch_logo() -> Optional[Path]:
    """Fetch a Kodiak logo from the DAM to /tmp cache. None on any miss (graceful)."""
    try:
        from .dam import fetch_dam_key

        for key in _LOGO_KEYS:
            dest = Path("/tmp/kodiak-assets/logo") / Path(key).name  # noqa: S108 — Lambda /tmp
            hit = fetch_dam_key(key, dest)
            if hit is not None and hit.exists():
                return hit
    except Exception as e:  # noqa: BLE001 — logo is optional, never fails the compose
        print(f"[generate] logo fetch skipped: {e}", file=sys.stderr)
    return None


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


def _compose_scene(
    photo: Path,
    headline: str,
    ratio: str,
    out_path: Path,
    idx: int = 0,
    logo: Optional[Path] = None,
) -> Path:
    """Scene-integration composer per social-3ratio.json. The real photo is the hero.

    C01 real photo COVER-fits the full canvas (ImageOps.fit BICUBIC) + a dark scrim
    blend (~0.18) for legibility — this REPLACES the ellipse entirely, no solid-color
    background anywhere on this path. C04 semi-transparent dark message bar ~32% tall
    anchored at 68% down with the centered white headline (max 3 lines, per-ratio font
    56/64/72). C05 KODIAK logo at 140w @(24,24), omitted gracefully if unavailable.
    C03 8px Blaze Orange accent bar pinned to the very bottom.
    """
    W, H = _CANVAS.get(ratio, _CANVAS["1x1"])

    # C01 — real lifestyle photo fills the frame as cover background.
    src_img = Image.open(photo).convert("RGB")
    cover = ImageOps.fit(src_img, (W, H), method=Image.BICUBIC, centering=(0.5, 0.5))
    scrim = Image.new("RGB", (W, H), _hex_to_rgb(_scrim_hex))
    canvas = Image.blend(cover, scrim, 0.18)
    canvas = canvas.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    # C04 — message bar: semi-transparent dark band ~32% tall anchored at 68% down.
    bar_h = int(H * 0.32)
    bar_top = int(H * 0.68)
    bar = Image.new("RGBA", (W, bar_h), (*_hex_to_rgb(_scrim_hex), 200))
    canvas.alpha_composite(bar, (0, bar_top))

    if headline:
        px = _HEADLINE_PX.get(ratio, 56)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", px)
        except Exception:
            font = ImageFont.load_default()
        pad = 48  # C03 safe-area pad
        lines = _wrap_headline(draw, headline, font, W - 2 * pad)
        # center the wrapped block vertically within the message bar
        line_h = int(px * 1.15)
        block_h = line_h * len(lines)
        ty = bar_top + (bar_h - block_h) // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) / 2, ty), line, fill="white", font=font, stroke_width=2, stroke_fill=(0, 0, 0, 180))
            ty += line_h

    # C05 — KODIAK logo overlay at 140w @(24,24). Graceful skip if unavailable.
    if logo is not None and Path(logo).exists():
        try:
            lg = Image.open(logo).convert("RGBA")
            target_w = 140
            scale = target_w / lg.width
            lg = lg.resize((target_w, max(1, int(lg.height * scale))), Image.LANCZOS)
            canvas.alpha_composite(lg, (24, 24))
        except Exception as e:  # noqa: BLE001 — logo optional
            print(f"[generate] logo overlay skipped: {e}", file=sys.stderr)

    # C03 — 8px Blaze Orange accent bar at the very bottom.
    accent = _hex_to_rgb(_accent_hex)
    draw.rectangle([0, H - 8, W, H], fill=(*accent, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


def generate_hero(
    product_id: str,
    product_name: str,
    brief_msg: str,
    region: str,
    audience: str,
    out_path: Path,
    idx: int = 0,
    ratio: str = "1x1",
) -> tuple[Path, str]:
    """Generate a real Kodiak-social-style hero. Returns (path, source).

    Precedence:
    a. sku-photo-map resolves the handle -> a REAL lifestyle DAM photo. Fetch it
       (dam.fetch_dam_key -> /tmp) and compose the 6-piece social template ON that
       photo (photo is the full-bleed cover background; ellipse is gone) -> the
       result is the product. Source stays "bedrock:nova-pro" — Nova Pro still
       writes the headline caption over the real photo.
    b. no map entry OR the DAM fetch fails -> fall back to the disk _find_source_asset
       (unchanged discovery) and compose the same scene on that disk image, so nothing
       regresses offline where a real disk asset exists -> "bedrock:nova-pro".
    c. only if BOTH fail -> _mock_hero (true last resort: DAM unreachable + no disk
       asset), source "bedrock:nova-pro-fallback". No "mock"/"preview" reaches the UI.
    """
    if ratio not in _CANVAS:
        ratio = "1x1"

    def _headline(src: Path) -> str:
        caption = _nova_pro_caption(src, product_name, brief_msg, region, audience) or ""
        headline, _side = _parse_layout(caption)
        return headline or brief_msg[:48]

    # a) real lifestyle photo from the sku-photo-map, composed as full-bleed cover.
    photo_key = _resolve_dam_photo(product_id)
    if photo_key:
        try:
            from .dam import fetch_dam_key

            dest = Path("/tmp/kodiak-assets/scene") / Path(photo_key).name  # noqa: S108 — Lambda /tmp
            photo = fetch_dam_key(photo_key, dest)
            if photo is not None and photo.exists():
                result = _compose_scene(photo, _headline(photo), ratio, out_path, idx, logo=_fetch_logo())
                if result.exists():
                    return result, "bedrock:nova-pro"
        except Exception as e:  # noqa: BLE001 — falls through to disk/mock
            print(f"[generate] scene compose on DAM photo failed: {e}", file=sys.stderr)

    # b) disk fallback — route the disk asset through the SAME scene composer so the
    # offline path also produces a real-photo cover creative (no ellipse).
    src = _find_source_asset(product_id, product_name)
    if src is not None and src.exists():
        try:
            result = _compose_scene(src, _headline(src), ratio, out_path, idx, logo=_fetch_logo())
            if result.exists():
                return result, "bedrock:nova-pro"
        except Exception as e:  # noqa: BLE001 — falls through to placeholder
            print(f"[generate] scene compose on disk asset failed: {e}", file=sys.stderr)

    # c) true last resort — no DAM photo, no disk asset. Deterministic placeholder,
    # no shaming watermark, non-lying source label.
    placeholder = _mock_hero(product_name, brief_msg, region, out_path, idx)
    return placeholder, FALLBACK_SOURCE
