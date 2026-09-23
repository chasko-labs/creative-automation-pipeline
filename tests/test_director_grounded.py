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

from creative_automation import art_director, director_memory
from creative_automation import generate as generate_mod


def _enable(monkeypatch):
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "true")
    # isolate the per-container director memo: each test starts unmemoized.
    monkeypatch.setattr(generate_mod, "_DIRECTOR_MEMO", {}, raising=False)


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


def test_load_library_drops_filename_captions(tmp_path, monkeypatch):
    # the committed library is ~95% asset titles; only voice-grade sentences load.
    lib = tmp_path / "lib.jsonl"
    entries_jsonl = [
        '{"id": "junk", "metadata": {"caption": "88b5787ee037 Kodiak Recipe Waffle 0725 4eb0b2"}, "vector": [1.0, 0.0]}',
        '{"id": "real", "metadata": {"caption": "Fuel your frontier with whole grains and protein"}, "vector": [0.0, 1.0]}',
    ]
    lib.write_text("\n".join(entries_jsonl), encoding="utf-8")
    monkeypatch.setattr(director_memory, "data_path", lambda *a: lib)
    director_memory.clear_cache()
    try:
        entries = director_memory._load_library()
    finally:
        director_memory.clear_cache()
    assert [e["id"] for e in entries] == ["real"]


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


def test_scrub_strips_markup_and_preamble():
    text = 'Here are the requested responses:\n- **"Fuel Your Wilder Days"**\n### Explanation:\nshort'
    out = generate_mod._scrub_director_line(
        text, [{"id": "x", "caption": "Unrelated brand sentence here now"}]
    )
    assert out == "Fuel Your Wilder Days"


def test_scrub_rejects_example_echo():
    out = generate_mod._scrub_director_line(
        "**Bear Bites for Cubs, Cinnamon Honey**",
        [{"id": "x", "caption": "Bear Bites for Cubs, cinnamon honey graham bears"}],
    )
    assert out is None  # echo of the example, not a written line


def test_director_headline_resamples_single_after_trio_refusal(monkeypatch):
    # PROVEN IN PROD: a trio of fragment-grade captions declines while the
    # top-1 alone complies — resample once with the single best example.
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory,
        "retrieve",
        lambda q, k=3: (
            [
                {"id": "j1", "caption": "fast and easy breakfast stack"},
                {"id": "j2", "caption": "Kodiak air fryer chicken and waffles"},
                {"id": "j3", "caption": "Kodiak carrot cake french toast bake"},
            ],
            "nova",
        ),
    )
    calls = {"n": 0}

    def _direct(ask, voice, examples=None):
        calls["n"] += 1
        if len(examples or []) > 1:
            return _live_result("I can't fulfill this request.")
        return _live_result("dawn patrol eats first")

    monkeypatch.setattr(art_director, "art_direct_grounded", _direct)
    out = generate_mod._director_headline_text("Power Cakes", "wild mornings", "us", "families")
    assert out == "Dawn Patrol Eats First"
    assert calls["n"] == 2


def test_headline_for_runs_full_pipeline(monkeypatch):
    # the set path must not bypass the director/normalize with raw Nova text.
    _enable(monkeypatch)
    monkeypatch.setattr(generate_mod, "_director_headline_text", lambda *a, **k: None)
    monkeypatch.setattr(
        generate_mod, "_nova_pro_caption", lambda *a, **k: "fuel wild mornings."
    )
    headline, source = generate_mod._headline_for(
        Path("x.png"), "Power Cakes", "brief words here", "us", "families"
    )
    assert headline == "Fuel Wild Mornings"
    assert source == "bedrock:nova-pro-caption"


def test_headline_for_prefers_director(monkeypatch):
    _enable(monkeypatch)
    monkeypatch.setattr(
        generate_mod, "_director_headline_text", lambda *a, **k: "Dawn Patrol Eats First"
    )
    headline, source = generate_mod._headline_for(
        Path("x.png"), "Power Cakes", "brief words here", "us", "families"
    )
    assert headline == "Dawn Patrol Eats First"
    assert source == generate_mod._DIRECTOR_LIVE_SOURCE


def test_director_headline_memoizes_second_call(monkeypatch):
    # PROVEN IN PROD: hero_set runs the pipeline twice per pack with the same
    # brief — the second run must be a free memo hit, not a repaid invoke.
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: ([{"id": "x", "caption": "Fuel your frontier mornings now"}], "nova")
    )
    calls = {"n": 0}

    def _direct(*a, **k):
        calls["n"] += 1
        return _live_result("dawn patrol eats first")

    monkeypatch.setattr(art_director, "art_direct_grounded", _direct)
    first = generate_mod._director_headline_text("P", "wild mornings here", "us", "f")
    second = generate_mod._director_headline_text("P", "wild mornings here", "us", "f")
    assert first == second == "Dawn Patrol Eats First"
    assert calls["n"] == 1


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
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
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
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
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


# --------------------------------------- wall-math fast-follow: caption gate
def test_headline_for_caption_skipped_on_low_budget(monkeypatch, capsys):
    # PROVEN IN PROD 2026-09-08: an un-gated caption after a 12s director spend
    # burned the silent seconds and the wall fired during finalize. With <7000+3000
    # ms left the caption must not run — the brief verbatim is the fallback.
    _enable(monkeypatch)
    monkeypatch.setattr(generate_mod, "_director_headline_text", lambda *a, **k: None)

    def _boom(*a, **k):
        raise AssertionError("caption must not run under budget")

    monkeypatch.setattr(generate_mod, "_nova_pro_caption", _boom)
    headline, source = generate_mod._headline_for(
        Path("x.png"), "Power Cakes", "brief words here", "us", "families",
        remaining_ms=lambda: 1000.0,
    )
    assert headline == "brief words here"
    assert source is None
    assert "nova caption skipped" in capsys.readouterr().err


def test_headline_for_caption_runs_with_budget(monkeypatch, capsys):
    _enable(monkeypatch)
    monkeypatch.setattr(generate_mod, "_director_headline_text", lambda *a, **k: None)
    monkeypatch.setattr(
        generate_mod, "_nova_pro_caption", lambda *a, **k: "fuel wild mornings."
    )
    headline, source = generate_mod._headline_for(
        Path("x.png"), "Power Cakes", "brief words here", "us", "families",
        remaining_ms=lambda: 20000.0,
    )
    assert headline == "Fuel Wild Mornings"
    assert source == "bedrock:nova-pro-caption"
    assert "nova caption ok latency=" in capsys.readouterr().err


def test_director_headline_failures_retry_no_poison(monkeypatch):
    # A cold-model timeout (outcome None) must not poison later warm calls in the
    # same container: only live successes are memoized, failures re-invoke.
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory, "retrieve", lambda q, k=3: ([{"id": "x", "caption": "c"}], "nova")
    )
    calls = {"n": 0}

    def _mock_voice(*a, **k):
        calls["n"] += 1
        return {"text": "mock line", "source": "mock", "safety": {"clean": True}}

    monkeypatch.setattr(art_director, "art_direct_grounded", _mock_voice)
    assert generate_mod._director_headline_text("P", "b", "us", "f") is None
    assert generate_mod._director_headline_text("P", "b", "us", "f") is None
    assert calls["n"] == 2


def test_headline_for_director_skipped_on_low_budget(monkeypatch, capsys):
    # Wall repair: the set path re-paid the full director cost (~8s) even with
    # the wall thin — director + render then exceed 22s and the pack falls to
    # rung D. With <10000+3000 ms left the director must not run at all.
    _enable(monkeypatch)

    def _boom(*a, **k):
        raise AssertionError("director must not run under budget")

    monkeypatch.setattr(generate_mod, "_director_headline_text", _boom)
    monkeypatch.setattr(generate_mod, "_nova_pro_caption", _boom)
    headline, source = generate_mod._headline_for(
        Path("x.png"), "Power Cakes", "brief words here", "us", "families",
        remaining_ms=lambda: 1000.0,
    )
    assert headline == "brief words here"
    assert source is None
    assert "set-headline skip" in capsys.readouterr().err


def test_headline_for_director_runs_with_budget(monkeypatch):
    # Adequate budget -> director still runs on the set path (memo makes the
    # repeat call ~free on warm containers).
    _enable(monkeypatch)
    monkeypatch.setattr(
        generate_mod, "_director_headline_text", lambda *a, **k: "Dawn Patrol Eats First"
    )
    headline, source = generate_mod._headline_for(
        Path("x.png"), "Power Cakes", "brief words here", "us", "families",
        remaining_ms=lambda: 20000.0,
    )
    assert headline == "Dawn Patrol Eats First"
    assert source == generate_mod._DIRECTOR_LIVE_SOURCE


def _write_seed(tmp_path: Path) -> None:
    from PIL import Image as _Image

    d = tmp_path / "input_assets" / "power-cakes"
    d.mkdir(parents=True, exist_ok=True)
    _Image.new("RGB", (64, 64), (200, 120, 40)).save(d / "hero-real.png", "PNG")


def test_concurrent_director_headline_lands_through_ladder(monkeypatch, tmp_path):
    # The ladder kick submits the director at hero start; rung C collects it.
    # Instant live line + local seed (pure-local rung C) -> grounded headline.
    monkeypatch.chdir(tmp_path)
    _write_seed(tmp_path)
    monkeypatch.setattr(
        generate_mod, "_director_headline_text", lambda *a, **k: "Dawn Patrol Eats First"
    )
    out = tmp_path / "hero.png"
    result, _source, prov = generate_mod.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert prov.get("headline_source") == generate_mod._DIRECTOR_LIVE_SOURCE


def test_concurrent_director_slow_voice_bounded_wait(monkeypatch, tmp_path):
    # Pin budgets to the pre-seasonal calibration so the 24s/16s wall logic is
    # exercised, not the new 28s/25s 5×Bedrock raise.
    monkeypatch.setattr(generate_mod, "GENERATE_SOFT_BUDGET_MS", 24000)
    monkeypatch.setattr(generate_mod, "_B_BUDGET_MS", 16000)
    monkeypatch.setattr(generate_mod, "_C_RESERVATION_MS", 3000)
    # A stalled voice (30s — longer than any ladder cascade, so the done()
    # poll can never pick it up mid-run) must not stall the ladder: the first
    # budget-shaped collect gives up at ~10s grace, the slow-voice latch holds
    # later rungs at ~0, and the degrade chain bottoms out at the brief
    # verbatim (the 10s wait leaves the clock too thin for the caption gate —
    # wall safety first, copy still ships via sidecar brief).
    import time as _time

    monkeypatch.chdir(tmp_path)
    _write_seed(tmp_path)

    def _slow(*a, **k):
        _time.sleep(30)
        return "Too Late To Matter"

    monkeypatch.setattr(generate_mod, "_director_headline_text", _slow)
    monkeypatch.setattr(
        generate_mod, "_nova_pro_caption", lambda *a, **k: "fuel wild mornings."
    )
    out = tmp_path / "hero.png"
    start = _time.monotonic()
    result, _source, prov = generate_mod.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    elapsed = _time.monotonic() - start
    assert result.exists()
    assert prov.get("headline") == "Fuel your frontier morning"
    assert prov.get("headline_source") is None
    assert elapsed < 16, f"slow voice gated the ladder — {elapsed:.1f}s"


def test_embed_client_carries_fail_fast_config():
    from creative_automation import embeddings as _emb

    client = _emb._boto_client()
    if client is None:
        import pytest as _pytest

        _pytest.skip("boto3 unavailable in this env")
    cfg = client.meta.config
    assert cfg.connect_timeout == 2
    assert cfg.read_timeout == 5
    # merged client config normalizes max_attempts -> total_max_attempts
    assert cfg.retries.get("total_max_attempts") == 2
