"""Retailer direction — OFFLINE, cred-free.

Retailer direction ships as TWO legs, never via the generated pixels:

- image leg: the composited logo mark (retailer layer, asset store
  brands/retailers/logos/ for costco/publix/target/walmart). Per the overlay
  spec defect 1, _THEME_SCENE_HINT carries NO retailer entries — retailer
  themes fall through to the generic prompt so no aisle/pack pseudo-text is
  ever baked into the scene.
- copy leg: _THEME_COPY_HINT framing in the copy sidecar txt+csv, for EVERY
  retailer theme including copy-only kroger/heb/whole-foods (no mark).
"""
from __future__ import annotations

import pytest

from creative_automation import bedrock_client
from creative_automation import generate

_RETAILER_THEMES = sorted(generate._THEME_COPY_HINT)


def test_no_retailer_scene_hints():
    # defect 1: retailer direction must not steer the generated pixels.
    for slug in _RETAILER_THEMES:
        assert slug not in generate._THEME_SCENE_HINT, slug
    # only non-retailer scene dispatches remain.
    assert set(generate._THEME_SCENE_HINT) == {"wild-grizzly-bears", "us-ski-snowboard"}


def test_copy_hints_cover_all_retailers_including_copy_only():
    for slug in (
        "localized-costco",
        "localized-publix",
        "localized-target",
        "kodiak-subscription",
        "target",
        "walmart",
        "whole-foods",
        "publix",
        "kroger",
        "heb",
    ):
        framing = generate._THEME_COPY_HINT.get(slug)
        assert framing and len(framing) > 10, slug


@pytest.mark.parametrize("slug", _RETAILER_THEMES)
def test_scene_prompt_is_generic_for_retailer_themes_offline(slug, tmp_path, monkeypatch):
    # boto3 absent -> deterministic default_prompt, which must NOT carry any
    # retailer aisle/pack dispatch — the mark + sidecar carry the direction.
    monkeypatch.setattr(bedrock_client, "boto3", None)
    src = tmp_path / "seed.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    prompt = generate._nova_pro_scene_prompt(
        src, "Power Cakes", "weekday breakfast", "US-WA", "bulk shoppers",
        theme=slug,
    )
    for banned in ("aisle", "pallet", "warehouse", "deli-fresh", "doorstep", "pantry"):
        assert banned not in prompt.lower(), (slug, prompt)


def test_sidecar_carries_retailer_framing_with_theme():
    sc = generate.build_copy_sidecar({}, "bulk breakfast", {}, theme="localized-costco")
    assert "retailer framing: bulk Family Size value" in sc["txt"]
    assert "retailer_framing" in sc["csv"]
    assert "bulk Family Size value" in sc["csv"]


def test_sidecar_generic_without_theme():
    sc = generate.build_copy_sidecar({}, "weekday breakfast", {}, theme=None)
    assert "retailer framing" not in sc["txt"]
    assert "retailer_framing" not in sc["csv"]


def test_same_brief_differs_by_retailer():
    # the acceptance in miniature: identical brief, retailer on/off -> copy differs.
    with_retailer = generate.build_copy_sidecar({}, "same brief", {}, theme="localized-costco")
    without = generate.build_copy_sidecar({}, "same brief", {}, theme=None)
    assert with_retailer["txt"] != without["txt"]


@pytest.mark.parametrize(
    "slug,framing",
    [
        ("kroger", "family grocery run"),
        ("heb", "texas family table"),
        ("whole-foods", "whole-ingredient shelf"),
        ("walmart", "everyday low price"),
    ],
)
def test_copy_only_and_walmart_framing_in_sidecar(slug, framing):
    sc = generate.build_copy_sidecar({}, "weekday breakfast", {}, theme=slug)
    assert framing in sc["txt"]
    assert framing in sc["csv"]
