"""Brand-copy source + fallback injection — OFFLINE, cred-free."""
from __future__ import annotations

import re

from creative_automation import brand_copy
from creative_automation.platform_copy import (
    PLATFORM_SPECS,
    fallback_platform_copy,
)

_ALLCAPS_RE = re.compile(r"(?<!#)\bKODIAK\b")
_BARE_RE = re.compile(r"(?<!#)\bKodiak\b(?!\s+(Cakes?|Park\s+City))")
_MARK_RE = re.compile(r"\(R\)|®")


def test_taglines_match_iso_naming_exactly():
    assert brand_copy.TAGLINE_EPIC == "Feeding Epic Days & Wilder Lives"
    assert brand_copy.TAGLINE_FRONTIER == "Nourishment for Today's Frontier"
    assert brand_copy.TAGLINE_KEEP_IT_WILD == "Keep It Wild"


def test_voices_cover_three_pillars():
    for voice in ("adventurous", "nourishing", "rugged"):
        assert voice in brand_copy.VOICES


def test_voice_tone_reference_loads():
    raw = brand_copy.load_voice_tone()
    assert raw.get("adventurous") and raw.get("nourishing")


def test_fallback_frames_cover_every_platform_kind():
    kinds = {spec["kind"] for spec in PLATFORM_SPECS.values()}
    assert kinds <= set(brand_copy.FALLBACK_HEADLINE_FRAMES)
    assert kinds <= set(brand_copy.FALLBACK_BODY_FRAMES)


def test_fallback_copy_uses_structured_source():
    from creative_automation.platform_copy import _body_for, _fallback_headline

    assert _fallback_headline("Fuel morning", "Power Cakes", "hooky") == brand_copy.fallback_headline(
        "hooky", "Fuel morning", "Power Cakes"
    )
    assert _body_for("seo", "h", "Power Cakes", "US-UT") == brand_copy.fallback_body(
        "seo", "Power Cakes", "US-UT"
    )


def test_fallback_has_no_marks_no_bare_brand_no_prohibited_claims():
    copy = fallback_platform_copy("Fuel your morning", "Power Cakes", "US-UT")
    for entry in copy.values():
        for key in ("headline", "body", "title", "description", "post"):
            text = entry.get(key, "")
            if not text:
                continue
            assert _ALLCAPS_RE.search(text) is None, text
            assert _BARE_RE.search(text) is None, text
            assert _MARK_RE.search(text) is None, text
            assert not any(ord(ch) > 0x2700 for ch in text), text
            for hint in brand_copy.PROHIBITED_CLAIM_HINTS:
                assert hint.lower() not in text.lower(), text


def test_fallback_carries_approved_claims_and_taglines():
    copy = fallback_platform_copy("Fuel your morning", "Power Cakes", "US-UT")
    blob = " ".join(
        (e.get("headline", "") or "") + " " + (e.get("body", "") or "") for e in copy.values()
    )
    assert "100% whole grain" in blob
    assert (
        brand_copy.TAGLINE_EPIC in blob or brand_copy.TAGLINE_FRONTIER in blob
    )
