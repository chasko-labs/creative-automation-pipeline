"""Async render jobs (POST /jobs start, GET /jobs status, worker branch) — no real AWS.

The HTTP API caps every response at 30s while the image model needs 20s+ per
restyle, so jobs split the wait: start validates + self-invokes async (202),
the worker runs the same preview ladder with relaxed walls, and the frontend
polls the S3 status doc. All AWS clients are faked here.
"""
from __future__ import annotations

import io
import json

from creative_automation import generate as generate_mod
from creative_automation import generate_lambda


class _FakeS3Error(Exception):
    """Module-local stub error so fakes never raise vanilla Exception (TRY002)."""


class _FakeS3:
    def __init__(self, objects: dict | None = None) -> None:
        self.puts: list[dict] = []
        self.objects = dict(objects or {})

    def put_object(self, **kwargs) -> dict:
        self.puts.append(kwargs)
        self.objects[kwargs["Key"]] = kwargs["Body"]
        return {}

    def get_object(self, Bucket, Key) -> dict:
        if Key not in self.objects:
            raise _FakeS3Error(f"NoSuchKey: {Key}")
        body = self.objects[Key]
        raw = body.encode("utf-8") if isinstance(body, str) else body
        return {"Body": io.BytesIO(raw)}


class _FakeLambda:
    def __init__(self) -> None:
        self.invokes: list[dict] = []

    def invoke(self, **kwargs) -> dict:
        self.invokes.append(kwargs)
        return {"StatusCode": 202}


def _clients(monkeypatch, s3: _FakeS3, lam: _FakeLambda | None = None):
    lam = lam if lam is not None else _FakeLambda()

    def _client(name: str, *a, **k):
        if name == "s3":
            return s3
        if name == "lambda":
            return lam
        raise AssertionError(f"unexpected client {name}")

    monkeypatch.setattr(generate_lambda.boto3, "client", _client)
    return lam


def _jobs_event(body: dict, method: str = "POST") -> dict:
    return {
        "requestContext": {"http": {"method": method, "path": "/jobs"}},
        "rawPath": "/jobs",
        "body": json.dumps(body),
    }


def test_jobs_start_returns_202_and_queues(monkeypatch) -> None:
    s3, lam = _FakeS3(), _FakeLambda()
    _clients(monkeypatch, s3, lam)
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "fn")
    resp = generate_lambda.handler(_jobs_event({"prompt": "x", "market": "us"}), None)
    assert resp["statusCode"] == 202
    started = json.loads(resp["body"])
    assert started["ok"] is True
    job_id = started["job_id"]
    assert len(job_id) == 12
    queued = json.loads(s3.objects[f"brands/kodiak/jobs/{job_id}.json"])
    assert queued["state"] == "queued"
    assert len(lam.invokes) == 1
    call = lam.invokes[0]
    assert call["InvocationType"] == "Event"
    payload = json.loads(call["Payload"])
    assert payload["_job"]["id"] == job_id
    assert payload["prompt"] == "x"


def test_jobs_start_malformed_body_is_400(monkeypatch) -> None:
    _clients(monkeypatch, _FakeS3())
    monkeypatch.setenv("AWS_LAMBDA_FUNCTION_NAME", "fn")
    event = _jobs_event({})
    event["body"] = "{nope"
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 400


def test_jobs_start_without_function_name_is_500(monkeypatch) -> None:
    _clients(monkeypatch, _FakeS3())
    monkeypatch.delenv("AWS_LAMBDA_FUNCTION_NAME", raising=False)
    resp = generate_lambda.handler(_jobs_event({"prompt": "x"}), None)
    assert resp["statusCode"] == 500


def test_jobs_status_round_trip(monkeypatch) -> None:
    doc = {"job_id": "abcdef012345", "state": "working"}
    s3 = _FakeS3({"brands/kodiak/jobs/abcdef012345.json": json.dumps(doc)})
    _clients(monkeypatch, s3)
    event = {
        "requestContext": {"http": {"method": "GET", "path": "/jobs"}},
        "rawPath": "/jobs",
        "queryStringParameters": {"id": "abcdef012345"},
    }
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["state"] == "working"


def test_jobs_status_unknown_and_malformed(monkeypatch) -> None:
    _clients(monkeypatch, _FakeS3())
    for params, want in (({"id": "abcdef012345"}, 404), ({"id": "nope"}, 400), ({}, 400)):
        event = {
            "requestContext": {"http": {"method": "GET", "path": "/jobs"}},
            "rawPath": "/jobs",
            "queryStringParameters": params,
        }
        assert generate_lambda.handler(event, None)["statusCode"] == want


def test_job_worker_runs_preview_and_stores_done(monkeypatch) -> None:
    s3 = _FakeS3()
    _clients(monkeypatch, s3)
    calls: list[dict] = []

    def _fake_preview(data, prompt):
        calls.append({"data": data, "prompt": prompt})
        return {"ok": True, "image_url": "https://x/y.png", "source": "test", "renders": []}

    monkeypatch.setattr(generate_lambda, "_handle_preview", _fake_preview)
    soft_before = generate_mod.GENERATE_SOFT_BUDGET_MS
    native_before = generate_mod._NATIVE_READ_TIMEOUT_S
    outpaint_before = generate_mod._OUTPAINT_BUDGET_MS
    out = generate_lambda.handler({"_job": {"id": "abcdef012345"}, "prompt": "hi", "market": "us"}, None)
    assert out == {"ok": True, "job_id": "abcdef012345"}
    assert calls and calls[0]["prompt"] == "hi"
    done = json.loads(s3.objects["brands/kodiak/jobs/abcdef012345.json"])
    assert done["state"] == "done"
    assert done["result"]["image_url"] == "https://x/y.png"
    # reused containers keep sync walls: globals restored after the worker run
    assert generate_mod.GENERATE_SOFT_BUDGET_MS == soft_before
    assert generate_mod._NATIVE_READ_TIMEOUT_S == native_before
    assert generate_mod._OUTPAINT_BUDGET_MS == outpaint_before


def test_job_worker_fault_lands_in_doc(monkeypatch) -> None:
    s3 = _FakeS3()
    _clients(monkeypatch, s3)

    def _boom(data, prompt):
        raise RuntimeError("ladder blew up")

    monkeypatch.setattr(generate_lambda, "_handle_preview", _boom)
    out = generate_lambda.handler({"_job": {"id": "abcdef012345"}, "prompt": "hi"}, None)
    assert out["job_id"] == "abcdef012345"
    doc = json.loads(s3.objects["brands/kodiak/jobs/abcdef012345.json"])
    assert doc["state"] == "error"
