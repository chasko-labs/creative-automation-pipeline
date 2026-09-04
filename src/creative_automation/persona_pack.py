"""Persona-aware downloadable asset pack — one zip a Kodiak team member can act on.

This is the LOCAL packaging function (backlog: wiring it to an async download endpoint
is a separate item). It composes existing units — the platform matrix (platforms.py),
the per-platform copy (platform_copy.py), the localization set, and the rendered heroes —
into one ZIP structured for the three people in docs/ux-persona-kodiak.md:

  - Maya (brand manager)   -> a launch-ready set: every ratio + its copy, ready to ship.
  - Diego (field ambassador) -> the territory story: the 9x16 vertical + its copy.
  - Priya (performance lead) -> the master (1x1) + a per-region rollup manifest.

Layout inside the zip (one image per RATIO, never duplicated per platform):

    images/{RATIO}/KODIAK-CAKES-{PRODUCT}-{REGION}-{LOCALITY}-{CHANNEL}-{RATIO}-{DATE}-{VERSION}.png
    platform-copy.json          # the TASK 2 per-platform copy objects
    localizations.json          # EN/ES/PT headline lines
    manifest.json               # product/market/date + ratio->dims->platforms matrix + persona index
    README.txt                  # plain-language layout + naming explainer for the team

Naming follows docs/iso-naming-conventions.md section 4 exactly (7 fields), with the one
deliberate extension that RATIO may also be 4x5 (a delivery ratio the pipeline renders
that predates the strict 1x1|9x16|16x9 filename regex). One image serves multiple
platforms; the manifest maps each ratio to the platforms that consume it, so the zip
carries one image per ratio + a mapping, not duplicate bytes per platform.

Pure stdlib (zipfile, json) + Pillow already in-tree — no new deps. Deterministic given
the same inputs (same file set, same manifest structure).
"""
from __future__ import annotations

import json
import zipfile
from pathlib import Path

from .naming import _region_field, _version_field, slugify, today_utc
from .platforms import platforms_for_ratio, ratio_dims, ratio_to_platforms_map

# RATIO field for the pack image name: the strict ISO regex allows 1x1|9x16|16x9; the
# pipeline also delivers 4x5 / 2x3. This builder accepts any lower-case NxM ratio so the
# rendered delivery set names cleanly. The channel field is a fixed literal since one
# image serves multiple channels — the manifest carries the per-ratio platform mapping.
_PACK_CHANNEL = "social"


def build_pack_image_name(
    product: str,
    region: str,
    locality: str,
    ratio: str,
    date: str | None = None,
    version: str | int = "v01",
    channel: str = _PACK_CHANNEL,
) -> str:
    """Build the 7-field ISO-style image filename for a pack ratio.

    Mirrors naming.build_iso_name field normalization but permits the delivery ratios
    (4x5, 2x3) the strict ISO regex omits — the pack names by ratio, and the manifest
    maps each ratio to the platforms it serves.
    """
    product_f = slugify(product) or "power-cakes"
    region_f = _region_field(region)
    locality_f = slugify(locality) or "national"
    channel_f = slugify(channel) or _PACK_CHANNEL
    ratio_f = str(ratio).strip().lower()
    date_f = date or today_utc()
    version_f = _version_field(version)
    return (
        f"KODIAK-CAKES-{product_f}-{region_f}-{locality_f}-"
        f"{channel_f}-{ratio_f}-{date_f}-{version_f}.png"
    )


def _persona_index(ratios: list[str], matrix: dict) -> dict:
    """Persona-oriented index into the pack (docs/ux-persona-kodiak.md).

    Maya gets the launch-ready set (all ratios). Diego gets the territory story (the 9x16
    vertical + its copy) when a 9x16 render exists, else the tallest available ratio.
    Priya gets the master (1x1) when present, else the first ratio, plus the note that
    the manifest carries the per-region rollup.
    """
    diego_ratio = "9x16" if "9x16" in ratios else (ratios[-1] if ratios else None)
    priya_master = "1x1" if "1x1" in ratios else (ratios[0] if ratios else None)
    return {
        "maya": {
            "role": "brand manager",
            "deliverable": "launch-ready set",
            "ratios": list(ratios),
            "note": "every ratio plus platform-copy.json — ready to ship per product/size",
        },
        "diego": {
            "role": "field ambassador",
            "deliverable": "territory story",
            "ratio": diego_ratio,
            "platforms": matrix.get(diego_ratio, {}).get("platforms", []) if diego_ratio else [],
            "note": "the vertical story creative plus its copy — shareable for a territory",
        },
        "priya": {
            "role": "performance lead",
            "deliverable": "master + per-region rollup",
            "master_ratio": priya_master,
            "note": "one master creative; per-region rollup lives in manifest.rollup",
        },
    }


def _rollup(market: str, localizations: list[dict], ratios: list[str], matrix: dict) -> dict:
    """Priya's per-region rollup line: one creative, the regions/languages it serves."""
    return {
        "market": market,
        "languages": [loc.get("lang_code") for loc in localizations if loc.get("lang_code")],
        "ratios": list(ratios),
        "platforms": sorted({p for r in ratios for p in matrix.get(r, {}).get("platforms", [])}),
        "note": "one creative set intelligently serves every listed region/language",
    }


def _readme_text(product: str, market: str, ratios: list[str], matrix: dict) -> str:
    """Plain-language layout + naming explainer for the team (ascii only)."""
    lines = [
        "KODIAK(R) CAMPAIGN ASSET PACK",
        "=============================",
        "",
        f"Product: {product}",
        f"Market:  {market}",
        "",
        "WHAT IS IN THIS PACK",
        "--------------------",
        "images/            one PNG per aspect ratio, organized in a folder per ratio.",
        "                   One image serves multiple platforms; manifest.json maps",
        "                   each ratio to the platforms that use it.",
        "platform-copy.json the campaign words tailored per social network (X, LinkedIn,",
        "                   Instagram, TikTok, Facebook, Pinterest, YouTube).",
        "localizations.json the headline in English plus the market's top languages.",
        "manifest.json      product, market, date, the ratio -> size -> platform matrix,",
        "                   and a persona index (Maya / Diego / Priya).",
        "",
        "RATIOS IN THIS PACK",
        "-------------------",
    ]
    for r in ratios:
        dims = matrix.get(r, {})
        plats = ", ".join(dims.get("platforms", [])) or "(none)"
        lines.append(f"  {r}  {dims.get('w')}x{dims.get('h')}  -> {plats}")
    lines += [
        "",
        "FILE NAMING (docs/iso-naming-conventions.md)",
        "--------------------------------------------",
        "  KODIAK-CAKES-{product}-{REGION}-{locality}-{channel}-{ratio}-{YYYYMMDD}-{vNN}.png",
        "",
        "WHO USES WHAT",
        "-------------",
        "  Maya (brand manager): the whole launch-ready set + platform-copy.json.",
        "  Diego (field ambassador): the 9x16 vertical + its copy for your territory.",
        "  Priya (performance lead): the 1x1 master + the per-region rollup in manifest.json.",
        "",
        "Keep It Wild. Nourishment for Today's Frontier.",
        "",
    ]
    return "\n".join(lines)


def build_asset_pack(
    renders: list[dict],
    platform_copy: dict,
    localizations: list[dict],
    provenance: dict,
    market: str,
    product: str,
    out_dir: Path,
    *,
    locality: str | None = None,
    date: str | None = None,
    version: str | int = "v01",
    matrix_path: Path | None = None,
) -> Path:
    """Assemble a persona-aware asset pack ZIP and return its path.

    Args:
        renders:      [{ratio, path, w, h, engine}, ...] as generate_hero_set emits. Each
                      render's file is placed under images/{ratio}/ named per convention.
                      A render whose path is missing on disk is still recorded in the
                      manifest (offline/CI) but not written into the zip.
        platform_copy: the TASK 2 {platform: copy-object} map (written verbatim).
        localizations: [{lang_code, headline, ...}, ...] (written verbatim).
        provenance:   the generate provenance object (summarized into the manifest).
        market/product: identity fields for naming + manifest.
        out_dir:      directory to write the .zip into (created if absent).
        locality:     optional locality slug for the filename; defaults to the market tail.
        date/version: ISO date (YYYYMMDD) + vNN for the filenames; default today/v01.
        matrix_path:  test seam for the platform matrix file.

    Returns the Path to the written zip. One image per ratio (no per-platform duplication);
    the manifest maps each ratio to its platforms. Deterministic given the same inputs.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    product_f = slugify(product) or "power-cakes"
    region_f = _region_field(market)
    locality_f = slugify(locality) if locality else (slugify(market) or "national")
    date_f = date or today_utc()

    # ratios present in the render set, in render order (dedup preserving order).
    ratios: list[str] = []
    for r in renders:
        rr = str(r.get("ratio", "")).strip().lower()
        if rr and rr not in ratios:
            ratios.append(rr)

    # ratio -> dims -> platforms matrix, scoped to the ratios actually in the pack.
    full_matrix = ratio_to_platforms_map(path=matrix_path)
    pack_matrix = {r: full_matrix.get(r) or _matrix_row_for(r, matrix_path) for r in ratios}

    # build the per-ratio image entries (name + on-disk source + platforms served).
    image_entries: list[dict] = []
    missing: list[str] = []
    for r in renders:
        ratio = str(r.get("ratio", "")).strip().lower()
        if not ratio:
            continue
        fname = build_pack_image_name(
            product, market, locality_f, ratio, date=date_f, version=version
        )
        arcname = f"images/{ratio}/{fname}"
        src = r.get("path")
        src_path = Path(src) if src else None
        present = bool(src_path and src_path.exists())
        entry = {
            "ratio": ratio,
            "filename": fname,
            "arcname": arcname,
            "w": r.get("w") or ratio_dims(ratio, matrix_path)[0],
            "h": r.get("h") or ratio_dims(ratio, matrix_path)[1],
            "engine": r.get("engine"),
            "platforms": platforms_for_ratio(ratio, matrix_path),
            "present": present,
        }
        image_entries.append(entry)
        if not present:
            missing.append(fname)

    persona_index = _persona_index(ratios, pack_matrix)
    manifest = {
        "schema": "kodiak.asset-pack.v1",
        "product": product_f,
        "market": market,
        "region": region_f,
        "locality": locality_f,
        "date": date_f,
        "provenance": _provenance_summary(provenance),
        "matrix": pack_matrix,
        "images": image_entries,
        "platforms": sorted(platform_copy.keys()),
        "personas": persona_index,
        "rollup": _rollup(market, localizations, ratios, pack_matrix),
        "missing": missing,
    }

    pack_name = (
        f"KODIAK-CAKES-{product_f}-{region_f}-{locality_f}-social-pack-{date_f}-"
        f"{_version_field(version)}.zip"
    )
    zip_path = out_dir / pack_name

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True))
        zf.writestr("platform-copy.json", json.dumps(platform_copy, indent=2, sort_keys=True))
        zf.writestr("localizations.json", json.dumps(localizations, indent=2))
        zf.writestr("README.txt", _readme_text(product_f, market, ratios, pack_matrix))
        for entry in image_entries:
            if entry["present"]:
                # find the render source for this ratio and write it under its arcname
                src = next(
                    (r.get("path") for r in renders
                     if str(r.get("ratio", "")).strip().lower() == entry["ratio"]),
                    None,
                )
                if src and Path(src).exists():
                    zf.write(Path(src), arcname=entry["arcname"])

    return zip_path


def _matrix_row_for(ratio: str, matrix_path: Path | None) -> dict:
    """Fallback matrix row when a ratio (e.g. 2x3) is not in the platform matrix.

    The pipeline delivers 2x3 as a story/pin derivative; it is not a first-class matrix
    ratio. Map it to the 9x16 vertical platform set so the manifest still tells the team
    where a vertical creative goes, without inventing a ratio in the SoT file.
    """
    dims = ratio_dims(ratio, matrix_path)
    served = platforms_for_ratio("9x16", matrix_path) if ratio == "2x3" else []
    return {"label": ratio, "w": dims[0], "h": dims[1], "platforms": served}


def _provenance_summary(provenance: dict) -> dict:
    """Compact, JSON-safe subset of the generate provenance for the manifest."""
    if not isinstance(provenance, dict):
        return {}
    keep = ("theme", "headline", "ratios", "languages", "platforms", "overlay_applied",
            "card_template", "scene_prompt")
    return {k: provenance[k] for k in keep if k in provenance}
