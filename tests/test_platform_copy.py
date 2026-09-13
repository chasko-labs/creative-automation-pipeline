"""Per-platform campaign copy — OFFLINE, cred-free.

No AWS: text_rewriter._has_creds() returns False with no creds env, so the rewrite seam
returns source="mock" and generate_platform_copy falls to its deterministic on-brand
templates tagged source="fallback". A monkeypatched "live" rewrite exercises the
source="generated" branch. Every assertion runs without touching Bedrock.
"""
from __future__ import annotations

import pytest

from creative_automation import text_rewriter
from creative_automation.platform_copy import (
    X_MAX_CHARS,
    YOUTUBE_TITLE_MAX,
    generate_platform_copy,
)
from creative_automation.platforms import PLATFORMS


@pytest.fixture(autouse=True)
def _no_creds(monkeypatch):
    # force the offline path: no ambient AWS creds -> rewrite seam returns mock.
    for var in ("AWS_ACCESS_KEY_ID", "AWS_PROFILE", "AWS_SESSION_TOKEN",
                "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI"):
        monkeypatch.delenv(var, raising=False)


def test_returns_entry_per_requested_platform():
    want = ["x", "linkedin", "instagram"]
    copy = generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT", platforms=want)
    assert set(copy.keys()) == set(want)


def test_default_covers_all_eight_publish_targets():
    # issue #201: Homepage, Blog, Instagram, Facebook, TikTok, YouTube, Pinterest, X.
    from creative_automation.platform_copy import PUBLISH_TARGETS

    copy = generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT")
    assert set(copy.keys()) == set(PUBLISH_TARGETS)
    assert len(copy) == 8


def test_explicit_seven_social_slugs_still_supported():
    copy = generate_platform_copy(
        "Fuel your morning", "Power Cakes", "US-UT", platforms=list(PLATFORMS)
    )
    assert set(copy.keys()) == set(PLATFORMS)


def test_offline_degrades_to_fallback_without_raising():
    copy = generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT")
    # no creds -> every entry is the deterministic fallback, none raised.
    for entry in copy.values():
        assert entry["source"] == "fallback"


def test_x_copy_respects_280_ceiling():
    # a long base message must still yield an X post <= 280 chars.
    long_msg = "protein packed whole grain goodness for every single wild frontier morning " * 6
    copy = generate_platform_copy(long_msg, "Power Cakes", "US-UT", platforms=["x"])
    x = copy["x"]
    assert len(x["post"]) <= X_MAX_CHARS
    assert 1 <= len(x["hashtags"]) <= 2 or x["hashtags"] == []  # spec target is 1-2


def test_youtube_has_title_and_description():
    copy = generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT", platforms=["youtube"])
    yt = copy["youtube"]
    assert "title" in yt and "description" in yt
    assert len(yt["title"]) <= YOUTUBE_TITLE_MAX
    assert yt["description"]  # non-empty description paragraph


def test_brand_mark_enforced_where_headline_names_brand():
    # Standing law (Atlanta backlog): bare KODIAK never ships — the allowed
    # naming "Kodiak Cakes" is present and no bare "Kodiak"/"KODIAK" survives.
    copy = generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT",
                                  platforms=["linkedin", "facebook"])
    for entry in copy.values():
        headline = entry["headline"]
        assert "Kodiak Cakes" in headline
        # no bare brand word (hashtags and allowed namings excluded).
        import re
        assert re.search(r"(?<!#)\bKODIAK\b", headline) is None
        assert re.search(r"(?<!#)\bKodiak\b(?!\s+(Cakes?|Park\s+City))", headline) is None


def test_hashtag_counts_per_spec():
    copy = generate_platform_copy(
        "Fuel your morning",
        "Power Cakes",
        "US-UT",
        platforms=["instagram", "tiktok", "pinterest", "linkedin", "homepage", "blog"],
    )
    assert len(copy["instagram"]["hashtags"]) == 4
    assert len(copy["tiktok"]["hashtags"]) == 3
    assert len(copy["pinterest"]["hashtags"]) == 3
    assert len(copy["linkedin"]["hashtags"]) == 2
    assert copy["homepage"]["hashtags"] == []
    assert len(copy["blog"]["hashtags"]) == 3


def test_pinterest_is_keyword_rich_no_hype():
    copy = generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT",
                                  platforms=["pinterest"])
    body = copy["pinterest"]["body"].lower()
    # SEO/keyword tone: mentions the product category words, no emoji.
    assert "whole grain" in body or "protein" in body
    assert not any(ord(ch) > 0x2700 for ch in body)  # no emoji block chars


def test_generated_source_when_backend_live(monkeypatch):
    # simulate a live Nova rewrite: patch rewrite_headline to return the bedrock source.
    def _live(base, market, **kwargs):
        return {"text": "Kodiak Cakes Power Cakes fuel your frontier",
                "source": "bedrock:nova-micro", "safety": {"clean": True},
                "dialect_applied": []}

    monkeypatch.setattr(text_rewriter, "rewrite_headline", _live)
    copy = generate_platform_copy("Fuel your morning", "Power Cakes", "US-UT",
                                  platforms=["instagram"])
    assert copy["instagram"]["source"] == "generated"
    assert "Kodiak Cakes" in copy["instagram"]["headline"]




def test_bounded_live_copy_one_platform_failure_falls_back(monkeypatch):
    from creative_automation import platform_copy

    original = platform_copy._generate_platform_entry

    def fail_instagram(base_message, product_name, market, platform, **kwargs):
        if platform == "instagram":
            raise RuntimeError("platform backend failed")
        return original(base_message, product_name, market, platform, **kwargs)

    monkeypatch.setattr(platform_copy, "_generate_platform_entry", fail_instagram)
    monkeypatch.setattr(
        text_rewriter,
        "rewrite_headline",
        lambda *args, **kwargs: {"text": "Kodiak Cakes fuel your frontier", "source": "bedrock:nova-micro"},
    )
    result = platform_copy.generate_platform_copy(
        "Fuel your morning", "Power Cakes", "US-UT", platforms=["instagram", "x"],
        per_platform_timeout_s=0.2, overall_timeout_s=1.0,
    )
    assert result["instagram"]["source"] == "fallback"
    assert result["x"]["source"] == "generated"


def test_bounded_copy_overall_timeout_returns_complete_fallback(monkeypatch):
    from creative_automation import platform_copy
    import time

    original = platform_copy._generate_platform_entry

    def slow_entry(*args, **kwargs):
        time.sleep(0.08)
        return original(*args, **kwargs)

    monkeypatch.setattr(platform_copy, "_generate_platform_entry", slow_entry)
    result = platform_copy.generate_platform_copy(
        "Fuel your morning", "Power Cakes", "US-UT", platforms=["instagram", "x", "youtube"],
        per_platform_timeout_s=0.2, overall_timeout_s=0.01,
    )
    assert set(result) == {"instagram", "x", "youtube"}
    assert all(entry["source"] == "fallback" for entry in result.values())


def test_platform_copy_lambda_route_validates_and_preserves_shape(monkeypatch):
    import json
    from creative_automation import generate_lambda
    from creative_automation.platform_copy import PUBLISH_TARGETS

    monkeypatch.setattr(text_rewriter, "_has_creds", lambda: False)
    event = {
        "path": "/campaigns/platform-copy",
        "body": json.dumps({
            "headline": "Fuel your morning",
            "product_name": "Power Cakes",
            "market": "US-UT",
        }),
    }
    response = generate_lambda.handler(event, None)
    payload = json.loads(response["body"])
    assert response["statusCode"] == 200
    assert set(payload["platform_copy"]) == set(PUBLISH_TARGETS)
    assert all(entry["source"] == "fallback" for entry in payload["platform_copy"].values())

    invalid = dict(event, body=json.dumps({"headline": "", "product_name": "Power Cakes", "market": "US-UT"}))
    assert generate_lambda.handler(invalid, None)["statusCode"] == 400


def test_platform_copy_fastapi_route_returns_400_for_non_object():
    from fastapi.testclient import TestClient
    from creative_automation.api import app

    response = TestClient(app).post("/campaigns/platform-copy", json=[])
    assert response.status_code == 400
