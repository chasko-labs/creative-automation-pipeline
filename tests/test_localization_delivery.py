"""Server-side localization delivery — top-3 per market, EN/ES/PT fallback, offline-safe.

Covers locales.resolve_target_languages (market top-2 + English, default fill), the
generate_lambda._build_localizations seam (translated vs rewrite-fallback), and the
handler surfacing localizations[] + provenance.languages additively. The rewrite/
translate seam is monkeypatched — nothing hits live AWS.
"""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import generate_lambda, locales, text_rewriter


# ------------------------------------------------------- resolve_target_languages
def test_known_market_yields_three_langs_including_english() -> None:
    # Park City lists es + pt as its top-2 non-English -> [en, es, pt], English first.
    langs = locales.resolve_target_languages("US-MW-PARKCITY-84098")
    codes = [le["lang_code"] for le in langs]
    assert len(codes) == 3
    assert codes[0] == "en"
    assert set(codes) == {"en", "es", "pt"}
    # each entry carries a translate_code
    assert all(le.get("translate_code") for le in langs)


def test_market_with_non_default_top_langs() -> None:
    # Wasatch lists es + de -> English + those two, in market order.
    langs = locales.resolve_target_languages("US-MW-WASATCH")
    codes = [le["lang_code"] for le in langs]
    assert codes[0] == "en"
    assert codes[1:] == ["es", "de"]


def test_unknown_market_defaults_to_en_es_pt() -> None:
    langs = locales.resolve_target_languages("US-NOWHERE-XYZ")
    codes = [le["lang_code"] for le in langs]
    assert codes == ["en", "es", "pt"]


def test_none_market_defaults_to_en_es_pt() -> None:
    codes = [le["lang_code"] for le in locales.resolve_target_languages(None)]
    assert codes == ["en", "es", "pt"]


# ------------------------------------------------------- _build_localizations seam
def test_build_localizations_marks_translated_on_live_backend(monkeypatch) -> None:
    # a live rewrite (source bedrock:nova-micro) surfaces as source="translated".
    def _fake_rewrite_all(base, market, langs, **kwargs):
        return [
            {"lang_code": c, "text": f"{base} [{c}]", "source": "bedrock:nova-micro"}
            for c in langs
        ]

    monkeypatch.setattr(text_rewriter, "rewrite_all", _fake_rewrite_all)
    locs, languages = generate_lambda._build_localizations("Keep It Wild", "US-MW-PARKCITY-84098")
    assert languages == ["en", "es", "pt"]
    assert [lo["lang_code"] for lo in locs] == ["en", "es", "pt"]
    assert all(lo["source"] == "translated" for lo in locs)
    assert all(lo["headline"].startswith("Keep It Wild") for lo in locs)
    assert all(lo.get("translate_code") for lo in locs)


def test_build_localizations_offline_is_rewrite_fallback(monkeypatch) -> None:
    # the offline path: rewrite_all returns source="mock" -> "rewrite-fallback", original line.
    def _mock_rewrite_all(base, market, langs, **kwargs):
        return [{"lang_code": c, "text": base, "source": "mock"} for c in langs]

    monkeypatch.setattr(text_rewriter, "rewrite_all", _mock_rewrite_all)
    locs, _langs = generate_lambda._build_localizations("Keep It Wild", None)
    assert all(lo["source"] == "rewrite-fallback" for lo in locs)
    assert all(lo["headline"] == "Keep It Wild" for lo in locs)


def test_build_localizations_backend_raises_degrades_without_crashing(monkeypatch) -> None:
    # a backend that raises must degrade to rewrite-fallback, never propagate.
    def _boom(base, market, langs, **kwargs):
        raise RuntimeError("bedrock down")

    monkeypatch.setattr(text_rewriter, "rewrite_all", _boom)
    locs, languages = generate_lambda._build_localizations("Wild Mornings", "US-NOWHERE")
    assert languages == ["en", "es", "pt"]
    assert [lo["lang_code"] for lo in locs] == ["en", "es", "pt"]
    assert all(lo["source"] == "rewrite-fallback" for lo in locs)
    assert all(lo["headline"] == "Wild Mornings" for lo in locs)


# ------------------------------------------------------- handler additive fields
class _FakeS3:
    def put_object(self, **kwargs) -> dict:
        return {}

    def generate_presigned_url(self, op, Params, ExpiresIn) -> str:  # noqa: N803
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def _fake_renders(out_dir: Path) -> list[dict]:
    from PIL import Image

    out_dir.mkdir(parents=True, exist_ok=True)
    dims = {"1x1": (1080, 1080), "4x5": (1080, 1350), "9x16": (1080, 1920), "16x9": (1920, 1080)}
    renders = []
    for ratio, (w, h) in dims.items():
        p = out_dir / f"hero-{ratio}.png"
        Image.new("RGB", (16, 16), (200, 120, 40)).save(p, "PNG")
        renders.append({"ratio": ratio, "path": p, "w": w, "h": h, "engine": "stability-outpaint"})
    return renders


def test_handler_surfaces_localizations_and_provenance_languages(monkeypatch, tmp_path) -> None:
    prov = {"engine": "stability-control-structure", "headline": "Keep It Wild"}

    def _stub(**kwargs):
        out_dir = kwargs.get("out_dir") or (tmp_path / "renders")
        return _fake_renders(Path(out_dir)), "bedrock:nova-pro", dict(prov)

    def _fake_rewrite_all(base, market, langs, **kwargs):
        return [
            {"lang_code": c, "text": f"{base} [{c}]", "source": "bedrock:nova-micro"}
            for c in langs
        ]

    monkeypatch.setattr(generate_lambda, "generate_hero_set", _stub)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    monkeypatch.setattr(text_rewriter, "rewrite_all", _fake_rewrite_all)

    event = {"body": json.dumps({"mode": "full", "prompt": "wild", "market": "US-MW-PARKCITY-84098"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    # additive: existing fields still present
    assert body["ok"] is True
    assert body["image_url"].startswith("https://presigned.example/")
    assert [r["ratio"] for r in body["renders"]] == ["1x1", "4x5", "9x16", "16x9"]
    # full mode is frontend-owned for copy (wall arithmetic): keys present, empty,
    # provenance names the owner. The seam itself is still covered below.
    assert body["localizations"] == []
    assert body["provenance"]["languages"] == []
    assert body["provenance"]["copy_owner"] == "frontend"


def test_handler_localization_offline_never_crashes(monkeypatch, tmp_path) -> None:
    # with NO rewrite monkeypatch, the real offline rewrite_all runs (no creds) and must
    # degrade to rewrite-fallback rather than 500 the generate call.
    def _stub(**kwargs):
        out_dir = kwargs.get("out_dir") or (tmp_path / "renders")
        return _fake_renders(Path(out_dir)), "bedrock:nova-pro", {"headline": "Keep It Wild"}

    monkeypatch.setattr(generate_lambda, "generate_hero_set", _stub)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    # ensure the offline gate: no creds env vars leak into the seam
    for var in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_SESSION_TOKEN",
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"):
        monkeypatch.delenv(var, raising=False)

    event = {"body": json.dumps({"mode": "full", "prompt": "wild", "market": "US-NOWHERE"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    locs = body["localizations"]
    assert locs == []
    assert body["provenance"]["copy_owner"] == "frontend"
