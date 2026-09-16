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
import hashlib
import json
import os
import sys
from pathlib import Path

EMBED_MODEL = os.getenv("BEDROCK_EMBED_MODEL", "amazon.nova-2-multimodal-embeddings-v1:0")
EMBED_DIM = int(os.getenv("BEDROCK_EMBED_DIM", "1024"))
BEDROCK_REGION = os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1"))
# GENERIC_INDEX = build embeddings optimized as a vector-store index (all modalities), per Nova 2 schema
EMBED_PURPOSE = os.getenv("BEDROCK_EMBED_PURPOSE", "GENERIC_INDEX")

# Fallback model for text-only when multimodal not enabled in account/region
FALLBACK_TEXT_MODEL = os.getenv("BEDROCK_TITAN_EMBED_MODEL", "amazon.titan-embed-text-v2:0")


# Fail-fast client config (wall repair): the embed call sits inside the
# grounded-director attempt, itself bounded at 8s — but a bare client (no
# timeouts, default retries) turned one slow Nova embed + Titan fallback into a
# ~14s hole PROVEN IN PROD, starving the restyle rung. Same fix dam.py already
# carries: bound every call so a stall fails fast into the attempt bound.
try:
    from botocore.config import Config as _BotoConfig
except ImportError:  # boto3 optional — local-only mode still works
    _BotoConfig = None  # type: ignore


def _boto_client():
    try:
        import boto3  # type: ignore
        from botocore.exceptions import BotoCoreError  # noqa: F401

        cfg = None
        if _BotoConfig is not None:
            cfg = _BotoConfig(
                connect_timeout=2,
                read_timeout=5,
                # max_attempts=1 (no retry): a transient embed blip fails fast
                # into the Titan fallback, which has the same bound — mirrors
                # dam.py. Merged total is initial + 1 retry-config slot.
                retries={"max_attempts": 1, "mode": "standard"},
            )
        return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION, config=cfg)
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
        "schemaVersion": "nova-multimodal-embed-v1",
        "taskType": "SINGLE_EMBEDDING",
        "singleEmbeddingParams": {
            "embeddingPurpose": EMBED_PURPOSE,
            "embeddingDimension": dim,
            # Nova max text is 8192 chars; truncate defensively so END truncationMode is not needed to fail
            "text": {"truncationMode": "END", "value": text[:8192]},
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
        except Exception as e2:  # noqa: BLE001 — fallback chain must never throw; both errors print
            print(f"[embed_text] both models failed, mock fallback: {e} / {e2}")
            return _mock_embedding(text, dim), "mock:titan-nova"


def _extract_vec(payload: dict) -> list[float] | None:
    embs = payload.get("embeddings")
    if isinstance(embs, list) and embs:
        return embs[0].get("embedding")
    return payload.get("embedding")


def _invoke(client, body: dict) -> list[float]:
    resp = client.invoke_model(
        modelId=EMBED_MODEL,
        contentType="application/json",
        accept="application/json",
        body=json.dumps(body),
    )
    payload = json.loads(resp["body"].read())
    vec = _extract_vec(payload)
    if vec is None:
        raise ValueError(f"unexpected image payload {list(payload.keys())}")
    return vec


def embed_image(image_path: str | Path, text_hint: str | None = None, dim: int = EMBED_DIM) -> tuple[list[float], str]:
    """Embed a single image with Nova 2 multimodal (inline base64). Falls back to mock only if no creds/file.

    Nova 2 SINGLE_EMBEDDING allows exactly one modality per call, so text_hint cannot be sent
    in the same request as the image. The image itself is embedded; the caption travels in metadata.
    """
    p = Path(image_path)
    client = _boto_client()
    if client is None or not p.exists():
        return _mock_embedding(text_hint or p.name, dim), "mock:nova-image"

    b64 = base64.b64encode(p.read_bytes()).decode("utf-8")
    ext = p.suffix.lower().lstrip(".")
    # Nova accepts png|jpeg|gif|webp; normalize jpg->jpeg, JPG/PNG case, jpeg passthrough
    fmt = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "gif": "gif", "webp": "webp"}.get(ext)
    if fmt is None:
        # unsupported (pdf, js, css, tif, etc) — caller should filter these out; mock as last resort
        return _mock_embedding(text_hint or p.name, dim), "mock:nova-image"

    def _body(source: dict) -> dict:
        return {
            "schemaVersion": "nova-multimodal-embed-v1",
            "taskType": "SINGLE_EMBEDDING",
            "singleEmbeddingParams": {
                "embeddingPurpose": EMBED_PURPOSE,
                "embeddingDimension": dim,
                "image": {"format": fmt, "detailLevel": "STANDARD_IMAGE", "source": source},
            },
        }

    # SourceObject inline-bytes shape confirmed against live Bedrock 2026: {"bytes": "<base64>"}
    # returns a real IMAGE embedding. Kept as a list so an alternate shape can be appended if the
    # API changes, rather than silently degrading to mock.
    source_shapes = [{"bytes": b64}]
    last_err: Exception | None = None
    for source in source_shapes:
        try:
            return _invoke(client, _body(source)), EMBED_MODEL
        except Exception as e:  # noqa: BLE001
            last_err = e
    print(f"[embed_image] real call failed for {p.name}: {last_err}")
    return _mock_embedding(text_hint or p.name, dim), "mock:nova-image"


def embed_multimodal(text: str, image_path: str | Path, dim: int = EMBED_DIM) -> tuple[list[float], str]:
    """Image-primary embed for design/reference lookup.

    Nova 2 SINGLE_EMBEDDING is single-modality per request, so this embeds the image and the
    text becomes retrieval metadata rather than being fused into the same vector.
    """
    return embed_image(image_path, text_hint=text, dim=dim)


# --------------------------------------------------------------------------- S3 Vectors store
# S3 Vectors PutVectors API shape CONFIRMED via botocore introspection of the installed
# s3vectors model (client.meta.service_model.operation_model("PutVectors")):
#   input: vectorBucketName (str), indexName (str), vectors (list, required)
#   vector item: key (str, required), data (structure, required), metadata (structure)
#   data structure: {"float32": [<floats>]}
# GetVectors input: vectorBucketName, indexName, keys (list, required), returnData,
# returnMetadata; output: vectors (list) — an absent key returns an empty list, a missing
# bucket/index raises NotFoundException. That empty-list signal is the dedup-skip gate.
_S3VECTORS_REGION = os.getenv("AWS_REGION", "us-east-1")

# S3 Vectors caps per-vector metadata size; keep values small and truncate long strings so a
# fat filename or s3_uri can never blow the metadata limit and reject the whole put.
_META_STR_CAP = 512


def _s3vectors_client():
    """Build a boto3 s3vectors client; None when boto3/creds absent (offline path)."""
    try:
        import boto3  # type: ignore

        return boto3.client("s3vectors", region_name=_S3VECTORS_REGION)
    except Exception as e:  # noqa: BLE001
        print(f"[vectors] s3vectors client unavailable: {e}", file=sys.stderr)
        return None


def _clean_metadata(metadata: dict | None) -> dict:
    """Coerce metadata to small scalar fields; truncate long strings defensively."""
    out: dict = {}
    for k, v in (metadata or {}).items():
        if v is None:
            continue
        if isinstance(v, str):
            out[str(k)] = v[:_META_STR_CAP]
        elif isinstance(v, (int, float, bool)):
            out[str(k)] = v
        else:
            out[str(k)] = str(v)[:_META_STR_CAP]
    return out


def vector_exists(key: str, *, bucket: str | None = None, index: str | None = None) -> bool:
    """True when a vector for `key` already lives in the index — the dedup-skip gate.

    GetVectors returns an empty vectors list for an absent key (not an error), so a
    non-empty list means the vector is already stored and the caller can SKIP re-embedding
    a known duplicate. Returns False on any unconfigured/offline/error condition (never
    raises) so a probe failure degrades to "embed anyway" rather than crashing ingest.
    """
    bucket = bucket or os.getenv("KODIAK_VECTOR_BUCKET")
    index = index or os.getenv("KODIAK_VECTOR_INDEX")
    if not bucket or not index:
        return False
    client = _s3vectors_client()
    if client is None:
        return False
    try:
        resp = client.get_vectors(
            vectorBucketName=bucket,
            indexName=index,
            keys=[key],
            returnData=False,
            returnMetadata=False,
        )
        return bool(resp.get("vectors"))
    except Exception as e:  # noqa: BLE001 — probe failure degrades to "not present"
        print(f"[vectors] get_vectors probe failed for {key}: {e}", file=sys.stderr)
        return False


def put_vector(
    vector: list[float],
    key: str,
    metadata: dict | None = None,
    *,
    bucket: str | None = None,
    index: str | None = None,
) -> bool:
    """Write one vector to the S3 Vectors index. Returns True on success, False otherwise.

    Never raises: an unset bucket/index, missing boto3, absent creds, or an API error all
    return False so the caller can degrade to embed_pending and keep the asset. The shape
    (vectorBucketName/indexName/vectors[{key,data:{float32},metadata}]) is the introspected
    live model form. Metadata is capped small (asset_id/filename/kind/sha256/etc — never raw
    bytes) so it stays under the S3 Vectors per-vector metadata limit.
    """
    bucket = bucket or os.getenv("KODIAK_VECTOR_BUCKET")
    index = index or os.getenv("KODIAK_VECTOR_INDEX")
    if not bucket or not index:
        return False
    if not vector:
        return False
    client = _s3vectors_client()
    if client is None:
        return False
    try:
        client.put_vectors(
            vectorBucketName=bucket,
            indexName=index,
            vectors=[
                {
                    "key": key,
                    "data": {"float32": [float(x) for x in vector]},
                    "metadata": _clean_metadata(metadata),
                }
            ],
        )
        return True
    except Exception as e:  # noqa: BLE001 — degrade to embed_pending, never crash ingest
        print(f"[vectors] put_vectors failed for {key}: {e}", file=sys.stderr)
        return False


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
    n_written = 0
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
        # pass-through provenance metadata (channel, caption, hashtags, timestamp, product, cue, etc.)
        if isinstance(item.get("metadata"), dict):
            line["metadata"] = item["metadata"]
        with open(jsonl, "a", encoding="utf-8") as f:
            f.write(json.dumps(line) + "\n")
        n_written += 1

    # manifest for S3 Vectors: how many, which model, dims
    manifest = {
        "model": EMBED_MODEL,
        "fallback": FALLBACK_TEXT_MODEL,
        "dim": dim,
        "count": n_written,
        "vector_bucket_note": "S3 Vectors uses a dedicated vector bucket (vectorBucketArn), not a regular S3 bucket — see https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_S3VectorsConfiguration.html",
        "output": str(jsonl),
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return jsonl
