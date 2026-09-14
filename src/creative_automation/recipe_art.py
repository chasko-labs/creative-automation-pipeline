"""Recipe-art generator — hand-drawn ink line-art for the recipe-card sketch zones.

The recipe card carries three art zones (raw_ingredient, technique, finished_plate)
that must render as HAND-DRAWN line-art illustrations, NOT photography and NOT the
hardcoded SVG placeholders. Stability Stable Image Core (stability.stable-image-core-v1:1)
in us-west-2 produces the deep-brown-ink-on-white look the card's production_specs
require. Stable Image Core has no style field, so the line-art directive is baked into
the prompt text ("hand-drawn ink line-art ... deep brown ink on white ... minimal line
drawing"); ink coverage <= 0.35.

Reuses spin._bedrock_client so there is one Bedrock client factory in the codebase.
Stable Image Core ON_DEMAND lives in us-west-2, so the client is forced to that region
via the region kwarg regardless of BEDROCK_REGION (which the DAM path may set to
us-east-1). Image generation can exceed the default 60s socket read, so the client is
built with read_timeout=300.

PRODUCTION-SPECS GATE: a render occasionally comes back heavy/shaded. After decoding we
measure dark-pixel coverage (luminance < 0.5) and reject anything over the 0.37 ceiling
(0.35 spec + 0.02 template tolerance), retrying once with a stronger negative prompt and
seed+1. A still-too-heavy render returns None rather than shipping a shaded block dressed
as a sketch — the frontend then falls back to its SVG placeholder.

Offline / no-creds safe: _bedrock_client returns None without credentials, so
generate_recipe_art returns None and logs a [recipe-art] line, never crashing.
"""
from __future__ import annotations

import base64
import io
import json
import os
import re
from pathlib import Path

from PIL import Image

from .spin import _bedrock_client

# zones the card exposes; geometry note only — aspect ratio chosen below.
ZONES = ("raw_ingredient", "technique", "finished_plate")

# Stable Image Core takes an aspect_ratio string (NOT width/height) from a fixed enum
# (16:9, 1:1, 21:9, 2:3, 3:2, 4:5, 5:4, 9:16, 9:21) — 2:1 is NOT valid and returns a
# ValidationException. raw_ingredient/technique zones are 3.0x1.5in (2:1 print box) so
# we render at 16:9 (1.78, nearest valid landscape) and CSS crops to the zone box at
# print; finished_plate is 3.0x2.0in and renders at 3:2 exactly.
_ZONE_ASPECT: dict[str, str] = {
    "raw_ingredient": "16:9",
    "technique": "16:9",
    "finished_plate": "3:2",
}

# deep-brown ink line-art prompts, one per zone. subject is the in-season ingredient.
_ZONE_PROMPT: dict[str, str] = {
    "raw_ingredient": (
        "hand-drawn ink line-art illustration of raw {subject}, loose organic contour "
        "lines, fine cross-hatching and stippling for texture, deep brown ink on white, "
        "botanical sketch style, minimal, uncolored, printer-friendly line drawing"
    ),
    "technique": (
        "hand-drawn ink line-art illustration showing the cooking technique for a "
        "{subject} recipe, kitchen action sketch, loose contour lines, deep brown ink on "
        "white, minimal line drawing, printer-friendly"
    ),
    "finished_plate": (
        "hand-drawn ink line-art illustration of a finished plated dish featuring "
        "{subject} over pancakes, appetizing composition, loose contour lines and light "
        "hatching, deep brown ink on white, minimal line drawing, printer-friendly"
    ),
}

_NEGATIVE_BASE = (
    "photograph, photorealistic, color photo, shading, gradient, solid fill, dark "
    "background, drop shadow, 3d render, watermark, text, words, lettering"
)
# retry after a coverage rejection pushes harder against heavy ink / dark masses
_NEGATIVE_STRONG = (
    _NEGATIVE_BASE
    + ", heavy ink, dense hatching, black fill, filled silhouette, high contrast, "
    "muddy, blotchy, dark shading, ink wash, painted"
)

MODEL_ID = os.getenv("KODIAK_BEDROCK_IMAGE_MODEL", "stability.stable-image-core-v1:1")
# Stable Image Core ON_DEMAND lives in us-west-2, not us-east-1. Force it regardless
# of BEDROCK_REGION so the DAM path setting us-east-1 does not break recipe art.
IMAGE_REGION = os.getenv("KODIAK_BEDROCK_IMAGE_REGION", "us-west-2")
DEFAULT_OUT_ROOT = Path(__file__).parents[2] / "output" / "recipe-art"

# production_specs.ink_coverage_ceiling (0.35) + tolerance (0.02) from recipe-card.json
_COVERAGE_CEILING = 0.37
# luminance below this counts as "dark ink" for the coverage measurement
_DARK_LUMA = 0.5


def slugify(subject: str) -> str:
    """Ingredient/subject -> filesystem+S3-safe slug (lowercase, hyphenated)."""
    s = re.sub(r"[^a-z0-9]+", "-", str(subject).strip().lower())
    return s.strip("-") or "subject"


def _dark_coverage(img: Image.Image) -> float:
    """Fraction of pixels darker than _DARK_LUMA (0..1). Higher = heavier ink.

    Uses PIL's L (luminance) conversion and a histogram so the measurement is O(256)
    rather than per-pixel. A pure-white sketch on white trends toward ~0; a shaded /
    filled render trends high and gets rejected by the gate.
    """
    lum = img.convert("L")
    hist = lum.histogram()  # 256 buckets, index = luminance 0..255
    total = sum(hist) or 1
    cutoff = int(_DARK_LUMA * 255)
    dark = sum(hist[: cutoff + 1])
    return dark / total


def _invoke_image(
    client, subject: str, zone: str, *, seed: int, negative: str
) -> Image.Image | None:
    """One Stable Image Core call -> decoded RGB image, or None on failure.

    Request uses aspect_ratio (Stability's contract; no width/height, no style field —
    the line-art directive is baked into the prompt). Success requires
    finish_reasons[0] is None; a non-null value (e.g. content-filtered) means the image
    was blocked, which we log and treat as a failure.
    """
    aspect_ratio = _ZONE_ASPECT.get(zone, "16:9")
    body = {
        "prompt": _ZONE_PROMPT[zone].format(subject=subject),
        "negative_prompt": negative,
        "aspect_ratio": aspect_ratio,
        "output_format": "png",
        "seed": seed,
    }
    try:
        resp = client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
        finish = payload.get("finish_reasons") or [None]
        if finish[0] is not None:
            print(
                f"[recipe-art] stable image core blocked zone={zone} subject={subject!r}: "
                f"finish_reason={finish[0]!r}"
            )
            return None
        out_b64 = payload["images"][0]
        return Image.open(io.BytesIO(base64.b64decode(out_b64))).convert("RGB")
    except Exception as e:  # noqa: BLE001 — surface AccessDenied etc. to the log
        print(f"[recipe-art] stable image core invoke failed zone={zone} subject={subject!r}: {e}")
        return None


def generate_recipe_art(
    subject: str,
    zone: str,
    *,
    seed: int,
    out_dir: Path | None = None,
) -> Path | None:
    """Generate a hand-drawn ink line-art PNG for one card sketch zone.

    zone: one of "raw_ingredient" | "technique" | "finished_plate".
    seed:  deterministic image seed so re-runs reproduce the same drawing.
    out_dir: defaults to output/recipe-art/<subject-slug>/ ; the file is <zone>.png.

    Returns the saved Path, or None when there are no creds, the model errors
    (e.g. AccessDenied — logged verbatim), or the coverage gate rejects both the
    initial render and the single stronger-negative retry. Never raises.
    """
    if zone not in ZONES:
        raise ValueError(f"unknown zone {zone!r}; expected one of {ZONES}")

    client = _bedrock_client("bedrock-runtime", read_timeout=300, region=IMAGE_REGION)
    if client is None:
        print(f"[recipe-art] no bedrock client (offline/no-creds) — skipping {zone} for {subject!r}")
        return None

    slug = slugify(subject)
    out_root = Path(out_dir) if out_dir else DEFAULT_OUT_ROOT / slug
    out_path = out_root / f"{zone}.png"

    # attempt 1: base negative
    img = _invoke_image(client, subject, zone, seed=seed, negative=_NEGATIVE_BASE)
    if img is not None:
        cov = _dark_coverage(img)
        if cov <= _COVERAGE_CEILING:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_path, "PNG")
            print(f"[recipe-art] {zone} for {subject!r} coverage={cov:.3f} -> {out_path}")
            return out_path
        print(
            f"[recipe-art] {zone} for {subject!r} coverage={cov:.3f} > {_COVERAGE_CEILING} "
            "(too heavy) — retrying with stronger negative + seed+1"
        )

    # attempt 2: stronger negative, seed+1
    img = _invoke_image(client, subject, zone, seed=seed + 1, negative=_NEGATIVE_STRONG)
    if img is not None:
        cov = _dark_coverage(img)
        if cov <= _COVERAGE_CEILING:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_path, "PNG")
            print(f"[recipe-art] {zone} for {subject!r} retry coverage={cov:.3f} -> {out_path}")
            return out_path
        print(
            f"[recipe-art] {zone} for {subject!r} REJECTED — retry coverage={cov:.3f} still "
            f"> {_COVERAGE_CEILING}; returning None (frontend falls back to SVG placeholder)"
        )
        return None

    print(f"[recipe-art] {zone} for {subject!r} produced no image after retry — None")
    return None
