"""Recipe video pipeline v0: dwell segmentation for flipping-card captures.

First test case: PXL_20260930_223402275.mp4 (382 s, 1080p hevc) — a
laminated bag cutout, typed cookbook pages, and printed website sheets,
shot handheld with wiggle, zoom hunts, and hand-enter page turns.

Signal design from that tape:
- motion spikes mark hand-enter page turns (transitions)
- stable low-motion runs mark readable dwells (best view lands near the end)
- sharpest frame per dwell wins; glare fraction flags lamination washout
- long low-sharpness dwells are gaps (empty background between cards)

Pillow only, matching the repo's imaging stack (no new native deps).

Later stages (not here): cluster dwell-best frames per recipe with
multimodal embeddings, read text with a vision reader, stitch text across
views until each recipe is covered, split family vs favorite by source
header text.
"""

from __future__ import annotations

import csv
from pathlib import Path

from PIL import Image, ImageChops, ImageStat

PROBE_SIZE = (480, 270)
DWELL_MOTION_THRESHOLD = 25.0
DWELL_MIN_LEN = 3
GLARE_WHITE_LEVEL = 250


def _probe(img: Image.Image) -> Image.Image:
    return img.convert("L").resize(PROBE_SIZE)


def score_frame(img: Image.Image) -> dict:
    """Sharpness, glare, and dark fractions for one frame.

    Sharpness is grayscale variance: crisp text spreads pixel values,
    blur squeezes them toward the mean. Glare is the fraction of
    near-white pixels (lamination washout).
    """
    small = _probe(img)
    hist = small.histogram()
    total = PROBE_SIZE[0] * PROBE_SIZE[1]
    return {
        "sharp": float(ImageStat.Stat(small).var[0]),
        "glare": sum(hist[GLARE_WHITE_LEVEL:]) / total,
        "dark": sum(hist[:6]) / total,
    }


def frame_motion(a: Image.Image, b: Image.Image) -> float:
    """Mean absolute per-pixel difference between two frames."""
    diff = ImageChops.difference(_probe(a), _probe(b))
    return float(ImageStat.Stat(diff).mean[0])


def segment_dwells(motions: list, threshold: float = DWELL_MOTION_THRESHOLD,
                   min_len: int = DWELL_MIN_LEN) -> list:
    """Split per-frame motion into stable dwell runs.

    A motion value above threshold ends the current dwell (hand-enter /
    page turn). Runs shorter than min_len are dropped as transitions.
    Returns a list of (start, end) inclusive frame indexes.
    """
    dwells = []
    cur: list = []
    for i, m in enumerate(motions):
        if m > threshold:
            if len(cur) >= min_len:
                dwells.append((cur[0], cur[-1]))
            cur = []
        else:
            cur.append(i)
    if len(cur) >= min_len:
        dwells.append((cur[0], cur[-1]))
    return dwells


def pick_best(scores: list) -> int:
    """Index of the sharpest frame in a dwell."""
    return max(range(len(scores)), key=lambda i: scores[i]["sharp"])


def score_video_frames(frames: list) -> tuple:
    """Score a list of frames; returns (scores, motions)."""
    scores = [score_frame(f) for f in frames]
    motions = [0.0]
    for prev, cur in zip(frames, frames[1:]):
        motions.append(frame_motion(prev, cur))
    return scores, motions


def write_dwell_manifest(path: Path, dwells: list, scores: list,
                         motions: list) -> None:
    """Write one row per dwell with its best frame for review."""
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["dwell", "start", "end", "n",
                    "best", "best_sharp", "best_glare"])
        for n, (s, e) in enumerate(dwells):
            sub = scores[s:e + 1]
            b = pick_best(sub)
            w.writerow([n, s, e, e - s + 1, s + b,
                        round(sub[b]["sharp"], 1),
                        round(sub[b]["glare"], 4)])
