"""S3-aware token loader with local fallback."""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

DEFAULT_LOCAL_TOKENS = Path(__file__).parent / "tokens" / "kodiak.tokens.json"
DESIGN_TOKENS = Path(__file__).parents[2] / "design" / "tokens" / "kodiak.json"


def _try_s3_tokens() -> dict | None:
    bucket = os.getenv("ASSET_STORE_S3_BUCKET", "").strip() or os.getenv("DAM_S3_BUCKET", "").strip() or None
    if not bucket:
        return None
    # only attempt if creds likely present
    try:
        import boto3  # type: ignore

        s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
        key = "brands/kodiak/tokens/kodiak.tokens.json"
        obj = s3.get_object(Bucket=bucket, Key=key)
        data = json.loads(obj["Body"].read())
        return data
    except Exception as e:  # noqa: BLE001 — S3 optional; any failure falls back to local
        print(f"[tokens] S3 load failed, falling back to local: {e}")
        return None


def _load_local() -> dict:
    for p in [DESIGN_TOKENS, DEFAULT_LOCAL_TOKENS]:
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
    raise FileNotFoundError("no local token file found; expected design/tokens/kodiak.json")


@lru_cache(maxsize=2)
def load_tokens() -> dict:
    s3 = _try_s3_tokens()
    if s3 is not None:
        return s3
    return _load_local()


def get_brand_colors(tokens: dict | None = None) -> list[str]:
    t = tokens or load_tokens()
    try:
        brand = t["kodiak"]["color"]["brand"]
        return [brand["bearBrown"]["$value"], brand["blazeOrange"]["$value"], brand["frontierGreen"]["$value"]]
    except (KeyError, TypeError):
        return ["#3B2316", "#E8530E", "#1A3C34"]


def get_canvas_dims(tokens: dict | None = None) -> dict:
    t = tokens or load_tokens()
    try:
        dims = t["kodiak"]["dimension"]["canvas"]
        out = {}
        for k, v in dims.items():
            if isinstance(v, dict) and "$value" in v:
                w, h = v["$value"]["width"], v["$value"]["height"]
                out[k] = (w, h)
        if out:
            return out
    except (KeyError, TypeError, AttributeError):
        print("[tokens] canvas dims unreadable, using defaults")
    return {"1x1": (1080, 1080), "9x16": (1080, 1920), "16x9": (1920, 1080)}


def get_typography(tokens: dict | None = None, ratio: str = "1x1") -> dict:
    t = tokens or load_tokens()
    try:
        return t["kodiak"]["typography"]["headline"][ratio]
    except (KeyError, TypeError):
        return {"$value": {"fontSize": "56px"}}
