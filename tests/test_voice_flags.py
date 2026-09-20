"""Co-flag discipline + wall-budget composition for the voice enablement track.

Pins the runtime halves (module-default dark voice; ENABLED prewarm is
CDK-side in infra-cdk/lib/generate-stack.ts alongside KODIAK_ARTDIRECTOR_ENABLED)
and proves the nested timeouts compose: the inner voice bound sits inside the
outer wall, and the art-director retry loop's worst-case sleep sits inside the
inner bound. Also proves the Scheduler raw-shape ping reaches the warm path
(pre-warm wired) and that a scale-to-zero cold start warms inside the budget.
No AWS, no network. If anyone widens a retry or flips a default, this fails loudly.
"""
import json
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


def test_prewarm_scheduler_raw_shape_short_circuits_ladder(monkeypatch):
    # Sprint-2 item 10 (pre-warm wired): the Scheduler target input is the RAW
    # payload {"warm": "art-director"} — no Function-URL body wrapper. It must
    # reach the warm path, never the hero ladder (previously _parse_body dropped
    # it to {} and every 4-minute ping ran the full ladder).
    def _boom(*a, **k):
        raise AssertionError("ladder must not run on a scheduler warm ping")

    monkeypatch.setattr(generate_lambda, "generate_hero", _boom)
    monkeypatch.setattr(generate_lambda, "generate_hero_set", _boom)

    resp = generate_lambda.handler({"warm": "art-director"}, None)
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["warmed"] is False  # voice flag dark in this env — nothing to warm
    assert body["reason"] == "voice-off"


def test_prewarm_scheduler_raw_shape_warms_live_voice(monkeypatch):
    # Flag on + live voice source on the RAW scheduler shape: warmed True.
    # This is the cold-start antidote — the ping keeps the imported model warm
    # so request-time invokes skip the ModelNotReadyException probe.
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    from creative_automation import art_director as _ad

    monkeypatch.setattr(
        _ad, "art_direct",
        lambda *a, **k: {"text": "Lace up.", "source": "bedrock:kodiak-artdirector"},
    )
    resp = generate_lambda.handler({"warm": "art-director"}, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["warmed"] is True


def test_cold_start_warms_inside_wall_budget(monkeypatch):
    # A scale-to-zero model throws ModelNotReadyException on first invoke, then
    # warms: the retry loop succeeds after exactly one sleep interval, and the
    # whole cold-start cost (retry sleep + inner voice bound + grace collect)
    # still sits inside the outer wall — voice can never eat the hero budget.
    from botocore.exceptions import ClientError

    not_ready = ClientError(
        {"Error": {"Code": "ModelNotReadyException", "Message": "model is warming"}},
        "Converse",
    )
    calls = {"n": 0}

    class WarmingThenLive:
        def __init__(self, *a, **k):
            pass

        async def stream(self, messages):
            calls["n"] += 1
            if calls["n"] < 2:
                raise not_ready
            yield {"contentBlockDelta": {"delta": {"text": "Lace up. Keep it wild."}}}

    monkeypatch.setattr(art_director, "BedrockModel", WarmingThenLive)
    sleeps: list[int] = []
    out = art_director._try_art_direct(
        art_director._build_ask("morning fuel", "adventurous"),
        region="us-west-2",
        model_arn=art_director.KODIAK_ARTDIRECTOR_MODEL_ARN,
        sleep=lambda s: sleeps.append(s),
    )
    assert out == "Lace up. Keep it wild."  # cold start warmed, not mocked
    assert calls["n"] == 2
    assert sleeps == [art_director.RETRY_SLEEP_SECONDS]
    cold_cost = (
        sum(sleeps)
        + generate_lambda.ART_DIRECTOR_TIMEOUT_S
        + generate_lambda._VOICE_COLLECT_TIMEOUT_S
    )
    assert cold_cost < generate_lambda.GENERATE_WALL_TIMEOUT_S
