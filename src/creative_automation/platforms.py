"""Platform -> ratio -> dimension matrix loader — the pipeline's read side of the SoT.

The authoritative mapping lives in data/platforms/platform-matrix.json (verified 2026-09)
so the asset-pack builder and the frontend read the SAME table. This module never mutates
that file; it loads it once, caches it, and hands back plain dicts/lists. Offline-safe:
a missing/unreadable file falls through to the deterministic embedded matrix so tests and
CI never depend on disk state.

The seven consumer-facing platform slugs are fixed:
    facebook  instagram  x  linkedin  pinterest  tiktok  youtube
The four ratio slugs are fixed and carry their pixel dims:
    1x1 1080x1080   4x5 1080x1350   9x16 1080x1920   16x9 1920x1080
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# repo-root-relative; parents[2] == repo root (src/creative_automation/platforms.py)
_MATRIX_PATH = Path(__file__).parents[2] / "data" / "platforms" / "platform-matrix.json"

# The seven sanctioned platform slugs, in a stable display order.
PLATFORMS: tuple[str, ...] = (
    "facebook",
    "instagram",
    "x",
    "linkedin",
    "pinterest",
    "tiktok",
    "youtube",
)
# The four sanctioned ratio slugs -> (w, h). Kept here as the offline fallback and as
# the authoritative dims a caller can assert against without touching disk.
RATIO_DIMS: dict[str, tuple[int, int]] = {
    "1x1": (1080, 1080),
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}

# Embedded fallback matrix — mirrors platform-matrix.json exactly so a disk read
# failure never changes behavior. Any edit here MUST mirror the JSON file.
_FALLBACK_MATRIX: dict = {
    "ratios": {
        "1x1": {"label": "Square", "w": 1080, "h": 1080,
                "platforms": ["facebook", "instagram", "x", "linkedin", "pinterest"]},
        "4x5": {"label": "Portrait", "w": 1080, "h": 1350,
                "platforms": ["instagram", "facebook"]},
        "9x16": {"label": "Vertical / Full-Screen", "w": 1080, "h": 1920,
                 "platforms": ["instagram", "facebook", "tiktok", "youtube", "pinterest"]},
        "16x9": {"label": "Landscape", "w": 1920, "h": 1080,
                 "platforms": ["youtube", "linkedin", "x", "facebook"]},
    },
    "platforms": {
        "facebook": {"label": "Facebook", "ratios": ["1x1", "4x5", "9x16", "16x9"]},
        "instagram": {"label": "Instagram", "ratios": ["1x1", "4x5", "9x16"]},
        "x": {"label": "X", "ratios": ["1x1", "16x9"]},
        "linkedin": {"label": "LinkedIn", "ratios": ["1x1", "16x9"]},
        "pinterest": {"label": "Pinterest", "ratios": ["1x1", "9x16"]},
        "tiktok": {"label": "TikTok", "ratios": ["9x16"]},
        "youtube": {"label": "YouTube", "ratios": ["9x16", "16x9"]},
    },
}

_MATRIX_CACHE: Optional[dict] = None


def load_matrix(path: Path | None = None) -> dict:
    """Load the platform matrix once. Returns {ratios, platforms, ...}.

    Reads data/platforms/platform-matrix.json; on any read/parse failure returns the
    deterministic embedded fallback so the pipeline never blocks on disk state. Module
    cached — a passed `path` bypasses the cache (test seam).
    """
    global _MATRIX_CACHE
    if path is not None:
        try:
            return json.loads(Path(path).read_text(encoding="utf-8"))
        except Exception:
            return _FALLBACK_MATRIX
    if _MATRIX_CACHE is not None:
        return _MATRIX_CACHE
    p = _MATRIX_PATH
    if p.exists():
        try:
            _MATRIX_CACHE = json.loads(p.read_text(encoding="utf-8"))
            return _MATRIX_CACHE
        except Exception:
            pass
    _MATRIX_CACHE = _FALLBACK_MATRIX
    return _MATRIX_CACHE


def platform_label(platform: str, path: Path | None = None) -> str:
    """Human label for a platform slug (e.g. 'x' -> 'X'). Falls back to the slug."""
    entry = load_matrix(path).get("platforms", {}).get(platform, {})
    return entry.get("label") or platform


def ratios_for_platform(platform: str, path: Path | None = None) -> list[str]:
    """The ratio slugs a platform consumes, in matrix order. [] for an unknown slug."""
    entry = load_matrix(path).get("platforms", {}).get(platform, {})
    return list(entry.get("ratios", []))


def platforms_for_ratio(ratio: str, path: Path | None = None) -> list[str]:
    """The platform slugs that consume a ratio, in matrix order. [] for an unknown ratio."""
    entry = load_matrix(path).get("ratios", {}).get(ratio, {})
    return list(entry.get("platforms", []))


def ratio_dims(ratio: str, path: Path | None = None) -> tuple[int, int]:
    """(w, h) pixel dims for a ratio slug. Reads the matrix, then the embedded floor."""
    entry = load_matrix(path).get("ratios", {}).get(ratio, {})
    w = entry.get("w")
    h = entry.get("h")
    if isinstance(w, int) and isinstance(h, int):
        return (w, h)
    return RATIO_DIMS.get(ratio, (0, 0))


def ratios_for_platforms(platforms: list[str], path: Path | None = None) -> list[str]:
    """Union of ratios consumed by a set of platforms, de-duped, in matrix ratio order.

    A ratio is included when at least one requested platform consumes it. Order follows
    the matrix ratios[] declaration order so the emitted set is deterministic.
    """
    wanted: set[str] = set()
    for p in platforms:
        wanted.update(ratios_for_platform(p, path))
    return [r for r in load_matrix(path).get("ratios", {}) if r in wanted]


def ratio_to_platforms_map(platforms: list[str] | None = None, path: Path | None = None) -> dict:
    """Emit {ratio: {w, h, label, platforms:[...]}} for the manifest.

    When `platforms` is given, each ratio's platforms list is filtered to that set (and
    ratios no platform consumes are dropped). When None, the full matrix is returned.
    """
    matrix = load_matrix(path)
    out: dict[str, dict] = {}
    for ratio, entry in matrix.get("ratios", {}).items():
        served = list(entry.get("platforms", []))
        if platforms is not None:
            served = [p for p in served if p in platforms]
            if not served:
                continue
        w, h = ratio_dims(ratio, path)
        out[ratio] = {
            "label": entry.get("label", ratio),
            "w": w,
            "h": h,
            "platforms": served,
        }
    return out
