"""Observer substrate tests — log schema, ring buffer, no-op trace, singleton."""
from __future__ import annotations

import json
import sys
import types

import pytest

from creative_automation import observability
from creative_automation.observability import (
    EVENT_VOCABULARY,
    LogRecord,
    Observer,
    get_observer,
    split_annotations,
    traced,
)


def test_log_event_returns_record_with_flat_json() -> None:
    obs = Observer("test-svc", xray_enabled=False)
    rec = obs.log_event("asset.add", asset_id="abc", size_bytes=12)
    assert isinstance(rec, LogRecord)
    assert rec.service == "test-svc"
    assert rec.event == "asset.add"
    assert rec.level == "info"
    assert rec.ts.endswith("Z")

    payload = json.loads(rec.to_json())
    assert payload["service"] == "test-svc"
    assert payload["event"] == "asset.add"
    assert payload["level"] == "info"
    # fields spread flat at top level, not nested
    assert payload["asset_id"] == "abc"
    assert payload["size_bytes"] == 12
    assert "fields" not in payload


def test_as_dict_matches_flat_shape() -> None:
    obs = Observer("svc", xray_enabled=False)
    rec = obs.log_event("asset.select", asset_id="xyz")
    d = rec.as_dict()
    assert {"ts", "service", "event", "level", "asset_id"}.issubset(d.keys())


def test_ring_buffer_recent_and_counts() -> None:
    obs = Observer("svc", xray_enabled=False, buffer_size=10)
    obs.log_event("asset.add", asset_id="1")
    obs.log_event("asset.add", asset_id="2")
    obs.log_event("asset.select", asset_id="1")

    recent = obs.recent(limit=2)
    assert len(recent) == 2
    # most-recent-first
    assert recent[0].event == "asset.select"
    assert recent[1].event == "asset.add"

    counts = obs.counts()
    assert counts == {"asset.add": 2, "asset.select": 1}


def test_ring_buffer_respects_maxlen() -> None:
    obs = Observer("svc", xray_enabled=False, buffer_size=2)
    obs.log_event("a")
    obs.log_event("b")
    obs.log_event("c")
    assert len(obs.recent(limit=100)) == 2
    assert obs.counts() == {"b": 1, "c": 1}


def test_trace_is_noop_when_xray_disabled() -> None:
    obs = Observer("svc", xray_enabled=False)
    # must not raise and must not require aws_xray_sdk to be installed
    with obs.trace("x", kind="raster") as seg:
        assert seg is None


def test_trace_noop_reraises_exceptions() -> None:
    obs = Observer("svc", xray_enabled=False)
    try:
        with obs.trace("x"):
            raise ValueError("boom")
    except ValueError as exc:
        assert str(exc) == "boom"
    else:
        raise AssertionError("trace should re-raise")


def test_get_observer_is_singleton() -> None:
    observability._OBSERVER = None
    a = get_observer("svc-a")
    b = get_observer("svc-b")
    assert a is b
    assert a.service == "svc-a"


def test_event_vocabulary_covers_pipeline_spans() -> None:
    for event in (
        "pipeline.build",
        "generate.image",
        "embeddings.embed",
        "rag.query",
        "rag.context_pack",
        "compose.render",
        "enhance.hero",
        "spin.edit",
        "translate.text",
        "localize.message",
        "compliance.check",
        "scorecards.score",
    ):
        assert event in EVENT_VOCABULARY


def test_split_annotations_routes_blobs_to_metadata() -> None:
    annotations, metadata = split_annotations(
        {
            "kind": "raster",
            "count": 3,
            "ratio": 0.5,
            "ok": True,
            "params": {"steps": 30},
            "tags": ["a", "b"],
            "long": "x" * 251,
            "missing": None,
        }
    )
    assert annotations == {"kind": "raster", "count": 3, "ratio": 0.5, "ok": True}
    assert set(metadata) == {"params", "tags", "long", "missing"}


class _FakeSegment:
    def __init__(self) -> None:
        self.annotations: dict[str, object] = {}
        self.metadata: dict[str, dict[str, object]] = {}
        self.exceptions: list[BaseException] = []

    def put_annotation(self, key: str, value: object) -> None:
        self.annotations[key] = value

    def put_metadata(self, key: str, value: object, namespace: str) -> None:
        self.metadata.setdefault(namespace, {})[key] = value

    def add_exception(self, exc: BaseException) -> None:
        self.exceptions.append(exc)


class _FakeRecorder:
    def __init__(self) -> None:
        self.segments: list[_FakeSegment] = []
        self.begun: list[str] = []
        self.ended = 0

    def begin_subsegment(self, name: str) -> _FakeSegment:
        self.begun.append(name)
        seg = _FakeSegment()
        self.segments.append(seg)
        return seg

    def end_subsegment(self) -> None:
        self.ended += 1


@pytest.fixture
def fake_xray(monkeypatch: pytest.MonkeyPatch) -> _FakeRecorder:
    """Install a fake aws_xray_sdk.core.xray_recorder; teardown restores sys.modules."""
    recorder = _FakeRecorder()
    core = types.ModuleType("aws_xray_sdk.core")
    core.xray_recorder = recorder  # type: ignore[attr-defined]
    pkg = types.ModuleType("aws_xray_sdk")
    monkeypatch.setitem(sys.modules, "aws_xray_sdk", pkg)
    monkeypatch.setitem(sys.modules, "aws_xray_sdk.core", core)
    return recorder


def test_traced_emits_span_with_duration_offline() -> None:
    obs = Observer("svc", xray_enabled=False)

    @traced("pipeline.build", attrs={"market": "atlanta"}, observer=obs)
    def build() -> str:
        return "done"

    assert build() == "done"
    rec = obs.recent(limit=1)[0]
    assert rec.event == "pipeline.build"
    assert rec.fields["status"] == "ok"
    assert rec.fields["market"] == "atlanta"
    assert isinstance(rec.fields["duration_ms"], float)
    assert rec.fields["duration_ms"] > 0


def test_traced_scalars_are_annotations_blobs_are_metadata(
    fake_xray: _FakeRecorder,
) -> None:
    obs = Observer("svc", xray_enabled=True)

    @traced(
        "generate.image",
        attrs={"model": "nova", "params": {"steps": 30}, "prompt": "y" * 300},
        result_attrs=True,
        observer=obs,
    )
    def render() -> dict:
        return {"asset_id": "abc", "blob": {"w": 1}}

    assert render()["asset_id"] == "abc"
    assert fake_xray.begun == ["generate.image"]
    assert fake_xray.ended == 1
    seg = fake_xray.segments[0]
    # scalars -> annotations
    assert seg.annotations["model"] == "nova"
    assert seg.annotations["asset_id"] == "abc"
    # nested/long values -> metadata under the span namespace, never annotations
    assert seg.metadata["generate.image"]["params"] == {"steps": 30}
    assert seg.metadata["generate.image"]["prompt"] == "y" * 300
    assert seg.metadata["generate.image"]["blob"] == {"w": 1}
    assert "params" not in seg.annotations
    # emitted record carries both, plus a non-zero duration
    rec = obs.recent(limit=1)[0]
    assert rec.fields["duration_ms"] > 0
    assert rec.fields["asset_id"] == "abc"
    assert rec.fields["params"] == {"steps": 30}


def test_traced_records_exceptions_and_reraises(fake_xray: _FakeRecorder) -> None:
    obs = Observer("svc", xray_enabled=True)

    @traced("rag.query", observer=obs)
    def boom() -> None:
        raise ValueError("kaput")

    with pytest.raises(ValueError, match="kaput"):
        boom()
    seg = fake_xray.segments[0]
    assert len(seg.exceptions) == 1
    assert isinstance(seg.exceptions[0], ValueError)
    rec = obs.recent(limit=1)[0]
    assert rec.event == "rag.query"
    assert rec.level == "error"
    assert rec.fields["status"] == "error"
    assert rec.fields["error_type"] == "ValueError"
    assert rec.fields["error"] == "kaput"
    assert rec.fields["duration_ms"] > 0


def test_traced_result_attrs_callable_and_bare_form() -> None:
    obs = Observer("svc", xray_enabled=False)

    @traced(event="compose.render", result_attrs=lambda r: {"layout": r[0]}, observer=obs)
    def render() -> tuple[str, dict]:
        return ("grid", {"ignored": True})

    assert render() == ("grid", {"ignored": True})
    assert obs.recent(limit=1)[0].fields["layout"] == "grid"

    @traced(observer=obs)
    def bare() -> int:
        return 1

    assert bare() == 1
    rec = obs.recent(limit=1)[0]
    assert rec.fields["status"] == "ok"
    assert rec.fields["duration_ms"] > 0


def test_trace_explicit_metadata_path(fake_xray: _FakeRecorder) -> None:
    obs = Observer("svc", xray_enabled=True)
    with obs.trace("rag.context_pack", brief_id="b1", metadata={"sources": ["s1", "s2"]}):
        pass
    seg = fake_xray.segments[0]
    assert seg.annotations == {"brief_id": "b1"}
    assert seg.metadata["rag.context_pack"] == {"sources": ["s1", "s2"]}
