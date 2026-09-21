"""Regional scoreboard data-build contract tests.

Guards three invariants for the adopted Kodiak regional scoreboard:
  1. every frontend places[] market_code resolves in the full keyed file
  2. every value in the full keyed file validates against the mirrored schema
  3. the lite file has exactly the same key set as the full file

The frontend's 75 market codes are parsed from the places[] array in
web/kodiak-posts-for-todays-frontier/js/data-core.js (the codes it will look up
at runtime). The inline places[] array was extracted from index.html into this
classic-script sibling. Parsing is preferred over a hardcoded list so the test
tracks the UI.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data" / "localization"
FULL = DATA / "regional-scoreboard.json"
LITE = DATA / "regional-scoreboard-lite.json"
SCHEMA = DATA / "regional-scoreboard.schema.json"
FRONTEND_DATA = (
    REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js" / "data-core.js"
)

EXPECTED_FRONTEND_CODES = 78

# import the build script's validator so the test enforces the same contract
_spec = importlib.util.spec_from_file_location(
    "build_regional_scoreboard",
    REPO_ROOT / "scripts" / "build-regional-scoreboard.py",
)
assert _spec and _spec.loader
_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build)


def _load(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def frontend_market_codes() -> list[str]:
    """Parse the places[] market values from the frontend js/data-core.js."""
    text = FRONTEND_DATA.read_text(encoding="utf-8")
    # the places array is a JS literal; each entry carries market:"US-..."
    codes = re.findall(r'market:"(US-[A-Z]{1,3}-[A-Z0-9 -]+)"', text)
    # de-dupe preserving order
    seen: dict[str, None] = {}
    for c in codes:
        seen.setdefault(c, None)
    return list(seen)


def test_frontend_code_count_is_stable() -> None:
    codes = frontend_market_codes()
    assert len(codes) == EXPECTED_FRONTEND_CODES, (
        f"expected {EXPECTED_FRONTEND_CODES} frontend market codes, found {len(codes)}"
    )


def test_full_covers_every_frontend_code() -> None:
    full = _load(FULL)
    codes = frontend_market_codes()
    missing = [c for c in codes if c not in full]
    assert not missing, f"full keyed file missing frontend codes: {missing}"


def test_every_full_value_validates_against_schema() -> None:
    full = _load(FULL)
    schema = _load(SCHEMA)
    failures: list[str] = []
    for key, rec in full.items():
        try:
            _build.validate_record(rec, schema, key)
        except _build.ValidationError as exc:  # pragma: no cover - failure path
            failures.append(str(exc))
    assert not failures, "schema validation failures:\n" + "\n".join(failures)


def test_lite_key_set_matches_full() -> None:
    full = _load(FULL)
    lite = _load(LITE)
    assert set(lite) == set(full), (
        "lite/full key mismatch: "
        f"only_full={sorted(set(full) - set(lite))} "
        f"only_lite={sorted(set(lite) - set(full))}"
    )


def test_lite_shape_has_ui_critical_fields() -> None:
    lite = _load(LITE)
    sample = lite["US-MW-PARKCITY-84098"]
    assert set(sample) == {
        "featured_frontier",
        "languages",
        "city_center",
        "design_palette",
        "campaign_type_fit",
    }
    assert "hook" in sample["featured_frontier"]
    assert "photo_cue" in sample["featured_frontier"]


def test_clean_alias_strips_annotation() -> None:
    # annotation stripped, code preserved
    assert _build.clean_alias("US-SE-ATL (Publix heartland sister)") == "US-SE-ATL"
    # internal space in a real code is preserved (not split on whitespace)
    assert _build.clean_alias("US-SW-EL PASO (border labor shed)") == "US-SW-EL PASO"
    # non-conforming token after strip is skipped
    assert _build.clean_alias("not-a-code") is None


def test_wasatch_alias_resolves_to_parkcity() -> None:
    full = _load(FULL)
    # both the primary and a clean alias resolve to the same park-city record
    assert "US-MW-PARKCITY-84098" in full
    assert "US-MW-WASATCH" in full
    assert full["US-MW-WASATCH"]["region_id"] == full["US-MW-PARKCITY-84098"]["region_id"]
