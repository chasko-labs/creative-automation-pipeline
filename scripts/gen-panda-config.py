#!/usr/bin/env python3
"""Generate panda.config.ts from design/tokens/kodiak.json.

Single transform for the typed design-system foundation. kodiak.json stays the
canonical W3C DTFM source (read BY KEY via src/creative_automation/token_loader.py:
brand.{bearBrown,blazeOrange,frontierGreen}.$value and semantic.overlay.scrim.$value),
so this generator never renames or removes an existing key -- it only reads and re-emits.

Panda CSS uses `value` (not DTFM `$value`) and its own ref syntax `{colors.x.y}`
(not DTFM `{kodiak.x.y}`), so panda.config.ts cannot BE the python artifact -- it is
generated FROM it. emitTokensOnly:true keeps this a pure token layer that changes zero
pixels: it produces css custom properties only, no utilities, no recipes.

Run (uv):
  uv run python scripts/gen-panda-config.py
  uv run python scripts/gen-panda-config.py --check   # non-zero exit if out of date

Nobody hand-edits panda.config.ts. Edit kodiak.json, re-run this.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOKENS_PATH = REPO_ROOT / "design" / "tokens" / "kodiak.json"
CONFIG_PATH = REPO_ROOT / "panda.config.ts"
STYLES_OUTFILE = "web/kodiak-posts-for-todays-frontier/design/styles.css"

# DTFM alias like {kodiak.color.brand.bearBrown} -> panda ref {colors.brand.bearBrown}
_ALIAS_RE = re.compile(r"^\{kodiak\.(.+)\}$")

# maps the leading kodiak.<segment> to the panda token-category root used in refs
_CATEGORY_ROOT = {
    "color": "colors",
    "spacing": "spacing",
    "radius": "radii",
    "typography.fontFamily": "fonts",
    "typography.fontWeight": "fontWeights",
}


def _panda_ref(dtfm_alias: str) -> str:
    """Rewrite a DTFM alias into a Panda semantic-token ref.

    {kodiak.color.neutral.50}                -> {colors.neutral.50}
    {kodiak.color.brand.bearBrown}           -> {colors.brand.bearBrown}
    {kodiak.spacing.2xl}                     -> {spacing.2xl}
    {kodiak.typography.fontFamily.headline}  -> {fonts.headline}
    """
    m = _ALIAS_RE.match(dtfm_alias)
    if not m:
        return dtfm_alias
    path = m.group(1)  # e.g. color.brand.bearBrown
    for prefix, root in _CATEGORY_ROOT.items():
        if path == prefix or path.startswith(prefix + "."):
            rest = path[len(prefix):].lstrip(".")
            return "{" + root + ("." + rest if rest else "") + "}"
    # fallback: strip the kodiak prefix, keep the remainder
    return "{" + path + "}"


def _resolve_value(raw):
    """Resolve a DTFM $value into a Panda value string.

    - alias string {kodiak...}   -> panda ref {category...}
    - fontFamily array           -> comma-joined css stack
    - anything else              -> passthrough
    """
    if isinstance(raw, str) and raw.startswith("{kodiak."):
        return _panda_ref(raw)
    if isinstance(raw, list):
        return ", ".join(str(v) for v in raw)
    return raw


def _is_token(node) -> bool:
    return isinstance(node, dict) and "$value" in node


def _walk_colors(brand: dict, neutral: dict) -> dict:
    """Flat color scale: brand.* nested + neutral.* nested."""
    colors: dict = {"brand": {}, "neutral": {}}
    for name, node in brand.items():
        if _is_token(node):
            colors["brand"][name] = {"value": node["$value"]}
    for name, node in neutral.items():
        if _is_token(node):
            colors["neutral"][name] = {"value": node["$value"]}
    return colors


def _walk_semantic_colors(semantic: dict) -> dict:
    """semantic.{background,foreground,border,overlay}.* -> semanticTokens.colors."""
    out: dict = {}
    for group, members in semantic.items():
        if not isinstance(members, dict):
            continue
        out[group] = {}
        for name, node in members.items():
            if _is_token(node):
                out[group][name] = {"value": _resolve_value(node["$value"])}
    return out


def _walk_fonts(font_family: dict) -> dict:
    out: dict = {}
    for name, node in font_family.items():
        if _is_token(node):
            out[name] = {"value": _resolve_value(node["$value"])}
    return out


def _walk_font_weights(font_weight: dict) -> dict:
    out: dict = {}
    for name, node in font_weight.items():
        if _is_token(node):
            out[name] = {"value": node["$value"]}
    return out


def _walk_font_sizes(typography: dict) -> dict:
    """Flatten headline/body/caption per-ratio fontSize into `<role>.<ratio>` keys."""
    out: dict = {}
    for role in ("headline", "body", "caption"):
        block = typography.get(role, {})
        for ratio, node in block.items():
            if _is_token(node):
                size = node["$value"].get("fontSize")
                if size:
                    out[f"{role}.{ratio}"] = {"value": size}
    return out


def _walk_dimension_scale(scale: dict) -> dict:
    """spacing / radius flat scales; skips the nested `semantic` subtree + $meta keys."""
    out: dict = {}
    for name, node in scale.items():
        if name.startswith("$") or name == "semantic":
            continue
        if _is_token(node):
            out[name] = {"value": node["$value"]}
    return out


def _walk_semantic_spacing(spacing: dict) -> dict:
    sem = spacing.get("semantic", {})
    out: dict = {}
    for name, node in sem.items():
        if _is_token(node):
            out[name] = {"value": _resolve_value(node["$value"])}
    return out


def _shadow_to_css(val: dict) -> str:
    return (
        f"{val['offsetX']} {val['offsetY']} {val['blur']} "
        f"{val['spread']} {val['color']}"
    )


def _walk_shadows(shadow: dict) -> dict:
    out: dict = {}
    for name, node in shadow.items():
        if name.startswith("$"):
            continue
        if _is_token(node):
            out[name] = {"value": _shadow_to_css(node["$value"])}
    return out


def build_theme(tokens: dict) -> dict:
    kodiak = tokens["kodiak"]
    color = kodiak["color"]
    typography = kodiak["typography"]
    spacing = kodiak["spacing"]
    radius = kodiak["radius"]
    shadow = kodiak["shadow"]

    theme_tokens = {
        "colors": _walk_colors(color["brand"], color["neutral"]),
        "fonts": _walk_fonts(typography["fontFamily"]),
        "fontWeights": _walk_font_weights(typography["fontWeight"]),
        "fontSizes": _walk_font_sizes(typography),
        "spacing": _walk_dimension_scale(spacing),
        "radii": _walk_dimension_scale(radius),
        "shadows": _walk_shadows(shadow),
    }
    semantic_tokens = {
        "colors": _walk_semantic_colors(color["semantic"]),
        "spacing": _walk_semantic_spacing(spacing),
    }
    return {"tokens": theme_tokens, "semanticTokens": semantic_tokens}


def render_config(theme: dict) -> str:
    """Emit panda.config.ts. GENERATED banner keeps hand-edits out."""
    # render the extend body without the outer braces, re-indented under `extend:`
    body = json.dumps(theme, indent=2, ensure_ascii=False).splitlines()
    inner = body[1:-1]  # drop the opening `{` and closing `}`
    theme_block = "\n".join(("    " + line) for line in inner)
    return f"""// GENERATED by scripts/gen-panda-config.py from design/tokens/kodiak.json
// DO NOT EDIT BY HAND. Edit kodiak.json then run: uv run python scripts/gen-panda-config.py
// emitTokensOnly keeps this a pure token layer -- css custom properties only, zero pixels changed.
import {{ defineConfig }} from "@pandacss/dev";

export default defineConfig({{
  emitTokensOnly: true,
  preflight: false,
  include: ["./web/kodiak-posts-for-todays-frontier/**/*.{{html,js,ts}}"],
  exclude: [],
  outdir: "web/kodiak-posts-for-todays-frontier/design/panda",
  theme: {{
    extend: {{
{theme_block}
    }},
  }},
}});
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate panda.config.ts from kodiak.json")
    parser.add_argument(
        "--check",
        action="store_true",
        help="exit non-zero if panda.config.ts is out of date (no write)",
    )
    args = parser.parse_args()

    tokens = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))
    theme = build_theme(tokens)
    rendered = render_config(theme)

    if args.check:
        current = CONFIG_PATH.read_text(encoding="utf-8") if CONFIG_PATH.exists() else ""
        if current != rendered:
            print("panda.config.ts is out of date -- run gen-panda-config.py", file=sys.stderr)
            return 1
        print("panda.config.ts is up to date")
        return 0

    CONFIG_PATH.write_text(rendered, encoding="utf-8")
    print(f"wrote {CONFIG_PATH.relative_to(REPO_ROOT)}")
    print(f"panda cssgen target: {STYLES_OUTFILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
