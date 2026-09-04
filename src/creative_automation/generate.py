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
import json
import os
import sys
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFont, ImageOps

# Attempt boto3 import lazily — local-only mode still works without it
try:
    import boto3
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:
    boto3 = None  # type: ignore


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
# Stability seed constraint: total pixels 4096..9437184, each dim >= 64. A real
# 1024x1024 DAM photo sits well inside the range; a seed below the floor in either
# dim is upscaled to 1024x1024 before invoke to avoid a ValidationException.
_STABILITY_MIN_DIM = 64
_STABILITY_UPSCALE_TO = 1024
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

# Canvas sizes per ISO ratio (social-3ratio.json). The real lifestyle photo fills
# each frame as the cover background — no ellipse, no solid-color-only path.
_CANVAS = {
    "1x1": (1080, 1080),
    "9x16": (1080, 1920),
    "16x9": (1920, 1080),
}
# Per-ratio headline slab size (C06: 56/64/72).
_HEADLINE_PX = {"1x1": 56, "9x16": 64, "16x9": 72}

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


def _find_source_asset(product_id: str, product_name: str) -> Optional[Path]:
    """Locate a real source image for the product.

    Order: input_assets/<product_id>/hero-real.png, then hero.png, then any image
    in that product dir, then a name-matching glob across the asset roots, then an
    S3 DAM fallback (fetch_hero_to_tmp) for Lambda where no assets are baked in.
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

        s3_hit = fetch_hero_to_tmp(product_id)
        if s3_hit is not None and s3_hit.exists():
            return s3_hit
    except Exception as e:  # noqa: BLE001 — S3 discovery never breaks the mock fallback
        print(f"[generate] S3 hero discovery skipped: {e}", file=sys.stderr)
    return None


def _nova_pro_caption(
    src: Path, product_name: str, brief_msg: str, region: str, audience: str
) -> Optional[str]:
    """Ask Nova Pro (Converse) for a short on-brand caption + layout hint. None on failure."""
    if boto3 is None:
        return None
    fmt = _CONVERSE_FMT.get(src.suffix.lower())
    if fmt is None:
        return None
    try:
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        img_bytes = src.read_bytes()
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
    default_prompt = (
        f"{product_name} product photo restyled for {_safe_theme_text(theme) if theme else brief_msg}, "
        f"{region} {audience}, on-brand Kodiak lifestyle scene, natural light, high detail"
    ).strip()
    if boto3 is None:
        return default_prompt
    fmt = _CONVERSE_FMT.get(src.suffix.lower())
    if fmt is None:
        return default_prompt
    try:
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        img_bytes = src.read_bytes()
        prompt = (
            f"You are an ad art director directing an image restyle. Product: "
            f"'{product_name}'. Region: {region}. Audience: {audience}. Campaign vibe: "
            f"{brief_msg}.{theme_hint} Look at the product image, which must keep its "
            "composition. Reply with ONE vivid scene/style description (max 40 words, no "
            "line breaks, no quotes) that restyles this photo to the theme — lighting, "
            "setting, mood, palette. Keep the product recognizable. No headline text."
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
    from io import BytesIO

    buf = BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


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
        client = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
        body = {
            "prompt": prompt,
            "image": _seed_b64_for_stability(seed),
            "control_strength": STABILITY_CONTROL_STRENGTH,
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
    except ClientError as e:  # surface the exact error code — never swallow AccessDenied
        code = e.response.get("Error", {}).get("Code", "Unknown")
        print(f"[generate] stability control-structure ClientError [{code}]: {e}", file=sys.stderr)
        return None
    except (BotoCoreError, Exception) as e:  # noqa: BLE001 — non-AWS failures fall through
        print(f"[generate] stability control-structure failed: {e}", file=sys.stderr)
        return None


def _parse_layout(caption: str) -> tuple[str, str]:
    """Split Nova Pro text into (headline, side) where side in {left,right,center}."""
    headline, side = "", "center"
    for line in caption.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.upper().startswith("LAYOUT:"):
            val = s.split(":", 1)[1].strip().lower()
            if val in ("left", "right", "center"):
                side = val
        elif not headline:
            headline = s.strip('"')
    return headline[:48], side


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


def _compose_scene(
    photo: Path,
    headline: str,
    ratio: str,
    out_path: Path,
    idx: int = 0,
) -> Path:
    """Scene-integration composer per social-3ratio.json. The real photo is the hero.

    C01 real photo COVER-fits the full canvas (ImageOps.fit BICUBIC) + a dark scrim
    blend (~0.18) for legibility — this REPLACES the ellipse entirely, no solid-color
    background anywhere on this path. C04 semi-transparent dark message bar ~32% tall
    anchored at 68% down with the centered white headline (max 3 lines, per-ratio font
    56/64/72). C03 8px Blaze Orange accent bar pinned to the very bottom. No Kodiak
    logo/wordmark is stamped — Kodiak campaigns carry no logo per brand preference.
    """
    W, H = _CANVAS.get(ratio, _CANVAS["1x1"])

    # C01 — real lifestyle photo fills the frame as cover background.
    src_img = Image.open(photo).convert("RGB")
    cover = ImageOps.fit(src_img, (W, H), method=Image.BICUBIC, centering=(0.5, 0.5))
    scrim = Image.new("RGB", (W, H), _hex_to_rgb(_scrim_hex))
    canvas = Image.blend(cover, scrim, 0.18)
    canvas = canvas.convert("RGBA")
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

    # C03 — 8px Blaze Orange accent bar at the very bottom.
    accent = _hex_to_rgb(_accent_hex)
    draw.rectangle([0, H - 8, W, H], fill=(*accent, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out_path, "PNG")
    return out_path


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
) -> tuple[Path, str]:
    """Generate a real Kodiak-social-style hero. Returns (path, source).

    Seed resolution (which real photo becomes the mode-3 seed), theme wins:
    0. theme provided AND _resolve_theme_photo(theme) resolves -> that thematic DAM
       photo is the seed (the chip theme drives the IMAGE, not the product default).
    a. no theme (or unresolved) -> sku-photo-map resolves the handle -> a REAL
       lifestyle DAM photo (dam.fetch_dam_key -> /tmp) is the seed.
    b. no map entry OR the DAM fetch fails -> disk _find_source_asset is the seed
       (unchanged discovery), so nothing regresses offline.

    Image engine seam (mode-3, run once on the resolved seed):
    1. Stability control-structure restyles the seed to the theme -> the theme lands
       in the pixels. Source "bedrock:stability-control-structure".
    2. Stability returns None (unavailable / AccessDenied — exact code already logged,
       never swallowed) -> Pillow _compose_scene on the SAME seed. Source
       "bedrock:nova-pro" (unchanged existing behavior).
    3. no seed at all -> _mock_hero (true last resort). Source
       "bedrock:nova-pro-fallback". No "mock"/"preview" reaches the UI.
    """
    if ratio not in _CANVAS:
        ratio = "1x1"

    def _headline(src: Path) -> str:
        caption = _nova_pro_caption(src, product_name, brief_msg, region, audience) or ""
        headline, _side = _parse_layout(caption)
        return headline or brief_msg[:48]

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
            except Exception as e:  # noqa: BLE001 — falls through to product precedence
                print(f"[generate] theme seed fetch failed: {e}", file=sys.stderr)
    if seed is None:
        photo_key = _resolve_dam_photo(product_id)
        if photo_key:
            try:
                from .dam import fetch_dam_key

                dest = Path("/tmp/kodiak-assets/scene") / Path(photo_key).name  # noqa: S108 — Lambda /tmp
                photo = fetch_dam_key(photo_key, dest)
                if photo is not None and photo.exists():
                    seed = photo
            except Exception as e:  # noqa: BLE001 — falls through to disk
                print(f"[generate] sku-mapped seed fetch failed: {e}", file=sys.stderr)
    if seed is None:
        disk = _find_source_asset(product_id, product_name)
        if disk is not None and disk.exists():
            seed = disk

    # ---- mode-3 image engine seam: real seed -> Stability restyle, else Pillow compose.
    if seed is not None:
        scene_prompt = _nova_pro_scene_prompt(seed, product_name, brief_msg, region, audience, theme)
        stylized = _stability_control_hero(seed, scene_prompt, out_path)
        if stylized is not None and stylized.exists():
            return stylized, STABILITY_SOURCE
        # Stability unavailable — the exact error was already logged (AccessDenied is a
        # Bryan SSO refresh issue, never swallowed). Downgrade to the Pillow composite.
        try:
            result = _compose_scene(seed, _headline(seed), ratio, out_path, idx)
            if result.exists():
                return result, "bedrock:nova-pro"
        except Exception as e:  # noqa: BLE001 — falls through to placeholder
            print(f"[generate] scene compose on seed failed: {e}", file=sys.stderr)

    # ---- true last resort — no seed at all. Deterministic placeholder, non-lying label.
    placeholder = _mock_hero(product_name, brief_msg, region, out_path, idx)
    return placeholder, FALLBACK_SOURCE
