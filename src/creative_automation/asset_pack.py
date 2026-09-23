"""Retailer asset-pack builder — zip a market's creatives + manifest for asset download.

Composes existing units, reinvents nothing:
  - naming.slugify / _region_field-style rules build the ISO-style pack filename
    KODIAK-CAKES-{product}-{REGION}-{locality}-retailers-pack-{YYYYMMDD}-{vNN}.zip
  - retailers.normalize_retailer resolves the market's retailer list to canonical keys
  - market-languages.json top_languages -> BCP-47 language tags for the manifest

The zip + manifest are pure stdlib (zipfile + tempfile). S3 upload/presign lives in
asset_store.s3_upload_and_presign; this module stays offline-safe so the endpoint and tests
work with no boto3 / no creds (local file path fallback).

The pack name is a .zip sibling of the 7-field .png ISO name — it swaps the
{channel}-{ratio} fields for the fixed literal 'retailers-pack' so a pack reads as
"all retailer-ready creatives for this market", not a single channel/ratio creative.
"""
from __future__ import annotations

import json
import re
import tempfile
import zipfile
from pathlib import Path

from .naming import slugify, today_utc
from .retailers import normalize_retailer

# repo-root-relative data file; parents[2] == repo root (src/creative_automation/asset_pack.py)
_MARKET_LANGS = Path(__file__).parents[2] / "data" / "localization" / "market-languages.json"

# pack filename: KODIAK-CAKES-{product}-{REGION}-{locality}-retailers-pack-{DATE}-{vNN}.zip
PACK_NAME_RE = re.compile(
    r"^KODIAK-CAKES-"
    r"(?P<product>[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"(?P<region>[A-Z0-9]+(?:-[A-Z0-9]+)*)-"
    r"(?P<locality>[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"retailers-pack-"
    r"(?P<date>[0-9]{8})-"
    r"(?P<version>v[0-9]{2})"
    r"\.zip$"
)


def _region_field(region: str) -> str:
    """Upper-case, hyphen-delimited region — mirrors naming._region_field (kept private there)."""
    s = str(region).strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "-", s)
    return s.strip("-") or "US"


def _version_field(version: str | int) -> str:
    if isinstance(version, int):
        return f"v{version:02d}"
    s = str(version).strip().lower().lstrip("v")
    return f"v{int(s):02d}" if s.isdigit() else "v01"


def build_pack_name(
    product: str,
    region: str,
    locality: str,
    date: str | None = None,
    version: str | int = "v01",
) -> str:
    """Produce the retailer-pack zip filename; always matches PACK_NAME_RE.

    Loose inputs are normalized the same way naming.build_iso_name normalizes its
    fields: product/locality slugified, region upper-cased, date defaults to today UTC.
    """
    product_f = slugify(product) or "power-cakes"
    region_f = _region_field(region)
    locality_f = slugify(locality) or "national"
    date_f = date or today_utc()
    version_f = _version_field(version)
    name = (
        f"KODIAK-CAKES-{product_f}-{region_f}-{locality_f}-"
        f"retailers-pack-{date_f}-{version_f}.zip"
    )
    if not PACK_NAME_RE.match(name):
        raise ValueError(f"built pack name failed validation: {name}")
    return name


def _load_market_langs(path: Path | None = None) -> list[dict]:
    p = path or _MARKET_LANGS
    if not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("markets", [])
    except (OSError, ValueError):
        return []


def market_language_tags(market: str, langs_path: Path | None = None) -> list[str]:
    """BCP-47 tags for a market from market-languages.json top_languages.

    Always leads with en-US (the base creative language). Each top language lang_code
    is joined to the US region subtag (BCP-47 language-REGION), e.g. es -> es-US.
    Returns just ['en-US'] when the market is not found — never blocks the pack.
    """
    tags = ["en-US"]
    for m in _load_market_langs(langs_path):
        if m.get("market") == market:
            for lang in m.get("top_languages", []):
                code = str(lang.get("lang_code", "")).strip().lower()
                if code and f"{code}-US" not in tags:
                    tags.append(f"{code}-US")
            break
    return tags


def market_retailers(retailer_field: str | None) -> list[str]:
    """Resolve a market's comma-separated retailer string to canonical retailer keys.

    Unknown retailers (store names not in the retailers alias table, e.g. "Smith's
    Food & Drug") are dropped — the pack manifest lists only the sanctioned lockup
    retailers (costco/publix/target) plus the "subscription" retailer-equivalent
    (issue #198). Returns [] when nothing resolves.
    """
    if not retailer_field:
        return []
    out: list[str] = []
    for raw in str(retailer_field).split(","):
        # strip parenthetical store qualifiers, e.g. "Target (Kimball Junction)" -> "Target"
        base = re.sub(r"\(.*?\)", "", raw).strip()
        key = normalize_retailer(base)
        if key and key not in out:
            out.append(key)
    return out


def build_asset_pack_zip(
    *,
    market: str,
    product: str,
    assets: list[dict],
    retailers: list[str],
    language_tags: list[str],
    dest_dir: Path,
    pack_name: str,
    generated: str | None = None,
) -> tuple[Path, dict]:
    """Write a retailer asset-pack zip into dest_dir and return (zip_path, manifest).

    The zip carries a manifest.json plus every asset file that exists on disk. Assets
    are described by the dicts campaigns() emits: each may carry a 'filename' (ISO name)
    and optionally a resolvable local path under input_assets. Missing files are recorded
    in the manifest 'missing' list rather than aborting the pack — offline/CI runs rarely
    have every rendered creative present, and the pack must still assemble.
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / pack_name

    contents: list[str] = []
    missing: list[str] = []
    for a in assets:
        fname = a.get("filename")
        if not fname:
            continue
        # candidate local locations for a rendered creative
        candidates = []
        if a.get("path"):
            candidates.append(Path(a["path"]))
        candidates.append(Path("input_assets") / fname)
        local = next((c for c in candidates if c.exists()), None)
        if local is not None:
            contents.append(fname)
        else:
            missing.append(fname)

    manifest = {
        "market": market,
        "product": slugify(product) or product,
        "retailers": retailers,
        "language_tags": language_tags,
        "generated": generated or f"{today_utc()}",
        "pack_name": pack_name,
        "asset_count": len(assets),
        "contents": contents,
        "missing": missing,
        "note": (
            "Retailer-ready KODIAK CAKES(R) creatives for this market. Missing entries "
            "are ISO names not yet rendered locally; regenerate via POST /pipeline/run."
        ),
    }

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2))
        for a in assets:
            fname = a.get("filename")
            if not fname or fname in missing:
                continue
            candidates = []
            if a.get("path"):
                candidates.append(Path(a["path"]))
            candidates.append(Path("input_assets") / fname)
            local = next((c for c in candidates if c.exists()), None)
            if local is not None:
                zf.write(local, arcname=fname)

    return zip_path, manifest


def pack_tempdir(prefix: str = "kodiak-pack-") -> Path:
    """A fresh temp dir for staging a pack zip. Caller owns cleanup lifetime."""
    return Path(tempfile.mkdtemp(prefix=prefix))
