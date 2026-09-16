"""Observer substrate tests — log schema, ring buffer, no-op trace, singleton."""
from __future__ import annotations

import json

from creative_automation import observability
from creative_automation.observability import LogRecord, Observer, get_observer


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
