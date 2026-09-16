"""Cloud Del Norte direction harness — scene prompts for the sep 29 banner hero.

Companion to the Kodiak direction path in generate.py, never a replacement:
any theme slug namespaced ``cdn-`` dispatches here, everything else keeps the
existing behavior untouched. The fine-tuned voice model (art_director) stays
out — this banner carries no headline copy.

Two hard rules inherited from the pipeline:
- no brand words reach the image model (they render as garbled glyphs), so
  these prompts name geography and shapes only, never the group name.
- blank surfaces everywhere: star and logo composite later in Pillow.
"""
from __future__ import annotations

CDN_THEME_PREFIX = "cdn-"

PALETTE_LINE = (
    "drawn only with navy #00002a, elevation #0a0a2e, violet #9060f0, "
    "deep purple #5a1f8a, award orange #ff9900, and desert gold #c9a23f"
)

STYLE_LINE = (
    "flat matte vector screen-print on cardstock, side-view at eye level, "
    "single top light with one shadow direction"
)

BLANK_LINE = (
    "every surface blank and free of anything that reads as writing: no text, "
    "no letters, no numbers, no logos, no watermark, no photorealism, no gloss, "
    "no white ink, no gradient mesh"
)

# Per-theme scene guidance, same role as _THEME_SCENE_HINT in generate.py:
# complete artist dispatches (setting, light, palette, composition).
CDN_THEME_HINT: dict[str, str] = {
    "cdn-background": (
        "empty night stadium background plate with no characters, no animals, "
        "and no ball: one ultra-low franklin ridgeline as a thin sliver inside "
        "the top 15 percent of the frame, low asymmetric peak right of center "
        "with antenna and three thin towers left of the peak, bare slope, tiny "
        "violet sparkles at the far edges only, top center empty, no clouds, a "
        "clear navy gap above the rooftops, broadcast truck joined to three "
        "staggered data-center halls with big roof steps and navy sky gaps "
        "between blocks, each hall a different lit window pattern of dim gold "
        "server-rack grids, bottom-quarter turf band with three small violet "
        "dashes, foreground low contrast behind an empty field, no text"
    ),
    "cdn-action": (
        "isolated player action group on plain navy ground with no buildings, "
        "no mountains, and no truck: hero-scale gold horned lizard sprinter "
        "with horned frill, spiked back, crown horns, and violet dorsal "
        "stripe in full sprint extension, head down below the shoulders, "
        "exactly four short stubby limbs with feet planted on the ground, "
        "orange oval football with one stripe and dark laces extended forward "
        "in a stiff-arm, two same-size violet ants with thick violet outlines "
        "both crouched low facing left ahead of the snout, six thin planted "
        "legs each, heads and mandibles aimed at the carrier legs, daylight "
        "gaps between the bodies, no text"
    ),
}

# Full negative prompt ported from the banner iteration sessions: every
# anatomy, invention, and layout failure the reviewers caught, stated once.
CDN_NEGATIVE = (
    "text, letters, numbers, logos, watermark, photorealism, gloss, white ink, "
    "white background, gradient mesh, extra limbs, double arm, phantom limb, "
    "merged bodies, centipede, entangled legs, frog leap, airborne, kangaroo, "
    "squat, crouch, seated runner, standing tall, stilt legs, giant ant, "
    "mascot hug, facing right, tailgating, spectator, star shapes, "
    "five-pointed star, invented landmark, circle badge, floating emblem, "
    "sawblade mountain, tall center peak, gray filler blocks, gray, clouds, "
    "continuous barracks wall, same baseline halls, equal roof heights, "
    "generic office blocks, uniform window strips, isolated truck, giant "
    "slashes, diagonal dashes, ticks under feet, egg, fruit, sticker halo, "
    "thick outline, confetti, beams, tripod, flag"
)


def is_cdn_theme(theme: str | None) -> bool:
    """True when this theme belongs to the Cloud Del Norte harness."""
    return bool(theme) and str(theme).startswith(CDN_THEME_PREFIX)


def cdn_default_scene_prompt(
    product_name: str,
    brief_msg: str,
    region: str,
    audience: str,
    theme: str | None,
) -> str:
    """Deterministic scene direction — no network, mirrors _default_scene_prompt."""
    hint = CDN_THEME_HINT.get(theme or "", "")
    direction = hint or brief_msg
    return (
        f"{STYLE_LINE}. {direction}. {PALETTE_LINE}. {product_name} hero, "
        f"{region} {audience}. {BLANK_LINE}."
    ).strip()


def cdn_nova_direction_text(
    product_name: str,
    brief_msg: str,
    region: str,
    audience: str,
    theme: str | None,
) -> str:
    """Nova Pro art-direction ask for the restyle — pure text builder.

    States the look (vector screen-print, sports action) instead of the
    product-photo framing the default path uses. Max 40 words on the reply
    so the answer stays a usable conditioning string.
    """
    hint = CDN_THEME_HINT.get(theme or "", "")
    theme_hint = f" Scene direction: {hint}" if hint else ""
    return (
        f"You are an art director for flat vector sports graphics. Subject: "
        f"'{product_name}'. Region: {region}. Audience: {audience}. Night "
        f"stadium mood: {brief_msg}.{theme_hint} Keep the seed composition. "
        f"Reply with ONE vivid scene and style description (max 40 words, no "
        f"line breaks, no quotes) — lighting, setting, mood, palette. The "
        f"scene must contain NO text, letters, numbers, signage, or labels "
        f"anywhere — blank surfaces only."
    )
