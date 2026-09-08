"""Retailer direction (#245) — OFFLINE, cred-free.

Selecting a retailer direction (Localized Costco chip -> theme=localized-costco)
must visibly change both the image direction and the copy. Image direction flows
through _THEME_SCENE_HINT (folded into the Nova Pro scene prompt AND the
deterministic fallback prompt); copy flows through _THEME_COPY_HINT into the
copy sidecar txt+csv. No theme = generic output on both legs.
"""
from __future__ import annotations

import pytest

from creative_automation import generate

_RETAILERS = sorted(generate._THEME_COPY_HINT)


def test_every_retailer_has_scene_and_copy_guidance():
    # equivalents per retailer: no retailer ships copy without image direction
    # or vice versa.
    assert set(generate._THEME_SCENE_HINT) >= set(generate._THEME_COPY_HINT)
    for slug, framing in generate._THEME_COPY_HINT.items():
        assert framing and len(framing) > 10, slug
        assert generate._THEME_SCENE_HINT[slug].strip(), slug


@pytest.mark.parametrize("slug", _RETAILERS)
def test_scene_prompt_carries_retailer_direction_offline(slug, tmp_path, monkeypatch):
    # boto3 absent -> deterministic default_prompt, which must carry the scene
    # hint so the direction lands even with no live Nova Pro.
    monkeypatch.setattr(generate, "boto3", None)
    src = tmp_path / "seed.png"
    src.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
    prompt = generate._nova_pro_scene_prompt(
        src, "Power Cakes", "weekday breakfast", "US-WA", "bulk shoppers",
        theme=slug,
    )
    hint_words = [w for w in generate._THEME_SCENE_HINT[slug].lower().split() if len(w) > 4]
    assert any(w.strip(",") in prompt.lower() for w in hint_words[:6]), prompt


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
