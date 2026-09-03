"""ISO naming — writer and checker share one regex, batch filenames pass the card."""
from pathlib import Path

from creative_automation.brief import load_brief
from creative_automation.naming import ISO_NAME_RE, build_iso_name, canon_ratio, slugify
from creative_automation.pipeline import run_pipeline
from creative_automation.scorecards import ISO_RE, score_batch


def test_build_iso_name_matches_shared_regex():
    cases = [
        ("power-cakes", "US-NM", "las-cruces-target", "instagram", "9x16"),
        ("protein-biscuits", "US-SW-LASCRUCES", "alamogordo-diner", "diner-board", "16x9"),
        ("savory-waffles", "US-MW", "park-city-wasatch", "subscription-email", "1x1"),
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
