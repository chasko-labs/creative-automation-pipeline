"""Cloud Del Norte direction harness — pure-function checks, no network.

Proves the cdn- dispatch contract: namespaced themes route to the vector
sports direction, everything else is untouched, brand words never reach
image prompts, and the negative prompt carries the session ban tail.
"""
from creative_automation import cdn_director
from creative_automation.brief import load_brief


def test_cdn_theme_detection():
    assert cdn_director.is_cdn_theme("cdn-background") is True
    assert cdn_director.is_cdn_theme("cdn-action") is True
    assert cdn_director.is_cdn_theme("wild-grizzly-bears") is False
    assert cdn_director.is_cdn_theme(None) is False


def test_default_prompt_is_vector_sports_not_product_photo():
    text = cdn_director.cdn_default_scene_prompt(
        "Stadium Background Plate", "code meets football", "US", "community", "cdn-background"
    )
    assert "screen-print" in text
    assert "no text" in text
    assert "product photo" not in text
    assert "frontier morning" not in text
    assert "cloud del norte" not in text.lower()


def test_action_theme_names_the_mascots():
    text = cdn_director.cdn_default_scene_prompt(
        "Player Action Group", "code meets football", "US", "community", "cdn-action"
    )
    assert "horned lizard" in text
    assert "four short stubby limbs" in text
    assert "six thin planted" in text


def test_negative_carries_the_ban_tail():
    neg = cdn_director.CDN_NEGATIVE
    for term in ("phantom limb", "five-pointed star", "gray", "clouds", "white ink"):
        assert term in neg


def test_brief_loads_with_two_plates(tmp_path=None):
    import pathlib

    brief = load_brief(
        pathlib.Path(__file__).parents[1] / "briefs" / "cdn-banner-sep29.yaml"
    )
    assert brief.brand == "CLOUD-DEL-NORTE"
    assert len(brief.products) >= 2
    assert "#9060f0" in (brief.brand_colors or [])
