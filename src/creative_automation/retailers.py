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

# canonical logo directory — drop {costco,publix,target,subscription}.svg here
LOGO_DIR = Path(__file__).parents[2] / "input_assets" / "retailer-logos"

# retailers that appear in the test campaigns. Georgia retailer is Publix
# (market US-SE-ATL: "Publix, Target"), alongside Costco and Target.
# "subscription" is the Kodiak Cakes DTC subscription as a retailer-equivalent,
# weighted toward rural/frontier markets with no in-town chain grocer
# (issue #198). It carries no logo file — resolve_retailer reports it missing
# so operators know, and campaign plans it as a fulfillment entry, not a lockup.
_RETAILER_ALIASES: dict[str, str] = {
    "costco": "costco",
    "costco wholesale": "costco",
    "publix": "publix",
    "target": "target",
    "subscription": "subscription",
    "kodiak subscription": "subscription",
    "kodiak cakes subscription": "subscription",
    "subscribe & save": "subscription",
    "subscribe and save": "subscription",
    "dtc subscription": "subscription",
}

# The four surfaces the chooser/retailer UI must show where the market
# supports them (issue #198): three chain grocers + DTC subscription.
SUPPORTED_RETAILERS: tuple[str, ...] = ("costco", "publix", "target", "subscription")

# brick-and-mortar order for surfacing — subscription always trails, it is the
# fulfillment fallback, never the lead when a chain grocer is on file.
_CHAIN_ORDER: tuple[str, ...] = ("costco", "publix", "target")

# DTC fulfillment line for the subscription retailer-equivalent (mirrors the
# frontier-gap fulfillment copy in api.py — one canonical string).
SUBSCRIPTION_FULFILLMENT = "DTC subscription — free shipping $45+"

# preferred vector filename per retailer; png is a raster fallback only
_LOGO_STEMS: dict[str, str] = {
    "costco": "costco",
    "publix": "publix",
    "target": "target",
    "subscription": "subscription",
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


# Market text that marks a rural/frontier market with no in-town chain grocer —
# the markets where the DTC subscription must surface (issue #198). Matched
# case-insensitively against "market-key + place" text. "farm" alone is NOT a
# signal (city farmers markets), but "no commercial retail" / "general store"
# / frontier-gap markers are.
_RURAL_HINTS = (
    "frontier",
    "rural",
    "ranch",
    "homestead",
    "backcountry",
    "reservation",
    "tribal",
    "frontier-gap",
    "no commercial retail",
    "general store",
)


def is_rural_market(market: str, place: str = "") -> bool:
    """True when a market reads as rural/frontier with no chain grocer.

    Args:
        market: the market key (e.g. "US-UT-KAMASVALLEY").
        place: the human place line (e.g. "Kamas Valley — Peoa / Oakley, UT
            84036 (Wasatch Back rural)"). Retailer strings carrying "no
            commercial retail" also count — pass the retailer field in here
            when the place line is thin.
    """
    hay = f"{market} {place}".lower()
    return any(hint in hay for hint in _RURAL_HINTS)


def surface_retailers(
    retailer_field: str | None,
    market: str = "",
    place: str = "",
) -> list[str]:
    """Chooser/retailer surface for a market (issue #198).

    Resolves the market's retailer string to the sanctioned chain grocers
    (costco/publix/target, deduped, in _CHAIN_ORDER) and appends the "subscription"
    retailer-equivalent when the market is rural/frontier OR when no chain grocer
    resolved (a frontier-gap market with nothing on file still gets DTC
    fulfillment). Chain grocers lead; subscription always trails.

    Returns [] only when the market is non-rural AND nothing resolved.
    """
    ordered: list[str] = []
    if retailer_field:
        import re as _re

        for raw in str(retailer_field).split(","):
            base = _re.sub(r"\(.*?\)", "", raw).strip()
            key = normalize_retailer(base)
            if key and key != "subscription" and key not in ordered:
                ordered.append(key)
    ordered.sort(key=lambda k: _CHAIN_ORDER.index(k))
    hay = f"{retailer_field or ''} {place}"
    if "subscription" not in ordered and (
        is_rural_market(market, hay) or not ordered
    ):
        ordered.append("subscription")
    return ordered
