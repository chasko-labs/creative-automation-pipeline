"""Lambda Function-URL handler: brief-to-hero via Nova Pro asset composition."""
from __future__ import annotations

import base64
import concurrent.futures
import json
import os
import re
import sys
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

import boto3
from botocore.config import Config
from botocore.exceptions import ConnectTimeoutError, ReadTimeoutError
from PIL import Image, ImageOps

from . import asset_browser, text_rewriter
from .generate import (
    GENERATE_SOFT_BUDGET_MS,
    KEEP_IT_WILD_THEME,
    LAYER_COBADGE,
    _apply_brand_overlay,
    _brand_floor,
    _finalize_render,
    _OUTPAINT_BUDGET_MS,
    _OUTPAINT_RESERVE_MS,
    _blend_idea_base,
    _pillow_outpaint_fallback,
    _STABILITY_RUNG_ON,
    _stability_outpaint,
    _recipe_card_defaults,
    _safe_prompt_text,
    _validate_recipe_fields,
    build_copy_sidecar,
    generate_hero,
    generate_hero_set,
    normalize_layers,
)
from .locales import resolve_target_languages
from .platform_copy import (
    PlatformCopyValidationError,
    build_platform_copy_response,
    clean_brand_copy,
    fallback_platform_copy,
)

# NOTE: full mode no longer calls platform_copy/localize in-request (frontend owns
# both — see _handle_full). The modules stay imported by tests directly.
from .platforms import PLATFORMS, RATIO_DIMS

# NEVER-503 CONTRACT: a well-formed POST /generate returns 200 with REAL Kodiak pixels
# 100% of the time. generate_hero runs a never-fail degradation ladder A->B->C->D whose
# floor (rung D, brand-floor) does zero network I/O and cannot fail, so the old "38s then
# 503" path is gone — a slow/absent Bedrock is a fall-through to rung C (pillow-compose),
# not an error. The interactive PREVIEW mode runs ONE 1x1 hero plus four derived
# tiles (9x16/16x9 attempt a live outpaint behind the preview budget gate, every
# gated-out tile ships its Pillow pad) under the 24s internal soft budget (well
# inside API Gateway's hard 30s cap); FULL mode keeps the complete GenAI-composed
# set + localization + platform copy for the async pack builder. Default is
# preview so the interactive endpoint stays fast. The ONLY non-200 is a 400 for
# a malformed request body.
# PREVIEW mode returns FIVE tiles: the ONE 1x1 hero plus the derived tiles —
# still well inside the soft budget; pads stay the fallback for every gated-out
# ratio, so the wall guarantee holds with or without a live extend.
PREVIEW_MODE = "preview"
FULL_MODE = "full"

# Preview tile set: the 1x1 primary first (top-level image_url back-compat +
# eager-load order unchanged) plus the four derived tiles. 4x5/blog are always
# server-side Pillow cover-pads of the finished 1x1 — zero extra model calls.
# 9x16/16x9 attempt a live Stability outpaint extend of the finished 1x1 when
# the preview budget gate passes (sprint-2 item 11), else the same Pillow pad —
# pads stay the fallback on every path, never an error. Dims come from the
# platform matrix SoT (platforms.RATIO_DIMS, issue #201 item 3), never a second
# table.
_PREVIEW_PAD_RATIOS = ("4x5", "9x16", "16x9", "blog")
# Preview tiles eligible for a live outpaint extend. 4x5 stays a deterministic
# pad (mirrors generate_hero_set: at most the two tall/wide extends ever run);
# blog (1200x630 OG hero) is a downscale of the 1x1, never an extend.
_PREVIEW_OUTPAINT_RATIOS = ("9x16", "16x9")


def _preview_now() -> float:
    """Preview wall-clock seam (time.monotonic). Monkeypatched in tests to move the clock."""
    return time.monotonic()

# STRUCTURAL OUTER-DEADLINE WALL (#118): the never-503 contract above relies on the
# per-rung remaining_ms() budget gates inside generate_hero to abandon a stalled rung
# gracefully. Those gates are QUALITY — they make the COMMON case drop to rung C with real
# generated pixels well inside the budget. But a per-call botocore/S3 stall can move the
# hang to whichever call is not yet bounded (a 4-deploy whack-a-mole: #116 bounded the
# probe, #117 bounded rung-B Bedrock, and an intermittent Transfer-manager hang remained).
# The wall is the CORRECTNESS guarantee that ends the game: the handler runs the entire
# generate ladder inside a ThreadPoolExecutor and WAITS only GENERATE_WALL_TIMEOUT_S. If
# the wait expires, the handler thread — which holds no stalled resource — composites rung
# D (_brand_floor, zero-I/O, bundled asset, cannot fail) IN THE HANDLER THREAD, does a
# bounded S3 put, and returns 200 real pixels tagged rung=D fallthrough_reason=wall-timeout.
# Wall = correctness (a floor is ALWAYS reachable); budget = quality (the common case still
# abandons to rung C with generated pixels). The app reaches this handler through
# API Gateway (29s integration cap), so 26s leaves ~3s for the post-wall
# composite + put + return leg. A cold-model first pass still misses — that is
# what the frontend's automatic warm retry is for — but a warm pass (caption
# overlapped with scene, restyle-cache hot) lands in ~22s.
GENERATE_WALL_TIMEOUT_S = float(os.getenv("GENERATE_WALL_TIMEOUT_S", "26"))

# Inner bound for the cross-region us-west-2 art-director invoke. Sits well inside the ~22s
# outer wall so a cold/scale-to-zero model (art_director's 4x28s cold-start retry) can never
# consume the hero-composition budget. On timeout: fall back to the original prompt (voice-off),
# NOT the rung-D wall floor.
ART_DIRECTOR_TIMEOUT_S = float(os.getenv("KODIAK_ARTDIRECTOR_TIMEOUT_S", "6"))

# ART-DIRECTOR VOICE STEP (dark by default): when KODIAK_ARTDIRECTOR_ENABLED is truthy,
# the incoming brief/prompt is run through the Kodiak brand-voice art-director model
# (src/creative_automation/art_director.py) and the returned on-brand line replaces the
# headline that feeds hero composition. Default is OFF — a single cheap env check then the
# headline flows through byte-for-byte as today, with zero import-time cost and no Bedrock
# call. The art_director import is deferred into the helper so the default-off path never
# pays for Strands import either. See _maybe_art_direct for the never-block/never-raise
# fallback contract (mirrors the never-503 ladder: any failure or None falls back to the
# original headline). The art-director inference is isolated in us-west-2 by art_director.py
# itself — this module does NOT pass AWS_REGION to it.
ART_DIRECTOR_ENABLED = os.getenv("KODIAK_ARTDIRECTOR_ENABLED", "false").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)
# Voices the art-director model was trained on; a request "voice" outside this set falls
# back to the default rather than being passed through here.
_ART_DIRECTOR_KNOWN_VOICES = ("adventurous", "nourishing")
_ART_DIRECTOR_DEFAULT_VOICE = "adventurous"


# Voice runs CONCURRENTLY with hero composition (wall repair): _kick_voice is
# called FIRST in _handle_preview/_handle_full, the returned future overlaps the
# whole pixel ladder, and _apply_art_upgrade_future collects it AFTER pixels
# exist with a short grace wait. PROVEN IN PROD: the old serial order (pixels,
# then up to 6s of voice against the same 22s wall) meant a cold art-director
# model plus any restyle render guaranteed wall-timeout fallthrough — finished
# pixels discarded for a headline nicety. Concurrent voice costs ~0s of wall:
# the inner 6s bound resolves long before pixels land, so the collect is instant
# and a slow voice can never gate the render. Same leak-and-drain contract as
# the outer wall: an abandoned voice worker writes nothing shared.
_VOICE_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1)
_VOICE_COLLECT_TIMEOUT_S = 2.0
# Reserve (ms) kept for response assembly + upload after the voice collect.
_VOICE_COLLECT_RESERVE_MS = 1500.0


def _voice_collect_timeout_s(remaining_ms=None) -> float:
    """Wall-aware voice wait (cost-incident follow-up).

    The old fixed 2s gave up on an opted-in headline even with 20s of wall
    left; renders take the minutes, the headline may take its seconds. Wait
    up to the wall remainder minus the response reserve — fallback stays for
    hard errors and true timeouts only. No clock (full path) keeps the old
    fixed bound.
    """
    if remaining_ms is None:
        return _VOICE_COLLECT_TIMEOUT_S
    try:
        return max(0.1, (remaining_ms() - _VOICE_COLLECT_RESERVE_MS) / 1000.0)
    except Exception:  # noqa: BLE001 — broken clock degrades to the fixed bound
        return _VOICE_COLLECT_TIMEOUT_S


def _voice_requested(data: dict[str, Any]) -> bool:
    """Per-request voice opt-in (cost incident 2026-09-23).

    Default requests never touch a voice model, whatever the env flags say —
    the caller must pass "art_director": true explicitly. Env flags remain as
    the kill-switch (both must allow AND the request must ask).
    """
    return str((data or {}).get("art_director") or "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _kick_voice(data: dict[str, Any], prompt: str):
    """Submit the art-director voice upgrade; returns a future, never raises.

    Call FIRST in the walled handlers so voice overlaps hero composition.
    _maybe_art_direct only reads data (never mutates), so sharing the dict with
    the pixel path is safe; a shallow copy is passed anyway as belt-and-braces.
    When the voice flag is dark this resolves near-instantly to the prompt.
    Without an explicit per-request opt-in no future is kicked at all.
    """
    if not _voice_requested(data):
        return None
    try:
        return _VOICE_POOL.submit(_maybe_art_direct, dict(data), prompt)
    except Exception as e:  # noqa: BLE001 — voice must never break the kick
        print(f"[generate_lambda] voice kick failed: {e}", file=sys.stderr)
        return None


def _apply_art_upgrade_future(fut, data: dict[str, Any], prompt: str, provenance: Any, timeout_s: float = _VOICE_COLLECT_TIMEOUT_S) -> None:
    """Collect a kicked voice future after pixels exist. Never raises.

    Records provenance["art_headline"] when the voice produced a real line;
    records nothing on timeout, worker fault, or fallback (voice-off). Pixels
    always ship regardless.
    """
    try:
        if fut is None or not isinstance(provenance, dict):
            return
        try:
            line = fut.result(timeout=timeout_s)
        except Exception:  # noqa: BLE001 — slow/faulty voice degrades to voice-off; pixels ship
            return  # slow voice -> voice-off, pixels ship
        if line and line.strip() and line.strip() != prompt.strip():
            # Military quarantine — warm agricultural frontier only
            low = line.lower()
            if any(b in low for b in ("listen up", "recruit", "muster", "enlist")):
                print(f"[generate_lambda] art_headline military filtered ({line[:60]!r})", file=sys.stderr)
                return
            provenance["art_headline"] = line.strip()
    except Exception as e:  # noqa: BLE001 — completed pixels always ship
        print(f"[generate_lambda] art upgrade skipped: {e}", file=sys.stderr)


def _handle_warm(data: dict[str, Any]) -> dict[str, Any]:
    """Pre-warm ping target for the EventBridge Scheduler rule (Unit 1).

    Runs one trivial art-director ask to keep the imported model warm. Dark-aware:
    with the voice flag off there is nothing to warm. Always 200, never raises.
    """
    try:
        if not ART_DIRECTOR_ENABLED:
            return _response(200, {"ok": True, "warmed": False, "reason": "voice-off"})
        from . import art_director  # deferred import — voice-off path never loads Strands

        out = art_director.art_direct(
            "morning fuel", _ART_DIRECTOR_DEFAULT_VOICE,
        )
        live = (out or {}).get("source") == "bedrock:kodiak-artdirector"
        return _response(200, {"ok": True, "warmed": live, "source": (out or {}).get("source")})
    except Exception as e:  # noqa: BLE001 — warm pings never fail loudly
        print(f"[generate_lambda] warm ping skipped: {e}", file=sys.stderr)
        return _response(200, {"ok": True, "warmed": False, "reason": "error"})


def _maybe_art_direct(data: dict[str, Any], prompt: str) -> str:
    """Optionally refine the headline via the Kodiak art-director voice; else pass through.

    Dark-by-default no-op: when ART_DIRECTOR_ENABLED is False this is a single boolean check
    that returns `prompt` unchanged — no import, no Bedrock call, no behavior change. When
    enabled, run the incoming brief/prompt as the art-direction "ask" through the trained
    brand voice and return the on-brand line as the headline for hero composition.

    Never blocks generation and never raises (mirrors the never-503 contract): any exception,
    or a None/empty return, falls back to the original `prompt` and logs the fallback to
    stderr. The art_director module owns its isolated us-west-2 region — AWS_REGION is NOT
    passed in. Called INSIDE the walled work (_handle_preview/_handle_full run in the
    ThreadPoolExecutor), so a slow inference is still bounded by GENERATE_WALL_TIMEOUT_S.
    """
    if not ART_DIRECTOR_ENABLED:
        return prompt
    if not _voice_requested(data):
        return prompt

    voice = (data.get("voice") or "").strip().lower()
    if voice not in _ART_DIRECTOR_KNOWN_VOICES:
        voice = _ART_DIRECTOR_DEFAULT_VOICE

    try:
        from . import art_director  # deferred import — default-off path never loads Strands

        # Bound the cross-region us-west-2 invoke on its own inner timeout, well inside the
        # outer wall, so art_director's cold-start retry loop can never burn the hero
        # budget. On timeout the abandoned worker keeps sleeping through its remaining
        # retries and then exits — it writes nothing shared, so it leaks and drains harmlessly
        # (same leak-and-drain contract the outer wall already documents for its own worker).
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        fut = executor.submit(art_director.art_direct, prompt, voice)  # region handled internally
        try:
            result = fut.result(timeout=ART_DIRECTOR_TIMEOUT_S)
        except concurrent.futures.TimeoutError:
            print(
                f"[generate_lambda] art-director inner timeout at {ART_DIRECTOR_TIMEOUT_S}s — "
                "falling back to original headline (voice-off)",
                file=sys.stderr,
            )
            return prompt
        finally:
            executor.shutdown(wait=False)
        line = (result or {}).get("text") if isinstance(result, dict) else None
        if line and line.strip():
            return line.strip()
        print(
            "[generate_lambda] art-director returned no usable text — "
            "falling back to original headline",
            file=sys.stderr,
        )
    except Exception as e:  # noqa: BLE001 — never block generation; fall back to headline
        print(f"[generate_lambda] art-director fallback: {e}", file=sys.stderr)
    return prompt

ASSET_STORE_S3_BUCKET = os.getenv("ASSET_STORE_S3_BUCKET", "").strip() or os.getenv("DAM_S3_BUCKET", "").strip() or "chasko-creative-dam-946179428633-us-east-1"
CORS_HEADERS = {
    "Content-Type": "application/json; charset=utf-8",
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


def _request_path(event: dict[str, Any]) -> str:
    """Resolve the request path from an HTTP API v2 event (v2 shape, then rawPath, then local dict).

    The deployed API Gateway is HTTP API v2 with a single $default catch-all routing every
    path to this one Lambda, so the handler is path-blind unless it reads the path itself.
    v2 carries it at requestContext.http.path; rawPath is the v2 mirror; a bare "path" key
    covers a local invoke dict. Default "/generate" so an event with no path info falls
    through to the existing generate ladder (back-compat with direct/local invokes).
    """
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    return http.get("path") or event.get("rawPath") or event.get("path") or "/generate"


def _handle_platform_copy(event: dict[str, Any]) -> dict[str, Any]:
    """POST /campaigns/platform-copy, outside the image-generation wall."""
    rc = event.get("requestContext") or {}
    http = rc.get("http") or {}
    method = (http.get("method") or event.get("httpMethod") or "POST").upper()
    if method != "POST":
        return _response(
            405,
            {
                "ok": False,
                "error": f"method {method} not allowed on /campaigns/platform-copy",
            },
        )
    try:
        data = _parse_body(event)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return _response(400, {"ok": False, "error": f"malformed request body: {e}"})
    try:
        return _response(200, build_platform_copy_response(data))
    except PlatformCopyValidationError as e:
        return _response(400, {"ok": False, "error": str(e)})


def _handle_localize(event: dict[str, Any]) -> dict[str, Any]:
    """POST /localize — one localized string with honest provenance via localize_service.

    localize_service.localize returns {text, source, provider, lang, ...}; the frontend
    localizeText() reads j.text (falls back to j.translated/j.translation), so the "text"
    key is passed straight through. A backend failure degrades to an HONEST EN-source
    response (never a fabricated translation) rather than crashing the Lambda.
    """
    try:
        data = _parse_body(event)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return _response(400, {"ok": False, "error": f"malformed request body: {e}"})
    if not isinstance(data, dict):
        return _response(400, {"ok": False, "error": "malformed request body: expected a JSON object"})

    text = (data.get("text") or "").strip()
    market = (data.get("market") or "").strip() or "us"
    target_lang = (data.get("target_lang") or data.get("lang") or "").strip()
    if not text:
        return _response(400, {"ok": False, "error": "text is required"})
    if not target_lang:
        return _response(400, {"ok": False, "error": "target_lang is required"})

    try:
        from .localize_service import localize as _localize

        result = _localize(text, market, target_lang)  # {text, source, provider, lang, ...}
        return _response(200, result)
    except Exception as e:  # noqa: BLE001 — never sink; honest EN-source degrade
        print(f"[generate_lambda] /localize failed: {e}", file=sys.stderr)
        return _response(
            200,
            {
                "text": text,
                "source": "error-fallback",
                "provider": "none",
                "lang": target_lang,
                "error": str(e),
            },
        )


def _handle_assets_library(event: dict[str, Any]) -> dict[str, Any]:
    """GET /assets/library — read-only asset store picker listing via the shared asset_browser module.

    category + limit come from the query string (this is a GET). asset_browser.list_library
    is the ONE implementation shared with api.py's route, so there is no drift. Never
    raises — S3-disabled and per-category failures degrade inside list_library.
    """
    qs = event.get("queryStringParameters") or {}
    category = (qs.get("category") or "").strip() or None
    raw_limit = (qs.get("limit") or "").strip()
    try:
        limit = int(raw_limit) if raw_limit else 60
    except (TypeError, ValueError):
        limit = 60
    try:
        return _response(200, asset_browser.list_library(category, limit))
    except Exception as e:  # noqa: BLE001 — a path handler error is a clean JSON, never a crash
        print(f"[generate_lambda] /assets/library failed: {e}", file=sys.stderr)
        return _response(500, {"ok": False, "error": str(e)})


# Asset-pack zip (#204): only keys under this prefix may enter a pack, so a pack
# request can never exfiltrate arbitrary asset store objects — it packs renders, nothing else.
_PACK_MEMBER_PREFIX = "brands/kodiak/renders/"
_PACK_KEY_PREFIX = "brands/kodiak/packs/"
_PACK_MAX_FILES = 8
_PACK_MAX_EXTRA_BYTES = 65536
_PACK_EXTRA_NAME_RE = re.compile(r"^[A-Za-z0-9-]+\.(txt|csv)$")
_ISO_SEG_RE = re.compile(r"[^A-Za-z0-9-]+")


def _iso_segment(value: Any, default: str) -> str:
    """One ISO filename segment: caller value sanitized S3-safe, else the default."""
    text = str(value or "").strip() or default
    return _ISO_SEG_RE.sub("-", text).strip("-") or default


def _pack_zip_name(product: str, region: str, locality: str, channel: str, date: str) -> str:
    """ISO pack name. The RATIO slot of the file contract carries 'multi' — one zip
    holds the whole multi-ratio set, and each member file names its own ratio."""
    return (
        f"KODIAK-CAKES-{product}-{region}-{locality}-{channel}-multi-{date}-v01.zip"
    )


def _pack_member_name(
    product: str, region: str, locality: str, channel: str, ratio: str, date: str
) -> str:
    """Per-member ISO name — matches the frontend single-download convention."""
    return (
        f"KODIAK-CAKES-{product}-{region}-{locality}-{channel}-{ratio}-{date}-v01.png"
    )


def _handle_pack(event: dict[str, Any]) -> dict[str, Any]:
    """POST /assets/pack — zip already-rendered asset store PNGs into an ISO-named pack.

    Body: {files: [{s3_uri, ratio?}...], extras?: [{name, text}...],
    product?, region?, locality?, channel?}.
    Packs ONLY keys under brands/kodiak/renders/ in the asset store bucket (400 otherwise),
    PUTs the zip to brands/kodiak/packs/<iso-name>.zip, and returns a presigned GET
    URL with Content-Disposition: attachment so the browser saves the ISO name.
    extras (#242: campaign copy sidecars) are small inline text members (.txt/.csv
    only, name-validated, 64KB cap each) — no second endpoint for words.
    S3-only (no Bedrock): runs inline, no wall executor needed. A missing member
    is a 400 naming the key — a partial zip would lie about the multi-ratio pack.
    """
    try:
        data = _parse_body(event)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        return _response(400, {"ok": False, "error": f"malformed request body: {e}"})
    if not isinstance(data, dict):
        return _response(400, {"ok": False, "error": "malformed request body: expected a JSON object"})
    files = data.get("files")
    if not isinstance(files, list) or not files:
        return _response(400, {"ok": False, "error": "files is required: [{s3_uri, ratio?}...]"})
    if len(files) > _PACK_MAX_FILES:
        return _response(400, {"ok": False, "error": f"at most {_PACK_MAX_FILES} files per pack"})
    product = _iso_segment(data.get("product"), "savory-waffles")
    region = _iso_segment(data.get("region"), "US-UT")
    locality = _iso_segment(data.get("locality"), "park-city-84098")
    channel = _iso_segment(data.get("channel"), "retailers")
    day = datetime.now(UTC).strftime("%Y%m%d")
    prefix = f"s3://{ASSET_STORE_S3_BUCKET}/"
    members: list[tuple[str, str]] = []
    for i, entry in enumerate(files):
        uri = (entry.get("s3_uri") or "") if isinstance(entry, dict) else ""
        ratio = _iso_segment((entry.get("ratio") if isinstance(entry, dict) else ""), f"{i + 1}")
        if not uri.startswith(prefix):
            return _response(400, {"ok": False, "error": f"files[{i}]: s3_uri must be in this asset store bucket"})
        key = uri[len(prefix):]
        if not key.startswith(_PACK_MEMBER_PREFIX) or not key.endswith(".png"):
            return _response(400, {"ok": False, "error": f"files[{i}]: only PNG renders under {_PACK_MEMBER_PREFIX} can be packed"})
        members.append((key, _pack_member_name(product, region, locality, channel, ratio, day)))
    extras: list[tuple[str, bytes]] = []
    for i, extra in enumerate(data.get("extras") or []):
        if not isinstance(extra, dict):
            return _response(400, {"ok": False, "error": f"extras[{i}]: must be {{name, text}}"})
        name = str(extra.get("name") or "")
        text = extra.get("text")
        if not _PACK_EXTRA_NAME_RE.match(name):
            return _response(400, {"ok": False, "error": f"extras[{i}]: name must match [A-Za-z0-9-].txt|.csv"})
        blob = str(text or "").encode("utf-8")
        if len(blob) > _PACK_MAX_EXTRA_BYTES:
            return _response(400, {"ok": False, "error": f"extras[{i}]: text over 64KB cap"})
        extras.append((f"{product}-{name}", blob))
    if len(members) + len(extras) > _PACK_MAX_FILES:
        return _response(400, {"ok": False, "error": f"at most {_PACK_MAX_FILES} files per pack"})
    import io as _io
    s3 = _s3_client()
    buf = _io.BytesIO()
    try:
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for key, name in members:
                try:
                    body = s3.get_object(Bucket=ASSET_STORE_S3_BUCKET, Key=key)["Body"].read()
                except Exception as e:  # noqa: BLE001 — name the missing key, pack nothing partial
                    return _response(400, {"ok": False, "error": f"member not found: {key} ({e})"})
                zf.writestr(name, body)
            for name, blob in extras:
                zf.writestr(name, blob)
    except Exception as e:  # noqa: BLE001 — zip build fault surfaces, never a crash
        print(f"[generate_lambda] /assets/pack zip failed: {e}", file=sys.stderr)
        return _response(500, {"ok": False, "error": "pack build failed"})
    zip_name = _pack_zip_name(product, region, locality, channel, day)
    zip_key = f"{_PACK_KEY_PREFIX}{zip_name}"
    try:
        s3.put_object(Bucket=ASSET_STORE_S3_BUCKET, Key=zip_key, Body=buf.getvalue(), ContentType="application/zip")
    except Exception as e:  # noqa: BLE001 — persist fault surfaces, never a crash
        print(f"[generate_lambda] /assets/pack put failed: {e}", file=sys.stderr)
        return _response(500, {"ok": False, "error": "pack upload failed"})
    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": ASSET_STORE_S3_BUCKET,
            "Key": zip_key,
            "ResponseContentDisposition": f'attachment; filename="{zip_name}"',
        },
        ExpiresIn=3600,
    )
    names = [name for _, name in members] + [name for name, _ in extras]
    print(f"[generate_lambda] /assets/pack ok: {zip_name} ({len(names)} files)", file=sys.stderr)
    return _response(200, {
        "ok": True,
        "zip_url": url,
        "zip_name": zip_name,
        "s3_uri": f"s3://{ASSET_STORE_S3_BUCKET}/{zip_key}",
        "files": names,
        "count": len(names),
    })


def _handle_library_assets(event: dict[str, Any]) -> dict[str, Any]:
    """POST /library/assets — real T2 asset ingest: store then best-effort embed + vector.

    Mirrors asset_api.add_asset_api's contract: filename/added_by/tags arrive as query params
    and the raw file bytes are the request body (octet-stream). API Gateway v2 base64-encodes
    binary bodies, so decode when isBase64Encoded is set.

    Flow (store is the ONLY hard requirement; embedding is best-effort with an embed_pending
    fallback so a slow/failed Nova call or an unconfigured index never loses an upload):
      1. validate filename + non-empty body (400 on either miss)
      2. AssetLibrary(bucket=ASSET_STORE_S3_BUCKET); if not s3_enabled -> honest 200 s3-disabled
      3. add_asset — DEDUP-FIRST: an identical sha256 returns the EXISTING ref, no re-put
      4. dedup-cost-control: skip the Nova embed when a vector already exists for the
         asset_id (vector_exists GetVectors probe). A dedup hit reuses the original
         asset_id, so its vector is already keyed and re-embedding would waste a Nova invoke.
      5. for a NEW asset: write bytes to /tmp, embed (image for raster, else text of
         filename+tags), put_vector keyed by asset_id. On embed/put failure -> embed_pending.
      6. wrap embed+put in a ThreadPoolExecutor bounded by EMBED_WALL_TIMEOUT_S so a slow
         Nova call cannot hang the request — on timeout the asset stands as embed_pending.

    COST NOTE: each NEW (non-dedup) asset spends exactly one Nova multimodal embed invoke.
    The dedup-first store + the vector_exists GetVectors skip bound this so a re-uploaded
    duplicate costs zero Nova invokes.
    """
    method = (event.get("requestContext", {}).get("http", {}).get("method")
              or event.get("httpMethod") or "POST").upper()
    if method != "POST":
        return _response(405, {"ok": False, "error": f"method {method} not allowed on /library/assets"})

    qs = event.get("queryStringParameters") or {}
    filename = (qs.get("filename") or "").strip()
    added_by = (qs.get("added_by") or "").strip() or "anonymous"
    raw_tags = (qs.get("tags") or "").strip()
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else None
    if not filename:
        return _response(400, {"ok": False, "error": "filename query param is required"})

    raw_body = event.get("body")
    if raw_body is None or raw_body == "":
        return _response(400, {"ok": False, "error": "empty request body: expected file bytes"})
    try:
        if event.get("isBase64Encoded"):
            data = base64.b64decode(raw_body)
        elif isinstance(raw_body, bytes):
            data = raw_body
        else:
            # a str body that was NOT flagged base64 is raw text bytes (e.g. local invoke)
            data = raw_body.encode("utf-8")
    except Exception as e:  # noqa: BLE001 — a bad body is a 400, never a 500
        return _response(400, {"ok": False, "error": f"could not decode request body: {e}"})
    if not data:
        return _response(400, {"ok": False, "error": "empty request body: expected file bytes"})

    from .asset_library import AssetKind, AssetLibrary, UnsupportedAssetKind

    library = AssetLibrary(bucket=ASSET_STORE_S3_BUCKET)
    if not library.s3_enabled:
        return _response(
            200,
            {"ok": False, "status": "s3-disabled", "note": "asset library storage not configured"},
        )

    try:
        ref = library.add_asset(data=data, filename=filename, added_by=added_by, tags=tags)
    except UnsupportedAssetKind as e:
        return _response(415, {"ok": False, "error": str(e)})
    except Exception as e:  # noqa: BLE001 — a store failure is honest, never a crash
        print(f"[generate_lambda] /library/assets store failed: {e}", file=sys.stderr)
        return _response(200, {"ok": False, "status": "store-failed", "error": str(e)})

    kind_val = ref.kind.value if isinstance(ref.kind, AssetKind) else str(ref.kind)

    # Dedup-cost-control: if a vector already exists for this asset_id, this was a dedup
    # hit (or a prior embed) — skip the Nova invoke entirely.
    tmp_path: Path | None = None
    embed_status = "embed_pending"
    embed_model: str | None = None
    dedup = False
    try:
        from .embeddings import embed_image, embed_text, put_vector, vector_exists

        if vector_exists(ref.asset_id):
            dedup = True
            embed_status = "embedded"  # vector already present; nothing to spend
        else:
            def _embed_and_store() -> tuple[bool, str | None]:
                nonlocal tmp_path
                meta = {
                    "asset_id": ref.asset_id,
                    "filename": ref.filename,
                    "kind": kind_val,
                    "sha256": ref.sha256,
                    "content_type": ref.content_type,
                    "source": ref.source,
                    "s3_uri": ref.s3_uri,
                }
                if kind_val == AssetKind.RASTER.value:
                    tmp_path = Path(f"/tmp/{uuid4().hex}-{ref.filename}")
                    tmp_path.write_bytes(data)
                    vec, model = embed_image(tmp_path, text_hint=ref.filename)
                else:
                    hint = ref.filename + ((" " + " ".join(tags)) if tags else "")
                    vec, model = embed_text(hint)
                meta["model"] = model
                ok = put_vector(vec, key=ref.asset_id, metadata=meta)
                return ok, model

            wall = float(os.getenv("EMBED_WALL_TIMEOUT_S", "20"))
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            fut = executor.submit(_embed_and_store)
            try:
                ok, embed_model = fut.result(timeout=wall)
                embed_status = "embedded" if ok else "embed_pending"
            except concurrent.futures.TimeoutError:
                print(
                    f"[generate_lambda] /library/assets embed wall fired at {wall}s — "
                    f"asset {ref.asset_id} stands as embed_pending",
                    file=sys.stderr,
                )
                embed_status = "embed_pending"
            finally:
                executor.shutdown(wait=False)
    except Exception as e:  # noqa: BLE001 — embed is best-effort; asset already stored
        print(f"[generate_lambda] /library/assets embed fallback: {e}", file=sys.stderr)
        embed_status = "embed_pending"
    finally:
        if tmp_path is not None:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError as e:  # best-effort temp cleanup
                print(f"[generate_lambda] tmp cleanup skipped: {e}", file=sys.stderr)

    return _response(
        201,
        {
            "ok": True,
            "asset_id": ref.asset_id,
            "s3_uri": ref.s3_uri,
            "sha256": ref.sha256,
            "kind": kind_val,
            "dedup": dedup,
            "embed_status": embed_status,
            "embed_model": embed_model,
        },
    )


def _translate_text_live(text: str, target_lang: str) -> str | None:
    """One Amazon Translate call for a non-English headline. None on any failure.

    Network-gated behind text_rewriter._has_creds() by the caller — this helper
    never runs offline (no IMDS stalls in CI). The Lambda execution role carries
    the translate:TranslateText grant (infra/generate-endpoint.yaml); without it
    this call fails closed to None and the offline chain below takes over.
    """
    try:
        from boto3 import client as _boto_client  # local import: boto3 optional offline
    except ImportError:
        return None
    try:
        client = _boto_client("translate", region_name=os.getenv("TRANSLATE_REGION", os.getenv("AWS_REGION", "us-east-1")))
        resp = client.translate_text(Text=text, SourceLanguageCode="en", TargetLanguageCode=target_lang)
        out = resp.get("TranslatedText", "").strip()
        return out or None
    except Exception as e:  # noqa: BLE001 — documented fallback, never sinks generate
        print(f"[generate_lambda] Amazon Translate fallback ({target_lang}): {e}", file=sys.stderr)
        return None


def _offline_translation(headline: str, lang: str) -> tuple[str | None, str]:
    """Offline translation for a headline: exact offline-dictionary hit, else None.

    Returns (text, provider). The dictionary is localize.OFFLINE (real translated
    strings for the campaign headlines); anything else returns None so the caller
    falls through to the tagged suffix — a non-English row is always preferred
    over a verbatim-English row (issue #201).
    """
    try:
        from .localize import OFFLINE as _OFFLINE
    except ImportError:
        return None, "none"
    entry = _OFFLINE.get(lang, {})
    if headline in entry:
        return entry[headline], "mock:dictionary"
    return None, "mock:dictionary"


def _build_localizations(headline: str, market: str | None) -> tuple[list[dict], list[str]]:
    """Localize a headline into a market's top-3 languages (English + market top-2).

    Server-side localization: resolve the target languages for `market` (EN/ES/PT default
    when unknown), then run the headline through the rewrite/translate seam
    (text_rewriter.rewrite_all -> Nova Micro rewrite -> dialect swap -> Amazon Translate,
    per the README chain). A non-English row NEVER carries the verbatim English string
    (issue #201): when the rewrite seam has no live backend, each non-English language
    falls through Amazon Translate (live, IAM-granted) -> the offline dictionary (real
    translated strings for the campaign headlines) -> a language-tagged suffix variant.
    Offline/no-creds is a documented path, never a crash.

    Returns (localizations, languages):
      localizations: [{lang_code, translate_code, headline, source}, ...] in target order
      languages:     [lang_code, ...] for the provenance object

    source is "translated" only when a live backend or the offline dictionary produced
    the text; anything else reads as "rewrite-fallback" so the UI labels it honestly.
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
    by_lang = {r["lang_code"]: r for r in results}

    try:
        from .translate import translate_with_provenance as _with_provenance
    except ImportError:
        _with_provenance = None  # type: ignore

    online = text_rewriter._has_creds()
    for code in langs:
        res = by_lang.get(code, {})
        text = res.get("text", headline)
        live = res.get("source") == "bedrock:nova-micro"
        if code == "en" or live:
            # English source, or a live Nova rewrite — nothing further to do.
            source = "translated" if live else "original"
            localizations.append(
                {
                    "lang_code": code,
                    "translate_code": translate_codes.get(code, code),
                    "headline": text,
                    "source": source,
                }
            )
            continue
        # Non-English and no live rewrite: walk the MT chain so the row never
        # reads as verbatim English.
        translated: str | None = None
        if online:
            translated = _translate_text_live(headline, translate_codes.get(code, code))
        if translated:
            localizations.append(
                {
                    "lang_code": code,
                    "translate_code": translate_codes.get(code, code),
                    "headline": translated,
                    "source": "translated",
                }
            )
            continue
        offline_text, _provider = _offline_translation(headline, code)
        if offline_text:
            localizations.append(
                {
                    "lang_code": code,
                    "translate_code": translate_codes.get(code, code),
                    "headline": offline_text,
                    "source": "translated",
                }
            )
            continue
        if _with_provenance is not None:
            tagged, _prov, _proven = _with_provenance(headline, code, market or "us")
        else:
            tagged = f"{headline} [{code}]"
        localizations.append(
            {
                "lang_code": code,
                "translate_code": translate_codes.get(code, code),
                "headline": tagged,
                "source": "rewrite-fallback",
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


def _request_layers(data: dict[str, Any]) -> dict:
    """Render-contract layers for this request (#199/#200): {} by default (clean).

    A missing/non-dict "layers" body key normalizes to {} — default Create returns a
    clean standalone image + copy sidecars, with every layer OFF. normalize_layers
    drops unknown keys so a stray client field can never switch on a composite.
    """
    layers = normalize_layers(data.get("layers") if isinstance(data, dict) else None)
    return layers if layers is not None else {}


def _reserve_cobadge(data: dict, theme: str | None, themes: object, layers: dict) -> dict:
    """Keep It Wild renders reserve the Vital Ground co-badge slot.

    The wild-grizzly-bears theme (single or inside a combo) auto-sets the
    conservation_badge layer so the mark composites like a retailer badge —
    or records unresolved and ships clean when the raster is absent. An
    explicit client layers value is never unset, only defaulted in.
    """
    names = {str(theme or "").strip()}
    if isinstance(themes, (list, tuple)):
        names.update(str(t or "").strip() for t in themes)
    if KEEP_IT_WILD_THEME in names and isinstance(layers, dict):
        layers.setdefault(LAYER_COBADGE, True)
    return layers


def _response_sidecar(
    provenance: dict[str, Any] | None,
    prompt: str,
    platform_copy: dict | None,
    theme: str | None,
    product: str,
    localizations: list[dict] | None = None,
    languages: list[str] | None = None,
    recipe_fields: dict | None = None,
    retailer: str | None = None,
) -> dict:
    """Copy sidecars for the response (#199, Atlanta H). Never raises."""
    try:
        return build_copy_sidecar(
            provenance, prompt, platform_copy, theme, product,
            localizations=localizations, languages=languages,
            recipe_fields=recipe_fields, retailer=retailer,
        )
    except Exception as e:  # noqa: BLE001 — sidecars are additive, never fatal
        print(f"[generate_lambda] copy sidecar build failed: {e}", file=sys.stderr)
        return {"txt": "", "csv": ""}


# Retailer proof (Atlanta E/H): theme slug -> retailer display name. An explicit
# request retailer always wins; Atlanta-like markets default to Publix below.
_THEME_RETAILER = {
    "localized-publix": "Publix",
    "localized-costco": "Costco",
    "localized-target": "Target",
    "publix": "Publix",
    "costco": "Costco",
    "target": "Target",
    # overlay wiring: walmart composites the asset store mark; kroger/heb/whole-foods
    # are copy-only (no mark) but still ship the explicit retailer proof row.
    "walmart": "Walmart",
    "kroger": "Kroger",
    "heb": "HEB",
    "whole-foods": "Whole Foods",
}

# Markets whose preview defaults to Publix proof when the request names no
# retailer/theme (US-SE-ATL: Atlanta 30301, retailer "Publix, Target" with Publix
# first per the market record; Spanish + Korean per market-languages.json).
_PUBLIX_DEFAULT_MARKETS = {"US-SE-ATL"}


def _season_pairing(season: object) -> tuple[dict | None, dict]:
    """(record, meta) for a request season; (None, {}) when unpaired.

    One chain: the season table resolves the record (static default as last
    resort); meta names the season key, the record id/name, and whether the
    pairing came from the season table or the static default. Dropdown-style
    requests (season key, month name, holiday — gh #313) resolve through the
    same pairing table the recipe card uses. Guarded: an absent season, an
    unknown value, or any error means no pairing — never raises, never
    fabricates."""
    try:
        from . import season_pairing as _seasons
        from .recipe_card import _season_fallback_recipe
        season_name = season if isinstance(season, str) and season.strip() else None
        if season_name is None:
            return None, {}
        rec = _season_fallback_recipe(season_name)
        if not isinstance(rec, dict):
            return None, {}
        pairing = _seasons.pairing_for_season(season_name)
        if pairing.get("source") == "season-table":
            label = _seasons.pairing_season_label(season_name)
        else:
            resolved = _seasons.resolve_season(season_name)
            pairing = _seasons.pairing_for_season(resolved.get("season"))
            label = resolved.get("season")
        meta = {
            "season": label,
            "recipe_id": rec.get("id"),
            "name": rec.get("name"),
            "source": pairing.get("source")
            if pairing.get("recipe_id") == rec.get("id")
            else "static-default",
            "reason": pairing.get("reason"),
        }
        return rec, meta
    except Exception:  # noqa: BLE001 — season never breaks the preview
        return None, {}


def _seasonal_recipe_default(season: object, product_name: str) -> dict | None:
    """Season-paired recipe default: the season table's record when the request
    names a season and the record fits the tease shape, else None (caller keeps
    the static default). Full catalog records carry 10 ingredients and long
    steps — those stay on the pairing display, never truncated into the tease.
    Never raises, never fabricates."""
    rec, _meta = _season_pairing(season)
    if rec is None:
        return None
    try:
        return _validate_recipe_fields(rec, product_name)
    except Exception:  # noqa: BLE001 — season never breaks the preview
        return None


def _preview_dish_name(data: dict[str, Any], product_name: str) -> str | None:
    """Campaign dish name for the image scene prompt (offline, never raises).

    Names the SAME dish the campaign display shows: an explicit request recipe
    first, then the season-table pairing name (prov["recipe"] — full catalog
    records never fit the tease shape, so the tease title alone would point at
    the static default while the display names the pairing), then the static
    default. Resolved BEFORE the pixel ladder (pure local lookup, ~0s wall)
    and threaded into generate_hero as dish=. None when nothing resolves; the
    scene prompt then reads as before.
    """
    def _dish_title(fields: object) -> str:
        # Validated tease fields carry "title"; raw catalog records carry "name".
        if not isinstance(fields, dict):
            return ""
        return str(fields.get("title") or fields.get("name") or "").strip()

    try:
        raw = data.get("recipe_fields")
        validated = _validate_recipe_fields(raw, product_name)
        if validated is not None:
            name = _dish_title(validated)
            if name:
                return name
        rec, meta = _season_pairing(data.get("season"))
        if rec is not None and isinstance(meta.get("name"), str) and meta["name"].strip():
            return meta["name"].strip()
        fallback = _recipe_card_defaults(product_name)
        if isinstance(fallback, dict):
            return _dish_title(fallback) or None
    except Exception:  # noqa: BLE001 — dish never breaks the preview
        return None
    return None


def _preview_campaign_data(
    data: dict[str, Any], prompt: str, provenance: dict[str, Any] | None
) -> dict[str, Any]:
    """Deterministic campaign messaging for a response — zero model calls.

    Builds (platform_copy, localizations, languages, recipe_fields, retailer)
    from the campaign brief with the offline template + offline-dictionary chain
    only: no Nova/Translate calls, no spend, microseconds against the wall, so
    the copy can ship IN the preview instead of being deferred to the pack.
    Live platform copy + live translations stay frontend-owned (rendered live
    via the /localize + rewrite seams when creds exist).

    Retailer: explicit data.retailer > retailer theme > Publix default for
    Atlanta-like markets. Recipe: explicit data.recipe_fields (validated, never
    fabricated) else the deterministic per-product defaults — the preview tease.
    """
    product = data.get("product", "power-cakes")
    product_name = str(product).replace("-", " ").title()
    theme = data.get("theme")
    market = data.get("market") or data.get("region") or "us"
    # Identity matters: an empty-but-real dict still receives the pairing, so
    # `or {}` (which silently drops writes on falsy input) is wrong here.
    prov = provenance if isinstance(provenance, dict) else {}
    base = clean_brand_copy(
        str(prov.get("copy_headline") or prov.get("headline") or prompt or "")[:80]
    ) or clean_brand_copy(str(prompt or ""))
    # Brief grounding: the image caption knows the seed, not the idea — lead
    # the base with the user's free-text subject so platform posts and
    # localizations carry what was asked for ("sea otters"), not just the
    # market template.
    base = clean_brand_copy(_blend_idea_base(base, prompt))

    platform_copy = fallback_platform_copy(base, product_name, market)

    targets = resolve_target_languages(market)
    languages = [t["lang_code"] for t in targets]
    localizations: list[dict] = []
    for t in targets:
        code = t["lang_code"]
        if code == "en":
            localizations.append({
                "lang_code": code,
                "translate_code": t.get("translate_code", code),
                "headline": base,
                "source": "original",
            })
            continue
        offline_text, _provider = _offline_translation(base, code)
        if offline_text:
            localizations.append({
                "lang_code": code,
                "translate_code": t.get("translate_code", code),
                "headline": clean_brand_copy(offline_text),
                "source": "translated",
            })
        else:
            # No invented translations: a language-tagged suffix keeps the row
            # honestly non-English until a live backend translates it.
            localizations.append({
                "lang_code": code,
                "translate_code": t.get("translate_code", code),
                "headline": clean_brand_copy(f"{base} [{code}]"),
                "source": "rewrite-fallback",
            })

    raw_recipe = data.get("recipe_fields")
    recipe_fields = _validate_recipe_fields(raw_recipe, product_name)
    if recipe_fields is None:
        recipe_fields = _seasonal_recipe_default(data.get("season"), product_name)
        if recipe_fields is None:
            recipe_fields = _recipe_card_defaults(product_name)
    # Season pairing display: a season that resolves through the season table
    # pairs the campaign with the real catalog record (name + traceability on
    # provenance). Static-default landings stay quiet — they add nothing over
    # the tease title. The tease shape above stays intact: full records are
    # never truncated into it.
    rec, meta = _season_pairing(data.get("season"))
    if (
        rec is not None
        and meta.get("source") == "season-table"
        and isinstance(meta.get("name"), str)
        and meta["name"].strip()
    ):
        prov["recipe"] = meta["name"].strip()
        prov["recipe_pairing"] = meta

    retailer = data.get("retailer")
    if not isinstance(retailer, str) or not retailer.strip():
        retailer = _THEME_RETAILER.get(str(theme or ""))
    if not retailer and market in _PUBLIX_DEFAULT_MARKETS:
        retailer = "Publix"

    return {
        "platform_copy": platform_copy,
        "localizations": localizations,
        "languages": languages,
        "recipe_fields": recipe_fields,
        "retailer": retailer,
    }


def _s3_client():
    """Build the S3 client with SigV4 + explicit region (ASIA session-token creds need it).

    BOUNDED RETURN-LEG (#118, PART 3): the final-image put in _upload_render is the ONE
    call that lives AFTER the outer wall fires (the post-wall rung-D path still has to
    persist its pixels), so the client carries a fail-fast Config — connect 1s, read a few
    seconds, max_attempts 1 — so the tail put itself cannot become the new stall the wall
    just eliminated upstream. A default (unbounded, 3-retry) client would reintroduce the
    whack-a-mole one leg later. The presign call on the same client is a local signing op
    (no network), so the bound only ever bites the put/get network legs.
    """
    # SigV4 + explicit region: session-token (ASIA) creds require SigV4 presigns; the
    # boto3 default can emit SigV2 query params that S3 rejects with 403.
    region = os.getenv("AWS_REGION", "us-east-1")
    put_connect = int(os.getenv("GENERATE_PUT_CONNECT_TIMEOUT_S", "1"))
    put_read = int(os.getenv("GENERATE_PUT_READ_TIMEOUT_S", "4"))
    return boto3.client(
        "s3",
        region_name=region,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "virtual"},
            connect_timeout=put_connect,
            read_timeout=put_read,
            retries={"max_attempts": 1, "mode": "standard"},
        ),
    )


_PLATFORM_ALIASES = {"insta": "instagram"}
_TAG_VALUE_RE = re.compile(r"^[a-z0-9-]{1,32}$")


def _normalize_platform_tags(platforms: Any) -> list[str]:
    """Canonicalize a platform list for the x-amz-meta-platforms object tag.

    Lowercases, canonicalizes the "insta" alias, keeps only S3-safe metadata
    characters, and dedupes preserving order. Unknown-but-safe slugs pass
    through (forward-compat); anything outside the safe pattern is dropped so
    a junk caller value can never corrupt object metadata.
    """
    out: list[str] = []
    for p in platforms or []:
        slug = _PLATFORM_ALIASES.get(str(p).strip().lower(), str(p).strip().lower())
        if slug and _TAG_VALUE_RE.match(slug) and slug not in out:
            out.append(slug)
    return out


def _upload_render(
    s3: Any, r: dict[str, Any], download_name: str, platforms: Any = None
) -> dict[str, Any]:
    """Upload one render's PNG bytes and return its {ratio, image_url, s3_uri, w, h} entry.

    platforms: optional per-platform slugs, written as x-amz-meta-platforms so the
    asset store browser can filter renders by platform. The Metadata arg is omitted
    entirely when the tag list is empty, so untagged objects (and existing
    offline stubs) are byte-identical to before.
    """
    ratio = r["ratio"]
    key = f"brands/kodiak/renders/{uuid4().hex}.png"
    tags = _normalize_platform_tags(platforms)
    put_kwargs: dict[str, Any] = {
        "Bucket": ASSET_STORE_S3_BUCKET,
        "Key": key,
        "Body": r["path"].read_bytes(),
        "ContentType": "image/png",
    }
    if tags:
        put_kwargs["Metadata"] = {"platforms": ",".join(tags)}
    s3.put_object(**put_kwargs)
    s3_uri = f"s3://{ASSET_STORE_S3_BUCKET}/{key}"
    # per-ratio download name so each saved file names its ratio.
    disposition_name = download_name.replace(".png", f"-{ratio.upper()}.png")
    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": ASSET_STORE_S3_BUCKET,
            "Key": key,
            "ResponseContentDisposition": f'attachment; filename="{disposition_name}"',
        },
        ExpiresIn=3600,
    )
    return {"ratio": ratio, "image_url": url, "s3_uri": s3_uri, "w": r["w"], "h": r["h"], "platforms": tags}


# Ratios eligible for a standalone extend call. Only blog stays a
# server-side pad (OG crops are conventionally crops); 4x5 joins the
# tall/wide tiles as a real outpaint — every portrait canvas earns its
# own composition instead of a center crop.
_EXTEND_RATIOS = ("4x5", "9x16", "16x9")


def _handle_extend(data: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Compose ONE tall/wide tile from an already-rendered 1x1 hero.

    Request fields: hero_s3_uri (the 1x1 entry from a preview response),
    ratio ("4x5", "9x16" or "16x9"), subject (extend prompt text, optional —
    falls back to the request prompt). One Stability outpaint extend, well
    inside the wall on its own. Any failure degrades to a Pillow pad of the
    same hero — the response always carries a tile, never an error beyond
    a 400 for a malformed request (ratio unknown, hero unreadable).
    """
    ratio = str(data.get("ratio") or "").strip()
    if ratio not in _EXTEND_RATIOS:
        return {"ok": False, "error": f"unknown extend ratio: {ratio!r} (want 4x5, 9x16 or 16x9)"}
    hero_uri = str(data.get("hero_s3_uri") or "")
    prefix = f"s3://{ASSET_STORE_S3_BUCKET}/"
    if not hero_uri.startswith(prefix):
        return {"ok": False, "error": "hero_s3_uri must be a render from this asset store bucket"}
    key = hero_uri[len(prefix):]
    if not key or ".." in key:
        return {"ok": False, "error": "unreadable hero_s3_uri"}
    out_dir = Path(f"/tmp/{uuid4().hex}")
    out_dir.mkdir(parents=True, exist_ok=True)
    hero_path = out_dir / "hero-1x1.png"
    try:
        body = _s3_client().get_object(Bucket=ASSET_STORE_S3_BUCKET, Key=key)["Body"].read()
    except Exception as e:  # noqa: BLE001 — missing key, creds, network
        return {"ok": False, "error": f"hero download failed: {type(e).__name__}"}
    try:
        hero_path.write_bytes(body)
        with Image.open(hero_path) as im:
            im.verify()
        with Image.open(hero_path) as im:
            im.load()
    except Exception:
        return {"ok": False, "error": "hero is not a readable image"}
    target_w, target_h = RATIO_DIMS[ratio]
    out_path = out_dir / f"hero-{ratio}.png"
    subject = str(data.get("subject") or "").strip() or prompt
    engine = "pillow-outpaint-fallback"
    try:
        extended = _stability_outpaint(hero_path, target_w, target_h, subject, out_path)
    except Exception as e:  # noqa: BLE001 — timeout/throttle degrades to pad
        print(f"[generate] extend {ratio} outpaint failed, padding: {e}", file=sys.stderr)
        extended = None
    if extended is None or not out_path.exists():
        _pillow_outpaint_fallback(hero_path, target_w, target_h, out_path)
    else:
        engine = "stability-outpaint"
    with Image.open(out_path) as im:
        w, h = im.size
    entry = _upload_render(
        _s3_client(),
        {"ratio": ratio, "path": out_path, "w": w, "h": h},
        _download_filename(
            str(data.get("product") or "power-cakes"),
            str(data.get("region") or "us"),
            data.get("theme"),
        ),
    )
    entry["engine"] = engine
    entry["ok"] = True
    return entry


_RECIPE_ART_ZONES = ("raw_ingredient", "technique", "finished_plate")
_RECIPE_ART_WALL_S = 25.0
# Scenic text-to-image needs longer than a sketch zone: Core photographic
# renders typically land in 20-60s. 150s stays well inside the 300s Lambda
# timeout with room for upload; the frontend shows progress meanwhile.
_SCENIC_WALL_S = 150.0


def _recipe_catalog_name(recipe_id: str) -> str | None:
    """Recipe display name for a catalog id, or None when unknown."""
    try:
        from ._datapaths import data_path

        recs = json.loads(data_path("recipes", "kodiak-recipes.json").read_text())
    except Exception:
        return None
    want = str(recipe_id or "").strip().lower()
    if not want:
        return None
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        if str(rec.get("id") or "").strip().lower() == want:
            name = str(rec.get("name") or "").strip()
            return name or None
    for rec in recs:
        if not isinstance(rec, dict):
            continue
        if str(rec.get("name") or "").strip().lower() == want:
            return str(rec.get("name") or "").strip() or None
    return None


def _handle_recipe_art(data: dict[str, Any]) -> dict[str, Any]:
    """Serve or generate ONE recipe-card sketch zone.

    Request fields: recipe_id (catalog id), zone (raw_ingredient | technique
    | finished_plate). Seeded path first: the first art_slug_candidates hit
    in the asset store returns its permanent site URL with seeded True. Otherwise ONE
    generate_recipe_art run (deterministic seed from recipe_id + zone) behind
    a 25s wall, uploaded to the asset store recipe-art prefix — the next request for
    the same cell serves seeded. Any failure (unknown recipe/zone, wall
    timeout, gate reject, upload miss) returns ok False and the frontend
    keeps its placeholder: a missing drawing is never an error here.
    """
    from . import asset_store as _asset_store
    from . import recipe_art as _ra

    zone = str(data.get("zone") or "").strip()
    if zone not in _RECIPE_ART_ZONES:
        return {"ok": False, "error": f"unknown art zone: {zone!r}"}
    name = _recipe_catalog_name(data.get("recipe_id"))
    if name is None:
        return {"ok": False, "error": "unknown recipe_id"}
    for slug in _ra.art_slug_candidates(name):
        if _asset_store.recipe_art_exists(slug, zone):
            return {
                "ok": True,
                "url": _asset_store.recipe_art_site_url(slug, zone),
                "seeded": True,
                "zone": zone,
            }
    import zlib

    seed = zlib.crc32(f"{data.get('recipe_id')}|{zone}".encode()) % (2**31)
    out_dir = Path(f"/tmp/recipe-art-{uuid4().hex}")
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(_ra.generate_recipe_art, name, zone, seed=seed, out_dir=out_dir)
    try:
        try:
            local = fut.result(timeout=_RECIPE_ART_WALL_S)
        except Exception as e:  # noqa: BLE001 — timeout or worker fault
            print(f"[generate] recipe-art {zone} walled: {type(e).__name__}", file=sys.stderr)
            local = None
    finally:
        # Never block on a leaked worker — same rule as the outer wall.
        pool.shutdown(wait=False)
    if local is None:
        return {"ok": False, "error": "generation unavailable"}
    slug = _ra.art_slug_candidates(name)[0]
    url = _asset_store.upload_recipe_art(Path(str(local)), slug, zone)
    if not url:
        return {"ok": False, "error": "publish failed"}
    return {"ok": True, "url": url, "seeded": False, "zone": zone}


def _handle_scenic_bg(data: dict[str, Any]) -> dict[str, Any]:
    """Serve or generate ONE photographic scenic background for a brief idea.

    Request fields: prompt (the brief — idea distilled server-side), market,
    season. Seeded path first: the idea slug already published in the asset
    store returns its permanent site URL + asset key with seeded True.
    Otherwise ONE Stable Image Core text-to-image run behind _SCENIC_WALL_S,
    uploaded to the scenic-bg prefix — the next request for the same idea
    serves seeded. The frontend feeds the returned KEY back into /generate
    as seed_key, so the scene rides the existing staged-seed path: no
    composite machinery changes. Any failure returns ok False and the
    frontend keeps its fast preview: a missing scene is never an error here.
    """
    from . import asset_store as _asset_store
    from .generate import _brief_idea, _scenic_background, _scenic_scene_text

    prompt = str(data.get("prompt") or "")
    idea = _brief_idea(_safe_prompt_text(prompt) if prompt else "")
    if not idea:
        return {"ok": False, "error": "no idea in brief"}
    slug = _asset_store.scenic_slug(idea)
    if _asset_store.scenic_exists(slug):
        return {
            "ok": True,
            "url": _asset_store.scenic_site_url(slug),
            "key": _asset_store.scenic_key(slug),
            "seeded": True,
            "idea": idea,
        }
    scene = _scenic_scene_text(
        prompt,
        data.get("market"),
        data.get("season"),
        (data.get("dish") if isinstance(data.get("dish"), str) else None),
    )
    if not scene:
        return {"ok": False, "error": "no scene in brief"}
    import zlib

    seed = zlib.crc32(f"scenic|{slug}".encode()) % (2**31)
    out = Path(f"/tmp/scenic-bg-{uuid4().hex}") / "hero-1x1.png"
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    fut = pool.submit(_scenic_background, scene, out, seed)
    try:
        try:
            local = fut.result(timeout=_SCENIC_WALL_S)
        except Exception as e:  # noqa: BLE001 — timeout or worker fault
            print(f"[generate] scenic-bg walled: {type(e).__name__}", file=sys.stderr)
            local = None
    finally:
        # Never block on a leaked worker — same rule as the outer wall.
        pool.shutdown(wait=False)
    if local is None:
        return {"ok": False, "error": "generation unavailable"}
    url = _asset_store.upload_scenic(Path(str(local)), slug)
    if not url:
        return {"ok": False, "error": "publish failed"}
    return {
        "ok": True,
        "url": url,
        "key": _asset_store.scenic_key(slug),
        "seeded": False,
        "idea": idea,
        "scene": scene,
    }


def _cover_fit_tile(path: Path, ratio: str) -> None:
    """Cover-fit a finished tile to its RATIO_DIMS frame, in place.

    Diffusion returns vary (Stability may hand back a capped resolution, the
    1x1 restyle keeps the seed's dims) — the shipped file must match the ratio
    the response claims. A fit failure keeps the pixels (dims over nothing).
    """
    try:
        dims = RATIO_DIMS[ratio]
    except KeyError:
        return
    try:
        with Image.open(path) as im:
            src = im.convert("RGB")
            if src.size == (dims[0], dims[1]):
                return
            ImageOps.fit(src, (dims[0], dims[1]), method=Image.BICUBIC).save(path, "PNG")
    except Exception as e:  # noqa: BLE001 — pixels beat dims
        print(f"[generate] tile {ratio} canvas fit skipped: {e}", file=sys.stderr)


def _handle_preview(data: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Fast interactive path (default): ONE 1x1 control-structure hero, under 30s.

    Runs the single-ratio generate_hero (ratio=1x1, clean by default per the render
    contract — copy ships as sidecars, kraft texture still baked) then derives the
    other tiles server-side from their OWN diffusion composition at their own
    frame: rung B restyles the 1x1 AND every sibling ratio CONCURRENTLY (one
    batch ≈ one restyle of wall, via generate_hero native_siblings), so the
    five tiles are five discrete compositions, never one image derived four
    ways. A ratio the fan-out skipped (scenic-verbatim seed) or lost keeps the
    old path — 9x16/16x9 attempt ONE Stability outpaint extend each behind the
    preview budget gate (sprint-2 item 11), everything else the Pillow
    cover-fit — so the preview keeps its wall guarantee. FULL mode remains the
    complete multi-ratio image path (generate_hero_set: 1x1 + 4x5 + 9x16 + 16x9).
    Returns the SAME response shape the frontend expects (renders[] with the 1x1 entry,
    top-level image_url = the 1x1, source + provenance), so showRenderSet keeps working
    with a single-entry renders[].

    Campaign messaging (Atlanta D/E/H) ships IN the preview via the deterministic
    offline chain (zero model calls, zero spend): full per-platform copy
    (X/Facebook meat + hashtags), the market's top-3 localizations (Spanish +
    Korean for Atlanta US-SE-ATL), the recipe tease, and retailer proof (Publix
    for Atlanta-like markets). Live copy/i18n stay frontend-owned.
    """
    # Voice kicked FIRST so it overlaps the whole pixel ladder (~0s of wall —
    # see _VOICE_POOL contract above). Never serial after pixels.
    voice_fut = _kick_voice(data, prompt)
    # Request-epoch clock for the preview outpaint gates below: the 1x1 hero
    # spends most of the soft budget, so gates MUST measure from HERE (preview
    # entry), not after the hero — same lesson as generate_hero_set
    # (2026-09-08): a reset clock passes a doomed extend and the wall fires
    # during finalize/uploads.
    _preview_start = _preview_now()
    product = data.get("product", "power-cakes")
    theme = data.get("theme")
    # Multi-theme combo: optional "themes" list (or comma-separated string).
    # First known slug drives seed + scene; extras become overlay/copy lines.
    themes = data.get("themes")
    seed_key = data.get("seed_key")
    # Render contract (#199/#200): default {} = clean standalone image, every layer
    # OFF. Only an explicit overlay_text layer re-enables the baked message bar.
    layers = _request_layers(data)
    layers = _reserve_cobadge(data, theme, themes, layers)
    out_dir = Path(f"/tmp/{uuid4().hex}")
    hero_path = out_dir / "hero-1x1.png"
    hero_path.parent.mkdir(parents=True, exist_ok=True)

    # ONE control-structure hero at 1x1 (clean by default — copy ships as sidecars).
    # The 9x16/16x9 tiles below attempt ONE live outpaint extend each behind the
    # preview budget gate (item 11); pads stay the fallback, so preview mode keeps
    # its single-hero speed guarantee with or without a live extend.
    # The campaign dish resolves BEFORE pixels (offline lookup, ~0s wall) so the
    # scene prompt names the same dish the recipe tease names — no image/recipe
    # disconnect.
    dish = _preview_dish_name(data, product.replace("-", " ").title())
    _preview_season = data.get("season")
    _preview_season = str(_preview_season).strip() or None if isinstance(_preview_season, str) else None
    # Native fan-out destinations: rung B restyles the 1x1 AND every sibling
    # ratio CONCURRENTLY (one batch ≈ one restyle of wall), so the five tiles
    # are five discrete compositions. A missing sibling file below falls back
    # to the derive-from-1x1 path per ratio, honestly labelled.
    _sibling_paths = {
        _r: out_dir / f"sibling-{_r}.png" for _r in _PREVIEW_PAD_RATIOS
    }
    result_path, source, provenance = generate_hero(
        product_id=product,
        product_name=product.replace("-", " ").title(),
        brief_msg=prompt,
        region=data.get("region", "us"),
        audience=data.get("audience", "active families"),
        out_path=hero_path,
        dish=dish,
        ratio="1x1",
        theme=theme,
        brand_overlay=bool(layers.get("overlay_text")),
        paper_overlay=True,
        seed_key=seed_key,
        layers=layers,
        themes=themes,
        art_director=_voice_requested(data),
        market=(data.get("market") or data.get("region") or "us"),
        season=_preview_season,
        native_siblings={_r: str(_p) for _r, _p in _sibling_paths.items()},
    )

    with Image.open(result_path) as im:
        w, h = im.size
    render = {"ratio": "1x1", "path": result_path, "w": w, "h": h}

    # Five-tile parity: every other size gets its OWN diffusion composition at
    # its own frame via the native-ratio pass above. A ratio the native pass
    # skipped or lost falls back to deriving from the finished 1x1 —
    # 9x16/16x9 attempt a live Stability outpaint extend when the preview budget
    # gate passes (sprint-2 item 11); every other outcome — gate fail, rung off,
    # timeout, error, empty response — falls back to the Pillow cover-fit, same
    # as ratios the native pass never covers. Fallback tiles derive from the
    # FINALIZED 1x1; per-ratio marks re-seat via _finalize_render with
    # paper_overlay=False. A tile never fails the preview: any per-ratio error
    # keeps the 1x1 and is recorded, never raised.
    # The per-ratio gates below reuse the request-epoch _preview_start taken at
    # preview entry, so remaining covers one outpaint PLUS the reserve for
    # pads/overlays against the TRUE wall-clock remainder.
    def _preview_remaining_ms() -> float:
        return GENERATE_SOFT_BUDGET_MS - (_preview_now() - _preview_start) * 1000.0

    brand_overlay = bool(layers.get("overlay_text"))
    headline = provenance.get("headline") if isinstance(provenance, dict) else ""
    # Raw subject for the outpaint extend prompt (_stability_outpaint wraps it in
    # the frozen style sandwich). Reuses the hero's scene prompt so NO extra
    # Bedrock call burns the wall; falls back to the brief when absent.
    _preview_outpaint_subject = ""
    if isinstance(provenance, dict):
        _preview_outpaint_subject = str(provenance.get("scene_prompt") or "").strip()
    if not _preview_outpaint_subject:
        _preview_outpaint_subject = prompt
    if isinstance(provenance, dict):
        # Per-ratio outpaint books (measurement): gate-time remaining + extend
        # latency + degrade reasons, all JSON-serializable. A slow ratio degrades
        # to the pad — never blows the wall.
        provenance.setdefault("outpaint_latency_ms", {})
        provenance.setdefault("outpaint_degraded", {})
        provenance.setdefault("outpaint_remaining_ms", {})
    pad_renders: list[dict[str, Any]] = []
    pad_engines: dict[str, str] = {}
    # Native fan-out outcomes landed inside rung B (concurrent with the 1x1
    # restyle): a sibling file present on disk is that tile's own composition.
    # Anything missing falls through to the derive-from-1x1 path below.
    _native_claims = provenance.get("native_ratios") if isinstance(provenance, dict) else {}
    if not isinstance(_native_claims, dict):
        _native_claims = {}
    for pad_ratio in _PREVIEW_PAD_RATIOS:
        try:
            # DECISION: RATIO_DIMS lookup stays INSIDE the per-pad guard so an
            # unknown ratio degrades to pad_degraded[pad_ratio]="KeyError" and
            # the 1x1 preview still returns 200 — never a second dims table.
            pad_w, pad_h = RATIO_DIMS[pad_ratio]
            pad_path = out_dir / f"hero-{pad_ratio}.png"
            pad_engine = "pillow-outpaint-fallback"
            _native_hit = _sibling_paths.get(pad_ratio)
            if (
                _native_claims.get(pad_ratio) == "stability-restyle-native"
                and _native_hit is not None
                and _native_hit.exists()
            ):
                # own diffusion composition at this frame — no extend, no pad.
                _native_hit.replace(pad_path)
                pad_engine = "stability-restyle-native"
            elif pad_ratio in _PREVIEW_OUTPAINT_RATIOS:
                _remaining = _preview_remaining_ms()
                if isinstance(provenance, dict):
                    provenance["outpaint_remaining_ms"][pad_ratio] = round(_remaining, 1)
                if not _STABILITY_RUNG_ON:
                    if isinstance(provenance, dict):
                        provenance["outpaint_degraded"][pad_ratio] = "stability-rung-disabled"
                    _pillow_outpaint_fallback(result_path, pad_w, pad_h, pad_path)
                elif _remaining < _OUTPAINT_BUDGET_MS + _OUTPAINT_RESERVE_MS:
                    if isinstance(provenance, dict):
                        provenance["outpaint_degraded"][pad_ratio] = "budget-exhausted"
                    _pillow_outpaint_fallback(result_path, pad_w, pad_h, pad_path)
                else:
                    _t0 = _preview_now()
                    print(f"[generate] stage outpaint {pad_ratio} start (remaining {_remaining:.0f}ms)", file=sys.stderr)
                    try:
                        extended = _stability_outpaint(
                            result_path, pad_w, pad_h,
                            _preview_outpaint_subject, pad_path,
                        )
                    except (ReadTimeoutError, ConnectTimeoutError):
                        extended = None
                        if isinstance(provenance, dict):
                            provenance["outpaint_degraded"][pad_ratio] = "bedrock-timeout"
                    except Exception as e:  # noqa: BLE001 — throttle/sabotage degrades
                        extended = None
                        if isinstance(provenance, dict):
                            provenance["outpaint_degraded"][pad_ratio] = (
                                f"outpaint-error: {type(e).__name__}"
                            )
                    finally:
                        if isinstance(provenance, dict):
                            provenance["outpaint_latency_ms"][pad_ratio] = round(
                                (_preview_now() - _t0) * 1000.0, 1
                            )
                    if extended is not None and pad_path.exists():
                        pad_engine = "stability-outpaint"
                    else:
                        if isinstance(provenance, dict):
                            provenance["outpaint_degraded"].setdefault(
                                pad_ratio, "outpaint-unavailable"
                            )
                        _pillow_outpaint_fallback(result_path, pad_w, pad_h, pad_path)
            else:
                _pillow_outpaint_fallback(result_path, pad_w, pad_h, pad_path)
            if brand_overlay and headline:
                try:
                    _apply_brand_overlay(pad_path, headline, pad_ratio, pad_path)
                except Exception as e:  # noqa: BLE001 — never lose the tile over the bar
                    print(f"[generate] preview brand overlay on {pad_ratio} failed: {e}",
                          file=sys.stderr)
            _finalize_render(pad_path, False, provenance if isinstance(provenance, dict) else {}, layers)
            _cover_fit_tile(pad_path, pad_ratio)
            with Image.open(pad_path) as im:
                pw, ph = im.size
            pad_renders.append({"ratio": pad_ratio, "path": pad_path, "w": pw, "h": ph})
            pad_engines[pad_ratio] = pad_engine
        except Exception as e:  # noqa: BLE001 — a lost pad degrades to fewer tiles
            print(f"[generate] preview pad {pad_ratio} failed, shipping without it: {e}",
                  file=sys.stderr)
            if isinstance(provenance, dict):
                fallthrough = provenance.setdefault("pad_degraded", {})
                if isinstance(fallthrough, dict):
                    fallthrough[pad_ratio] = type(e).__name__

    s3 = _s3_client()
    eff_theme = provenance.get("theme", theme) if isinstance(provenance, dict) else theme
    download_name = _download_filename(product, data.get("region", "us"), eff_theme)
    entry = _upload_render(s3, render, download_name)
    entries = [entry]
    for pad in pad_renders:
        try:
            entries.append(_upload_render(s3, pad, download_name))
        except Exception as e:  # noqa: BLE001 — a lost upload degrades to fewer tiles
            print(f"[generate] preview upload {pad['ratio']} failed, shipping without it: {e}",
                  file=sys.stderr)
            # DECISION: a failed upload evicts the pad from pad_engines so
            # provenance["ratios"] names exactly the shipped renders[] tiles.
            pad_engines.pop(pad["ratio"], None)
            if isinstance(provenance, dict):
                fallthrough = provenance.setdefault("pad_degraded", {})
                if isinstance(fallthrough, dict):
                    fallthrough[pad["ratio"]] = f"upload-{type(e).__name__}"

    if isinstance(provenance, dict):
        # the preview ships all five tiles; per-ratio engines say which tiles are
        # own native compositions vs live outpaints vs pillow pads. FULL mode
        # remains the complete composed-set path for the pack.
        provenance["ratios"] = {"1x1": "primary", **pad_engines}
        provenance["mode"] = PREVIEW_MODE
        provenance.pop("deferred", None)
    # Collect the voice kicked at handler entry (overlapped pixels, ~0s wall);
    # recorded as provenance + sidecar, never swaps the brief. The wait is
    # wall-aware: an opted-in headline may take its seconds while wall remains.
    _apply_art_upgrade_future(
        voice_fut, data, prompt, provenance,
        timeout_s=_voice_collect_timeout_s(_preview_remaining_ms),
    )

    # Campaign messaging IN the preview (Atlanta D/E/H): deterministic offline
    # chain — zero model calls, so it cannot blow the wall. Runs after the art
    # upgrade so a recorded art_headline lands in the sidecar too.
    campaign = _preview_campaign_data(data, prompt, provenance)
    if isinstance(provenance, dict):
        provenance["languages"] = campaign["languages"]
        provenance["retailer"] = campaign["retailer"]
        recipe = campaign["recipe_fields"] or {}
        # A season pairing already named the campaign recipe inside the
        # campaign builder — the tease title never overwrites it.
        if recipe.get("title") and "recipe_pairing" not in provenance:
            provenance["recipe"] = recipe.get("title")
        provenance["platforms"] = sorted(campaign["platform_copy"].keys())
        provenance["copy_owner"] = "backend-preview-fallback"

    return {
        "ok": True,
        "image_url": entry["image_url"],
        "s3_uri": entry["s3_uri"],
        "source": source,
        "prompt": prompt,
        "theme": theme,
        "themes": themes,
        "mode": PREVIEW_MODE,
        "renders": entries,
        "provenance": provenance,
        "localizations": campaign["localizations"],
        "platform_copy": campaign["platform_copy"],
        "layers": layers,
        "recipe_fields": campaign["recipe_fields"],
        "retailer": campaign["retailer"],
        "copy_sidecar": _response_sidecar(
            provenance, prompt, campaign["platform_copy"], theme, product,
            localizations=campaign["localizations"],
            languages=campaign["languages"],
            recipe_fields=campaign["recipe_fields"],
            retailer=campaign["retailer"],
        ),
    }


def _handle_full(data: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Complete async-pack path: 3-size set + localization + per-platform copy.

    generate_hero_set delivers the four delivery ratios (1x1, 4x5, 9x16, 16x9):
    photographic base (packshot composite when the box resolves, else one
    control-structure restyle) with talls/wides as Pillow cover-pads. Localization
    and platform copy are frontend-owned (live seams), not computed here — the
    ~8-10s of Nova Micro fan-out could not fit the 22s wall. Runs ~10s (packshot
    base) to ~21s (restyle base).
    """
    # Voice kicked FIRST so it overlaps the whole pixel ladder (~0s of wall —
    # see _VOICE_POOL contract above). Never serial after pixels.
    voice_fut = _kick_voice(data, prompt)
    product = data.get("product", "power-cakes")
    theme = data.get("theme")
    themes = data.get("themes")
    seed_key = data.get("seed_key")
    # Render contract (#199/#200): default {} = clean standalone set, every layer OFF.
    layers = _request_layers(data)
    layers = _reserve_cobadge(data, theme, themes, layers)
    out_dir = Path(f"/tmp/{uuid4().hex}")
    # "prompt" is the campaign brief/vibe now, not a generation seed. generate_hero_set
    # composes over a real product asset via Nova Pro vision / Stability, delivering all
    # three delivery ratios (1x1, 4x5, 2x3) from one call. When "theme" is present it
    # drives the IMAGE (theme wins over the product default); product is still passed
    # for iso-naming / fallback.
    dish = _preview_dish_name(data, product.replace("-", " ").title())
    _set_season = data.get("season")
    _set_season = str(_set_season).strip() or None if isinstance(_set_season, str) else None
    renders, source, provenance = generate_hero_set(
        product_id=product,
        product_name=product.replace("-", " ").title(),
        brief_msg=prompt,
        region=data.get("region", "us"),
        audience=data.get("audience", "active families"),
        out_dir=out_dir,
        theme=theme,
        brand_overlay=bool(layers.get("overlay_text")),
        seed_key=seed_key,
        layers=layers,
        themes=themes,
        market=(data.get("market") or data.get("region") or "us"),
        season=_set_season,
        dish=dish,
        art_director=_voice_requested(data),
    )

    s3 = _s3_client()
    eff_theme = provenance.get("theme", theme) if isinstance(provenance, dict) else theme
    download_name = _download_filename(product, data.get("region", "us"), eff_theme)

    # The requested platform set doubles as the publish tag: every render is
    # stamped x-amz-meta-platforms at upload so the asset store browser can filter by
    # platform. Client may pass "platforms": [...] to scope the set; default is
    # all seven sanctioned platforms.
    req_platforms = data.get("platforms")
    if not isinstance(req_platforms, list) or not req_platforms:
        req_platforms = list(PLATFORMS)

    # Upload each ratio and build the renders[] response array. The 1x1 url is also
    # mirrored to the top-level image_url for the current frontend (back-compat).
    response_renders: list[dict[str, Any]] = [
        _upload_render(s3, r, download_name, req_platforms) for r in renders
    ]
    # back-compat: top-level image_url + s3_uri point at the 1x1 primary render.
    primary = next((rr for rr in response_renders if rr["ratio"] == "1x1"), response_renders[0])
    primary_url = primary["image_url"]

    # Server-side campaign messaging (Atlanta H): the deterministic offline chain
    # (zero model calls) ships full platform copy + top-3 localizations + recipe
    # tease + retailer proof in the pack response and sidecars. Live Nova rewrites
    # server-side would cost ~8-10s against the immovable 22s wall — the measured
    # reason full-mode sets hit brand-floor — so live copy + live translations stay
    # frontend-owned (rendered live via the /localize + rewrite seams).
    if isinstance(provenance, dict):
        provenance["mode"] = FULL_MODE
    # Collect the voice kicked at handler entry (overlapped pixels, ~0s wall);
    # recorded as provenance + sidecar, never swaps the brief.
    _apply_art_upgrade_future(voice_fut, data, prompt, provenance)

    campaign = _preview_campaign_data(data, prompt, provenance)
    # The requested platform set doubles as the publish tag (stamped above); the
    # deterministic copy covers the full publish set so the sidecar is complete.
    platform_copy = campaign["platform_copy"]
    localizations = campaign["localizations"]
    if isinstance(provenance, dict):
        provenance["languages"] = campaign["languages"]
        provenance["retailer"] = campaign["retailer"]
        recipe = campaign["recipe_fields"] or {}
        # A season pairing already named the campaign recipe inside the
        # campaign builder — the tease title never overwrites it.
        if recipe.get("title") and "recipe_pairing" not in provenance:
            provenance["recipe"] = recipe.get("title")
        provenance["platforms"] = sorted(platform_copy.keys())
        provenance["copy_owner"] = "backend-pack-fallback"

    return {
        "ok": True,
        "image_url": primary_url,
        "s3_uri": primary["s3_uri"],
        "source": source,
        "prompt": prompt,
        "theme": theme,
        "themes": themes,
        "mode": FULL_MODE,
        "renders": response_renders,
        "provenance": provenance,
        "localizations": localizations,
        "platform_copy": platform_copy,
        "layers": layers,
        "recipe_fields": campaign["recipe_fields"],
        "retailer": campaign["retailer"],
        "copy_sidecar": _response_sidecar(
            provenance, prompt, platform_copy, theme, product,
            localizations=localizations,
            languages=campaign["languages"],
            recipe_fields=campaign["recipe_fields"],
            retailer=campaign["retailer"],
        ),
    }


def _post_wall_brand_floor(data: dict[str, Any], prompt: str) -> dict[str, Any]:
    """Last-resort rung-D response built IN THE HANDLER THREAD after the wall fires.

    Called only when the ThreadPoolExecutor wait for the generate ladder exceeds
    GENERATE_WALL_TIMEOUT_S. The abandoned worker thread keeps running the stalled call
    and leaks until the container freezes/thaws — that is SAFE here because:
      - the leaked path writes to its OWN per-invocation out_dir (uuid4), and this floor
        writes to a DIFFERENT per-invocation path (a fresh uuid4 out_dir), so there is NO
        shared mutable buffer or fixed /tmp filename the leaked thread could be mid-write on
      - asset_store._s3_download now uses get_object+read (no Transfer-manager thread pool), so the
        leak is a single bounded socket read, not a whole worker pool
    _brand_floor is genuinely zero-I/O: it composites the package-bundled Kodiak logo
    (src/creative_automation/brand_assets/) in Pillow — no Bedrock, no asset store, no network — so
    it is ALWAYS reachable after the wall and cannot fail. The only network op on this path
    is the bounded S3 put of the finished floor pixels (PART 3 timeout applies).
    """
    product = data.get("product", "power-cakes")
    theme = data.get("theme")
    layers = _request_layers(data)
    # DISTINCT per-invocation path — never the abandoned worker's out_dir.
    out_dir = Path(f"/tmp/{uuid4().hex}-wall")
    hero_path = out_dir / "hero-1x1.png"
    hero_path.parent.mkdir(parents=True, exist_ok=True)

    product_name = product.replace("-", " ").title()
    # rung D, in-memory, zero network — real Kodiak brand pixels, cannot fail.
    result_path = _brand_floor(product_name, "1x1", hero_path)

    with Image.open(result_path) as im:
        w, h = im.size
    render = {"ratio": "1x1", "path": result_path, "w": w, "h": h}

    s3 = _s3_client()  # bounded put client (PART 3) — the one call living past the wall
    download_name = _download_filename(product, data.get("region", "us"), theme)
    entry = _upload_render(s3, render, download_name)

    provenance = {
        "seed_source": None,
        "seed_selection": "none",
        "engine": "brand-floor",
        "rung": "D",
        "origin": "backend",
        "fallthrough_reason": "wall-timeout",
        "mode": PREVIEW_MODE,
        "incoming_prompt": prompt,
        "theme": theme,
        "ratios": {"1x1": "primary"},
        "deferred": ["4x5", "9x16", "16x9"],
    }

    # Wall floor still ships deterministic campaign messaging (offline chain —
    # pure local, cannot stall the return leg).
    campaign = _preview_campaign_data(data, prompt, provenance)
    provenance["languages"] = campaign["languages"]
    provenance["retailer"] = campaign["retailer"]
    provenance["platforms"] = sorted(campaign["platform_copy"].keys())
    provenance["copy_owner"] = "backend-wall-fallback"

    return {
        "ok": True,
        "image_url": entry["image_url"],
        "s3_uri": entry["s3_uri"],
        "source": "brand-floor:wall-timeout",
        "prompt": prompt,
        "theme": theme,
        "mode": PREVIEW_MODE,
        "renders": [entry],
        "provenance": provenance,
        "localizations": campaign["localizations"],
        "platform_copy": campaign["platform_copy"],
        "layers": layers,
        "recipe_fields": campaign["recipe_fields"],
        "retailer": campaign["retailer"],
        "copy_sidecar": _response_sidecar(
            provenance, prompt, campaign["platform_copy"], theme, product,
            localizations=campaign["localizations"],
            languages=campaign["languages"],
            recipe_fields=campaign["recipe_fields"],
            retailer=campaign["retailer"],
        ),
    }


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Compose a hero from real source assets driven by a brief, upload it, return a presigned URL.

    Two modes (request field "mode", default "preview"):
      - preview: ONE 1x1 control-structure hero, no outpaint, no localization — fast
        enough to return inside API Gateway's hard 30s window (the interactive default).
      - full:    the complete 4-size set (photographic base + pads, ~10-21s), for
        the download-pack builder. Localization + platform copy render live in
        the frontend, not in this response.
    """
    if _is_options(event):
        return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}
    # PATH DISPATCH (#$default catch-all): the deployed HTTP API v2 routes EVERY path to
    # this one Lambda, so specific paths must be branched here or they fall into the
    # generate ladder and get a hero image back instead of their real response. OPTIONS is
    # short-circuited above so preflight still 200s for every path. Everything unmatched
    # (/generate, /, anything else) falls through to the EXISTING generate ladder unchanged.
    _path = _request_path(event)
    _p = _path.rstrip("/") or "/"  # strip trailing slash for matching; keep root "/" as-is
    if _p == "/localize":
        return _handle_localize(event)
    if _p == "/campaigns/platform-copy":
        return _handle_platform_copy(event)
    if _p == "/assets/library":
        return _handle_assets_library(event)
    if _p == "/library/assets":
        return _handle_library_assets(event)  # T2 asset ingest — store + best-effort embed
    if _p == "/assets/pack":
        return _handle_pack(event)  # #204 ISO asset-pack zip — S3-only, no wall needed
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
    # Pre-warm ping (EventBridge Scheduler, Unit 1): never touches the ladder.
    # The Scheduler target input is the RAW payload {"warm": "art-director"} (no
    # Function-URL body wrapper), so match the raw event shape too — _parse_body
    # drops a body-less event without a "prompt" key to {}, which used to send
    # every 4-minute ping down the full hero ladder instead of the warm path.
    if data.get("warm") == "art-director" or event.get("warm") == "art-director":
        return _handle_warm(data if data.get("warm") == "art-director" else event)
    try:
        prompt = (data.get("prompt") or "").strip()
        if not prompt:
            prompt = "KODIAK - Nourishment for Today's Frontier. Keep It Wild."
        # Strip any real celebrity name out of the client-built prompt BEFORE it becomes
        # brief_msg — the raw name trips Stability's content filter otherwise.
        prompt = _safe_prompt_text(prompt)

        mode = (data.get("mode") or PREVIEW_MODE).strip().lower()
        if mode == "extend":
            # Standalone tall/wide extend of an already-rendered hero. One
            # outpaint call fits the wall alone — no worker thread needed.
            return _response(200, _handle_extend(data, prompt))
        if mode == "recipe-art":
            # One recipe-card sketch zone: seeded asset store url when published,
            # otherwise one walled generation that publishes itself.
            return _response(200, _handle_recipe_art(data))
        if mode == "scenic-bg":
            # One photographic scenic background for the brief's idea: seeded
            # asset store url + key when published, otherwise one walled
            # text-to-image generation that publishes itself. The frontend
            # feeds key back as seed_key so the scene rides staged-seed.
            return _response(200, _handle_scenic_bg(data))

        # OUTER WALL: run the entire generate ladder in a worker thread and WAIT only
        # GENERATE_WALL_TIMEOUT_S. The per-rung budget gates inside generate_hero handle
        # the common case (graceful drop to rung C with generated pixels); this wall is
        # the last-resort STRUCTURAL guarantee that no internal stall — whichever call it
        # moves to — can push the handler past the 30s API Gateway edge. On timeout the
        # handler thread (holding no stalled resource) composites the zero-I/O rung-D
        # brand floor and returns 200 real pixels. A well-formed POST NEVER 503s.
        work = _handle_full if mode == FULL_MODE else _handle_preview
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(work, data, prompt)
        try:
            payload = future.result(timeout=GENERATE_WALL_TIMEOUT_S)
        except concurrent.futures.TimeoutError:
            # Abandon the WAIT (the worker keeps running the stalled call and leaks —
            # safe: it writes to its own out_dir, get_object read is a single socket).
            # Build the floor in THIS thread and return real rung-D pixels.
            print(
                f"[generate_lambda] outer wall fired at {GENERATE_WALL_TIMEOUT_S}s — "
                "rung-D brand-floor fallthrough (wall-timeout)",
                file=sys.stderr,
            )
            payload = _post_wall_brand_floor(data, prompt)
        finally:
            # Do NOT block on the leaked worker — let it drain on its own; the container
            # freeze/thaw reclaims it. wait=False keeps the return leg off the stalled call.
            executor.shutdown(wait=False)
        return _response(200, payload)
    except Exception as e:  # noqa: BLE001 — a well-formed POST should never reach here
        # The ladder guarantees a real-pixel 200, so an exception here is an infrastructure
        # fault (e.g. S3 upload), NOT a generation failure. Surface as 500, never 503.
        return _response(500, {"ok": False, "error": str(e)})
