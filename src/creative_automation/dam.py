"""DAM lookup — local folder or mock S3."""
from __future__ import annotations

from pathlib import Path
from typing import Optional


ASSET_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
HERO_NAMES = {"hero", "main", "cover", "product"}


def find_hero_asset(product_id: str, dam_root: Path, explicit: Optional[str] = None) -> Optional[Path]:
    """Return hero image path if found, else None.

    Lookup order:
    1. explicit path if provided
    2. dam_root / product_id / hero.*  (any ext)
    3. dam_root / product_id / any image
    4. dam_root / brand / logo.* (not hero, but caller checks)
    """
    if explicit:
        p = Path(explicit)
        if not p.is_absolute():
            p = dam_root / p
        if p.exists():
            return p

    product_dir = dam_root / product_id
    if product_dir.is_dir():
        # hero.* first
        for ext in ASSET_EXTS:
            for name in HERO_NAMES:
                c = product_dir / f"{name}{ext}"
                if c.exists():
                    return c
        # any image in dir
        for ext in ASSET_EXTS:
            hits = list(product_dir.glob(f"*{ext}"))
            if hits:
                return sorted(hits)[0]
    return None


def find_brand_logo(dam_root: Path) -> Optional[Path]:
    for base in [dam_root / "brand", dam_root]:
        if base.is_dir():
            for ext in ASSET_EXTS:
                for name in ("logo", "brand", "mark"):
                    c = base / f"{name}{ext}"
                    if c.exists():
                        return c
            # any logo-ish
            for ext in ASSET_EXTS:
                hits = list(base.glob(f"*{ext}"))
                if hits:
                    return hits[0]
    return None
