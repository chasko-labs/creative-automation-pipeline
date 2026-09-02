"""Agent-friendly API for the Kodiak reference library — design / reference / training / RAG.

Marketing teams ask: "What worked for green chile families?" — the API answers by
searching the Nova multimodal vectors (or mock fallback) and returning the closest
past wins by meaning, not exact words. No third-party models.

Run locally:
  uv run python -m creative_automation.reference_api  # FastAPI at http://127.0.0.1:8182
  curl "http://127.0.0.1:8182/search?q=green%20chile%20families&type=text&k=3"

MCP: also exposed as a local MCP tool via .agents/mcp-kodiak-reference.json so
Muse / kiro agents can call `kodiak_reference_search` without HTTP.
"""
from __future__ import annotations

import json
import math
import pathlib
from typing import Literal

try:
    from fastapi import FastAPI, Query  # type: ignore
    from pydantic import BaseModel  # type: ignore

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False

from .embeddings import embed_text, embed_multimodal, EMBED_DIM

VEC_DIR = pathlib.Path("data/vectors")
JSONL = VEC_DIR / "kodiak-embeddings.jsonl"

app = FastAPI(title="Kodiak Reference Library", version="1.0.0") if HAS_FASTAPI else None  # type: ignore


class Hit(BaseModel if HAS_FASTAPI else object):  # type: ignore
    id: str = ""  # type: ignore
    type: str = ""  # type: ignore
    source: str = ""  # type: ignore
    score: float = 0.0  # type: ignore
    dim: int = EMBED_DIM  # type: ignore


def _load_vectors() -> list[dict]:
    if not JSONL.exists():
        return []
    out = []
    for line in JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            out.append(json.loads(line))
    return out


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)


def search(query: str, k: int = 5, type_filter: Literal["text", "image", "multimodal"] | None = None) -> list[dict]:
    """Agent-friendly search — returns top-k hits with scores, queryable via API or MCP."""
    qvec, _ = embed_text(query)
    vecs = _load_vectors()
    if not vecs:
        # fallback to plain localization jsonl grep when vectors not yet built
        fallbacks = []
        for p in pathlib.Path("data/localization").glob("*.jsonl"):
            for line in p.read_text(encoding="utf-8").splitlines():
                if query.lower() in line.lower():
                    j = json.loads(line)
                    fallbacks.append({"id": j.get("text", "")[:80], "type": "text", "source": j.get("text", "")[:200], "score": 0.9})
                    if len(fallbacks) >= k:
                        break
        return fallbacks[:k]

    scored = []
    for v in vecs:
        if type_filter and v.get("type") != type_filter:
            continue
        s = _cosine(qvec, v["vector"])
        scored.append({**v, "score": s})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


if HAS_FASTAPI:

    @app.get("/health")  # type: ignore
    def health():
        vecs = _load_vectors()
        return {"ok": True, "vectors": len(vecs), "index": str(JSONL) if JSONL.exists() else "not yet built — run scripts/embed-reference-library.py --all"}

    @app.get("/search")  # type: ignore
    def search_api(q: str = Query(..., description="What worked for ..."), k: int = 5, type: str | None = None):
        hits = search(q, k=k, type_filter=type)  # type: ignore
        # strip vectors for response size
        for h in hits:
            h.pop("vector", None)
        return {"query": q, "k": k, "hits": hits, "model": "amazon.nova-2-multimodal-embeddings-v1:0 (or mock fallback)"}

    @app.get("/reference/{ref_id}")  # type: ignore
    def get_reference(ref_id: str):
        for v in _load_vectors():
            if v["id"] == ref_id:
                out = dict(v)
                out.pop("vector", None)
                return out
        return {"error": "not found", "id": ref_id, "hint": "run scripts/embed-reference-library.py --all first"}

    @app.post("/embed")  # type: ignore
    def embed_api(body: dict):
        # body: {text: str, image_path?: str}
        if body.get("image_path"):
            vec, model = embed_multimodal(body.get("text", ""), body["image_path"])  # type: ignore
        else:
            vec, model = embed_text(body.get("text", ""))
        return {"model": model, "dim": len(vec), "vector": vec[:8], "note": "truncated preview — full vector is 1024 dims"}


if __name__ == "__main__":
    import uvicorn  # type: ignore

    print("Kodiak Reference Library at http://127.0.0.1:8182 — docs at /docs (FastAPI)")
    print("Try: curl 'http://127.0.0.1:8182/search?q=green%20chile%20families&k=3'")
    uvicorn.run(app, host="127.0.0.1", port=8182)
