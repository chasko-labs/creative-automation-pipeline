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

from . import embeddings
from ._datapaths import data_path

LIBRARY_REL = ("vectors", "kodiak-embeddings.jsonl")
LIBRARY_MAX_RECORDS = int(os.getenv("KODIAK_DIRECTOR_LIBRARY_MAX", "4000"))

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
    """Parse the committed embedding library once; cache the captioned entries."""
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
                norm = math.sqrt(sum(v * v for v in vec)) or 1.0
                entries.append(
                    {
                        "id": str(record.get("id", "")),
                        "text": text,
                        "vector": [float(v) for v in vec],
                        "norm": norm,
                    }
                )
    except Exception:
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
    except Exception:
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
