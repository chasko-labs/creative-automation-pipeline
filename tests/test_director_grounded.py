"""Grounded art-director headline loop: retrieve -> direct -> normalize -> fallback.

The concept, offline: the request is embedded, top-k brand-voice captions come
back from the committed training library, the trained voice model directs with
those examples in-ask, and the line normalizes to house style. Every transport
is monkeypatched — no Bedrock, no network, no creds. Suite conftest forces the
kill-switch OFF; tests here opt back in explicitly.
"""
from __future__ import annotations

import time
from pathlib import Path

from PIL import Image

from creative_automation import art_director
from creative_automation import director_memory
from creative_automation import generate as generate_mod


def _enable(monkeypatch):
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "true")


def _lib_entry(id_, vec, caption):
    import math

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return {"id": id_, "text": caption, "vector": list(vec), "norm": norm}


# ------------------------------------------------------------- retriever: cosine
def test_retrieve_topk_cosine_correct(monkeypatch):
    monkeypatch.setattr(
        director_memory,
        "_library_cache",
        [
            _lib_entry("a", [1.0, 0.0], "Alpha brand line"),
            _lib_entry("b", [0.0, 1.0], "Beta brand line"),
        ],
    )
    monkeypatch.setattr(
        director_memory.embeddings, "embed_text", lambda q: ([1.0, 0.0], "nova-live")
    )
    examples, model = retrieve_q("dawn pancakes")
    assert model == "nova-live"
    assert [e["id"] for e in examples] == ["a", "b"]
    assert examples[0]["caption"] == "Alpha brand line"
    assert examples[0]["score"] > examples[1]["score"]


def retrieve_q(q):
    return director_memory.retrieve(q, k=2)


def test_retrieve_refuses_mock_vectors(monkeypatch):
    monkeypatch.setattr(
        director_memory,
        "_library_cache",
        [_lib_entry("a", [1.0, 0.0], "Alpha brand line")],
    )
    calls = {"n": 0}

    def _embed(q):
        calls["n"] += 1
        return ([1.0, 0.0], "mock:titan-nova")

    monkeypatch.setattr(director_memory.embeddings, "embed_text", _embed)
    examples, model = director_memory.retrieve("dawn pancakes", k=2)
    assert examples == []
    assert model == "mock:titan-nova"
    assert calls["n"] == 1  # embed ran; retrieval refused on its tag


def test_retrieve_empty_library_yields_no_examples(monkeypatch):
    monkeypatch.setattr(director_memory, "_library_cache", [])
    monkeypatch.setattr(
        director_memory.embeddings, "embed_text", lambda q: ([1.0, 0.0], "nova-live")
    )
    examples, _model = director_memory.retrieve("dawn pancakes", k=2)
    assert examples == []


def test_retrieve_blank_query_never_embeds(monkeypatch):
    calls = {"n": 0}

    def _embed(q):
        calls["n"] += 1
        return ([1.0, 0.0], "nova-live")

    monkeypatch.setattr(director_memory.embeddings, "embed_text", _embed)
    examples, _model = director_memory.retrieve("   ", k=2)
    assert examples == []
    assert calls["n"] == 0


# ------------------------------------------------------- grounded ask construction
def test_grounded_ask_folds_examples_inside_trained_shape():
    ask = art_director._grounded_ask(
        "headline for Power Cakes",
        "adventurous",
        [{"id": "x", "caption": "Fuel your frontier"}, {"id": "y", "caption": "Keep it wild"}],
    )
    assert ask.startswith("### Instruction:")
    assert "Fuel your frontier" in ask and "Keep it wild" in ask
    assert "headline for Power Cakes" in ask


def test_grounded_ask_empty_examples_is_stock_ask():
    assert art_director._grounded_ask("raw ask", "adventurous", []) == art_director._build_ask(
        "raw ask", "adventurous"
    )


# ----------------------------------------------------------------- house style
def test_title_case_headline_house_style():
    assert (
        generate_mod._title_case_headline("fuel the adventure: power your mornings.")
        == "Fuel The Adventure: Power Your Mornings"
    )
    assert (
        generate_mod._title_case_headline("nourishment for today's frontier")
        == "Nourishment For Today's Frontier"
    )
    assert generate_mod._title_case_headline("Power Up Family Mornings!") == (
        "Power Up Family Mornings!"
    )
    assert generate_mod._title_case_headline("") == ""


# ------------------------------------------------------- director loop + gates
def _live_result(text):
    return {"text": text, "source": "bedrock:kodiak-artdirector", "safety": {"clean": True}}


def test_director_headline_live_grounded_normalizes(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: ([{"id": "x", "caption": "Fuel your frontier"}], "nova")
    )
    monkeypatch.setattr(
        art_director, "art_direct_grounded", lambda *a, **k: _live_result("fuel wild mornings.")
    )
    out = generate_mod._director_headline_text("Power Cakes", "wild mornings", "us", "families")
    assert out == "Fuel Wild Mornings"


def test_director_headline_mock_source_falls_back(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: ([{"id": "x", "caption": "Fuel your frontier"}], "nova")
    )
    monkeypatch.setattr(
        art_director,
        "art_direct_grounded",
        lambda *a, **k: {"text": "canned mock line", "source": "mock"},
    )
    out = generate_mod._director_headline_text("Power Cakes", "wild mornings", "us", "families")
    assert out is None  # a mock transport must never write a production headline


def test_director_headline_refusal_falls_back(monkeypatch):
    # PROVEN IN PROD: junk retrieved captions make the live model decline — a
    # refusal is a failed attempt, never a headline (falls back to stock Nova).
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: ([{"id": "x", "caption": "88b5787ee037 waffle 0725"}], "nova")
    )
    monkeypatch.setattr(
        art_director,
        "art_direct_grounded",
        lambda *a, **k: _live_result("I can't fulfill this request."),
    )
    out = generate_mod._director_headline_text("Power Cakes", "wild mornings", "us", "families")
    assert out is None


def test_director_headline_no_examples_falls_back(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(director_memory, "retrieve", lambda q, k=3: ([], "nova"))
    called = {"n": 0}

    def _direct(*a, **k):
        called["n"] += 1
        return _live_result("x")

    monkeypatch.setattr(art_director, "art_direct_grounded", _direct)
    assert generate_mod._director_headline_text("P", "b", "us", "f") is None
    assert called["n"] == 0


def test_director_headline_timeout_falls_back(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: ([{"id": "x", "caption": "c"}], "nova")
    )

    def _slow(*a, **k):
        time.sleep(0.5)
        return _live_result("too late")

    monkeypatch.setattr(art_director, "art_direct_grounded", _slow)
    monkeypatch.setattr(generate_mod, "_DIRECTOR_TIMEOUT_S", 0.1)
    assert generate_mod._director_headline_text("P", "b", "us", "f") is None


def test_director_kill_switch_skips_retrieve(monkeypatch):
    # conftest leaves the switch OFF; retrieve must never run.
    called = {"n": 0}
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: called.__setitem__("n", 1) or ([], "x")
    )
    assert generate_mod._director_headline_text("P", "b", "us", "f") is None
    assert called["n"] == 0


def test_has_creds_sees_lambda_full_uri(monkeypatch):
    for var in (
        "AWS_ACCESS_KEY_ID",
        "AWS_PROFILE",
        "AWS_SESSION_TOKEN",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
    ):
        monkeypatch.delenv(var, raising=False)
    assert art_director._has_creds() is False
    monkeypatch.setenv("AWS_CONTAINER_CREDENTIALS_FULL_URI", "http://localhost/creds")
    assert art_director._has_creds() is True


# ------------------------------------------------- end to end through the ladder
def _make_seed(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (1024, 1024), (30, 90, 160)).save(path, "PNG")
    return path


def test_rung_c_headline_uses_grounded_director(monkeypatch, tmp_path):
    _enable(monkeypatch)
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(
        generate_mod, "_nova_pro_caption", lambda *a, **k: "trail fuel should not win"
    )
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: ([{"id": "x", "caption": "c"}], "nova")
    )
    monkeypatch.setattr(
        art_director, "art_direct_grounded", lambda *a, **k: _live_result("fuel wild mornings.")
    )
    out = tmp_path / "hero.png"
    result, source, prov = generate_mod.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert source == "bedrock:nova-pro"  # rung C compose, director-voiced headline
    assert prov["headline"] == "Fuel Wild Mornings"
    assert prov["headline_source"] == "bedrock:kodiak-artdirector"


def test_rung_c_headline_stock_nova_normalized(monkeypatch, tmp_path):
    # kill-switch OFF (conftest): stock caption path, still house-styled.
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o: None)
    monkeypatch.setattr(generate_mod, "_nova_pro_scene_prompt", lambda *a, **k: "scene")
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", lambda *a, **k: "trail fuel.")
    out = tmp_path / "hero.png"
    result, _source, prov = generate_mod.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert prov["headline"] == "Trail Fuel"
    assert prov["headline_source"] == "bedrock:nova-pro-caption"
