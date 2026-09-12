"""Local-CI drift guard: generated styles.css must match design/tokens/kodiak.json.

Local checks replace server-side build minutes for the token layer. Re-derives the expected brand + semantic
color hex values straight from kodiak.json (the canonical DTFM source), then asserts the
committed generated css contains them.

Until styles.css is generated (needs the panda toolchain: `npm run tokens:config` then
`npm run tokens:css`), the test skips-with-reason rather than failing -- the file is a
downstream build artifact, not something pytest can synthesize.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOKENS_PATH = REPO_ROOT / "design" / "tokens" / "kodiak.json"
STYLES_PATH = REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "design" / "styles.css"

_ALIAS_RE = re.compile(r"^\{kodiak\.(.+)\}$")


def _load_tokens() -> dict:
    return json.loads(TOKENS_PATH.read_text(encoding="utf-8"))


def _deref(tokens: dict, dotted: str) -> str:
    """Resolve a dotted kodiak path (e.g. color.brand.bearBrown) to a concrete hex."""
    node = tokens["kodiak"]
    for seg in dotted.split("."):
        node = node[seg]
    value = node["$value"]
    if isinstance(value, str) and value.startswith("{kodiak."):
        inner = _ALIAS_RE.match(value).group(1)
        return _deref(tokens, inner)
    return value


def _expected_brand_hex(tokens: dict) -> dict[str, str]:
    brand = tokens["kodiak"]["color"]["brand"]
    return {
        "bearBrown": brand["bearBrown"]["$value"],
        "blazeOrange": brand["blazeOrange"]["$value"],
        "frontierGreen": brand["frontierGreen"]["$value"],
    }


def _expected_semantic_hex(tokens: dict) -> dict[str, str]:
    """Resolve semantic colors to concrete hex, matching the palette in the brief."""
    return {
        "background.default": _deref(tokens, "color.semantic.background.default"),
        "foreground.default": _deref(tokens, "color.semantic.foreground.default"),
        "overlay.scrim": _deref(tokens, "color.semantic.overlay.scrim"),
    }


def test_kodiak_json_present():
    assert TOKENS_PATH.exists(), f"missing canonical token source {TOKENS_PATH}"


def test_brand_palette_matches_brief():
    """Guards the seam: the three brand hexes the python pipeline reads by key."""
    tokens = _load_tokens()
    brand = _expected_brand_hex(tokens)
    assert brand["bearBrown"].upper() == "#3B2316"
    assert brand["blazeOrange"].upper() == "#E8530E"
    assert brand["frontierGreen"].upper() == "#1A3C34"
    # scrim is the compose.py seam -- 8-digit RGBA, must stay exact
    assert _deref(tokens, "color.semantic.overlay.scrim").upper() == "#1A1110CC"


def _skip_if_no_styles():
    if not STYLES_PATH.exists():
        pytest.skip(
            "styles.css not generated yet -- run `npm run tokens:config` then "
            "`npm run tokens:css` (needs @pandacss/dev installed). drift check "
            "activates once the artifact is committed."
        )


def test_generated_css_contains_brand_hex():
    _skip_if_no_styles()
    tokens = _load_tokens()
    css = STYLES_PATH.read_text(encoding="utf-8").upper()
    for name, hex_val in _expected_brand_hex(tokens).items():
        assert hex_val.upper() in css, f"brand {name} ({hex_val}) missing from generated css"


def test_generated_css_contains_semantic_hex():
    _skip_if_no_styles()
    tokens = _load_tokens()
    css = STYLES_PATH.read_text(encoding="utf-8").upper()
    for name, hex_val in _expected_semantic_hex(tokens).items():
        assert hex_val.upper() in css, f"semantic {name} ({hex_val}) missing from generated css"


def test_generated_css_has_root_block():
    _skip_if_no_styles()
    css = STYLES_PATH.read_text(encoding="utf-8")
    assert ":root" in css, "generated css missing :root custom-property block"
