"""Observability substrate — structured JSON logging + optional AWS X-Ray, offline-first.

The AssetLibrary is the first consumer: every op emits a LogRecord to stdout and opens
an X-Ray subsegment. X-Ray autodetects; when aws-xray-sdk is absent it is a pure no-op.
"""
from __future__ import annotations

import json
import os
import sys
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime


def _xray_autodetect() -> bool:
    """True only if aws-xray-sdk importable and AWS_XRAY_SDK_ENABLED != 'false'."""
    if os.getenv("AWS_XRAY_SDK_ENABLED", "").strip().lower() == "false":
        return False
    try:
        import aws_xray_sdk.core  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


@dataclass(frozen=True)
class LogRecord:
    """One structured log line — flat JSON when serialized (fields spread at top level)."""

    ts: str
    service: str
    event: str
    level: str
    fields: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        """Flat dict: ts, service, event, level, then fields spread at top level."""
        out: dict[str, object] = {
            "ts": self.ts,
            "service": self.service,
            "event": self.event,
            "level": self.level,
        }
        out.update(self.fields)
        return out

    def to_json(self) -> str:
        """Flat single-line JSON object."""
        return json.dumps(self.as_dict(), separators=(",", ":"), default=str)


class Observer:
    """Structured logger + X-Ray tracer with an in-process ring buffer for /report."""

    def __init__(
        self,
        service: str,
        *,
        xray_enabled: bool | None = None,
        buffer_size: int = 500,
    ) -> None:
        self.service = service
        self.xray_enabled = _xray_autodetect() if xray_enabled is None else xray_enabled
        self._buffer: deque[LogRecord] = deque(maxlen=buffer_size)

    def log_event(self, event: str, level: str = "info", **fields: object) -> LogRecord:
        """Build a LogRecord, print flat JSON to stdout, append to ring buffer, return it."""
        ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        record = LogRecord(ts=ts, service=self.service, event=event, level=level, fields=dict(fields))
        print(record.to_json())
        self._buffer.append(record)
        return record

    @contextmanager
    def trace(self, name: str, **annotations: object) -> Iterator[object]:
        """X-Ray subsegment context; a pure no-op (yield None) when X-Ray disabled."""
        if not self.xray_enabled:
            yield None
            return
        from aws_xray_sdk.core import xray_recorder  # type: ignore

        subsegment = xray_recorder.begin_subsegment(name)
        try:
            for key, value in annotations.items():
                try:
                    if subsegment is not None:
                        subsegment.put_annotation(key, value)
                except Exception as exc:  # noqa: BLE001 — tracing must never break the request
                    print(f"[observability] put_annotation failed: {exc}", file=sys.stderr)
            yield subsegment
        except Exception as exc:
            try:
                if subsegment is not None:
                    subsegment.add_exception(exc)
            except Exception as add_exc:  # noqa: BLE001 — tracing must never mask the real error
                print(f"[observability] add_exception failed: {add_exc}", file=sys.stderr)
            raise
        finally:
            try:
                xray_recorder.end_subsegment()
            except Exception as end_exc:  # noqa: BLE001 — tracing teardown never raises
                print(f"[observability] end_subsegment failed: {end_exc}", file=sys.stderr)

    def recent(self, limit: int = 50) -> list[LogRecord]:
        """Last N records, most-recent-first."""
        items = list(self._buffer)
        items.reverse()
        return items[:limit]

    def counts(self) -> dict[str, int]:
        """Event -> occurrence count over the ring buffer."""
        out: dict[str, int] = {}
        for record in self._buffer:
            out[record.event] = out.get(record.event, 0) + 1
        return out


_OBSERVER: Observer | None = None


def get_observer(service: str = "kodiak-creative") -> Observer:
    """Process-singleton Observer so all callers share one ring buffer."""
    global _OBSERVER
    if _OBSERVER is None:
        _OBSERVER = Observer(service)
    return _OBSERVER
