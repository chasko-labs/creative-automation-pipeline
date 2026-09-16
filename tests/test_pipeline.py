from pathlib import Path

from PIL import Image

from creative_automation.brief import load_brief
from creative_automation.pipeline import run_pipeline


def test_pipeline_generates_three_ratios(tmp_path):
    brief = load_brief("briefs/example.yaml")
    dam = Path("input_assets")
    out = tmp_path / "out"
    report = run_pipeline(brief, dam, out)
    assert report["summary"]["total_creatives"] == 9  # 3 products x 3 ratios
    for prod in brief.products:
        for ratio in ["1x1", "9x16", "16x9"]:
            p = out / prod.id / ratio / f"{prod.id}_{ratio}.png"
            assert p.exists(), f"missing {p}"
            img = Image.open(p)
            # check dimensions
            if ratio == "1x1":
                assert img.size == (1080, 1080)
            elif ratio == "9x16":
                assert img.size == (1080, 1920)
            elif ratio == "16x9":
                assert img.size == (1920, 1080)

def test_dam_reuse_vs_generate(tmp_path):
    brief = load_brief("briefs/example.yaml")
    dam = Path("input_assets")
    out = tmp_path / "out2"
    report = run_pipeline(brief, dam, out)
    # hydrating-serum has real dam asset (now dam+enhanced with institutional grading)
    hs = next(p for p in report["products"] if p["id"] == "hydrating-serum")
    assert hs["hero_source"] in ("dam", "dam+enhanced")
    rm = next(p for p in report["products"] if p["id"] == "radiant-moisturizer")
    # radiant-moisturizer has no DAM asset of its own and no sku-photo-map entry, and
    # the default-brand-hero fallback was retired when the real-photo scene composer
    # landed. With no seed and no packshot the never-fail ladder ends at rung D
    # (brand-floor): real pixels, zero I/O, non-shaming label. Never "mock"/"preview".
    assert rm["hero_source"] == "brand-floor"
    assert "mock" not in rm["hero_source"]

def test_legal_flag(tmp_path):
    from creative_automation.compliance import check_legal
    assert check_legal("This miracle cure is guaranteed")["passed"] is False
    assert check_legal("Hydrate your glow")["passed"] is True
