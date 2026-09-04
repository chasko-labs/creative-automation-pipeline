"""Lambda Function-URL handler: brief-to-hero via Nova Pro asset composition."""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config

from .generate import _safe_prompt_text, generate_hero_set

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


def _download_filename(product: str, region: str, theme: str | None) -> str:
    """Build a stable, safe .png filename for the presigned download attachment."""
    parts = [p for p in (theme or product, region) if p]
    slug = "-".join(parts) if parts else "campaign-asset"
    slug = re.sub(r"[^A-Za-z0-9-]+", "-", slug).strip("-").upper()
    slug = slug or "CAMPAIGN-ASSET"
    return f"KODIAK-CAKES-{slug}.png"


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Compose a hero from real source assets driven by a brief, upload it, return a presigned URL."""
    if _is_options(event):
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    try:
        data = _parse_body(event)
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            prompt = "KODIAK - Nourishment for Today's Frontier. Keep It Wild."
        # Strip any real celebrity name out of the client-built prompt BEFORE it becomes
        # brief_msg — the raw name trips Stability's content filter otherwise.
        prompt = _safe_prompt_text(prompt)
        product = data.get("product", "power-cakes")
        theme = data.get("theme")

        out_dir = Path(f"/tmp/{uuid4().hex}")  # noqa: S108 — Lambda only allows /tmp writes
        # "prompt" is the campaign brief/vibe now, not a generation seed. generate_hero_set
        # composes over a real product asset via Nova Pro vision / Stability, delivering all
        # three delivery ratios (1x1, 4x5, 2x3) from one call. When "theme" is present it
        # drives the IMAGE (theme wins over the product default); product is still passed
        # for iso-naming / fallback.
        renders, source, provenance = generate_hero_set(
            product_id=product,
            product_name=product.replace("-", " ").title(),
            brief_msg=prompt,
            region=data.get("region", "us"),
            audience=data.get("audience", "active families"),
            out_dir=out_dir,
            theme=theme,
        )

        # SigV4 + explicit region: session-token (ASIA) creds require SigV4 presigns;
        # the boto3 default can emit SigV2 query params that S3 rejects with 403.
        region = os.getenv("AWS_REGION", "us-east-1")
        s3 = boto3.client(
            "s3",
            region_name=region,
            config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
        )
        download_name = _download_filename(product, data.get("region", "us"), theme)

        # Upload each ratio and build the renders[] response array. The 1x1 url is also
        # mirrored to the top-level image_url for the current frontend (back-compat).
        response_renders: list[dict[str, Any]] = []
        primary_url: str | None = None
        for r in renders:
            ratio = r["ratio"]
            key = f"brands/kodiak/renders/{uuid4().hex}.png"
            s3.put_object(
                Bucket=DAM_S3_BUCKET,
                Key=key,
                Body=r["path"].read_bytes(),
                ContentType="image/png",
            )
            s3_uri = f"s3://{DAM_S3_BUCKET}/{key}"
            # per-ratio download name so each saved file names its ratio.
            disposition_name = download_name.replace(".png", f"-{ratio.upper()}.png")
            url = s3.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": DAM_S3_BUCKET,
                    "Key": key,
                    "ResponseContentDisposition": f'attachment; filename="{disposition_name}"',
                },
                ExpiresIn=3600,
            )
            response_renders.append(
                {"ratio": ratio, "image_url": url, "s3_uri": s3_uri, "w": r["w"], "h": r["h"]}
            )
            if ratio == "1x1":
                primary_url = url

        # back-compat: top-level image_url + s3_uri point at the 1x1 primary render.
        primary = next((rr for rr in response_renders if rr["ratio"] == "1x1"), response_renders[0])
        if primary_url is None:
            primary_url = primary["image_url"]

        return _response(
            200,
            {
                "ok": True,
                "image_url": primary_url,
                "s3_uri": primary["s3_uri"],
                "source": source,
                "prompt": prompt,
                "theme": theme,
                "renders": response_renders,
                "provenance": provenance,
            },
        )
    except Exception as e:  # noqa: BLE001 — surface any failure as a 500 JSON body
        return _response(500, {"ok": False, "error": str(e)})
