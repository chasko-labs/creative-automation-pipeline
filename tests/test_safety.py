"""Content-safety gate — clean corporate copy passes, unsafe/off-brand text is flagged."""
import pytest

from creative_automation.safety import (
    UnsafeTextError,
    check_text,
    redact,
    reject_if_unsafe,
)


def test_clean_corporate_copy_passes():
    text = "Protein-packed whole grains for your family's frontier breakfast."
    result = check_text(text)
    assert result["clean"] is True
    assert result["flagged"] == []


def test_profanity_is_flagged():
    result = check_text("This is damn good, no bullshit.")
    assert result["clean"] is False
    cats = {f["category"] for f in result["flagged"]}
    assert "profanity" in cats


def test_political_is_flagged():
    result = check_text("Vote for the best breakfast, no matter if you're liberal or conservative.")
    assert result["clean"] is False
    cats = {f["category"] for f in result["flagged"]}
    assert "political" in cats


def test_corporate_tone_tick_is_flagged():
    result = check_text("We absolutely love this product.")
    assert result["clean"] is False
    flagged_terms = {f["term"] for f in result["flagged"]}
    assert "absolutely" in flagged_terms
    assert any(f["category"] == "corporate_tone" for f in result["flagged"])


def test_word_boundary_no_false_positive():
    # "ass" is a profanity term but must not trip inside "pass" / "grass" / "class"
    result = check_text("Pass the grass-fed butter to the whole class.")
    assert result["clean"] is True


def test_slur_seed_placeholder_never_matches():
    # the slur seed is a placeholder; ordinary text must stay clean
    result = check_text("A warm, welcoming breakfast for every family.")
    assert result["clean"] is True


def test_redact_replaces_flagged_terms():
    out = redact("This is damn good.")
    assert "damn" not in out.lower()
    assert "[redacted]" in out


def test_reject_if_unsafe_raises():
    with pytest.raises(UnsafeTextError):
        reject_if_unsafe("We absolutely crushed it, you bastard.")


def test_reject_if_unsafe_passes_clean_text():
    text = "Fuel your morning with whole grains."
    assert reject_if_unsafe(text) == text
