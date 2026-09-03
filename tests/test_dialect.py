"""Dialect knowledge bases — load, trap coverage, and diacritic round-trip.

A diacritic is meaning, not cosmetic (Vietnamese tone marks, Portuguese/French
accents, Spanish enye). These tests fail loudly if any dialect file loses a
codepoint or drops its trap rows.
"""
import json
from pathlib import Path

import pytest

from creative_automation.locales import (
    DialectTerm,
    dialect_traps,
    load_dialect,
    resolve_dialect_terms,
)

DIALECT_DIR = Path(__file__).parents[1] / "data" / "localization" / "dialect"

# (region, lang) -> a trap term_local that MUST survive with its exact diacritics
EXPECTED = {
    ("US-SW", "es"): "hotcakes",
    ("US-FL-CUBAN", "es"): "panqueque",
    ("US-FL", "ht"): "manje maten",
    ("US-SEATTLE", "vi"): "ph\u1edf",           # pho, o-horn-hook
    ("US-VT", "fr"): "d\u00e9jeuner",           # dejeuner, e-acute
    ("US-PARKCITY", "pt"): "caf\u00e9 da manh\u00e3",  # e-acute + a-tilde
}

ALL_PAIRS = list(EXPECTED.keys())


@pytest.mark.parametrize("region,lang", ALL_PAIRS)
def test_dialect_loads_and_has_traps(region, lang):
    terms = load_dialect(region, lang)
    assert len(terms) >= 8, f"{region}/{lang} should seed 8-15 rows, got {len(terms)}"
    assert all(isinstance(t, DialectTerm) for t in terms)
    traps = dialect_traps(region, lang)
    assert len(traps) >= 2, f"{region}/{lang} must carry trap rows, got {len(traps)}"


@pytest.mark.parametrize("region,lang", ALL_PAIRS)
def test_expected_trap_term_present(region, lang):
    locals_ = {t.term_local for t in load_dialect(region, lang)}
    assert EXPECTED[(region, lang)] in locals_


def test_es_sw_and_cuban_contradict():
    # the two Spanish KBs deliberately invert — hotcakes (SW) vs panqueque (Cuban)
    sw = {t.term_local for t in load_dialect("US-SW", "es")}
    cuban = {t.term_local for t in load_dialect("US-FL-CUBAN", "es")}
    assert "hotcakes" in sw and "hotcakes" not in cuban
    assert "panqueque" in cuban and "panqueque" not in sw


def test_ht_fl_does_not_default_to_french():
    # Haitian Creole breakfast/bread must be Kreyol, not French
    locals_ = {t.term_local for t in load_dialect("US-FL", "ht")}
    assert "manje maten" in locals_ and "pen" in locals_
    assert "petit-d\u00e9jeuner" not in locals_ and "pain" not in locals_


def test_fr_vt_dejeuner_is_breakfast():
    terms = {t.term_local: t for t in load_dialect("US-VT", "fr")}
    assert "d\u00e9jeuner" in terms
    assert terms["d\u00e9jeuner"].category == "trap"
    assert "breakfast" in terms["d\u00e9jeuner"].usage_note.lower()
    assert "bleuets" in terms  # not myrtilles


def test_diacritics_survive_round_trip():
    """Every non-ascii codepoint on disk must reload byte-identical."""
    checks = {
        "dialect-vi-seattle.jsonl": ["ph\u1edf", "b\u00f2"],       # tone marks
        "dialect-pt-parkcity.jsonl": ["a\u00e7\u00facar", "p\u00e3o", "manh\u00e3"],
        "dialect-fr-vt.jsonl": ["d\u00e9jeuner", "d\u00eener", "cr\u00eape"],
        "dialect-es-sw.jsonl": ["ni\u00f1o"],                       # enye
        "dialect-es-fl-cuban.jsonl": ["caf\u00e9", "az\u00facar"],
        "dialect-ht-fl.jsonl": ["cr\u00eape", "caf\u00e9"],
    }
    for fname, needles in checks.items():
        raw = (DIALECT_DIR / fname).read_text(encoding="utf-8")
        rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
        blob = json.dumps(rows, ensure_ascii=False)
        for needle in needles:
            assert needle in raw, f"{needle!r} missing from raw {fname}"
            assert needle in blob, f"{needle!r} lost on json round-trip in {fname}"


def test_files_are_utf8_no_ascii_escapes():
    # ensure_ascii=False was used — no \\uXXXX escape sequences on disk
    for path in DIALECT_DIR.glob("*.jsonl"):
        raw = path.read_text(encoding="utf-8")
        assert "\\u" not in raw, f"{path.name} contains ascii-escaped unicode"


def test_resolve_dialect_terms_flags_standard():
    # standard 'myrtilles' in copy should suggest the Quebec 'bleuets'
    hits = resolve_dialect_terms("des myrtilles fraiches", "US-VT", "fr")
    matched = {h["suggest_local"] for h in hits}
    assert "bleuets" in matched
    assert hits[0]["is_trap"] is True  # traps sort first


def test_resolve_unknown_region_is_empty():
    assert resolve_dialect_terms("anything", "US-NOWHERE", "xx") == []
