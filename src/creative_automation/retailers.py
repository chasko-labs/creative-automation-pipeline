"""Retailer logo lockup lookup — the ONE sanctioned text-in-image exception.

Kodiak imagery carries little-to-no text. The single exception is a retailer logo
lockup (e.g. the Costco mark with a specific local store address). That lockup is a
separate explicit operation, never part of the default spin. This module resolves a
retailer name -> logo asset path (SVG preferred) + an optional local store address
string for the overlay.

We do NOT fabricate logo files. SVGs are expected under input_assets/retailer-logos/.
resolve_retailer() reports which are present and which are missing so tooling and
operators know what to drop in. SVG is preferred so downstream tooling (Pillow via a
rasterizer, or an SVG compositor) can place the mark cleanly at any scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# canonical logo directory — drop {costco,publix,target}.svg here
LOGO_DIR = Path(__file__).parents[2] / "input_assets" / "retailer-logos"

# retailers that appear in the test campaigns. Georgia retailer is Publix
# (market US-SE-ATL: "Publix, Target"), alongside Costco and Target.
_RETAILER_ALIASES: dict[str, str] = {
    "costco": "costco",
    "costco wholesale": "costco",
    "publix": "publix",
    "target": "target",
}

# preferred vector filename per retailer; png is a raster fallback only
_LOGO_STEMS: dict[str, str] = {
    "costco": "costco",
    "publix": "publix",
    "target": "target",
}

# example local store addresses for the lockup — real addresses supplied per campaign.
# These seed the two campaigns Bryan named (SF Bay Area + Atlanta 30361).
STORE_ADDRESS_SEEDS: dict[str, str] = {
    "costco:san-francisco": "Costco Wholesale — 450 10th St, San Francisco, CA 94103",
    "publix:atlanta": "Publix — 1250 W Peachtree St NW, Atlanta, GA 30309",
}


@dataclass
class RetailerLogo:
    """Resolved retailer lockup asset + optional store address for overlay."""

    name: str
    svg_path: Path
    png_path: Path
    svg_exists: bool
    png_exists: bool
    store_address: str | None = None
    notes: list[str] = field(default_factory=list)

    @property
    def asset_path(self) -> Path | None:
        """Preferred usable asset — SVG first, then PNG, else None (missing)."""
        if self.svg_exists:
            return self.svg_path
        if self.png_exists:
            return self.png_path
        return None

    @property
    def missing(self) -> bool:
        return self.asset_path is None


def normalize_retailer(name: str) -> str | None:
    """Map a free-form retailer name to a canonical key, or None if unknown."""
    return _RETAILER_ALIASES.get(name.strip().lower())


def resolve_retailer(
    name: str,
    *,
    store_address: str | None = None,
    logo_dir: Path | None = None,
) -> RetailerLogo:
    """Resolve a retailer name to its logo lockup asset + optional store address.

    SVG is preferred; PNG is a raster fallback. Missing files are reported via
    svg_exists / png_exists / missing, never fabricated.
    """
    key = normalize_retailer(name)
    if key is None:
        raise ValueError(
            f"unknown retailer {name!r}; known: {sorted(set(_RETAILER_ALIASES.values()))}"
        )
    base = Path(logo_dir) if logo_dir else LOGO_DIR
    stem = _LOGO_STEMS[key]
    svg_path = base / f"{stem}.svg"
    png_path = base / f"{stem}.png"
    notes: list[str] = []
    if not svg_path.exists():
        notes.append(f"missing preferred SVG — drop {svg_path} (vector lockup for clean scaling)")
    if not svg_path.exists() and not png_path.exists():
        notes.append(f"no raster fallback either — {png_path} absent")
    return RetailerLogo(
        name=key,
        svg_path=svg_path,
        png_path=png_path,
        svg_exists=svg_path.exists(),
        png_exists=png_path.exists(),
        store_address=store_address,
        notes=notes,
    )


def missing_logos(logo_dir: Path | None = None) -> list[str]:
    """Return canonical retailer keys whose logo asset is absent (neither SVG nor PNG)."""
    return [
        key
        for key in sorted(set(_RETAILER_ALIASES.values()))
        if resolve_retailer(key, logo_dir=logo_dir).missing
    ]
