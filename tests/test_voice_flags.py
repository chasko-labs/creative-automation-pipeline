"""Co-flag discipline + wall-budget composition for the voice enablement track.

Pins the prod defaults (dark voice, DISABLED prewarm is CDK-side; the runtime
halves are pinned here) and proves the nested timeouts compose: the inner
voice bound sits inside the outer wall, and the art-director retry loop's
worst-case sleep sits inside the inner bound. No AWS, no network — pure
arithmetic over the module constants. If anyone widens a retry or flips a
default, this fails loudly.
"""
import os

from creative_automation import art_director, generate, generate_lambda


def test_voice_flag_dark_by_default():
    # do NOT set KODIAK_ARTDIRECTOR_ENABLED — prod default is dark.
    assert "KODIAK_ARTDIRECTOR_ENABLED" not in os.environ
    assert generate_lambda.ART_DIRECTOR_ENABLED is False


def test_grounded_director_on_by_default_in_prod(monkeypatch):
    # conftest forces the kill-switch OFF for hermetic tests; prod default is ON.
    monkeypatch.delenv("KODIAK_DIRECTOR_GROUNDED", raising=False)
    assert generate._director_enabled() is True


def test_stability_rung_on_by_default_in_prod(monkeypatch):
    # generative rung ships ON; dev opts out per-run via env, never in code.
    monkeypatch.delenv("KODIAK_ENABLE_STABILITY_RUNG", raising=False)
    import importlib

    import creative_automation.generate as _gen

    reloaded = importlib.reload(_gen)
    try:
        assert reloaded._STABILITY_RUNG_ON is True
    finally:
        importlib.reload(_gen)


def test_wall_budget_composition():
    # inner voice bound < outer wall: a hung voice can never eat the hero budget.
    assert generate_lambda.ART_DIRECTOR_TIMEOUT_S < generate_lambda.GENERATE_WALL_TIMEOUT_S
    assert generate_lambda.GENERATE_WALL_TIMEOUT_S == 22
    assert generate_lambda.ART_DIRECTOR_TIMEOUT_S == 6
    # worst-case added sleep of the cold-start probe <= inner bound.
    worst_sleep = (art_director.RETRY_ATTEMPTS - 1) * art_director.RETRY_SLEEP_SECONDS
    assert worst_sleep == 2
    assert worst_sleep <= generate_lambda.ART_DIRECTOR_TIMEOUT_S
    # post-render voice collect is a grace wait, also inside the inner bound.
    assert generate_lambda._VOICE_COLLECT_TIMEOUT_S < generate_lambda.ART_DIRECTOR_TIMEOUT_S
