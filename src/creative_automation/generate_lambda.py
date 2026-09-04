"""Lambda Function-URL handler: brief-to-hero via Nova Pro asset composition."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config

from .generate import generate_hero

DAM_S3_BUCKET = os.getenv("DAM_S3_BUCKET", "chasko-creative-dam-946179428633-us-east-1")
CORS_HEADERS = {
    "Content-Type": "application/json",
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
}


def _parse_body(event: dict[str, Any]) -> dict[str, Any]:
    """Extract the JSON payload from a Function-URL event body or a raw local dict."""
    body = event.get("body")
    if body is None:
        return event if "prompt" in event else {}
    if isinstance(body, dict):
        return body
    return json.loads(body)


def _is_options(event: dict[str, Any]) -> bool:
    """Return True when the request is a CORS preflight OPTIONS call."""
    method = event.get("requestContext", {}).get("http", {}).get("method")
    return method == "OPTIONS" or event.get("httpMethod") == "OPTIONS"


def _response(status: int, payload: dict[str, Any]) -> dict[str, Any]:
    """Shape a Function-URL response with CORS headers and a JSON string body."""
    return {"statusCode": status, "headers": CORS_HEADERS, "body": json.dumps(payload)}


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Compose a hero from real source assets driven by a brief, upload it, return a presigned URL."""
    if _is_options(event):
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    try:
        data = _parse_body(event)
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            prompt = "KODIAK - Nourishment for Today's Frontier. Keep It Wild."
        product = data.get("product", "power-cakes")

        out_path = Path(f"/tmp/{uuid4().hex}.png")  # noqa: S108 — Lambda only allows /tmp writes
        # "prompt" is the campaign brief/vibe now, not a generation seed. generate_hero
        # composes over a real product asset via Nova Pro vision, or falls back to a mock.
        result, source = generate_hero(
            product_id=product,
            product_name=product.replace("-", " ").title(),
            brief_msg=prompt,
            region=data.get("region", "us"),
            audience=data.get("audience", "active families"),
            out_path=out_path,
            idx=0,
        )

        key = f"brands/kodiak/renders/{uuid4().hex}.png"
        # SigV4 + explicit region: session-token (ASIA) creds require SigV4 presigns;
        # the boto3 default can emit SigV2 query params that S3 rejects with 403.
        region = os.getenv("AWS_REGION", "us-east-1")
        s3 = boto3.client(
            "s3",
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
        s3.put_object(
            Bucket=DAM_S3_BUCKET,
            Key=key,
            Body=result.read_bytes(),
            ContentType="image/png",
        )
        s3_uri = f"s3://{DAM_S3_BUCKET}/{key}"
        image_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": DAM_S3_BUCKET, "Key": key},
            ExpiresIn=3600,
        )

        return _response(
            200,
            {
                "ok": True,
                "image_url": image_url,
                "s3_uri": s3_uri,
                "source": source,
                "prompt": prompt,
            },
        )
    except Exception as e:  # noqa: BLE001 — surface any failure as a 500 JSON body
        return _response(500, {"ok": False, "error": str(e)})
