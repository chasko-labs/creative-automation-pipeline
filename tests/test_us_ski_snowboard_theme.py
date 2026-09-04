"""US Ski & Snowboard theme — OFFLINE, cred-free.

No network, no AWS. Asserts the us-ski-snowboard theme resolves a real generic DAM seed
(no named athlete), routes through generate_hero_set like other themes (provenance/theme
present), and that the Nova Pro scene prompt carries the winter/alpine guidance while
NEVER leaking a real athlete name.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import generate

# real named-athlete tokens that must never appear in a generated scene prompt.
_ATHLETE_NAMES = ("karissa", "schweizer", "emily", "harrington", "alex", "howes",
                  "quinn", "mason", "natalia", "grossman", "zac", "efron")


def _png(path: Path, size=(400, 300)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, (200, 210, 230)).save(path, "PNG")
    return path


def test_theme_resolves_generic_non_athlete_seed():
    key = generate._resolve_theme_photo("us-ski-snowboard")
    assert key is not None
    assert key.startswith("brands/kodiak/raw-ingest/")
    base = key.lower()
    for name in _ATHLETE_NAMES:
        assert name not in base, f"us-ski-snowboard seed leaks athlete token {name!r}: {key}"


def test_scene_prompt_carries_winter_guidance_no_athlete_name(tmp_path):
    # boto3 offline path returns the deterministic default_prompt, which folds in the
    # _THEME_SCENE_HINT winter guidance. Assert on-theme + no real athlete name.
    src = _png(tmp_path / "seed.png")
    prompt = generate._nova_pro_scene_prompt(
        src, "Power Cakes", "athlete fuel", "US-UT", "active athletes",
        theme="us-ski-snowboard",
    )
    low = prompt.lower()
    assert "wasatch" in low or "alpine" in low or "snow" in low
    for name in _ATHLETE_NAMES:
        assert name not in low, f"scene prompt leaks athlete token {name!r}: {prompt}"


def test_theme_routes_through_generate_hero_set(tmp_path, monkeypatch):
    # theme flows through the set builder like any other theme: provenance carries the
    # theme and the three delivery ratios, brand overlay applied. Offline: DAM disabled,
    # engines patched to None so the deterministic fallback path is exercised.
    import creative_automation.dam as dam

    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)

    out_dir = tmp_path / "set"
    renders, source, provenance = generate.generate_hero_set(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="athlete fuel before the training day",
        region="US-UT",
        audience="active athletes",
        out_dir=out_dir,
        theme="us-ski-snowboard",
    )
    # three delivery ratios produced
    assert [r["ratio"] for r in renders] == ["1x1", "4x5", "2x3"]
    for r in renders:
        assert r["path"].exists()
    # provenance carries the theme + per-ratio engine record
    assert provenance.get("theme") == "us-ski-snowboard"
    assert set(provenance.get("ratios", {}).keys()) == {"1x1", "4x5", "2x3"}
    assert provenance.get("overlay_applied") is True
