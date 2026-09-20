"""Structured brand-copy source — single source of truth for fallback voice.

Authored from:
  - references/keep-it-wild/voice-tone.json (adventurous / nourishing / rugged /
    guardrails / localization)
  - references/keep-it-wild/mood-keywords.json (taglines + keyword pool)
  - docs/iso-naming-conventions.md section 2 (the two approved external taglines,
    fixed words + fixed punctuation)

platform_copy's deterministic fallback templates (_fallback_headline / _body_for)
read their frames from here, so offline copy stays on-brand without duplicating
voice strings in two places.

Marks policy (owner decision 2026-09-20): generated/social fallback copy uses the
ascii form "Kodiak Cakes" because models garble registered glyphs ((R)/R) into
visible artifacts. Registered forms (KODIAK(R)/KODIAK CAKES(R)) are reserved for
locked surfaces: packaging, logo lockups, and the pipeline footer stamp
(pipeline._write_preview). clean_brand_copy normalizes any legacy (R)/(R) mark
that leaks into generated copy back to the ascii form.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path

# Canonical approved taglines (iso-naming section 2 — fixed words/punctuation).
TAGLINE_EPIC = "Feeding Epic Days & Wilder Lives"
TAGLINE_FRONTIER = "Nourishment for Today's Frontier"
TAGLINE_KEEP_IT_WILD = "Keep It Wild"

# ascii brand naming for generated/social copy (see module docstring).
BRAND_NAME = "Kodiak Cakes"

# Approved substantiated claims safe for fallback copy.
APPROVED_CLAIMS = (
    "100% whole grains",
    "protein-packed",
    "14g protein",
)

# Unsubstantiated patterns that must never appear in fallback copy
# (guardrails: avoid % claims per 17% class-action precedent).
PROHIBITED_CLAIM_HINTS = (
    "17%",
    "% more",
    "% less",
    "number one",
    "#1",
)

# Voice pillars distilled from voice-tone.json.
VOICES: dict[str, dict[str, str]] = {
    "adventurous": {
        "summary": "Verbs-forward, trail-ready invites. Second-person, active, outdoor imperatives.",
        "examples": "Fuel your frontier; Blaze your morning trail; Epic days start here",
    },
    "nourishing": {
        "summary": "Whole-grain honesty + protein purpose (14g). Warm parental, never diet jargon.",
        "examples": "Heirloom recipe, 100% whole grains; real food tradition",
    },
    "rugged": {
        "summary": "Wasatch-born grit, honest, unpolished but not gruff. Short sentences, light frontier idioms.",
        "examples": "keep it wild; wilder lives",
    },
}

# Fallback headline frames per platform tone-kind. {brand} {product} {base}
# placeholders; frames stay ascii and emoji-free so offline output never surprises.
FALLBACK_HEADLINE_FRAMES: dict[str, str] = {
    "short": "{brand} {product}: {base}",
    "professional": "{brand} {product} \u2014 {base}. 100% whole grains, protein-packed.",
    "hooky": "Fuel your frontier. {brand} {product} \u2014 {base}",
    "trend": "POV: your breakfast actually fuels the day. {brand} {product}.",
    "community": "Gather the family around {brand} {product} \u2014 {base}",
    "seo": "{product} protein pancake and waffle mix \u2014 {base}, whole grain breakfast",
    "video": "{brand} {product}: {base}",
    "homepage": "{brand} {product} \u2014 {base}",
    "article": "{product}: a photographic-editorial Kodiak Cakes breakfast \u2014 {base}",
}

# Fallback body frames per tone-kind. {product} {place} {epic} {frontier} placeholders.
FALLBACK_BODY_FRAMES: dict[str, str] = {
    "professional": (
        "{product} delivers 100% whole grains and protein in every serving. "
        "Built for teams and families who want real food that keeps up. {frontier}."
    ),
    "community": (
        "Weekend mornings just got better{place}. {product} brings the whole "
        "family to the table with protein-packed whole grains. {epic}."
    ),
    "seo": (
        "{product} protein pancake mix made with 100% whole grains. High-protein "
        "breakfast recipe idea for busy mornings, meal prep, and family brunch. {frontier}."
    ),
    "video": (
        "{product} is protein-packed whole-grain fuel for whatever your day holds"
        "{place}. Watch how a real Kodiak Cakes breakfast comes together in minutes. {epic}."
    ),
    "hooky": "Protein-packed whole grains, ready fast. {epic}.",
    "trend": "14g protein. 100% whole grain. No cap. {epic}.",
    "homepage": (
        "{product} \u2014 protein-packed 100% whole grains for the whole "
        "family{place}. {frontier}."
    ),
    "article": (
        "A photographic-editorial Kodiak Cakes breakfast{place}: {product} "
        "in-scene, lifestyle, product-in-use. Whole-grain protein for slow "
        "mornings and big days. {epic}."
    ),
    "short": "",
}

# Deterministic hashtag pool (ascii, no emoji).
HASHTAG_POOL = ("KeepItWild", "KodiakCakes", "ProteinPacked", "WholeGrain", "FuelYourFrontier")


def _references_dir() -> Path:
    env = os.getenv("CAP_BRAND_REFS")
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "references" / "keep-it-wild"


@lru_cache(maxsize=1)
def load_voice_tone() -> dict:
    """Load the raw voice-tone.json reference ({} when unreachable)."""
    try:
        return json.loads((_references_dir() / "voice-tone.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def fallback_headline(kind: str, base_message: str, product_name: str) -> str:
    """Render the fallback headline for a tone-kind from the structured frames."""
    frame = FALLBACK_HEADLINE_FRAMES.get(kind, "{brand} {product} \u2014 {base}")
    return frame.format(
        brand=BRAND_NAME, product=product_name.strip(), base=base_message.strip()
    )


def fallback_body(kind: str, product_name: str, market: str | None) -> str:
    """Render the fallback body/description for a tone-kind from the structured frames."""
    frame = FALLBACK_BODY_FRAMES.get(kind, "")
    if not frame:
        return ""
    place = f" in {market}" if market else ""
    return frame.format(
        product=product_name.strip(), place=place, epic=TAGLINE_EPIC, frontier=TAGLINE_FRONTIER
    )


def voice_summary() -> dict[str, str]:
    """Compact voice pillar summaries, preferring the live voice-tone.json when present."""
    raw = load_voice_tone()
    out: dict[str, str] = {}
    for voice, meta in VOICES.items():
        out[voice] = str(raw.get(voice, meta["summary"]) if isinstance(raw.get(voice), str) else meta["summary"])
    return out
