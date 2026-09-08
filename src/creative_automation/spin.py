"""Spin — asset-editing toolkit that frees real assets and re-spins them on-brand.

Three always-on operations Bryan wants for every campaign, each with PREDEFINED
Kodiak standards (not ad-hoc params):

1. remove_background — free the subject (the bear, the partner, the product) by
   removing ONLY distracting background so it can be re-spun. Modes:
     transparent | solid (Kodiak color) | image (provided background plate).
2. batch_crop — crop many files at once, subject-aware center, per platform ratio.
3. color_grade — named, reusable presets. Default applies only the GENTLEST kraft
   texture + a mild warm frontier tone.

Amazon-first: prefer Bedrock (Nova Canvas background removal / outpainting via
bedrock-runtime, Rekognition detect-labels for crop bounding boxes) when creds
present AND KODIAK_BEDROCK_EDIT=1. Graceful Pillow fallback keeps CI green offline.

HARD BRAND RULE: this toolkit never bakes text into images. Retailer-logo lockups
are a separate explicit operation (see retailers.py + compose retailer overlay).

All fallbacks are Pillow-only, deterministic, offline.
"""
from __future__ import annotations

import glob as _glob
import os
from pathlib import Path

from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

from .compose import CANONICAL, RATIOS
from .enhance import _hex, _kraft_texture

# Kodiak fill palette for solid background replacement — names map to brand tokens.
FILL_COLORS: dict[str, str] = {
    "bear-brown": "#3B2316",
    "frontier-green": "#1A3C34",
    "parchment": "#FFF8F0",
    "blaze-orange": "#E8530E",
}

# Named, reusable color-grade presets. Params are deliberately gentle — Kodiak
# imagery stays product-honest. texture_opacity feeds enhance._kraft_texture.
COLOR_GRADE_PRESETS: dict[str, dict[str, float | str]] = {
    # default — gentlest signature: faint kraft + mild warm frontier tone
    "kodiak-signature-gentle": {
        "contrast": 1.03,
        "brightness": 1.01,
        "color": 1.03,
        "warmth": 1.04,
        "texture_opacity": 0.04,
        "tint": "#3B2316",
        "tint_strength": 0.02,
    },
    # Wasatch dawn — cooler highlights, soft blue-hour lift, slightly airier
    "wasatch-dawn": {
        "contrast": 1.05,
        "brightness": 1.04,
        "color": 0.98,
        "warmth": 0.97,
        "texture_opacity": 0.03,
        "tint": "#1A3C34",
        "tint_strength": 0.03,
    },
    # trail-warm — pushed golden-hour warmth for outdoor / hero energy
    "trail-warm": {
        "contrast": 1.06,
        "brightness": 1.02,
        "color": 1.08,
        "warmth": 1.10,
        "texture_opacity": 0.05,
        "tint": "#E8530E",
        "tint_strength": 0.04,
    },
}

DEFAULT_PRESET = "kodiak-signature-gentle"
_ASSET_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


# ------------------------------------------------------------------ Bedrock gate
def _bedrock_edit_enabled() -> bool:
    """Opt-in Amazon edit path.

    Requires KODIAK_BEDROCK_EDIT=1 AND boto3 importable. Default off so CI (no
    creds) always takes the deterministic Pillow fallback and stays green.
    """
    if os.getenv("KODIAK_BEDROCK_EDIT") != "1":
        return False
    try:
        import boto3  # noqa: F401
    except ImportError:
        return False
    return True


def _bedrock_client(service: str = "bedrock-runtime"):
    try:
        import boto3

        region = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
        return boto3.client(service, region_name=region)
    except Exception as e:  # noqa: BLE001 — any failure falls back to Pillow
        print(f"[spin] bedrock client unavailable, using local fallback: {e}")
        return None


# ------------------------------------------------------------------ 1. background
def _subject_matte(img: Image.Image) -> Image.Image:
    """Offline subject-preserving matte — a deterministic Pillow fallback.

    Not a neural cutout. Estimates background as the dominant border color, then
    builds an alpha mask that keeps pixels differing from that border color.
    Frees the subject enough to re-spin without any third-party model. Distracting
    even-toned backgrounds (studio, sky, seamless) matte cleanly; busy scenes keep
    more, which is the safe direction (we do not want to erase the subject).
    """
    rgb = img.convert("RGB")
    w, h = rgb.size
    # sample border pixels to estimate background color
    px = rgb.load()
    step = max(1, min(w, h) // 64)
    samples: list[tuple[int, int, int]] = []
    for x in range(0, w, step):
        samples.append(px[x, 0])
        samples.append(px[x, h - 1])
    for y in range(0, h, step):
        samples.append(px[0, y])
        samples.append(px[w - 1, y])
    n = len(samples)
    br = sum(s[0] for s in samples) // n
    bg = sum(s[1] for s in samples) // n
    bb = sum(s[2] for s in samples) // n

    # per-pixel distance from background color -> grayscale, then threshold
    bg_plate = Image.new("RGB", (w, h), (br, bg, bb))
    diff = ImageChops.difference(rgb, bg_plate).convert("L")
    # normalize + threshold: pixels close to bg become transparent
    diff = ImageOps.autocontrast(diff, cutoff=1)
    thresh = 32
    mask = diff.point(lambda v: 255 if v > thresh else 0)
    # soften edges so the freed subject composites cleanly
    mask = mask.filter(ImageFilter.MaxFilter(3)).filter(ImageFilter.GaussianBlur(1.2))
    return mask


def _bedrock_remove_background(img: Image.Image) -> Image.Image | None:
    """Nova Canvas BACKGROUND_REMOVAL -> RGBA cutout. Returns None on any failure."""
    import base64
    import io
    import json

    client = _bedrock_client("bedrock-runtime")
    if client is None:
        return None
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        body = {
            "taskType": "BACKGROUND_REMOVAL",
            "backgroundRemovalParams": {"image": b64},
        }
        model_id = os.getenv("KODIAK_BEDROCK_IMAGE_MODEL", "amazon.nova-canvas-v1:0")
        resp = client.invoke_model(modelId=model_id, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        out_b64 = payload["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(out_b64))).convert("RGBA")
    except Exception as e:  # noqa: BLE001
        print(f"[spin] bedrock background removal failed, using local matte: {e}")
        return None


def remove_background(
    src: Path,
    mode: str = "transparent",
    *,
    fill: str = "parchment",
    bg_image: Path | None = None,
    out: Path | None = None,
) -> Path:
    """Free the subject by removing distracting background, then re-place it.

    mode:
      transparent — RGBA cutout on transparent canvas
      solid       — composite onto a Kodiak fill color (fill= name in FILL_COLORS or hex)
      image       — composite onto a provided background plate (bg_image=, e.g. Wasatch dawn)

    Bedrock (Nova Canvas) cutout when KODIAK_BEDROCK_EDIT=1 + creds, else Pillow matte.
    """
    if mode not in {"transparent", "solid", "image"}:
        raise ValueError(f"unknown mode {mode!r}; expected transparent|solid|image")
    out = out or src.with_suffix(".freed.png")

    img = Image.open(src).convert("RGBA")

    cutout: Image.Image | None = None
    if _bedrock_edit_enabled():
        cutout = _bedrock_remove_background(img)
    if cutout is None:
        mask = _subject_matte(img)
        cutout = img.copy()
        cutout.putalpha(mask)

    w, h = cutout.size
    if mode == "transparent":
        result = cutout
    elif mode == "solid":
        hexv = FILL_COLORS.get(fill, fill)
        plate = Image.new("RGBA", (w, h), (*_hex(hexv), 255))
        plate.alpha_composite(cutout)
        result = plate
    else:  # image
        if bg_image is None or not Path(bg_image).exists():
            raise ValueError("mode=image requires an existing bg_image path")
        plate = Image.open(bg_image).convert("RGBA")
        plate = ImageOps.fit(plate, (w, h), method=Image.BICUBIC, centering=(0.5, 0.5))
        plate.alpha_composite(cutout)
        result = plate

    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out, "PNG")
    return out


# ------------------------------------------------------------------ 2. batch crop
def _resolve_ratio(ratio_key: str) -> tuple[int, int]:
    key = CANONICAL.get(ratio_key, ratio_key)
    dims = RATIOS.get(key, RATIOS.get(ratio_key))
    if dims is None:
        raise ValueError(f"unknown ratio {ratio_key!r}; expected one of {sorted(CANONICAL)}")
    return dims


def _saliency_center(img: Image.Image) -> tuple[float, float]:
    """Center-weighted entropy centroid — the subject-aware focal point.

    Offline heuristic: high-detail regions (edges) pull the crop center toward the
    subject, biased gently to image center to avoid runaway crops on noisy borders.
    Returns (cx, cy) as 0..1 fractions.
    """
    gray = img.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    small = edges.resize((32, 32))
    px = small.load()
    total = 0.0
    sx = 0.0
    sy = 0.0
    for y in range(32):
        for x in range(32):
            wgt = px[x, y]
            total += wgt
            sx += wgt * x
            sy += wgt * y
    if total <= 0:
        return 0.5, 0.5
    cx = (sx / total) / 31.0
    cy = (sy / total) / 31.0
    # bias 60% toward detected centroid, 40% toward image center for stability
    cx = 0.6 * cx + 0.4 * 0.5
    cy = 0.6 * cy + 0.4 * 0.5
    return cx, cy


def _bedrock_subject_center(img: Image.Image) -> tuple[float, float] | None:
    """Rekognition detect-labels bounding box centroid. None on any failure."""
    import io

    client = _bedrock_client("rekognition")
    if client is None:
        return None
    try:
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG")
        resp = client.detect_labels(
            Image={"Bytes": buf.getvalue()}, MaxLabels=10, MinConfidence=70
        )
        boxes = [
            inst["BoundingBox"]
            for label in resp.get("Labels", [])
            for inst in label.get("Instances", [])
            if "BoundingBox" in inst
        ]
        if not boxes:
            return None
        # centroid of the largest box (dominant subject)
        big = max(boxes, key=lambda b: b["Width"] * b["Height"])
        cx = big["Left"] + big["Width"] / 2
        cy = big["Top"] + big["Height"] / 2
        return cx, cy
    except Exception as e:  # noqa: BLE001
        print(f"[spin] rekognition detect-labels failed, using local saliency: {e}")
        return None


def _iter_paths(paths_or_glob: str | Path | list) -> list[Path]:
    if isinstance(paths_or_glob, (str, Path)):
        p = Path(paths_or_glob)
        if p.is_dir():
            return sorted(f for f in p.iterdir() if f.suffix.lower() in _ASSET_EXTS)
        if any(ch in str(paths_or_glob) for ch in "*?[") or not p.exists():
            return sorted(Path(m) for m in _glob.glob(str(paths_or_glob)) if Path(m).suffix.lower() in _ASSET_EXTS)
        return [p]
    return [Path(x) for x in paths_or_glob]


def batch_crop(
    paths_or_glob: str | Path | list,
    ratios: list[str],
    out_dir: Path,
    *,
    subject_aware: bool = True,
) -> list[Path]:
    """Crop many files at once — subject-aware center, per target platform ratio.

    Outputs out_dir/<stem>.<ratio>.png at the exact token canvas dims for each ratio.
    Rekognition bounding boxes when KODIAK_BEDROCK_EDIT=1 + creds, else Pillow saliency.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    files = _iter_paths(paths_or_glob)
    for f in files:
        img = Image.open(f).convert("RGB")
        center = (0.5, 0.5)
        if subject_aware:
            center = None
            if _bedrock_edit_enabled():
                center = _bedrock_subject_center(img)
            if center is None:
                center = _saliency_center(img)
        for ratio in ratios:
            w, h = _resolve_ratio(ratio)
            key = CANONICAL.get(ratio, ratio)
            cropped = ImageOps.fit(img, (w, h), method=Image.BICUBIC, centering=center)
            dst = out_dir / f"{f.stem}.{key}.png"
            cropped.save(dst, "PNG")
            written.append(dst)
    return written


# ------------------------------------------------------------------ 3. color grade
def _warm(img: Image.Image, factor: float) -> Image.Image:
    """Shift white balance warmer (>1) or cooler (<1) via per-channel scaling."""
    if factor == 1.0:
        return img
    r, g, b, *rest = img.split()
    r = r.point(lambda v: min(255, int(v * factor)))
    b = b.point(lambda v: min(255, int(v / factor)))
    channels = [r, g, b] + rest
    return Image.merge(img.mode, channels)


def color_grade(
    src: Path,
    preset: str = DEFAULT_PRESET,
    *,
    out: Path | None = None,
) -> Path:
    """Apply a named, reusable Kodiak color-grade preset.

    Default 'kodiak-signature-gentle' applies only the gentlest kraft texture +
    mild warm frontier tone. No text is ever baked in.
    """
    if preset not in COLOR_GRADE_PRESETS:
        raise ValueError(
            f"unknown preset {preset!r}; expected one of {sorted(COLOR_GRADE_PRESETS)}"
        )
    p = COLOR_GRADE_PRESETS[preset]
    out = out or src.with_suffix(f".{preset}.png")

    img = Image.open(src).convert("RGBA")
    img = ImageEnhance.Contrast(img).enhance(float(p["contrast"]))
    img = ImageEnhance.Brightness(img).enhance(float(p["brightness"]))
    img = ImageEnhance.Color(img).enhance(float(p["color"]))
    img = _warm(img, float(p["warmth"]))

    # gentle brand tint wash
    ts = float(p["tint_strength"])
    if ts > 0:
        tint = Image.new("RGBA", img.size, (*_hex(str(p["tint"])), int(255 * ts)))
        img = Image.alpha_composite(img, tint)

    # signature kraft texture at preset opacity (reuses enhance._kraft_texture)
    tex = _kraft_texture(img.size, opacity=float(p["texture_opacity"]))
    img = Image.alpha_composite(img, tex)

    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out


# ------------------------------------------------------------------ convenience
def spin_asset(
    src: Path,
    *,
    ratio: str = "1x1",
    bg_mode: str = "transparent",
    fill: str = "parchment",
    bg_image: Path | None = None,
    preset: str = DEFAULT_PRESET,
    out_dir: Path | None = None,
) -> Path:
    """Chain free-subject -> crop -> grade for a single platform ratio.

    Returns the final graded path. Intermediate freed/cropped files land in out_dir
    (or a .spin sibling dir) so the chain is inspectable.
    """
    src = Path(src)
    out_dir = Path(out_dir) if out_dir else src.parent / ".spin"
    out_dir.mkdir(parents=True, exist_ok=True)

    freed = remove_background(
        src, bg_mode, fill=fill, bg_image=bg_image, out=out_dir / f"{src.stem}.freed.png"
    )
    cropped = batch_crop(freed, [ratio], out_dir)[0]
    key = CANONICAL.get(ratio, ratio)
    graded = color_grade(cropped, preset, out=out_dir / f"{src.stem}.{key}.{preset}.png")
    return graded
