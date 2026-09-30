"""Observability substrate — structured JSON logging + optional AWS X-Ray, offline-first.

The AssetLibrary is the first consumer: every op emits a LogRecord to stdout and opens
an X-Ray subsegment. X-Ray autodetects; when aws-xray-sdk is absent it is a pure no-op.
"""
from __future__ import annotations

import functools
import json
import os
import sys
import time
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def _xray_autodetect() -> bool:
    """True only if aws-xray-sdk importable and AWS_XRAY_SDK_ENABLED != 'false'."""
    if os.getenv("AWS_XRAY_SDK_ENABLED", "").strip().lower() == "false":
        return False
    try:
        import aws_xray_sdk.core  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


EVENT_VOCABULARY: frozenset[str] = frozenset(
    {
        # asset library + ingest (existing producers: asset_library.py, asset_ingest.py)
        "asset.add",
        "asset.dedup_hit",
        "asset.list",
        "asset.select",
        "asset.reject",
        "asset.embed",
        "asset.embed_skip",
        "asset.embed_pending",
        # pipeline engines (unblocks #42/#44-46 consumers)
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
    }
)
"""Stable event vocabulary for log_event/traced.

Membership is documentary, not enforced: log_event stays permissive so ad-hoc
events (and existing tests emitting bare names) keep working. Prefer these names
for new producers so dashboards and Logs Insights queries match a known shape.
"""

MAX_ANNOTATION_STRING_LEN = 250


def _is_annotation_value(value: object) -> bool:
    """True when a value is safe as an X-Ray annotation (indexed, filterable).

    Rule: bool/int/float and short strings go to annotations. Everything else
    (dicts, lists, long strings, bytes, None, nested objects) goes to metadata,
    which X-Ray stores unindexed and untruncated.
    """
    if isinstance(value, bool | int | float):
        return True
    return isinstance(value, str) and len(value) <= MAX_ANNOTATION_STRING_LEN


def split_annotations(values: Mapping[str, object]) -> tuple[dict[str, object], dict[str, object]]:
    """Split span attrs into (annotations, metadata) per the annotation-vs-metadata rule."""
    annotations: dict[str, object] = {}
    metadata: dict[str, object] = {}
    for key, value in values.items():
        if _is_annotation_value(value):
            annotations[key] = value
        else:
            metadata[key] = value
    return annotations, metadata


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
    def trace(
        self,
        name: str,
        metadata: Mapping[str, object] | None = None,
        **annotations: object,
    ) -> Iterator[object]:
        """X-Ray subsegment context; a pure no-op (yield None) when X-Ray disabled.

        Annotation-vs-metadata rule: scalar kwargs (bool/int/float, short str)
        become X-Ray annotations (indexed, filterable, length-capped by X-Ray).
        Non-scalars (dicts, lists, long strings, bytes, None) are routed to
        X-Ray metadata under this subsegment's namespace instead of being
        truncated as annotations. Pass ``metadata={...}`` to force the metadata
        path explicitly; it is merged with the auto-routed values.
        """
        if not self.xray_enabled:
            yield None
            return
        from aws_xray_sdk.core import xray_recorder  # type: ignore

        scalar, routed = split_annotations(annotations)
        merged: dict[str, object] = dict(routed)
        if metadata:
            merged.update(metadata)
        subsegment = xray_recorder.begin_subsegment(name)
        try:
            for key, value in scalar.items():
                try:
                    if subsegment is not None:
                        subsegment.put_annotation(key, value)
                except Exception as exc:  # noqa: BLE001 — tracing must never break the request
                    print(f"[observability] put_annotation failed: {exc}", file=sys.stderr)
            for key, value in merged.items():
                try:
                    if subsegment is not None:
                        subsegment.put_metadata(key, value, name)
                except Exception as exc:  # noqa: BLE001 — tracing must never break the request
                    print(f"[observability] put_metadata failed: {exc}", file=sys.stderr)
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


def _resolve_result_attrs(
    result_attrs: bool | str | Callable[[Any], Mapping[str, object] | None] | None,
    result: Any,
) -> dict[str, object]:
    """Derive extra span attrs from a decorated function's return value."""
    if result_attrs is False or result_attrs is None:
        return {}
    if callable(result_attrs):
        derived = result_attrs(result)
        return dict(derived) if derived else {}
    if isinstance(result_attrs, str):
        if isinstance(result, Mapping):
            nested = result.get(result_attrs)
            return dict(nested) if isinstance(nested, Mapping) else {}
        return {}
    # True: merge the result itself when it is a mapping
    return dict(result) if isinstance(result, Mapping) else {}


def traced(
    _event: str | Callable[..., Any] | None = None,
    *,
    event: str | None = None,
    attrs: Mapping[str, object] | None = None,
    result_attrs: bool | str | Callable[[Any], Mapping[str, object] | None] | None = False,
    observer: Observer | None = None,
) -> Any:
    """Decorate a function so each call opens a span with duration + exception recording.

    Usable bare (``@traced``), with an event name (``@traced("pipeline.build")``),
    or with keywords (``@traced(event="rag.query", attrs={...})``). Without an
    explicit event the function's qualified name is used.

    Each call:

    - opens ``observer.trace(event, ...)``: static ``attrs`` scalars land as
      X-Ray annotations, large/nested values as X-Ray metadata;
    - records exceptions on the subsegment (via ``trace``) and re-raises;
    - merges returned attrs when ``result_attrs`` is set: True merges a
      Mapping result, a str key merges ``result[key]``, a callable merges
      whatever mapping it returns for the result;
    - always emits a ``log_event`` record with ``duration_ms`` (float,
      non-zero), ``status`` ("ok"/"error"), and the merged attrs flattened
      into the log fields — so offline runs still get a span-shaped record.

    Example::

        obs = Observer("pipeline", xray_enabled=False)

        @traced("generate.image", attrs={"model": "nova"}, observer=obs)
        def render(prompt: str) -> dict:
            return {"asset_id": "abc", "params": {"steps": 30}}
    """
    name = _event if isinstance(_event, str) else event

    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        span = name or fn.__qualname__

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            obs = observer if observer is not None else get_observer()
            static = dict(attrs) if attrs else {}
            start = time.perf_counter()
            try:
                with obs.trace(span, **static) as seg:
                    result = fn(*args, **kwargs)
                    extra = _resolve_result_attrs(result_attrs, result)
                    if extra and seg is not None:
                        scalar, blob = split_annotations(extra)
                        for key, value in scalar.items():
                            try:
                                seg.put_annotation(key, value)
                            except Exception as exc:  # noqa: BLE001 — tracing never breaks the request
                                print(
                                    f"[observability] put_annotation failed: {exc}",
                                    file=sys.stderr,
                                )
                        for key, value in blob.items():
                            try:
                                seg.put_metadata(key, value, span)
                            except Exception as exc:  # noqa: BLE001 — tracing never breaks the request
                                print(
                                    f"[observability] put_metadata failed: {exc}",
                                    file=sys.stderr,
                                )
                duration_ms = (time.perf_counter() - start) * 1000.0
                fields: dict[str, object] = dict(static)
                fields.update(extra)
                fields["duration_ms"] = duration_ms
                fields["status"] = "ok"
                obs.log_event(span, **fields)
                return result
            except Exception as exc:
                duration_ms = (time.perf_counter() - start) * 1000.0
                fields = dict(static)
                fields["duration_ms"] = duration_ms
                fields["status"] = "error"
                fields["error_type"] = type(exc).__name__
                fields["error"] = str(exc)
                obs.log_event(span, level="error", **fields)
                raise

        return wrapper

    if callable(_event):
        return decorator(_event)
    return decorator


_OBSERVER: Observer | None = None


def get_observer(service: str = "kodiak-creative") -> Observer:
    """Process-singleton Observer so all callers share one ring buffer."""
    global _OBSERVER
    if _OBSERVER is None:
        _OBSERVER = Observer(service)
    return _OBSERVER
