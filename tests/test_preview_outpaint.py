"""Preview outpaint budget gate (sprint-2 item 11) — no real AWS."""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import generate_lambda


class _FakeS3Error(Exception):
    """Module-local stub error so fakes never raise vanilla Exception (TRY002)."""


class _FakeS3:
    """Stub s3 client capturing put_object and returning a canned presigned url."""

    def __init__(self) -> None:
        self.puts: list[dict] = []

    def put_object(self, **kwargs) -> dict:
        self.puts.append(kwargs)
        return {}

    def generate_presigned_url(self, op, Params, ExpiresIn) -> str:
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def _stub_hero(**kwargs):
    """Instant generate_hero stub: real tiny PNG + provenance with a scene prompt."""
    from PIL import Image

    out_path = Path(kwargs["out_path"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), (200, 120, 40)).save(out_path, "PNG")
    prov = {
        "seed_source": "power-cakes-hero",
        "engine": "stability-control-structure",
        "scene_prompt": "wild frontier restyle",
        "headline": "Keep It Wild",
    }
    return out_path, "bedrock:stability-control-structure", dict(prov)


def _fake_extend_ok(base_png: Path, target_w: int, target_h: int,
                    prompt: str, out_path: Path) -> Path:
    """Successful live extend: writes a real PNG at the TARGET dims."""
    from PIL import Image

    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (target_w, target_h), (40, 120, 200)).save(out_path, "PNG")
    return out_path


def _run_preview(monkeypatch) -> dict:
    monkeypatch.setattr(generate_lambda, "generate_hero", _stub_hero)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())
    event = {"body": json.dumps({"prompt": "a bear eating pancakes", "product": "power-cakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    return json.loads(resp["body"])


def test_preview_outpaint_success_marks_live_engines(monkeypatch) -> None:
    # Gate passes on the instant stub hero; both extends succeed -> live engines
    # for 9x16/16x9, pads stay for 4x5/blog, no degrade entries recorded.
    monkeypatch.setattr(generate_lambda, "_preview_now", lambda: 1000.0)
    calls: list = []

    def _spy(base_png, w, h, prompt, out_path):
        calls.append((w, h, prompt))
        return _fake_extend_ok(base_png, w, h, prompt, out_path)

    monkeypatch.setattr(generate_lambda, "_stability_outpaint", _spy)
    body = _run_preview(monkeypatch)
    assert len(calls) == 2
    assert body["provenance"]["ratios"] == {
        "1x1": "primary",
        "4x5": "pillow-outpaint-fallback",
        "9x16": "stability-outpaint",
        "16x9": "stability-outpaint",
        "blog": "pillow-outpaint-fallback",
    }
    assert body["provenance"]["outpaint_degraded"] == {}
    assert set(body["provenance"]["outpaint_latency_ms"]) == {"9x16", "16x9"}
    # gate-time measurement recorded per attempted ratio alongside latency
    assert set(body["provenance"]["outpaint_remaining_ms"]) == {"9x16", "16x9"}
    # the extend prompt reuses the hero scene prompt, never an extra model call
    assert all(subject == "wild frontier restyle" for _, _, subject in calls)
    # live tiles upload at true matrix dims
    from creative_automation.platforms import RATIO_DIMS

    by_ratio = {r["ratio"]: r for r in body["renders"]}
    assert (by_ratio["9x16"]["w"], by_ratio["9x16"]["h"]) == RATIO_DIMS["9x16"]
    assert (by_ratio["16x9"]["w"], by_ratio["16x9"]["h"]) == RATIO_DIMS["16x9"]


def test_preview_outpaint_budget_exhausted_falls_back_to_pads(monkeypatch) -> None:
    # A slow hero (all but ~1s of the soft wall spent) leaves ~1s: the gate
    # fails, NO extend is attempted, both tiles ship pads with honest degrade
    # reasons — still 200. Remaining is the soft budget minus elapsed, so the
    # ticks below leave ~1s regardless of the soft-budget default.
    soft = generate_lambda.GENERATE_SOFT_BUDGET_MS
    # tick 1000 -> soft-1000 elapsed (1000 remaining) triggers budget-exhausted
    ticks = iter([1000.0, 1000.0 + soft - 1000.0, 1000.0 + soft - 1000.0, 1000.0 + soft - 1000.0])
    monkeypatch.setattr(generate_lambda, "_preview_now", lambda: next(ticks, 1000.0 + soft - 1000.0))
    calls: list = []
    monkeypatch.setattr(
        generate_lambda, "_stability_outpaint",
        lambda *a, **k: calls.append(a) or None,
    )
    body = _run_preview(monkeypatch)
    assert calls == []
    assert body["provenance"]["ratios"]["9x16"] == "pillow-outpaint-fallback"
    assert body["provenance"]["ratios"]["16x9"] == "pillow-outpaint-fallback"
    assert body["provenance"]["outpaint_degraded"] == {
        "9x16": "budget-exhausted",
        "16x9": "budget-exhausted",
    }
    # measurement recorded: ~1000ms remaining at gate time (soft budget sensitive)
    # Don't hardcode 1000 across budget changes (24s→28s); just assert gate saw low remaining
    for ratio in ("9x16", "16x9"):
        assert body["provenance"]["outpaint_remaining_ms"][ratio] < 6000.0
    assert body["provenance"]["outpaint_latency_ms"] == {}


def test_preview_outpaint_rung_disabled_falls_back_to_pads(monkeypatch) -> None:
    # KODIAK_ENABLE_STABILITY_RUNG=0 dev path: no extend attempted, pads ship.
    monkeypatch.setattr(generate_lambda, "_preview_now", lambda: 1000.0)
    monkeypatch.setattr(generate_lambda, "_STABILITY_RUNG_ON", False)
    calls: list = []
    monkeypatch.setattr(
        generate_lambda, "_stability_outpaint",
        lambda *a, **k: calls.append(a) or None,
    )
    body = _run_preview(monkeypatch)
    assert calls == []
    assert body["provenance"]["outpaint_degraded"] == {
        "9x16": "stability-rung-disabled",
        "16x9": "stability-rung-disabled",
    }
    assert body["provenance"]["ratios"]["9x16"] == "pillow-outpaint-fallback"


def test_preview_outpaint_timeout_degrades_to_pads(monkeypatch) -> None:
    # A hung extend (fail-fast read timeout) degrades to the pad, never an error.
    from botocore.exceptions import ReadTimeoutError

    monkeypatch.setattr(generate_lambda, "_preview_now", lambda: 1000.0)

    def _hang(*a, **k):
        raise ReadTimeoutError(endpoint_url="https://bedrock-runtime.us-east-1.amazonaws.com")

    monkeypatch.setattr(generate_lambda, "_stability_outpaint", _hang)
    body = _run_preview(monkeypatch)
    assert body["ok"] is True
    assert body["provenance"]["outpaint_degraded"] == {
        "9x16": "bedrock-timeout",
        "16x9": "bedrock-timeout",
    }
    assert body["provenance"]["ratios"]["9x16"] == "pillow-outpaint-fallback"
    assert body["provenance"]["ratios"]["16x9"] == "pillow-outpaint-fallback"
    assert set(body["provenance"]["outpaint_latency_ms"]) == {"9x16", "16x9"}


def test_preview_outpaint_generic_error_degrades_to_pads(monkeypatch) -> None:
    # A poisoned extend (throttle/validation, not a timeout) degrades to the pad
    # with the error type recorded — still 200, pads stay the fallback.
    monkeypatch.setattr(generate_lambda, "_preview_now", lambda: 1000.0)

    def _poisoned(*a, **k):
        raise RuntimeError("throttled")

    monkeypatch.setattr(generate_lambda, "_stability_outpaint", _poisoned)
    body = _run_preview(monkeypatch)
    assert body["ok"] is True
    assert body["provenance"]["outpaint_degraded"] == {
        "9x16": "outpaint-error: RuntimeError",
        "16x9": "outpaint-error: RuntimeError",
    }
    assert body["provenance"]["ratios"]["9x16"] == "pillow-outpaint-fallback"
    assert body["provenance"]["ratios"]["16x9"] == "pillow-outpaint-fallback"
    assert set(body["provenance"]["outpaint_latency_ms"]) == {"9x16", "16x9"}
    # 4x5/blog never attempt an extend: no degrade entries, always pads.
    assert body["provenance"]["ratios"]["4x5"] == "pillow-outpaint-fallback"
    assert body["provenance"]["ratios"]["blog"] == "pillow-outpaint-fallback"
    assert "4x5" not in body["provenance"]["outpaint_degraded"]
    assert "blog" not in body["provenance"]["outpaint_degraded"]


def _fake_bedrock_throttle_then_ok(monkeypatch, failures: int,
                                   code: str = "ThrottlingException") -> dict:
    """Fake fail-fast client: throttle `failures` times, then a valid payload."""
    import base64
    import io

    from PIL import Image

    from creative_automation import bedrock_client, stability_rungs
    from creative_automation.bedrock_client import ClientError

    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 20, 30)).save(buf, "PNG")
    payload = {"images": [base64.b64encode(buf.getvalue()).decode("ascii")]}
    calls: dict = {"n": 0, "sleeps": []}

    class _Body:
        def read(self) -> bytes:
            return json.dumps(payload).encode()

    class _FakeBedrock:
        def invoke_model(self, **kwargs):
            calls["n"] += 1
            if calls["n"] <= failures:
                raise ClientError({"Error": {"Code": code, "Message": "burst"}}, "InvokeModel")
            return {"body": _Body()}

    monkeypatch.setattr(bedrock_client, "_bedrock_failfast_client", lambda **k: _FakeBedrock())
    monkeypatch.setattr(stability_rungs.time, "sleep", lambda s: calls["sleeps"].append(s))
    return calls


def _hero_base(tmp_path) -> Path:
    from PIL import Image

    base = tmp_path / "hero-1x1.png"
    Image.new("RGB", (1080, 1080), (200, 120, 40)).save(base, "PNG")
    return base


def test_outpaint_throttle_retries_then_succeeds(monkeypatch, tmp_path) -> None:
    """Two burst rejections then a model answer: one tile, no pad."""
    from creative_automation import stability_rungs

    calls = _fake_bedrock_throttle_then_ok(monkeypatch, failures=2)
    out = tmp_path / "hero-9x16.png"
    got = stability_rungs._stability_outpaint(_hero_base(tmp_path), 1080, 1350, "subject", out)
    assert got == out
    assert out.exists()
    assert calls["n"] == 3
    assert calls["sleeps"] == [1.5, 3.0]


def test_outpaint_service_unavailable_retries(monkeypatch, tmp_path) -> None:
    """'Too many connections' is the same transient class: retried, then served."""
    from creative_automation import stability_rungs

    calls = _fake_bedrock_throttle_then_ok(monkeypatch, failures=1,
                                           code="ServiceUnavailableException")
    out = tmp_path / "hero-16x9.png"
    got = stability_rungs._stability_outpaint(_hero_base(tmp_path), 1350, 1080, "subject", out)
    assert got == out
    assert calls["n"] == 2


def test_outpaint_throttle_exhausted_reraises_for_caller(monkeypatch, tmp_path) -> None:
    """Persistent throttling still surfaces so the caller books the degrade reason."""
    from creative_automation import stability_rungs
    from creative_automation.bedrock_client import ClientError

    calls = _fake_bedrock_throttle_then_ok(monkeypatch, failures=99)
    out = tmp_path / "hero-9x16.png"
    try:
        stability_rungs._stability_outpaint(_hero_base(tmp_path), 1080, 1350, "subject", out)
    except ClientError as e:
        assert e.response["Error"]["Code"] == "ThrottlingException"
    else:
        raise AssertionError("expected ClientError to propagate")
    assert calls["n"] == stability_rungs.OUTPAINT_MAX_ATTEMPTS
    assert len(calls["sleeps"]) == stability_rungs.OUTPAINT_MAX_ATTEMPTS - 1


def test_outpaint_non_throttle_error_does_not_retry(monkeypatch, tmp_path) -> None:
    """A real rejection (bad request, denied) degrades at once: one call, no sleep."""
    from creative_automation import stability_rungs

    calls = _fake_bedrock_throttle_then_ok(monkeypatch, failures=99,
                                           code="ValidationException")
    out = tmp_path / "hero-9x16.png"
    assert stability_rungs._stability_outpaint(_hero_base(tmp_path), 1080, 1350, "subject", out) is None
    assert calls["n"] == 1
    assert calls["sleeps"] == []
