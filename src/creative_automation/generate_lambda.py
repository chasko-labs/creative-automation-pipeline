"""Lambda Function-URL handler: brief-to-hero via Nova Pro asset composition."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config
from PIL import Image

from . import text_rewriter
from .generate import _safe_prompt_text, generate_hero, generate_hero_set
from .locales import resolve_target_languages
from .platform_copy import generate_platform_copy
from .platforms import PLATFORMS

# NEVER-503 CONTRACT: a well-formed POST /generate returns 200 with REAL Kodiak pixels
# 100% of the time. generate_hero runs a never-fail degradation ladder A->B->C->D whose
# floor (rung D, brand-floor) does zero network I/O and cannot fail, so the old "38s then
# 503" path is gone — a slow/absent Bedrock is a fall-through to rung C (pillow-compose),
# not an error. The interactive PREVIEW mode runs ONE 1x1 hero under the 24s internal soft
# budget (well inside API Gateway's hard 30s cap); FULL mode keeps the complete 3-size set
# + localization + platform copy for the async pack builder. Default is preview so the
# interactive endpoint stays fast. The ONLY non-200 is a 400 for a malformed request body.
PREVIEW_MODE = "preview"
FULL_MODE = "full"

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


def _build_localizations(headline: str, market: str | None) -> tuple[list[dict], list[str]]:
    """Localize a headline into a market's top-3 languages (English + market top-2).

    Server-side localization: resolve the target languages for `market` (EN/ES/PT default
    when unknown), then run the headline through the rewrite/translate seam
    (text_rewriter.rewrite_all -> Nova Micro rewrite -> dialect swap -> Amazon Translate,
    per the README chain). Offline/no-creds is a documented path, never a crash: a rewrite
    that could not reach a live backend comes back tagged source="mock", which surfaces
    here as source="rewrite-fallback" (the original line per language). A live rewrite
    surfaces as source="translated".

    Returns (localizations, languages):
      localizations: [{lang_code, translate_code, headline, source}, ...] in target order
      languages:     [lang_code, ...] for the provenance object
    """
    targets = resolve_target_languages(market)
    langs = [t["lang_code"] for t in targets]
    translate_codes = {t["lang_code"]: t.get("translate_code", t["lang_code"]) for t in targets}

    localizations: list[dict] = []
    try:
        results = text_rewriter.rewrite_all(headline, market or "us", langs)
    except Exception as e:  # noqa: BLE001 — localization must never sink the generate call
        print(f"[generate_lambda] localization fallback: {e}", file=sys.stderr)
        results = [
            {"lang_code": code, "text": headline, "source": "rewrite-fallback"}
            for code in langs
        ]

    for res in results:
        code = res["lang_code"]
        # "translated" only when a live backend produced the text; mock/offline/error
        # all read as the graceful fallback so the UI can label them honestly.
        source = "translated" if res.get("source") == "bedrock:nova-micro" else "rewrite-fallback"
        localizations.append(
            {
                "lang_code": code,
                "translate_code": translate_codes.get(code, code),
                "headline": res.get("text", headline),
                "source": source,
            }
        )
    return localizations, langs


def _download_filename(product: str, region: str, theme: str | None) -> str:
    """Build a stable, safe .png filename for the presigned download attachment."""
    parts = [p for p in (theme or product, region) if p]
    slug = "-".join(parts) if parts else "campaign-asset"
    slug = re.sub(r"[^A-Za-z0-9-]+", "-", slug).strip("-").upper()
    slug = slug or "CAMPAIGN-ASSET"
    return f"KODIAK-CAKES-{slug}.png"


def _s3_client():
    """Build the S3 client with SigV4 + explicit region (ASIA session-token creds need it)."""
    # SigV4 + explicit region: session-token (ASIA) creds require SigV4 presigns; the
    # boto3 default can emit SigV2 query params that S3 rejects with 403.
    region = os.getenv("AWS_REGION", "us-east-1")
    return boto3.client(
        "s3",
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def _upload_render(s3: Any, r: dict[str, Any], download_name: str) -> dict[str, Any]:
    """Upload one render's PNG bytes and return its {ratio, image_url, s3_uri, w, h} entry."""
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
    return {"ratio": ratio, "image_url": url, "s3_uri": s3_uri, "w": r["w"], "h": r["h"]}


def _handle_preview(data: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Fast interactive path (default): ONE 1x1 control-structure hero, under 30s.

    Runs the single-ratio generate_hero (ratio=1x1, brand + paper overlay ON — the real
    GenAI hero) and SKIPS the two serial Stability outpaint extends and the localization
    rewrites — those are the >30s killers and are deferred to the async pack (FULL mode).
    Returns the SAME response shape the frontend expects (renders[] with the 1x1 entry,
    top-level image_url = the 1x1, source + provenance), so showRenderSet keeps working
    with a single-entry renders[]. Localizations + platform_copy come back empty on the
    preview and provenance notes the taller ratios + copy are deferred to the pack.
    """
    product = data.get("product", "power-cakes")
    theme = data.get("theme")
    out_dir = Path(f"/tmp/{uuid4().hex}")  # noqa: S108 — Lambda only allows /tmp writes
    hero_path = out_dir / "hero-1x1.png"
    hero_path.parent.mkdir(parents=True, exist_ok=True)

    # ONE control-structure hero at 1x1 with the brand + kraft overlays baked in. No
    # outpaint call is made on this path — that is the whole point of preview mode.
    result_path, source, provenance = generate_hero(
        product_id=product,
        product_name=product.replace("-", " ").title(),
        brief_msg=prompt,
        region=data.get("region", "us"),
        audience=data.get("audience", "active families"),
        out_path=hero_path,
        ratio="1x1",
        theme=theme,
        brand_overlay=True,
        paper_overlay=True,
    )

    with Image.open(result_path) as im:
        w, h = im.size
    render = {"ratio": "1x1", "path": result_path, "w": w, "h": h}

    s3 = _s3_client()
    download_name = _download_filename(product, data.get("region", "us"), theme)
    entry = _upload_render(s3, render, download_name)

    if isinstance(provenance, dict):
        # the preview only ships the 1x1; taller ratios + localization + per-platform
        # copy are the download-pack (FULL mode) concern, deferred off the sync path.
        provenance["ratios"] = {"1x1": "primary"}
        provenance["mode"] = PREVIEW_MODE
        provenance["deferred"] = ["4x5", "2x3", "localization", "platform_copy"]

    return {
        "ok": True,
        "image_url": entry["image_url"],
        "s3_uri": entry["s3_uri"],
        "source": source,
        "prompt": prompt,
        "theme": theme,
        "mode": PREVIEW_MODE,
        "renders": [entry],
        "provenance": provenance,
        "localizations": [],
        "platform_copy": {},
    }


def _handle_full(data: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Complete async-pack path: 3-size set + localization + per-platform copy.

    This is the original behavior — generate_hero_set delivers all three delivery ratios
    (1x1, 4x5, 2x3) via one control-structure restyle + two outpaint extends, then the
    headline is localized into the market's top-3 languages and per-platform copy is
    produced. Runs ~35s so it is NOT the interactive default; the async pack builder
    drives it via mode="full".
    """
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

    s3 = _s3_client()
    download_name = _download_filename(product, data.get("region", "us"), theme)

    # Upload each ratio and build the renders[] response array. The 1x1 url is also
    # mirrored to the top-level image_url for the current frontend (back-compat).
    response_renders: list[dict[str, Any]] = [
        _upload_render(s3, r, download_name) for r in renders
    ]
    # back-compat: top-level image_url + s3_uri point at the 1x1 primary render.
    primary = next((rr for rr in response_renders if rr["ratio"] == "1x1"), response_renders[0])
    primary_url = primary["image_url"]

    # Server-side localization (additive): deliver the campaign headline in the
    # market's top-3 languages (English + market top-2, EN/ES/PT default when the
    # market is unknown). The headline is the Nova Pro line when present, else the
    # incoming prompt. Offline-safe — never crashes the generate call.
    market = data.get("market") or data.get("region", "us")
    headline = (provenance or {}).get("headline") or prompt
    localizations, languages = _build_localizations(headline, market)
    if isinstance(provenance, dict):
        provenance["languages"] = languages
        provenance["mode"] = FULL_MODE

    # Per-platform campaign copy (additive): tailor the campaign message to each
    # social network's tone/length rules. Client may pass "platforms": [...] to
    # scope the set; default is all seven sanctioned platforms. Offline-safe — the
    # copy degrades to a deterministic on-brand template tagged source="fallback"
    # when no live Nova backend, exactly like the localization path.
    req_platforms = data.get("platforms")
    if not isinstance(req_platforms, list) or not req_platforms:
        req_platforms = list(PLATFORMS)
    product_name = product.replace("-", " ").title()
    try:
        platform_copy = generate_platform_copy(
            headline, product_name, market, platforms=req_platforms
        )
    except Exception as e:  # noqa: BLE001 — copy must never sink the generate call
        print(f"[generate_lambda] platform_copy fallback: {e}", file=sys.stderr)
        platform_copy = {}
    if isinstance(provenance, dict):
        provenance["platforms"] = list(platform_copy.keys())

    return {
        "ok": True,
        "image_url": primary_url,
        "s3_uri": primary["s3_uri"],
        "source": source,
        "prompt": prompt,
        "theme": theme,
        "mode": FULL_MODE,
        "renders": response_renders,
        "provenance": provenance,
        "localizations": localizations,
        "platform_copy": platform_copy,
    }


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Compose a hero from real source assets driven by a brief, upload it, return a presigned URL.

    Two modes (request field "mode", default "preview"):
      - preview: ONE 1x1 control-structure hero, no outpaint, no localization — fast
        enough to return inside API Gateway's hard 30s window (the interactive default).
      - full:    the complete 3-size set + localization + per-platform copy (~35s), for
        the async download-pack builder.
    """
    if _is_options(event):
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    # TOP-LEVEL VALIDATION (before the ladder): a genuinely malformed request — an
    # unparseable JSON body — is the ONLY non-200 (a 400). A well-formed POST always
    # reaches the never-fail ladder in generate_hero, which returns 200 real pixels
    # 100% of the time (rung D cannot fail), so 503 is structurally unreachable here.
    try:
        data = _parse_body(event)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return _response(400, {"ok": False, "error": f"malformed request body: {e}"})
    if not isinstance(data, dict):
        return _response(400, {"ok": False, "error": "malformed request body: expected a JSON object"})
    try:
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            prompt = "KODIAK - Nourishment for Today's Frontier. Keep It Wild."
        # Strip any real celebrity name out of the client-built prompt BEFORE it becomes
        # brief_msg — the raw name trips Stability's content filter otherwise.
        prompt = _safe_prompt_text(prompt)

        mode = (data.get("mode") or PREVIEW_MODE).strip().lower()
        if mode == FULL_MODE:
            payload = _handle_full(data, prompt)
        else:
            payload = _handle_preview(data, prompt)
        return _response(200, payload)
    except Exception as e:  # noqa: BLE001 — a well-formed POST should never reach here
        # The ladder guarantees a real-pixel 200, so an exception here is an infrastructure
        # fault (e.g. S3 upload), NOT a generation failure. Surface as 500, never 503.
        return _response(500, {"ok": False, "error": str(e)})
