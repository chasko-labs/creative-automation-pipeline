"""Co-flag discipline + wall-budget composition for the voice enablement track.

Pins the runtime halves (module-default dark voice; the ON flip +
ENABLED prewarm are CDK-side in infra-cdk/lib/generate-stack.ts alongside
KODIAK_ARTDIRECTOR_ENABLED) and proves the nested timeouts compose: the
inner voice bound sits inside the outer wall, and the art-director retry
loop's worst-case sleep sits inside the inner bound. Also proves the
Scheduler raw-shape ping reaches the warm path (pre-warm wired), that a
scale-to-zero cold start warms inside the budget, and that the async voice
upgrade (kicked concurrent voice + grace collect) upgrades provenance on a
live line but never gates or breaks pixels on a slow/faulty voice.
No AWS, no network. If anyone widens a retry or flips a default, this fails loudly.

DECISION (carry-10): the flip stays deploy-scoped (CDK env true + Scheduler
ENABLED); the module default stays dark (false). A module-ON default would
run mock-voice in every offline/CI context and widen the blast radius, while
the CDK flip keeps rollback at flag-off with pixels unaffected. No other
defaults change here.

DECISION (cost incident 2026-09-23): the deploy-scoped default is now OFF
(CDK env false unless `-c artDirectorVoice=on`) and the pre-warm Scheduler
rule is deleted from IaC. The imported voice model bills per copy-minute
24/7; default-ON kept a ~$38/day charge alive with zero traffic value.
"""
import json
import os
import threading
from pathlib import Path

from creative_automation import art_director, generate, generate_lambda


def test_voice_flag_dark_by_default():
    # do NOT set KODIAK_ARTDIRECTOR_ENABLED — prod default is dark.
    assert "KODIAK_ARTDIRECTOR_ENABLED" not in os.environ
    assert generate_lambda.ART_DIRECTOR_ENABLED is False


def test_grounded_director_requires_primary_voice_flag(monkeypatch):
    # cost incident 2026-09-23: the legacy per-path default is ON in prod, but
    # the voice must still stay off unless the primary flag opts in.
    monkeypatch.delenv("KODIAK_DIRECTOR_GROUNDED", raising=False)
    monkeypatch.delenv("KODIAK_ARTDIRECTOR_ENABLED", raising=False)
    assert generate._director_enabled() is False
    monkeypatch.setenv("KODIAK_ARTDIRECTOR_ENABLED", "true")
    assert generate._director_enabled() is True


def test_primary_flag_off_blocks_grounded_path_with_zero_transport(monkeypatch):
    # prod-shaped env (legacy flag ON, primary flag OFF): the headline path
    # must return None before retrieve/embed/voice — zero Bedrock calls.
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "true")
    monkeypatch.delenv("KODIAK_ARTDIRECTOR_ENABLED", raising=False)

    def _boom(*a, **k):
        raise AssertionError("no transport may run while the primary flag is off")

    from creative_automation import art_director, director_memory

    monkeypatch.setattr(director_memory, "retrieve", _boom)
    monkeypatch.setattr(art_director, "art_direct_grounded", _boom)
    out = generate._director_headline_text("Power Cakes", "wild mornings", "us", "families")
    assert out is None


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
    assert generate_lambda.GENERATE_WALL_TIMEOUT_S == 26
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


def test_fast_probe_shape():
    # Fast probe, not the old long loop: exactly one warming retry (2 attempts
    # x 2s sleep). Widening attempts would keep worst_sleep <= inner bound for
    # a while but stop being a probe — pin the shape, not just the product.
    assert art_director.RETRY_ATTEMPTS == 2
    assert art_director.RETRY_SLEEP_SECONDS == 2


def test_cdk_voice_flip_and_prewarm_on():
    # Cost incident 2026-09-23 ($139 imported-model copy-minute burn): the
    # CDK stack ships the voice flag OFF (opt-IN per deploy via `-c
    # artDirectorVoice=on` for an active voice test window only), and the
    # pre-warm Scheduler rule is DELETED from IaC — disabled is not enough
    # because it can be re-enabled. If the flag default flips back to
    # always-on, or any Scheduler pre-warm returns, the deploy resumes a
    # 24/7 copy-minute charge while the runtime tests stay green — so pin
    # the safe IaC text (and the schedule's absence) here.
    root = Path(__file__).resolve().parent.parent
    stack = (root / "infra-cdk" / "lib" / "generate-stack.ts").read_text()
    assert 'artDirectorVoice") === "on"' in stack  # flag opt-in arm
    assert ': "false"' in stack  # flag default arm
    assert "ArtDirectorPrewarmSchedule" not in stack
    assert "rate(4 minutes)" not in stack


def test_async_upgrade_records_live_line(monkeypatch):
    # Flag on + live voice: the kicked concurrent voice resolves to a real
    # line and the post-render collect records art_headline in provenance.
    # This is the async-upgrade payoff — pixels already exist, voice upgrades.
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    from creative_automation import art_director as _ad

    monkeypatch.setattr(
        _ad,
        "art_direct",
        lambda ask, voice="adventurous", **k: {
            "text": "Lace up. Keep it wild.",
            "source": "bedrock:kodiak-artdirector",
        },
    )
    prompt = "morning fuel"
    provenance: dict = {}
    fut = generate_lambda._kick_voice({"voice": "adventurous", "art_director": True}, prompt)
    assert fut is not None
    generate_lambda._apply_art_upgrade_future(fut, {"voice": "adventurous", "art_director": True}, prompt, provenance)
    assert provenance == {"art_headline": "Lace up. Keep it wild."}


def test_async_upgrade_slow_voice_ships_pixels_voice_off(monkeypatch):
    # A slow voice must never gate the render: the grace collect gives up fast
    # and records nothing — pixels ship voice-off, no raise.
    release = threading.Event()
    from creative_automation import art_director as _ad

    def _slow(ask, voice="adventurous", **k):
        release.wait(30)
        return {"text": "too late", "source": "bedrock:kodiak-artdirector"}

    monkeypatch.setattr(_ad, "art_direct", _slow)
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    provenance: dict = {}
    try:
        fut = generate_lambda._kick_voice({"art_director": True}, "morning fuel")
        generate_lambda._apply_art_upgrade_future(
            fut, {"art_director": True}, "morning fuel", provenance, timeout_s=0.05
        )
    finally:
        release.set()
    assert provenance == {}


def test_voice_fault_falls_back_to_prompt_never_raises(monkeypatch):
    # Faulty voice (Bedrock down, bad shape, anything) degrades to the
    # original headline — never raises, never an empty headline — and the
    # collect records nothing since the line equals the prompt.
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    from creative_automation import art_director as _ad

    def _fault(ask, voice="adventurous", **k):
        raise RuntimeError("bedrock down")

    monkeypatch.setattr(_ad, "art_direct", _fault)
    prompt = "morning fuel"
    assert generate_lambda._maybe_art_direct({}, prompt) == prompt
    provenance: dict = {}
    fut = generate_lambda._kick_voice({}, prompt)
    generate_lambda._apply_art_upgrade_future(fut, {}, prompt, provenance)
    assert provenance == {}


def test_unknown_voice_falls_back_to_default(monkeypatch):
    # A request voice outside the trained set never passes through raw — it
    # rides the default voice, while a known voice passes through verbatim.
    monkeypatch.setattr(generate_lambda, "ART_DIRECTOR_ENABLED", True)
    from creative_automation import art_director as _ad

    seen: list[str] = []

    def _capture(ask, voice="adventurous", **k):
        seen.append(voice)
        return {"text": "Lace up. Keep it wild.", "source": "bedrock:kodiak-artdirector"}

    monkeypatch.setattr(_ad, "art_direct", _capture)
    generate_lambda._maybe_art_direct({"voice": "feral", "art_director": True}, "morning fuel")
    generate_lambda._maybe_art_direct({"voice": "nourishing", "art_director": True}, "morning fuel")
    assert seen == [
        generate_lambda._ART_DIRECTOR_DEFAULT_VOICE,
        "nourishing",
    ]
