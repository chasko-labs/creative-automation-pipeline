"""text_shaping.shape_for_pillow — the one call the compose layer makes before ImageDraw.text.

Pillow does no complex-text shaping, so Arabic has to be reshaped (isolated glyphs ->
positional presentation forms) and bidi-reordered (logical -> visual) here or it renders
unreadable. Latin must pass through untouched. These are the two contracts the compose
layer leans on.
"""
import pytest

from creative_automation.text_shaping import shape_for_pillow

# skip the Arabic contract if the shaping deps are absent — the module degrades to
# pass-through by design, so asserting a transform there would be a false failure.
try:
    import arabic_reshaper  # noqa: F401
    from bidi.algorithm import get_display  # noqa: F401

    _HAS_SHAPING = True
except ImportError:
    _HAS_SHAPING = False


def test_latin_passes_through_unchanged():
    text = "Nourishment for Today's Frontier"
    assert shape_for_pillow(text, "en") == text


def test_latin_passes_through_when_lang_none():
    assert shape_for_pillow("Kodiak Cakes", None) == "Kodiak Cakes"


def test_empty_string_is_noop():
    assert shape_for_pillow("", "ar") == ""


@pytest.mark.skipif(not _HAS_SHAPING, reason="arabic-reshaper/python-bidi not installed")
def test_arabic_reshapes_and_reverses():
    # logical-order Arabic: three separate letters that must join + reorder RTL
    src = "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"  # "العربية"
    out = shape_for_pillow(src, "ar")
    # shaping must change the string — presentation forms + bidi visual order differ
    # from the raw logical codepoints
    assert out != src
    # visual order reverses the first logical char to the end
    assert out[-1] == src[0] or out[0] != src[0]
    # reshaped output pulls in Arabic presentation-form codepoints (U+FB50..U+FEFF)
    assert any("\uFB50" <= ch <= "\uFEFF" for ch in out)


@pytest.mark.skipif(not _HAS_SHAPING, reason="arabic-reshaper/python-bidi not installed")
def test_arabic_dialect_tag_still_shapes():
    src = "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"
    assert shape_for_pillow(src, "ar-EG") != src
