"""Canonical ISO creative naming — single source of truth for the 7-field pattern.

The standard lives in docs/iso-naming-conventions.md section 4:

    KODIAK-CAKES-{PRODUCT}-{REGION}-{LOCALITY}-{CHANNEL}-{RATIO}-{DATE}-{VERSION}.png

Both the pipeline writer and the scorecards checker import ISO_NAME_RE from here
so the name that gets written and the name that gets validated can never drift.
"""
from __future__ import annotations

import datetime
import re

# --- the 7 fields, spelled exactly as the standard requires ---
#   PRODUCT  lower-case hyphenated slug            power-cakes
#   REGION   upper-case, hyphen delimited          US-NM, US-SW-LASCRUCES, US-MW
#   LOCALITY lower-case hyphenated city+store      las-cruces-target, park-city-wasatch
#   CHANNEL  lower-case, hyphen delimited           instagram, diner-board, subscription-email
#   RATIO    exactly one of 1x1 | 4x5 | 9x16 | 16x9
#   DATE     YYYYMMDD (ISO 8601 basic)
#   VERSION  vNN zero-padded                        v01, v02
ISO_NAME_RE = re.compile(
    r"^KODIAK-CAKES-"
    r"(?P<product>[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"(?P<region>[A-Z0-9]+(?:-[A-Z0-9]+)*)-"
    r"(?P<locality>[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"(?P<channel>[a-z0-9]+(?:-[a-z0-9]+)*)-"
    r"(?P<ratio>1x1|4x5|9x16|16x9)-"
    r"(?P<date>[0-9]{8})-"
    r"(?P<version>v[0-9]{2})"
    r"\.png$"
)

_RATIO_CANON = {
    "1x1": "1x1", "1:1": "1x1",
    "4x5": "4x5", "4:5": "4x5",
    "9x16": "9x16", "9:16": "9x16",
    "16x9": "16x9", "16:9": "16x9",
}

# --- BCP-47 language tags for creative metadata/headers ---
# The filename pattern above is one contract; the language tag written into
# report metadata + headers is another. Both live here so naming discipline is
# in one module. BCP47_RE validates the common shapes we emit: a 2-3 letter
# primary subtag, optional script (Xxxx), optional region (US / 419). It is a
# pragmatic subset of RFC 5646 — enough to reject en_US, EN-us, and bare junk.
BCP47_RE = re.compile(
    r"^(?P<lang>[a-z]{2,3})"
    r"(?:-(?P<script>[A-Z][a-z]{3}))?"
    r"(?:-(?P<region>[A-Z]{2}|[0-9]{3}))?$"
)

# default region subtag per primary language for the US-market creative set.
# Every market in this pipeline ships in the US, so English/Spanish default to
# -US; languages tied to a specific origin community still resolve to -US here
# because the audience is the US diaspora, not the origin country.
_DEFAULT_REGION_FOR_LANG = "US"


def bcp47_tag(lang: str, region: str | None = None) -> str:
    """Normalize a loose language code (+ optional region) to a BCP-47 tag.

    Accepts 'en', 'EN', 'en_US', 'en-us', 'es_419' and returns the well-formed
    'en-US' / 'es-419' form. Primary subtag lower-cases, region subtag
    upper-cases (or stays a 3-digit UN M.49 code). When no region is supplied
    and none is embedded, defaults to -US (this pipeline is US-market only).
    Raises ValueError if the result is not a valid BCP-47 tag.
    """
    raw = str(lang).strip().replace("_", "-")
    parts = [p for p in raw.split("-") if p]
    if not parts:
        raise ValueError(f"empty language code {lang!r}")
    primary = parts[0].lower()
    # region: explicit arg wins, else an embedded subtag, else the US default
    region_sub = None
    if region:
        region_sub = str(region).strip()
    elif len(parts) > 1:
        region_sub = parts[-1]
    if region_sub:
        region_sub = region_sub.upper() if region_sub.isalpha() else region_sub
    else:
        region_sub = _DEFAULT_REGION_FOR_LANG
    tag = f"{primary}-{region_sub}"
    if not BCP47_RE.match(tag):
        raise ValueError(f"could not build valid BCP-47 tag from {lang!r}/{region!r}: {tag}")
    return tag


def is_bcp47(tag: str) -> bool:
    """True when tag is a well-formed BCP-47 tag (the subset BCP47_RE accepts)."""
    return bool(BCP47_RE.match(str(tag)))


def slugify(text: str) -> str:
    """Lower-case, hyphen-delimited, ascii-safe slug — no leading/trailing/double hyphens."""
    s = str(text).strip().lower()
    # collapse anything that is not a-z0-9 into a single hyphen
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def canon_ratio(ratio: str) -> str:
    """Map any accepted ratio spelling to the standard 1x1 | 4x5 | 9x16 | 16x9."""
    key = _RATIO_CANON.get(str(ratio).strip())
    if key is None:
        raise ValueError(f"unknown ratio {ratio!r}; expected one of {sorted(set(_RATIO_CANON))}")
    return key


def today_utc() -> str:
    """YYYYMMDD in coordinated universal time, per ISO 8601 basic date."""
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d")


def _region_field(region: str) -> str:
    """Upper-case, hyphen-delimited region. Spaces and slashes collapse to hyphens."""
    s = str(region).strip().upper()
    s = re.sub(r"[^A-Z0-9]+", "-", s)
    return s.strip("-") or "US"


def _version_field(version: str | int) -> str:
    """Zero-padded vNN. Accepts 1, '1', 'v1', 'v01'."""
    if isinstance(version, int):
        return f"v{version:02d}"
    s = str(version).strip().lower().lstrip("v")
    if not s.isdigit():
        return "v01"
    return f"v{int(s):02d}"


def build_iso_name(
    product: str,
    region: str,
    locality: str,
    channel: str,
    ratio: str,
    date: str | None = None,
    version: str | int = "v01",
) -> str:
    """Produce the exact 7-field ISO creative filename ending in .png.

    Missing/loose inputs are normalized: product/locality/channel are slugified,
    region is upper-cased, ratio is canonicalized, date defaults to today UTC,
    version zero-pads. The result always matches ISO_NAME_RE.
    """
    product_f = slugify(product)
    region_f = _region_field(region)
    locality_f = slugify(locality) or "national"
    channel_f = slugify(channel) or "instagram"
    ratio_f = canon_ratio(ratio)
    date_f = date or today_utc()
    version_f = _version_field(version)

    name = (
        f"KODIAK-CAKES-{product_f}-{region_f}-{locality_f}-"
        f"{channel_f}-{ratio_f}-{date_f}-{version_f}.png"
    )
    if not ISO_NAME_RE.match(name):
        raise ValueError(f"built name failed ISO validation: {name}")
    return name


def derive_locality(region: str, place: str | None = None, retailer: str | None = None) -> str:
    """Best-effort locality when the brief has no explicit field.

    Prefers place+retailer; falls back to the trailing region segment; then 'national'.
    """
    parts: list[str] = []
    if place:
        parts.append(slugify(place))
    if retailer:
        parts.append(slugify(retailer))
    combined = "-".join(p for p in parts if p)
    if combined:
        return combined
    # fall back to the most specific region segment (e.g. US-MW -> mw)
    region_segs = [seg for seg in re.split(r"[^A-Za-z0-9]+", str(region)) if seg]
    if len(region_segs) > 1:
        return slugify(region_segs[-1])
    return "national"
