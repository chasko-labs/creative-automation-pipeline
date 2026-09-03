"""End-to-end pipeline test - one command, full loop, marketing-readable."""
from pathlib import Path
from PIL import Image
from creative_automation.brief import load_brief
from creative_automation.pipeline import run_pipeline

def test_e2e_on_the_go(tmp_path):
    brief = load_brief("briefs/kodiak-on-the-go.yaml")
    out = tmp_path / "out"
    report = run_pipeline(brief, Path("input_assets"), out)
    # on-the-go is 3 products x 3 ratios = 9, all use allowed language
    assert report["summary"]["total_creatives"] == 9
    assert "9/9" in report["summary"]["compliance_pass_rate"]
    # every product got its 3 sizes
    for prod in brief.products:
        for ratio in ["1x1","9x16","16x9"]:
            p = out / prod.id / ratio / f"{prod.id}_{ratio}.png"
            assert p.exists()
            # headline is English on-the-go message
            assert "On the go" in report["products"][0]["localized_message"] or "On the go" in brief.campaign_message
            # dims correct
            im = Image.open(p)
            assert im.size in [(1080,1080),(1080,1920),(1920,1080)]

def test_e2e_retailer_tuned_headlines(tmp_path):
    # Publix vs Target vs Costco must have different headlines but same template
    for brief_path, expected_snippet in [
        ("briefs/kodiak-publix.yaml","your family"),
        ("briefs/kodiak-target.yaml","Fuel your frontier"),
        ("briefs/kodiak-costco.yaml","Stock the frontier"),
    ]:
        brief = load_brief(brief_path)
        out = tmp_path / Path(brief_path).stem
        report = run_pipeline(brief, Path("input_assets"), out)
        assert expected_snippet.lower() in report["products"][0]["localized_message"].lower()
        assert report["summary"]["total_creatives"] == 9

def test_localization_memory_seed():
    # training data exists for 18 regions + retailers
    data = Path("data/localization/localization-training-data.jsonl")
    assert data.exists()
    lines = data.read_text().strip().splitlines()
    assert len(lines) >= 18
    # Las Cruces green chile exemplar must be present
    assert any("Las Cruces" in line and "green chile" in line.lower() for line in lines)
