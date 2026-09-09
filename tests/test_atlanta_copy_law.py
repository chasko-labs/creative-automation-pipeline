"""Atlanta shakedown copy law — failing-first (backlog units B + H).

Standing law (docs/plans/2026-09-09-atlanta-shakedown-backlog.md): the word
KODIAK is FORBIDDEN in generated copy (logo lockups only); allowed namings are
"Kodiak Cakes" and "Kodiak Park City"; bare "Kodiak" appears nowhere; social
voice uses #kodiakcakes-style hashtags. No invented translations/frontier data.

OFFLINE, cred-free: _no_creds forces the deterministic fallback seams.
"""
from __future__ import annotations

import csv
import io
import re

import pytest

from creative_automation import text_rewriter

# The word KODIAK (all caps) never ships in copy, except inside a hashtag token.
_ALLCAPS_RE = re.compile(r"(?<!#)\bKODIAK\b")
# Title-case Kodiak must always be followed by an allowed naming.
_BARE_RE = re.compile(r"(?<!#)\bKodiak\b(?!\s+(Cakes?|Park\s+City))")


def _assert_copy_clean(*texts: str) -> None:
    for t in texts:
        assert _ALLCAPS_RE.search(t or "") is None, f"bare KODIAK ships: {t!r}"
        assert _BARE_RE.search(t or "") is None, f"bare Kodiak ships: {t!r}"


@pytest.fixture(autouse=True)
def _no_creds(monkeypatch):
    for var in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_SESSION_TOKEN",
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"):
        monkeypatch.delenv(var, raising=False)


ATLANTA_OFFENDERS = [
    "Warm Up Your Winter Nights With Kodiak",
    "KODIAK Sandersville frontier — Georgia pecans",
    "KODIAK\xae Sandersville frontier \u2014 Georgia pecans",
    "Watch how a real Kodiak breakfast comes together",
]


def test_atlanta_offenders_never_survive_platform_copy():
    from creative_automation.platform_copy import generate_platform_copy

    for offender in ATLANTA_OFFENDERS:
        copy = generate_platform_copy(offender, "Power Cakes", "US-SE-ATL")
        for entry in copy.values():
            texts = [
                entry.get("headline", ""),
                entry.get("body", ""),
                entry.get("title", ""),
                entry.get("description", ""),
                entry.get("post", ""),
            ]
            _assert_copy_clean(*texts)


def test_live_rewrite_with_bare_kodiak_is_cleaned():
    from creative_automation.platform_copy import generate_platform_copy

    def _live(base, market, **kwargs):
        return {"text": "Warm Up Your Winter Nights With Kodiak",
                "source": "bedrock:nova-micro", "safety": {"clean": True},
                "dialect_applied": []}

    orig = text_rewriter.rewrite_headline
    text_rewriter.rewrite_headline = _live  # type: ignore
    try:
        copy = generate_platform_copy("warm winter nights", "Power Cakes", "US-SE-ATL",
                                      platforms=["x", "facebook"])
    finally:
        text_rewriter.rewrite_headline = orig  # type: ignore
    assert copy["x"]["source"] == "generated"
    _assert_copy_clean(copy["x"]["headline"], copy["x"]["post"],
                       copy["facebook"]["headline"], copy["facebook"]["body"])


def test_fallback_templates_carry_no_bare_kodiak():
    from creative_automation.platform_copy import fallback_platform_copy

    copy = fallback_platform_copy("Fuel your morning", "Power Cakes", "US-SE-ATL")
    for entry in copy.values():
        _assert_copy_clean(entry.get("headline", ""), entry.get("body", ""),
                           entry.get("title", ""), entry.get("description", ""),
                           entry.get("post", ""))
    # X/Facebook carry real meat, not an echo.
    assert copy["x"]["post"]
    assert copy["facebook"]["body"]


def test_localize_never_ships_bare_kodiak_es_ko():
    from creative_automation.localize import localize_message

    for lang in ("es", "ko"):
        for offender in ATLANTA_OFFENDERS:
            text, _source = localize_message(offender, lang, "US-SE-ATL")
            _assert_copy_clean(text)


def test_atlanta_resolves_to_es_and_ko():
    from creative_automation.locales import resolve_target_languages

    langs = [t["lang_code"] for t in resolve_target_languages("US-SE-ATL")]
    assert langs == ["en", "es", "ko"]


def test_sidecar_carries_campaign_messaging_retailer_recipe_i18n():
    from creative_automation.generate import build_copy_sidecar
    from creative_automation.platform_copy import fallback_platform_copy

    platform_copy = fallback_platform_copy(
        "Warm Up Your Winter Nights With Kodiak Cakes", "Power Cakes", "US-SE-ATL")
    localizations = [
        {"lang_code": "en", "translate_code": "en", "headline": "Fuel your frontier",
         "source": "original"},
        {"lang_code": "es", "translate_code": "es", "headline": "Fuel your frontier [es]",
         "source": "rewrite-fallback"},
        {"lang_code": "ko", "translate_code": "ko", "headline": "Fuel your frontier [ko]",
         "source": "rewrite-fallback"},
    ]
    recipe = {"title": "Power Cakes Trail Stack",
              "ingredients": ["2 cups Power Cakes mix"],
              "steps": ["Whisk", "Cook", "Stack"]}
    sc = build_copy_sidecar(
        {"copy_headline": "Warm Up Your Winter Nights With Kodiak Cakes"},
        "Warm Up Your Winter Nights",
        platform_copy,
        theme="localized-publix",
        product="power-cakes",
        localizations=localizations,
        languages=["en", "es", "ko"],
        recipe_fields=recipe,
        retailer="Publix",
    )
    _assert_copy_clean(sc["txt"])
    rows = list(csv.reader(io.StringIO(sc["csv"])))
    fields = [r[0] for r in rows]
    assert "retailer" in fields
    assert any(f.startswith("i18n.") for f in fields)
    assert any(f.startswith("recipe.") for f in fields)
    assert any(f.endswith(".headline") and "x" in f for f in fields)
    assert "KODIAK" not in sc["txt"]
    assert "KODIAK" not in sc["csv"]


def test_atlanta_preview_scenario_es_ko_publix_recipe_no_spend(monkeypatch, tmp_path):
    """Offline Atlanta-scenario pass (Park City-style default path, no model, no S3).

    Stubs the single 1x1 hero + S3, POSTs an Atlanta request with a bare-Kodiak
    brief, and asserts the preview carries Spanish + Korean, Publix retailer
    proof, the recipe tease, full platform copy, and no bare brand word anywhere.
    """
    import json
    from pathlib import Path

    from creative_automation import generate_lambda

    from PIL import Image

    def _stub_hero(**kwargs):
        out_path = Path(kwargs["out_path"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (16, 16), (200, 120, 40)).save(out_path, "PNG")
        return out_path, "bedrock:stability-control-structure", {
            "engine": "stability-control-structure",
            "copy_headline": "Warm Up Your Winter Nights With Kodiak",
        }

    class _FakeS3:
        def put_object(self, **kwargs):
            return {}

        def generate_presigned_url(self, op, Params, ExpiresIn):
            return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"

    monkeypatch.setattr(generate_lambda, "generate_hero", _stub_hero)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    event = {"body": json.dumps({
        "prompt": "Warm Up Your Winter Nights With Kodiak",
        "product": "power-cakes",
        "market": "US-SE-ATL",
    })}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["mode"] == "preview"
    assert len(body["renders"]) == 1

    # Spanish + market second language (Korean for Atlanta) IN the preview.
    assert [loc["lang_code"] for loc in body["localizations"]] == ["en", "es", "ko"]
    # Retailer proof: Localized Publix for the Atlanta-like market.
    assert body["retailer"] == "Publix"
    # Recipe tease + platform-voiced copy (X post + Facebook body).
    assert body["recipe_fields"]["title"]
    assert body["platform_copy"]["x"]["post"]
    assert body["platform_copy"]["facebook"]["body"]
    rows = list(csv.reader(io.StringIO(body["copy_sidecar"]["csv"])))
    fields = [r[0] for r in rows]
    assert "retailer" in fields
    assert "recipe.title" in fields
    assert "i18n.es.headline" in fields
    assert "i18n.ko.headline" in fields
    # Standing law across every GENERATED-copy field (body.prompt is the verbatim
    # request echo — the record, not generated copy — so it is excluded).
    generated = json.dumps({
        "platform_copy": body["platform_copy"],
        "localizations": body["localizations"],
        "copy_sidecar": body["copy_sidecar"],
        "recipe_fields": body["recipe_fields"],
        "retailer": body["retailer"],
        "provenance": {k: v for k, v in body["provenance"].items()
                       # record-echo fields (raw brief/model line for debugging),
                       # not generated copy — the sidecar + copy rows carry cleaned text.
                       if k not in ("incoming_prompt", "copy_headline", "headline",
                                    "art_headline")},
    })
    _assert_copy_clean(generated)
