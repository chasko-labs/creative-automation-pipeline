"""POST /localize seam — resolution-order contract.

The seam has a fixed resolution order the frontend depends on:
  precomputed (DynamoDB) -> live MT routed by language -> offline mock.

These tests mock every transport boundary (DynamoDB get_precomputed, Amazon Translate,
Bedrock Converse) and the credential gate so no test touches AWS. The highest-value
assertions are the ethics guard (nv/zip must NOT call any translate/bedrock path) and the
precompute-hit scale path (most reads should resolve there with provider=precomputed).
"""
from creative_automation import localize_memory, localize_service
from creative_automation.localize_service import localize

MARKET = "US-SW-LASCRUCES"
BASE = "Nourishment for Today's Frontier"


def _no_precompute(monkeypatch):
    """Force a DynamoDB miss so tests exercise the live/offline branches."""
    monkeypatch.setattr(localize_memory, "get_precomputed", lambda *a, **k: None)
    monkeypatch.setattr(localize_service.localize_memory, "get_precomputed", lambda *a, **k: None)


def _has_creds(monkeypatch, value: bool):
    monkeypatch.setattr(localize_service, "_has_creds", lambda: value)


def test_precomputed_hit_returns_provider_precomputed(monkeypatch):
    # a DynamoDB hit short-circuits before any live call
    def fake_get(text, market, lang):
        assert (text, market, lang) == (BASE, MARKET, "es")
        return {"text": "Nutrición para la Frontera de Hoy", "provider": "precomputed", "source": "dynamodb"}

    monkeypatch.setattr(localize_service.localize_memory, "get_precomputed", fake_get)
    # guard: no live path may fire on a precompute hit
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("translate called on precompute hit")))
    monkeypatch.setattr(localize_service, "_bedrock_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("bedrock called on precompute hit")))

    res = localize(BASE, MARKET, "es")
    assert res["provider"] == "precomputed"
    assert res["source"] == "dynamodb"
    assert res["lang"] == "es"
    assert res["text"] == "Nutrición para la Frontera de Hoy"


def test_supported_lang_miss_routes_to_amazon_translate(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, True)
    called = {}

    def fake_translate(text, lang, source_lang="en"):
        called["lang"] = lang
        return "Nutrición para la Frontera de Hoy"

    monkeypatch.setattr(localize_service, "_amazon_translate", fake_translate)
    # bedrock must NOT be called for an Amazon-Translate-supported lang
    monkeypatch.setattr(localize_service, "_bedrock_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("bedrock called for supported lang")))

    res = localize(BASE, MARKET, "es")
    assert res["provider"] == "amazon-translate"
    assert res["source"] == "live"
    assert called["lang"] == "es"
    assert res.get("low_confidence") is None


def test_gap_lang_routes_to_bedrock_low_confidence(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, True)
    called = {}

    def fake_bedrock(text, lang, market):
        called["lang"] = lang
        return "protina para iti frontier"  # ilo (Ilocano) — a machine-able gap

    monkeypatch.setattr(localize_service, "_bedrock_translate", fake_bedrock)
    # amazon translate must NOT be called for a gap lang
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("amazon-translate called for gap lang")))

    res = localize(BASE, MARKET, "ilo")
    assert res["provider"] == "bedrock"
    assert res["source"] == "live"
    assert res["low_confidence"] is True
    assert called["lang"] == "ilo"


def test_navajo_returns_human_required_no_mt_call(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, True)  # creds present — still must NOT machine translate
    # any transport call for nv is an ethics violation — make them fail the test loudly
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("translate called for nv")))
    monkeypatch.setattr(localize_service, "_bedrock_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("bedrock called for nv")))

    res = localize(BASE, MARKET, "nv")
    assert res["provider"] == "human-required"
    assert res["source"] == "original"
    assert res["human_pending"] is True
    assert res["text"] == BASE  # original text, unchanged


def test_zapotec_returns_human_required_no_mt_call(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, True)
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("translate called for zip")))
    monkeypatch.setattr(localize_service, "_bedrock_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("bedrock called for zip")))

    res = localize(BASE, MARKET, "zip")
    assert res["provider"] == "human-required"
    assert res["source"] == "original"
    assert res["human_pending"] is True
    assert res["text"] == BASE


def test_no_creds_returns_mock(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, False)
    # no live path may fire with no creds
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("translate called with no creds")))
    monkeypatch.setattr(localize_service, "_bedrock_translate", lambda *a, **k: (_ for _ in ()).throw(AssertionError("bedrock called with no creds")))

    res = localize(BASE, MARKET, "es")
    assert res["source"] == "mock"
    assert res["provider"] == "offline-dictionary"
    assert res["text"] == BASE


def test_english_passthrough(monkeypatch):
    _no_precompute(monkeypatch)
    res = localize(BASE, MARKET, "en")
    assert res["source"] == "original"
    assert res["provider"] == "passthrough"
    assert res["text"] == BASE


def test_amazon_translate_transport_failure_falls_to_mock(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, True)
    monkeypatch.setattr(localize_service, "_amazon_translate", lambda *a, **k: None)  # transport miss
    res = localize(BASE, MARKET, "fr")
    assert res["source"] == "mock"
    assert res["provider"] == "offline-dictionary"
    assert res["text"] == BASE


def test_response_is_safety_gated(monkeypatch):
    # a precompute hit carrying flagged text must come back redacted (safety is last hop)
    monkeypatch.setattr(
        localize_service.localize_memory,
        "get_precomputed",
        lambda *a, **k: {"text": "This damn breakfast", "provider": "precomputed", "source": "dynamodb"},
    )
    res = localize(BASE, MARKET, "es")
    assert "damn" not in res["text"].lower()
    assert "[redacted]" in res["text"]


def test_response_contract_shape(monkeypatch):
    _no_precompute(monkeypatch)
    _has_creds(monkeypatch, False)
    res = localize(BASE, MARKET, "es")
    # the four keys the frontend codes against are always present
    assert {"text", "source", "provider", "lang"}.issubset(res.keys())
