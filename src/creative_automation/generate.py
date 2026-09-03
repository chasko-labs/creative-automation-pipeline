"""Hero image generation — Bedrock Nova Canvas with local mock fallback."""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

# Attempt boto3 import lazily
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None  # type: ignore


NOVA_CANVAS_MODEL = os.getenv("BEDROCK_NOVA_CANVAS_MODEL", "amazon.nova-canvas-v1:0")
BEDROCK_REGION = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))

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


def _mock_hero(product_name: str, brief_msg: str, region: str, out_path: Path, idx: int = 0) -> Path:
    """Generate a deterministic placeholder hero image (1024x1024)."""
    W, H = 1024, 1024
    bg_hex, accent_hex = MOCK_PALETTES[idx % len(MOCK_PALETTES)]

    def hex_to_rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))

    bg = hex_to_rgb(bg_hex)
    accent = hex_to_rgb(accent_hex)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # accent circle
    draw.ellipse([W * 0.15, H * 0.12, W * 0.85, H * 0.62], fill=accent)

    # try font
    try:
        # Use default; DejaVu likely available
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # product name centered
    text = product_name[:32]
    bbox = draw.textbbox((0, 0), text, font=font_big)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, H * 0.68), text, fill="white", font=font_big)

    sub = f"{region}  ·  mock hero  ·  {brief_msg[:40]}"
    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((W - tw2) / 2, H * 0.76), sub, fill=(255, 255, 255, 200), font=font_small)

    # watermark for mock
    draw.text((20, H - 40), "MOCK — replace with Nova Canvas when AWS creds available", fill=(255, 255, 255, 120), font=font_small)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def _try_bedrock_nova_canvas(prompt: str, out_path: Path, width: int = 1024, height: int = 1024) -> Optional[Path]:
    """Attempt Bedrock Nova Canvas invoke. Returns path on success, None on any failure."""
    if boto3 is None:
        return None
    # quick cred check
    if not os.getenv("AWS_PROFILE") and not os.getenv("AWS_ACCESS_KEY_ID"):
        # still try — boto may have SSO creds — but don't block
        pass
    try:
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        body = {
            "taskType": "TEXT_IMAGE",
            "textToImageParams": {"text": prompt},
            "imageGenerationConfig": {
                "width": width,
                "height": height,
                "numberOfImages": 1,
                "quality": "standard",
                "cfgScale": 7.5,
                "seed": 42,
            },
        }
        resp = client.invoke_model(
            modelId=NOVA_CANVAS_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(resp["body"].read())
        # Nova Canvas returns { images: [ base64 ] }
        images = payload.get("images") or []
        if not images:
            return None
        b64 = images[0]
        data = base64.b64decode(b64)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(data)
        return out_path
    except (ClientError, BotoCoreError, Exception) as e:
        # silent fallback — caller logs
        print(f"[generate] Bedrock Nova Canvas unavailable, falling back to mock: {e}", file=sys.stderr)
        return None


def generate_hero(
    product_id: str,
    product_name: str,
    brief_msg: str,
    region: str,
    audience: str,
    out_path: Path,
    idx: int = 0,
) -> tuple[Path, str]:
    """Generate hero image. Returns (path, source) where source is 'bedrock' or 'mock'."""
    prompt = (
        f"Premium studio hero image for consumer product '{product_name}' ({product_id}), "
        f"target audience: {audience}, region: {region}, campaign vibe: {brief_msg}. "
        "Clean background, soft studio lighting, centered product, negative space for text overlay, "
        "photorealistic, high detail, social ad ready, no text, no logo."
    )

    # try bedrock first
    result = _try_bedrock_nova_canvas(prompt, out_path)
    if result is not None and result.exists():
        return result, "bedrock:nova-canvas"

    # fallback
    mock_path = _mock_hero(product_name, brief_msg, region, out_path, idx)
    return mock_path, "mock"
