"""Scene-prompt + Nova caption cluster — extracted from generate.py.

Brief clause builders, theme maps, scene prompts (Nova + deterministic),
Nova Pro caption with budget gate. Transport via bedrock_client; generate.py
imports only what it calls — outside code imports this module directly.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

from PIL import Image

from . import bedrock_client
from .bedrock_client import BotoCoreError, ClientError


# Nova Pro fail-fast: the two rung-B vision calls (caption + scene-prompt) build the SAME
# fail-fast bedrock-runtime client as the Stability invoke, but with a TIGHTER read
# timeout so caption + scene-prompt + stability all fit under the ~24s soft budget. The
# root-cause of the 33s silent gap was these two Converse calls on a bare client with NO
# Config — one hung unbounded past the 30s gateway cap. Capped here, a slow Nova Pro
# degrades gracefully (caption -> brief fallback, scene-prompt -> deterministic default).
BEDROCK_NOVA_READ_TIMEOUT_S = int(os.getenv("BEDROCK_NOVA_READ_TIMEOUT_S", "6"))


# Image engine: Bedrock Stability control-structure
# (us.stability.stable-image-control-structure-v1:0) — seed a real asset photo and the
# theme lands in the pixels (composition preserved, style restyled). Nova Pro
# (amazon.nova-pro-v1:0, Converse) is the art-director: it writes the localized
# headline AND the control-structure prompt that drives the restyle. Amazon Nova
# Canvas is LEGACY/un-invokable — do not use. The Stability text-to-image generators
# (stable-image-core, sd3-5-large, stable-image-ultra) are NOT granted yet — only the
# seed-driven control-structure edit model is a path, and mode-3 always has a seed.
NOVA_TEXT_MODEL = os.getenv("BEDROCK_NOVA_MODEL", "amazon.nova-pro-v1:0")


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


# Panel flag raised when a request names a theme the map cannot honor.
PANEL_FLAG_THEME_MISMATCH = "theme-mismatch"


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
    if bedrock_client.boto3 is None:
        return None
    try:
        img_bytes, fmt = _seed_small_for_nova(src)
    except (OSError, ValueError):
        return None
    try:
        client = bedrock_client._bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
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
    if bedrock_client.boto3 is None:
        return default_prompt
    try:
        img_bytes, fmt = _seed_small_for_nova(src)
    except (OSError, ValueError):
        return default_prompt
    try:
        client = bedrock_client._bedrock_failfast_client(read_timeout=BEDROCK_NOVA_READ_TIMEOUT_S)
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


# theme-asset-map: theme-slug -> best real thematic asset key. Sibling of sku-photo-map,
# same 3-candidate resolve pattern. A chip theme drives the IMAGE (theme wins over the
# product default) — see generate_hero precedence.
_THEME_ASSET_MAP_PATH = Path(__file__).parents[2] / "data" / "products" / "theme-asset-map.json"


# Retired named-person slugs: no chip ships them, but a user can still TYPE the
# name into the brief — and that raw token trips the Stability filter the same
# way. Scrubbed to the same filter-safe persona so free text can never regress
# into a filter trip.
_RETIRED_PERSONA_MAP: dict[str, str] = {
    "zac-efron": "energetic athletic young man, morning-fitness lifestyle vibe",
}


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

