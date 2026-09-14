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

PRODUCTION-SPECS GATE: a render occasionally comes back heavy/shaded, and leafy or
clustered subjects tend to fill the frame with dense foliage / overlapping forms. After
decoding we measure dark-pixel coverage (luminance < 0.5) and reject anything over the
0.37 ceiling (0.35 spec + 0.02 template tolerance). The gate escalates across up to
_MAX_ATTEMPTS tries: each retry bumps the seed and swaps in a stronger negative, and the
final attempt adds a "very minimal, almost blank" directive. The raw_ingredient prompt
is also biased toward sparse single-specimen linework, with a per-subject-class hint that
nudges leafy greens toward "a leaf or two" and clustered fruit/nut subjects toward "two
or three pieces". A still-too-heavy render returns None rather than shipping a shaded
block dressed as a sketch — the frontend then falls back to its SVG placeholder.

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
# raw_ingredient is the ink-heavy zone: leafy greens and clustered fruit/nut subjects
# push Stable Image Core toward dense foliage / overlapping forms that blow past the
# coverage gate. The base prompt is written for SPARSE linework — single specimen,
# generous negative space, thin clean contours — so ink-heavy subjects come back light.
_ZONE_PROMPT: dict[str, str] = {
    "raw_ingredient": (
        "hand-drawn ink line-art illustration of a single raw {subject}, one specimen "
        "not a cluster, isolated on white, sparse clean contour lines, thin lines, "
        "minimal detail, generous white space, lots of negative space, airy open "
        "linework, deep brown ink on white, botanical sketch style, uncolored, "
        "printer-friendly line drawing"
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
    "background, drop shadow, 3d render, watermark, text, words, lettering, "
    "dense foliage, full bunch, pile, cluster, many leaves, overlapping"
)
# retry after a coverage rejection pushes harder against heavy ink / dark masses
# and against density (the two failure modes: heavy ink and crowded subjects)
_NEGATIVE_STRONG = (
    _NEGATIVE_BASE
    + ", heavy ink, dense hatching, black fill, filled silhouette, high contrast, "
    "muddy, blotchy, dark shading, ink wash, painted, busy, intricate detail, "
    "heavy linework, filled shapes, crowded, many items"
)

# subject-class hints: append a short sparsity clause when the subject keyword-matches.
# Kept as a small readable mapping (keyword tuple -> clause), not a per-ingredient table.
# Leafy subjects render as a leaf or two rather than a dense bunch; small clustered
# fruit/nut subjects render as two or three pieces rather than a full pile. Subjects
# that match neither just use the strengthened base prompt.
_LEAFY_KEYWORDS = (
    "green",
    "collard",
    "kale",
    "sprout",
    "lettuce",
    "artichoke",
    "chard",
    "spinach",
    "cabbage",
)
_CLUSTER_KEYWORDS = (
    "berry",
    "berries",
    "grape",
    "pecan",
    "nut",
    "bean",
    "pea",
    "cherry",
)
_LEAFY_CLAUSE = (
    ", just a single leaf or two, open airy linework, not a dense bunch, "
    "few strokes, mostly empty white space"
)
_CLUSTER_CLAUSE = (
    ", only two or three pieces, simple outlines, not a full pile, "
    "well spaced apart, mostly empty white space"
)
# strongest final-attempt directive: near-blank, minimal strokes
_MINIMAL_CLAUSE = ", very minimal, almost blank, only a few strokes, extremely sparse"


def _subject_class_clause(subject: str) -> str:
    """Return a short sparsity clause for ink-heavy subject classes, else "".

    Leafy greens and clustered fruit/nut subjects are the coverage-gate offenders;
    a keyword match biases the prompt toward a sparse rendering. First match wins
    (leafy checked before cluster). Non-matching subjects get no clause.
    """
    low = str(subject).lower()
    if any(kw in low for kw in _LEAFY_KEYWORDS):
        return _LEAFY_CLAUSE
    if any(kw in low for kw in _CLUSTER_KEYWORDS):
        return _CLUSTER_CLAUSE
    return ""


# coverage gate allows up to this many total attempts before returning None.
# attempt 1: base negative, seed. attempt 2: stronger negative, seed+1.
# attempt 3 (final): stronger negative + minimal-strokes directive, seed+2.
_MAX_ATTEMPTS = 3

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
    client, subject: str, zone: str, *, seed: int, negative: str, extra_clause: str = ""
) -> Image.Image | None:
    """One Stable Image Core call -> decoded RGB image, or None on failure.

    Request uses aspect_ratio (Stability's contract; no width/height, no style field —
    the line-art directive is baked into the prompt). extra_clause is appended to the
    formatted zone prompt (subject-class sparsity hint and/or the final-attempt minimal
    directive). Success requires finish_reasons[0] is None; a non-null value (e.g.
    content-filtered) means the image was blocked, which we log and treat as a failure.
    """
    aspect_ratio = _ZONE_ASPECT.get(zone, "16:9")
    body = {
        "prompt": _ZONE_PROMPT[zone].format(subject=subject) + extra_clause,
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
    (e.g. AccessDenied — logged verbatim), or the coverage gate rejects every attempt
    (up to _MAX_ATTEMPTS). Never raises.
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

    # subject-class sparsity hint applies to the ink-heavy raw_ingredient zone only;
    # technique/finished_plate compose differently and are not gate offenders.
    class_clause = _subject_class_clause(subject) if zone == "raw_ingredient" else ""

    # Escalating attempts, capped at _MAX_ATTEMPTS. Each attempt strengthens against the
    # two failure modes (heavy ink, crowded subject):
    #   attempt 0: base negative, seed          + class hint
    #   attempt 1: stronger negative, seed+1     + class hint
    #   attempt 2+: stronger negative, seed+N    + class hint + minimal-strokes directive
    for attempt in range(_MAX_ATTEMPTS):
        negative = _NEGATIVE_BASE if attempt == 0 else _NEGATIVE_STRONG
        extra_clause = class_clause
        if attempt >= 2:
            extra_clause += _MINIMAL_CLAUSE
        img = _invoke_image(
            client,
            subject,
            zone,
            seed=seed + attempt,
            negative=negative,
            extra_clause=extra_clause,
        )
        if img is None:
            # a failed invoke (block/error) is not retryable by escalation — stop.
            print(
                f"[recipe-art] {zone} for {subject!r} produced no image "
                f"(attempt {attempt + 1}/{_MAX_ATTEMPTS}) — None"
            )
            return None
        cov = _dark_coverage(img)
        if cov <= _COVERAGE_CEILING:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(out_path, "PNG")
            print(
                f"[recipe-art] {zone} for {subject!r} coverage={cov:.3f} "
                f"(attempt {attempt + 1}/{_MAX_ATTEMPTS}) -> {out_path}"
            )
            return out_path
        if attempt + 1 < _MAX_ATTEMPTS:
            print(
                f"[recipe-art] {zone} for {subject!r} coverage={cov:.3f} > {_COVERAGE_CEILING} "
                f"(too heavy, attempt {attempt + 1}/{_MAX_ATTEMPTS}) — "
                "retrying with stronger negative + seed bump"
            )
        else:
            print(
                f"[recipe-art] {zone} for {subject!r} REJECTED — coverage={cov:.3f} still "
                f"> {_COVERAGE_CEILING} after {_MAX_ATTEMPTS} attempts; returning None "
                "(frontend falls back to SVG placeholder)"
            )

    return None
