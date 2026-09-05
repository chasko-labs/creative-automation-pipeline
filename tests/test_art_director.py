"""Kodiak art-director brand-voice engine — offline path + cold-start retry.

No AWS credentials in CI, so the default path exercises the mock fallback: the chain still
runs build-prompt -> (no Strands) -> safety, and the returned text is always safe and tagged
source="mock". The two higher-value assertions prove (1) the ModelNotReadyException
scale-to-zero retry loop fires with backoff and eventually succeeds, and (2) the prompt is
formatted in the exact ### Instruction / ### Response shape the model was fine-tuned on.
"""
from creative_automation import art_director
from creative_automation.art_director import art_direct


def test_offline_fallback_with_no_creds(monkeypatch):
    # simulate a no-credentials environment: the chain returns a deterministic on-brand mock
    monkeypatch.setattr(art_director, "_has_creds", lambda: False)
    result = art_direct("a hero shot of Power Cakes on a summit at dawn", voice="adventurous")
    assert result["source"] == "mock"
    assert result["text"]
    assert result["safety"]["clean"] is True


def test_mock_voice_is_on_brand_per_voice(monkeypatch):
    monkeypatch.setattr(art_director, "_has_creds", lambda: False)
    adventurous = art_direct("trail mix morning", voice="adventurous")
    nourishing = art_direct("trail mix morning", voice="nourishing")
    # distinct copy per trained voice, both safe, both mock
    assert adventurous["text"] != nourishing["text"]
    assert "wild" in adventurous["text"].lower()
    assert "whole grain" in nourishing["text"].lower()
    assert adventurous["source"] == nourishing["source"] == "mock"


def test_prompt_uses_trained_instruction_response_shape():
    # the fine-tuned shape is non-negotiable: "### Instruction:\n<ask>\n\n### Response:\n"
    prompt = art_director._build_ask("a summit at dawn", "adventurous")
    assert prompt.startswith("### Instruction:\n")
    assert prompt.endswith("### Response:\n")
    assert "\n\n### Response:\n" in prompt
    # the voice framing is folded into the instruction body, not a separate field
    assert "adventurous voice" in prompt
    assert "a summit at dawn" in prompt


def test_model_not_ready_retries_then_succeeds(monkeypatch):
    """Scale-to-zero cold start: first invokes throw ModelNotReadyException, then it warms.

    Strands does not retry ModelNotReadyException — _try_art_direct owns the backoff. We
    mock the BedrockModel so no network is touched and inject a no-op sleep so the test is
    fast. The client warms on the third attempt and returns on-brand text.
    """
    from botocore.exceptions import ClientError

    not_ready = ClientError(
        {"Error": {"Code": "ModelNotReadyException", "Message": "model is warming"}},
        "Converse",
    )
    calls = {"n": 0}

    class FakeModel:
        def __init__(self, *a, **k):
            pass

        async def stream(self, messages):
            calls["n"] += 1
            if calls["n"] < 3:
                raise not_ready
            yield {"contentBlockDelta": {"delta": {"text": "Lace up. Keep it wild."}}}

    monkeypatch.setattr(art_director, "BedrockModel", FakeModel)
    sleeps: list[int] = []
    prompt = art_director._build_ask("summit at dawn", "adventurous")
    out = art_director._try_art_direct(
        prompt,
        region="us-west-2",
        model_arn="arn:aws:bedrock:us-west-2:946179428633:imported-model/cx15b77k5nge",
        sleep=lambda s: sleeps.append(s),
    )
    assert out == "Lace up. Keep it wild."
    assert calls["n"] == 3  # two warming misses, then success
    assert sleeps == [art_director.RETRY_SLEEP_SECONDS, art_director.RETRY_SLEEP_SECONDS]


def test_model_not_ready_exhausts_attempts_returns_none(monkeypatch):
    """If the model never warms within RETRY_ATTEMPTS, fall through to None (-> mock)."""
    from botocore.exceptions import ClientError

    not_ready = ClientError(
        {"Error": {"Code": "ModelNotReadyException", "Message": "model is warming"}},
        "Converse",
    )

    class AlwaysWarming:
        def __init__(self, *a, **k):
            pass

        async def stream(self, messages):
            raise not_ready
            yield  # pragma: no cover — make this an async generator

    monkeypatch.setattr(art_director, "BedrockModel", AlwaysWarming)
    out = art_director._try_art_direct(
        art_director._build_ask("x", "adventurous"),
        region="us-west-2",
        model_arn="arn:test",
        sleep=lambda s: None,
    )
    assert out is None


def test_non_recoverable_error_returns_none_immediately(monkeypatch):
    """A non-ModelNotReady error is not retried — one attempt, then None (-> mock)."""
    from botocore.exceptions import ClientError

    denied = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "no access"}},
        "Converse",
    )
    calls = {"n": 0}

    class Denied:
        def __init__(self, *a, **k):
            pass

        async def stream(self, messages):
            calls["n"] += 1
            raise denied
            yield  # pragma: no cover

    monkeypatch.setattr(art_director, "BedrockModel", Denied)
    out = art_director._try_art_direct(
        art_director._build_ask("x", "adventurous"),
        region="us-west-2",
        model_arn="arn:test",
        sleep=lambda s: None,
    )
    assert out is None
    assert calls["n"] == 1  # no retry on a non-warming error


def test_live_path_tags_source_and_gates_safety(monkeypatch):
    """With creds present and a mocked warm client, source flips to the live tag + is safe."""
    monkeypatch.setattr(art_director, "_has_creds", lambda: True)

    class WarmModel:
        def __init__(self, *a, **k):
            pass

        async def stream(self, messages):
            yield {"contentBlockDelta": {"delta": {"text": "Real food for real adventures."}}}

    monkeypatch.setattr(art_director, "BedrockModel", WarmModel)
    result = art_direct("packshot on a granite ledge", voice="nourishing")
    assert result["source"] == "bedrock:kodiak-artdirector"
    assert result["text"] == "Real food for real adventures."
    assert result["safety"]["clean"] is True


def test_live_output_is_safety_redacted(monkeypatch):
    """Live model output still passes through the safety gate — unsafe copy never leaves."""
    monkeypatch.setattr(art_director, "_has_creds", lambda: True)

    class ProfaneModel:
        def __init__(self, *a, **k):
            pass

        async def stream(self, messages):
            yield {"contentBlockDelta": {"delta": {"text": "This damn pancake is unreal."}}}

    monkeypatch.setattr(art_director, "BedrockModel", ProfaneModel)
    result = art_direct("hero shot", voice="adventurous")
    assert "damn" not in result["text"].lower()
    assert "[redacted]" in result["text"]
    assert result["safety"]["clean"] is True
    assert result["source"] == "bedrock:kodiak-artdirector"
