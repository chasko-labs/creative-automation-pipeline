"""Complex-text shaping for the Pillow compose layer.

Pillow does NO complex-text shaping. Arabic glyphs have positional presentation forms
(isolated/initial/medial/final) and the script is right-to-left; without reshaping +
bidi reordering, ImageDraw.text renders isolated letters left-to-right — unreadable.
`shape_for_pillow` is the single call the compose layer makes before ImageDraw.text:
RTL/Arabic gets reshaped + bidi-reordered, everything else passes through unchanged.

Myanmar + Devanagari conjunct shaping is not done here — it needs libraqm (a system lib
baked into infra/generate.Dockerfile), which Pillow uses transparently once present.
This module only covers the reshape + bidi step that has to happen in Python before
the draw call.
"""
from __future__ import annotations

# defensive import: the compose layer stays importable in envs without the shaping deps
# (offline dev, CI without the full pipeline extras). Absence degrades to pass-through
# rather than crashing the whole module import.
try:
    import arabic_reshaper
    from bidi.algorithm import get_display
except ImportError:  # pragma: no cover - exercised only when deps absent
    arabic_reshaper = None  # type: ignore
    get_display = None  # type: ignore

# languages whose loc-lines are RTL / need Arabic presentation-form reshaping.
# matches the .loc-line[lang="ar"] direction:rtl rule in the frontend.
_RTL_LANGS = {"ar", "fa", "ur", "ps", "he", "yi"}


def _is_rtl(lang: str | None) -> bool:
    if not lang:
        return False
    return lang.split("-", 1)[0].lower() in _RTL_LANGS


def shape_for_pillow(text: str, lang: str | None = None) -> str:
    """Return text ready for ImageDraw.text.

    RTL/Arabic text is reshaped (isolated glyphs -> positional presentation forms) and
    bidi-reordered (logical -> visual order). LTR text is returned unchanged. If the
    shaping deps are not installed, text is returned unchanged so the caller never breaks.
    """
    if not text or not _is_rtl(lang):
        return text
    if arabic_reshaper is None or get_display is None:
        # deps absent — cannot shape; return logical order rather than raising
        return text
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)
