"""Stability + outpaint image rungs — extracted from generate.py.

Control-structure restyle hero, outpaint extend, native-ratio routing, Pillow
outpaint fallback, plus the seed/style/brief helpers they use. Bedrock
transport comes from bedrock_client; generate.py re-exports every name here.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from PIL import Image, ImageOps

from . import bedrock_client
from .bedrock_client import (
    boto3,
    BotoCoreError,
    ClientError,
    ConnectTimeoutError,
    ReadTimeoutError,
)


# Outpaint extend budget: the standalone mode:extend request bypasses the
# 22s ladder wall (it does one outpaint + upload inside the 30s gateway
# cap), so the 12s ladder read cap does NOT apply here. Measured 24h
# Bedrock p-average is 20.0s (max 20.5s) — 25s lets the model answer
# instead of degrading every tall/wide tile to a Pillow pad, with ~5s
# headroom for S3 download/upload + response under the gateway cap.
BEDROCK_OUTPAINT_READ_TIMEOUT_S = int(os.getenv("BEDROCK_OUTPAINT_READ_TIMEOUT_S", "25"))


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


# Seed discipline: derived seed = uniqueness (same brief re-renders vary by
# market + season + day); pinned seed = reproducibility (ops sets
# BEDROCK_STABILITY_SEED explicitly, or KODIAK_DETERMINISTIC=1 for tests).
# The variations button still passes seed per call via seed_value.
STABILITY_SEED = int(os.getenv("BEDROCK_STABILITY_SEED", "42"))


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


def _stability_control_hero(
    seed: Path,
    prompt: str,
    out_path: Path,
    *,
    control_strength: float | None = None,
    seed_value: int | None = None,
    retry_once: bool = True,
    read_timeout: int | None = None,
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
        client = (
            bedrock_client._bedrock_failfast_client(read_timeout=read_timeout)
            if read_timeout is not None
            else bedrock_client._bedrock_failfast_client()
        )
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
    read_timeout: int | None = None,
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
            read_timeout=read_timeout,
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
        client = bedrock_client._bedrock_failfast_client(read_timeout=BEDROCK_OUTPAINT_READ_TIMEOUT_S)
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

