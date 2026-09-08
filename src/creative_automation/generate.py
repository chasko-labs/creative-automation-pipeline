"""Hero image generation — Bedrock Stability image-conditioning on real brand assets.

Precedence (see generate_hero): a real seed asset (theme photo, sku-mapped DAM photo,
or disk asset) restyled to the theme by Bedrock Stability control-structure so the
theme lands in the pixels (source bedrock:stability-control-structure); else the same
seed composed by Pillow under Nova Pro art-direction (source bedrock:nova-pro); else a
deterministic on-brand placeholder labelled bedrock:nova-pro-fallback. The word
mock/preview never reaches the UI. Nova Canvas is retired (Legacy) and is not a path.
"""
from __future__ import annotations

import base64
import concurrent.futures
import csv
import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

# Attempt boto3 import lazily — local-only mode still works without it
try:
    import boto3
    from botocore.config import Config as _BotoConfig
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
        ConnectTimeoutError,
        ReadTimeoutError,
    )
except ImportError:
    boto3 = None  # type: ignore
    _BotoConfig = None  # type: ignore

    # Offline/no-boto shims so the never-503 ladder's except-tuple is always a valid
    # exception set (catching these names must never itself raise a NameError).
    class BotoCoreError(Exception):  # type: ignore[no-redef]
        pass

    class ClientError(Exception):  # type: ignore[no-redef]
        pass

    class ReadTimeoutError(Exception):  # type: ignore[no-redef]
        pass

    class ConnectTimeoutError(Exception):  # type: ignore[no-redef]
        pass


# ---------------------------------------------------------------- never-fail ladder
# GOVERNING PRINCIPLE: a well-formed POST /generate returns 200 with REAL Kodiak pixels
# 100% of the time. The generate_hero ladder A->B->C->D falls through linearly and always
# ends at rung D (brand-floor), which does zero network I/O and cannot fail. Only a
# malformed request (validated in the handler, before the ladder) is a 4xx; 503 is
# structurally unreachable from a well-formed POST.
#
# TIME BUDGET: the Lambda timeout is 300s but API Gateway caps the interactive call at
# 30s, so the 24s internal soft budget (NOT context.get_remaining_time_in_millis) is the
# real authority. Each rung checks remaining_ms() against its worst-case cost BEFORE
# starting and skips a rung that will not fit, so the ladder always reserves time to
# reach a real-pixel floor. time.monotonic (never time.time) so a wall-clock step never
# corrupts the deadline.
GENERATE_SOFT_BUDGET_MS = int(os.getenv("GENERATE_SOFT_BUDGET_MS", "24000"))
# Rung B (Bedrock stability-restyle) worst-case cost estimate: the read timeout (12s)
# plus connect + decode + overlay headroom. B is attempted only if remaining_ms covers
# this AND the C reservation, so a slow Bedrock call can never starve the C recovery.
_B_BUDGET_MS = int(os.getenv("GENERATE_B_BUDGET_MS", "16000"))
# Held-back reservation so rung C (pillow-compose, ~1-2s) can ALWAYS run after B, even
# when B burns its full budget. C is the guaranteed-real workhorse below B.
_C_RESERVATION_MS = int(os.getenv("GENERATE_C_RESERVATION_MS", "3000"))
# HARD WALL for the pre-ladder S3 discovery phases (seed probe + packshot probe). Each
# unmapped-SKU probe fans out sequential S3 misses (~10s+ each) that run BEFORE any rung
# gate, so a slow probe alone could blow the 30s API Gateway cap even though B/C/D are
# gated. A probe is entered ONLY while remaining_ms() still leaves this probe's own
# worst-case cost PLUS the C reservation; once the wall is crossed the probe is abandoned
# (treated as no-seed / no-packshot) so the ladder still reaches rung C or D by ~24s.
_PROBE_BUDGET_MS = int(os.getenv("GENERATE_PROBE_BUDGET_MS", "5000"))
# Bedrock fail-fast: a dedicated bedrock-runtime client for the rung-B invoke_model only,
# built with an explicit botocore Config so the old "38s then 503" becomes "12s then fall
# to C". NO retries — a retry inside a 30s gateway cap is a budget killer.
BEDROCK_READ_TIMEOUT_S = int(os.getenv("BEDROCK_READ_TIMEOUT_S", "12"))
BEDROCK_CONNECT_TIMEOUT_S = int(os.getenv("BEDROCK_CONNECT_TIMEOUT_S", "3"))
# Nova Pro fail-fast: the two rung-B vision calls (caption + scene-prompt) build the SAME
# fail-fast bedrock-runtime client as the Stability invoke, but with a TIGHTER read
# timeout so caption + scene-prompt + stability all fit under the ~24s soft budget. The
# root-cause of the 33s silent gap was these two Converse calls on a bare client with NO
# Config — one hung unbounded past the 30s gateway cap. Capped here, a slow Nova Pro
# degrades gracefully (caption -> brief fallback, scene-prompt -> deterministic default).
BEDROCK_NOVA_READ_TIMEOUT_S = int(os.getenv("BEDROCK_NOVA_READ_TIMEOUT_S", "6"))
# Per-subcall rung-B budget reservations (ms): each Bedrock sub-call is entered ONLY while
# remaining_ms() still covers that call's worst-case cost PLUS the rung-C reservation, so
# no single sub-call can consume the budget rung C needs to return real pixels by ~24s.
_B_NOVA_SCENE_MS = int(os.getenv("GENERATE_B_NOVA_SCENE_MS", "7000"))
_B_STABILITY_MS = int(os.getenv("GENERATE_B_STABILITY_MS", "13000"))
# Grounded-director headline reservation (ms): embed-the-request + retrieve + trained
# voice-model invoke, bounded by _DIRECTOR_TIMEOUT_S inside. Entered only while the
# clock covers this PLUS the compose reservation, so the director can never starve
# a floor rung. Kill-switch env read per call (default ON — every failure degrades
# to stock Nova), so ops can flip it without a redeploy.
_DIRECTOR_BUDGET_MS = int(os.getenv("GENERATE_DIRECTOR_BUDGET_MS", "10000"))
_DIRECTOR_TIMEOUT_S = float(os.getenv("GENERATE_DIRECTOR_TIMEOUT_S", "8"))
_DIRECTOR_LIVE_SOURCE = "bedrock:kodiak-artdirector"
# Refusal guard: a live voice model can still decline (junk retrieved examples make
# refusal likely — PROVEN IN PROD 2026-09-08: hash-laden DAM titles as in-voice
# examples produced "I Can't Fulfill This Request" as the campaign headline). A
# refusal is a failed attempt, not a headline — fall back to stock Nova.
_REFUSAL_PHRASES = (
    "i can't",
    "i cannot",
    "i'm sorry",
    "i am sorry",
    "as an ai",
    "unable to",
    "can't fulfill",
    "can't help",
    "won't be able",
)
# Lines containing these never reach the render — model meta-preambles, not copy.
_PREAMBLE_PATTERNS = (
    "here are",
    "here is",
    "requested",
    "headline options",
    "options:",
    "explanation:",
)


def _director_enabled() -> bool:
    """Kill-switch for the grounded-director headline path. ON unless opted out."""
    return os.getenv("KODIAK_DIRECTOR_GROUNDED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )
# Restyled-background cache (DAM prefix): the rung-A bg restyle costs ~10s of Bedrock,
# which fits a preview but never a full set (base + pads + uploads must clear the same
# 22s wall). The cache is content-addressed on (seed bytes + prompt inputs): a preview
# warms it, the set base reuses the SAME pixels — no second Bedrock call, wall holds,
# preview and pack stay consistent. Best-effort everywhere: any S3 failure degrades to
# the uncached behavior (fresh restyle when budget allows, else raw seed).
_RESTYLE_CACHE_PREFIX = "brands/kodiak/renders/restyle-cache/"
_RESTYLE_CACHE_BUCKET = os.getenv("DAM_S3_BUCKET", "chasko-creative-dam-946179428633-us-east-1")
# NOTE: the prefix MUST stay under brands/kodiak/renders/ — the GenerateLambda role grants
# PutObject/GetObject only on renders/* and library/* (generate-stack.ts). A top-level
# restyle-cache/ prefix is denied and the cache silently never warms.


def _restyle_cache_key(seed_bytes: bytes, product_name: str, brief_msg: str,
                        region: str, audience: str, theme: str | None) -> str:
    h = hashlib.sha256()
    h.update(seed_bytes)
    for part in (product_name, brief_msg, region, audience, theme or ""):
        h.update(b"\x00")
        h.update(str(part).encode("utf-8", "replace"))
    return _RESTYLE_CACHE_PREFIX + h.hexdigest() + ".png"


def _restyle_cache_get(key: str, dest: Path) -> bool:
    """Fetch a cached restyle to dest. False on ANY failure (miss, creds, network)."""
    try:
        if boto3 is None:
            return False
        s3 = boto3.client("s3")
        dest.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(_RESTYLE_CACHE_BUCKET, key, str(dest))
        return dest.exists() and dest.stat().st_size > 0
    except Exception:
        return False


def _restyle_cache_put(key: str, src: Path) -> None:
    """Store a fresh restyle. Never raises — cache misses just cost a future restyle."""
    try:
        if boto3 is None:
            return
        s3 = boto3.client("s3")
        s3.put_object(Bucket=_RESTYLE_CACHE_BUCKET, Key=key,
                      Body=src.read_bytes(), ContentType="image/png")
    except Exception:
        pass


class _RungBBudgetSkip(Exception):
    """Internal sentinel: a per-subcall budget gate abandoned rung B for rung C.

    Not an error — carries no failure, only a control-flow signal so the two gates
    (scene-prompt, stability) share one clean fall-to-C path. fallthrough_reason is set
    to budget-exhausted at the raise site before this propagates.
    """


# Image engine: Bedrock Stability control-structure
# (us.stability.stable-image-control-structure-v1:0) — seed a real DAM photo and the
# theme lands in the pixels (composition preserved, style restyled). Nova Pro
# (amazon.nova-pro-v1:0, Converse) is the art-director: it writes the localized
# headline AND the control-structure prompt that drives the restyle. Amazon Nova
# Canvas is LEGACY/un-invokable — do not use. The Stability text-to-image generators
# (stable-image-core, sd3-5-large, stable-image-ultra) are NOT granted yet — only the
# seed-driven control-structure edit model is a path, and mode-3 always has a seed.
NOVA_TEXT_MODEL = os.getenv("BEDROCK_NOVA_MODEL", "amazon.nova-pro-v1:0")
# Stability control-structure is invoked via its INFERENCE-PROFILE id. The bare
# stability.* id raises ValidationException — always use the us.stability.* profile.
STABILITY_CONTROL_MODEL = os.getenv(
    "BEDROCK_STABILITY_MODEL", "us.stability.stable-image-control-structure-v1:0"
)
# How strongly the seed composition constrains the restyle (0..1). ~0.7 keeps the
# product recognizable while letting the theme drive color/lighting/scene.
STABILITY_CONTROL_STRENGTH = float(os.getenv("BEDROCK_CONTROL_STRENGTH", "0.7"))
# Style sandwich (character-consistency pattern): frozen style head + varying subject
# + frozen detail tail. Nova (or the brief fallback) supplies ONLY the subject; the
# frozen ends keep every restyle/outpaint on-brand no matter what the subject says.
STYLE_HEAD = os.getenv(
    "KODIAK_STYLE_HEAD",
    "Photorealistic Kodiak frontier lifestyle photography, natural light, high detail, on-brand earthy palette. Subject: ",
)
STYLE_TAIL = os.getenv(
    "KODIAK_STYLE_TAIL",
    ". No text, no letters, no signage, blank surfaces only.",
)
# Mascot lock (Unit 2 — character consistency on the restyle rails): a FROZEN
# descriptor block pinned into the style-sandwich SUBJECT slot so the same brand
# bear renders recognizably identical across scenes (cabin / market / campfire).
# Gated on KODIAK_MASCOT_LOCK (default OFF) so existing renders are byte-identical
# unless the lock is explicitly enabled; text overridable via KODIAK_MASCOT_DESCRIPTOR.
MASCOT_DESCRIPTOR_BLOCK = (
    "Same Kodiak brand bear mascot in every render: friendly medium-brown grizzly "
    "bear with rounded ears, cream muzzle, warm amber eyes, and thick frontier fur "
    "with consistent markings"
)


def _mascot_lock_on() -> bool:
    """True when the frozen mascot descriptor is pinned into the subject slot."""
    return os.getenv("KODIAK_MASCOT_LOCK", "").strip().lower() in (
        "1", "true", "yes", "on",
    )


def _mascot_block() -> str:
    """Frozen descriptor text (env override wins, same pattern as STYLE_HEAD/TAIL)."""
    return os.getenv("KODIAK_MASCOT_DESCRIPTOR", MASCOT_DESCRIPTOR_BLOCK).strip()
# Seed discipline: locked seed = consistency (same brief re-renders identically);
# swept seed = controlled variations (the variations button passes seed per call).
STABILITY_SEED = int(os.getenv("BEDROCK_STABILITY_SEED", "42"))


def _style_sandwich(subject: str) -> str:
    """Wrap a varying subject in the frozen style ends. Idempotent.

    With the mascot lock on, the frozen MASCOT descriptor block is pinned into the
    SUBJECT slot ahead of the varying scene text, so every restyle carries the same
    bear identity no matter what the scene says. Already-wrapped prompts are
    unwrapped-aware: the block is injected after STYLE_HEAD when missing.
    """
    subject = (subject or "").strip()
    if _mascot_lock_on():
        block = _mascot_block()
        if block and block not in subject:
            if subject.startswith(STYLE_HEAD):
                subject = STYLE_HEAD + block + " Scene: " + subject[len(STYLE_HEAD):]
            else:
                subject = f"{block} Scene: {subject}"
    if subject.startswith(STYLE_HEAD):
        return subject
    return f"{STYLE_HEAD}{subject}{STYLE_TAIL}"
# Stability outpaint is invoked via its INFERENCE-PROFILE id (bare stability.* raises
# ValidationException). Confirmed ACTIVE + AUTHORIZED + AVAILABLE in us-east-1. The
# taller ratios (4x5, 2x3) are DERIVED from the 1x1 control-structure hero via outpaint
# — one restyle call plus two extend calls, cheaper than three full restyles and keeps
# the subject consistent across sizes. Schema mirrors control-structure (Stability's
# {prompt, image, left/right/up/down, output_format} — NOT Nova's taskType).
STABILITY_OUTPAINT_MODEL = os.getenv(
    "BEDROCK_STABILITY_OUTPAINT_MODEL", "us.stability.stable-outpaint-v1:0"
)
# Stability seed constraint: total pixels 4096..9437184, each dim >= 64. A real
# 1024x1024 DAM photo sits well inside the range; a seed below the floor in either
# dim is upscaled to 1024x1024 before invoke to avoid a ValidationException.
_STABILITY_MIN_DIM = 64
_STABILITY_UPSCALE_TO = 1024
_STABILITY_MAX_DIM = int(os.getenv("BEDROCK_STABILITY_SEED_MAX_SIDE", "1280"))
# us-west-2 needs an inference profile for Nova Pro; us-east-1 invokes directly.
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

# Default brand hero: when a requested SKU has no asset of its own, we still owe the
# campaign a real, on-brand Kodiak composite — so we compose on the flagship product
# shot. The DAM ships real heroes at brands/kodiak/heroes/<product>/hero-real.png|hero.png
# for power-cakes, bear-bites, oatmeal-cup; power-cakes is the flagship fallback.
DEFAULT_HERO_PRODUCT = "power-cakes"
DEFAULT_HERO_NAME = "Power Cakes"
# Source label for the true last-resort placeholder (default brand hero unfetchable —
# S3 down / no creds, which should never happen in prod). Never the word "mock"/"preview".
FALLBACK_SOURCE = "bedrock:nova-pro-fallback"
# Source label for a real GenAI restyle via Bedrock Stability control-structure —
# the theme is conditioned into the pixels, not just composited by Pillow.
STABILITY_SOURCE = "bedrock:stability-control-structure"
# Source label for the packshot-first composite path: a real product BOX resolved for
# the SKU and was pasted VERBATIM over a background scene — NO generative step ever
# touched the product pixels, so it structurally cannot render as bread or candy. This
# mirrors campaign.py::_render_asset's dam:packshot-composite provenance so the live
# /generate endpoint reports the composite path the same way the batch pipeline does.
# See docs/architecture/compose-fix/compose-fix-spec.md precedence table (order a/b).
PACKSHOT_SOURCE = "dam:packshot-composite"

# ---- degradation-ladder engine labels + provenance rungs.
# The ladder's four rungs each emit a distinct provenance.engine + rung letter so the
# response says which rung produced the pixels. Rung A reuses PACKSHOT_SOURCE (the
# packshot-composite path already returns that). Rungs B/C/D use these:
#   B stability-restyle   -> STABILITY_SOURCE  (rung "B")
#   C pillow-compose      -> "bedrock:nova-pro" (rung "C", the guaranteed-real workhorse)
#   D brand-floor         -> BRAND_FLOOR_SOURCE (rung "D", zero-I/O floor, cannot fail)
BRAND_FLOOR_SOURCE = "brand-floor"
# The bundled-in-the-deployment-package Kodiak brand asset rung D composites. It ships
# INSIDE the module (packages=["src/creative_automation"]), so it lands in /var/task with
# the code — no S3, no external fetch, always present. When even this is somehow absent,
# rung D still composites the brand wordmark on a brand-color canvas (pure Pillow), so
# rung D is unconditionally real Kodiak pixels with zero network.
_BRAND_FLOOR_ASSET = Path(__file__).parent / "brand_assets" / "kodiak-primary-logo.png"

# Canvas sizes per ISO ratio (social-3ratio.json). The real lifestyle photo fills
# each frame as the cover background — no ellipse, no solid-color-only path.
_CANVAS = {
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
    # Delivery ratios (pinned v2 DoD): 4x5 portrait feed, 9x16 vertical, 16x9
    # landscape, all cover-fit from the photographic base in full mode.
    "4x5": (1080, 1350),
    "2x3": (1000, 1500),
}
# The four delivery ratios returned by generate_hero_set, in response order (pinned
# v2 DoD: 1:1 1080x1080, 4:5 1080x1350, 9:16 1080x1920, 16:9 1920x1080). 9x16 and
# 16x9 are composed Stability outpaint extends of the 1x1 hero when the 22s wall
# allows; 4x5 stays a Pillow cover-pad. Wall arithmetic: base + caption + uploads
# already spend 8-21s of the immovable 22s wall, so each outpaint is budget-gated
# per ratio — a slow or unfitting ratio degrades to the pad, never blows the wall.
# Pad is ~0.3s per ratio with honest per-ratio engine labels.
# The 1x1 is the primary (also mirrored to the top-level image_url for frontend
# back-compat).
_DELIVERY_RATIOS = ("1x1", "4x5", "9x16", "16x9")
# Ratios derived via live Stability outpaint when the budget gate passes. 4x5 is
# deliberately NOT listed: it stays a deterministic Pillow cover-pad so at most two
# outpaint invokes ever run inside the 22s wall.
_OUTPAINT_RATIOS = ("9x16", "16x9")
# Per-outpaint worst-case cost estimate (ms): the fail-fast read timeout (12s) plus
# connect + decode + normalize headroom. An outpaint is attempted ONLY while the
# set clock still covers this PLUS the outpaint reserve, so a slow extend degrades
# to the pillow pad instead of blowing the immovable 22s wall.
_OUTPAINT_BUDGET_MS = int(os.getenv("GENERATE_OUTPAINT_BUDGET_MS", "13000"))
# Held-back reservation (ms) for the remaining per-ratio work (pads, brand overlay,
# kraft finalize) after an outpaint attempt. Mirrors the rung-C reservation pattern.
_OUTPAINT_RESERVE_MS = int(os.getenv("GENERATE_OUTPAINT_RESERVE_MS", "2000"))
# Per-ratio headline slab size (C06: 56/64/72).
_HEADLINE_PX = {"1x1": 56, "9x16": 64, "16x9": 72, "4x5": 60, "2x3": 64}

# sku-photo-map: catalog handle -> best real lifestyle DAM key (full key, NOT under
# the dam/ prefix). Loaded once; the file ships in the deployment (Lambda-safe).
# Default (repo-checkout) location. _resolve_map_path() picks the first candidate
# that actually exists at runtime — the install layout differs between local dev
# (parents[2] IS the repo root with data/) and the Lambda image (pip install .
# lands the module under site-packages, where parents[2]/data does not exist).
_SKU_PHOTO_MAP_PATH = Path(__file__).parents[2] / "data" / "products" / "sku-photo-map.json"
# theme-asset-map: theme-slug -> best real thematic DAM key. Sibling of sku-photo-map,
# same 3-candidate resolve pattern. A chip theme drives the IMAGE (theme wins over the
# product default) — see generate_hero precedence.
_THEME_ASSET_MAP_PATH = Path(__file__).parents[2] / "data" / "products" / "theme-asset-map.json"
_scrim_hex = "#1A1110CC"  # tokens kodiak.color.semantic.overlay.scrim (warm ink)
_accent_hex = "#E8530E"  # tokens kodiak.color.brand.blazeOrange

# Persona sanitization: a theme slug naming a real person is REJECTED by Stability's
# content filter (finish_reasons:["Filter reason: prompt"]) and by extension poisons
# any Nova Pro scene prompt that echoes it. Map named-person slugs to a filter-safe
# descriptive persona so the raw name NEVER reaches a prompt. Ordinary theme slugs
# fall through to the plain slug-to-words form. Add entries as new named-person themes
# appear — each is a one-line slug -> persona mapping. This map is PROMPT-ONLY; the
# theme-asset-map seed-photo selection stays keyed on the raw slug (unchanged).
_THEME_PERSONA_MAP: dict[str, str] = {
    "zac-efron": "energetic athletic young man, morning-fitness lifestyle vibe",
}

# Per-theme scene guidance for the Nova Pro control-structure restyle prompt. When a
# theme has an entry here, its vivid scene description is folded into the art-director
# prompt AND the deterministic fallback prompt so the restyle lands on-theme even with
# no live Nova Pro. Entries stay GENERIC — no real person's name or likeness. For the
# US Ski & Snowboard partner campaign this honors the real partnership (Milano Cortina
# 2026, Park City, Kodiak Kitchen at the USANA Center of Excellence) without naming or
# implying endorsement by any individual athlete.
_THEME_SCENE_HINT: dict[str, str] = {
    "us-ski-snowboard": (
        "winter Wasatch alpine dawn, fresh snow and pine ridgeline above Park City, "
        "cast-iron protein stack as athlete fuel before the training day, crisp cold "
        "light, podium-energy mood, generic active winter athletes only (no faces, no "
        "real person), on-brand Kodiak"
    ),
}


def _safe_theme_text(theme_slug: str) -> str:
    """Return prompt-safe descriptive text for a theme slug.

    A named-person slug maps to its filter-safe persona (no real name); any other slug
    falls back to the plain slug-to-words form. Only text destined for a PROMPT passes
    through here — seed-photo selection remains keyed on the raw slug.
    """
    persona = _THEME_PERSONA_MAP.get(theme_slug)
    if persona is not None:
        return persona
    return theme_slug.replace("-", " ")


def _safe_prompt_text(prompt: str) -> str:
    """Strip real celebrity names out of a free-text incoming prompt.

    The frontend builds the prompt client-side and can embed a real person's display
    name (e.g. "Zac Efron") verbatim. That name reaches Stability via brief_msg and
    trips the content filter (finish_reasons:["Filter reason: prompt"]). For every
    named-person slug in _THEME_PERSONA_MAP, replace the display name ("Zac Efron")
    and the spaced-slug form ("zac efron") with the filter-safe persona text, matching
    case-insensitively. Ordinary prompts with no named person pass through unchanged.
    """
    out = prompt
    for slug, persona in _THEME_PERSONA_MAP.items():
        words = slug.split("-")
        display_name = " ".join(words).title()  # "zac-efron" -> "Zac Efron"
        spaced_slug = " ".join(words)  # "zac efron"
        for needle in (display_name, spaced_slug):
            # case-insensitive replace without regex: scan lowercased copy for the span
            lowered = out.lower()
            target = needle.lower()
            start = lowered.find(target)
            while start != -1:
                out = out[:start] + persona + out[start + len(needle):]
                lowered = out.lower()
                start = lowered.find(target)
    return out

# Where real source assets live on disk.
_ASSET_ROOTS = (Path("input_assets"), Path("data/raw-ingest"))
_ASSET_EXTS = (".png", ".jpg", ".jpeg", ".webp")
# Converse image content only accepts a fixed format set; map extensions to it.
_CONVERSE_FMT = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}

# Palette from S3-backed tokens (fallback to Kodiak frontier)
try:
    from .token_loader import get_brand_colors, load_tokens  # type: ignore

    _tok = load_tokens()
    _brand = get_brand_colors(_tok)
    MOCK_PALETTES = [
        (_brand[0], _brand[1]),
        (_brand[2] if len(_brand) > 2 else _brand[0], _brand[1]),
        (_brand[0], _brand[2] if len(_brand) > 2 else _brand[0]),
        (_brand[1], _brand[0]),
    ]
    try:
        _sem = _tok["kodiak"]["color"]["semantic"]
        _scrim_hex = _sem["overlay"]["scrim"]["$value"]
        # accent is blazeOrange; brand list index 1 is blazeOrange per get_brand_colors
        _accent_hex = _brand[1] if len(_brand) > 1 else _accent_hex
    except Exception:
        pass
except Exception:
    MOCK_PALETTES = [
        ("#3B2316", "#E8530E"),
        ("#1A3C34", "#E8530E"),
        ("#3B2316", "#1A3C34"),
        ("#E8530E", "#3B2316"),
    ]


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


# --------------------------------------------------------------- SKU -> photo resolver
_SKU_PHOTO_MAP_CACHE: Optional[dict] = None


def _resolve_map_path() -> Path:
    """Pick the sku-photo-map path that exists under the current install layout.

    Candidate order (first existing wins):
      a. $SKU_PHOTO_MAP_PATH (Lambda points this at the shipped copy in /var/task)
      b. Path(__file__).parents[2]/data/products/sku-photo-map.json (repo checkout)
      c. Path(__file__).parent/data/sku-photo-map.json (map packaged with the module)
    Falls back to the parents[2] default even if absent, so a load failure names a
    sensible path in its error message.
    """
    candidates: list[Path] = []
    env = os.getenv("SKU_PHOTO_MAP_PATH")
    if env:
        candidates.append(Path(env))
    candidates.append(_SKU_PHOTO_MAP_PATH)
    candidates.append(Path(__file__).parent / "data" / "sku-photo-map.json")
    for c in candidates:
        if c.exists():
            return c
    return _SKU_PHOTO_MAP_PATH


def _load_sku_photo_map() -> dict:
    """Load the sku-photo-map once. Returns the {handle: entry} map.

    Path resolved by _resolve_map_path() so it works both in local dev and in the
    Lambda image. Module-level cache. Returns an empty dict on any read/parse
    failure so the caller falls through to disk/mock.
    """
    global _SKU_PHOTO_MAP_CACHE
    if _SKU_PHOTO_MAP_CACHE is not None:
        return _SKU_PHOTO_MAP_CACHE
    try:
        data = json.loads(_resolve_map_path().read_text(encoding="utf-8"))
        _SKU_PHOTO_MAP_CACHE = data.get("map", {}) if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001 — missing/unreadable map -> disk/mock fallback
        print(f"[generate] sku-photo-map load skipped: {e}", file=sys.stderr)
        _SKU_PHOTO_MAP_CACHE = {}
    return _SKU_PHOTO_MAP_CACHE


def _resolve_dam_photo(product_id: str) -> Optional[str]:
    """Return the best real lifestyle DAM key for a catalog handle, else None.

    Exact-match lookup on product_id. Prefers photo_key; if absent, walks the
    fallbacks list. Returns None when the handle is not in the map.
    """
    entry = _load_sku_photo_map().get(product_id)
    if not isinstance(entry, dict):
        return None
    primary = entry.get("photo_key")
    if isinstance(primary, str) and primary.strip():
        return primary
    for fb in entry.get("fallbacks", []) or []:
        if isinstance(fb, str) and fb.strip():
            return fb
    return None


# ------------------------------------------------------------- theme -> photo resolver
_THEME_ASSET_MAP_CACHE: Optional[dict] = None


def _resolve_theme_map_path() -> Path:
    """Pick the theme-asset-map path that exists under the current install layout.

    Candidate order (first existing wins), mirroring _resolve_map_path:
      a. $THEME_ASSET_MAP_PATH (Lambda points this at the shipped copy in /var/task)
      b. Path(__file__).parents[2]/data/products/theme-asset-map.json (repo checkout)
      c. Path(__file__).parent/data/theme-asset-map.json (map packaged with the module)
    Falls back to the parents[2] default even if absent, so a load failure names a
    sensible path in its error message.
    """
    candidates: list[Path] = []
    env = os.getenv("THEME_ASSET_MAP_PATH")
    if env:
        candidates.append(Path(env))
    candidates.append(_THEME_ASSET_MAP_PATH)
    candidates.append(Path(__file__).parent / "data" / "theme-asset-map.json")
    for c in candidates:
        if c.exists():
            return c
    return _THEME_ASSET_MAP_PATH


def _load_theme_asset_map() -> dict:
    """Load the theme-asset-map once. Returns the {theme-slug: entry} map.

    Module-level cache. Returns an empty dict on any read/parse failure so the
    caller falls through to the existing product precedence.
    """
    global _THEME_ASSET_MAP_CACHE
    if _THEME_ASSET_MAP_CACHE is not None:
        return _THEME_ASSET_MAP_CACHE
    try:
        data = json.loads(_resolve_theme_map_path().read_text(encoding="utf-8"))
        _THEME_ASSET_MAP_CACHE = data.get("map", {}) if isinstance(data, dict) else {}
    except Exception as e:  # noqa: BLE001 — missing/unreadable map -> product fallback
        print(f"[generate] theme-asset-map load skipped: {e}", file=sys.stderr)
        _THEME_ASSET_MAP_CACHE = {}
    return _THEME_ASSET_MAP_CACHE


def _resolve_theme_photo(theme_slug: str) -> Optional[str]:
    """Return the best real thematic DAM key for a theme slug, else None.

    Prefers photo_key; if somehow absent, walks the pool list. Returns None when
    the theme is not in the map.
    """
    entry = _load_theme_asset_map().get(theme_slug)
    if not isinstance(entry, dict):
        return None
    primary = entry.get("photo_key")
    if isinstance(primary, str) and primary.strip():
        return primary
    for p in entry.get("pool", []) or []:
        if isinstance(p, str) and p.strip():
            return p
    return None


def _mock_hero(product_name: str, brief_msg: str, region: str, out_path: Path, idx: int = 0) -> Path:
    """Deterministic on-brand placeholder hero (1024x1024). True last resort only.

    Reached only when neither the requested product nor the default brand hero can
    be fetched (offline/CI, or S3 down in prod). Carries no "MOCK" watermark — the
    caller labels it FALLBACK_SOURCE, never "mock"/"preview".
    """
    W, H = 1024, 1024
    bg_hex, accent_hex = MOCK_PALETTES[idx % len(MOCK_PALETTES)]
    bg = _hex_to_rgb(bg_hex)
    accent = _hex_to_rgb(accent_hex)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)
    draw.ellipse([W * 0.15, H * 0.12, W * 0.85, H * 0.62], fill=accent)

    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 56)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    text = product_name[:32]
    bbox = draw.textbbox((0, 0), text, font=font_big)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) / 2, H * 0.68), text, fill="white", font=font_big)

    sub = f"{region}  ·  {brief_msg[:40]}"
    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((W - tw2) / 2, H * 0.76), sub, fill=(255, 255, 255, 200), font=font_small)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def _brand_floor(product_name: str, ratio: str, out_path: Path) -> Path:
    """Rung D — the ultimate floor. Real Kodiak pixels, ZERO network, cannot fail.

    Composite the bundled-in-the-deployment-package Kodiak brand logo onto a Bear-Brown
    brand-color canvas with a Blaze Orange accent bar and the product wordmark. The logo
    ships INSIDE the module (src/creative_automation/brand_assets/), so it lands in
    /var/task with the code — no S3, no external fetch, always present. If the bundled
    asset is somehow unreadable, the canvas + wordmark + accent bar are still real Kodiak
    brand pixels drawn purely in Pillow, so this rung has no failure path and no
    fallthrough — nothing sits below it.
    """
    W, H = _CANVAS.get(ratio, _CANVAS["1x1"])
    bg = _hex_to_rgb(MOCK_PALETTES[0][0])  # Bear Brown brand base
    accent = _hex_to_rgb(_accent_hex)  # Blaze Orange
    canvas = Image.new("RGB", (W, H), bg)

    # bundled brand logo, centered in the upper safe area — the real brand mark. Never
    # let a logo read failure sink the rung: the wordmark + canvas below are the floor.
    try:
        if _BRAND_FLOOR_ASSET.exists():
            logo = Image.open(_BRAND_FLOOR_ASSET).convert("RGBA")
            max_w, max_h = int(W * 0.5), int(H * 0.38)
            scale = min(max_w / logo.width, max_h / logo.height)
            lw, lh = max(1, int(logo.width * scale)), max(1, int(logo.height * scale))
            logo = logo.resize((lw, lh), Image.LANCZOS)
            canvas.paste(logo, ((W - lw) // 2, int(H * 0.16)), logo)
    except Exception as e:  # noqa: BLE001 — floor never fails; wordmark below stands in
        print(f"[generate] brand-floor logo skipped: {e}", file=sys.stderr)

    draw = ImageDraw.Draw(canvas)
    try:
        font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()

    word = "KODIAK CAKES"
    bbox = draw.textbbox((0, 0), word, font=font_big)
    draw.text(((W - (bbox[2] - bbox[0])) / 2, H * 0.62), word, fill="white", font=font_big)
    sub = f"{product_name[:32]}  ·  Keep It Wild"
    bbox2 = draw.textbbox((0, 0), sub, font=font_small)
    draw.text(((W - (bbox2[2] - bbox2[0])) / 2, H * 0.72), sub, fill=(255, 248, 240), font=font_small)

    # Blaze Orange accent bar pinned to the very bottom (brand signature).
    draw.rectangle([0, H - 8, W, H], fill=accent)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG")
    return out_path


def _call_with_optional_deadline(fn, *args, deadline_ms=None):
    """Call fn(*args, deadline_ms=...) but tolerate callables without that kwarg.

    The real probe fns (_find_source_asset, dam.resolve_packshot) accept deadline_ms so
    the fan-out can bail mid-loop. Test stubs and older signatures may not — fall back to
    the bare call so threading the deadline never breaks a monkeypatched path.
    """
    try:
        return fn(*args, deadline_ms=deadline_ms)
    except TypeError:
        return fn(*args)


def _find_source_asset(product_id: str, product_name: str, deadline_ms=None) -> Optional[Path]:
    """Locate a real source image for the product.

    Order: input_assets/<product_id>/hero-real.png, then hero.png, then any image
    in that product dir, then a name-matching glob across the asset roots, then an
    S3 DAM fallback (fetch_hero_to_tmp) for Lambda where no assets are baked in.

    deadline_ms (optional zero-arg callable -> remaining ms) bounds the step-3 S3
    fan-out so an unmapped-SKU probe abandons mid-loop rather than running to ~37s.
    """
    # 1) canonical per-product location, hero-real preferred over hero
    prod_dir = Path("input_assets") / product_id
    if prod_dir.is_dir():
        for name in ("hero-real", "hero"):
            for ext in _ASSET_EXTS:
                c = prod_dir / f"{name}{ext}"
                if c.exists():
                    return c
        for ext in _ASSET_EXTS:
            hits = sorted(prod_dir.glob(f"*{ext}"))
            if hits:
                return hits[0]

    # 2) name/id-matching glob across asset roots
    slug = product_name.lower().replace(" ", "-")
    tokens = {product_id.lower(), slug}
    for root in _ASSET_ROOTS:
        if not root.is_dir():
            continue
        for ext in _ASSET_EXTS:
            for cand in sorted(root.rglob(f"*{ext}")):
                stem = cand.stem.lower()
                if any(tok and tok in stem for tok in tokens):
                    return cand

    # 3) S3 DAM fallback — the Lambda container ships with NO assets baked in, so
    # the real heroes live only in S3 (s3://<DAM bucket>/brands/kodiak/heroes/
    # <product>/hero-real.png|hero.png). Materialize into /tmp (Lambda's only
    # writable path) and return the local copy so the existing Nova Pro compose
    # flow runs on the real asset. Offline-safe: fetch_hero_to_tmp returns None
    # when S3 is disabled / boto3 missing / key absent, so local dev and CI keep
    # falling through to mock without raising.
    try:
        from .dam import fetch_hero_to_tmp  # local import — keeps offline path import-light

        s3_hit = _call_with_optional_deadline(fetch_hero_to_tmp, product_id, deadline_ms=deadline_ms)
        if s3_hit is not None and s3_hit.exists():
            return s3_hit
    except Exception as e:  # noqa: BLE001 — S3 discovery never breaks the mock fallback
        print(f"[generate] S3 hero discovery skipped: {e}", file=sys.stderr)
    return None


_NOVA_SEED_MAX_SIDE = int(os.getenv("BEDROCK_NOVA_SEED_MAX_SIDE", "1024"))


def _seed_small_for_nova(src: Path) -> tuple[bytes, str]:
    """Downscaled RGB JPEG of the seed for Nova Converse vision calls.

    Root-cause repair: hero-real seeds are 2400px/15MB+ PNGs and Converse drops
    image payloads over ~3.75MB (connection closed locally, hang-to-timeout in
    Lambda) — which starved rung B of its scene-prompt and rung C of its caption.
    1024px JPEG is ~100-200KB: same art-direction signal, fits every timeout.
    """
    img = Image.open(src).convert("RGB")
    if max(img.size) > _NOVA_SEED_MAX_SIDE:
        img.thumbnail((_NOVA_SEED_MAX_SIDE, _NOVA_SEED_MAX_SIDE), Image.LANCZOS)
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, "JPEG", quality=82)
    return buf.getvalue(), "jpeg"


def _nova_pro_caption(
    src: Path, product_name: str, brief_msg: str, region: str, audience: str
) -> Optional[str]:
    """Ask Nova Pro (Converse) for a short on-brand caption + layout hint. None on failure."""
    if boto3 is None:
        return None
    try:
        img_bytes, fmt = _seed_small_for_nova(src)
    except Exception:
        return None
    try:
        client = _bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
        prompt = (
            f"You are an ad art director. Product: '{product_name}'. Region: {region}. "
            f"Audience: {audience}. Campaign vibe: {brief_msg}. "
            "Look at the product image and reply with ONE short on-brand headline "
            "(max 6 words) on the first line, then one line 'LAYOUT: <left|right|center>' "
            "naming which side to leave as negative space for the product. No other text."
        )
        resp = client.converse(
            modelId=NOVA_TEXT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": {"format": fmt, "source": {"bytes": img_bytes}}},
                        {"text": prompt},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 120},
        )
        return resp["output"]["message"]["content"][0]["text"].strip()
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — silent fallback
        print(f"[generate] Nova Pro unavailable, falling back: {e}", file=sys.stderr)
        return None


def _nova_pro_scene_prompt(
    src: Path, product_name: str, brief_msg: str, region: str, audience: str, theme: str | None
) -> str:
    """Ask Nova Pro (Converse) for the control-structure restyle prompt.

    This is the art-director directing the IMAGE restyle (distinct from the headline
    caption). Returns a scene/theme description string that drives Stability's
    control-structure conditioning. Falls back to a deterministic brief/theme-derived
    prompt on any Nova Pro failure so the Stability call always has a usable prompt.
    """
    theme_hint = f" Theme: {_safe_theme_text(theme)}." if theme else ""
    scene_hint = _THEME_SCENE_HINT.get(theme or "", "")
    if scene_hint:
        theme_hint += f" Scene direction: {scene_hint}."
    default_prompt = (
        f"{product_name} product photo restyled for "
        f"{scene_hint or (_safe_theme_text(theme) if theme else brief_msg)}, "
        f"{region} {audience}, on-brand Kodiak lifestyle scene, natural light, high detail"
    ).strip()
    if boto3 is None:
        return default_prompt
    try:
        img_bytes, fmt = _seed_small_for_nova(src)
    except Exception:
        return default_prompt
    try:
        client = _bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
        prompt = (
            f"You are an ad art director directing an image restyle. Product: "
            f"'{product_name}'. Region: {region}. Audience: {audience}. Campaign vibe: "
            f"{brief_msg}.{theme_hint} Look at the product image, which must keep its "
            "composition. Reply with ONE vivid scene/style description (max 40 words, no "
            "line breaks, no quotes) that restyles this photo to the theme — lighting, "
            "setting, mood, palette. Keep the product recognizable. No headline text. "
            "The scene must contain NO text, letters, numbers, signage, or labels "
            "anywhere — blank surfaces only, since the model renders glyphs as gibberish."
        )
        resp = client.converse(
            modelId=NOVA_TEXT_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"image": {"format": fmt, "source": {"bytes": img_bytes}}},
                        {"text": prompt},
                    ],
                }
            ],
            inferenceConfig={"maxTokens": 120},
        )
        text = resp["output"]["message"]["content"][0]["text"].strip().replace("\n", " ")
        return text or default_prompt
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — deterministic fallback
        print(f"[generate] Nova Pro scene-prompt unavailable, using default: {e}", file=sys.stderr)
        return default_prompt


def _seed_b64_for_stability(src: Path) -> str:
    """Return a base64 PNG of the seed, upscaled to meet Stability's size floor.

    Stability control-structure requires each dim >= 64 (total pixels 4096..9437184).
    A seed below the floor in either dim is upscaled to a safe square before encode;
    an in-range seed is re-encoded as PNG verbatim (RGB) so the payload is well-formed.
    """
    img = Image.open(src).convert("RGB")
    w, h = img.size
    if w < _STABILITY_MIN_DIM or h < _STABILITY_MIN_DIM:
        img = img.resize((_STABILITY_UPSCALE_TO, _STABILITY_UPSCALE_TO), Image.LANCZOS)
    elif max(w, h) > _STABILITY_MAX_DIM:
        # Ceiling: a 2400px seed base64-encodes to ~20MB and burns the whole 13s
        # Stability reservation on upload alone. 1280px still resolves past the
        # 1080px campaign target and restyles in ~11s measured.
        scale = _STABILITY_MAX_DIM / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _bedrock_failfast_client(read_timeout: int | None = None):
    """Fail-fast bedrock-runtime client for EVERY Bedrock invoke in the request path.

    Explicit botocore Config: connect_timeout=3s, retries max_attempts=0, and a read
    timeout that defaults to the Stability cap (BEDROCK_READ_TIMEOUT_S=12s) but can be
    overridden — the two Nova Pro Converse calls pass BEDROCK_NOVA_READ_TIMEOUT_S (6s) so
    caption + scene-prompt + stability all fit under the ~24s soft budget. NO retries,
    because a retry inside the 30s gateway cap is a budget killer. This is the ONLY way a
    bedrock-runtime client is built in rung B — no bare boto3.client anywhere in the path,
    which is the fix for the 33s silent gap (an uncapped Nova Pro Converse call).
    """
    cfg = _BotoConfig(
        read_timeout=read_timeout if read_timeout is not None else BEDROCK_READ_TIMEOUT_S,
        connect_timeout=BEDROCK_CONNECT_TIMEOUT_S,
        retries={"max_attempts": 0, "mode": "standard"},
    )
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION, config=cfg)


def _stability_control_hero(seed: Path, prompt: str, out_path: Path) -> Optional[Path]:
    """Restyle the seed photo to the theme via Bedrock Stability control-structure.

    Invokes the us.stability.stable-image-control-structure-v1:0 inference profile with
    Stability's schema ({prompt, image, control_strength, output_format}) — NOT Nova's
    taskType schema. Decodes images[0] (base64 PNG) and writes it to out_path. Returns
    the path on success, None on any failure.

    AccessDenied is surfaced with its exact error code (a Bryan SSO refresh issue) — it
    is NOT swallowed silently into a mock. The caller downgrades to the Pillow compose
    only after this returns None, and the exact error is always logged to stderr.
    """
    if boto3 is None:
        print("[generate] stability skipped: boto3 unavailable", file=sys.stderr)
        return None
    try:
        client = _bedrock_failfast_client()
        body = {
            "prompt": _style_sandwich(prompt),
            "image": _seed_b64_for_stability(seed),
            "control_strength": STABILITY_CONTROL_STRENGTH,
            "seed": STABILITY_SEED,
            "output_format": "png",
        }
        resp = client.invoke_model(
            modelId=STABILITY_CONTROL_MODEL,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read())
        images = payload.get("images") or []
        if not images:
            print(
                f"[generate] stability returned no images: "
                f"finish_reasons={payload.get('finish_reasons')} keys={list(payload)}",
                file=sys.stderr,
            )
            return None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(images[0]))
        return out_path if out_path.exists() else None
    except (ReadTimeoutError, ConnectTimeoutError):
        # Rung-B budget guard: a timeout is re-raised so the generate_hero ladder classifies
        # the fallthrough as bedrock-timeout and drops to rung C (the "12s then fall to C"
        # behavior). Swallowing it here would lose that reason.
        raise
    except ClientError as e:  # surface the exact error code — never swallow AccessDenied
        code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[generate] stability control-structure ClientError [{code}]: {e}", file=sys.stderr)
        # A throttle is a distinct, retryable-elsewhere condition — re-raise so the ladder
        # records fallthrough_reason=throttle. Other client errors (AccessDenied, validation)
        # stay swallowed to None (the documented downgrade-to-Pillow path, code already logged).
        if "Throttl" in str(code):
            raise
        return None
    except (BotoCoreError, Exception) as e:  # noqa: BLE001 — non-AWS failures fall through
        print(f"[generate] stability control-structure failed: {e}", file=sys.stderr)
        return None


def _stability_outpaint(
    base_png: Path, target_w: int, target_h: int, prompt: str, out_path: Path
) -> Optional[Path]:
    """Extend base_png to (target_w, target_h) via Bedrock Stability outpaint.

    PART B — derive the 9x16 / 16x9 delivery ratios from the 1x1 control-structure
    hero so the subject stays consistent and only one restyle call is spent. Invokes the
    us.stability.stable-outpaint-v1:0 inference profile with Stability's edit schema
    ({prompt, image, left/right/up/down, output_format}) — NOT Nova's taskType. The
    left/right/up/down are pixel deltas added to each edge; here the base is centered so
    horizontal/vertical growth splits evenly across the two opposing edges. Decodes
    images[0] (base64 PNG) to out_path. Returns the path on success, None on any failure
    (the caller then falls back to a Pillow cover-pad of the same base — see
    _pillow_outpaint_fallback). Seed dims must stay in Stability's range (>=64/dim,
    4096..9437184 total px); the 1080x1080 hero and the modest deltas sit well inside.

    Uses the shared fail-fast bedrock-runtime client (rung-B pattern: connect 3s,
    read 12s, zero retries) so a hung extend can never stall the 22s wall — a
    timeout is re-raised so the caller records a timeout degrade, matching
    _stability_control_hero. The prompt goes through the frozen style sandwich so
    the extend stays on-brand.
    """
    if boto3 is None:
        print("[generate] outpaint skipped: boto3 unavailable", file=sys.stderr)
        return None
    try:
        base = Image.open(base_png).convert("RGB")
        bw, bh = base.size
        # Only ever GROW: negative deltas are clamped to 0 (outpaint extends, never crops).
        dw = max(target_w - bw, 0)
        dh = max(target_h - bh, 0)
        left = dw // 2
        right = dw - left
        up = dh // 2
        down = dh - up
        if left == right == up == down == 0:
            # already at/over target in both dims — nothing to extend.
            return None
        from io import BytesIO

        buf = BytesIO()
        base.save(buf, "PNG")
        image_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        client = _bedrock_failfast_client()
        body = {
            "prompt": _style_sandwich(prompt),
            "image": image_b64,
            "left": left,
            "right": right,
            "up": up,
            "down": down,
            "output_format": "png",
        }
        resp = client.invoke_model(
            modelId=STABILITY_OUTPAINT_MODEL,
            body=json.dumps(body),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(resp["body"].read())
        images = payload.get("images") or []
        if not images:
            print(
                f"[generate] outpaint returned no images: "
                f"finish_reasons={payload.get('finish_reasons')} keys={list(payload)}",
                file=sys.stderr,
            )
            return None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(images[0]))
        # Stability may return exact target or its own rounded dims; normalize to target.
        if out_path.exists():
            fitted = ImageOps.fit(
                Image.open(out_path).convert("RGB"),
                (target_w, target_h),
                method=Image.BICUBIC,
                centering=(0.5, 0.5),
            )
            fitted.save(out_path, "PNG")
            return out_path
        return None
    except (ReadTimeoutError, ConnectTimeoutError):
        # Budget guard (mirrors _stability_control_hero): re-raise so the
        # generate_hero_set per-ratio gate records a timeout degrade to the pad
        # instead of mislabeling it as a plain unavailable outpaint.
        raise
    except ClientError as e:  # surface the exact error code — never swallow AccessDenied
        code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[generate] outpaint ClientError [{code}]: {e}", file=sys.stderr)
        if "Throttl" in str(code):
            raise
        return None
    except (BotoCoreError, Exception) as e:  # noqa: BLE001 — non-AWS failures fall through
        print(f"[generate] outpaint failed: {e}", file=sys.stderr)
        return None


def _pillow_outpaint_fallback(base_png: Path, target_w: int, target_h: int, out_path: Path) -> Path:
    """Smart cover-fit of the 1x1 hero to a taller ratio when outpaint is unavailable.

    PART B fallback — cover-fit keeps the subject centered and fills the taller frame
    without letterbox bars (some crop of the long edge is accepted). The caller marks
    provenance engine "pillow-outpaint-fallback" so the response never claims a GenAI
    extend happened when it did not.
    """
    fitted = ImageOps.fit(
        Image.open(base_png).convert("RGB"),
        (target_w, target_h),
        method=Image.BICUBIC,
        centering=(0.5, 0.5),
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fitted.save(out_path, "PNG")
    return out_path


# --------------------------------------------------------------- kraft-paper texture
# PART D — a deterministic brown-paper-bag grain baked into every final render at ~2%.
# Pillow-only (numpy is not a core dependency), fixed-seed so output is byte-reproducible
# and testable. Warm kraft base ~#C8A97E + low-amplitude per-pixel noise + sparse fibrous
# specks. To dump a reusable 512x512 tile for the web side to load, run:
#     python -c "from creative_automation.generate import _kraft_texture; \
#                _kraft_texture(512, 512).save('kraft-512.png')"
_KRAFT_BASE = (200, 169, 126)  # ~#C8A97E warm kraft
_KRAFT_SEED = 20260101  # fixed so _kraft_texture(w,h) is deterministic across runs


def _kraft_texture(w: int, h: int) -> Image.Image:
    """Synthesize a deterministic subtle brown-paper-bag texture tile (RGB, w x h).

    Fixed-seed low-amplitude luminance noise over a warm kraft base plus a handful of
    slightly darker fibrous specks. Deterministic: same (w, h) -> identical bytes, so
    it is testable and reproducible. Pillow + stdlib random only, no numpy.
    """
    import random

    rng = random.Random(_KRAFT_SEED)
    img = Image.new("RGB", (w, h), _KRAFT_BASE)
    px = img.load()
    br, bg, bb = _KRAFT_BASE
    # per-pixel low-amplitude grain (+-10 luminance) — the paper-fiber tone variation.
    for y in range(h):
        for x in range(w):
            n = rng.randint(-10, 10)
            px[x, y] = (
                max(0, min(255, br + n)),
                max(0, min(255, bg + n)),
                max(0, min(255, bb + n)),
            )
    # sparse fibrous specks: ~1 per 900 px, a touch darker, 1px, for the bag grain.
    draw = ImageDraw.Draw(img)
    speck_count = max(1, (w * h) // 900)
    for _ in range(speck_count):
        sx = rng.randint(0, w - 1)
        sy = rng.randint(0, h - 1)
        d = rng.randint(18, 34)
        draw.point((sx, sy), fill=(max(0, br - d), max(0, bg - d), max(0, bb - d)))
    return img


_KRAFT_TILE_SIZE = 256
_kraft_tile_cache: Image.Image | None = None


def _kraft_tile_cached() -> Image.Image:
    """One deterministic 256px grain tile, memoized per process."""
    global _kraft_tile_cache
    if _kraft_tile_cache is None:
        _kraft_tile_cache = _kraft_texture(_KRAFT_TILE_SIZE, _KRAFT_TILE_SIZE)
    return _kraft_tile_cache


def _apply_paper_overlay(img: Image.Image, opacity: float = 0.02) -> Image.Image:
    """Blend the kraft texture over img at a very slight opacity (~2%). Returns RGB.

    PART D — the final step on every returned render (all ratios; every path).
    "Very slight, like 2% visible": alpha ~0.02-0.03, so the texture reads as a
    faint paper tooth, not a wash. Same-size output as input. Performance fix:
    the texture used to be synthesized per-pixel at full frame size (15s across
    4 ratios in pure Python — the measured full-mode wall killer). Now one memoized
    256px tile is resized with C-level BICUBIC (~50ms at 1920px). Deterministic:
    same tile + deterministic resize = identical bytes every run.
    """
    base = img.convert("RGB")
    tile = _kraft_tile_cached()
    if (base.width, base.height) != tile.size:
        tex = tile.resize((base.width, base.height), Image.BICUBIC)
    else:
        tex = tile
    return Image.blend(base, tex, max(0.0, min(1.0, opacity)))


# Nova Pro usually puts LAYOUT: on its own line, but sometimes appends it inline
# ("Power up mornings! LAYOUT: right") — an inline suffix must never reach the
# rendered headline. Matches a trailing LAYOUT directive anywhere in the line.
_LAYOUT_INLINE_RE = re.compile(r"\s*LAYOUT\s*:\s*(left|right|center)\s*$", re.IGNORECASE)


def _parse_layout(caption: str) -> tuple[str, str]:
    """Split Nova Pro text into (headline, side) where side in {left,right,center}."""
    headline, side = "", "center"
    for line in caption.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _LAYOUT_INLINE_RE.search(s)
        if m:
            side = m.group(1).lower()
            s = _LAYOUT_INLINE_RE.sub("", s).strip().strip('"')
            if s and not headline:
                headline = s
            continue
        if s.upper().startswith("LAYOUT:"):
            val = s.split(":", 1)[1].strip().lower()
            if val in ("left", "right", "center"):
                side = val
        elif not headline:
            headline = s.strip('"')
    return headline[:48], side


def _title_case_headline(text: str) -> str:
    """House-style headline: Title Case, no trailing period.

    str.title() mangles apostrophes ("Today's" -> "Today'S"), so capitalize per
    word-match instead. Model-written headlines only — the raw user-brief
    fallback stays byte-for-byte the user's words.
    """
    s = (text or "").strip().rstrip(".").strip()
    return re.sub(
        r"[A-Za-z]+(?:'[A-Za-z]+)?",
        lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(),
        s,
    )


def _scrub_director_line(text: str, examples: list[dict]) -> Optional[str]:
    """Extract one render-safe line from raw voice-model output.

    The fine-tuned model wraps lines in markdown (**bold**, "quotes"), prepends
    meta-preambles ("Here are the requested responses:"), and sometimes echoes
    an in-ask example back instead of writing. Any of those reaching the render
    is a defect, so: strip markup, drop preamble/bullet lines, take the first
    substantial line, and reject example-echoes (>=70% word overlap with any
    example). Returns None when nothing render-safe remains (caller resamples
    or falls back to stock Nova).
    """
    t = text.replace("**", "").replace("*", "").replace('"', "").replace("#", "")
    lines = [ln.strip(" -\u2022\t") for ln in t.strip().splitlines()]
    lines = [ln for ln in lines if len(ln.split()) >= 2]
    lines = [
        ln
        for ln in lines
        if not any(p in ln.lower() for p in _PREAMBLE_PATTERNS)
    ]
    if not lines:
        return None
    line = lines[0].strip()
    words = {w.strip(",.!?;:").lower() for w in line.split()} - {""}
    for example in examples:
        example_words = {
            w.strip(",.!?;:").lower()
            for w in str(example.get("caption", "")).split()
        } - {""}
        if example_words and words and len(words & example_words) / len(words) >= 0.7:
            return None
    return line or None


def _director_headline_text(
    product_name: str, brief_msg: str, region: str, audience: str
) -> Optional[str]:
    """Grounded-director headline: retrieve brand voice, direct, normalize.

    The concept loop in one bounded call: embed the request -> top-k corpus
    captions -> trained voice model directs with those examples in-ask ->
    scrub + layout-parse + house-style normalize. Returns None on ANY failure
    (no examples, offline mock source, refusal, unscrubbable output, timeout,
    exception) so the caller falls back to the stock Nova caption. The mock
    source is refused explicitly — a mock transport must never write a
    production headline. A refused/scrubbed trio resamples ONCE with the single
    best example (PROVEN IN PROD 2026-09-08: trios of fragment-grade captions
    decline while the top-1 alone complies); a dead transport does not
    resample — it falls straight through to Nova.
    """
    import sys as _sys

    def _dnote(msg: str) -> None:
        print(f"[director] {msg}", file=_sys.stderr)

    if not _director_enabled():
        _dnote("skip: kill-switch off")
        return None
    # Memo (PROVEN IN PROD 2026-09-08): generate_hero_set runs the headline
    # pipeline TWICE per pack (base hero + set headline) with the same brief —
    # the second run re-pays embed + up to two voice invokes (~14s) and burns
    # the 22s wall to rung D. Same inputs deterministically yield the same
    # voice line, so memoize per warm container (capped FIFO). A memo hit costs
    # ~0 and bypasses the budget gate + executor below. The kill-switch stays
    # above the memo so an ops flip takes effect immediately.
    global _DIRECTOR_MEMO
    try:
        _DIRECTOR_MEMO
    except NameError:
        _DIRECTOR_MEMO = {}
    memo_key = (product_name, brief_msg, region, audience)
    if memo_key in _DIRECTOR_MEMO:
        _dnote("memo hit")
        return _DIRECTOR_MEMO[memo_key]
    try:
        from . import art_director
        from . import director_memory
    except ImportError as e:
        _dnote(f"skip: import failed ({e})")
        return None

    def _attempt() -> Optional[str]:
        query = f"{product_name} {brief_msg} {region} {audience}".strip()
        examples, model_used = director_memory.retrieve(query, k=3)
        if not examples:
            _dnote(f"no examples (embed={model_used})")
            return None
        _dnote(f"retrieved {len(examples)} examples via {model_used}")
        ask = (
            f"Write one short on-brand headline (max 6 words) for {product_name}: "
            f"{brief_msg}. Region {region}, audience {audience}."
        )
        samples = [examples[:3]]
        if len(examples[:1]) < len(examples[:3]):
            samples.append(examples[:1])
        for sample in samples:
            if not sample:
                break
            result = art_director.art_direct_grounded(
                ask, "adventurous", examples=sample
            )
            if not isinstance(result, dict) or result.get("source") != _DIRECTOR_LIVE_SOURCE:
                _dnote(f"voice not live (source={(result or {}).get('source')})")
                return None
            text = str(result.get("text", "")).strip()
            if not text:
                continue
            if any(phrase in text.lower() for phrase in _REFUSAL_PHRASES):
                _dnote(f"voice refused ({text[:60]!r}) — resampling")
                continue
            line = _scrub_director_line(text, sample)
            if line is None:
                _dnote(f"voice output unusable ({text[:60]!r}) — resampling")
                continue
            headline, _side = _parse_layout(line)
            normed = _title_case_headline(headline)
            if normed:
                return normed
        return None

    # Leak-and-drain on timeout (same contract generate_lambda documents for its own
    # inner director timeout): exiting a `with` executor would shutdown(wait=True) and
    # block until the abandoned worker finishes its retries — the timeout would be a
    # lie and the wall would burn. shutdown(wait=False) abandons the worker; it writes
    # nothing shared, retries out, and drains harmlessly.
    try:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    except Exception:
        return None
    try:
        fut = executor.submit(_attempt)
        try:
            outcome = fut.result(timeout=_DIRECTOR_TIMEOUT_S)
        except Exception:
            outcome = None
    finally:
        executor.shutdown(wait=False)
    _DIRECTOR_MEMO[memo_key] = outcome
    while len(_DIRECTOR_MEMO) > 64:
        _DIRECTOR_MEMO.pop(next(iter(_DIRECTOR_MEMO)))
    return outcome


def _wrap_headline(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Word-wrap headline to fit max_w, capped at 3 lines (C04)."""
    if not text:
        return []
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        trial = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), trial, font=font)
        if bbox[2] - bbox[0] <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w
        if len(lines) == 3:
            break
    if cur and len(lines) < 3:
        lines.append(cur)
    return lines[:3]


def _apply_brand_overlay(
    base_img_path: Path,
    headline: str,
    ratio: str,
    out_path: Path,
) -> Path:
    """Draw only the deterministic Kodiak brand elements on top of an existing image.

    PART C — the on-brand layer, extracted so it can composite over EITHER a Stability
    GenAI hero (the image is already the background — no cover-fit, no scrim) OR the
    Pillow scene composer (which supplies its own cover-fit + scrim first). Draws:
    C04 the ~32% dark message bar at 68% down with the centered wrapped white headline
    (per-ratio font), and C03 the 8px Blaze Orange accent bar pinned to the bottom.
    (No text footer: the box art already carries the brand.)
    Never resizes the incoming image — the base is opened and drawn on at its own size.
    No Kodiak logo/wordmark (brand preference).
    """
    canvas = Image.open(base_img_path).convert("RGBA")
    W, H = canvas.size
    draw = ImageDraw.Draw(canvas)

    # C04 — message bar: semi-transparent dark band ~32% tall anchored at 68% down.
    bar_h = int(H * 0.32)
    bar_top = int(H * 0.68)
    bar = Image.new("RGBA", (W, bar_h), (*_hex_to_rgb(_scrim_hex), 200))
    canvas.alpha_composite(bar, (0, bar_top))

    if headline:
        px = _HEADLINE_PX.get(ratio, 56)
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", px)
        except Exception:
            font = ImageFont.load_default()
        pad = 48  # C03 safe-area pad
        lines = _wrap_headline(draw, headline, font, W - 2 * pad)
        # center the wrapped block vertically within the message bar
        line_h = int(px * 1.15)
        block_h = line_h * len(lines)
        ty = bar_top + (bar_h - block_h) // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            draw.text(((W - tw) / 2, ty), line, fill="white", font=font, stroke_width=2, stroke_fill=(0, 0, 0, 180))
            ty += line_h

    # (footer text removed 2026-09-08 cleanup order — the box art already carries the
    # Kodiak identity; stamping more brand text on the photo reads off-brand.)

    # C03 — 8px Blaze Orange accent bar at the very bottom.
    accent = _hex_to_rgb(_accent_hex)
    draw.rectangle([0, H - 8, W, H], fill=(*accent, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


def _recipe_card_defaults(product_name: str) -> dict:
    """On-brand default recipe fields derived from the product name (deterministic).

    Used when the brief supplies no recipe_fields. No randomness — same product name
    yields the same card copy, so _compose_recipe_card stays byte-deterministic.
    """
    return {
        "title": f"{product_name} Trail Stack",
        "ingredients": [
            f"2 cups {product_name} mix",
            "1 cup water or milk",
            "1 tbsp maple",
        ],
        "steps": [
            "Whisk mix with liquid",
            "Cook on a hot griddle",
            "Stack, top, and fuel up",
        ],
    }


def _compose_recipe_card(
    hero_img_path: Path,
    title: str,
    ratio: str,
    out_path: Path,
    recipe_fields: dict | None = None,
) -> Path:
    """Deterministic Pillow recipe-card: GenAI hero in a fixed image slot + brand card.

    The whole point: the card STRUCTURE is composed deterministically in Pillow
    (typography, title bar, ingredient/step zones, accent bar, safe-area), and the
    generative hero image is PLACED into a defined image slot rather than the model
    inventing the layout. Layout:

      - top ~55% : the GenAI hero, cover-fit into the image slot (ImageOps.fit BICUBIC)
      - title bar: a scrim-ink band straddling the hero/card seam, title in headline font
      - lower ~45%: token-brand card on a warm kraft base — an ingredients column and a
        steps column drawn in the body font, inside a safe-area pad
      - C03 8px Blaze Orange accent bar pinned to the very bottom

    Deterministic: same inputs -> same bytes (fonts + palette are fixed; the only
    randomness in the pipeline is the already-seeded kraft texture applied later by
    _finalize_render). Reuses generate.py palette constants (_scrim_hex, _accent_hex),
    _CANVAS dims, _HEADLINE_PX, and _wrap_headline — no new hardcoded hex.
    """
    W, H = _CANVAS.get(ratio, _CANVAS["1x1"])
    fields = recipe_fields or {}
    ingredients = [str(x) for x in fields.get("ingredients", []) if str(x).strip()]
    steps = [str(x) for x in fields.get("steps", []) if str(x).strip()]

    # image slot = top 55% of the canvas; the GenAI hero cover-fits it (stays the hero).
    slot_h = int(H * 0.55)
    hero = Image.open(hero_img_path).convert("RGB")
    hero_fit = ImageOps.fit(hero, (W, slot_h), method=Image.BICUBIC, centering=(0.5, 0.4))

    # card base: warm kraft ink for the lower region so it reads as a paper card.
    card = Image.new("RGB", (W, H), _KRAFT_BASE)
    card.paste(hero_fit, (0, 0))
    canvas = card.convert("RGBA")
    draw = ImageDraw.Draw(canvas)

    pad = 48  # C03 safe-area pad, shared with _apply_brand_overlay

    # title bar: a scrim-ink band across the hero/card seam, title centered in it.
    title_h = int(H * 0.14)
    title_top = slot_h - title_h // 2
    bar = Image.new("RGBA", (W, title_h), (*_hex_to_rgb(_scrim_hex), 220))
    canvas.alpha_composite(bar, (0, title_top))
    if title:
        px = _HEADLINE_PX.get(ratio, 56)
        try:
            tfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", px)
        except Exception:
            tfont = ImageFont.load_default()
        lines = _wrap_headline(draw, title, tfont, W - 2 * pad)
        line_h = int(px * 1.15)
        block_h = line_h * len(lines)
        ty = title_top + (title_h - block_h) // 2
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=tfont)
            tw = bbox[2] - bbox[0]
            draw.text(
                ((W - tw) / 2, ty), line, fill="white", font=tfont,
                stroke_width=2, stroke_fill=(0, 0, 0, 180),
            )
            ty += line_h

    # body zones: ingredients (left) + steps (right) in the kraft card region.
    body_px = max(20, int(_HEADLINE_PX.get(ratio, 56) * 0.42))
    try:
        hfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", body_px)
        bfont = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", body_px)
    except Exception:
        hfont = ImageFont.load_default()
        bfont = hfont
    ink = _hex_to_rgb(_scrim_hex)
    body_top = title_top + title_h + pad // 2
    line_gap = int(body_px * 1.4)
    col_x = {"left": pad, "right": W // 2 + pad // 2}

    def _draw_zone(x: int, heading: str, items: list[str]) -> None:
        y = body_top
        draw.text((x, y), heading, fill=(*ink, 255), font=hfont)
        y += line_gap
        for item in items[:6]:
            draw.text((x, y), f"- {item}", fill=(*ink, 255), font=bfont)
            y += line_gap

    _draw_zone(col_x["left"], "Ingredients", ingredients)
    _draw_zone(col_x["right"], "Steps", steps)

    # C03 — 8px Blaze Orange accent bar at the very bottom.
    accent = _hex_to_rgb(_accent_hex)
    draw.rectangle([0, H - 8, W, H], fill=(*accent, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


def _compose_scene(
    photo: Path,
    headline: str,
    ratio: str,
    out_path: Path,
    idx: int = 0,
    clean: bool = False,
) -> Path:
    """Scene-integration composer per social-3ratio.json. The real photo is the hero.

    C01 real photo COVER-fits the full canvas (ImageOps.fit BICUBIC) + a dark scrim
    blend (~0.18) for legibility — this REPLACES the ellipse entirely, no solid-color
    background anywhere on this path. The message bar + headline + Blaze Orange accent
    bar are then drawn by the shared _apply_brand_overlay (PART C) so the pure-Pillow
    path and the Stability-hero path share one deterministic brand layer. No Kodiak
    logo/wordmark is stamped — Kodiak campaigns carry no logo per brand preference.

    clean=True (render contract #199): the photographic cover + scrim stand alone —
    no message bar, no baked-in overlay text. Copy ships as sidecar files instead.
    """
    W, H = _CANVAS.get(ratio, _CANVAS["1x1"])

    # C01 — real lifestyle photo fills the frame as cover background + dark scrim.
    src_img = Image.open(photo).convert("RGB")
    cover = ImageOps.fit(src_img, (W, H), method=Image.BICUBIC, centering=(0.5, 0.5))
    scrim = Image.new("RGB", (W, H), _hex_to_rgb(_scrim_hex))
    canvas = Image.blend(cover, scrim, 0.18)

    # Write the scrimmed background, then delegate the deterministic brand layer to the
    # shared overlay so Stability heroes get the exact same message bar + accent bar.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path, "PNG")
    if clean:
        return out_path
    return _apply_brand_overlay(out_path, headline, ratio, out_path)


# ------------------------------------------------- render-contract layers (#196/#199/#200)
# Default Create returns a clean standalone image + copy sidecars; independently
# selectable layers (product image, retailer mark, partner mark) compose into the
# scene only when explicitly selected, default OFF. layers=None preserves the legacy
# behavior (packshot-first + baked overlay) for existing library callers and tests;
# ANY dict (even empty) selects the new contract.
LAYER_PRODUCT_IMAGE = "product_image"
LAYER_RETAILER = "retailer"
LAYER_PARTNER = "partner_logo"
LAYER_OVERLAY_TEXT = "overlay_text"

# Packaged US Ski & Snowboard partner mark (ships inside the module like the rung-D
# brand asset, so Lambda always has it — no S3, no web-origin fetch).
_PARTNER_MARK_ASSET = Path(__file__).parent / "brand_assets" / "us-ski-snowboard-kodiak.png"


def normalize_layers(layers: dict | None) -> dict | None:
    """Normalize a raw layers request into the contract shape. None stays None (legacy).

    Keeps only known keys: product_image/partner_logo/overlay_text (truthy flags) and
    retailer (a non-empty slug string). Anything else is dropped so a stray client key
    can never switch on a composite.
    """
    if layers is None:
        return None
    if not isinstance(layers, dict):
        return {}
    norm: dict = {}
    for flag in (LAYER_PRODUCT_IMAGE, LAYER_PARTNER, LAYER_OVERLAY_TEXT):
        if layers.get(flag):
            norm[flag] = True
    retailer = layers.get(LAYER_RETAILER)
    if isinstance(retailer, str) and retailer.strip():
        norm[LAYER_RETAILER] = retailer.strip().lower()
    return norm


def _resolve_retailer_mark(slug: str) -> Path | None:
    """Best-effort raster retailer mark for a slug. None when missing/unusable.

    Never raises and never fabricates: an unknown slug, a missing file, or an
    SVG-only lockup (Pillow cannot rasterize SVG here) all resolve to None so the
    caller records the layer unresolved and ships the clean image.
    """
    try:
        from .retailers import resolve_retailer  # local import — keeps offline path light

        res = resolve_retailer(slug)
        asset = res.asset_path
        if asset is None:
            return None
        asset = Path(asset)
        if asset.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp") and asset.exists():
            return asset
        sibling = asset.with_suffix(".png")
        if sibling.exists():
            return sibling
        return None
    except Exception:
        return None


def _paste_mark(canvas: Image.Image, mark: Image.Image, corner: str, frac: float) -> Image.Image:
    """Paste a small mark with a subtle white backing. corner: right|left."""
    W, H = canvas.size
    mw = max(48, int(W * frac))
    scale = mw / max(mark.width, 1)
    mh = max(1, int(mark.height * scale))
    mark = mark.resize((mw, mh), Image.BICUBIC)
    pad = max(4, int(W * 0.008))
    backing = Image.new("RGB", (mw + pad * 2, mh + pad * 2), (255, 255, 255))
    x = W - mw - pad * 2 - pad if corner == "right" else pad
    y = H - mh - pad * 2 - pad
    canvas.paste(backing, (x, y))
    canvas.paste(mark, (x + pad, y + pad), mark if mark.mode == "RGBA" else None)
    return canvas


def _apply_layer_marks(path: Path, layers: dict, provenance: dict) -> None:
    """Composite selected retailer/partner marks onto a finished clean render, in place.

    Best-effort and never fatal: an unresolvable mark is recorded in provenance
    (<layer>_layer: "unresolved:…") and the clean image ships untouched.
    """
    if not layers:
        return
    retailer = layers.get(LAYER_RETAILER)
    want_partner = bool(layers.get(LAYER_PARTNER))
    if not retailer and not want_partner:
        return
    try:
        canvas = Image.open(path).convert("RGB")
    except Exception as e:  # noqa: BLE001 — never lose the render over a mark
        print(f"[generate] layer marks skipped (unreadable base): {e}", file=sys.stderr)
        return
    applied: list[str] = []
    if retailer:
        mark_path = _resolve_retailer_mark(str(retailer))
        if mark_path is not None:
            try:
                canvas = _paste_mark(canvas, Image.open(mark_path).convert("RGBA"), "right", 0.16)
                applied.append(f"retailer:{retailer}")
            except Exception as e:  # noqa: BLE001 — unresolved, ship clean
                print(f"[generate] retailer mark paste failed: {e}", file=sys.stderr)
                provenance["retailer_layer"] = f"unresolved:{retailer}"
        else:
            provenance["retailer_layer"] = f"unresolved:{retailer}"
    if want_partner:
        if _PARTNER_MARK_ASSET.exists():
            try:
                canvas = _paste_mark(
                    canvas, Image.open(_PARTNER_MARK_ASSET).convert("RGBA"), "left", 0.14
                )
                applied.append("partner_logo")
            except Exception as e:  # noqa: BLE001 — unresolved, ship clean
                print(f"[generate] partner mark paste failed: {e}", file=sys.stderr)
                provenance["partner_layer"] = "unresolved:paste-failed"
        else:
            provenance["partner_layer"] = "unresolved:asset-missing"
    if applied:
        try:
            canvas.save(path, "PNG")
            provenance["layer_marks"] = applied
        except Exception as e:  # noqa: BLE001 — never lose the render over a mark
            print(f"[generate] layer marks save failed: {e}", file=sys.stderr)


def build_copy_sidecar(
    provenance: dict | None,
    prompt: str,
    platform_copy: dict | None = None,
    theme: str | None = None,
    product: str | None = None,
) -> dict:
    """Build the copy sidecars (#199): campaign copy as text + CSV, never baked in.

    Deterministic (no timestamps) so output is byte-stable. The headline prefers the
    composed copy_headline the ladder recorded, then the legacy overlay headline,
    then the raw brief — copy always ships even when the image is clean.
    """
    provenance = provenance or {}
    platform_copy = platform_copy or {}
    headline = (
        provenance.get("copy_headline")
        or provenance.get("headline")
        or str(prompt or "")[:80]
    )
    product_label = product or "kodiak"
    theme_line = f"theme: {theme}" if theme else "theme: none"
    txt_lines = [
        f"KODIAK campaign copy — {product_label}",
        theme_line,
        f"headline: {headline}",
        f"brief: {prompt}",
    ]
    for plat in sorted(platform_copy):
        entry = platform_copy[plat] or {}
        body = entry.get("body") or entry.get("description") or ""
        tags = entry.get("hashtags")
        tags = " ".join(tags) if isinstance(tags, list) else (tags or "")
        title = entry.get("headline") or entry.get("title") or ""
        txt_lines.append(f"[{plat}] {title} — {body} {tags}".strip())
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["field", "value"])
    writer.writerow(["product", product_label])
    writer.writerow(["theme", theme or ""])
    writer.writerow(["headline", headline])
    writer.writerow(["brief", prompt])
    for plat in sorted(platform_copy):
        entry = platform_copy[plat] or {}
        writer.writerow([f"{plat}.headline", entry.get("headline") or entry.get("title") or ""])
        writer.writerow([f"{plat}.body", entry.get("body") or entry.get("description") or ""])
        tags = entry.get("hashtags")
        writer.writerow([
            f"{plat}.hashtags",
            " ".join(tags) if isinstance(tags, list) else (tags or ""),
        ])
    return {"txt": "\n".join(txt_lines) + "\n", "csv": buf.getvalue()}


def generate_hero(
    product_id: str,
    product_name: str,
    brief_msg: str,
    region: str,
    audience: str,
    out_path: Path,
    idx: int = 0,
    ratio: str = "1x1",
    theme: str | None = None,
    brand_overlay: bool = True,
    paper_overlay: bool = True,
    bare_base: bool = False,
    seed_key: str | None = None,
    layers: dict | None = None,
) -> tuple[Path, str, dict]:
    """Generate a real Kodiak-social-style hero. Returns (path, source, provenance).

    layers selects the render contract (#199/#200): None (default) preserves the
    legacy behavior — packshot-first composite + baked overlay text. ANY dict (even
    empty) selects the clean contract — a standalone photographic image with NO
    center-pasted box and NO baked-in overlay text (copy ships via build_copy_sidecar);
    the product box composites only with layers={"product_image": True} (thirds
    placement, never center-pasted), and retailer/partner marks only with their keys.
    Under the clean contract the overlay_text layer alone re-enables the message bar.

    Never-fail degradation ladder A->B->C->D (linear, one-directional; every rung REAL
    Kodiak pixels). Each rung checks the remaining time budget against its worst-case cost
    before starting and skips a rung that will not fit; a caught failure logs cause+rung
    and CONTINUES down the ladder, never raising. Rung D cannot fail, so a well-formed call
    always ends in real pixels — 503 is unreachable from here.
      A packshot-composite  — real product BOX pasted verbatim over an AI-restyled
          scene when budget allows (tried first for a mapped SKU)
      B stability-restyle   — Bedrock restyle of a resolved seed, budget-gated + fail-fast
      C pillow-compose      — Pillow composite of the seed + brand overlay (guaranteed-real)
      D brand-floor         — bundled Kodiak brand asset on a brand-color canvas, ZERO I/O

    Seed resolution (which real photo becomes the rung-B seed), theme wins:
    0. theme provided AND _resolve_theme_photo(theme) resolves -> that thematic DAM
       photo is the seed (the chip theme drives the IMAGE, not the product default).
    0b. staged DAM pick (seed_key from the asset browser) -> that exact photo is the
       seed (the customer's pick drives the IMAGE). Fetched verbatim, never probed.
    a. no theme (or unresolved) -> sku-photo-map resolves the handle -> a REAL
       lifestyle DAM photo (dam.fetch_dam_key -> /tmp) is the seed.
    b. no map entry OR the DAM fetch fails -> disk _find_source_asset is the seed
       (unchanged discovery), so nothing regresses offline.

    PART A — provenance: a JSON-serializable dict explaining what was provided vs what
    was done, plus which rung produced the pixels + why the ladder fell through. PART C —
    brand_overlay (default-on) composites the deterministic brand layer. PART D —
    paper_overlay (default-on) bakes the ~2% kraft texture into the FINAL render.
    """
    # TIME BUDGET + DEADLINE. Capture the monotonic start once; the 24s soft budget (env
    # GENERATE_SOFT_BUDGET_MS) is the real authority, not the Lambda 300s timeout. Each
    # rung gates on remaining_ms() so the ladder always reserves time to reach a floor.
    start = time.monotonic()

    def remaining_ms() -> float:
        return GENERATE_SOFT_BUDGET_MS - (time.monotonic() - start) * 1000.0

    def _probe_ok() -> bool:
        """HARD WALL gate for a pre-ladder S3 probe.

        True only while the clock still leaves one probe's worst-case cost
        (_PROBE_BUDGET_MS) PLUS the rung-C reservation. Once false, the caller abandons
        the probe (no-seed / no-packshot) so a slow S3 fan-out can never starve the
        guaranteed-real rung C or D — the ladder still returns real pixels by ~24s.
        """
        return remaining_ms() >= _PROBE_BUDGET_MS + _C_RESERVATION_MS

    if ratio not in _CANVAS:
        ratio = "1x1"

    def _headline(src: Path) -> str:
        # grounded trained director first (budget-gated, bounded, live-source
        # only, already house-styled); stock Nova caption second; raw brief
        # last and verbatim. provenance records which voice wrote the line.
        if remaining_ms() >= _DIRECTOR_BUDGET_MS + _C_RESERVATION_MS:
            directed = _director_headline_text(
                product_name, brief_msg, region, audience
            )
            if directed:
                provenance["headline_source"] = _DIRECTOR_LIVE_SOURCE
                print(f"[director] grounded headline: {directed}", file=sys.stderr)
                return directed
        else:
            print(
                f"[director] skip: budget {remaining_ms():.0f}ms < "
                f"{_DIRECTOR_BUDGET_MS + _C_RESERVATION_MS}ms",
                file=sys.stderr,
            )
        caption = _nova_pro_caption(src, product_name, brief_msg, region, audience) or ""
        headline, _side = _parse_layout(caption)
        if headline:
            provenance["headline_source"] = "bedrock:nova-pro-caption"
            return _title_case_headline(headline)
        return brief_msg[:48]

    # Render-contract layers (#199/#200): normalize once; None = legacy ladder,
    # any dict = clean contract (no default box paste, no baked overlay text).
    layers = normalize_layers(layers)
    overlay_on = bool(brand_overlay) if layers is None else bool(layers.get(LAYER_OVERLAY_TEXT))
    want_box = layers is None or bool(layers.get(LAYER_PRODUCT_IMAGE))

    # PART A — provenance accumulator. Populated as the seed + engine paths resolve so
    # the response can explain "what was provided vs what was done to make this image".
    provenance: dict = {
        "seed_source": None,
        "seed_selection": "none",
        "engine": None,
        "rung": None,
        "fallthrough_reason": None,
        "elapsed_ms": None,
        "scene_prompt": None,
        "control_strength": None,
        "model": None,
        "incoming_prompt": brief_msg,
        "theme": theme,
        "headline": None,
        "overlay_applied": False,
        "paper_overlay": False,
        "packshot": None,
        "layers": layers,
        "clean": layers is not None,
        "copy_headline": None,
    }

    def _seal(reason: str | None = None) -> None:
        """Record the elapsed clock (and an optional fallthrough reason) into provenance."""
        provenance["elapsed_ms"] = int((time.monotonic() - start) * 1000.0)
        if reason is not None:
            provenance["fallthrough_reason"] = reason

    # ---- seed resolution: theme photo, else sku-mapped DAM photo, else disk asset.
    seed: Optional[Path] = None
    if theme:
        theme_key = _resolve_theme_photo(theme)
        if theme_key:
            try:
                from .dam import fetch_dam_key

                dest = Path("/tmp/kodiak-assets/theme") / Path(theme_key).name  # noqa: S108 — Lambda /tmp
                photo = fetch_dam_key(theme_key, dest)
                if photo is not None and photo.exists():
                    seed = photo
                    provenance["seed_selection"] = "theme-photo"
                    provenance["seed_source"] = Path(theme_key).stem
            except Exception as e:  # noqa: BLE001 — falls through to product precedence
                print(f"[generate] theme seed fetch failed: {e}", file=sys.stderr)
    if seed is None and seed_key:
        # staged DAM pick from the asset browser: the exact photo the customer chose.
        # Fetched verbatim by full key (no prefix join — browser contract); any failure
        # falls through to the normal resolution below, so a stale pick never sinks a rung.
        try:
            from .dam import fetch_dam_key

            dest = Path("/tmp/kodiak-assets/staged") / Path(seed_key).name  # noqa: S108 — Lambda /tmp
            photo = fetch_dam_key(seed_key, dest)
            if photo is not None and photo.exists():
                seed = photo
                provenance["seed_selection"] = "staged-dam-asset"
                provenance["seed_source"] = Path(seed_key).stem
                if theme == "riff-on-past-content":
                    provenance["riff_on"] = seed_key
        except Exception as e:  # noqa: BLE001 — falls through to sku-mapped lookup
            print(f"[generate] staged seed fetch failed: {e}", file=sys.stderr)
    if seed is None:
        photo_key = _resolve_dam_photo(product_id)
        if photo_key:
            try:
                from .dam import fetch_dam_key

                dest = Path("/tmp/kodiak-assets/scene") / Path(photo_key).name  # noqa: S108 — Lambda /tmp
                photo = fetch_dam_key(photo_key, dest)
                if photo is not None and photo.exists():
                    seed = photo
                    provenance["seed_selection"] = "sku-mapped-dam"
                    provenance["seed_source"] = Path(photo_key).stem
            except Exception as e:  # noqa: BLE001 — falls through to disk
                print(f"[generate] sku-mapped seed fetch failed: {e}", file=sys.stderr)
    if seed is None:
        # _find_source_asset's step 3 is an S3 DAM fan-out (sequential hero-real/hero x
        # ext misses ~10s+ on an unmapped SKU) that runs BEFORE any rung gate. Enter it
        # only while the wall still leaves room for a probe + the C reservation; past the
        # wall, abandon the seed probe (treat as no-seed) so the ladder still reaches a
        # real-pixel floor by ~24s.
        if _probe_ok():
            disk = _call_with_optional_deadline(
                _find_source_asset, product_id, product_name, deadline_ms=remaining_ms
            )
            if disk is not None and disk.exists():
                seed = disk
                provenance["seed_selection"] = "disk-asset"
                provenance["seed_source"] = disk.stem
        else:
            print(
                f"[generate] seed probe skipped (budget {remaining_ms():.0f}ms < "
                f"{_PROBE_BUDGET_MS + _C_RESERVATION_MS}ms) -> no-seed",
                file=sys.stderr,
            )
            provenance["fallthrough_reason"] = "budget-exhausted"

    # ---- PACKSHOT-FIRST (compose-fix root-cause repair): if a real product BOX resolves
    # for this SKU, paste it VERBATIM over a background scene — NO generative step touches
    # those product pixels, so it structurally cannot render as bread or candy. This
    # mirrors campaign.py::_render_asset order a/b. The BACKGROUND scene still gets the
    # rung-B restyle first when the budget allows (fresh AI pixels every render); the
    # box is pasted over the restyled scene, never fed into the restyle. Generation
    # remains the FALLBACK below for the no-packshot case. See
    # docs/architecture/compose-fix/compose-fix-spec.md.
    from .dam import resolve_packshot  # local import — keeps the offline path import-light

    # HARD WALL: resolve_packshot's step 3 (find_hero_asset) is another S3 fan-out on an
    # unmapped SKU. Only probe for a packshot while the wall still leaves a probe + the C
    # reservation; past the wall, skip straight to the generative ladder (rung C/D).
    # Clean contract (#199): no probe at all unless the product_image layer is selected —
    # default Create never center-pastes a box it went looking for.
    packshot = (
        _call_with_optional_deadline(resolve_packshot, product_id, deadline_ms=remaining_ms)
        if (want_box and _probe_ok())
        else None
    )
    if packshot is None and want_box and not _probe_ok():
        print(
            f"[generate] packshot probe skipped (budget {remaining_ms():.0f}ms < "
            f"{_PROBE_BUDGET_MS + _C_RESERVATION_MS}ms) -> generative ladder",
            file=sys.stderr,
        )
        provenance["fallthrough_reason"] = "budget-exhausted"
    if packshot is not None:
        try:
            # Headline pipeline runs on the packshot-first path too: the grounded
            # director + stock Nova caption both need an image source, and the
            # resolved packshot box photo serves when no seed photo resolved.
            # Without this the mapped-SKU path used the raw brief verbatim and
            # the director never ran in prod.
            headline_src = seed if seed is not None else packshot
            headline = _headline(headline_src) if headline_src is not None else brief_msg[:48]
            # Background scene: the already-resolved real seed photo (theme/sku/disk) is
            # the backdrop; when there is no seed, a deterministic on-brand background is
            # synthesized. Neither is a generative render of the PRODUCT — the box is the
            # only product pixels and it is pasted verbatim by compose_creative below.
            bg_path = out_path.parent / f"{out_path.stem}-bg.png"
            bg_path.parent.mkdir(parents=True, exist_ok=True)
            # AI background: restyle the seed scene (rung-B machinery, same budget
            # gate rung B itself uses) BEFORE the verbatim box paste, so a mapped
            # SKU ships fresh photographic pixels instead of recycling the raw DAM
            # photo. The box is pasted over the restyle below — never an input to
            # it. Any skip/failure keeps the unstyled seed; rung A never fails.
            #
            # WALL ARITHMETIC: a fresh restyle (~10s Bedrock) fits a preview but never
            # a full set (base + pads + uploads share the same 22s wall). Set bases
            # (bare_base) therefore NEVER restyle fresh — they reuse the content-
            # addressed cache a preview warmed, else the raw seed. Same pixels as the
            # preview, no second Bedrock call, wall holds.
            bg_restyle = False
            cache_key = None
            if seed is not None:
                try:
                    cache_key = _restyle_cache_key(
                        Path(seed).read_bytes(), product_name, brief_msg,
                        region, audience, theme)
                    cached = out_path.parent / f"{out_path.stem}-restyle-cached.png"
                    if _restyle_cache_get(cache_key, cached):
                        seed = cached
                        bg_restyle = True
                        provenance["bg_restyle_source"] = "cache"
                except Exception:
                    cache_key = None
            if (seed is not None and not bg_restyle and not bare_base
                    and remaining_ms() >= _B_BUDGET_MS + _C_RESERVATION_MS):
                try:
                    a_scene = _nova_pro_scene_prompt(
                        seed, product_name, brief_msg, region, audience, theme
                    )
                    provenance["scene_prompt"] = a_scene
                    if remaining_ms() >= _B_STABILITY_MS + _C_RESERVATION_MS:
                        restyled = out_path.parent / f"{out_path.stem}-restyle.png"
                        if _stability_control_hero(seed, a_scene, restyled) is not None and restyled.exists():
                            seed = restyled
                            bg_restyle = True
                            provenance["bg_restyle_source"] = "fresh"
                            if cache_key is not None:
                                _restyle_cache_put(cache_key, restyled)
                except Exception as e:  # noqa: BLE001 — unstyled seed, same as before
                    print(f"[generate] rung A bg restyle skipped: {e}", file=sys.stderr)
            provenance["bg_restyle"] = bg_restyle
            if seed is not None:
                bg_src = Image.open(seed).convert("RGB")
                bg_w, bg_h = _CANVAS.get(ratio, _CANVAS["1x1"])
                ImageOps.fit(bg_src, (bg_w, bg_h), method=Image.BICUBIC, centering=(0.5, 0.5)).save(bg_path, "PNG")
                provenance["seed_source"] = provenance["seed_source"] or Path(seed).stem
            else:
                _mock_hero(product_name, brief_msg, region, bg_path, idx)
            # Verbatim box composite: compose_creative pastes the real box (product_layer)
            # over the background and bakes its own message bar + accent bar, so no
            # separate _apply_brand_overlay is needed on this path (matches _render_asset).
            # Clean contract (#199/#200): bare composite (no message bar — copy ships as
            # sidecars) with thirds placement (composed into the scene, never
            # center-pasted). rung A only runs here when the product_image layer was
            # selected (want_box gate above).
            from .compose import compose_creative

            layer_box = layers is not None and bool(layers.get(LAYER_PRODUCT_IMAGE))
            compose_creative(
                hero_path=bg_path,
                out_path=out_path,
                message=headline if overlay_on else "",
                ratio_key=ratio,
                product_layer=packshot,
                bare=bare_base or (layers is not None),
                placement="thirds" if layer_box else "center",
            )
            provenance["engine"] = "packshot-composite"
            provenance["rung"] = "A"
            provenance["model"] = "pillow:compose-creative"
            provenance["packshot"] = str(packshot)
            # A staged DAM pick stays labelled: the box is pasted over the exact
            # photo the customer chose, so seed_selection must say so (the pick
            # drives the render — mislabelling it "packshot" hides that).
            if provenance.get("seed_selection") != "staged-dam-asset":
                provenance["seed_selection"] = "packshot"
            provenance["overlay_applied"] = bool(overlay_on)
            provenance["headline"] = headline if overlay_on else None
            provenance["copy_headline"] = headline
            _finalize_render(out_path, paper_overlay, provenance, layers)
            _seal()
            return out_path, PACKSHOT_SOURCE, provenance
        except Exception as e:  # noqa: BLE001 — a composite failure falls through to generation
            print(f"[generate] packshot composite failed, falling through to generation: {e}", file=sys.stderr)

    # ---- RUNG B (stability-restyle) -> RUNG C (pillow-compose) -> RUNG D (brand-floor).
    # Never-503 contract: every attempt below is wrapped so a caught failure logs
    # cause+rung and CONTINUES down the ladder. Rung D cannot fail, so the ladder always
    # ends in a 200 with real pixels.
    _bedrock_fail_tuple = (
        ReadTimeoutError,
        ConnectTimeoutError,
        ClientError,
        BotoCoreError,
        ValueError,
        KeyError,
        OSError,
    )
    if seed is not None:
        # ---- RUNG B: Bedrock stability-restyle. Attempted ONLY if the budget covers B's
        # worst-case cost PLUS the held-back C reservation, so a slow Bedrock call can
        # never starve rung C. Skipped (fall to C) when the budget will not fit — no seed
        # is not a concern here (seed is not None), so the budget gate is the sole B gate.
        if remaining_ms() >= _B_BUDGET_MS + _C_RESERVATION_MS:
            try:
                # Per-subcall budget gate 1 — the Nova Pro scene-prompt (fail-fast, capped
                # at BEDROCK_NOVA_READ_TIMEOUT_S). Enter it ONLY while the clock still
                # covers the scene call PLUS the downstream stability + C reservation, so a
                # slow Nova Pro can never consume the budget rung C needs. If it will not
                # fit, skip the rest of B and drop to C. The scene call itself also
                # degrades to a deterministic default on timeout, but this gate keeps the
                # WALL-CLOCK bounded even before the timeout fires.
                if remaining_ms() < _B_NOVA_SCENE_MS + _B_STABILITY_MS + _C_RESERVATION_MS:
                    print(
                        f"[generate] rung B scene-prompt skipped (budget {remaining_ms():.0f}ms < "
                        f"{_B_NOVA_SCENE_MS + _B_STABILITY_MS + _C_RESERVATION_MS}ms) -> rung C",
                        file=sys.stderr,
                    )
                    provenance["fallthrough_reason"] = "budget-exhausted"
                    raise _RungBBudgetSkip
                scene_prompt = _nova_pro_scene_prompt(
                    seed, product_name, brief_msg, region, audience, theme
                )
                provenance["scene_prompt"] = scene_prompt
                # Per-subcall budget gate 2 — the Stability invoke (fail-fast, capped at
                # BEDROCK_READ_TIMEOUT_S). Re-check AFTER the scene call actually spent its
                # time; if the remaining clock can no longer cover stability + the C
                # reservation, abandon B and fall to C rather than risk the gateway cap.
                if remaining_ms() < _B_STABILITY_MS + _C_RESERVATION_MS:
                    print(
                        f"[generate] rung B stability skipped (budget {remaining_ms():.0f}ms < "
                        f"{_B_STABILITY_MS + _C_RESERVATION_MS}ms) -> rung C",
                        file=sys.stderr,
                    )
                    provenance["fallthrough_reason"] = "budget-exhausted"
                    raise _RungBBudgetSkip
                stylized = _stability_control_hero(seed, scene_prompt, out_path)
                if stylized is not None and stylized.exists():
                    provenance["engine"] = "stability-restyle"
                    provenance["rung"] = "B"
                    provenance["control_strength"] = STABILITY_CONTROL_STRENGTH
                    provenance["seed"] = STABILITY_SEED
                    provenance["style"] = "sandwich-locked"
                    provenance["mascot_lock"] = _mascot_lock_on()
                    provenance["model"] = STABILITY_CONTROL_MODEL
                    # PART C — deterministic on-brand headline + accent bar ON TOP of the
                    # GenAI hero (Nova Pro still supplies the headline). Default-on for
                    # the legacy ladder; clean contract (#199) keeps the hero clean and
                    # records the line for the copy sidecars instead.
                    try:
                        b_headline = _headline(seed)
                        provenance["copy_headline"] = b_headline
                        if overlay_on:
                            _apply_brand_overlay(stylized, b_headline, ratio, stylized)
                            provenance["overlay_applied"] = True
                            provenance["headline"] = b_headline
                    except Exception as e:  # noqa: BLE001 — never lose the GenAI hero
                        print(f"[generate] brand overlay on stability hero failed: {e}", file=sys.stderr)
                    _finalize_render(stylized, paper_overlay, provenance, layers)
                    _seal()
                    return stylized, STABILITY_SOURCE, provenance
                # helper returned None — timeout/throttle/model-error already logged to
                # stderr with its exact code. Fall to rung C with a model-error reason.
                provenance["fallthrough_reason"] = "model-error"
            except _RungBBudgetSkip:
                # a per-subcall budget gate abandoned B (reason already set to
                # budget-exhausted) — fall cleanly to rung C, NOT a model error.
                pass
            except (ReadTimeoutError, ConnectTimeoutError) as e:
                print(f"[generate] rung B bedrock timeout -> fall to C: {e}", file=sys.stderr)
                provenance["fallthrough_reason"] = "bedrock-timeout"
            except ClientError as e:  # throttle / access / validation
                code = e.response.get("Error", {}).get("Code", "Unknown") if hasattr(e, "response") else "Unknown"
                reason = "throttle" if "Throttl" in str(code) else "model-error"
                print(f"[generate] rung B ClientError [{code}] -> fall to C: {e}", file=sys.stderr)
                provenance["fallthrough_reason"] = reason
            except _bedrock_fail_tuple as e:  # noqa: BLE001 — any other Bedrock failure falls to C
                print(f"[generate] rung B failed -> fall to C: {e}", file=sys.stderr)
                provenance["fallthrough_reason"] = "model-error"
        else:
            # budget will not fit B (+C reservation) — skip straight to C.
            print(
                f"[generate] rung B skipped (budget {remaining_ms():.0f}ms < "
                f"{_B_BUDGET_MS + _C_RESERVATION_MS}ms) -> rung C",
                file=sys.stderr,
            )
            provenance["fallthrough_reason"] = "budget-exhausted"

        # ---- RUNG C: Pillow compose overlay on the SAME seed. The guaranteed-real
        # workhorse rung B falls through to. Always available (no network).
        # Clean contract (#199): photographic cover only — the headline is recorded
        # for the copy sidecars, never baked into the pixels.
        try:
            c_headline = _headline(seed)
            provenance["copy_headline"] = c_headline
            result = _compose_scene(
                seed, c_headline if overlay_on else "", ratio, out_path, idx,
                clean=not overlay_on,
            )
            if result.exists():
                provenance["engine"] = "pillow-compose"
                provenance["rung"] = "C"
                provenance["model"] = "pillow:compose-scene"
                provenance["overlay_applied"] = bool(overlay_on)
                provenance["headline"] = c_headline if overlay_on else None
                _finalize_render(result, paper_overlay, provenance, layers)
                _seal()
                return result, "bedrock:nova-pro", provenance
        except Exception as e:  # noqa: BLE001 — falls through to rung D (brand-floor)
            print(f"[generate] rung C compose failed -> fall to rung D: {e}", file=sys.stderr)

    # ---- RUNG D (brand-floor): the ultimate floor. Reached when no seed resolved (so B/C
    # had nothing to work with), or when a rung-C compose somehow failed. Composites the
    # bundled Kodiak brand asset onto a brand-color canvas — ZERO external I/O, cannot
    # fail, no fallthrough. This is why 503 is unreachable from a well-formed POST.
    if provenance["fallthrough_reason"] is None:
        provenance["fallthrough_reason"] = "no-seed"
    floor = _brand_floor(product_name, ratio, out_path)
    provenance["engine"] = "brand-floor"
    provenance["rung"] = "D"
    provenance["model"] = "pillow:brand-floor"
    provenance["copy_headline"] = provenance.get("copy_headline") or brief_msg[:48]
    _finalize_render(floor, paper_overlay, provenance, layers)
    _seal()
    return floor, BRAND_FLOOR_SOURCE, provenance


def _finalize_render(
    path: Path, paper_overlay: bool, provenance: dict, layers: dict | None = None
) -> None:
    """PART D final step — bake the ~2% kraft texture into a render in place.

    Applies to every returned render on every path (stability, pillow, placeholder).
    Records paper_overlay=True in provenance on success. Never raises past the render —
    a texture failure must not lose the hero.

    layers (render contract #200): selected retailer/partner marks composite onto the
    finished render BEFORE the grain, so marks sit under the paper tooth like print.
    None (legacy) changes nothing.
    """
    if layers:
        try:
            _apply_layer_marks(path, layers, provenance)
        except Exception as e:  # noqa: BLE001 — marks are cosmetic; never lose the hero
            print(f"[generate] layer marks failed: {e}", file=sys.stderr)
    if not paper_overlay:
        return
    try:
        finished = _apply_paper_overlay(Image.open(path).convert("RGB"))
        finished.save(path, "PNG")
        provenance["paper_overlay"] = True
    except Exception as e:  # noqa: BLE001 — texture is cosmetic; never lose the hero over it
        print(f"[generate] paper overlay failed: {e}", file=sys.stderr)


def generate_hero_set(
    product_id: str,
    product_name: str,
    brief_msg: str,
    region: str,
    audience: str,
    out_dir: Path,
    theme: str | None = None,
    brand_overlay: bool = True,
    paper_overlay: bool = True,
    seed_key: str | None = None,
    layers: dict | None = None,
) -> tuple[list[dict], str, dict]:
    """Deliver all four sizes from ONE call. Returns (renders, source, provenance).

    Design (PART B): the primary 1x1 is generated once (clean, no overlays) so it can
    seed 9x16 + 16x9 via composed Stability outpaint extends — one restyle plus two
    extends, cheaper than three full restyles and keeps the subject consistent. Each
    extend is per-ratio budget-gated against the immovable 22s wall (slow ratios
    degrade to the Pillow pad); 4x5 is always the deterministic pad. After sizing,
    the deterministic brand layer (PART C) + the ~2% kraft texture (PART D) are
    applied uniformly to all four.

    renders: [{ratio, path, w, h, engine}, ...] in _DELIVERY_RATIOS order. The caller
    (handler) uploads each and builds the response renders[] + the top-level image_url
    back-compat = the 1x1 url. Provenance is one object for the whole set, noting which
    ratios came from outpaint vs the pillow-outpaint-fallback.
    """
    # Clean 1x1 base: engine runs once, overlays OFF, so the base is a pristine hero to
    # outpaint from (overlays are applied per-ratio below, after sizing).
    base_path = out_dir / "hero-1x1-base.png"
    base_path.parent.mkdir(parents=True, exist_ok=True)
    layers = normalize_layers(layers)
    provenance_layers = layers
    clean_base, source, provenance = generate_hero(
        product_id=product_id,
        product_name=product_name,
        brief_msg=brief_msg,
        region=region,
        audience=audience,
        out_path=base_path,
        idx=0,
        ratio="1x1",
        theme=theme,
        brand_overlay=False,
        paper_overlay=False,
        bare_base=True,
        seed_key=seed_key,
        layers=layers,
    )
    provenance["layers"] = provenance_layers
    provenance["clean"] = provenance_layers is not None

    # The set headline re-runs the full pipeline (grounded director first, stock
    # Nova normalized second) on the clean base — the base hero call above ran
    # with overlays off and left provenance["headline"] empty, and the old
    # Nova-only helper overwrote grounded provenance with an un-normalized line.
    headline, headline_source = _headline_for(clean_base, product_name, brief_msg, region, audience)
    provenance["headline"] = headline if brand_overlay else None
    provenance["copy_headline"] = provenance.get("copy_headline") or headline
    if headline_source:
        provenance["headline_source"] = headline_source
    provenance["ratios"] = {}
    # Per-ratio outpaint books: measured extend latency + degrade reasons, both
    # JSON-serializable. A slow ratio degrades to the pad — never blows the wall.
    provenance["outpaint_latency_ms"] = {}
    provenance["outpaint_degraded"] = {}
    # The base hero call above already spent most of the soft budget, so the set
    # clock starts HERE for the per-ratio outpaint gates (same monotonic source as
    # the ladder; remaining covers one outpaint PLUS the reserve for pads/overlays).
    _set_start = time.monotonic()

    def _set_remaining_ms() -> float:
        return GENERATE_SOFT_BUDGET_MS - (time.monotonic() - _set_start) * 1000.0

    # Raw subject for the outpaint extend prompt (_stability_outpaint wraps it in
    # the frozen style sandwich). Reuse the base hero's scene prompt so NO extra
    # Bedrock call burns the wall; fall back to the brief when it is absent.
    _outpaint_subject = (
        str(provenance.get("scene_prompt") or "").strip() or brief_msg
    )

    # recipe-cards theme routes each sized hero through the deterministic Pillow card
    # template (_compose_recipe_card): the GenAI hero drops into a fixed image slot and
    # the lower region becomes a token-brand card. Other themes keep the plain brand
    # overlay path unchanged. recipe_fields default from the product name (no brief seam
    # into this function), so the card copy is deterministic and on-brand.
    is_recipe_card = theme == "recipe-cards"
    recipe_fields = _recipe_card_defaults(product_name) if is_recipe_card else None
    if is_recipe_card:
        provenance["card_template"] = True

    renders: list[dict] = []
    for ratio in _DELIVERY_RATIOS:
        target_w, target_h = _CANVAS[ratio]
        ratio_path = out_dir / f"hero-{ratio}.png"
        if ratio == "1x1":
            # the primary is the clean base at its native square — copy forward.
            ImageOps.fit(
                Image.open(clean_base).convert("RGB"),
                (target_w, target_h),
                method=Image.BICUBIC,
                centering=(0.5, 0.5),
            ).save(ratio_path, "PNG")
            ratio_engine = "primary"
        elif ratio in _OUTPAINT_RATIOS:
            # Composed outpaint extend of the 1x1 hero, per-ratio budget-gated:
            # attempted ONLY while the set clock still covers one outpaint PLUS
            # the reserve — a slow ratio degrades to the pad, never blows the
            # immovable 22s wall. Latency is measured per ratio for the report.
            ratio_engine = "pillow-outpaint-fallback"
            if _set_remaining_ms() < _OUTPAINT_BUDGET_MS + _OUTPAINT_RESERVE_MS:
                provenance["outpaint_degraded"][ratio] = "budget-exhausted"
                _pillow_outpaint_fallback(clean_base, target_w, target_h, ratio_path)
            else:
                _t0 = time.monotonic()
                try:
                    extended = _stability_outpaint(
                        clean_base, target_w, target_h, _outpaint_subject, ratio_path
                    )
                except (ReadTimeoutError, ConnectTimeoutError):
                    extended = None
                    provenance["outpaint_degraded"][ratio] = "bedrock-timeout"
                except Exception as e:  # noqa: BLE001 — throttle/sabotage degrades
                    extended = None
                    provenance["outpaint_degraded"][ratio] = f"outpaint-error: {type(e).__name__}"
                finally:
                    provenance["outpaint_latency_ms"][ratio] = round(
                        (time.monotonic() - _t0) * 1000.0, 1
                    )
                if extended is not None and ratio_path.exists():
                    ratio_engine = "stability-outpaint"
                else:
                    provenance["outpaint_degraded"].setdefault(ratio, "outpaint-unavailable")
                    _pillow_outpaint_fallback(clean_base, target_w, target_h, ratio_path)
        else:
            # 4x5 stays a deterministic Pillow cover-pad (never a live outpaint):
            # photographic, fast (~0.3s), and honest about what it is.
            _pillow_outpaint_fallback(clean_base, target_w, target_h, ratio_path)
            ratio_engine = "pillow-outpaint-fallback"

        # PART C — deterministic brand layer over each sized render (default-on). For the
        # recipe-cards theme this is the full card template instead of the plain overlay.
        if is_recipe_card:
            try:
                _compose_recipe_card(ratio_path, headline, ratio, ratio_path, recipe_fields)
                ratio_engine = f"{ratio_engine}+recipe-card-template"
            except Exception as e:  # noqa: BLE001 — never lose the render over the card layer
                print(f"[generate] recipe-card template on {ratio} failed: {e}", file=sys.stderr)
        elif brand_overlay:
            try:
                _apply_brand_overlay(ratio_path, headline, ratio, ratio_path)
            except Exception as e:  # noqa: BLE001 — never lose the render over the overlay
                print(f"[generate] brand overlay on {ratio} failed: {e}", file=sys.stderr)
        # PART D — bake the ~2% kraft texture as the final step on every render.
        # Selected retailer/partner marks (#200) composite per ratio under the grain.
        _finalize_render(ratio_path, paper_overlay, provenance, layers)

        with Image.open(ratio_path) as im:
            w, h = im.size
        renders.append({"ratio": ratio, "path": ratio_path, "w": w, "h": h, "engine": ratio_engine})
        provenance["ratios"][ratio] = ratio_engine

    provenance["overlay_applied"] = bool(brand_overlay) or is_recipe_card
    return renders, source, provenance


def _headline_for(
    src: Path, product_name: str, brief_msg: str, region: str, audience: str
) -> tuple[str, Optional[str]]:
    """Set headline through the full pipeline (module-level so generate_hero_set
    can reuse it). Returns (headline, headline_source|None): the grounded
    director first, stock Nova normalized second, raw brief last."""
    directed = _director_headline_text(product_name, brief_msg, region, audience)
    if directed:
        return directed, _DIRECTOR_LIVE_SOURCE
    caption = _nova_pro_caption(src, product_name, brief_msg, region, audience) or ""
    headline, _side = _parse_layout(caption)
    if headline:
        return _title_case_headline(headline), "bedrock:nova-pro-caption"
    return brief_msg[:48], None
