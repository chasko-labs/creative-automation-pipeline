"""Precompute writer — offline contract tests.

The writer (scripts/precompute-localization.py) is the WRITE side of the same contract
localize_memory.get_precomputed reads. These tests monkeypatch every transport boundary so
nothing touches AWS:
  - _amazon_translate / _bedrock_translate -> deterministic fakes
  - the DynamoDB client -> a fake capturing put_item / get_item calls

Highest-value assertions:
  - keys are built via localize_memory.build_key (hashing the SOURCE message)
  - nv / zip are SKIPPED entirely (ethics guard — no fake MT ever written)
  - amazon vs bedrock routing is chosen by language, matching live MT
  - written items carry text / provider / source="dynamodb"
  - --dry-run writes nothing
  - one lang's translate failure does not stop the others

The script lives in scripts/ (not the importable package), so it is loaded by path.
"""
from __future__ import annotations

import importlib.util
import pathlib
import types

import pytest

from creative_automation import localize_memory

REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "precompute-localization.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("precompute_localization", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pc = _load_module()


MARKET = "US-SW-LASCRUCES"
MESSAGE = "Nourishment for Today's Frontier"


class FakeDynamo:
    """Captures put_item / get_item calls; get_item returns preseeded items only."""

    def __init__(self, present: dict | None = None):
        self.puts: list[dict] = []
        self.gets: list[dict] = []
        self._present = present or {}  # (pk, sk) -> Item dict

    def put_item(self, TableName, Item):
        self.puts.append({"TableName": TableName, "Item": Item})

    def get_item(self, TableName, Key):
        self.gets.append({"TableName": TableName, "Key": Key})
        pk = Key["pk"]["S"]
        sk = Key["sk"]["S"]
        item = self._present.get((pk, sk))
        return {"Item": item} if item else {}


def _args(**over):
    base = {"dry_run": False, "only_missing": False, "region": "us-east-1", "limit": None, "table": None}
    base.update(over)
    return types.SimpleNamespace(**base)


def _patch_markets(monkeypatch, langs):
    """Force load_markets to a single deterministic market with the given target langs."""
    monkeypatch.setattr(
        pc, "load_markets", lambda: [{"market": MARKET, "message": MESSAGE, "langs": langs}]
    )


def _patch_translate(monkeypatch, amazon=None, bedrock=None):
    def amazon_fake(text, lang, source_lang="en"):
        return amazon(text, lang) if amazon else f"AMZ:{lang}:{text}"

    def bedrock_fake(text, lang, market):
        return bedrock(text, lang, market) if bedrock else f"BED:{lang}:{text}"

    monkeypatch.setattr(pc, "_amazon_translate", amazon_fake)
    monkeypatch.setattr(pc, "_bedrock_translate", bedrock_fake)


def _run_with_fake_dynamo(monkeypatch, args, fake):
    monkeypatch.setattr(pc, "_client", lambda region: fake)
    return pc.run(args)


def test_keys_built_via_build_key_on_source_message(monkeypatch):
    # es is an Amazon-Translate lang; the written key must hash the SOURCE message, not the
    # translated text, so the reader (which passes the source) lands on the same item.
    _patch_markets(monkeypatch, ["es"])
    _patch_translate(monkeypatch)
    fake = FakeDynamo()
    rc = _run_with_fake_dynamo(monkeypatch, _args(), fake)
    assert rc == 0

    expected_en = localize_memory.build_key(MARKET, "en", MESSAGE)
    expected_es = localize_memory.build_key(MARKET, "es", MESSAGE)
    written = {(p["Item"]["pk"]["S"], p["Item"]["sk"]["S"]) for p in fake.puts}
    assert (expected_en["pk"], expected_en["sk"]) in written
    assert (expected_es["pk"], expected_es["sk"]) in written


def test_en_source_stored_verbatim_provider_precomputed(monkeypatch):
    _patch_markets(monkeypatch, ["es"])
    _patch_translate(monkeypatch)
    fake = FakeDynamo()
    _run_with_fake_dynamo(monkeypatch, _args(), fake)

    en_items = [p["Item"] for p in fake.puts if p["Item"]["lang"]["S"] == "en"]
    assert len(en_items) == 1
    it = en_items[0]
    assert it["text"]["S"] == MESSAGE  # verbatim source
    assert it["provider"]["S"] == "precomputed"
    assert it["source"]["S"] == "dynamodb"


def test_amazon_routing_for_supported_lang(monkeypatch):
    _patch_markets(monkeypatch, ["es"])
    _patch_translate(monkeypatch, amazon=lambda t, lang: "Nutricion para la Frontera de Hoy")
    # bedrock must not fire for an amazon-supported lang
    monkeypatch.setattr(
        pc,
        "_bedrock_translate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("bedrock called for amazon lang")),
    )
    fake = FakeDynamo()
    _run_with_fake_dynamo(monkeypatch, _args(), fake)

    es = [p["Item"] for p in fake.puts if p["Item"]["lang"]["S"] == "es"]
    assert len(es) == 1
    assert es[0]["provider"]["S"] == "amazon-translate"
    assert es[0]["source"]["S"] == "dynamodb"
    assert es[0]["text"]["S"] == "Nutricion para la Frontera de Hoy"


def test_bedrock_routing_for_gap_lang(monkeypatch):
    _patch_markets(monkeypatch, ["ilo"])  # Ilocano — a machine-able gap
    _patch_translate(monkeypatch, bedrock=lambda t, lang, m: "protina para iti frontier")
    # amazon must not fire for a gap lang
    monkeypatch.setattr(
        pc,
        "_amazon_translate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("amazon called for gap lang")),
    )
    fake = FakeDynamo()
    _run_with_fake_dynamo(monkeypatch, _args(), fake)

    ilo = [p["Item"] for p in fake.puts if p["Item"]["lang"]["S"] == "ilo"]
    assert len(ilo) == 1
    assert ilo[0]["provider"]["S"] == "bedrock"
    assert ilo[0]["source"]["S"] == "dynamodb"
    assert ilo[0]["text"]["S"] == "protina para iti frontier"


def test_human_required_langs_skipped(monkeypatch):
    # nv / zip / hmn must never be machine translated and never written — only en is written.
    # hmn joined this set for quality/reachability (incoherent nova-pro Hmong), nv/zip for ethics.
    _patch_markets(monkeypatch, ["nv", "zip", "hmn"])
    monkeypatch.setattr(
        pc,
        "_amazon_translate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("translate called for human-required")),
    )
    monkeypatch.setattr(
        pc,
        "_bedrock_translate",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("bedrock called for human-required")),
    )
    fake = FakeDynamo()
    _run_with_fake_dynamo(monkeypatch, _args(), fake)

    langs_written = {p["Item"]["lang"]["S"] for p in fake.puts}
    assert langs_written == {"en"}  # nv, zip, hmn never written
    assert "nv" not in langs_written
    assert "zip" not in langs_written
    assert "hmn" not in langs_written


def test_dry_run_writes_nothing(monkeypatch):
    _patch_markets(monkeypatch, ["es", "ilo"])
    _patch_translate(monkeypatch)
    fake = FakeDynamo()
    # _client must not even be constructed on a dry run; make it explode if called
    monkeypatch.setattr(
        pc, "_client", lambda region: (_ for _ in ()).throw(AssertionError("client built on dry-run"))
    )
    rc = pc.run(_args(dry_run=True))
    assert rc == 0
    assert fake.puts == []  # untouched fake, and no client was built


def test_only_missing_skips_present_items(monkeypatch):
    _patch_markets(monkeypatch, ["es"])
    _patch_translate(monkeypatch)
    # preseed the es item as already present
    es_key = localize_memory.build_key(MARKET, "es", MESSAGE)
    present = {
        (es_key["pk"], es_key["sk"]): {"pk": {"S": es_key["pk"]}, "sk": {"S": es_key["sk"]}}
    }
    fake = FakeDynamo(present=present)
    _run_with_fake_dynamo(monkeypatch, _args(only_missing=True), fake)

    langs_written = {p["Item"]["lang"]["S"] for p in fake.puts}
    assert "es" not in langs_written  # present -> skipped
    assert "en" in langs_written  # en not preseeded -> still written


def test_one_translate_failure_does_not_stop_others(monkeypatch):
    # es raises, ilo succeeds — es is counted a failure, ilo + en still written
    _patch_markets(monkeypatch, ["es", "ilo"])

    def amazon_boom(text, lang, source_lang="en"):
        raise RuntimeError("amazon transport blew up")

    monkeypatch.setattr(pc, "_amazon_translate", amazon_boom)
    monkeypatch.setattr(pc, "_bedrock_translate", lambda t, lang, m: f"BED:{lang}")
    fake = FakeDynamo()
    rc = _run_with_fake_dynamo(monkeypatch, _args(), fake)
    assert rc == 0  # partial success is not a batch abort

    langs_written = {p["Item"]["lang"]["S"] for p in fake.puts}
    assert "en" in langs_written
    assert "ilo" in langs_written
    assert "es" not in langs_written  # the failing lang was skipped, not fatal


def test_translate_miss_empty_text_not_written(monkeypatch):
    # a transport miss returns None/"" — must not write an empty item
    _patch_markets(monkeypatch, ["fr"])
    monkeypatch.setattr(pc, "_amazon_translate", lambda t, lang, source_lang="en": None)
    fake = FakeDynamo()
    _run_with_fake_dynamo(monkeypatch, _args(), fake)

    langs_written = {p["Item"]["lang"]["S"] for p in fake.puts}
    assert "fr" not in langs_written
    assert "en" in langs_written


def test_limit_slices_markets(monkeypatch):
    monkeypatch.setattr(
        pc,
        "load_markets",
        lambda: [
            {"market": "M1", "message": MESSAGE, "langs": ["es"]},
            {"market": "M2", "message": MESSAGE, "langs": ["es"]},
        ],
    )
    _patch_translate(monkeypatch)
    fake = FakeDynamo()
    _run_with_fake_dynamo(monkeypatch, _args(limit=1), fake)

    markets_written = {p["Item"]["market"]["S"] for p in fake.puts}
    assert markets_written == {"M1"}


def test_translate_for_routing_matches_live_groups(monkeypatch):
    # unit-level: translate_for chooses provider strictly by the shared routing groups.
    # patch the transports so no live call fires; assert only the provider tag.
    from creative_automation.localize_service import AMAZON_TRANSLATE_LANGS, BEDROCK_GAP_LANGS

    an_amazon = next(iter(AMAZON_TRANSLATE_LANGS))
    a_gap = next(iter(BEDROCK_GAP_LANGS))
    monkeypatch.setattr(pc, "_amazon_translate", lambda t, lang, source_lang="en": "amz")
    monkeypatch.setattr(pc, "_bedrock_translate", lambda t, lang, m: "bed")

    assert pc.translate_for(MESSAGE, MARKET, "en") == (MESSAGE, "precomputed")
    assert pc.translate_for(MESSAGE, MARKET, an_amazon)[1] == "amazon-translate"
    assert pc.translate_for(MESSAGE, MARKET, a_gap)[1] == "bedrock"
    assert pc.translate_for(MESSAGE, MARKET, "xx-unrouted") == (None, None)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-x", "-q"]))
