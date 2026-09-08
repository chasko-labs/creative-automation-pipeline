"""Brand-term policy (#244) — OFFLINE, cred-free.

Policy (decided 2026-09-08, documented in localize_service module docstring):
slogans and marks never translate. BRAND_TERMS ship verbatim (canonical casing)
in every localized string; everything else translates around them.

These tests mock every transport boundary and prove the structural guarantee:
even a maximally hostile MT engine (uppercases everything, i.e. "translates" the
slogan too) cannot move a brand term, gaps still translate, stale precomputed
hits are bypassed, and pure-term text never wastes an MT call.
"""
from creative_automation import localize_memory, localize_service
from creative_automation.localize_service import (
    BRAND_TERMS,
    _bedrock_prompt,
    _terms_in,
    localize,
    translate_with_terms,
)

MARKET = "US-SW-LASCRUCES"
WITH_TERM = "Keep It Wild mornings fuel the frontier"


def _no_precompute(monkeypatch):
    monkeypatch.setattr(localize_memory, "get_precomputed", lambda *a, **k: None)
    monkeypatch.setattr(localize_service.localize_memory, "get_precomputed", lambda *a, **k: None)


def _has_creds(monkeypatch, value: bool):
    monkeypatch.setattr(localize_service, "_has_creds", lambda: value)


def _hostile(seg: str) -> str:
    """Fake MT that mangles everything it touches (uppercases)."""
    return seg.upper()


def test_terms_list_is_documented_and_nonempty():
    assert "Keep It Wild" in BRAND_TERMS
    assert "KODIAK" in BRAND_TERMS
    assert len(BRAND_TERMS) >= 2


def test_terms_in_finds_canonical_forms():
    assert _terms_in("keep it wild and KODIAK breakfast") == ["Keep It Wild", "KODIAK"]
    assert _terms_in("nothing branded here") == []


def test_hostile_mt_cannot_move_terms():
    out = translate_with_terms(WITH_TERM, _hostile)
    assert "Keep It Wild" in out  # verbatim, not "KEEP IT WILD"
    assert "KEEP IT WILD" not in out
    assert "MORNINGS FUEL THE FRONTIER" in out  # gaps still translated


def test_canonical_casing_restored():
    out = translate_with_terms("keep it wild mornings", _hostile)
    assert out.startswith("Keep It Wild")


def test_boundary_whitespace_reglued():
    # MT drops the leading space on short gaps — words must not fuse.
    out = translate_with_terms("Keep It Wild mornings", lambda s: "las mañanas")
    assert out == "Keep It Wild las mañanas"


def test_pure_term_text_never_calls_mt():
    def boom(seg):
        raise AssertionError("MT called for pure-term text")

    assert translate_with_terms("Keep It Wild", boom) == "Keep It Wild"


def test_term_free_text_passes_through_whole():
    seen = []
    out = translate_with_terms("plain flapjacks", lambda s: seen.append(s) or "X")
    assert out == "X" and seen == ["plain flapjacks"]


def test_localize_es_preserves_term_live(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, True)
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda text, lang, **k: text.upper())
    res = localize(WITH_TERM, MARKET, "es")
    assert res["provider"] == "amazon-translate"
    assert "Keep It Wild" in res["text"]
    assert "KEEP IT WILD" not in res["text"]


def test_localize_pt_preserves_term_live(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, True)
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda text, lang, **k: text.upper())
    res = localize(WITH_TERM, MARKET, "pt")
    assert "Keep It Wild" in res["text"]


def test_stale_precompute_hit_bypassed_to_live(monkeypatch):
    # hit mangled the slogan (pre-policy artifact) -> ignored, live MT serves
    monkeypatch.setattr(
        localize_service.localize_memory,
        "get_precomputed",
        lambda *a, **k: {"text": "MANTÉNLO SALVAJE mornings", "provider": "precomputed", "source": "dynamodb"},
    )
    _has_creds(monkeypatch, True)
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda text, lang, **k: text.upper())
    res = localize(WITH_TERM, MARKET, "es")
    assert res["provider"] == "amazon-translate"
    assert "Keep It Wild" in res["text"]


def test_fresh_precompute_hit_with_terms_served(monkeypatch):
    # hit already complies -> still the scale path, no live call
    monkeypatch.setattr(
        localize_service.localize_memory,
        "get_precomputed",
        lambda *a, **k: {"text": "Keep It Wild mañanas", "provider": "precomputed", "source": "dynamodb"},
    )
    monkeypatch.setattr(
        localize_service, "_amazon_translate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("live call on compliant hit")),
    )
    res = localize(WITH_TERM, MARKET, "es")
    assert res["provider"] == "precomputed"
    assert "Keep It Wild" in res["text"]


def test_bedrock_prompt_carries_term_instruction():
    prompt = _bedrock_prompt("Keep It Wild mornings", "ilo", MARKET)
    for term in BRAND_TERMS:
        assert term in prompt
    assert "verbatim" in prompt.lower()
