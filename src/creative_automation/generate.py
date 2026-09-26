"""Hero image generation — Bedrock Stability image-conditioning on real brand assets.

Precedence (see generate_hero): a real seed asset (theme photo, sku-mapped asset photo,
or disk asset) restyled to the theme by Bedrock Stability control-structure so the
theme lands in the pixels (source bedrock:stability-control-structure); else the same
seed composed by Pillow under Nova Pro art-direction (source bedrock:nova-pro); else a
deterministic on-brand placeholder labelled bedrock:nova-pro-fallback. The word
mock/preview never reaches the UI. Nova Canvas is retired (Legacy) and is not a path.
"""
from __future__ import annotations

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
# Director-voice headline cluster (extracted: owns the code; re-exported here
# so existing importers, tests, and monkeypatch targets keep working).
from .director_voice import (
    _DIRECTOR_LIVE_SOURCE,
    _DIRECTOR_TIMEOUT_S,
    _LAYOUT_INLINE_RE,
    _PREAMBLE_PATTERNS,
    _REFUSAL_PHRASES,
    _director_enabled,
    _director_headline_text,
    _parse_layout,
    _sanitize_military_headline,
    _scrub_director_line,
    _title_case_headline,
    _voice_requested,
)
# Card-compose cluster (extracted: owns the code; re-exported here so
# existing importers and tests keep working).
from .card_compose import (
    _CANVAS,
    _HEADLINE_PX,
    _KRAFT_BASE,
    _accent_hex,
    _compose_recipe_card,
    _hex_to_rgb,
    _scrim_hex,
    _wrap_headline,
)
# Scene-prompt + Nova caption cluster (extracted: owns the code, except
# _caption_with_budget which stays here on the ladder constants).
from .scene_prompts import (
    BEDROCK_NOVA_READ_TIMEOUT_S,
    NOVA_TEXT_MODEL,
    PANEL_FLAG_THEME_MISMATCH,
    _BEAR_LAW_CLAUSE,
    _BEAR_PALETTE_RE,
    _BEAR_TRIGGER_THEMES,
    _BEAR_WORD_RE,
    _IDEA_MARKERS,
    _MONTH_NUM,
    _NOVA_SEED_MAX_SIDE,
    _OVERLAY_MARK_THEMES,
    _RETIRED_PERSONA_MAP,
    _THEME_ASSET_MAP_CACHE,
    _THEME_ASSET_MAP_PATH,
    _THEME_COPY_HINT,
    _THEME_PERSONA_MAP,
    _THEME_SCENE_HINT,
    _bear_law_clause,
    _brief_idea,
    _brief_setting_clause,
    _brief_subject_clause,
    _combo_scene_suffix,
    _default_scene_prompt,
    _load_theme_asset_map,
    _market_scene_clause,
    _normalize_theme_slugs,
    _nova_pro_caption,
    _nova_pro_scene_prompt,
    _resolve_theme_map_path,
    _safe_prompt_text,
    _safe_theme_text,
    _scenic_scene_text,
    _season_month,
    _seed_small_for_nova,
    _with_locale_and_bear,
    combine_themes,
)
# Shared Bedrock data-plane client (extracted: owns the code, including the
# fail-fast constructor — patch bedrock_client, never this re-export).
from . import bedrock_client
from .bedrock_client import (
    BEDROCK_CONNECT_TIMEOUT_S,
    BEDROCK_READ_TIMEOUT_S,
    BEDROCK_REGION,
    _bedrock_failfast_client,
)
# Stability + outpaint rungs (extracted: own the code; re-exported here so
# existing importers and tests keep working).
from .stability_rungs import (
    BEDROCK_OUTPAINT_READ_TIMEOUT_S,
    KODIAK_PALETTE,
    STABILITY_CONTROL_MODEL,
    STABILITY_CONTROL_STRENGTH,
    STABILITY_OUTPAINT_MODEL,
    STABILITY_SEED,
    STYLE_HEAD,
    STYLE_TAIL,
    _BRAND_SCRUB_RE,
    _NATIVE_RATIO_DIMS,
    _STABILITY_MAX_DIM,
    _STABILITY_MIN_DIM,
    _STABILITY_UPSCALE_TO,
    _control_for_brief,
    _pillow_outpaint_fallback,
    _seed_b64_for_stability,
    _stability_control_hero,
    _stability_native_ratio,
    _stability_outpaint,
    _stable_hash_int,
    _style_sandwich,
)

# boto3 lives in bedrock_client (single home): the client binding is read off
# that module at call time so tests patch ONE namespace. Exception classes are
# stable identities — safe to bind here.
from .bedrock_client import (
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    ReadTimeoutError,
    _BotoConfig,
)

# Re-export surface for the extracted clusters above: external importers,
# tests, and monkeypatch targets keep addressing these via generate.
# (Ruff F401 treats __all__ members as re-exports.)
__all__ = [
    "BEDROCK_CONNECT_TIMEOUT_S",
    "BEDROCK_NOVA_READ_TIMEOUT_S",
    "BEDROCK_OUTPAINT_READ_TIMEOUT_S",
    "BEDROCK_READ_TIMEOUT_S",
    "BEDROCK_REGION",
    "BotoCoreError",
    "ClientError",
    "ConnectTimeoutError",
    "KODIAK_PALETTE",
    "NOVA_TEXT_MODEL",
    "PANEL_FLAG_THEME_MISMATCH",
    "ReadTimeoutError",
    "STABILITY_CONTROL_MODEL",
    "STABILITY_CONTROL_STRENGTH",
    "STABILITY_OUTPAINT_MODEL",
    "STABILITY_SEED",
    "STYLE_HEAD",
    "STYLE_TAIL",
    "_BRAND_SCRUB_RE",
    "_BEAR_LAW_CLAUSE",
    "_BEAR_PALETTE_RE",
    "_BEAR_TRIGGER_THEMES",
    "_BEAR_WORD_RE",
    "_BotoConfig",
    "_CANVAS",
    "_DIRECTOR_LIVE_SOURCE",
    "_DIRECTOR_TIMEOUT_S",
    "_HEADLINE_PX",
    "_IDEA_MARKERS",
    "_KRAFT_BASE",
    "_LAYOUT_INLINE_RE",
    "_MONTH_NUM",
    "_NATIVE_RATIO_DIMS",
    "_NOVA_SEED_MAX_SIDE",
    "_OVERLAY_MARK_THEMES",
    "_PREAMBLE_PATTERNS",
    "_REFUSAL_PHRASES",
    "_RETIRED_PERSONA_MAP",
    "_STABILITY_MAX_DIM",
    "_STABILITY_MIN_DIM",
    "_STABILITY_UPSCALE_TO",
    "_THEME_ASSET_MAP_CACHE",
    "_THEME_ASSET_MAP_PATH",
    "_THEME_COPY_HINT",
    "_THEME_PERSONA_MAP",
    "_THEME_SCENE_HINT",
    "_accent_hex",
    "_bear_law_clause",
    "_bedrock_failfast_client",
    "_brief_idea",
    "_brief_setting_clause",
    "_brief_subject_clause",
    "_combo_scene_suffix",
    "_compose_recipe_card",
    "_control_for_brief",
    "_default_scene_prompt",
    "_director_enabled",
    "_director_headline_text",
    "_hex_to_rgb",
    "_load_theme_asset_map",
    "_market_scene_clause",
    "_normalize_theme_slugs",
    "_nova_pro_caption",
    "_nova_pro_scene_prompt",
    "_parse_layout",
    "_pillow_outpaint_fallback",
    "_resolve_theme_map_path",
    "_safe_prompt_text",
    "_safe_theme_text",
    "_sanitize_military_headline",
    "_scenic_scene_text",
    "_scrim_hex",
    "_season_month",
    "_seed_b64_for_stability",
    "_seed_small_for_nova",
    "_scrub_director_line",
    "_stability_control_hero",
    "_stability_native_ratio",
    "_stability_outpaint",
    "_stable_hash_int",
    "_style_sandwich",
    "_title_case_headline",
    "_voice_requested",
    "_with_locale_and_bear",
    "_wrap_headline",
    "combine_themes",
]


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
# Stock-caption reservation (ms): the Nova Pro caption fallback is entered ONLY while
# remaining_ms() still covers its worst-case cost (the fail-fast read timeout) PLUS
# the rung-C reservation. PROVEN IN PROD 2026-09-08: an un-gated caption after a
# 12s director spend burns the silent seconds before rung C and the wall fires
# during finalize. On skip the headline falls to the raw brief (the documented
# third fallback) with a skip log, same as a caption that returns empty.
_CAPTION_BUDGET_MS = int(os.getenv("GENERATE_CAPTION_BUDGET_MS", "7000"))
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
        if bedrock_client.boto3 is None:
            return False
        s3 = bedrock_client.boto3.client("s3")
        dest.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(_RESTYLE_CACHE_BUCKET, key, str(dest))
        return dest.exists() and dest.stat().st_size > 0
    except Exception:  # noqa: BLE001 — cache miss on ANY failure per contract
        return False


def _restyle_cache_put(key: str, src: Path) -> None:
    """Store a fresh restyle. Never raises — cache misses just cost a future restyle."""
    try:
        if bedrock_client.boto3 is None:
            return
        s3 = bedrock_client.boto3.client("s3")
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


# Retired named-person slugs: no chip ships them, but a user can still TYPE the
# name into the brief — and that raw token trips the Stability filter the same
# way. Scrubbed to the same filter-safe persona so free text can never regress
# into a filter trip.


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


# Theme slugs whose direction ships as a logo-mark overlay + copy line, never as
# pixel-prompt scene text (retailer-aisle decision 2026-09-20).


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


# Native delivery frames for the per-ratio diffusion pass: each campaign ratio
# gets its own control-structure restyle composed AT its frame (not derived from
# the 1x1), so the five tiles are five distinct compositions. blog is the
# 1200x630 Open Graph frame (756k px — inside Stability's 4096..9437184 range).
# Sibling invokes get a roomier single-attempt read timeout than the 12s
# fail-fast serial cap: the batch costs one invoke of wall, and a cold model
# needs ~15-20s — 12s would systematically execute every cold sibling.
_NATIVE_READ_TIMEOUT_S = int(os.getenv("GENERATE_NATIVE_READ_TIMEOUT_S", "20"))


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
    if bedrock_client.boto3 is None:
        return None
    try:
        client = bedrock_client._bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
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
        # Issue 308 spend-per-repeat counter: hits = restyles served from the
        # content-addressed cache (free), misses = paid fresh Stability invokes
        # (gate-rejected ones included — the money spent either way). Summed
        # over a session's responses this is the cache hit rate, which decides
        # whether repeat renders are free or full price.
        "restyle_cache": {"hits": 0, "misses": 0},
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
                        provenance["restyle_cache"]["hits"] += 1
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
                            provenance["restyle_cache"]["misses"] += 1
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
                                        # Fan-out mode shares one wall across five
                                        # invokes: the 1x1 also skips its legacy
                                        # retry (a 12s second attempt is what
                                        # breaches the shared wall) and takes the
                                        # roomier single attempt instead. A cold
                                        # miss falls to rung C, never the wall.
                                        try:
                                            return _stability_control_hero(
                                                seed, scene_prompt, _dest,
                                                control_strength=rung_b_strength,
                                                seed_value=request_seed,
                                                retry_once=False,
                                                read_timeout=_NATIVE_READ_TIMEOUT_S,
                                            )
                                        except TypeError:
                                            return _stability_control_hero(seed, scene_prompt, _dest)
                                    return _stability_native_ratio(
                                        seed, scene_prompt, _ratio, _dest,
                                        control_strength=rung_b_strength,
                                        seed_value=None if request_seed is None else request_seed + _idx,
                                        retry_once=False,
                                        read_timeout=_NATIVE_READ_TIMEOUT_S,
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
                            # Issue 308: the fan-out path never consults the
                            # restyle cache, so every landed tile is full price.
                            if _stylized_1x1 is not None and _stylized_1x1.exists():
                                provenance["restyle_cache"]["misses"] += 1
                            provenance["restyle_cache"]["misses"] += sum(
                                1 for _o in _native_outcomes.values()
                                if _o == "stability-restyle-native"
                            )
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
                        if stylized is not None and stylized.exists():
                            provenance["restyle_cache"]["misses"] += 1
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
                                        # The diverge retry is a second paid
                                        # invoke (the too-close first attempt
                                        # was already counted at its site).
                                        provenance["restyle_cache"]["misses"] += 1
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
                    # Frame truth: the restyle returns the SEED's dims, not the
                    # ratio frame — cover-fit to _CANVAS[ratio] AFTER the
                    # similarity gate judged (gate needs same-dims pixels) so
                    # the shipped file matches the ratio the response claims.
                    try:
                        _cw, _ch = _CANVAS.get(ratio, _CANVAS["1x1"])
                        _styl = Path(stylized)
                        try:
                            _same = _styl.resolve() == Path(seed).resolve()
                        except (OSError, ValueError):
                            _same = False
                        if _same:
                            # scenic-verbatim: the seed IS the pixels — copy to
                            # out_path before framing so the cached seed photo
                            # is never mutated by the cover-fit.
                            Image.open(_styl).convert("RGB").save(out_path, "PNG")
                            _styl = Path(out_path)
                            stylized = _styl
                        _fit_src = Image.open(_styl).convert("RGB")
                        if _fit_src.size != (_cw, _ch):
                            ImageOps.fit(
                                _fit_src, (_cw, _ch), method=Image.BICUBIC
                            ).save(_styl, "PNG")
                    except Exception as e:  # noqa: BLE001 — a fit failure keeps pixels over dims
                        print(f"[generate] rung B canvas fit skipped: {e}", file=sys.stderr)
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
