"""Nova multimodal embeddings — design / reference / training / RAG.

Current standards (AWS blog + Bedrock list-foundation-models --by-output-modality EMBEDDING, 2025-09-02):
- model: amazon.nova-2-multimodal-embeddings-v1:0  (blog: amazon nova multimodal embeddings now available)
- fallback text-only: amazon.titan-embed-text-v2:0 (1024 dims, S3 Vectors native)
- dims: 3072 / 1024 / 384 / 256 — we use 1024 (balance retrieval quality vs storage/cost)
- endpoint: bedrock-runtime InvokeModel (not Converse) — embeddings are data plane, not chat
- body type: taskType SINGLE_EMBEDDING / singleEmbeddingParams { embeddingDimension, text/image }

No third-party models — only Amazon family (Nova, Titan). References checked via
context7 / aws-mcp-readonly docs and `aws bedrock list-foundation-models`.

Usage: background agents walk data/raw-ingest/kodiakcakes/images/, references/,
design/tokens/ and call embed_*() to build S3 Vectors + Knowledge Base.
"""
from __future__ import annotations

import base64
import json
import hashlib
import os
from pathlib import Path
from typing import Literal

EMBED_MODEL = os.getenv("BEDROCK_EMBED_MODEL", "amazon.nova-2-multimodal-embeddings-v1:0")
EMBED_DIM = int(os.getenv("BEDROCK_EMBED_DIM", "1024"))
BEDROCK_REGION = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))

# Fallback model for text-only when multimodal not enabled in account/region
FALLBACK_TEXT_MODEL = os.getenv("BEDROCK_TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0")


def _boto_client():
    try:
        import boto3  # type: ignore
        from botocore.exceptions import BotoCoreError  # noqa: F401

        return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    except Exception as e:  # noqa: BLE001
        print(f"[embed] boto3 unavailable: {e}")
        return None


def _mock_embedding(text: str | None = None, dim: int = EMBED_DIM) -> list[float]:
    """Deterministic mock for local dev without AWS creds — hash-seeded floats normalized."""
    seed = hashlib.sha256((text or "image").encode()).digest()
    vals = []
    for i in range(dim):
        # cycle through seed bytes, map to [-1,1]
        b = seed[i % len(seed)]
        vals.append((b / 128.0) - 1.0)
    # L2 normalize so cosine works
    import math

    norm = math.sqrt(sum(v * v for v in vals)) or 1.0
    return [v / norm for v in vals]


def embed_text(text: str, dim: int = EMBED_DIM) -> tuple[list[float], str]:
    """Embed plain text with Nova multimodal (or Titan fallback). Returns (vector, model_used)."""
    client = _boto_client()
    if client is None:
        return _mock_embedding(text, dim), "mock:titan-nova"

    body = {
        "taskType": "SINGLE_EMBEDDING",
        "singleEmbeddingParams": {
            "embeddingDimension": dim,
            "text": {"truncationMode": "END", "value": text},
        },
    }
    try:
        resp = client.invoke_model(
            modelId=EMBED_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(resp["body"].read())
        vec = payload.get("embeddings", [{}])[0].get("embedding") or payload.get("embedding")
        if vec is None:
            raise ValueError(f"unexpected payload {list(payload.keys())}")
        return vec, EMBED_MODEL
    except Exception as e:  # noqa: BLE001
        # fallback to Titan text
        body2 = {"inputText": text, "dimensions": dim, "normalize": True}
        try:
            resp2 = client.invoke_model(
                modelId=FALLBACK_TEXT_MODEL,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body2),
            )
            payload2 = json.loads(resp2["body"].read())
            vec2 = payload2.get("embedding")
            if vec2 is None:
                raise
            return vec2, FALLBACK_TEXT_MODEL
        except Exception as e2:
            print(f"[embed_text] both models failed, mock fallback: {e} / {e2}")
            return _mock_embedding(text, dim), "mock:titan-nova"


def embed_image(image_path: str | Path, text_hint: str | None = None, dim: int = EMBED_DIM) -> tuple[list[float], str]:
    """Embed image (+ optional text hint) with Nova multimodal. Falls back to mock if no creds."""
    p = Path(image_path)
    client = _boto_client()
    if client is None or not p.exists():
        hint = text_hint or p.name
        return _mock_embedding(hint, dim), "mock:nova-image"

    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    # Guess mime
    ext = p.suffix.lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else "image/png" if ext == "png" else f"image/{ext}"
    # Nova 2 multimodal expects interleaved content: we send as image + optional text in same request
    # Blog shows S3 Vectors client with metadata original format + content; here we use singleEmbeddingParams with image
    body = {
        "taskType": "SINGLE_EMBEDDING",
        "singleEmbeddingParams": {
            "embeddingDimension": dim,
            "images": [{"format": mime.split("/")[1], "source": {"bytes": b64}}],
        },
    }
    if text_hint:
        body["singleEmbeddingParams"]["text"] = {"truncationMode": "END", "value": text_hint}
    try:
        resp = client.invoke_model(
            modelId=EMBED_MODEL,
            contentType="application/json",
            accept="application/json",
            body=json.dumps(body),
        )
        payload = json.loads(resp["body"].read())
        vec = payload.get("embeddings", [{}])[0].get("embedding") or payload.get("embedding")
        if vec is None:
            raise ValueError(f"unexpected image payload {list(payload.keys())}")
        return vec, EMBED_MODEL
    except Exception as e:
        print(f"[embed_image] fallback mock for {p.name}: {e}")
        return _mock_embedding(text_hint or p.name, dim), "mock:nova-image"


def embed_multimodal(text: str, image_path: str | Path, dim: int = EMBED_DIM) -> tuple[list[float], str]:
    """Interleaved text + image — the RAG sweet spot for design/reference lookup."""
    return embed_image(image_path, text_hint=text, dim=dim)


def embed_batch(
    items: list[dict],
    out_dir: Path | str = "data/vectors",
    dim: int = EMBED_DIM,
) -> Path:
    """Batch helper for background agents — walks items of {id, type, path/text} and writes JSONL vectors.

    Writes to out_dir/kodiak-embeddings.jsonl with fields: id, type, source, dim, model, vector.
    Also writes a tiny manifest for S3 Vectors ingestion.
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    jsonl = out / "kodiak-embeddings.jsonl"
    # overwrite
    jsonl.write_text("")
    for item in items:
        iid = item["id"]
        itype = item.get("type", "text")
        if itype == "image" or (itype == "multimodal" and item.get("path")):
            vec, model = embed_image(item["path"], text_hint=item.get("text"), dim=dim) if itype == "image" else embed_multimodal(item["text"], item["path"], dim=dim)
            src = str(item.get("path", iid))
        else:
            vec, model = embed_text(item.get("text", iid), dim=dim)
            src = item.get("text", iid)[:120]
        line = {"id": iid, "type": itype, "source": src, "dim": dim, "model": model, "vector": vec}
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")

    # manifest for S3 Vectors: how many, which model, dims
    manifest = {
        "model": EMBED_MODEL,
        "fallback": FALLBACK_TEXT_MODEL,
        "dim": dim,
        "count": len(items),
        "vector_bucket_note": "S3 Vectors uses a dedicated vector bucket (vectorBucketArn), not a regular S3 bucket — see https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_S3VectorsConfiguration.html",
        "output": str(jsonl),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return jsonl
