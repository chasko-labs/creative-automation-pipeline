#!/usr/bin/env python3
"""Build the Kodiak regional scoreboard artifacts for the pipeline.

Reads the adopted source-of-truth region records (73 files, one per region) plus
the schema from a committed, self-contained location inside the pipeline. Validates
every record against the schema, then emits two derived artifacts:

  data/localization/regional-scoreboard.json       full keyed file (backend)
  data/localization/regional-scoreboard-lite.json  lean UI subset (frontend)

Both are keyed by market_code AND by every clean alias (see ALIAS-STRIP below), so
US-MW-PARKCITY-84098 (primary) and US-MW-WASATCH (alias) both resolve to park-city.

Idempotent + re-runnable: re-running with unchanged source yields byte-identical
output (records are sorted by market_code, aliases sorted, json dumped with sorted
keys). FAILS LOUDLY (non-zero exit, raised exception) if any record does not validate
against the schema, so a future re-seed cannot silently ship a broken record.

This build depends only on the pipeline's own committed copy of the records + schema
under data/localization/regional-scoreboard/ -- never on the heraldstack-mcp planning
tree. Validation is dependency-free (no jsonschema package) and reads the mirrored
schema as the contract, so a schema change is honored on the next build.

usage:
  uv run python scripts/build-regional-scoreboard.py
  uv run python scripts/build-regional-scoreboard.py --source <dir> --schema <file>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# committed, self-contained source location inside the pipeline (NOT heraldstack-mcp)
DEFAULT_SOURCE = REPO_ROOT / "data" / "localization" / "regional-scoreboard" / "regions"
DEFAULT_SCHEMA = REPO_ROOT / "data" / "localization" / "regional-scoreboard.schema.json"

OUT_FULL = REPO_ROOT / "data" / "localization" / "regional-scoreboard.json"
OUT_LITE = REPO_ROOT / "data" / "localization" / "regional-scoreboard-lite.json"

# market_code contract, mirrors the schema pattern for market_code.
# NOTE: spaces are legal INSIDE a code (e.g. "US-SW-EL PASO"), so alias annotation
# stripping keys on the parenthetical " (", never on bare whitespace -- see below.
MARKET_CODE_RE = re.compile(r"^US-[A-Z]{1,3}-[A-Z0-9 -]+$")

# lite palette trim thresholds -- applied only if the lite payload is large.
PALETTE_TRIM_COLORS = 3
PALETTE_TRIM_TEXTURES = 3
LITE_SIZE_BUDGET_BYTES = 200 * 1024


class ValidationError(Exception):
    """Raised when a record does not conform to the schema. Fails the build loud."""


def clean_alias(raw: str) -> str | None:
    """Strip the human annotation from an alias token and return the bare market_code.

    ALIAS-STRIP: aliases are authored as strings like
        "US-SE-ATL (Publix heartland sister)"
    The market_code is the token before the first annotation, which is always a
    parenthetical introduced by " (". We split on " (" and take the head, then trim.
    We deliberately do NOT split on bare whitespace: a valid code can contain an
    internal space (e.g. "US-SW-EL PASO"), and splitting on whitespace would corrupt
    it. Tokens that do not match the market-code pattern after stripping are skipped
    (return None) so junk never lands in the key map.
    """
    token = raw.split(" (", 1)[0].strip()
    if MARKET_CODE_RE.match(token):
        return token
    return None


# --------------------------------------------------------------------------- #
# minimal, dependency-free JSON Schema validator.
# supports the subset the scoreboard schema uses: type, required, properties,
# pattern, enum, minimum/maximum, minLength/maxLength, items, patternProperties,
# additionalProperties. reads the mirrored schema so the contract stays in one place.
# --------------------------------------------------------------------------- #

_TYPE_MAP: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "array": (list,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
}


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return isinstance(value, _TYPE_MAP[expected])


def _validate(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    expected_type = schema.get("type")
    if expected_type and not _type_ok(value, expected_type):
        errors.append(f"{path}: expected {expected_type}, got {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in enum {schema['enum']}")

    if isinstance(value, str):
        pat = schema.get("pattern")
        if pat and not re.search(pat, value):
            errors.append(f"{path}: {value!r} does not match pattern {pat}")
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than minLength {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than maxLength {schema['maxLength']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, dict):
        _validate_object(value, schema, path, errors)

    if isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{i}]", errors)


def _validate_object(
    value: dict[str, Any], schema: dict[str, Any], path: str, errors: list[str]
) -> None:
    for req in schema.get("required", []):
        if req not in value:
            errors.append(f"{path}: missing required field {req!r}")

    props = schema.get("properties", {})
    pattern_props = schema.get("patternProperties", {})
    additional = schema.get("additionalProperties", True)

    for key, sub in value.items():
        child = f"{path}.{key}" if path else key
        if key in props:
            _validate(sub, props[key], child, errors)
            continue
        matched = False
        for pat, pat_schema in pattern_props.items():
            if re.search(pat, key):
                _validate(sub, pat_schema, child, errors)
                matched = True
                break
        if matched:
            continue
        if props or pattern_props:
            if additional is False:
                errors.append(f"{child}: additional property not allowed")
            elif isinstance(additional, dict):
                _validate(sub, additional, child, errors)


def validate_record(record: dict[str, Any], schema: dict[str, Any], source: str) -> None:
    """Validate one record; raise ValidationError listing every failure."""
    errors: list[str] = []
    _validate(record, schema, "", errors)
    if errors:
        joined = "\n  ".join(errors)
        raise ValidationError(f"{source} failed schema validation:\n  {joined}")


# --------------------------------------------------------------------------- #
# build
# --------------------------------------------------------------------------- #


def load_records(source: Path) -> list[tuple[str, dict[str, Any]]]:
    files = sorted(source.glob("*.json"))
    if not files:
        raise SystemExit(f"no region records found under {source}")
    out: list[tuple[str, dict[str, Any]]] = []
    for f in files:
        with f.open(encoding="utf-8") as fh:
            out.append((f.name, json.load(fh)))
    return out


def build_full_map(
    records: list[tuple[str, dict[str, Any]]],
) -> dict[str, dict[str, Any]]:
    """market_code (primary) + every clean alias -> full record. primary wins on clash."""
    keyed: dict[str, dict[str, Any]] = {}
    primaries: set[str] = set()
    for name, rec in records:
        code = rec["market_code"]
        keyed[code] = rec
        primaries.add(code)
    for name, rec in records:
        for raw in rec.get("aliases", []):
            token = clean_alias(raw)
            if token is None:
                continue
            # never let an alias shadow a primary key
            if token in primaries:
                continue
            keyed.setdefault(token, rec)
    return {k: keyed[k] for k in sorted(keyed)}


def to_lite(rec: dict[str, Any], trim_palette: bool) -> dict[str, Any]:
    """Project a full record down to the UI-critical fields the frontend inlines."""
    ff = rec.get("featured_frontier", {})
    palette = rec.get("design_palette", {})
    colors = palette.get("colors", [])
    textures = palette.get("textures", [])
    if trim_palette:
        colors = colors[:PALETTE_TRIM_COLORS]
        textures = textures[:PALETTE_TRIM_TEXTURES]
    campaign_fit = {
        ctype: {"fit": cfg.get("fit"), "angle": cfg.get("angle")}
        for ctype, cfg in rec.get("campaign_type_fit", {}).items()
    }
    return {
        "featured_frontier": {
            "hook": ff.get("hook"),
            "photo_cue": ff.get("photo_cue"),
        },
        "languages": [
            {"lang_code": lang.get("lang_code"), "lang_name": lang.get("lang_name")}
            for lang in rec.get("languages", [])
        ],
        "city_center": {
            "name": rec.get("city_center", {}).get("name"),
            "landmark": rec.get("city_center", {}).get("landmark"),
        },
        "design_palette": {
            "colors": [{"name": c.get("name"), "hex": c.get("hex")} for c in colors],
            "textures": textures,
        },
        "campaign_type_fit": campaign_fit,
    }


def build_lite_map(
    full_map: dict[str, dict[str, Any]], trim_palette: bool
) -> dict[str, Any]:
    return {code: to_lite(rec, trim_palette) for code, rec in full_map.items()}


def dump(path: Path, data: Any) -> int:
    text = json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the Kodiak regional scoreboard.")
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    ap.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    args = ap.parse_args()

    with args.schema.open(encoding="utf-8") as fh:
        schema = json.load(fh)

    records = load_records(args.source)

    # validate FIRST -- fail loud before writing anything
    for name, rec in records:
        validate_record(rec, schema, name)

    full_map = build_full_map(records)

    # first pass: full palette. trim only if the lite payload blows the budget.
    lite_map = build_lite_map(full_map, trim_palette=False)
    lite_bytes = len(
        (json.dumps(lite_map, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        )
    )
    trimmed = False
    if lite_bytes > LITE_SIZE_BUDGET_BYTES:
        lite_map = build_lite_map(full_map, trim_palette=True)
        trimmed = True

    full_size = dump(OUT_FULL, full_map)
    lite_size = dump(OUT_LITE, lite_map)

    primaries = sum(1 for _, r in records)
    print(f"records validated : {len(records)}")
    print(f"primary codes     : {primaries}")
    print(f"total keys (+alias): {len(full_map)}")
    print(f"{OUT_FULL.relative_to(REPO_ROOT)} : {full_size:,} bytes")
    print(f"{OUT_LITE.relative_to(REPO_ROOT)} : {lite_size:,} bytes"
          f"{' (palette trimmed to top 3)' if trimmed else ''}")
    if lite_size > LITE_SIZE_BUDGET_BYTES:
        print(f"WARNING: lite payload {lite_size:,} bytes exceeds "
              f"{LITE_SIZE_BUDGET_BYTES:,} budget", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
