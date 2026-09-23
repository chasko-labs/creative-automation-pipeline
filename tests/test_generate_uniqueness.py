"""Uniqueness fixes: per-request seed, market/season prompts, memo salt, two-mode gate."""
from __future__ import annotations

from creative_automation import art_director, director_memory
from creative_automation import generate as generate_mod


def _enable(monkeypatch):
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "true")
    monkeypatch.setenv("KODIAK_ARTDIRECTOR_ENABLED", "true")
    monkeypatch.setattr(generate_mod, "_DIRECTOR_MEMO", {}, raising=False)


def _live_result(text):
    return {"source": generate_mod._DIRECTOR_LIVE_SOURCE, "text": text}


# --- fix 1: per-request seed -------------------------------------------

def test_request_seed_varies_by_market_season_day(monkeypatch) -> None:
    monkeypatch.delenv("KODIAK_DETERMINISTIC", raising=False)
    monkeypatch.setattr(generate_mod, "_STABILITY_SEED_PINNED", False)
    base = generate_mod._request_seed("wild mornings", "US-OH-CINCINNATI", "september", "2026-09-23")
    assert base != generate_mod._request_seed("wild mornings", "US-CA-OCEANSIDE", "september", "2026-09-23")
    assert base != generate_mod._request_seed("wild mornings", "US-OH-CINCINNATI", "october", "2026-09-23")
    assert base != generate_mod._request_seed("wild mornings", "US-OH-CINCINNATI", "september", "2026-09-24")
    assert base == generate_mod._request_seed("wild mornings", "US-OH-CINCINNATI", "september", "2026-09-23")
    assert 0 <= base <= 0xFFFFFFFF


def test_request_seed_pinned_when_deterministic(monkeypatch) -> None:
    monkeypatch.setenv("KODIAK_DETERMINISTIC", "1")
    monkeypatch.setattr(generate_mod, "_STABILITY_SEED_PINNED", False)
    assert generate_mod._request_seed("b", "m1", "s1", "2026-01-01") == generate_mod.STABILITY_SEED
    assert generate_mod._request_seed("b", "m2", "s2", "2026-02-02") == generate_mod.STABILITY_SEED


def test_request_seed_pinned_when_env_pin(monkeypatch) -> None:
    monkeypatch.delenv("KODIAK_DETERMINISTIC", raising=False)
    monkeypatch.setattr(generate_mod, "_STABILITY_SEED_PINNED", True)
    assert generate_mod._request_seed("b", "m1", "s1", "2026-01-01") == generate_mod.STABILITY_SEED


def test_restyle_cache_key_sensitive_to_seed() -> None:
    a = generate_mod._restyle_cache_key(b"seed", "p", "b", "r", "a", None, "m", "s", 111)
    b = generate_mod._restyle_cache_key(b"seed", "p", "b", "r", "a", None, "m", "s", 222)
    c = generate_mod._restyle_cache_key(b"seed", "p", "b", "r", "a", None, "m", "s", 111)
    assert a != b
    assert a == c


# --- fix 2: market + season reach the prompts ---------------------------

def test_default_scene_prompt_names_market_and_season() -> None:
    prompt = generate_mod._default_scene_prompt(
        "Power Cakes", "wild mornings", "us", "families", None, None, None,
        "US-OH-CINCINNATI", "september",
    )
    assert "US-OH-CINCINNATI" in prompt
    assert "september" in prompt


def test_default_scene_prompt_never_duplicates_brief_suffix() -> None:
    brief = "wild mornings (frontier: Lebanon, OH - US-OH-CINCINNATI market, september picks)"
    prompt = generate_mod._default_scene_prompt(
        "Power Cakes", brief, "us", "families", None, None, None,
        "US-OH-CINCINNATI", "september",
    )
    assert prompt.lower().count("us-oh-cincinnati") == brief.lower().count("us-oh-cincinnati")
    assert prompt.lower().count("september") == brief.lower().count("september")


def test_default_scene_prompt_unchanged_without_locale() -> None:
    a = generate_mod._default_scene_prompt("P", "wild mornings", "us", "f", None)
    b = generate_mod._default_scene_prompt("P", "wild mornings", "us", "f", None, None, None, None, None)
    assert a == b


def test_nova_scene_fallback_carries_locale(monkeypatch, tmp_path) -> None:
    # boto3 None -> deterministic default, which must still name market/season.
    monkeypatch.setattr(generate_mod, "boto3", None)
    seed = tmp_path / "seed.png"
    seed.write_bytes(b"fakepng")
    prompt = generate_mod._nova_pro_scene_prompt(
        seed, "P", "wild mornings", "us", "f", None, None, None,
        "US-OH-CINCINNATI", "september",
    )
    assert "US-OH-CINCINNATI" in prompt
    assert "september" in prompt


def test_nova_scene_postprocess_reattaches_locale(monkeypatch, tmp_path) -> None:
    # Live Nova compresses locality out of its 40-word reply: the post-process
    # re-attaches market/season deterministically, keeping Nova's scene text.
    from PIL import Image

    seed = tmp_path / "seed.png"
    Image.new("RGB", (256, 256), (180, 90, 30)).save(seed, "PNG")

    class _FakeNova:
        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": "Cozy fall kitchen."}]}}}

    monkeypatch.setattr(generate_mod, "_bedrock_failfast_client", lambda **kwargs: _FakeNova())
    prompt = generate_mod._nova_pro_scene_prompt(
        seed, "Power Cakes", "wild mornings", "us", "families", None, None, None,
        "US-OH-CINCINNATI", "october",
    )
    assert "Cozy fall kitchen." in prompt
    assert "US-OH-CINCINNATI" in prompt
    assert "october" in prompt


# --- fix 3: memo salted by market + season -------------------------------

def _voice_setup(monkeypatch, calls):
    _enable(monkeypatch)
    monkeypatch.setattr(
        director_memory, "retrieve", lambda query, k=3: ([{"id": "x", "caption": "Fuel your frontier mornings now"}], "nova")
    )

    def _direct(*args, **kwargs):
        calls["n"] += 1
        return _live_result("dawn patrol eats first")

    monkeypatch.setattr(art_director, "art_direct_grounded", _direct)


def test_memo_still_hits_identical_request(monkeypatch) -> None:
    calls = {"n": 0}
    _voice_setup(monkeypatch, calls)
    first = generate_mod._director_headline_text("P", "wild mornings", "us", "f", True, None, "mkt", "june")
    report: dict = {}
    second = generate_mod._director_headline_text("P", "wild mornings", "us", "f", True, report, "mkt", "june")
    assert first == second == "Dawn Patrol Eats First"
    assert calls["n"] == 1
    assert report.get("voice_source") == "memo"


def test_memo_misses_when_season_differs(monkeypatch) -> None:
    calls = {"n": 0}
    _voice_setup(monkeypatch, calls)
    generate_mod._director_headline_text("P", "wild mornings", "us", "f", True, None, "mkt", "june")
    generate_mod._director_headline_text("P", "wild mornings", "us", "f", True, None, "mkt", "october")
    assert calls["n"] == 2


def test_memo_misses_when_market_differs(monkeypatch) -> None:
    calls = {"n": 0}
    _voice_setup(monkeypatch, calls)
    generate_mod._director_headline_text("P", "wild mornings", "us", "f", True, None, "mkt-a", "june")
    generate_mod._director_headline_text("P", "wild mornings", "us", "f", True, None, "mkt-b", "june")
    assert calls["n"] == 2


# --- fix 4: two-mode similarity gate -------------------------------------

def test_diverge_requested() -> None:
    assert generate_mod._diverge_requested(None, None) is False
    assert generate_mod._diverge_requested("", "  ") is False
    assert generate_mod._diverge_requested("halloween", None) is True
    assert generate_mod._diverge_requested(None, "october") is True


def test_gate_decision_matrix(monkeypatch) -> None:
    monkeypatch.setattr(generate_mod, "SIMILARITY_GATE_THRESHOLD", 8)
    monkeypatch.setattr(generate_mod, "KODIAK_MIN_DIVERGENCE", 2)
    decide = generate_mod._similarity_gate_decision
    assert decide(3, False) == "pass"
    assert decide(30, False) == "reject-drift"
    assert decide(30, True) == "pass"
    assert decide(0, True) == "retry"
    assert decide(1, True) == "retry"
