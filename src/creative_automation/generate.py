"""Hero image generation — Nova Pro asset-driven composition with local mock fallback.

Precedence (see generate_hero): a real product source asset composed on a brand
background, captioned by Nova Pro (Converse, us-east-1), else a deterministic mock.
Nova Canvas is retired (provider-marked Legacy) and is not an invocation path.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

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


def _mock_hero(product_name: str, brief_msg: str, region: str, out_path: Path, idx: int = 0) -> Path:
    """Generate a deterministic placeholder hero image (1024x1024). Last resort."""
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

    sub = f"{region}  ·  mock hero  ·  {brief_msg[:40]}"
    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((W - tw2) / 2, H * 0.76), sub, fill=(255, 255, 255, 200), font=font_small)

    draw.text((20, H - 40), "MOCK — no real source asset / Nova Pro unavailable", fill=(255, 255, 255, 120), font=font_small)

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


def _compose_hero(
    src: Path, caption: str, region: str, out_path: Path, idx: int = 0
) -> Path:
    """Place the real product image on a brand-palette background with negative space."""
    W, H = 1024, 1024
    bg_hex, accent_hex = MOCK_PALETTES[idx % len(MOCK_PALETTES)]
    bg = _hex_to_rgb(bg_hex)
    accent = _hex_to_rgb(accent_hex)
    headline, side = _parse_layout(caption)

    canvas = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(canvas)

    # subtle accent band behind the product for depth
    draw.ellipse([W * 0.10, H * 0.08, W * 0.90, H * 0.72], fill=accent)

    # load + fit the real product image into ~62% of the frame, preserving aspect
    product = Image.open(src).convert("RGBA")
    box = int(min(W, H) * 0.62)
    product.thumbnail((box, box), Image.LANCZOS)
    pw, ph = product.size

    # negative space: product hugs the side Nova Pro picked, text takes the rest
    if side == "left":
        px = int(W * 0.55) + (box - pw) // 2
    elif side == "right":
        px = int(W * 0.10) + (box - pw) // 2
    else:
        px = (W - pw) // 2
    py = int(H * 0.14) + (box - ph) // 2
    canvas.paste(product, (px, py), product)

    if headline:
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
        except Exception:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0, 0), headline, font=font)
        tw = bbox[2] - bbox[0]
        tx = (W - tw) / 2 if side == "center" else (W * 0.06 if side == "right" else W * 0.94 - tw)
        draw.text((tx, H * 0.80), headline, fill="white", font=font)

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
) -> tuple[Path, str]:
    """Generate hero image. Returns (path, source).

    Precedence:
    1. real source asset found + Nova Pro composes -> "bedrock:nova-pro"
       (a Nova Pro call failure still composes on the real asset with an empty
        caption, so a located asset never silently degrades to a mock)
    2. no real asset located OR compose raises -> "mock"
    """
    src = _find_source_asset(product_id, product_name)
    if src is not None and src.exists():
        try:
            caption = _nova_pro_caption(src, product_name, brief_msg, region, audience) or ""
            result = _compose_hero(src, caption, region, out_path, idx)
            if result.exists():
                return result, "bedrock:nova-pro"
        except Exception as e:  # noqa: BLE001 — compose failure falls through to mock
            print(f"[generate] hero compose failed, falling back to mock: {e}", file=sys.stderr)

    mock_path = _mock_hero(product_name, brief_msg, region, out_path, idx)
    return mock_path, "mock"
