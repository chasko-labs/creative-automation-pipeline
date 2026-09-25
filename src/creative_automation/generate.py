"""Hero image generation — Bedrock Stability image-conditioning on real brand assets.

Precedence (see generate_hero): a real seed asset (theme photo, sku-mapped asset photo,
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

from PIL import Image, ImageDraw, ImageFont, ImageOps

from .platform_copy import clean_brand_copy

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
# TIME BUDGET: the Lambda timeout is 300s but the app calls through API Gateway
# (29s integration cap), so the 24s internal soft budget
# (NOT context.get_remaining_time_in_millis) is the real authority. Each rung
# checks remaining_ms() against its worst-case cost BEFORE starting and skips a
# rung that will not fit, so the ladder always reserves time to reach a
# real-pixel floor. time.monotonic (never time.time) so a wall-clock step never
# corrupts the deadline.
GENERATE_SOFT_BUDGET_MS = int(os.getenv("GENERATE_SOFT_BUDGET_MS", "24000"))
# Rung B (Bedrock stability-restyle) worst-case cost estimate: scene (7s) +
# stability (13s) worst case = 20s. B is attempted only if remaining_ms covers
# this AND the C reservation, so a slow Bedrock call can never starve the C
# recovery. Fits the 24s soft budget with the 2s C reservation held back.
_B_BUDGET_MS = int(os.getenv("GENERATE_B_BUDGET_MS", "20000"))
# Held-back reservation so rung C (pillow-compose, ~1-2s) can ALWAYS run after B, even
# when B burns its full budget. C is the guaranteed-real workhorse below B.
_C_RESERVATION_MS = int(os.getenv("GENERATE_C_RESERVATION_MS", "2000"))
# Generative-rung switch. Default ON preserves prod: every Stability call (rung B hero
# restyle, rung A packshot background restyle, 9x16/16x9 outpaint extends) runs as before.
# Dev opts out (KODIAK_ENABLE_STABILITY_RUNG=0) for faster, fully-deterministic turnaround:
# no Bedrock Stability invocations at all, every ratio renders via the Nova-Pro-art-directed
# Pillow path. Nova Pro (the art director — headline + scene prompt) still runs either way.
_STABILITY_RUNG_ON = os.getenv("KODIAK_ENABLE_STABILITY_RUNG", "1").strip().lower() not in ("0", "false", "no", "")
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
# Outpaint extend budget: the standalone mode:extend request bypasses the
# 22s ladder wall (it does one outpaint + upload inside the 30s gateway
# cap), so the 12s ladder read cap does NOT apply here. Measured 24h
# Bedrock p-average is 20.0s (max 20.5s) — 25s lets the model answer
# instead of degrading every tall/wide tile to a Pillow pad, with ~5s
# headroom for S3 download/upload + response under the gateway cap.
BEDROCK_OUTPAINT_READ_TIMEOUT_S = int(os.getenv("BEDROCK_OUTPAINT_READ_TIMEOUT_S", "25"))
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
# Stock-caption reservation (ms): the Nova Pro caption fallback is entered ONLY while
# remaining_ms() still covers its worst-case cost (the fail-fast read timeout) PLUS
# the rung-C reservation. PROVEN IN PROD 2026-09-08: an un-gated caption after a
# 12s director spend burns the silent seconds before rung C and the wall fires
# during finalize. On skip the headline falls to the raw brief (the documented
# third fallback) with a skip log, same as a caption that returns empty.
_CAPTION_BUDGET_MS = int(os.getenv("GENERATE_CAPTION_BUDGET_MS", "7000"))
_DIRECTOR_LIVE_SOURCE = "bedrock:kodiak-artdirector"
# Grounded-director concurrency (wall repair): the director voice (embed +
# up to two invokes, ~8s worst case) used to run SERIALLY inside _headline —
# after seed resolution, before rung B — so director + restyle alone exceeded
# the 22s wall on cold containers. _kick_director submits it once at ladder
# start; _headline collects with a budget-shaped wait (rich clock waits for a
# real headline, thin clock takes ~0 and falls to caption). Same leak-and-drain
# contract as the other bounded executors: an abandoned voice worker writes
# nothing shared. The per-container memo still makes repeat calls ~free.
_DIRECTOR_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=2)
# Caption overlap: rung B's Nova Pro caption needs only (seed + statics), the
# same inputs as the scene-prompt — so it is submitted at rung-B entry and
# collected after the restyle, overlapping scene + stability (~4-7s saved on a
# warm pass: the difference between landing in-wall and a second fallthrough).
# Leak-and-drain like the other pools: a thin-clock collect takes "" and the
# worker drains on its own read timeout, writing nothing shared.
_CAPTION_POOL = concurrent.futures.ThreadPoolExecutor(max_workers=1)
# Refusal guard: a live voice model can still decline (junk retrieved examples make
# refusal likely — PROVEN IN PROD 2026-09-08: hash-laden asset titles as in-voice
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
    "here's a",
    "requested",
    "headline options",
    "options:",
    "explanation:",
    # chatty-instruction-model openers/closers (Nova Micro narrates its work:
    # "Sure, here's a rephrased version…" … "This version captures the essence…").
    "sure,",
    "rephrased version",
    "captures the essence",
)


def _director_enabled() -> bool:
    """Kill-switch for the grounded-director headline path. OFF unless opted in.

    Requires BOTH flags: KODIAK_DIRECTOR_GROUNDED (legacy per-path switch,
    default true) AND KODIAK_ARTDIRECTOR_ENABLED (primary voice switch,
    default false). Cost incident 2026-09-23: flipping only the primary flag
    left this path live because it keyed off the legacy flag alone — every
    voice path must short-circuit on the one primary boolean.
    """
    grounded = os.getenv("KODIAK_DIRECTOR_GROUNDED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )
    primary = os.getenv("KODIAK_ARTDIRECTOR_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )
    return grounded and primary
# Restyled-background cache (asset prefix): the rung-A bg restyle costs ~10s of Bedrock,
# which fits a preview but never a full set (base + pads + uploads must clear the same
# 22s wall). The cache is content-addressed on (seed bytes + prompt inputs): a preview
# warms it, the set base reuses the SAME pixels — no second Bedrock call, wall holds,
# preview and pack stay consistent. Best-effort everywhere: any S3 failure degrades to
# the uncached behavior (fresh restyle when budget allows, else raw seed).
_RESTYLE_CACHE_PREFIX = "brands/kodiak/renders/restyle-cache/"
_RESTYLE_CACHE_BUCKET = os.getenv("ASSET_STORE_S3_BUCKET", "").strip() or os.getenv("DAM_S3_BUCKET", "").strip() or "chasko-creative-dam-946179428633-us-east-1"
# NOTE: the prefix MUST stay under brands/kodiak/renders/ — the GenerateLambda role grants
# PutObject/GetObject only on renders/* and library/* (generate-stack.ts). A top-level
# restyle-cache/ prefix is denied and the cache silently never warms.


def _restyle_cache_key(seed_bytes: bytes, product_name: str, brief_msg: str,
                        region: str, audience: str, theme: str | None,
                        dish: str | None = None, market: str | None = None,
                        season: str | None = None, seed_value: int | None = None) -> str:
    h = hashlib.sha256()
    h.update(seed_bytes)
    # Uniqueness fix 1: the Stability seed is a cache input — a restyle
    # generated under one per-request seed must never serve a request that
    # derived a different seed, or the seed fix would be a no-op on cache hit.
    for part in (product_name, brief_msg, region, audience, theme or "", dish or "",
                 market or "", season or "", "" if seed_value is None else str(seed_value)):
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
    except Exception:  # noqa: BLE001 — cache miss on ANY failure per contract
        return False


def _restyle_cache_put(key: str, src: Path) -> None:
    """Store a fresh restyle. Never raises — cache misses just cost a future restyle."""
    try:
        if boto3 is None:
            return
        s3 = boto3.client("s3")
        s3.put_object(Bucket=_RESTYLE_CACHE_BUCKET, Key=key,
                      Body=src.read_bytes(), ContentType="image/png")
    except Exception as e:  # noqa: BLE001 — cache write never breaks the render
        print(f"[generate] restyle cache put skipped: {e}", file=sys.stderr)


class _RungBBudgetSkip(Exception):
    """Internal sentinel: a per-subcall budget gate abandoned rung B for rung C.

    Not an error — carries no failure, only a control-flow signal so the two gates
    (scene-prompt, stability) share one clean fall-to-C path. fallthrough_reason is set
    to budget-exhausted at the raise site before this propagates.
    """


# Image engine: Bedrock Stability control-structure
# (us.stability.stable-image-control-structure-v1:0) — seed a real asset photo and the
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
# How strongly the seed composition constrains the restyle (0..1). 0.6 lets the
# painterly style head dominate the seed photo's texture (0.7 kept too much
# photographic gloss). Product identity is safe: the packshot composites via
# Pillow from the real asset, never from restyled pixels.
STABILITY_CONTROL_STRENGTH = float(os.getenv("BEDROCK_CONTROL_STRENGTH", "0.35"))
# Brief-aware jitter so the same market/product/brief doesn't produce pixel-identical
# oranges every time — small ±0.06 range on top of the 0.35 base, keyed by brief hash.
def _stable_hash_int(text: str, nbytes: int = 4) -> int:
    """Stable integer digest for deterministic mode. Builtin hash() is salted per
    process (PYTHONHASHSEED), so it must never back KODIAK_DETERMINISTIC."""
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:nbytes], "big")


def _control_for_brief(brief_msg: str | None) -> float:
    base = STABILITY_CONTROL_STRENGTH
    if os.getenv("KODIAK_DETERMINISTIC") == "1":
        h = _stable_hash_int(brief_msg or "", 1)
        jitter = (h / 255.0 - 0.5) * 0.12  # -0.06 .. +0.06 deterministic for tests
        return max(0.2, min(0.6, base + jitter))
    import random

    # Dynamic per-campaign: base jitter + small per-invocation random so same brief varies
    h = hash(brief_msg or "") & 0xFF
    base_jitter = (h / 255.0 - 0.5) * 0.12
    dyn_jitter = random.uniform(-0.03, 0.03)
    return max(0.2, min(0.6, base + base_jitter + dyn_jitter))
# Style sandwich (character-consistency pattern): frozen style head + varying subject
# + frozen detail tail. Nova (or the brief fallback) supplies ONLY the subject; the
# frozen ends keep every restyle/outpaint on-brand no matter what the subject says.
# Brand palette rendered as COLOR LANGUAGE, not hex — diffusion models read
# color words, not "#3B2316". Values traced to design/tokens/kodiak.json (single
# source, drift-guarded by tests/test_kodiak_parity.py) and the contrast direction
# in references/keep-it-wild/photography-direction.json ("cool rock + warm sunrise
# vs #3B2316/#E8530E/#1A3C34 accent"). "on-brand earthy palette" alone was inert —
# the model had no way to know what on-brand meant. Env-overridable like the other
# style knobs.
#   bear brown  #3B2316  deep roasted brown (warm base / shadow)
#   blaze orange #E8530E high-contrast accent (single hero accent, sparingly)
#   frontier green #1A3C34 evergreen / forest (cool balance)
#   box parchment #F5EAD3 warm cream (highlight / negative space)
# Wording note (2026-09-10, after a live render): describe the palette as a COLOR
# GRADE, not as scene objects. "forest-green" rendered a literal pine forest and
# "alpenglow / dawn light" rendered a large orange sunset sky — the model paints the
# noun. So: brown/cream is the DOMINANT grade, green is a muted UNDERTONE (not a
# forest), orange is a small ACCENT DETAIL (explicitly not the sky), light is warm
# neutral daylight (not a sunset).
KODIAK_PALETTE = os.getenv(
    "KODIAK_PALETTE",
    "warm natural daylight with soft cream and parchment highlights, gentle bear-brown "
    "shadows, and a single small warm amber highlight detail; muted, photographic and "
    "understated, no oversaturated color, no large green or brown flat color blocks, "
    "no camouflage pattern",
)
STYLE_HEAD = os.getenv(
    "KODIAK_STYLE_HEAD",
    # no brand token in the image prompt: the model renders any brand word it
    # sees as packaging glyphs and garbles it ("KODA CAKTS"). brand identity
    # ships via the composited real asset store packshot/logo (Pillow), never pixels.
    # Photographic editorial is the default: real light, real food, no painterly
    # flat color blocks or camo-like patches. Palette is light-biased.
    "Soft natural-light photographic editorial, documentary food photography, "
    "shallow depth of field, real kitchen and market setting, photographic detail, "
    f"{KODIAK_PALETTE}. Subject: ",
)
STYLE_TAIL = os.getenv(
    "KODIAK_STYLE_TAIL",
    # explicit anti-gibberish: control-structure preserves seed structure, so
    # text-shaped regions in the seed photo restyle into fake lettering unless
    # told otherwise. every surface blank and unmarked, no exceptions.
    ". Absolutely no text of any kind — no words, no letters, no numbers, no "
    "logos, no labels, no signage, no packaging copy, no readable or garbled "
    "lettering. All packaging, paper, tags, and surfaces blank and unmarked.",
)
# Brand tokens scrubbed out of every stability-bound prompt (proven 2026-09-10:
# the word in the prompt renders as hallucinated pack copy). Applied to the
# whole assembled prompt so subject, scene hints, and bear-law clause are covered.
_BRAND_SCRUB_RE = re.compile(r"(?i)(?:on-brand\s+)?\bkodiak(?:\s+cakes)?\b[\s-]*")
# Bear law (brand standard): bears are NEVER a frozen mascot — no friendly
# identical-every-render character, no cartoon/hand-drawn bears, no bear
# touching product/packaging/logo, no people with bears in a tame frame, no
# named bear. Three lawful treatments only: (1) logo/line-art raster pasted
# post-render, never model-drawn; (2) wildlife photoreal — distant unposed
# grizzly in wild Northern-Rockies-style habitat, human-free; (3) sign, not
# animal — tracks, trail, scratched bark, no bear in frame. The clause below
# is REQUEST-DRIVEN (wild-grizzly-bears theme or a bear-naming brief), never
# injected by default — everyday packs stay bear-free.
_BEAR_TRIGGER_THEMES = frozenset({"wild-grizzly-bears"})
_BEAR_WORD_RE = re.compile(r"\b(bears?|grizzl(y|ies)|cubs?|bruins?)\b", re.IGNORECASE)
# Palette language, not a bear request: "bear-brown timber/shadows" names the
# brand color, never the animal. Stripped before the bear-word check so style
# copy cannot summon a bear.
_BEAR_PALETTE_RE = re.compile(r"bear[-\s]brown", re.IGNORECASE)
_BEAR_LAW_CLAUSE = (
    "Bear direction (brand law): no mascot, no cartoon or hand-drawn bear, no "
    "bear touching product, packaging, or logo, no people with bears, no named "
    "bear character. Bear presence only as a distant unposed photoreal grizzly "
    "in wild Northern-Rockies-style habitat, human-free — otherwise bear sign "
    "only: tracks, trail, scratched bark, no bear animal in frame."
)


def _bear_law_clause(theme: str | None, brief_msg: str | None) -> str:
    """Brand-law bear direction, or "" when the request asks for no bear.

    Request-driven: the wild-grizzly-bears theme, or a brief naming bears,
    earns the constraint clause. Anything else renders bear-free — the model
    is never handed bear identity by default.
    """
    if (theme or "").strip() in _BEAR_TRIGGER_THEMES:
        return _BEAR_LAW_CLAUSE
    if brief_msg and _BEAR_WORD_RE.search(_BEAR_PALETTE_RE.sub("", brief_msg)):
        return _BEAR_LAW_CLAUSE
    return ""


# Seed discipline: derived seed = uniqueness (same brief re-renders vary by
# market + season + day); pinned seed = reproducibility (ops sets
# BEDROCK_STABILITY_SEED explicitly, or KODIAK_DETERMINISTIC=1 for tests).
# The variations button still passes seed per call via seed_value.
STABILITY_SEED = int(os.getenv("BEDROCK_STABILITY_SEED", "42"))
_STABILITY_SEED_PINNED = "BEDROCK_STABILITY_SEED" in os.environ


def _request_seed(brief_msg: str | None, market: str | None = None,
                  season: str | None = None, date_str: str | None = None) -> int:
    """Stability seed for one render request (uniqueness fix 1).

    sha256 over brief + market + season + day, so identical briefs in
    different markets, seasons, or days restyle to different pixels instead
    of near-identical images. KODIAK_DETERMINISTIC=1 (tests) and an explicit
    BEDROCK_STABILITY_SEED pin both return the constant STABILITY_SEED.
    date_str is "YYYY-MM-DD" (UTC today when omitted); pass it explicitly
    for reproducible per-day renders.
    """
    if os.getenv("KODIAK_DETERMINISTIC") == "1" or _STABILITY_SEED_PINNED:
        return STABILITY_SEED
    if not date_str:
        date_str = time.strftime("%Y-%m-%d", time.gmtime())
    parts = [brief_msg or "", market or "", season or "", date_str]
    return _stable_hash_int("\x00".join(parts), 4)


def _style_sandwich(subject: str) -> str:
    """Wrap a varying subject in the frozen style ends. Idempotent.

    Bear identity is NEVER injected here — the model draws no mascot, no
    character, no logo. Request-driven bear direction (brand law) arrives
    inside the subject itself via _bear_law_clause, upstream of this wrap.
    """
    subject = (subject or "").strip()
    if subject.startswith(STYLE_HEAD):
        assembled = subject
    else:
        assembled = f"{STYLE_HEAD}{subject}{STYLE_TAIL}"
    # brand scrub last: no brand word ever reaches the image model.
    scrubbed = _BRAND_SCRUB_RE.sub("", assembled)
    return re.sub(r"\s{2,}", " ", scrubbed).strip()
# Stability outpaint is invoked via its INFERENCE-PROFILE id (bare stability.* raises
# ValidationException). Confirmed ACTIVE + AUTHORIZED + AVAILABLE in us-east-1. Only the
# 9x16 and 16x9 ratios are DERIVED from the 1x1 control-structure hero via outpaint (two
# extend calls); 4x5 is a deterministic Pillow cover-pad, never an outpaint. Schema mirrors
# control-structure (Stability's
# {prompt, image, left/right/up/down, output_format} — NOT Nova's taskType).
STABILITY_OUTPAINT_MODEL = os.getenv(
    "BEDROCK_STABILITY_OUTPAINT_MODEL", "us.stability.stable-outpaint-v1:0"
)
# Stability seed constraint: total pixels 4096..9437184, each dim >= 64. A real
# 1024x1024 asset photo sits well inside the range; a seed below the floor in either
# dim is upscaled to 1024x1024 before invoke to avoid a ValidationException.
_STABILITY_MIN_DIM = 64
_STABILITY_UPSCALE_TO = 1024
_STABILITY_MAX_DIM = int(os.getenv("BEDROCK_STABILITY_SEED_MAX_SIDE", "1280"))
# us-west-2 needs an inference profile for Nova Pro; us-east-1 invokes directly.
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")

# Default brand hero: when a requested SKU has no asset of its own, we still owe the
# campaign a real, on-brand Kodiak composite — so we compose on the flagship product
# shot. The asset store ships real heroes at brands/kodiak/heroes/<product>/hero-real.png|hero.png
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
# mirrors campaign.py::_render_asset's asset-store:packshot-composite provenance so the live
# /generate endpoint reports the composite path the same way the batch pipeline does.
# See docs/architecture/compose-fix/compose-fix-spec.md precedence table (order a/b).
PACKSHOT_SOURCE = "asset-store:packshot-composite"

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
# kraft finalize, S3 uploads of all four ratios) after an outpaint attempt. Mirrors
# the rung-C reservation pattern. Sized 2026-09-08: a 12-19s stability extend plus
# ~3-4s of uploads/finalize cannot fit the immovable 22s wall after the director +
# caption spend, so the reserve keeps in-wall attempts to the rare case where one
# extend plus all uploads provably fit; otherwise the request ships the pillow pad
# and the extend story stays async (receipts under artifacts.async_extend).
_OUTPAINT_RESERVE_MS = int(os.getenv("GENERATE_OUTPAINT_RESERVE_MS", "6000"))
# Per-ratio headline slab size (C06: 56/64/72).
_HEADLINE_PX = {"1x1": 56, "9x16": 64, "16x9": 72, "4x5": 60}

# sku-photo-map: catalog handle -> best real lifestyle asset key (full key, NOT under
# the asset-library/ prefix). Loaded once; the file ships in the deployment (Lambda-safe).
# Default (repo-checkout) location. _resolve_map_path() picks the first candidate
# that actually exists at runtime — the install layout differs between local dev
# (parents[2] IS the repo root with data/) and the Lambda image (pip install .
# lands the module under site-packages, where parents[2]/data does not exist).
_SKU_PHOTO_MAP_PATH = Path(__file__).parents[2] / "data" / "products" / "sku-photo-map.json"
# theme-asset-map: theme-slug -> best real thematic asset key. Sibling of sku-photo-map,
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
# Currently empty (no named-person themes ship); the infrastructure stays so a
# future partner theme cannot regress into a filter trip.
_THEME_PERSONA_MAP: dict[str, str] = {
}

# Per-theme scene guidance for the Nova Pro control-structure restyle prompt. When a
# theme has an entry here, its vivid scene description is folded into the art-director
# prompt AND the deterministic fallback prompt so the restyle lands on-theme even with
# no live Nova Pro. Entries stay GENERIC — no real person's name or likeness. For the
# US Ski & Snowboard partner campaign this honors the real partnership (Milano Cortina
# 2026, Park City, Kodiak Kitchen at the USANA Center of Excellence) without naming or
# implying endorsement by any individual athlete.
# Shared frontier palette, spelled out anywhere a hint names it: bear-brown timber
# (#3B2316), frontier-green pine (#1A2F29), warm kraft paper (#C8A97E), cream
# whole-grain tones, low golden morning sun. Every hint below is a complete
# artist dispatch — setting, light, palette, material, composition — because a
# bare noun ("on-brand Kodiak") means nothing to the model. No text, letters,
# signage, or logos anywhere in frame: the model renders glyphs as gibberish.
_THEME_SCENE_HINT: dict[str, str] = {
    # unified wild angle: the KODIAK Bear + Keep It Wild conservation program are
    # one story — grizzly habitat, Vital Ground corridor, frontier morning.
    "wild-grizzly-bears": (
        "grizzly-country meadow at first light, pine ridgeline in frontier-green "
        "behind, low golden sun from frame left, bear-brown timber and kraft tones "
        "in the foreground, wildflower meadow leading to distant peaks, visible "
        "grain texture, Keep It Wild conservation mood, no bears in close-up, no text"
    ),
    "us-ski-snowboard": (
        "Wasatch alpine dawn above Park City, fresh-snow ridgeline and pine in "
        "frontier-green and white, cast-iron skillet with a protein stack steaming "
        "in the lower third, cold blue-shadow light warming to gold at the ridge, "
        "generic active winter athletes only with no faces and no real person, no text"
    ),
    # NOTE (retailer overlay wiring): retailer scene-hint entries were REMOVED
    # here on purpose. Retailer direction no longer steers the generated pixels
    # (aisle/pack cues risk baked pseudo-text and off-brand scenes); it ships as
    # the composited logo mark (costco/publix/target/walmart via the retailer
    # layer, asset store brands/retailers/logos/) + the copy-sidecar retailer-framing
    # line (_THEME_COPY_HINT, which keeps every retailer incl. copy-only
    # kroger/heb/whole-foods). Retailer themes fall through to the generic
    # persona/brief prompt below.
}

# Per-retailer copy framing (#245): appended to the copy sidecar (txt + csv) when
# the request theme names a retailer. The brand headline is never rewritten — the
# retailer direction ships as its own sidecar line, visible in the downloadable
# copy and echoed in the campaign panel via the brief's directions clause.
_THEME_COPY_HINT: dict[str, str] = {
    "localized-costco": "bulk Family Size value — warehouse-club aisle, stock-up trip",
    "localized-publix": "neighborhood warmth — southern family table",
    "localized-target": "everyday-family aisle — one-trip basket, modern everyday value",
    "kodiak-subscription": "subscription cadence — front-door delivery, pantry always stocked",
    "target": "everyday-family aisle — one-trip basket, modern everyday value",
    "walmart": "everyday low price pantry stock-up — family value",
    "whole-foods": "whole-ingredient shelf — ingredient-aware premium pantry",
    "publix": "neighborhood warmth — southern family table",
    "kroger": "family grocery run — fresh everyday value",
    "heb": "texas family table — bold local flavor value",
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


# Retired named-person slugs: no chip ships them, but a user can still TYPE the
# name into the brief — and that raw token trips the Stability filter the same
# way. Scrubbed to the same filter-safe persona so free text can never regress
# into a filter trip.
_RETIRED_PERSONA_MAP: dict[str, str] = {
    "zac-efron": "energetic athletic young man, morning-fitness lifestyle vibe",
}


def _safe_prompt_text(prompt: str) -> str:
    """Strip real celebrity names out of a free-text incoming prompt.

    The frontend builds the prompt client-side and a user can type a real
    person's display name (e.g. "Zac Efron") verbatim. That name reaches
    Stability via brief_msg and trips the content filter
    (finish_reasons:["Filter reason: prompt"]). For every named-person slug in
    _THEME_PERSONA_MAP plus _RETIRED_PERSONA_MAP, replace the display name
    ("Zac Efron") and the spaced-slug form ("zac efron") with the filter-safe
    persona text, matching case-insensitively. Ordinary prompts with no named
    person pass through unchanged.
    """
    out = prompt
    for slug, persona in {**_THEME_PERSONA_MAP, **_RETIRED_PERSONA_MAP}.items():
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
    except (KeyError, TypeError, AttributeError, IndexError) as e:
        print(f"[generate] token semantic colors unreadable, keeping defaults: {e}", file=sys.stderr)
except Exception:  # noqa: BLE001 — import-time palette fallback; module must import offline
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
_SKU_PHOTO_MAP_CACHE: dict | None = None


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


def _resolve_asset_photo(product_id: str) -> str | None:
    """Return the best real lifestyle asset key for a catalog handle, else None.

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
_THEME_ASSET_MAP_CACHE: dict | None = None


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


def _resolve_theme_photo(theme_slug: str) -> str | None:
    """Return the best real thematic asset key for a theme slug, else None.

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


# Panel flag raised when a request names a theme the map cannot honor.
PANEL_FLAG_THEME_MISMATCH = "theme-mismatch"


def _normalize_theme_slugs(themes) -> list[str]:
    """Normalize a themes input (list/tuple or comma-separated string) to slugs."""
    if themes is None:
        return []
    if isinstance(themes, str):
        raw = themes.split(",")
    else:
        try:
            raw = list(themes)
        except TypeError:
            return []
    out: list[str] = []
    for item in raw:
        slug = str(item or "").strip().lower()
        if slug and slug not in out:
            out.append(slug)
    return out


# Theme slugs whose direction ships as a logo-mark overlay + copy line, never as
# pixel-prompt scene text (retailer-aisle decision 2026-09-20).
_OVERLAY_MARK_THEMES: frozenset[str] = frozenset({
    "localized-costco", "localized-publix", "localized-target",
    "target", "walmart", "whole-foods", "publix", "kroger", "heb",
    "kodiak-subscription",
})


def combine_themes(themes) -> dict:
    """Multi-theme combination rule (deterministic, offline).

    One primary theme drives seed + scene: the FIRST requested slug that
    resolves in the theme-asset-map. Every other KNOWN slug maps to an
    overlay layer (its scene hint folded into the scene prompt) plus a copy
    line (its copy framing folded into the copy sidecar). UNKNOWN slugs map
    to nothing renderable — they raise a panel flag on the mismatch path
    (provenance["panel_flag"]) instead of raising or silently dropping.

    Returns {"themes", "primary", "extras", "overlay_layers", "copy_lines",
    "unknown", "panel_flag"} — panel_flag is None when every slug resolved.
    """
    slugs = _normalize_theme_slugs(themes)
    known = [s for s in slugs if _load_theme_asset_map().get(s) is not None]
    unknown = [s for s in slugs if s not in known]
    primary = known[0] if known else None
    extras = known[1:]
    overlay_layers = []
    for slug in extras:
        # Retailer/mark themes never steer pixels — their direction ships as a
        # logo-mark overlay layer + copy-sidecar framing line, never scene text.
        if slug in _OVERLAY_MARK_THEMES:
            overlay_layers.append({"theme": slug, "scene": "", "mark": True})
            continue
        hint = _THEME_SCENE_HINT.get(slug, "")
        overlay_layers.append(
            {"theme": slug, "scene": hint or _safe_theme_text(slug)}
        )
    copy_lines = []
    for slug in extras:
        framing = _THEME_COPY_HINT.get(slug)
        copy_lines.append(
            {"theme": slug, "framing": framing or f"theme direction: {_safe_theme_text(slug)}"}
        )
    panel_flag = (
        f"{PANEL_FLAG_THEME_MISMATCH}: unknown theme(s): {', '.join(unknown)}"
        if unknown
        else None
    )
    return {
        "themes": slugs,
        "primary": primary,
        "extras": extras,
        "overlay_layers": overlay_layers,
        "copy_lines": copy_lines,
        "unknown": unknown,
        "panel_flag": panel_flag,
    }


def _combo_scene_suffix(combo: dict | None) -> str:
    """Scene-prompt suffix layering the combo extras over the primary scene."""
    if not combo:
        return ""
    parts = []
    for layer in combo.get("overlay_layers", []) or []:
        # mark-only layers carry no scene text — their direction ships via the
        # logo overlay + copy sidecar, never the pixel prompt.
        if not (layer.get("scene") or "").strip():
            continue
        parts.append(f"Also layering {layer['theme']}: {layer['scene']}.")
    return (" " + " ".join(parts)) if parts else ""


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
    except OSError:
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
    except OSError:
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

    The real probe fns (_find_source_asset, asset_store.resolve_packshot) accept deadline_ms so
    the fan-out can bail mid-loop. Test stubs and older signatures may not — fall back to
    the bare call so threading the deadline never breaks a monkeypatched path.
    """
    try:
        return fn(*args, deadline_ms=deadline_ms)
    except TypeError:
        return fn(*args)


def _find_source_asset(product_id: str, product_name: str, deadline_ms=None) -> Path | None:
    """Locate a real source image for the product.

    Order: input_assets/<product_id>/hero-real.png, then hero.png, then any image
    in that product dir, then a name-matching glob across the asset roots, then an
    S3 asset store fallback (fetch_hero_to_tmp) for Lambda where no assets are baked in.

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

    # 3) S3 asset store fallback — the Lambda container ships with NO assets baked in, so
    # the real heroes live only in S3 (s3://<asset store bucket>/brands/kodiak/heroes/
    # <product>/hero-real.png|hero.png). Materialize into /tmp (Lambda's only
    # writable path) and return the local copy so the existing Nova Pro compose
    # flow runs on the real asset. Offline-safe: fetch_hero_to_tmp returns None
    # when S3 is disabled / boto3 missing / key absent, so local dev and CI keep
    # falling through to mock without raising.
    try:
        from .asset_store import fetch_hero_to_tmp  # local import — keeps offline path import-light

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
) -> str | None:
    """Ask Nova Pro (Converse) for a short on-brand caption + layout hint. None on failure."""
    if boto3 is None:
        return None
    try:
        img_bytes, fmt = _seed_small_for_nova(src)
    except (OSError, ValueError):
        return None
    try:
        client = _bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
        prompt = (
            f"You are an ad art director. Product: '{product_name}'. Region: {region}. "
            f"Audience: {audience}. Campaign vibe: {brief_msg}. "
            "Look at the product image and reply with ONE short on-brand headline "
            "(max 6 words) on the first line, then one line 'LAYOUT: <left|right|center>' "
            "naming which side to leave as negative space for the product. No other text. "
            "Brand law: never write the bare words KODIAK or Kodiak — the only allowed "
            "brand namings are 'Kodiak Cakes' and 'Kodiak Park City'. Never use military, "
            "recruitment, or 'LISTEN UP' language — warm agricultural frontier marketplace "
            "vibe only. Headline must be warm and inviting, not commanding."
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


def _caption_with_budget(src, product_name, brief_msg, region, audience, remaining_ms=None) -> str:
    """Stock Nova caption behind the wall clock, with start/done latency logs.

    Entered ONLY while remaining_ms() still covers the caption's worst-case cost
    (_CAPTION_BUDGET_MS) PLUS the rung-C reservation, so a slow caption can never
    starve rung C. remaining_ms None = no clock (tests/offline) -> always attempt.
    Returns "" on skip or failure so callers fall through to the raw brief.
    """
    if remaining_ms is not None and remaining_ms() < _CAPTION_BUDGET_MS + _C_RESERVATION_MS:
        print(
            f"[generate] nova caption skipped (budget {remaining_ms():.0f}ms < "
            f"{_CAPTION_BUDGET_MS + _C_RESERVATION_MS}ms) -> brief fallback",
            file=sys.stderr,
        )
        return ""
    _t0 = time.monotonic()
    caption = _nova_pro_caption(src, product_name, brief_msg, region, audience) or ""
    _dt = (time.monotonic() - _t0) * 1000.0
    print(
        f"[generate] nova caption {'ok' if caption else 'empty'} latency={_dt:.0f}ms",
        file=sys.stderr,
    )
    return caption


def _brief_setting_clause(brief_msg: str | None) -> str:
    """Compact setting directive parsed from the brief's curated markers.

    The frontend brief carries ecology:/frontier:/in-season: segments from the
    pair data (never fabricated). The full brief is too noisy to survive Nova's
    40-word compression, so this distills the place + seasonal feature into one
    clause any market can use — Manhattan/October resolves exactly like the
    original Cincinnati/September case did, instead of needing a per-market
    special case. Returns '' when the brief carries no markers.
    """
    if not brief_msg:
        return ""
    ecology = frontier = seasonal = ""
    for seg in str(brief_msg).replace("◇", "·").split("·"):
        low = seg.strip().lower()
        if low.startswith("ecology:") and not ecology:
            ecology = seg.strip()[len("ecology:"):].strip()
        elif low.startswith("frontier:") and not frontier:
            frontier = seg.strip()[len("frontier:"):].strip()
        elif low.startswith("in-season:") and not seasonal:
            seasonal = seg.strip()[len("in-season:"):].strip().rstrip(".")
    bits = []
    place = frontier or ecology
    if place:
        bits.append(f"Setting: {place}.")
    if seasonal:
        bits.append(f"Seasonal feature: {seasonal}.")
    elif ecology and frontier:
        bits.append(f"Local touch: {ecology}.")
    return " ".join(bits)


#: Brief segments that are pipeline metadata, never the user's idea.
_IDEA_MARKERS = (
    "market:", "season:", "month:", "ecology:", "frontier:", "in-season:",
    "products:", "product:", "directions:", "direction:", "audience:",
    "region:", "retailer:", "recipe:",
)


def _brief_idea(brief_msg: str | None) -> str:
    """Distill the user's free-text campaign idea from the brief.

    The frontend brief is idea-first plus a curated suffix (market:/season:/
    ecology:/frontier:/in-season:/products: ...). Only the free text is the
    idea — "sea otters" must survive as a subject even though no photo pool
    tag will ever match it. Returns '' when the brief carries no free text.
    """
    if not brief_msg:
        return ""
    text = str(brief_msg).replace("◇", "·").replace("—", "·").replace("–", "·")
    # Parenthetical marker payloads ("wild mornings (frontier: Lebanon, OH -
    # US-OH-CINCINNATI market, september picks)") are metadata, not idea —
    # strip paren groups carrying a colon; plain parens ("pancakes (fluffy)")
    # stay part of the idea.
    text = re.sub(r"\([^()]*:[^()]*\)", "", text)
    bits = []
    for seg in text.split("·"):
        s = seg.strip().strip(",;").strip()
        if not s:
            continue
        if s.lower().split(":", 1)[0].strip() + ":" in _IDEA_MARKERS and ":" in s:
            continue
        bits.append(s)
    idea = " ".join(bits).strip()
    return idea[:80]


#: Idea tokens too generic to steer a seed pick.
_IDEA_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "of", "for", "with", "on", "in", "to",
    "my", "our", "your", "its", "this", "that", "with", "from", "with",
    "morning", "mornings", "day", "campaign", "idea", "photo", "image",
    "please", "make", "show", "with",
})


def _idea_tokens(idea: str) -> set[str]:
    """Content words of the idea for pool matching."""
    return {
        w for w in re.findall(r"[a-z0-9]+", (idea or "").lower())
        if w not in _IDEA_STOPWORDS and len(w) > 2
    }


def _brief_seed_pick(idea: str, candidates: list[tuple[str, str]]) -> str | None:
    """Pick the pool key whose caption/keystem best matches the idea.

    candidates are (key, caption-text) pairs. Score is shared content-word
    overlap; winner needs at least one shared word, ties break to first
    listed (pool order stays the authority). Returns None on no overlap so
    the caller keeps its existing pick — never worse than before.
    """
    toks = _idea_tokens(idea)
    if not toks or not candidates:
        return None
    best: str | None = None
    best_score = 0
    for key, caption in candidates:
        words = set(re.findall(r"[a-z0-9]+", f"{key} {caption or ''}".lower()))
        score = len(toks & words)
        if score > best_score:
            best, best_score = key, score
    return best


def _blend_idea_base(base: str, brief_msg: str | None) -> str:
    """Lead a copy base with the brief's free-text idea.

    The image caption knows the seed, not the idea — without the lead,
    platform posts and localizations carry only the market template.
    Skipped when the base already names the idea; capped at 80 chars like
    every other base.
    """
    idea = _brief_idea(brief_msg)
    if idea and idea.lower() not in (base or "").lower():
        return f"{idea} — {base or ''}"[:80]
    return base


def _staged_dest(seed_key: str) -> Path:
    """Unique /tmp dest for a staged seed key.

    Key-hashed, never bare-basename: see the collision note at the staged
    fetch call site.
    """
    import hashlib as _hashlib

    tag = _hashlib.sha1(str(seed_key).encode()).hexdigest()[:12]
    return Path("/tmp/kodiak-assets/staged") / f"{tag}-{Path(seed_key).name}"


# Marker for idea-composed photo seeds (Stable Image Core text-to-image).
# A seed carrying this marker already IS the campaign idea in pixels — the
# control-structure restyle must not touch it (seen live: a christmas-cats
# scenic restyled into a bear, then into a bare food table). It rides
# verbatim straight to compose; bg_source records the truth.
_SCENIC_SEED_MARKER = "/scenic-bg/"


def _is_scenic_seed(seed_key: str | None) -> bool:
    """True when the staged key names an idea-composed scenic background."""
    return bool(seed_key) and _SCENIC_SEED_MARKER in str(seed_key)


def _brief_subject_clause(brief_msg: str | None) -> str:
    """MUST-keep clause for the campaign subject (the idea, not the setting).

    The setting clause keeps place/season; this keeps the WHAT — without it
    Nova compresses "sea otters" out of the 40-word scene and the restyle
    just repaints the seed. Sanitized so adversary tokens never reach pixels.
    """
    idea = _brief_idea(brief_msg)
    if not idea:
        return ""
    safe = _safe_prompt_text(idea) if idea else ""
    if not safe:
        return ""
    return f" You MUST feature the campaign subject: {safe}."


def _default_scene_prompt(
    product_name: str, brief_msg: str, region: str, audience: str, theme: str | None,
    extra_themes: list[str] | None = None, dish: str | None = None,
    market: str | None = None, season: str | None = None,
) -> str:
    """Deterministic restyle direction for a photo seed — no network.

    Used as the Nova scene-prompt fallback AND as the whole scene-prompt step
    for theme-photo seeds (the photo already carries the theme, so a second
    vision call buys nothing and burns rung C's budget). Combo extras
    (extra_themes) fold in as overlay layers behind the primary theme scene.

    Frontier-aware: brief_msg now carries the rich autocomplete suffix
    (frontier: Lebanon, OH — Pawpaw season (Sep) · in-season: pawpaws
    (pawpaw, tropical custard) · market: Cincinnati...). That suffix is the
    in-season ingredient + favorite_flavors + frontier place that makes
    Cincinnati September look nothing like Halloween apples/cider — without
    it every preview collapses to the same generic pumpkin-patch background
    and [Image #1][2][3] repeat. We keep brief_msg verbatim so the frontier
    context threads to Stability even when Nova is down.
    """
    scene_hint = _THEME_SCENE_HINT.get(theme or "", "")
    # Who + where: the filter-safe persona names the person (never the raw
    # celebrity token), the hint dispatches the scene. Theme without a hint
    # falls back to the persona alone; no theme falls back to the brief.
    # Frontier/ingredient note: brief_msg is already frontier-aware (see
    # autocomplete.js buildSuffix), so direction preserves it.
    if theme:
        who = _safe_theme_text(theme)
        hint = f"{scene_hint} Featuring {who}." if scene_hint else who
        # Keep frontier ecology + ingredient even when themed — themed previews
        # otherwise lose the locality that makes September pawpaws ≠ Halloween.
        # Scrub free-text celebrity names so a typed "Zac Efron" never reaches
        # Stability (test_path_adversary).
        safe_brief = _safe_prompt_text(brief_msg) if brief_msg else ""
        direction = f"{hint} Campaign vibe: {safe_brief}." if safe_brief else hint
    else:
        direction = brief_msg
        # Locality survives Nova truncation: distill the brief's curated
        # ecology/frontier/in-season markers into a compact setting clause for
        # ANY market (Manhattan/October included), not just Cincinnati.
        setting = _brief_setting_clause(brief_msg)
        if setting and setting.lower() not in str(direction or "").lower():
            direction = f"{direction} {setting}"
        # Subject survives too: the free-text idea is the WHAT the user asked
        # for — without the MUST clause the restyle just repaints the seed.
        subject = _brief_subject_clause(brief_msg)
        if subject and subject.lower() not in str(direction or "").lower():
            direction = f"{direction} {subject}"
    if dish and str(dish).strip() and str(dish).strip().lower() not in str(direction or "").lower():
        # The campaign recipe names the dish — without it the restyle keeps the
        # seed's generic composition and the image disconnects from the recipe.
        direction = f"{direction} Featuring a serving of {str(dish).strip()}."
    direction = _with_locale_and_bear(
        direction, theme, brief_msg, market, season,
    )
    base = (
        f"{product_name} product photo restyled for "
        f"{direction}, "
        f"{region} {audience}, frontier morning light, natural grain texture, high detail, lifestyle and natural world visible"
    ).strip()
    if extra_themes:
        combo = combine_themes([theme or "", *(extra_themes or [])])
        base += _combo_scene_suffix(combo)
    return base


_MONTH_NUM = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _season_month(season: str | None) -> int | None:
    """Month number for a season string (month names only, never fabricated).

    Returns None for anything that is not a plain month name — the caller
    then emits the place without produce rather than guessing a month.
    """
    if not season:
        return None
    return _MONTH_NUM.get(str(season).strip().lower())


def _market_scene_clause(market: str | None, season: str | None) -> str:
    """Human market clause for scene prompts — never a raw market code.

    Resolves the market code through local_flavor_for: human place + the
    season month's in-season produce + sourcing. Unknown markets, missing
    data, or unparseable seasons yield '' so the caller emits NO market
    clause instead of a raw code (a raw code teaches the image model
    nothing and reads as a zip-code bug in provenance).
    """
    code = str(market or "").strip()
    if not code:
        return ""
    try:
        from .local_flavor import local_flavor_for

        # Install-layout-proof data path: local_flavor anchors at
        # parents[2]/data (repo checkout) which does NOT exist under the
        # Lambda site-packages install — resolve via _datapaths (CAP_DATA_ROOT
        # in the image) so the clause works in both layouts.
        try:
            from ._datapaths import data_path

            candidate = data_path("localization", "local-flavor.json")
            flavor_path = str(candidate) if candidate.exists() else None
        except Exception:  # noqa: BLE001 — resolver failure degrades to default
            flavor_path = None
        info = local_flavor_for(code, _season_month(season), path=flavor_path)
        if not info.get("matched"):
            return ""
        place = str(info.get("place") or "").strip()
        if not place:
            return ""
        produce = [str(p).strip() for p in (info.get("produce") or []) if str(p).strip()][:2]
        source = str(info.get("source") or "").strip()
        month_name = str(season).strip() if _season_month(season) else ""
        head = f"Setting: {place}" + (f" in {month_name}" if month_name else "")
        tail_bits = []
        if produce:
            tail_bits.append(f"{' and '.join(produce)} in season")
        if source:
            tail_bits.append(f"at {source}")
        if tail_bits:
            return head + " — " + ", ".join(tail_bits) + "."
        return head + "."
    except Exception:  # noqa: BLE001 — market lore never breaks the preview
        return ""


def _with_locale_and_bear(direction: str | None, theme: str | None,
                          brief_msg: str | None, market: str | None,
                          season: str | None) -> str:
    """Append market/season locality + request-driven bear law to a scene
    direction, each only when absent already (the frontier autocomplete
    suffix often carries both — never duplicate). Shared by the deterministic
    default AND the live-Nova post-process so Nova's 40-word compression can
    never silently drop locality or the bear constraint."""
    # Locality the brief suffix may not carry: two markets ordering the same
    # dish must not get the same scene prompt. The market arrives as a raw
    # code — resolve it to human place + produce, never emit the code.
    clause = _market_scene_clause(market, season)
    if clause and clause.lower() not in str(direction or "").lower():
        direction = f"{direction} {clause}"
    if season and str(season).strip() and str(season).strip().lower() not in str(direction or "").lower():
        direction = f"{direction} {str(season).strip()}."
    # Request-driven bear law: the wild-grizzly-bears theme or a bear-naming
    # brief earns the constraint clause; everything else stays bear-free.
    bear_clause = _bear_law_clause(theme, brief_msg)
    if bear_clause and bear_clause.lower() not in str(direction or "").lower():
        direction = f"{direction} {bear_clause}"
    return str(direction or "")


# ---- scenic background (text-to-image hero path).
# Control-structure restyle preserves its seed's composition, so an idea with
# no matching pool photo ("sea otters") can never reach pixels through it.
# Stable Image Core (text-to-image, same grant recipe art already uses)
# composes the scene from words instead. The scenic image becomes a photo
# seed like any other: uploaded to the asset store, then re-requested through
# the staged-seed path, so no composite machinery changes. Product identity
# stays safe — the box is still pasted verbatim by compose_creative.
_SCENIC_MODEL_ID = os.getenv(
    "KODIAK_SCENIC_MODEL", "stability.stable-image-core-v1:1"
)
_SCENIC_REGION = os.getenv("KODIAK_SCENIC_REGION", "us-west-2")
_SCENIC_READ_TIMEOUT_S = int(os.getenv("KODIAK_SCENIC_READ_TIMEOUT_S", "120"))
_SCENIC_NEGATIVE = (
    "text, letters, numbers, signage, labels, watermark, logo, "
    "blurry, deformed, cartoon"
)


def _scenic_scene_text(
    brief_msg: str | None, market: str | None = None,
    season: str | None = None, dish: str | None = None,
) -> str:
    """Photographic text-to-image prompt for the idea.

    Idea first (the WHAT), then the setting clause (the WHERE/when), then a
    photographic tail — Core renders photos, not ink sketches, so no line-art
    directive. Sanitized: adversary tokens never reach the model.
    """
    idea = _brief_idea(brief_msg)
    setting = _brief_setting_clause(brief_msg)
    market_clause = _market_scene_clause(market, season)
    bits = []
    if idea:
        bits.append(_safe_prompt_text(idea) or idea)
    if setting and setting.lower() not in " ".join(bits).lower():
        bits.append(setting)
    if market_clause and market_clause.lower() not in " ".join(bits).lower():
        bits.append(market_clause)
    if dish and str(dish).strip():
        bits.append(f"a serving of {str(dish).strip()} nearby")
    scene = " ".join(bits).strip()
    if not scene:
        return ""
    return (
        f"Photorealistic advertising photograph: {scene}. "
        "golden natural light, rich color, sharp focus, high detail"
    )


def _scenic_background(
    scene: str, out_path: Path, request_seed: int = 0,
) -> Path | None:
    """Render one photographic scenic background via Stable Image Core.

    Returns the saved PNG path, or None when there are no creds, the model
    errors, the content filter blocks, or the read times out. Never raises —
    every failure degrades to the caller's existing no-seed path.
    """
    if not scene or not str(scene).strip():
        return None
    try:
        from .spin import _bedrock_client
    except ImportError:
        return None
    try:
        client = _bedrock_client(
            "bedrock-runtime",
            read_timeout=_SCENIC_READ_TIMEOUT_S,
            region=_SCENIC_REGION,
        )
    except Exception:
        return None
    if client is None:
        return None
    import base64 as _b64
    import io as _io
    import json as _json

    body = {
        "prompt": str(scene)[:1200],
        "negative_prompt": _SCENIC_NEGATIVE,
        "aspect_ratio": "1:1",
        "output_format": "png",
        "seed": int(request_seed or 0),
    }
    try:
        resp = client.invoke_model(modelId=_SCENIC_MODEL_ID, body=_json.dumps(body))
        payload = _json.loads(resp["body"].read())
        finish = payload.get("finish_reasons") or [None]
        if finish[0] is not None:
            print(
                f"[generate] scenic-bg blocked: finish_reason={finish[0]!r}",
                file=sys.stderr,
            )
            return None
        img = Image.open(_io.BytesIO(_b64.b64decode(payload["images"][0]))).convert("RGB")
    except Exception as e:  # noqa: BLE001 — degrade to no-seed path
        print(f"[generate] scenic-bg invoke failed: {e}", file=sys.stderr)
        return None
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(out_path, "PNG")
        return out_path
    except (OSError, ValueError):
        return None


def _nova_pro_scene_prompt(
    src: Path, product_name: str, brief_msg: str, region: str, audience: str, theme: str | None,
    extra_themes: list[str] | None = None, dish: str | None = None,
    market: str | None = None, season: str | None = None,
) -> str:
    """Ask Nova Pro (Converse) for the control-structure restyle prompt.

    This is the art-director directing the IMAGE restyle (distinct from the headline
    caption). Returns a scene/theme description string that drives Stability's
    control-structure conditioning. Falls back to a deterministic brief/theme-derived
    prompt on any Nova Pro failure so the Stability call always has a usable prompt.
    Combo extras fold in as overlay layers behind the primary theme scene.
    """
    theme_hint = f" Theme: {_safe_theme_text(theme)}." if theme else ""
    scene_hint = _THEME_SCENE_HINT.get(theme or "", "")
    if scene_hint:
        theme_hint += f" Scene direction: {scene_hint}."
    if extra_themes:
        combo = combine_themes([theme or "", *(extra_themes or [])])
        theme_hint += _combo_scene_suffix(combo)
    default_prompt = _default_scene_prompt(product_name, brief_msg, region, audience, theme, extra_themes, dish, market, season)
    if boto3 is None:
        return default_prompt
    try:
        img_bytes, fmt = _seed_small_for_nova(src)
    except (OSError, ValueError):
        return default_prompt
    try:
        client = _bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
        # Locality + dish survive the 40-word compression: the brief's curated
        # place/season markers are restated as hard requirements, and the
        # campaign dish is named so the pixels match the paired recipe.
        keep_clause = ""
        setting = _brief_setting_clause(brief_msg)
        if setting:
            keep_clause += f" You MUST keep this setting: {setting}"
        keep_clause += _brief_subject_clause(brief_msg)
        clean_dish = str(dish or "").strip()
        if clean_dish:
            keep_clause += f" The image MUST show a serving of {clean_dish}."
        locale_ask = ""
        market_clause = _market_scene_clause(market, season)
        if market_clause:
            locale_ask += f" {market_clause}"
        elif season and str(season).strip():
            # Unresolvable market: name the season, never the raw code.
            locale_ask += f" Season: {str(season).strip()}."
        bear_ask = _bear_law_clause(theme, brief_msg)
        if bear_ask:
            locale_ask += f" {bear_ask}"
        prompt = (
            f"You are an ad art director directing an image restyle. Product: "
            f"'{product_name}'. Region: {region}. Audience: {audience}.{locale_ask} Campaign vibe: "
            f"{brief_msg}.{theme_hint}{keep_clause} Look at the product image, which must keep its "
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
        if not text:
            return default_prompt
        # Nova's 40-word compression drops the idea even when instructed (seen
        # live: "christmas cats" in the prompt, no cats in the scene), so
        # re-attach the subject deterministically (absent-only, never dup) —
        # same pattern as the locale/bear re-attach below.
        _idea_text = _brief_idea(brief_msg)
        if _idea_text:
            _safe_idea = _safe_prompt_text(_idea_text)
            if _safe_idea and _safe_idea.lower() not in text.lower():
                text = f"{text} Featuring {_safe_idea}."
        # Nova's 40-word compression drops locality and constraints: re-attach
        # market/season + bear law deterministically (absent-only, never dup).
        return _with_locale_and_bear(text, theme, brief_msg, market, season)
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


# ------------------------------------------------------- similarity gate (B -> C)
# dHash-64 gate on rung B: a control-structure restyle preserves the seed's
# composition, so the Hamming distance between the seed and the pre-overlay restyle
# is small for a healthy restyle and large when the model drifted (wrong scene,
# dropped product, noise). When the distance exceeds the threshold the B pixels are
# rejected and the ladder falls to rung C (guaranteed-real Pillow compose) with
# fallthrough_reason="similarity-gate" — same never-503 contract as every other B
# failure, one more named reason. The comparison runs on the PRE-OVERLAY restyle:
# the message bar alone shifts dHash by ~12, so a post-overlay read would
# false-reject every good B. Pillow-only, no numpy, ~ms on 1080px frames.
# Calibrated 2026-09-20 on staged renders (input_assets/power-cakes/hero.png):
# identical 0, scrim/compose-like + mild-restyle proxies 0-1, message-barred 12-13,
# different-photo / solid-canvas / noise 30-34. Threshold 8 sits in the clean gap.
# Two-mode gate (uniqueness dial, not decorative):
# - preserve (no seasonal/theme divergence requested): a restyle that lands far
#   from the seed drifted (wrong scene, dropped product, noise) — reject past
#   the threshold and fall to rung C, as originally calibrated.
# - diverge (season + holiday + theme requested a different scene): a restyle
#   that lands ON the seed ignored the direction — the model echoed the photo
#   and uniqueness failed. Below KODIAK_MIN_DIVERGENCE the ladder retries once
#   with the next seed + lighter control (budget permitting), then accepts.
# A single threshold cannot serve both modes: seasonal restyles (Halloween
# cider, September pawpaws) legitimately score 30+ while a plain restyle that
# scores 30+ is drift. The mode comes from the request (theme/season), never
# from the pixels.
SIMILARITY_GATE_THRESHOLD = int(os.getenv("KODIAK_SIMILARITY_THRESHOLD", "8"))
KODIAK_MIN_DIVERGENCE = int(os.getenv("KODIAK_MIN_DIVERGENCE", "2"))


def _diverge_requested(theme: str | None, season: str | None) -> bool:
    """True when the request asked for a different scene than the seed photo."""
    return bool((theme or "").strip() or (season or "").strip())


def _similarity_gate_decision(sim_dist: int, diverge: bool) -> str:
    """Gate verdict for a seed-vs-restyle dHash distance: "pass",
    "reject-drift" (preserve mode, too far — fall to rung C), or "retry"
    (diverge mode, too close — one budgeted retry with a varied seed)."""
    if diverge:
        return "retry" if sim_dist < KODIAK_MIN_DIVERGENCE else "pass"
    return "reject-drift" if sim_dist > SIMILARITY_GATE_THRESHOLD else "pass"


def _similarity_gate_enabled() -> bool:
    """Kill-switch for the dHash B-to-C gate. ON unless opted out (no redeploy)."""
    return os.getenv("KODIAK_SIMILARITY_GATE", "1").strip().lower() in (
        "1", "true", "yes", "on",
    )


def dhash64(src: Path | Image.Image) -> int:
    """Classic 64-bit difference hash: 9x8 gray, horizontal neighbor bits."""
    img = Image.open(src).convert("L") if isinstance(src, Path) else src.convert("L")
    small = img.resize((9, 8), Image.BICUBIC)
    px = list(small.tobytes())
    h = 0
    for r in range(8):
        for c in range(8):
            h = (h << 1) | (1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0)
    return h


def hamming_distance(a: int, b: int) -> int:
    """Hamming distance between two dHash ints (0..64)."""
    return bin(a ^ b).count("1")


def _similarity_distance(seed: Path, candidate: Path) -> int | None:
    """dHash-64 distance seed-vs-candidate. None when either image is unreadable."""
    try:
        return hamming_distance(dhash64(seed), dhash64(candidate))
    except (OSError, ValueError) as e:
        print(f"[generate] similarity hash skipped (unreadable image): {e}", file=sys.stderr)
        return None


def _scene_prompt_source(scene_prompt: str, product_name: str, brief_msg: str,
                         region: str, audience: str, theme: str | None,
                         dish: str | None = None, market: str | None = None,
                         season: str | None = None) -> str:
    """Name which branch wrote a rung scene prompt: live Nova vs deterministic default.

    _nova_pro_scene_prompt degrades to the deterministic default on ANY Nova failure,
    so equality with the default is the honest discriminator on both branches — no
    new plumbing through the Converse call, and the theme-photo fast path (which never
    calls Nova) classifies as default through the same comparison.
    """
    default = _default_scene_prompt(product_name, brief_msg, region, audience, theme, None, dish, market, season)
    return "default" if (scene_prompt or "") == default else "nova"

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


def _stability_control_hero(
    seed: Path,
    prompt: str,
    out_path: Path,
    *,
    control_strength: float | None = None,
    seed_value: int | None = None,
    retry_once: bool = True,
) -> Path | None:
    """Restyle the seed photo to the theme via Bedrock Stability control-structure.

    Invokes the us.stability.stable-image-control-structure-v1:0 inference profile with
    Stability's schema ({prompt, image, control_strength, output_format}) — NOT Nova's
    taskType schema. Decodes images[0] (base64 PNG) and writes it to out_path. Returns
    the path on success, None on any failure.

    control_strength and seed_value are optional overrides for parameter sweeps (see
    param_sweep.py). When None they fall back to the module defaults
    STABILITY_CONTROL_STRENGTH / STABILITY_SEED — so every existing caller is unchanged.
    The sweep harness MUST drive this production function, never re-implement the invoke.

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
            "control_strength": (
                control_strength if control_strength is not None else STABILITY_CONTROL_STRENGTH
            ),
            "seed": seed_value if seed_value is not None else STABILITY_SEED,
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
    except (ReadTimeoutError, ConnectTimeoutError) as e:
        # Retry once on timeout with a slightly lower control (less seed preservation) —
        # transient Bedrock stalls often succeed on second try; if it still times out,
        # re-raise so the ladder records bedrock-timeout → Rung C. This keeps Rung B
        # reachable without swallowing the reason. Fan-out siblings pass
        # retry_once=False: a cold sibling degrades to the pad honestly instead of
        # doubling a doomed call inside the shared wall.
        if not retry_once:
            raise
        print(f"[generate] stability timeout {e}, retrying once", file=sys.stderr)
        try:
            body["control_strength"] = max(0.2, body["control_strength"] - 0.05)
            resp = client.invoke_model(
                modelId=STABILITY_CONTROL_MODEL,
                body=json.dumps(body),
                contentType="application/json",
                accept="application/json",
            )
            payload = json.loads(resp["body"].read())
            images = payload.get("images") or []
            if images:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_bytes(base64.b64decode(images[0]))
                return out_path if out_path.exists() else None
        except Exception as e2:
            print(f"[generate] stability retry failed: {e2}", file=sys.stderr)
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


# Native delivery frames for the per-ratio diffusion pass: each campaign ratio
# gets its own control-structure restyle composed AT its frame (not derived from
# the 1x1), so the five tiles are five distinct compositions. blog is the
# 1200x630 Open Graph frame (756k px — inside Stability's 4096..9437184 range).
_NATIVE_RATIO_DIMS = {
    "4x5": (1080, 1350),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
    "blog": (1200, 630),
}


def _stability_native_ratio(
    seed_local: Path | str,
    scene_prompt: str,
    ratio: str,
    out_path: Path,
    *,
    seed_value: int | None = None,
    control_strength: float | None = None,
    retry_once: bool = True,
) -> Path | None:
    """Restyle the resolved seed photo natively at one delivery ratio's frame.

    Cover-fits the seed photo to _NATIVE_RATIO_DIMS[ratio], then runs the same
    control-structure restyle rung B uses — the model composes inside the real
    frame instead of a 1x1 that is later extended or cropped. Returns the path
    on success, None on any failure (the caller falls back to the deterministic
    Pillow cover-fit of the finished 1x1, honestly labelled). Never raises past
    the caller: a bad ratio slug, missing seed, or failed invoke is a None.
    """
    try:
        dims = _NATIVE_RATIO_DIMS[ratio]
    except KeyError:
        print(f"[generate] native ratio unknown: {ratio!r}", file=sys.stderr)
        return None
    try:
        seed_img = Image.open(seed_local).convert("RGB")
    except Exception as e:  # noqa: BLE001 — missing/unreadable seed degrades to pad
        print(f"[generate] native ratio seed unreadable: {e}", file=sys.stderr)
        return None
    try:
        target_w, target_h = dims
        if target_w < 64 or target_h < 64 or target_w * target_h > 9437184:
            print(
                f"[generate] native ratio {ratio} outside Stability dims",
                file=sys.stderr,
            )
            return None
        framed = ImageOps.fit(seed_img, (target_w, target_h), method=Image.BICUBIC)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        seed_path = out_path.parent / f"{out_path.stem}-seed.png"
        framed.save(seed_path, "PNG")
        return _stability_control_hero(
            seed_path,
            scene_prompt,
            out_path,
            control_strength=control_strength,
            seed_value=seed_value,
            retry_once=retry_once,
        )
    except TypeError:
        # unparametrized _stability_control_hero (older test doubles): retry bare.
        try:
            return _stability_control_hero(seed_path, scene_prompt, out_path)
        except Exception as e:  # noqa: BLE001 — degrade to pad, never raise
            print(f"[generate] native ratio {ratio} failed: {e}", file=sys.stderr)
            return None
    except Exception as e:  # noqa: BLE001 — degrade to pad, never raise
        print(f"[generate] native ratio {ratio} failed: {e}", file=sys.stderr)
        return None


def _stability_outpaint(
    base_png: Path, target_w: int, target_h: int, prompt: str, out_path: Path
) -> Path | None:
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

    Uses the shared fail-fast bedrock-runtime client with the extend read
    budget (BEDROCK_OUTPAINT_READ_TIMEOUT_S, 25s against a measured 20s
    model p-average: the standalone extend request bypasses the ladder
    wall, so the 12s ladder cap must not starve outpaints into pads).
    A timeout is re-raised so the caller
    records a timeout degrade, matching _stability_control_hero. The prompt
    goes through the frozen style sandwich so the extend stays on-brand.
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
        client = _bedrock_failfast_client(read_timeout=BEDROCK_OUTPAINT_READ_TIMEOUT_S)
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
    """Cover-fit with ratio-aware focal offset so fallback tiles are visually distinct.

    PART B fallback — cover-fit fills the frame without letterbox bars. Centering
    shifts per ratio so four pillow tiles are not four identical center crops
    (distinct focal regions = distinct local flavor). The caller still marks
    provenance engine "pillow-outpaint-fallback" so the response never claims a
    GenAI extend happened when it did not.
    """
    # Per-ratio focal centering: 4x5 favors lower food, 9x16 center, 16x9 upper scene
    centering = (0.5, 0.5)
    if target_w == 1080 and target_h == 1350:  # 4x5 portrait
        centering = (0.5, 0.62)
    elif target_w == 1080 and target_h == 1920:  # 9x16 vertical
        centering = (0.5, 0.45)
    elif target_w == 1920 and target_h == 1080:  # 16x9 landscape
        centering = (0.5, 0.38)
    elif target_w == 1200 and target_h == 630:  # blog
        centering = (0.5, 0.40)
    fitted = ImageOps.fit(
        Image.open(base_png).convert("RGB"),
        (target_w, target_h),
        method=Image.BICUBIC,
        centering=centering,
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


def _sanitize_military_headline(text: str) -> str | None:
    """Strip military/recruitment language; return None if unrecoverable.

    The grounded director and stock Nova both occasionally emit 'LISTEN UP'
    style commanding language despite prompt bans. Quarantine here so no
    military headline reaches provenance or pixels. Warm agricultural frontier
    only.
    """
    if not text:
        return None
    low = text.lower()
    # Any military/recruitment trigger quarantines the line for resample/fallback
    banned = ("listen up", "recruit", "attention ", "muster", "enlist")
    if any(b in low for b in banned):
        # Try to salvage by stripping the banned prefix phrase and leading interjections
        # e.g. "Alright, Listen Up, Kid. Summer In San Diego..." -> "Summer In San Diego..."
        stripped = re.sub(r"(?i)\b(listen up|recruit|attention|muster|enlist)\b[,\s]*", "", text)
        stripped = re.sub(r"(?i)^\s*(alright|okay|hey|listen)[,\s]+", "", stripped)
        stripped = re.sub(r"(?i)\b(kid|partner|recruit)\b[,\.\s!]*", "", stripped) if "listen up" in low else stripped
        stripped = stripped.strip(" ,.-!\t\n\"'")
        # Collapse double spaces and strip leading punctuation left from the cut
        stripped = re.sub(r"\s{2,}", " ", stripped)
        stripped = stripped.lstrip(" !,.-\"'")
        if stripped and len(stripped.split()) >= 2 and not any(b in stripped.lower() for b in banned):
            # If the salvage starts with punctuation or is still a sentence fragment
            # starting with "You're" from a conversational ramble, quarantine it
            # and let the caller fall back to the warm frontier brief headline
            if stripped[:1] in "!?,." or stripped.lower().startswith("you're"):
                return None
            return _title_case_headline(stripped)
        return None
    return text


def _scrub_director_line(text: str, examples: list[dict]) -> str | None:
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


def _voice_requested(value: object) -> bool:
    """Per-request voice opt-in (cost incident 2026-09-23).

    Default requests never touch a voice model, whatever the env flags say —
    the caller must opt in explicitly per request. Env flags remain as the
    kill-switch (both must allow AND the request must ask).
    """
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _director_headline_text(
    product_name: str, brief_msg: str, region: str, audience: str,
    art_director: bool = False, report: dict | None = None,
    market: str | None = None, season: str | None = None,
) -> str | None:
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
    if not art_director:
        _dnote("skip: no per-request opt-in")
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
        _ = _DIRECTOR_MEMO
    except NameError:
        _DIRECTOR_MEMO = {}
    # Uniqueness fix 3: the memo key salts market + season, so the same
    # brief in June and October (or Cincinnati and Seattle) re-derives
    # instead of replaying one memoized line. Identical full requests
    # (the twice-per-pack double call) still hit.
    memo_key = (product_name, brief_msg, region, audience, market or "", season or "")
    # Paid-voice attempt counter for the UI ("refining…" while attempts > 1).
    # Memo hits cost zero new calls. Reported out via `report` when provided.
    attempts = {"n": 0}
    if memo_key in _DIRECTOR_MEMO:
        _dnote("memo hit")
        if report is not None:
            report["voice_attempts"] = 0
            report["voice_source"] = "memo"
        cached = _DIRECTOR_MEMO[memo_key]
        # Sanitize even memo hits — a warm container may hold a pre-fix military line
        sanitized = _sanitize_military_headline(cached)
        if sanitized is None:
            _dnote(f"memo military filtered ({cached[:60]!r}) — miss")
            # bust the poisoned memo entry so the next call re-derives a clean line
            try:
                del _DIRECTOR_MEMO[memo_key]
            except KeyError:
                pass
            return None
        if sanitized != cached:
            _dnote(f"memo military stripped: {cached[:60]!r} -> {sanitized[:60]!r}")
            _DIRECTOR_MEMO[memo_key] = sanitized
            return sanitized
        return cached
    try:
        from . import art_director, director_memory
    except ImportError as e:
        _dnote(f"skip: import failed ({e})")
        return None

    def _attempt() -> str | None:
        query = f"{product_name} {brief_msg} {region} {audience} {market or ''} {season or ''}".strip()
        examples, model_used = director_memory.retrieve(query, k=3)
        if not examples:
            _dnote(f"no examples (embed={model_used})")
            return None
        _dnote(f"retrieved {len(examples)} examples via {model_used}")
        locale_ask = ""
        if market and str(market).strip():
            locale_ask += f" Market {str(market).strip()}."
        if season and str(season).strip():
            locale_ask += f" Season {str(season).strip()}."
        ask = (
            f"Write one short on-brand headline (max 6 words) for {product_name}: "
            f"{brief_msg}. Region {region}, audience {audience}.{locale_ask}"
        )
        samples = [examples[:3]]
        if len(examples[:1]) < len(examples[:3]):
            samples.append(examples[:1])
        for sample in samples:
            if not sample:
                break
            attempts["n"] += 1
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
            sanitized = _sanitize_military_headline(normed)
            if sanitized is None:
                _dnote(f"voice military filtered ({normed[:60]!r}) — resampling")
                continue
            if sanitized:
                return sanitized
        return None

    # Leak-and-drain on timeout (same contract generate_lambda documents for its own
    # inner director timeout): exiting a `with` executor would shutdown(wait=True) and
    # block until the abandoned worker finishes its retries — the timeout would be a
    # lie and the wall would burn. shutdown(wait=False) abandons the worker; it writes
    # nothing shared, retries out, and drains harmlessly.
    try:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    except Exception:  # noqa: BLE001 — tribunal alloc must never break the voice
        return None
    try:
        fut = executor.submit(_attempt)
        try:
            outcome = fut.result(timeout=_DIRECTOR_TIMEOUT_S)
        except Exception:  # noqa: BLE001 — worker outcome None on any failure
            outcome = None
    finally:
        executor.shutdown(wait=False)
    # Memoize only live successes: a cold-model timeout (outcome None) must not poison
    # later warm invocations in the same container — they retry the voice fresh and
    # degrade to the Nova caption only if the voice fails again.
    if report is not None:
        report["voice_attempts"] = attempts["n"]
        report["voice_source"] = _DIRECTOR_LIVE_SOURCE if outcome is not None else None
    if outcome is not None:
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
        except OSError:
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


def _validate_recipe_fields(raw: object, product_name: str) -> dict | None:
    """Strict-shape check on LLM-authored recipe fields. None when unusable.

    Never fabricates: requires a real title + 2..6 short ingredients + 2..6
    short steps, all plain strings. Anything else falls back to the default.
    """
    if not isinstance(raw, dict):
        return None
    title = raw.get("title")
    ingredients = raw.get("ingredients")
    steps = raw.get("steps")
    if not isinstance(title, str) or not title.strip():
        return None
    if not isinstance(ingredients, list) or not 2 <= len(ingredients) <= 6:
        return None
    if not isinstance(steps, list) or not 2 <= len(steps) <= 6:
        return None
    if not all(isinstance(x, str) and x.strip() for x in ingredients + steps):
        return None
    if any(len(x) > 90 for x in ingredients + steps) or len(title) > 60:
        return None
    # Standing copy law: the authoring model may emit a bare brand word.
    return {
        "title": clean_brand_copy(" ".join(title.split())),
        "ingredients": [clean_brand_copy(" ".join(str(x).split())) for x in ingredients],
        "steps": [clean_brand_copy(" ".join(str(x).split())) for x in steps],
    }


def _author_recipe_fields(
    product_name: str, brief_msg: str, region: str
) -> dict | None:
    """Ask Nova (Converse, TEXT-ONLY — no image) to author recipe-card copy.

    Grounded on the real product + campaign brief; the model may only use the
    named product plus plain pantry staples (never invents SKUs). Returns
    validated fields, or None on any failure — the caller falls back to
    _recipe_card_defaults. Text-only keeps this cheap next to the vision calls.
    """
    if boto3 is None:
        return None
    try:
        client = _bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
        prompt = (
            "You write recipe-card copy for Kodiak Cakes packaging. "
            "Brand law: never write the bare words KODIAK or Kodiak — the only allowed "
            "brand namings are 'Kodiak Cakes' and 'Kodiak Park City'. "
            f"Product: '{product_name}'. Campaign vibe: {brief_msg}. Region: {region}. "
            "Reply with ONLY a JSON object, no other text, shaped exactly like "
            '{"title": "short recipe name", '
            '"ingredients": ["3 to 5 short lines, first must use the product above, '
            "rest plain pantry staples only — never invent product names\"], "
            '"steps": ["3 to 5 short steps, max 12 words each"]}.'
        )
        resp = client.converse(
            modelId=NOVA_TEXT_MODEL,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 300},
        )
        text = resp["output"]["message"]["content"][0]["text"].strip()
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end <= start:
            return None
        return _validate_recipe_fields(json.loads(text[start : end + 1]), product_name)
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — default fallback
        print(f"[generate] recipe author unavailable, using default: {e}", file=sys.stderr)
        return None


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
        except OSError:
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
    except OSError:
        hfont = ImageFont.load_default()
        bfont = hfont
    ink = _hex_to_rgb(_scrim_hex)
    body_top = title_top + title_h + pad // 2
    line_gap = int(body_px * 1.4)
    col_x = {"left": pad, "right": W // 2 + pad // 2}

    # Legibility floor: body text must end above the accent bar. Each column
    # fits what fits — items that would cross the floor are dropped, so a
    # long LLM-authored list can never bleed off the card or under the bar.
    floor_y = H - 8 - line_gap
    capacity = max(0, (floor_y - body_top - line_gap) // line_gap)

    def _draw_zone(x: int, heading: str, items: list[str]) -> int:
        y = body_top
        draw.text((x, y), heading, fill=(*ink, 255), font=hfont)
        y += line_gap
        drawn = 0
        for item in items[:capacity]:
            draw.text((x, y), f"- {item}", fill=(*ink, 255), font=bfont)
            y += line_gap
            drawn += 1
        return drawn

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
LAYER_COBADGE = "conservation_badge"
LAYER_OVERLAY_TEXT = "overlay_text"

# Packaged US Ski & Snowboard partner mark (ships inside the module like the rung-D
# brand asset, so Lambda always has it — no S3, no web-origin fetch).
_PARTNER_MARK_ASSET = Path(__file__).parent / "brand_assets" / "us-ski-snowboard-kodiak.png"
# Vital Ground co-badge slot for Keep It Wild renders. The mark itself is NOT
# fabricated here — supply brand_assets/vital-ground.png (the real co-badge
# raster) and it pastes; absent, the slot records unresolved and ships clean,
# exactly like a missing retailer mark. Never model-drawn, never invented.
_VITAL_GROUND_MARK_ASSET = Path(__file__).parent / "brand_assets" / "vital-ground.png"
# Theme whose renders reserve the co-badge slot (same campaign system as the
# retailer badge, not decoration).
KEEP_IT_WILD_THEME = "wild-grizzly-bears"


def normalize_layers(layers: dict | None) -> dict | None:
    """Normalize a raw layers request into the contract shape. None stays None (legacy).

    Keeps only known keys: product_image/partner_logo/conservation_badge/overlay_text
    (truthy flags) and retailer (a non-empty slug string). Anything else is dropped
    so a stray client key can never switch on a composite.
    """
    if layers is None:
        return None
    if not isinstance(layers, dict):
        return {}
    norm: dict = {}
    for flag in (LAYER_PRODUCT_IMAGE, LAYER_PARTNER, LAYER_COBADGE, LAYER_OVERLAY_TEXT):
        if layers.get(flag):
            norm[flag] = True
    retailer = layers.get(LAYER_RETAILER)
    if isinstance(retailer, str) and retailer.strip():
        norm[LAYER_RETAILER] = retailer.strip().lower()
    return norm


def _ensure_writable_out_path(out_path: Path, provenance: dict) -> Path:
    """Redirect an unwritable render target to a tmp fallback. Never raises.

    Ladder contract: an unwritable out_dir degrades to a recorded tmp fallback
    (provenance["out_dir_degrade"] names requested vs actual + reason) and the
    ladder still lands on a real-pixel rung — never an uncaught OSError/500.
    A writable target is returned unchanged with no provenance touched.
    """
    candidate = Path(out_path)
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError as e:  # noqa: BLE001 — degrade to tmp, never raise
        import tempfile

        print(
            f"[generate] out_dir unwritable ({candidate.parent}): {e} -> tmp fallback",
            file=sys.stderr,
        )
        fallback = Path(tempfile.mkdtemp(prefix="kodiak-hero-")) / candidate.name
        provenance["out_dir_degrade"] = {
            "requested": str(candidate),
            "actual": str(fallback),
            "reason": f"{type(e).__name__}: {e}",
        }
        return fallback


def _resolve_retailer_mark(slug: str) -> Path | None:
    """Best-effort raster retailer mark for a slug. None when missing/unusable.

    asset-store-first via retailers.resolve_retailer_logo
    (brands/retailers/logos/<slug>.png, local raster fallback). Copy-only
    retailers (kroger/heb/whole-foods), subscription, unknown slugs, missing
    files, and SVG-only lockups (Pillow cannot rasterize SVG here) all resolve
    to None so the caller records the layer unresolved and ships the clean
    image — the copy sidecar still carries the retailer framing line.

    Lockup geometry (decided here, single place): the mark composites at
    _paste_mark, bottom-right, ~16% canvas width on a white backing plate —
    clear of the centered product layer and above the message-bar zone, so it
    reads as a channel badge, never as in-scene signage.
    """
    try:
        from .retailers import resolve_retailer_logo  # local import — keeps offline path light

        hit = resolve_retailer_logo(slug)
        if hit is not None and Path(hit).exists():
            return Path(hit)
        return None
    except Exception:  # noqa: BLE001 — unresolved mark resolves to None, ship clean
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
    """Composite selected retailer/partner/conservation marks onto a finished clean render, in place.

    Best-effort and never fatal: an unresolvable mark is recorded in provenance
    (<layer>_layer: "unresolved:…") and the clean image ships untouched.
    """
    if not layers:
        return
    retailer = layers.get(LAYER_RETAILER)
    want_partner = bool(layers.get(LAYER_PARTNER))
    want_cobadge = bool(layers.get(LAYER_COBADGE))
    if not retailer and not want_partner and not want_cobadge:
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
    if want_cobadge:
        # Vital Ground co-badge slot (Keep It Wild renders): same contract as
        # the retailer badge — real raster pasted by code, bottom-left mark
        # family; missing asset records unresolved and ships clean.
        if _VITAL_GROUND_MARK_ASSET.exists():
            try:
                canvas = _paste_mark(
                    canvas, Image.open(_VITAL_GROUND_MARK_ASSET).convert("RGBA"), "left", 0.14
                )
                applied.append("conservation_badge")
            except Exception as mark_error:  # noqa: BLE001 — unresolved, ship clean
                print(f"[generate] cobadge mark paste failed: {mark_error}", file=sys.stderr)
                provenance["cobadge_layer"] = "unresolved:paste-failed"
        else:
            provenance["cobadge_layer"] = "unresolved:asset-missing"
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
    *,
    localizations: list[dict] | None = None,
    languages: list[str] | None = None,
    recipe_fields: dict | None = None,
    retailer: str | None = None,
) -> dict:
    """Build the copy sidecars (#199, Atlanta H): campaign copy as text + CSV, never baked in.

    Deterministic (no timestamps) so output is byte-stable. The headline prefers the
    composed copy_headline the ladder recorded, then the legacy overlay headline,
    then the raw brief — copy always ships even when the image is clean.

    True campaign messaging (Atlanta H): full per-platform copy, multilingual
    variants (i18n.{lang}.headline rows), the local recipe (recipe.* rows), and
    retailer proof (retailer + retailer_framing rows) all ship as field,value
    rows in the CSV and as lines in the txt. Every string passes through the
    standing-law brand cleaner, so no bare KODIAK/Kodiak ships.
    """
    provenance = provenance or {}
    platform_copy = platform_copy or {}
    headline = clean_brand_copy(
        provenance.get("copy_headline")
        or provenance.get("headline")
        or str(prompt or "")[:80]
    )
    brief = clean_brand_copy(str(prompt or ""))
    product_label = product or "kodiak"
    theme_line = f"theme: {theme}" if theme else "theme: none"
    txt_lines = [
        f"Kodiak Cakes campaign copy — {product_label}",
        theme_line,
        f"headline: {headline}",
        f"brief: {brief}",
    ]
    # retailer direction (#245, Atlanta E/H): the theme's copy framing ships as its
    # own line so a retailer choice visibly changes the copy. An explicit retailer
    # (e.g. Publix for Atlanta-like markets) ships as its own row too.
    retailer_framing = _THEME_COPY_HINT.get(theme or "")
    if retailer:
        txt_lines.append(f"retailer: {retailer}")
    if retailer_framing:
        txt_lines.append(f"retailer framing: {retailer_framing}")
    # multi-theme combo extras (primary already drove theme/copy above): each
    # extra ships as its own copy line so the combo is visible in the sidecar.
    combo = provenance.get("theme_combo") if isinstance(provenance, dict) else None
    combo_lines: list[dict] = []
    if isinstance(combo, dict):
        combo_lines = combo.get("copy_lines") or []
        if combo.get("extras"):
            txt_lines.append(
                f"theme combo: {combo.get('primary')} + {', '.join(combo['extras'])}"
            )
    for line in combo_lines:
        if isinstance(line, dict) and line.get("framing"):
            txt_lines.append(f"extra framing ({line.get('theme')}): {line['framing']}")
    panel_flag = provenance.get("panel_flag") if isinstance(provenance, dict) else None
    if panel_flag:
        txt_lines.append(f"panel flag: {panel_flag}")
    # recipe tease (Atlanta E/H): the local recipe card ships in the sidecar.
    recipe_fields = recipe_fields or {}
    recipe_title = recipe_fields.get("title") if isinstance(recipe_fields, dict) else None
    if recipe_title:
        txt_lines.append(f"recipe: {clean_brand_copy(str(recipe_title))}")
    # art-director voice upgrade: recorded when the post-render voice step produced
    # a real line (never swaps the headline — the brief stays the record).
    art_headline = provenance.get("art_headline") if provenance else None
    if art_headline:
        txt_lines.append(f"art-director voice: {clean_brand_copy(str(art_headline))}")

    def _plat_title(entry: dict) -> str:
        return clean_brand_copy(str(entry.get("headline") or entry.get("title") or ""))

    def _plat_body(entry: dict) -> str:
        return clean_brand_copy(str(entry.get("body") or entry.get("description") or ""))

    def _plat_tags(entry: dict) -> str:
        tags = entry.get("hashtags")
        return " ".join(tags) if isinstance(tags, list) else (tags or "")

    for plat in sorted(platform_copy):
        entry = platform_copy[plat] or {}
        txt_lines.append(f"[{plat}] {_plat_title(entry)} — {_plat_body(entry)} {_plat_tags(entry)}".strip())
    # multilingual variants: one tease line per non-English localization.
    for loc in localizations or []:
        if not isinstance(loc, dict):
            continue
        code = loc.get("lang_code", "")
        if code and code != "en":
            txt_lines.append(
                f"[{code}] {clean_brand_copy(str(loc.get('headline', '')))}".strip()
            )
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["field", "value"])
    writer.writerow(["product", product_label])
    writer.writerow(["theme", theme or ""])
    writer.writerow(["headline", headline])
    writer.writerow(["brief", brief])
    if retailer:
        writer.writerow(["retailer", retailer])
    if retailer_framing:
        writer.writerow(["retailer_framing", retailer_framing])
    if isinstance(combo, dict) and combo.get("extras"):
        writer.writerow(["theme_combo", f"{combo.get('primary')}+{','.join(combo['extras'])}"])
    for line in combo_lines:
        if isinstance(line, dict) and line.get("framing"):
            writer.writerow([f"extra_framing.{line.get('theme')}", line["framing"]])
    if panel_flag:
        writer.writerow(["panel_flag", panel_flag])
    if recipe_title:
        writer.writerow(["recipe.title", clean_brand_copy(str(recipe_title))])
        ingredients = recipe_fields.get("ingredients") if isinstance(recipe_fields, dict) else None
        if isinstance(ingredients, list):
            for i, ing in enumerate(ingredients):
                writer.writerow([f"recipe.ingredient_{i + 1}", clean_brand_copy(str(ing))])
        steps = recipe_fields.get("steps") if isinstance(recipe_fields, dict) else None
        if isinstance(steps, list):
            for i, step in enumerate(steps):
                writer.writerow([f"recipe.step_{i + 1}", clean_brand_copy(str(step))])
    if art_headline:
        writer.writerow(["art_headline", clean_brand_copy(str(art_headline))])
    for plat in sorted(platform_copy):
        entry = platform_copy[plat] or {}
        writer.writerow([f"{plat}.headline", _plat_title(entry)])
        writer.writerow([f"{plat}.body", _plat_body(entry)])
        writer.writerow([f"{plat}.hashtags", _plat_tags(entry)])
    for loc in localizations or []:
        if not isinstance(loc, dict):
            continue
        code = loc.get("lang_code", "")
        if not code:
            continue
        writer.writerow([f"i18n.{code}.headline", clean_brand_copy(str(loc.get("headline", "")))])
        writer.writerow([f"i18n.{code}.source", str(loc.get("source", ""))])
    if languages:
        writer.writerow(["languages", ",".join(languages)])
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
    themes: list[str] | str | None = None,
    dish: str | None = None,
    art_director: bool = False,
    market: str | None = None,
    season: str | None = None,
    native_siblings: dict | None = None,
) -> tuple[Path, str, dict]:
    """Generate a real Kodiak-social-style hero. Returns (path, source, provenance).

    native_siblings: optional {ratio: out_path} for the delivery ratios. When set
    and rung B runs a live restyle, the 1x1 restyle AND one restyle per sibling
    ratio fire CONCURRENTLY (one ThreadPoolExecutor batch ≈ one restyle of wall),
    each composed at its own frame via _stability_native_ratio — five discrete
    diffusion compositions, never one image derived four ways. Sibling outcomes
    land in provenance["native_ratios"] ({ratio: engine-or-reason}); a missing
    or failed sibling is the caller's cue to derive that tile the old way.
    Scenic-verbatim seeds never fan out (a restyle re-invents the subject).

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
    0. theme provided AND _resolve_theme_photo(theme) resolves -> that thematic asset store
       photo is the seed (the chip theme drives the IMAGE, not the product default).
    0b. staged staged asset pick (seed_key from the asset browser) -> that exact photo is the
       seed (the customer's pick drives the IMAGE). Fetched verbatim, never probed.
    a. no theme (or unresolved) -> sku-photo-map resolves the handle -> a REAL
       lifestyle asset photo (asset_store.fetch_asset_key -> /tmp) is the seed.
    b. no map entry OR the asset store fetch fails -> disk _find_source_asset is the seed
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

    # Multi-theme combination: the first KNOWN slug drives seed + scene
    # (overriding the single theme); remaining known slugs become overlay
    # layers + copy lines; unknown slugs raise a panel flag, never raise.
    # themes=None preserves the legacy single-theme path exactly.
    theme_combo: dict | None = combine_themes(themes) if themes is not None else None
    if theme_combo is not None and theme_combo["primary"] is not None:
        theme = theme_combo["primary"]
    combo_extras: list[str] = list(theme_combo["extras"]) if theme_combo else []

    # Director kicked once at ladder start so the voice overlaps seed
    # resolution + rung composition instead of serializing after them.
    # The report dict carries the paid-attempt count back for provenance.
    _ladder_voice_report: dict = {}
    # Uniqueness seed for this request (fix 1): rung A + B restyles derive
    # from brief + market + season + day instead of the constant 42.
    request_seed = _request_seed(brief_msg, market, season)
    try:
        _director_fut = _DIRECTOR_POOL.submit(
            _director_headline_text, product_name, brief_msg, region, audience,
            art_director, _ladder_voice_report, market, season,
        )
    except Exception:  # noqa: BLE001 — director kick is best-effort; caption path covers
        _director_fut = None
    # Slow-voice latch: the ladder calls _headline once per attempted rung
    # (A/B/C) — without this, three budget-shaped waits could stack past the
    # grace the wall allows. The first wait that times out marks the voice
    # dead; later calls only poll an already-done future (free) and otherwise
    # fall straight to caption.
    _voice_state = {"dead": False}

    def _headline(src: Path, caption_future=None) -> str:
        # caption_future: an overlapped _caption_with_budget already submitted
        # at rung-B entry (caption needs only seed + statics, same as the
        # scene-prompt). Collect with a budget-shaped wait instead of burning a
        # second serial Nova call. None = call directly, as rung C does.
        # grounded trained director first (budget-gated collect, live-source
        # only, already house-styled); stock Nova caption second; raw brief
        # last and verbatim. provenance records which voice wrote the line.
        # The collect wait is budget-shaped: a rich clock waits up to the
        # director bound for a real headline; a thin clock takes ~0 and falls
        # through to caption immediately.
        if remaining_ms() >= _DIRECTOR_BUDGET_MS + _C_RESERVATION_MS:
            directed = None
            if _director_fut is not None:
                if _director_fut.done():
                    try:
                        directed = _director_fut.result(timeout=0)
                    except Exception:  # noqa: BLE001 — dead voice falls to caption, pixels unaffected
                        directed = None
                        _voice_state["dead"] = True
                elif not _voice_state["dead"]:
                    try:
                        grace_s = min(
                            (_DIRECTOR_TIMEOUT_S + 2.0),
                            max(0.3, (remaining_ms() - _C_RESERVATION_MS - 500.0) / 1000.0),
                        )
                        directed = _director_fut.result(timeout=grace_s)
                    except Exception:  # noqa: BLE001 — slow voice -> caption path, pixels unaffected
                        directed = None
                        _voice_state["dead"] = True
            if "voice_attempts" in _ladder_voice_report and isinstance(provenance, dict):
                provenance["voice_attempts"] = _ladder_voice_report["voice_attempts"]
            if directed:
                # Military quarantine even on the memoized/director path — warm frontier only
                sanitized = _sanitize_military_headline(directed)
                if sanitized is None:
                    print(f"[director] military headline filtered ({directed[:60]!r}) -> caption fallback", file=sys.stderr)
                    provenance["headline_source"] = "filtered:military"
                else:
                    if sanitized != directed:
                        print(f"[director] military stripped: {directed[:60]!r} -> {sanitized[:60]!r}", file=sys.stderr)
                        directed = sanitized
                    provenance["headline_source"] = _DIRECTOR_LIVE_SOURCE
                    print(f"[director] grounded headline: {directed}", file=sys.stderr)
                    return directed
        else:
            print(
                f"[director] skip: budget {remaining_ms():.0f}ms < "
                f"{_DIRECTOR_BUDGET_MS + _C_RESERVATION_MS}ms",
                file=sys.stderr,
            )
        print(f"[generate] stage caption start (budget {remaining_ms():.0f}ms)", file=sys.stderr)
        _caption_t0 = time.monotonic()
        if caption_future is not None:
            try:
                _wait_s = max(
                    0.0,
                    min(
                        5.0,
                        (remaining_ms() - _C_RESERVATION_MS - 500.0) / 1000.0,
                    ),
                )
                caption = caption_future.result(timeout=_wait_s) if _wait_s > 0 else ""
            except Exception as e:  # noqa: BLE001 — thin clock: brief fallback, worker drains alone
                print(f"[generate] overlapped caption collect skipped: {e}", file=sys.stderr)
                caption = ""
            print(f"[generate] stage caption (overlapped) collected: {'ok' if caption else 'empty'}", file=sys.stderr)
        else:
            caption = _caption_with_budget(
                src, product_name, brief_msg, region, audience, remaining_ms=remaining_ms
            )
            print(f"[generate] stage caption done in {time.monotonic() - _caption_t0:.1f}s", file=sys.stderr)
        headline, _side = _parse_layout(caption)
        if headline:
            normed = _title_case_headline(headline)
            sanitized = _sanitize_military_headline(normed)
            if sanitized is not None:
                provenance["headline_source"] = "bedrock:nova-pro-caption"
                return sanitized
            print(f"[director] caption military filtered ({normed[:60]!r}) -> brief fallback", file=sys.stderr)
            provenance["headline_source"] = "filtered:military"
        return brief_msg[:48]

    # Render-contract layers (#199/#200): normalize once; None = legacy ladder,
    # any dict = clean contract (no default box paste, no baked overlay text).
    layers = normalize_layers(layers)
    overlay_on = bool(brand_overlay) if layers is None else bool(layers.get(LAYER_OVERLAY_TEXT))
    want_box = layers is None or bool(layers.get(LAYER_PRODUCT_IMAGE))

    # PART A — provenance accumulator. Populated as the seed + engine paths resolve so
    # the response can explain "what was provided vs what was done to make this image".
    # Engine-key contract (pinned): engine is one of packshot-composite (rung A),
    # stability-restyle (rung B), pillow-compose (rung C), brand-floor (rung D).
    # origin marks which side rendered the envelope: "backend" here. The frontend
    # surfaces both via the rung badge + provenance panel, never relabelling them.
    provenance: dict = {
        "seed_source": None,
        "seed_selection": "none",
        "engine": None,
        "rung": None,
        "origin": "backend",
        "fallthrough_reason": None,
        "elapsed_ms": None,
        "scene_prompt": None,
        "control_strength": None,
        "model": None,
        "incoming_prompt": brief_msg,
        "dish": dish,
        "theme": theme,
        "themes": theme_combo["themes"] if theme_combo else None,
        "theme_combo": (
            {
                "primary": theme_combo["primary"],
                "extras": theme_combo["extras"],
                "overlay_layers": theme_combo["overlay_layers"],
                "copy_lines": theme_combo["copy_lines"],
                "unknown": theme_combo["unknown"],
            }
            if theme_combo
            else None
        ),
        "panel_flag": theme_combo["panel_flag"] if theme_combo else None,
        "headline": None,
        "overlay_applied": False,
        "paper_overlay": False,
        "packshot": None,
        "layers": layers,
        "clean": layers is not None,
        "copy_headline": None,
    }
    # Unwritable out_dir degrades to a recorded tmp fallback HERE so every rung
    # below (A bg composite, B restyle, C compose, D floor) writes the usable
    # path — the ladder still lands on real pixels, never an uncaught OSError.
    out_path = _ensure_writable_out_path(out_path, provenance)

    def _seal(reason: str | None = None) -> None:
        """Record the elapsed clock (and an optional fallthrough reason) into provenance."""
        provenance["elapsed_ms"] = int((time.monotonic() - start) * 1000.0)
        if reason is not None:
            provenance["fallthrough_reason"] = reason

    # ---- seed resolution: theme photo, else sku-mapped asset photo, else disk asset.
    # _idea_hit tracks whether the seed honors the brief's free-text idea: an
    # explicit theme/staged pick is the user's own visual vote, and a
    # brief-matched pool pick carries an idea word. Auto sku/disk rotation
    # does not count — it can serve a kitchen frame for "sea otters".
    seed: Path | None = None
    _idea_hit = False
    if theme:
        theme_key = _resolve_theme_photo(theme)
        if theme_key:
            try:
                from .asset_store import fetch_asset_key

                dest = Path("/tmp/kodiak-assets/theme") / Path(theme_key).name
                photo = fetch_asset_key(theme_key, dest)
                if photo is not None and photo.exists():
                    seed = photo
                    provenance["seed_selection"] = "theme-photo"
                    provenance["seed_source"] = Path(theme_key).stem
                    _idea_hit = True
            except Exception as e:  # noqa: BLE001 — falls through to product precedence
                print(f"[generate] theme seed fetch failed: {e}", file=sys.stderr)
    if seed is None and seed_key:
        # staged staged asset pick from the asset browser: the exact photo the customer chose.
        # Fetched verbatim by full key (no prefix join — browser contract); any failure
        # falls through to the normal resolution below, so a stale pick never sinks a rung.
        try:
            from .asset_store import fetch_asset_key

            # Key-unique dest (never bare basename): Lambda /tmp persists per
            # execution environment and fetch_asset_key trusts a nonzero
            # dest, so two keys sharing a basename (every scenic
            # hero-1x1.png) would restyle yesterday's file. Seen live: a
            # christmas-cats preview restyled a stale bear frame.
            dest = _staged_dest(seed_key)
            photo = fetch_asset_key(seed_key, dest)
            if photo is not None and photo.exists():
                seed = photo
                provenance["seed_selection"] = "staged-asset"
                provenance["seed_source"] = Path(seed_key).stem
                provenance["seed_key"] = seed_key
                _idea_hit = True
                if theme == "riff-on-past-content":
                    provenance["riff_on"] = seed_key
        except Exception as e:  # noqa: BLE001 — falls through to sku-mapped lookup
            print(f"[generate] staged seed fetch failed: {e}", file=sys.stderr)
    if seed is None:
        # Non-deterministic but brief-aware: the brief (your campaign idea) picks the seed
        # among the SKU's asset store pool, so peaches vs pumpkins vs a custom idea don't all get
        # the same deterministic Community Kitchen frame — we rotate through the fallbacks.
        candidates: list[str] = []
        primary = _resolve_asset_photo(product_id)
        captions: dict[str, str] = {}
        if primary:
            candidates.append(primary)
            # Pull fallbacks from sku-photo-map for this SKU so the same product can
            # still look different when the brief changes (peaches → tacos → kitchen).
            try:
                _entry = _load_sku_photo_map().get(product_id, {})
                if isinstance(_entry, dict):
                    _cap = _entry.get("caption")
                    if isinstance(_cap, str) and _cap.strip():
                        captions[primary] = _cap
                    for _fb in _entry.get("fallbacks", []) or []:
                        if _fb not in candidates:
                            candidates.append(_fb)
            except Exception:
                pass
        # Brief-aware pick first: when the idea names something the pool can
        # actually show (a caption/keystem word match), that seed wins over
        # random rotation — "peaches" should not serve the taco frame. No
        # overlap falls through to the existing pick, never worse than before.
        photo_key = None
        if candidates:
            _idea = _brief_idea(brief_msg)
            _match = _brief_seed_pick(
                _idea, [(c, captions.get(c, "")) for c in candidates]
            )
            if _match is not None:
                photo_key = _match
                _idea_hit = True
                print(f"[generate] brief-matched seed pick {photo_key} for idea {(_idea or '')[:40]!r}", file=sys.stderr)
        # Dynamic per-campaign: every invocation picks a fresh seed among the SKU's pool
        # so the same brief does not lock to one Community Kitchen frame — campaign images
        # are meant to be varied. Recipe stays deterministic via market|month|ingredient
        # rotation (recipe_card.py), so ingredients remain stable while campaigns vary.
        # Deterministic mode (KODIAK_DETERMINISTIC=1) keeps hash-based pick for tests.
        if photo_key is None and candidates:
            if os.getenv("KODIAK_DETERMINISTIC") == "1":
                h = _stable_hash_int((brief_msg or "") + product_id)
                photo_key = candidates[h % len(candidates)]
                print(f"[generate] brief-aware seed pick {photo_key} from {len(candidates)} candidates (deterministic)", file=sys.stderr)
            else:
                import random

                photo_key = random.choice(candidates)
                print(f"[generate] dynamic seed pick {photo_key} from {len(candidates)} candidates", file=sys.stderr)
        if photo_key:
            try:
                from .asset_store import fetch_asset_key

                dest = Path("/tmp/kodiak-assets/scene") / Path(photo_key).name
                photo = fetch_asset_key(photo_key, dest)
                if photo is not None and photo.exists():
                    seed = photo
                    provenance["seed_selection"] = "sku-mapped-asset"
                    provenance["seed_source"] = Path(photo_key).stem
            except Exception as e:  # noqa: BLE001 — falls through to disk
                print(f"[generate] sku-mapped seed fetch failed: {e}", file=sys.stderr)
    if seed is None:
        # _find_source_asset's step 3 is an S3 asset store fan-out (sequential hero-real/hero x
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

    # ---- idea honesty: record the free-text subject, and say so when no photo
    # in any pool can show it. A restyle preserves its seed's composition, so
    # "sea otters" over a kitchen frame is structurally impossible — the
    # response must admit that instead of serving the frame silently. Only
    # fills an empty fallthrough_reason; budget/similarity causes keep priority.
    provenance["idea_subject"] = _brief_idea(brief_msg)
    if (
        provenance["idea_subject"]
        and not _idea_hit
        and provenance.get("fallthrough_reason") is None
    ):
        provenance["fallthrough_reason"] = (
            f"idea-beyond-photo-pool ({provenance['idea_subject'][:60]}): "
            "no pool photo matches the idea — served closest packshot/scene, "
            "subject kept in scene direction"
        )
    # ---- PACKSHOT-FIRST (compose-fix root-cause repair): if a real product BOX resolves
    # for this SKU, paste it VERBATIM over a background scene — NO generative step touches
    # those product pixels, so it structurally cannot render as bread or candy. This
    # mirrors campaign.py::_render_asset order a/b. The BACKGROUND scene still gets the
    # rung-B restyle first when the budget allows (fresh AI pixels every render); the
    # box is pasted over the restyled scene, never fed into the restyle. Generation
    # remains the FALLBACK below for the no-packshot case. See
    # docs/architecture/compose-fix/compose-fix-spec.md.
    from .asset_store import resolve_packshot  # local import — keeps the offline path import-light

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
            # SKU ships fresh photographic pixels instead of recycling the raw asset store
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
                        region, audience, theme, dish, market, season,
                        request_seed)
                    cached = out_path.parent / f"{out_path.stem}-restyle-cached.png"
                    if _restyle_cache_get(cache_key, cached):
                        seed = cached
                        bg_restyle = True
                        provenance["bg_restyle_source"] = "cache"
                except (OSError, ValueError, TypeError):
                    cache_key = None
            if (seed is not None and not bg_restyle and not bare_base
                    and remaining_ms() >= _B_BUDGET_MS + _C_RESERVATION_MS):
                try:
                    a_scene = _nova_pro_scene_prompt(
                        seed, product_name, brief_msg, region, audience, theme,
                        combo_extras or None, dish, market, season,
                    )
                    provenance["scene_prompt"] = a_scene
                    provenance["scene_prompt_source"] = _scene_prompt_source(
                        a_scene, product_name, brief_msg, region, audience, theme, dish,
                        market, season,
                    )
                    # _STABILITY_RUNG_ON gate: dev skips the packshot background restyle
                    # and falls to the deterministic packshot composite (unrestyled seed).
                    if _STABILITY_RUNG_ON and remaining_ms() >= _B_STABILITY_MS + _C_RESERVATION_MS:
                        restyled = out_path.parent / f"{out_path.stem}-restyle.png"
                        if _stability_control_hero(seed, a_scene, restyled, seed_value=request_seed) is not None and restyled.exists():
                            seed = restyled
                            bg_restyle = True
                            provenance["bg_restyle_source"] = "fresh"
                            provenance["seed"] = request_seed
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
            # A staged staged asset pick stays labelled: the box is pasted over the exact
            # photo the customer chose, so seed_selection must say so (the pick
            # drives the render — mislabelling it "packshot" hides that).
            if provenance.get("seed_selection") != "staged-asset":
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
        # _STABILITY_RUNG_ON gates the whole generative rung: dev (flag off) skips B entirely
        # and falls to rung C (Nova-Pro-art-directed Pillow compose) with a distinct reason.
        if _STABILITY_RUNG_ON and remaining_ms() >= _B_BUDGET_MS + _C_RESERVATION_MS:
            try:
                # Caption overlap: fire the Nova caption NOW so it runs inside
                # the scene + stability calls; _headline collects it after the
                # restyle. Skipped on a thin clock (the direct path logs the
                # skip exactly as before).
                _caption_future = None
                if remaining_ms() >= _CAPTION_BUDGET_MS + _C_RESERVATION_MS:
                    _caption_future = _CAPTION_POOL.submit(
                        _caption_with_budget, seed, product_name, brief_msg,
                        region, audience,
                    )
                # Per-subcall budget gate 1 — the Nova Pro scene-prompt (fail-fast, capped
                # at BEDROCK_NOVA_READ_TIMEOUT_S). Enter it ONLY while the clock still
                # covers the scene call PLUS the downstream stability + C reservation, so a
                # slow Nova Pro can never consume the budget rung C needs. If it will not
                # fit, skip the rest of B and drop to C. The scene call itself also
                # degrades to a deterministic default on timeout, but this gate keeps the
                # WALL-CLOCK bounded even before the timeout fires.
                if provenance.get("seed_selection") == "theme-photo":
                    # Theme-photo fast path: the seed photo already carries the
                    # theme, so the Nova scene vision call buys nothing — skip
                    # it outright (up to ~12s) and protect rung C's reservation.
                    scene_prompt = _default_scene_prompt(
                        product_name, brief_msg, region, audience, theme,
                        combo_extras or None, dish, market, season,
                    )
                    print(
                        "[generate] rung B scene-prompt fast-pathed "
                        "(theme-photo seed, deterministic default)",
                        file=sys.stderr,
                    )
                else:
                    if remaining_ms() < _B_NOVA_SCENE_MS + _B_STABILITY_MS + _C_RESERVATION_MS:
                        print(
                            f"[generate] rung B scene-prompt skipped (budget {remaining_ms():.0f}ms < "
                            f"{_B_NOVA_SCENE_MS + _B_STABILITY_MS + _C_RESERVATION_MS}ms) -> rung C",
                            file=sys.stderr,
                        )
                        provenance["fallthrough_reason"] = "budget-exhausted"
                        raise _RungBBudgetSkip
                    print(f"[generate] stage scene-prompt start (budget {remaining_ms():.0f}ms)", file=sys.stderr)
                    _scene_t0 = time.monotonic()
                    scene_prompt = _nova_pro_scene_prompt(
                        seed, product_name, brief_msg, region, audience, theme,
                        combo_extras or None, dish, market, season,
                    )
                    print(f"[generate] stage scene-prompt done in {time.monotonic() - _scene_t0:.1f}s", file=sys.stderr)
                provenance["scene_prompt"] = scene_prompt
                provenance["scene_prompt_source"] = _scene_prompt_source(
                    scene_prompt, product_name, brief_msg, region, audience, theme, dish,
                    market, season,
                )
                # Scenic-verbatim bypass: an idea-composed seed already IS the
                # campaign in pixels — no Bedrock call is needed, so neither
                # the budget gate below nor the restyle may touch it. The
                # restyle re-invents subjects (seen live: christmas-cats seed
                # restyled into a bear, then into a bare table); the seed
                # rides verbatim straight to compose. Engine stays
                # stability-restyle (closed set, backend GenAI rung B);
                # bg_source + model tell the truth.
                _scenic_verbatim = _is_scenic_seed(provenance.get("seed_key"))
                if _scenic_verbatim:
                    print(
                        f"[generate] rung B scenic-verbatim {Path(seed_key or '').name} "
                        f"-> compose, no restyle",
                        file=sys.stderr,
                    )
                # Per-subcall budget gate 2 — the Stability invoke (fail-fast, capped at
                # BEDROCK_READ_TIMEOUT_S). Re-check AFTER the scene call actually spent its
                # time; if the remaining clock can no longer cover stability + the C
                # reservation, abandon B and fall to C rather than risk the gateway cap.
                # Scenic-verbatim spends no Bedrock, so the gate does not apply.
                if remaining_ms() < _B_STABILITY_MS + _C_RESERVATION_MS and not _scenic_verbatim:
                    print(
                        f"[generate] rung B stability skipped (budget {remaining_ms():.0f}ms < "
                        f"{_B_STABILITY_MS + _C_RESERVATION_MS}ms) -> rung C",
                        file=sys.stderr,
                    )
                    provenance["fallthrough_reason"] = "budget-exhausted"
                    raise _RungBBudgetSkip
                # Compute once: the recorded strength must equal the strength
                # actually sent (dynamic mode jitters per call). Scenic-verbatim
                # skips the invoke entirely: the seed IS the finished pixels.
                rung_b_strength = _control_for_brief(brief_msg)
                if _scenic_verbatim:
                    stylized = seed
                    rung_b_strength = None
                    print("[generate] stage restyle skipped (scenic-verbatim)", file=sys.stderr)
                else:
                    print(f"[generate] stage restyle start (budget {remaining_ms():.0f}ms)", file=sys.stderr)
                    _restyle_t0 = time.monotonic()
                    _siblings = dict(native_siblings) if isinstance(native_siblings, dict) else {}
                    if _siblings:
                        # Native fan-out: the 1x1 AND every sibling ratio restyle
                        # CONCURRENTLY (one batch ≈ one restyle of wall), each at
                        # its own frame. Per-ratio seeds step so sibling tiles
                        # never echo each other. A lost sibling is recorded, never
                        # raised — the caller derives that tile the old way.
                        _native_outcomes: dict[str, str] = {}
                        try:
                            import concurrent.futures as _futures

                            _jobs = [("1x1", out_path)] + [
                                (str(_r), Path(_p)) for _r, _p in _siblings.items()
                            ]
                            with _futures.ThreadPoolExecutor(max_workers=len(_jobs)) as _pool:
                                def _fire(_ratio: str, _dest: Path, _idx: int):
                                    if _ratio == "1x1":
                                        try:
                                            return _stability_control_hero(
                                                seed, scene_prompt, _dest,
                                                control_strength=rung_b_strength,
                                                seed_value=request_seed,
                                            )
                                        except TypeError:
                                            return _stability_control_hero(seed, scene_prompt, _dest)
                                    return _stability_native_ratio(
                                        seed, scene_prompt, _ratio, _dest,
                                        control_strength=rung_b_strength,
                                        seed_value=None if request_seed is None else request_seed + _idx,
                                        retry_once=False,
                                    )

                                _pending = {
                                    _pool.submit(_fire, _ratio, _dest, _i): (_ratio, _dest)
                                    for _i, (_ratio, _dest) in enumerate(_jobs)
                                }
                                _stylized_1x1 = None
                                for _fut in _futures.as_completed(_pending):
                                    _ratio, _dest = _pending[_fut]
                                    try:
                                        _each = _fut.result(
                                            timeout=max(1.0, remaining_ms() / 1000.0)
                                        )
                                    except Exception as _e:  # noqa: BLE001 — timeout included
                                        _each = None
                                        _native_outcomes[_ratio] = f"native-error: {type(_e).__name__}"
                                    if _ratio == "1x1":
                                        _stylized_1x1 = _each
                                    elif _each is not None and Path(_dest).exists():
                                        _native_outcomes[_ratio] = "stability-restyle-native"
                                    else:
                                        _native_outcomes.setdefault(_ratio, "native-unavailable")
                            stylized = _stylized_1x1
                        except Exception as _e:  # noqa: BLE001 — pool failure keeps the serial path below
                            print(f"[generate] native fan-out failed: {_e}", file=sys.stderr)
                            _native_outcomes = {}
                            stylized = None
                        provenance["native_ratios"] = _native_outcomes
                    if not _siblings or stylized is None and not provenance.get("native_ratios"):
                        try:
                            stylized = _stability_control_hero(seed, scene_prompt, out_path, control_strength=rung_b_strength, seed_value=request_seed)
                        except TypeError:
                            stylized = _stability_control_hero(seed, scene_prompt, out_path)
                            rung_b_strength = None  # unparametrized fallback: record no strength
                    print(f"[generate] stage restyle done in {time.monotonic() - _restyle_t0:.1f}s", file=sys.stderr)
                if stylized is not None and stylized.exists():
                    # Similarity gate (B -> C): reject a drifted restyle BEFORE the
                    # overlay lands — the message bar alone shifts dHash by ~12, so
                    # this MUST read the pre-overlay pixels. A reject falls to rung
                    # C with fallthrough_reason="similarity-gate"; an unreadable
                    # image fails OPEN (never lose a GenAI hero over a hash read).
                    # Scenic-verbatim has no restyle to judge — skip the gate.
                    if _similarity_gate_enabled() and not _scenic_verbatim:
                        _sim_dist = _similarity_distance(seed, stylized)
                        provenance["similarity_threshold"] = SIMILARITY_GATE_THRESHOLD
                        _diverge = _diverge_requested(theme, season)
                        provenance["similarity_mode"] = "diverge" if _diverge else "preserve"
                        if _sim_dist is None:
                            provenance["similarity_gate"] = "error"
                        else:
                            provenance["similarity_distance"] = _sim_dist
                            _verdict = _similarity_gate_decision(_sim_dist, _diverge)
                            if _verdict == "reject-drift":
                                print(
                                    f"[generate] rung B similarity-gate reject "
                                    f"(distance {_sim_dist} > {SIMILARITY_GATE_THRESHOLD}) "
                                    f"-> fall to C",
                                    file=sys.stderr,
                                )
                                provenance["similarity_gate"] = "fail"
                                provenance["fallthrough_reason"] = "similarity-gate"
                                stylized = None
                            elif _verdict == "retry":
                                # Diverge requested but the model echoed the seed:
                                # one retry with the next seed + lighter control,
                                # into a sibling file so a retry failure keeps
                                # the first restyle. Budget-gated like every B
                                # sub-call; a thin clock accepts the echo and
                                # labels it instead of burning the wall.
                                provenance["similarity_gate"] = "retry-too-close"
                                if remaining_ms() >= _B_STABILITY_MS + _C_RESERVATION_MS:
                                    _retry_seed = request_seed + 1
                                    _retry_strength = max(
                                        0.2, (rung_b_strength if rung_b_strength is not None else STABILITY_CONTROL_STRENGTH) - 0.1
                                    )
                                    _retry_path = out_path.parent / f"{out_path.stem}-diverge.png"
                                    try:
                                        _retried = _stability_control_hero(
                                            seed, scene_prompt, _retry_path,
                                            control_strength=_retry_strength,
                                            seed_value=_retry_seed,
                                        )
                                    except TypeError:
                                        _retried = None
                                    except Exception as retry_error:  # noqa: BLE001 — retry failure keeps the first restyle
                                        print(f"[generate] diverge retry failed: {retry_error}", file=sys.stderr)
                                        _retried = None
                                    if _retried is not None and _retried.exists():
                                        _retry_dist = _similarity_distance(seed, _retried)
                                        provenance["similarity_retry_distance"] = _retry_dist
                                        provenance["similarity_retry_seed"] = _retry_seed
                                        stylized = _retried
                                        request_seed = _retry_seed
                                        provenance["similarity_gate"] = "retry-accept"
                                    else:
                                        provenance["similarity_gate"] = "retry-failed-accept"
                                else:
                                    provenance["similarity_gate"] = "too-close-accept"
                            else:
                                provenance["similarity_gate"] = "pass"
                    else:
                        provenance["similarity_gate"] = "disabled"
                if stylized is not None and stylized.exists():
                    provenance["engine"] = "stability-restyle"
                    provenance["rung"] = "B"
                    if rung_b_strength is not None:
                        provenance["control_strength"] = rung_b_strength
                    provenance["seed"] = request_seed
                    provenance["style"] = "sandwich-locked"
                    provenance["seed_local"] = str(seed)
                    provenance["model"] = STABILITY_CONTROL_MODEL
                    if _scenic_verbatim:
                        # No restyle ran: the Core-composed seed is the hero.
                        provenance["bg_source"] = "scenic-verbatim"
                        provenance["model"] = _SCENIC_MODEL_ID
                    # PART C — deterministic on-brand headline + accent bar ON TOP of the
                    # GenAI hero (Nova Pro still supplies the headline). Default-on for
                    # the legacy ladder; clean contract (#199) keeps the hero clean and
                    # records the line for the copy sidecars instead.
                    try:
                        b_headline = _headline(seed, _caption_future)
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
                # A similarity-gate reject already set its own reason above — keep it.
                if provenance.get("fallthrough_reason") != "similarity-gate":
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
            except _bedrock_fail_tuple as e:
                print(f"[generate] rung B failed -> fall to C: {e}", file=sys.stderr)
                provenance["fallthrough_reason"] = "model-error"
        else:
            # skip straight to C — either the generative rung is disabled (dev) or the
            # budget will not fit B (+C reservation). Keep the reason honest so provenance
            # distinguishes a dev opt-out from a real budget exhaustion.
            if not _STABILITY_RUNG_ON:
                print(
                    "[generate] rung B skipped (stability rung disabled) -> rung C",
                    file=sys.stderr,
                )
                provenance["fallthrough_reason"] = "stability-rung-disabled"
            else:
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
                provenance["seed_local"] = str(seed)
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
    try:
        floor = _brand_floor(product_name, ratio, out_path)
    except OSError as e:
        # Late write failure (read-only dir: the top-of-ladder mkdir probe
        # passed because the dir exists, but the save is denied) — one recorded
        # tmp retry so rung D still lands, never an uncaught 500.
        import tempfile

        print(
            f"[generate] rung D save failed ({out_path}): {e} -> tmp fallback",
            file=sys.stderr,
        )
        out_path = Path(out_path)
        prior = provenance.get("out_dir_degrade")
        requested = str(prior.get("requested")) if isinstance(prior, dict) else str(out_path)
        out_path = Path(tempfile.mkdtemp(prefix="kodiak-hero-")) / out_path.name
        provenance["out_dir_degrade"] = {
            "requested": requested,
            "actual": str(out_path),
            "reason": f"{type(e).__name__}: {e}",
        }
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
    themes: list[str] | str | None = None,
    dish: str | None = None,
    art_director: bool = False,
    market: str | None = None,
    season: str | None = None,
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
    # Request-epoch clock. The base hero call below spends most of the soft budget,
    # so the per-ratio outpaint gates MUST measure from HERE (request start), not
    # from after the base call — PROVEN IN PROD 2026-09-08: a clock reset after the
    # base showed a full 24s remaining with ~10s of wall left, the gate passed a
    # doomed 12s extend, and the wall fired during finalize (rung D).
    _request_start = time.monotonic()

    def _set_remaining_ms() -> float:
        return GENERATE_SOFT_BUDGET_MS - (time.monotonic() - _request_start) * 1000.0

    # Unwritable out_dir degrades to a recorded tmp fallback (same ladder contract
    # as generate_hero) — the set still ships every ratio, never an uncaught 500.
    # Real write probe (not just mkdir): a read-only existing dir passes mkdir
    # but denies saves, so write + delete a sentinel to prove writability.
    _set_out_requested = Path(out_dir)
    _set_probe: dict = {}
    _set_probed = _ensure_writable_out_path(_set_out_requested / ".keep", _set_probe)
    out_dir = _set_probed.parent
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        _sentinel = out_dir / ".writability-probe"
        _sentinel.write_bytes(b"ok")
        _sentinel.unlink()
    except OSError as e:  # noqa: BLE001 — read-only dir: degrade to tmp, never raise
        import tempfile

        print(
            f"[generate] set out_dir not writable ({out_dir}): {e} -> tmp fallback",
            file=sys.stderr,
        )
        out_dir = Path(tempfile.mkdtemp(prefix="kodiak-set-"))
        _set_probe["out_dir_degrade"] = {
            "requested": str(_set_out_requested),
            "actual": str(out_dir),
            "reason": f"{type(e).__name__}: {e}",
        }
    if "out_dir_degrade" in _set_probe:
        _set_probe["out_dir_degrade"]["requested"] = str(_set_out_requested)
        _set_probe["out_dir_degrade"]["actual"] = str(out_dir)
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
        dish=dish,
        idx=0,
        ratio="1x1",
        theme=theme,
        brand_overlay=False,
        paper_overlay=False,
        bare_base=True,
        seed_key=seed_key,
        layers=layers,
        themes=themes,
        market=market,
        season=season,
    )
    provenance["layers"] = provenance_layers
    provenance["clean"] = provenance_layers is not None
    if "out_dir_degrade" in _set_probe:
        provenance.setdefault("out_dir_degrade", _set_probe["out_dir_degrade"])

    # The set headline re-runs the full pipeline (grounded director first, stock
    # Nova normalized second) on the clean base — the base hero call above ran
    # with overlays off and left provenance["headline"] empty, and the old
    # Nova-only helper overwrote grounded provenance with an un-normalized line.
    _voice_report: dict = {}
    headline, headline_source = _headline_for(
        clean_base, product_name, brief_msg, region, audience,
        remaining_ms=_set_remaining_ms, art_director=art_director,
        report=_voice_report, market=market, season=season,
    )
    if isinstance(provenance, dict) and "voice_attempts" in _voice_report:
        provenance["voice_attempts"] = _voice_report["voice_attempts"]
    provenance["headline"] = headline if brand_overlay else None
    provenance["copy_headline"] = provenance.get("copy_headline") or headline
    if headline_source:
        provenance["headline_source"] = headline_source
    provenance["ratios"] = {}
    # Per-ratio outpaint books: measured extend latency + degrade reasons, both
    # JSON-serializable. A slow ratio degrades to the pad — never blows the wall.
    provenance["outpaint_latency_ms"] = {}
    provenance["outpaint_degraded"] = {}
    # The base hero call above already spent most of the soft budget; the per-ratio
    # outpaint gates below reuse the request-epoch _set_remaining_ms defined at
    # function entry, so remaining covers one outpaint PLUS the reserve for
    # pads/overlays against the TRUE wall-clock remainder.

    # Raw subject for the outpaint extend prompt (_stability_outpaint wraps it in
    # the frozen style sandwich). Reuse the base hero's scene prompt so NO extra
    # Bedrock call burns the wall; fall back to the brief when it is absent.
    # Sync the in-season ingredient so apples briefs show apples, not pears/pumpkins.
    _season_ingredient = None
    try:
        from .locales import resolve_this_month as _rtm  # single source of truth for seasonal ingredient

        _resolved = _rtm(region, ym=None)
        if _resolved and _resolved.get("ingredient"):
            _season_ingredient = str(_resolved["ingredient"]).strip()
    except Exception:
        _season_ingredient = None
    _base_subject = str(provenance.get("scene_prompt") or "").strip() or brief_msg
    if _season_ingredient and _season_ingredient.lower() not in _base_subject.lower():
        _base_subject = f"{_base_subject}, featuring {_season_ingredient}"
    _outpaint_subject = _base_subject

    # recipe-cards theme routes each sized hero through the deterministic Pillow card
    # template (_compose_recipe_card): the GenAI hero drops into a fixed image slot and
    # the lower region becomes a token-brand card. Other themes keep the plain brand
    # overlay path unchanged. recipe_fields default from the product name (no brief seam
    # into this function), so the card copy is deterministic and on-brand.
    eff_theme = provenance.get("theme", theme)
    is_recipe_card = eff_theme == "recipe-cards"
    recipe_fields = None
    if is_recipe_card:
        provenance["card_template"] = True
        # LLM-authored card copy when the wall covers it; deterministic default
        # otherwise. Authoring is text-only and cheap, but a slow model must
        # never starve the rung-C reservation — same gate as the caption
        # (_set_remaining_ms is this function's wall clock).
        if _set_remaining_ms() < _CAPTION_BUDGET_MS + _C_RESERVATION_MS:
            print(
                f"[generate] recipe author skipped (budget {_set_remaining_ms():.0f}ms < "
                f"{_CAPTION_BUDGET_MS + _C_RESERVATION_MS}ms) -> default fields",
                file=sys.stderr,
            )
            provenance["recipe_author"] = "default"
            recipe_fields = _recipe_card_defaults(product_name)
        else:
            try:
                authored = _author_recipe_fields(product_name, brief_msg, region)
            except Exception as e:  # noqa: BLE001 — author must never break the set
                print(f"[generate] recipe author raised, using default: {e}", file=sys.stderr)
                authored = None
            if authored is not None:
                provenance["recipe_author"] = "nova"
                recipe_fields = authored
            else:
                provenance["recipe_author"] = "default"
                recipe_fields = _recipe_card_defaults(product_name)

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
            # Variety: each outpaint gets a ratio-specific composition suffix so the
            # 5-size set is not 5 crops of one frame — 9x16 vertical trail/lifestyle,
            # 16x9 wide farmstand/aspen-gold, each still anchored to the same hero subject.
            _ratio_suffix = {
                "9x16": ", vertical composition, lifestyle trail moment, foreground detail",
                "16x9": ", wide panoramic farmstand, aspen gold horizon, open sky negative space",
            }.get(ratio, "")
            _ratio_subject = _outpaint_subject + _ratio_suffix
            ratio_engine = "pillow-outpaint-fallback"
            if not _STABILITY_RUNG_ON:
                # dev opts out of the generative rung: use the deterministic Pillow
                # cover-pad for 9x16/16x9 too (same path 4x5 always uses).
                provenance["outpaint_degraded"][ratio] = "stability-rung-disabled"
                _pillow_outpaint_fallback(clean_base, target_w, target_h, ratio_path)
            elif _set_remaining_ms() < _OUTPAINT_BUDGET_MS + _OUTPAINT_RESERVE_MS:
                provenance["outpaint_degraded"][ratio] = "budget-exhausted"
                _pillow_outpaint_fallback(clean_base, target_w, target_h, ratio_path)
            else:
                _t0 = time.monotonic()
                try:
                    extended = _stability_outpaint(
                        clean_base, target_w, target_h, _ratio_subject, ratio_path
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
    src: Path, product_name: str, brief_msg: str, region: str, audience: str,
    remaining_ms=None, art_director: bool = False, report: dict | None = None,
    market: str | None = None, season: str | None = None,
) -> tuple[str, str | None]:
    """Set headline through the full pipeline (module-level so generate_hero_set
    can reuse it). Returns (headline, headline_source|None): the grounded
    director first, stock Nova normalized second, raw brief last. remaining_ms
    (when the caller has a wall clock) budget-gates the director AND the
    caption fallback.

    Wall repair: the set path used to re-pay the full director cost (embed +
    up to two voice invokes, ~8s) unconditionally — on a cold container after
    a restyle base, director + render alone exceed the 22s wall and the pack
    falls to rung D. Gated like the base-hero _headline: thin budget skips
    straight to caption/brief. The per-container memo still makes the adequate-
    budget second call ~free."""
    directed = None
    if remaining_ms is None:
        directed = _director_headline_text(product_name, brief_msg, region, audience, art_director=art_director, report=report, market=market, season=season)
    else:
        try:
            director_ok = remaining_ms() >= _DIRECTOR_BUDGET_MS + _C_RESERVATION_MS
        except Exception:  # noqa: BLE001 — deadline probe must never gate the voice
            director_ok = True
        if director_ok:
            directed = _director_headline_text(product_name, brief_msg, region, audience, art_director=art_director, report=report, market=market, season=season)
        else:
            try:
                print(
                    f"[director] set-headline skip: budget {remaining_ms():.0f}ms < "
                    f"{_DIRECTOR_BUDGET_MS + _C_RESERVATION_MS}ms",
                    file=sys.stderr,
                )
            except (OSError, ValueError):
                print("[director] set-headline skip (budget log unavailable)", file=sys.stderr)
    if directed:
        sanitized = _sanitize_military_headline(directed)
        if sanitized is None:
            print(f"[director] set-headline military filtered ({directed[:60]!r})", file=sys.stderr)
        else:
            if sanitized != directed:
                print(f"[director] set-headline military stripped: {directed[:60]!r} -> {sanitized[:60]!r}", file=sys.stderr)
                directed = sanitized
            return clean_brand_copy(directed), _DIRECTOR_LIVE_SOURCE
    caption = _caption_with_budget(
        src, product_name, brief_msg, region, audience, remaining_ms=remaining_ms
    )
    headline, _side = _parse_layout(caption)
    if headline:
        normed = _title_case_headline(headline)
        sanitized = _sanitize_military_headline(normed)
        if sanitized is not None:
            return clean_brand_copy(sanitized), "bedrock:nova-pro-caption"
        print(f"[director] set-caption military filtered ({normed[:60]!r})", file=sys.stderr)
    return clean_brand_copy(brief_msg[:48]), None
