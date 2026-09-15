"""ISO naming — writer and checker share one regex, batch filenames pass the card."""
from pathlib import Path

import pytest

from creative_automation.brief import load_brief
from creative_automation.naming import (
    ISO_NAME_RE,
    bcp47_tag,
    build_iso_name,
    canon_ratio,
    is_bcp47,
    slugify,
)
from creative_automation.pipeline import run_pipeline
from creative_automation.scorecards import ISO_RE, score_batch


def test_build_iso_name_matches_shared_regex():
    cases = [
        ("power-cakes", "US-NM", "las-cruces-target", "instagram", "9x16"),
        ("protein-biscuits", "US-SW-LASCRUCES", "alamogordo-diner", "diner-board", "16x9"),
        ("savory-waffles", "US-MW", "park-city-wasatch", "subscription-email", "1x1"),
        ("power-cakes", "US-SE-ATL", "atlanta-publix", "instagram", "4x5"),
    ]
    for product, region, locality, channel, ratio in cases:
        name = build_iso_name(product, region, locality, channel, ratio, date="20250902", version="v01")
        assert ISO_NAME_RE.match(name), f"{name} failed naming.ISO_NAME_RE"
        # scorecards must validate against the exact same pattern object
        assert ISO_RE.match(name), f"{name} failed scorecards.ISO_RE"


def test_writer_and_checker_share_one_regex():
    # the scorecards card imports the naming pattern — same object, no drift possible
    assert ISO_RE is ISO_NAME_RE


def test_loose_inputs_are_normalized():
    name = build_iso_name("Power Cakes", "us-mw", "Park City / Wasatch", "Diner Board", "1:1", date="20250902", version=2)
    assert name == "KODIAK-CAKES-power-cakes-US-MW-park-city-wasatch-diner-board-1x1-20250902-v02.png"
    assert ISO_NAME_RE.match(name)


def test_slugify_and_ratio_helpers():
    assert slugify("Las Cruces + Alamogordo") == "las-cruces-alamogordo"
    assert slugify("--Trail__Mix--") == "trail-mix"
    assert canon_ratio("1:1") == "1x1"
    assert canon_ratio("16:9") == "16x9"


def test_4x5_is_a_first_class_delivery_ratio():
    # 4x5 is one of the four customer delivery ratios (1x1, 4x5, 9x16, 16x9). It must
    # canonicalize from both spellings and pass the shared ISO filename regex so the
    # pack path and the strict path share ONE contract.
    assert canon_ratio("4x5") == "4x5"
    assert canon_ratio("4:5") == "4x5"
    name = build_iso_name("power-cakes", "US-SE-ATL", "atlanta-publix", "instagram", "4:5",
                          date="20260903", version="v01")
    assert name == "KODIAK-CAKES-power-cakes-US-SE-ATL-atlanta-publix-instagram-4x5-20260903-v01.png"
    assert ISO_NAME_RE.match(name), f"{name} failed naming.ISO_NAME_RE"
    assert ISO_RE.match(name), f"{name} failed scorecards.ISO_RE"


def test_bad_filename_rejected_by_iso_regex():
    # underscores, wrong date order, missing version, bad ratio must all fail
    bad = [
        "KODIAK-CAKES-power-cakes-US-NM-las-cruces-instagram-1x1-20250902.png",  # no version
        "KODIAK-CAKES-power-cakes-US-NM-las-cruces-instagram-4x3-20250902-v01.png",  # bad ratio
        "KODIAK-CAKES-power-cakes-US-NM-las-cruces-instagram-1x1-2025-09-02-v01.png",  # dashed date
        "kodiak-cakes-power-cakes-US-NM-las-cruces-instagram-1x1-20250902-v01.png",  # lower brand
        "KODIAK-CAKES-Power-Cakes-US-NM-las-cruces-instagram-1x1-20250902-v01.png",  # upper product
    ]
    for name in bad:
        assert ISO_NAME_RE.match(name) is None, f"{name} should be rejected"


def test_bad_ratio_normalizes_or_raises_on_build():
    # build_iso_name canonicalizes a loose ratio rather than emitting a bad name
    name = build_iso_name("power-cakes", "US-NM", "las-cruces", "instagram", "1:1", date="20250902")
    assert ISO_NAME_RE.match(name)
    # an unknown ratio raises rather than writing a non-conforming filename
    with pytest.raises(ValueError):
        build_iso_name("power-cakes", "US-NM", "las-cruces", "instagram", "4x3", date="20250902")


def test_bcp47_tags_are_well_formed():
    # loose inputs normalize to hyphenated, correctly-cased BCP-47 — not en_US
    assert bcp47_tag("en") == "en-US"
    assert bcp47_tag("es") == "es-US"
    assert bcp47_tag("en_US") == "en-US"
    assert bcp47_tag("EN-us") == "en-US"
    assert bcp47_tag("es", region="419") == "es-419"
    # every produced tag validates, and none contain an underscore
    for lc in ("en", "es", "fr", "de", "zh", "vi", "pt", "ht", "ar"):
        tag = bcp47_tag(lc)
        assert is_bcp47(tag), tag
        assert "_" not in tag


def test_bcp47_rejects_malformed():
    assert is_bcp47("en_US") is False  # underscore is not BCP-47
    assert is_bcp47("EN-US") is False  # primary subtag must be lower-case
    assert is_bcp47("english") is False  # primary subtag is 2-3 letters


def test_pipeline_writes_bcp47_tags_into_metadata(tmp_path):
    brief = load_brief("briefs/kodiak.yaml")
    out = tmp_path / "out"
    report = run_pipeline(brief, Path("input_assets"), out)

    # top-level language_tags are all well-formed BCP-47
    assert report["language_tags"]
    for tag in report["language_tags"]:
        assert is_bcp47(tag), tag
        assert "_" not in tag

    # every emitted artifact carries a BCP-47 lang_tag (en-US, not en_US)
    for a in report["artifacts"]:
        assert "lang_tag" in a
        assert is_bcp47(a["lang_tag"]), a["lang_tag"]
        assert "-" in a["lang_tag"]

    # product variants carry the tag too
    for p in report["products"]:
        for v in p["variants"]:
            assert is_bcp47(v["lang_tag"]), v["lang_tag"]


def test_generated_batch_filenames_pass_naming_card(tmp_path):
    brief = load_brief("briefs/kodiak.yaml")
    out = tmp_path / "out"
    report = run_pipeline(brief, Path("input_assets"), out)

    # every emitted artifact carries a human_name that is the ISO standard
    for a in report["artifacts"]:
        assert "human_name" in a
        assert ISO_NAME_RE.match(a["human_name"]), a["human_name"]
        assert (out / a["path"]).exists(), a["path"]

    # the naming card must pass 100% on the fresh batch
    result = score_batch(out)
    naming = next(c for c in result["brutal_cards"] if c["id"] == "naming")
    assert naming["pass"] is True, f"naming card did not pass: {naming}"
    assert naming["pct"] == 100
