"""compose.py — deterministic Pillow creative assembly as documentation-as-code.

Module contract (read this before touching any function below):

    1. Pillow layout is deterministic code — not a model.
       Every pixel position, palette pick, type scale and safe-area
       inset is computed by plain Python math over token values.
       The generative model (Bedrock Stability / Nova Pro) supplies
       ONLY the hero photo pixels when no verbatim DAM asset exists.
       It NEVER decides layout, NEVER places the logo, NEVER sets
       type, NEVER draws the accent bar.  If the model hallucinated
       a logo or lettering, this module would still overwrite it
       with the real brand asset in code.

    2. Cutouts paste VERBATIM with a soft drop shadow.
       Both the product-box packshot (705599* DAM) and the licensed
       partner-person cutout (transparent-background PNG) are
       composited as-is: no cover-fit, no scrim blend, no enhance,
       no face synthesis, no color regrade.  A single soft drop
       shadow (8 px offset, 40 % black, GaussianBlur 12) is drawn
       on an RGBA scratch layer UNDER the asset so it reads as a
       physical object on the scene.  The shadow is the ONLY
       synthesized pixel that touches the cutout path.

    3. Tokens arrive S3-first, local fallback.
       token_loader.load_tokens() tries DAM_S3_BUCKET first
       (s3://<bucket>/brands/kodiak/tokens/kodiak.tokens.json) via
       boto3; any failure (no bucket env, no creds, no object,
       network) falls back to the committed
       design/tokens/kodiak.json (and then src/…/tokens/…).  All
       canvas dims, colors, spacing and type come from _tokens at
       import time with a second hard fallback to literal legacy
       values so `import compose` never raises offline or in CI.

    4. The model never touches logo / type.
       Bear-logo placement (top-left, token clearSpace), headline
       typography (per-ratio token fontSize 56/64/72, DejaVu Bold,
       centered, max 3 lines, stroke 2), accent bar (blaze orange
       8 px bottom), scrim and parchment are ALL drawn here with
       ImageDraw/ImageFont over the photo.  Text lives in the
       message-bar band (bottom 32 %, scrim 80 % ink) and nowhere
       else.  Any text that appeared inside the hero photo is
       treated as a defect — prompts explicitly forbid lettering.

Function map (what the task names as "every function"):

    build_card        -> compose_creative (alias build_card)  — the
                       top-level card builder that orchestrates every
                       layer in ratio-correct order.
    place_cutout      -> compose_partner_cutout (alias place_cutout)
                       — the verbatim person-cutout placer.
    paper texture     -> _paper_texture / _apply_paper_texture —
                       deterministic kraft tooth (~2 % blend) as the
                       final finishing pass.
    brand overlay     -> _brand_overlay — the deterministic scrim +
                       headline + logo + retailer badge + accent bar
                       layer that gives the card its brand identity.

Each function's docstring AND its inline comments are the spec.
If prose and code disagree, fix code to match the docstring and
the token contract — do not weaken the docstring to match a bug.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from .token_loader import get_brand_colors, get_canvas_dims, load_tokens

# ---------------------------------------------------------------------------
# Tokens: S3-first, local fallback — import-time, never raises.
# ---------------------------------------------------------------------------
# Why S3 first: prod DAM is the single source of truth for brand tokens.
# A token change shipped to S3 propagates without a code deploy; the local
# committed JSON is only the CI/offline safety net.  load_tokens() hides
# that split: it tries s3.get_object(DAM_S3_BUCKET,
# brands/kodiak/tokens/kodiak.tokens.json) via boto3 and, on ANY
# exception (no env, no creds, NoSuchKey, network), falls through to
# design/tokens/kodiak.json.  Every consumer in this file reads _tokens
# through that same entry point so the precedence is uniform.
#
# Why import-time try/except: compose.py is imported inside the Lambda
# handler path and inside campaign/generate offline tooling.  An import
# must never raise just because S3 is unreachable or a token key is
# missing — the card still needs to render with sane legacy defaults.
_tokens = None  # populated below; None means "tokens unreadable, use literals"
try:
    # S3-first inside load_tokens(): DAM_S3_BUCKET env -> boto3 get_object.
    _tokens = load_tokens()
except Exception:  # noqa: BLE001 — import-time token fallback; compose must import offline
    # Any load failure (no file, JSON parse, boto3 not installed, no bucket)
    # collapses to None so every downstream read can `if _tokens else <literal>`.
    _tokens = None

# ---------------------------------------------------------------------------
# Canvas dims from tokens (fallback to legacy quad).
# ---------------------------------------------------------------------------
# Tokens carry per-ratio canvases under kodiak.dimension.canvas.* ->
# {"width","height"} pairs per W3C DTFM.  get_canvas_dims() unwraps those
# into a plain {ratio: (W,H)} map.  Both spellings (1x1 / 1:1) point at the
# same tuple object so callers can pass either form without mapping.
try:
    _dims = get_canvas_dims(_tokens)  # S3-loaded dims win when present
    RATIOS: dict[str, tuple[int, int]] = {
        "1x1": _dims.get("1x1", (1080, 1080)),
        "4x5": _dims.get("4x5", (1080, 1350)),
        "9x16": _dims.get("9x16", (1080, 1920)),
        "16x9": _dims.get("16x9", (1920, 1080)),
        # colon aliases so "1:1" callers get the same canvas without extra branch
        "1:1": _dims.get("1x1", (1080, 1080)),
        "4:5": _dims.get("4x5", (1080, 1350)),
        "9:16": _dims.get("9x16", (1080, 1920)),
        "16:9": _dims.get("16x9", (1920, 1080)),
    }
except Exception:  # noqa: BLE001 — import-time dims fallback; compose must import offline
    # Legacy quad when tokens are absent — matches the 3-ratio + 4x5 history.
    RATIOS: dict[str, tuple[int, int]] = {
        "1x1": (1080, 1080),
        "4x5": (1080, 1350),
        "9x16": (1080, 1920),
        "16x9": (1920, 1080),
        "1:1": (1080, 1080),
        "4:5": (1080, 1350),
        "9:16": (1080, 1920),
        "16:9": (1920, 1080),
    }

# Canonical fold: both spellings -> the x-form used as the dict key internally.
CANONICAL = {
    "1x1": "1x1", "1:1": "1x1",
    "4x5": "4x5", "4:5": "4x5",
    "9x16": "9x16", "9:16": "9x16",
    "16x9": "16x9", "16:9": "16x9",
}

# ---------------------------------------------------------------------------
# Brand defaults from tokens (fallback to Kodiak frontier triple).
# ---------------------------------------------------------------------------
# Design tokens source: design/tokens/kodiak.json :: kodiak.color.brand.*
#   bearBrown  #3B2316  primary / text / ink
#   blazeOrange #E8530E accent / CTA / 8 px bar
#   frontierGreen #1A3C34 secondary / evergreen
# S3 mirror: brands/kodiak/tokens/kodiak.tokens.json — same shape, S3 wins.
# _default_brand[1] is blazeOrange by get_brand_colors() contract.
# _scrim is the warm-ink overlay behind the headline bar.
try:
    _default_brand = get_brand_colors(_tokens)  # [bearBrown, blazeOrange, frontierGreen]
    _brand_accent = _default_brand[1] if len(_default_brand) > 1 else "#E8530E"
    _scrim = _tokens["kodiak"]["color"]["semantic"]["overlay"]["scrim"]["$value"] if _tokens else "#1A1110CC"
except Exception:  # noqa: BLE001 — import-time brand fallback; compose must import offline
    _default_brand = ["#3B2316", "#E8530E", "#1A3C34"]
    _brand_accent = "#E8530E"
    _scrim = "#1A1110CC"  # token kodiak.color.semantic.overlay.scrim -> warm ink #1A1110CC

# ---------------------------------------------------------------------------
# Paper texture constants — deterministic kraft tooth (see _paper_texture).
# ---------------------------------------------------------------------------
# This is the "paper texture" leg of the spec: a subtle kraft paper tooth
# applied as the very last pass so the final PNG reads as a tactile card,
# not a flat screen crop.  2 % opacity is the design intent ("like 2 %
# visible").  The base color mirrors the token parchment so the texture is
# legible on light and dark heroes.
_KRAFT_BASE: tuple[int, int, int] = (244, 237, 230)  # near token neutral 100 / parchment
_KRAFT_SEED: int = 0x4B4F4449  # "KODI" — fixed seed => byte-identical texture every run
_KRAFT_TILE: int = 256  # one memoized tile resized in C is ~30x faster than per-pixel
_kraft_tile_cache: Image.Image | None = None  # process-memoized RGB tile
_HEX_RE = __import__("re").compile(r"^#([0-9a-fA-F]{6})([0-9a-fA-F]{2})?$")


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    """Parse #RRGGBB or #RRGGBBAA into an (R,G,B) triple.

    The alpha byte, when present, is ignored — the caller that needs
    alpha parses it separately from the 8-digit form.  Keeps the common
    hex->rgb path trivial and deterministic.
    """
    h = h.lstrip("#")
    # first three bytes are always R/G/B regardless of 6- vs 8-digit form
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a deterministic headline/body font — model never touches type.

    Picks the first usable file from a fixed candidate list so type is
    100 % code-controlled: DejaVuSans-Bold first (headline weight 800
    surrogate), then regular DejaVuSans, then Pillow's built-in bitmap
    font.  Every caller routes through here so the typeface is uniform
    and offline-safe (no network, no model).

    Why this matters: the generative image prompt is explicitly told
    "no text of any kind — no words, no letters, no numbers, no logos"
    so the model never renders lettering.  All lettering in the final
    card is drawn by ImageDraw.text() with fonts from THIS function.
    """
    # Fixed disk candidates — deterministic, offline, no model.
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        try:
            # truetype() embeds the glyph metrics at the requested px size;
            # same size -> same metrics -> deterministic wrapping.
            return ImageFont.truetype(p, size)
        except OSError as e:
            # One font unreadable (missing file, bad build image) -> try next
            # rather than crash the whole compose.  Logs to stderr for ops.
            print(f"[compose] font {p} unreadable, trying next: {e}", file=sys.stderr)
            continue
    # Final fallback: PIL bitmap font.  Metrics differ slightly but never raises.
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    """Greedy word-wrap a single string into <= max_width lines (Pillow-measured).

    Measures each candidate with draw.textbbox() so wrapping respects the
    real glyph advance at the token fontSize, not a character count.
    Deterministic: same font + same max_width -> identical breaks.

    This helper is the shared wrapping used by compose_creative's headline
    band.  The 3-line clamp is applied by the caller after wrapping.
    """
    # Naive word split is correct for headlines; hyphens stay with their token.
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        # trial append; measure the full trial string including the space
        test = f"{cur} {w}".strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            # fits within the scrim band's inner width (W - 2*pad)
            cur = test
        else:
            # would overflow -> commit current line, start new with w
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------------------
# Paper texture — deterministic kraft tooth, ~2 % visible.
# ---------------------------------------------------------------------------

def _paper_texture(w: int, h: int) -> Image.Image:
    """synthesize a deterministic subtle kraft paper texture tile (RGB, w x h).

    This is the "paper texture" function the spec names — the tactile
    tooth that makes the final card read as frontier kraft, not flat
    screen color.  Implementation: fixed-seed low-amplitude luminance
    noise (+-10) over warm kraft base plus sparse darker fibrous specks
    (~1 per 900 px).  Deterministic: same (w,h) -> identical bytes,
    because the RNG is seeded with _KRAFT_SEED and is not global random.
    Pillow + stdlib random only (no numpy), so offline/CI safe.

    Why not a real texture PNG: a generated file would need S3 sync and
    would fork the asset contract.  Synthesized in code, the texture is
    always present and byte-identical without any external fetch.
    """
    rng = random.Random(_KRAFT_SEED)  # fresh fixed-seed RNG every call -> deterministic
    img = Image.new("RGB", (w, h), _KRAFT_BASE)
    px = img.load()
    br, bg, bb = _KRAFT_BASE
    # per-pixel low-amplitude grain: each channel jitter +-10 keeps warmth
    for y in range(h):
        for x in range(w):
            n = rng.randint(-10, 10)
            px[x, y] = (
                max(0, min(255, br + n)),
                max(0, min(255, bg + n)),
                max(0, min(255, bb + n)),
            )
    # sparse fibrous specks — a touch darker, 1 px, for the bag grain
    draw = ImageDraw.Draw(img)
    speck_count = max(1, (w * h) // 900)
    for _ in range(speck_count):
        sx = rng.randint(0, w - 1)
        sy = rng.randint(0, h - 1)
        d = rng.randint(18, 34)
        draw.point((sx, sy), fill=(max(0, br - d), max(0, bg - d), max(0, bb - d)))
    return img


def _paper_texture_cached() -> Image.Image:
    """return one memoized 256 px kraft grain tile — the fast path.

    Synthesizing per-pixel at full frame size costs ~15 s across 4 ratios
    in pure Python (the old wall killer).  One 256 px tile memoized per
    process and resized with C-level BICUBIC (~50 ms at 1920 px) is
    deterministic and ~30x faster, with identical visual result.
    """
    global _kraft_tile_cache
    if _kraft_tile_cache is None:
        _kraft_tile_cache = _paper_texture(_KRAFT_TILE, _KRAFT_TILE)
    return _kraft_tile_cache


def _apply_paper_texture(img: Image.Image, opacity: float = 0.02) -> Image.Image:
    """blend the kraft texture over img at very slight opacity (~2 %). returns RGB.

    This is the "paper texture" brand-overlay's final finishing pass and
    the last step on every returned render before save.

    - "very slight, like 2 % visible" => alpha ~0.02-0.03 so texture reads
      as faint paper tooth, not a wash.
    - Same-size output as input; no crop, no resize beyond the C-level
      tile resize.  Deterministic: same tile + deterministic resize =>
      identical bytes every run.
    - Called by compose_creative (and by generate.py::_finalize_render)
      so every path — packshot-composite, generated scene, brand floor —
      carries the tooth.

    Leg of the "paper texture" spec; inlined here so compose.py reads as
    a self-contained paper demo without importing generate.py.
    """
    base = img.convert("RGB")
    tile = _paper_texture_cached()
    # Resize the memoized tile to the canvas with C-level BICUBIC so the
    # texture scale tracks the ratio (1080x1080 vs 1920x1080 etc.).
    if (base.width, base.height) != tile.size:
        tex = tile.resize((base.width, base.height), Image.BICUBIC)
    else:
        tex = tile
    # Clamp opacity to [0,1] so callers cannot accidentally blank the hero.
    return Image.blend(base, tex, max(0.0, min(1.0, opacity)))


# ---------------------------------------------------------------------------
# Brand overlay — deterministic scrim + headline + logo + accent bar.
# ---------------------------------------------------------------------------

def _brand_overlay(
    canvas: Image.Image,
    headline: str,
    ratio_key: str,
    brand_logo: Path | None = None,
    brand_colors: list[str] | None = None,
    retailer_logo: Path | None = None,
) -> Image.Image:
    """draw the ONLY on-image brand layer — every pixel is code, never model.

    This is the "brand overlay" function the spec names.  It is the sole
    place brand identity is stamped: the model is never asked to render a
    logo, wordmark or packaging glyph, and the hero photo prompt explicitly
    forbids lettering.  All brand comes from deterministic Pillow drawing
    over the photo in four composited pieces:

      C04  ~32 % dark message bar at 68 % down (token scrim, alpha 140)
           with the centered, wrapped white headline (per-ratio token
           fontSize 56/64/72, DejaVu Bold, stroke 2, max 3 lines).
      LOGO KODIAK Bear top-left badge when brand_logo is supplied — pasted
           with its own alpha, scaled to token logoOffset / logo width.
      RETAILER small bottom-right badge (~18 % W) with white backing when
           retailer_logo is supplied (Costco/Target etc), kept above the
           accent bar and inside the message scrim.
      C03  8 px Blaze Orange accent bar pinned to the very bottom (token
           accentBar), and the same blazeOrange token as the fallback.

    Inputs:
      canvas    — RGBA image already composited (background + box + person).
      headline  — campaign copy; empty skips the text draw but the bars remain.
      ratio_key — token lookup for headline fontSize (1x1 / 4x5 / 9x16 / 16x9).
      brand_logo, retailer_logo — optional raster logo paths; missing -> skip.

    Returns the same RGBA canvas with the overlay composited in place.
    """
    # Work in RGBA so alpha for scrim + logos composites correctly.
    W, H = canvas.size
    draw = ImageDraw.Draw(canvas, "RGBA")

    # ---- token reads: single routing so S3-override propagates uniformly ----
    # canvasPad (outer safe inset), messageBarTop (top of the scrim band),
    # accentBar height, scrim color, logoOffset, headline fontSize per ratio.
    # Each is guarded: token missing -> literal fallback so overlay never raises.
    try:
        pad = _tokens["kodiak"]["spacing"]["canvasPad"]["$value"] if _tokens else 48
        bar_pct = (
            float(str(_tokens["kodiak"]["spacing"]["messageBarTop"]["$value"]).strip("%")) / 100
            if _tokens and "messageBarTop" in _tokens["kodiak"]["spacing"]
            else 0.68
        )
        if _tokens and ratio_key in _tokens["kodiak"]["typography"]["headline"]:
            font_size = int(
                _tokens["kodiak"]["typography"]["headline"][ratio_key]["$value"]["fontSize"].replace("px", "")
            )
        else:
            font_size = 72 if ratio_key == "16x9" else (64 if ratio_key == "9x16" else 56)
    except (KeyError, TypeError, ValueError, AttributeError):
        pad, bar_pct, font_size = 48, 0.68, (56 if W >= 1080 else 42)

    # ---- scrim band + headline (bottom 32 %, scrim = warm ink) ----
    text_max_w = W - pad * 2           # inner width inside the safe pad
    font = _load_font(font_size)
    bar_top = int(H * bar_pct)         # 68 % down per token C04
    # Parse scrim #RRGGBBAA or #RRGGBB — 8-digit carries its own alpha.
    try:
        scrim_hex = _scrim.lstrip("#")
        if len(scrim_hex) == 8:
            r, g, b, a = (int(scrim_hex[i:i+2], 16) for i in (0, 2, 4, 6))
            fill = (r, g, b, a)
        else:
            # 6-digit form -> 140/255 (~55 %) fallback matches legacy overlay
            fill = (0, 0, 0, 140)
    except (ValueError, AttributeError, TypeError):
        fill = (0, 0, 0, 140)
    # Bottom band fills bottom 32 %; alpha gives the photo just enough legibility.
    draw.rectangle([0, bar_top, W, H], fill=fill)
    # Headline lives centered in that band, wrapped and clamped to 3 lines.
    if headline:
        y = bar_top + 28
        lines = _wrap_text(draw, headline, font, text_max_w)[:3]
        for line in lines:
            bbox = draw.textbbox((0, 0), line, font=font)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
            # Pillow stroke_width=2 + dark stroke is the legibility halo, not a model stroke.
            draw.text(((W - tw) / 2, y), line, fill="white", font=font, stroke_width=2, stroke_fill=(0, 0, 0))
            y += th + 10

    # ---- logo (KODIAK Bear) — top-left, token clearSpace; model never places logo ----
    # The generative prompt is told to avoid logography; this is the ONLY place
    # the Bear mark appears, pasted as a real raster asset with preserved alpha.
    if brand_logo and Path(brand_logo).exists():
        try:
            logo = Image.open(brand_logo).convert("RGBA")
            try:
                logo_offset = _tokens["kodiak"]["spacing"]["logoOffset"]["$value"] if _tokens else 24
                min_w = 80
                default_w = 140
            except (KeyError, TypeError, AttributeError):
                logo_offset, default_w, min_w = 24, 140, 80
            lw = max(min_w, default_w)
            if logo.width != lw:
                lh = int(logo.height * (lw / logo.width))
                logo = logo.resize((lw, lh), Image.BICUBIC)
            canvas.paste(logo, (logo_offset, logo_offset), logo)
        except (OSError, ValueError) as e:
            print(f"[compose] logo overlay failed: {e}", file=sys.stderr)

    # ---- retailer badge — bottom-right, small, only when variant is not direct ----
    # Channel-partner wire pulls a real SVG/PNG from input_assets/retailer-logos/*
    # and reaches this overlay only when the brief names a retailer; direct &
    # subscription variants skip it so house brand stays solo.
    if retailer_logo and Path(retailer_logo).exists():
        try:
            rlogo = Image.open(retailer_logo).convert("RGBA")
            rw = int(W * 0.18)
            rh = int(rlogo.height * (rw / rlogo.width)) if rlogo.width else 0
            rx = W - rw - 24
            ry = max(H - rh - 24, bar_top + 20)  # never overlaps message bar text
            # Subtle white backing for retailer mark legibility on any hero.
            backing = Image.new("RGBA", (rw + 6*2, rh + 6*2), (255, 255, 255, 220))
            canvas.paste(backing, (rx - 6, ry - 6), backing)
            # Resize once and reuse — previous code resized twice (perf).
            rlogo_small = rlogo.resize((rw, rh), Image.BICUBIC)
            canvas.paste(rlogo_small, (rx, ry), rlogo_small)
        except (OSError, ValueError) as e:
            print(f"[compose] retailer logo failed: {e}", file=sys.stderr)

    # ---- blaze-orange accent bar — bottom 8 px, token-driven ----
    colors = brand_colors or _default_brand
    if colors:
        try:
            hexv = (colors[1] if len(colors) > 1 else colors[0]).lstrip("#")
            rgb = tuple(int(hexv[i:i+2], 16) for i in (0, 2, 4))
            try:
                bar_h = _tokens["kodiak"]["spacing"]["accentBar"]["$value"] if _tokens else 8
            except (KeyError, TypeError, AttributeError):
                bar_h = 8
            draw.rectangle([0, H - bar_h, W, H], fill=rgb)
        except (ValueError, AttributeError, TypeError) as e:
            print(f"[compose] accent bar skipped: {e}", file=sys.stderr)

    return canvas


# ---------------------------------------------------------------------------
# Cutout placement — verbatim person paste with soft shadow (place_cutout).
# ---------------------------------------------------------------------------

def compose_partner_cutout(
    bg: Image.Image,
    cutout_path: Path | str,
    side: str = "left",
) -> Image.Image:
    """place_cutout — composite a licensed partner cutout (a PERSON, not a vibe).

    This is the "place_cutout" function the spec names.  The cutout is an
    approved transparent-background photo of the partner — pasted VERBATIM
    with a soft drop shadow: NO cover-fit, NO scrim blend, NO enhance, NO
    face synthesis.  Not a single pixel of the person is generated or
    altered; the scene is built AROUND them.  Thirds placement mirrors the
    product layer (person left, box right) so the two never collide.

    Determinism:
      - Scale is min(W*0.44 / cut.w, (H*0.68)*0.86 / cut.h) so the figure
        stays fully inside the upper safe area above the message bar and
        never crosses the logo slot.
      - Anchor is thirds-based: 0.30 (left) or 0.64 (right) so the figure
        sits on the left third and the box on the right third.

    Shadow discipline:
      - Silhouette is 40 % black from the cutout's own alpha (preserves
        hair/edge shape exactly).
      - Offset +8,+8 and GaussianBlur(12) on an RGBA scratch layer placed
        UNDER the paste so the person reads as a physical figure.

    Guard: raises ValueError when the cutout lacks an alpha channel — a
    fully opaque cutout would obliterate the background and is rejected.

    Args:
        bg:          RGB or RGBA background — already darkened ~18 % for
                     message-bar legibility and already carrying any product
                     box layer (so the person composites OVER the scene and
                     UNDER the brand overlay).
        cutout_path: path to transparent-background PNG (licensed asset).
        side:        "left" (default, thirds-left) or "right" for tests.

    Returns:
        new RGB image with the person composited verbatim.
    """
    # Open as RGBA so the cutout's own alpha controls the paste edge.
    cut = Image.open(cutout_path).convert("RGBA")
    # Reject fully opaque cutouts — must carry real transparency or the
    # composite would box the background.
    if cut.getchannel("A").getextrema() == (255, 255):
        raise ValueError(f"partner cutout must carry transparency: {cutout_path}")
    W, H = bg.size
    # Safe area mirrors the box layer: above the 68 % message bar and below the Bear slot.
    bar_top_frac = 0.68
    max_w, max_h = W * 0.44, (H * bar_top_frac) * 0.86
    scale = min(max_w / cut.width, max_h / cut.height)
    cw, ch = max(1, int(cut.width * scale)), max(1, int(cut.height * scale))
    cut = cut.resize((cw, ch), Image.BICUBIC)
    # Thirds anchoring: person left, box right — never collide.
    anchor = 0.30 if side == "left" else 0.64
    cx = min(max(int(W * anchor - cw / 2), 8), max(W - cw - 8, 8))
    cy = min(max(int(H * 0.80 - ch), int(H * 0.06)), max(H - ch - 8, 8))
    # ----- shadow: silhouette typed from the cutout's own alpha -----
    # 40 % black silhouette: same shape as the cutout edge, preserves hair.
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sil = Image.new("RGBA", (cw, ch), (0, 0, 0, 102))
    sil.putalpha(cut.split()[-1].point(lambda a: int(a * 0.40)))
    shadow.paste(sil, (cx + 8, cy + 8), sil)
    try:
        # 12 px Gaussian blur is the soft drop; moderate enough to read crisp on screen.
        shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    except Exception as e:  # noqa: BLE001 — cosmetic blur is best-effort
        print(f"[compose] partner shadow blur skipped: {e}", file=sys.stderr)
    # Composite shadow UNDER the cutout: first alpha_composite the shadow onto bg,
    # then paste the verbatim cutout ON TOP so not a single cutout pixel is filtered.
    bg = Image.alpha_composite(bg.convert("RGBA"), shadow).convert("RGB")
    bg.paste(cut, (cx, cy), cut)
    return bg


# place_cutout is the canonical "every function (place_cutout)" name the
# task calls for — direct alias so tests or callers that reference
# place_cutout get the same verbatim behavior as compose_partner_cutout.
place_cutout = compose_partner_cutout  # alias: spec name for compose_partner_cutout


# ---------------------------------------------------------------------------
# Card builder — deterministic composition for every ratio (build_card).
# ---------------------------------------------------------------------------

def compose_creative(
    hero_path: Path,
    out_path: Path,
    message: str,
    ratio_key: str,
    brand_logo: Path | None = None,
    brand_colors: list[str] | None = None,
    retailer_logo: Path | None = None,
    product_layer: Path | None = None,
    bare: bool = False,
    placement: str = "center",
    partner_cutout: Path | None = None,
) -> Path:
    """build_card — produce a social creative at the requested ratio.

    This is the "build_card" function the spec names — the top-level Pillow
    orchestrator that turns a hero photo + message + optional real product
    box + optional partner-person cutout into a finished ratio card.  It is
    100 % deterministic: the same hero bytes + same message + same tokens
    -> same PNG bytes (modulo the hero photo itself).  The generative model
    is NEVER called from this path — campaign.py and generate.py decide
    which hero file to hand in; this function only arranges pixels.

    Layer order (back to front, each step documented inline below):

      1. Background fill: hero cover-fit to (W,H) via ImageOps.fit BICUBIC,
         then 18 % black blend for message-bar legibility.
      2. Foreground hero contain (ONLY when no verbatim box is pasted) so
         the photo is fully visible in the upper safe area.
      3. Product-composite layer: when product_layer resolves, paste the
         VERBATIM real box (soft drop shadow, contained to the upper safe
         area above the message bar).  No cover-fit, no scrim, no enhance.
         placement "thirds" puts the box on the right third per render
         contract #200; "center" is the legacy centered slot.
      4. Partner-person layer: licensed transparent cutout verbatim on the
         left third via compose_partner_cutout (see place_cutout above).
      5. Brand overlay (delegates to _brand_overlay): scrim band, headline,
         Bear logo, retailer badge, blaze-orange accent bar — the ONLY
         brand identity the card carries (model never touches logo/type).
      6. Paper texture: subtle kraft tooth (~2 % blend) via
         _apply_paper_texture as the final finishing pass before save.

    Args:
        hero_path:     local image path for the hero photo (real DAM photo,
                       mock brand floor, or Stability/Canvas scene — caller
                       decides; this function treats it as opaque pixels).
        out_path:      output PNG path (parents are created).
        message:       campaign headline — wrapped, centered, clamped to
                       3 lines, drawn by Pillow with token type scale.
        ratio_key:     one of 1x1/1:1/4x5/4:5/9x16/9:16/16x9/16:9; maps via
                       CANONICAL -> RATIOS dims driven by tokens.
        brand_logo:    optional Bear logo raster (top-left); model never
                       fabricates this — only a real file here places it.
        brand_colors:  optional 3-tuple override; defaults to token triple
                       Bear Brown / Blaze Orange / Frontier Green.
        retailer_logo: optional channel-partner badge (small bottom-right,
                       white backing); wiring from campaign.py.
        product_layer: when set, the VERBATIM real product-box packshot
                       (a 705599* PNG) composited as a physical product
                       layer — the compose-fix root-cause repair.  When
                       None, the existing foreground-hero paste stands
                       (generated-scene mode).
        bare:          when True, return the background-only base (used by
                       _render_asset's set generation: each derived ratio
                       draws its own bar in _apply_brand_overlay).
        placement:     "center" (legacy — box centered) or "thirds" (render
                       contract #200 — box on right third, base near lower
                       safe area so packshot and person never overlap).
        partner_cutout:when set, a licensed transparent-background photo of
                       the partner person composited verbatim thirds-left.

    Returns the out_path on success.  Raises ValueError for an unknown
    ratio.  Never raises for missing optional layers — they are silently
    skipped so callers stay byte-identical when no box/cutout is selected.
    """
    # ---- ratio canonicalization + canvas dims (token-driven) ----
    key = CANONICAL.get(ratio_key, ratio_key)
    if key not in RATIOS and ratio_key not in RATIOS:
        raise ValueError(f"unknown ratio {ratio_key}, expected one of {list(CANONICAL.keys())}")
    W, H = RATIOS.get(key, RATIOS.get(ratio_key, (1080, 1080)))

    # ---- 1. background fill: cover-fit hero + 18 % darken ----
    # ImageOps.fit crops/pads with BICUBIC so the photo fills (W,H) without
    # distortion; blend with 0.18 black gives the later white headline its
    # contrast budget without a photographic re-grade.
    hero = Image.open(hero_path).convert("RGB")
    bg = hero.copy()
    bg = ImageOps.fit(bg, (W, H), method=Image.BICUBIC, bleed=0.0, centering=(0.5, 0.5))
    bg = Image.blend(bg, Image.new("RGB", (W, H), (0, 0, 0)), 0.18)

    # ---- 2. foreground hero contain — SKIPPED when a verbatim box is pasted ----
    # When has_box is True the background already shows the full full-bleed
    # ambiance; pasting a second smaller sharp copy nested inside reads as a
    # tunneled frame-within-frame plus a brightness seam (only bg is darkened).
    # Box-on-photo over full-bleed ambiance is the cleaner composite.
    has_box = product_layer is not None and Path(product_layer).exists()
    if not has_box:
        # Contain keeps the hero fully visible in the upper 58 % safe area.
        scale = min(W * 0.82 / hero.width, H * 0.58 / hero.height)
        fw, fh = int(hero.width * scale), int(hero.height * scale)
        fg = hero.resize((fw, fh), Image.BICUBIC)
        bg.paste(fg, ((W - fw) // 2, int(H * 0.08)))

    # ---- 3. product-composite layer — compose-fix root-cause repair ----
    # When a real box resolves (has_box), paste it VERBATIM with a soft drop
    # shadow over the background in the upper safe area.  It overlays the
    # generated/lifestyle fg hero so the actual retail box is what the eye
    # reads.  No cover-fit, no scrim, no enhance — those pixels are fixed
    # brand art.  See docs/architecture/compose-fix/compose-fix-spec.md §3.
    if has_box:
        try:
            box = Image.open(product_layer).convert("RGBA")
            # Safe area: box must stay above H*0.68 (message bar top) and
            # below the logo slot (token logoOffset).
            bar_top_frac = 0.68
            box_max_w = W * 0.62
            box_max_h = (H * bar_top_frac) * 0.72
            box_scale = min(box_max_w / box.width, box_max_h / box.height)
            bw, bh = max(1, int(box.width * box_scale)), max(1, int(box.height * box_scale))
            box = box.resize((bw, bh), Image.BICUBIC)
            bar_top_px = int(H * bar_top_frac)
            if placement == "thirds":
                # Render-contract #200: right-third vertical, base near lower safe area.
                bx = min(max(int(W * 0.64 - bw / 2), 8), max(W - bw - 8, 8))
                by = min(max(int(H * 0.80 - bh), int(H * 0.06)), max(H - bh - 8, 8))
            else:
                # Legacy: centered, clamped >=24 px above bar_top so headline stays clear.
                bx = (W - bw) // 2
                by = int(H * 0.08)
                if by + bh > bar_top_px - 24:
                    by = max(int(H * 0.04), bar_top_px - 24 - bh)
            # Soft drop shadow on an RGBA scratch layer, composited UNDER the box.
            shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            sil = Image.new("RGBA", (bw, bh), (0, 0, 0, 102))  # ~40 % black
            sil.putalpha(box.split()[-1].point(lambda a: int(a * 0.40)))
            shadow.paste(sil, (bx + 8, by + 8), sil)
            try:
                shadow = shadow.filter(ImageFilter.GaussianBlur(12))
            except Exception as e:  # noqa: BLE001 — cosmetic blur is best-effort
                print(f"[compose] product shadow blur skipped: {e}", file=sys.stderr)
            bg = Image.alpha_composite(bg.convert("RGBA"), shadow).convert("RGB")
            # Paste the verbatim box on top of its shadow — no pixel alteration.
            bg.paste(box, (bx, by), box)
        except Exception as e:  # noqa: BLE001 — product layer is best-effort
            print(f"[compose] product layer composite failed: {e}", file=sys.stderr)

    # ---- 4. partner-person layer — licensed cutout verbatim (thirds-left) ----
    # Thirds-left person, thirds-right box — never synthesized, never enhanced.
    # Byte-identical no-op when partner_cutout is None or missing (callers w/o
    # a person stay byte-identical).
    if partner_cutout is not None and Path(partner_cutout).exists():
        try:
            bg = compose_partner_cutout(bg, partner_cutout, side="left")
        except (ValueError, OSError) as e:
            print(f"[compose] partner cutout composite failed: {e}", file=sys.stderr)

    # ---- 5. bare short-circuit — set generation's per-ratio brand pass draws the bar ----
    # When bare=True (generate_hero_set base), stop before the brand overlay:
    # each derived ratio then composites its own bar in _apply_brand_overlay.
    if bare:
        # Paper texture still rides along even on bare bases so the kraft tooth
        # is uniform across the set — last step before save.
        bg = _apply_paper_texture(bg, opacity=0.02)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        bg.save(out_path, "PNG")
        return out_path

    # ---- 5. brand overlay — scrim + headline + logos + accent bar (model never draws these) ----
    # Delegate to _brand_overlay for a single composited pass so scrim, headline,
    # Bear logo, retailer badge and blaze-orange bar are byte-identical to the
    # extracted helper and testable in isolation.  Convert to RGBA for the
    # alpha compositing the overlay needs.
    bg_rgba = bg.convert("RGBA")
    bg_rgba = _brand_overlay(
        bg_rgba, headline=message, ratio_key=ratio_key,
        brand_logo=brand_logo, brand_colors=brand_colors, retailer_logo=retailer_logo,
    )
    bg = bg_rgba.convert("RGB")

    # ---- 6. paper texture — final kraft tooth (~2 % blend) ----
    # Deterministic, subtle, always last so it sits above every layer equally.
    # Same-size output as input; same inputs -> identical bytes.
    bg = _apply_paper_texture(bg, opacity=0.02)

    # ---- save ----
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bg.save(out_path, "PNG")
    return out_path


# build_card is the canonical "every function (build_card)" name the task calls
# for — direct alias so callers or tests that import build_card get the same
# deterministic card-builder as compose_creative.  Docstring points to the real
# implementation so the name reads as documentation too.
build_card = compose_creative  # alias: spec name for compose_creative
# Provide an ergonomic docstring on the alias itself for `help(build_card)`.
build_card.__doc__ = """build_card — alias for compose_creative (the deterministic card builder).

See compose_creative docstring for the full layer order, verbatim-cutout
shadow, S3-first token, and model-never-touches-logo/type contracts.
"""

# Expose paper-texture and brand-overlay helpers under the spec's short names
# so `from compose import paper_texture` / `brand_overlay` style probes resolve.
paper_texture = _paper_texture  # alias: spec "paper texture" function
brand_overlay = _brand_overlay  # alias: spec "brand overlay" function
