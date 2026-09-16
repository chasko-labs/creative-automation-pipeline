"""Retrieval grounding for the Kodiak art director — the training library at serve time.

The brand voice model was trained on the Kodiak social corpus; this module puts that
same corpus behind it at inference. retrieve() embeds the incoming request, runs a
cosine top-k over the committed embedding library (data/vectors/kodiak-embeddings.jsonl,
Nova multimodal 1024-dim), and returns captioned brand examples the director folds
into its ask. No independent vector service, no new infra.

Discipline (mirrors the ladder's never-fail contract):
- never raises: missing library, failed embed, and empty results all yield [].
- never grounds on mock vectors: embeddings.embed_text degrades to a deterministic
  mock tagged "mock:*" offline — mock vectors retrieve arbitrary records, which is
  worse than no grounding, so a mock model_used refuses retrieval outright.
- lazy + cached: the 46MB library parses once per warm container, norms precomputed.
"""
from __future__ import annotations

import json
import math
import os
import re

from . import embeddings
from ._datapaths import data_path

LIBRARY_REL = ("vectors", "kodiak-embeddings.jsonl")
LIBRARY_MAX_RECORDS = int(os.getenv("KODIAK_DIRECTOR_LIBRARY_MAX", "4000"))

_HEX_TOKEN = re.compile(r"\b[0-9a-f]{6,}\b")
_NUMERIC_TOKEN = re.compile(r"^\d{1,8}$")


def _is_voice_caption(text: str) -> bool:
    """True when a caption reads like brand voice, not a DAM filename.

    PROVEN IN PROD (2026-09-08): 2,289 of the library's 2,403 "captions" are
    hash-laden asset titles (e.g. "88b5787ee037 Kodiak Recipe ... 4eb0b2").
    Folded in-ask, they make the voice model decline — and a declined attempt
    is a wasted Bedrock round-trip that always falls back to stock Nova. Gate
    here so top-k grounds on voice: real sentences, no hash runs, and at most
    one bare numeric token (portfolio titles carry MMYY-style date clusters
    like "1025 0148 1"; real lines carry at most one — "5g" and "100%" have
    alpha/% suffixes and do not count as bare numerics).
    """
    words = [w for w in re.split(r"\s+", text) if w.isalpha() and len(w) > 1]
    if len(words) < 4 or _HEX_TOKEN.search(text.lower()):
        return False
    bare_numbers = sum(1 for w in re.split(r"\s+", text) if _NUMERIC_TOKEN.match(w))
    return bare_numbers <= 1

_library_cache: list[dict] | None = None


def _record_text(record: dict) -> str | None:
    """The brand-voice text a record contributes, or None when it has none."""
    meta = record.get("metadata") or {}
    caption = (meta.get("caption") or "").strip()
    if caption:
        return caption
    if record.get("type") == "text":
        text = (meta.get("text") or meta.get("body") or "").strip()
        return text or None
    return None


def _load_library() -> list[dict]:
    """Parse the committed embedding library once; cache voice-quality entries.

    Filename-grade captions are dropped at load (see _is_voice_caption) so
    cosine ranks real brand sentences, not DAM titles.
    """
    global _library_cache
    if _library_cache is not None:
        return _library_cache
    entries: list[dict] = []
    try:
        path = data_path(*LIBRARY_REL)
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh):
                if i >= LIBRARY_MAX_RECORDS:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                text = _record_text(record)
                vec = record.get("vector")
                if not text or not isinstance(vec, list) or not vec:
                    continue
                if not _is_voice_caption(text):
                    continue
                norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                entries.append(
                    {
                        "id": str(record.get("id", "")),
                        "text": text,
                        "vector": [float(v) for v in vec],
                        "norm": norm,
                    }
                )
    except (OSError, AttributeError, ValueError, TypeError):
        entries = []
    _library_cache = entries
    return entries


def _cosine(query: list[float], qnorm: float, entry: dict) -> float:
    dot = sum(q * e for q, e in zip(query, entry["vector"]))
    denom = qnorm * entry["norm"]
    return dot / denom if denom else 0.0


def retrieve(query_text: str, k: int = 3) -> tuple[list[dict], str]:
    """Top-k brand-voice examples for the request. Returns (examples, model_used).

    examples are [{id, caption, score}] sorted by descending cosine score. Returns
    ([], model_used) whenever grounding is unavailable — including when the embed
    fell back to mock vectors, which must never drive retrieval.
    """
    query = (query_text or "").strip()
    if not query or k <= 0:
        return [], "none"
    try:
        qvec, model_used = embeddings.embed_text(query)
    except Exception:  # noqa: BLE001 — never-raise grounding contract; failed embed yields []
        return [], "embed-failed"
    if not qvec or str(model_used).startswith("mock"):
        return [], str(model_used)
    qnorm = math.sqrt(sum(v * v for v in qvec)) or 1.0
    library = _load_library()
    if not library:
        return [], model_used
    scored = sorted(
        (
            {
                "id": e["id"],
                "caption": e["text"],
                "score": round(_cosine(qvec, qnorm, e), 4),
            }
            for e in library
        ),
        key=lambda r: r["score"],
        reverse=True,
    )
    return scored[:k], model_used


def clear_cache() -> None:
    """Test hook — drop the parsed library so the next retrieve re-reads."""
    global _library_cache
    _library_cache = None
