"""Multi-theme combination rule: one primary drives seed+scene, extras layer on.

Offline: the combo rule + scene fold + sidecar lines are pure deterministic
code over the committed theme-asset-map; the end-to-end hero tests mock the
asset store fetch + Stability rung so no AWS is touched.
"""
from __future__ import annotations

import io
import json
from pathlib import Path

from PIL import Image

from creative_automation import generate

PRIMARY = "wild-grizzly-bears"
EXTRA = "localized-costco"


def _png_bytes(size=(512, 512), color=(180, 90, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _make_seed(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_bytes())
    return path


# ---------------------------------------------------------------- rule proper
def test_combine_themes_primary_extras_copy_and_overlay() -> None:
    combo = generate.combine_themes([PRIMARY, EXTRA])
    assert combo["themes"] == [PRIMARY, EXTRA]
    assert combo["primary"] == PRIMARY
    assert combo["extras"] == [EXTRA]
    assert combo["unknown"] == []
    assert combo["panel_flag"] is None
    # retailer extra maps to a mark-only overlay layer: no scene text, ever.
    assert len(combo["overlay_layers"]) == 1
    layer = combo["overlay_layers"][0]
    assert layer["theme"] == EXTRA
    assert layer["scene"] == ""
    assert layer["mark"] is True
    # extra maps to a copy line carrying its copy framing
    assert len(combo["copy_lines"]) == 1
    assert combo["copy_lines"][0]["theme"] == EXTRA
    assert "Family Size" in combo["copy_lines"][0]["framing"]


def test_combine_themes_unknown_raises_panel_flag_not_exception() -> None:
    combo = generate.combine_themes([PRIMARY, "nope-not-a-theme"])
    assert combo["primary"] == PRIMARY
    assert combo["extras"] == []
    assert combo["unknown"] == ["nope-not-a-theme"]
    assert combo["panel_flag"] is not None
    assert combo["panel_flag"].startswith(generate.PANEL_FLAG_THEME_MISMATCH)
    assert "nope-not-a-theme" in combo["panel_flag"]


def test_combine_themes_all_unknown_has_no_primary_but_flags() -> None:
    combo = generate.combine_themes(["bogus-one", "bogus-two"])
    assert combo["primary"] is None
    assert combo["extras"] == []
    assert combo["unknown"] == ["bogus-one", "bogus-two"]
    assert combo["panel_flag"] is not None


def test_combine_themes_normalizes_string_dupes_and_case() -> None:
    combo = generate.combine_themes("Wild-Grizzly-Bears, wild-grizzly-bears , localized-target")
    assert combo["themes"] == [PRIMARY, "localized-target"]
    assert combo["primary"] == PRIMARY
    assert combo["extras"] == ["localized-target"]


def test_combine_themes_empty_is_clean() -> None:
    combo = generate.combine_themes([])
    assert combo == {
        "themes": [],
        "primary": None,
        "extras": [],
        "overlay_layers": [],
        "copy_lines": [],
        "unknown": [],
        "panel_flag": None,
    }


# ------------------------------------------------------- scene-prompt folding
def test_default_scene_prompt_folds_extras_as_overlay() -> None:
    prompt = generate._default_scene_prompt(
        "Power Cakes", "wild mornings", "us", "families", PRIMARY, [EXTRA]
    )
    assert "grizzly-country meadow" in prompt  # primary scene still leads
    # retailer extra contributes zero pixel text — mark ships via overlay only.
    assert "Also layering" not in prompt
    assert "warehouse-club" not in prompt
    assert "aisle" not in prompt
    assert "pallet" not in prompt


def test_default_scene_prompt_without_extras_unchanged() -> None:
    prompt = generate._default_scene_prompt(
        "Power Cakes", "wild mornings", "us", "families", PRIMARY
    )
    assert "Also layering" not in prompt


def test_nova_scene_prompt_offline_fallback_folds_extras(monkeypatch) -> None:
    # boto3 absent -> deterministic default path, extras still folded
    monkeypatch.setattr(generate, "boto3", None)
    prompt = generate._nova_pro_scene_prompt(
        Path("seed.png"), "Power Cakes", "wild mornings", "us", "families",
        PRIMARY, [EXTRA],
    )
    assert "Also layering" not in prompt
    assert "warehouse-club" not in prompt


# ------------------------------------------------------- hero end to end
def _mock_theme_seed(monkeypatch, tmp_path: Path):
    seed = _make_seed(tmp_path / "theme-seed.png")
    from creative_automation import asset_store

    monkeypatch.setattr(asset_store, "fetch_asset_key", lambda key, dest: seed)
    monkeypatch.setattr(generate, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
    # rung B records the scene prompt, then the mocked restyle falls to rung C
    monkeypatch.setattr(generate, "_stability_control_hero", lambda s, p, o: None)
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: "")
    return seed


def test_generate_hero_combo_primary_drives_seed_and_scene(tmp_path: Path, monkeypatch) -> None:
    _mock_theme_seed(monkeypatch, tmp_path)
    out = tmp_path / "hero.png"
    result, _source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        themes=[PRIMARY, EXTRA],
    )
    assert result.exists()
    assert prov["seed_selection"] == "theme-photo"
    assert prov["theme"] == PRIMARY  # primary drives seed + scene
    assert prov["themes"] == [PRIMARY, EXTRA]
    assert prov["theme_combo"]["primary"] == PRIMARY
    assert prov["theme_combo"]["extras"] == [EXTRA]
    assert prov["panel_flag"] is None
    # retailer extra leaves zero pixel text; combo recorded in provenance.
    assert prov["scene_prompt"] is not None
    assert "Also layering" not in prov["scene_prompt"]
    assert "warehouse-club" not in prov["scene_prompt"]


def test_generate_hero_themes_overrides_single_theme(tmp_path: Path, monkeypatch) -> None:
    _mock_theme_seed(monkeypatch, tmp_path)
    out = tmp_path / "hero.png"
    _result, _source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        theme="localized-target",
        themes=[PRIMARY],
    )
    assert prov["theme"] == PRIMARY


def test_generate_hero_combo_unknown_flags_panel_never_raises(
    tmp_path: Path, monkeypatch
) -> None:
    _mock_theme_seed(monkeypatch, tmp_path)
    out = tmp_path / "hero.png"
    result, _source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        themes=["bogus-theme-xyz"],
    )
    assert result.exists()
    assert prov["panel_flag"] is not None
    assert prov["panel_flag"].startswith(generate.PANEL_FLAG_THEME_MISMATCH)
    assert "bogus-theme-xyz" in prov["panel_flag"]
    assert prov["theme"] is None  # no known primary -> no theme driver


def test_generate_hero_single_theme_path_unchanged(tmp_path: Path, monkeypatch) -> None:
    # themes=None preserves the legacy contract: no combo keys populated
    _mock_theme_seed(monkeypatch, tmp_path)
    out = tmp_path / "hero.png"
    _result, _source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        theme=PRIMARY,
    )
    assert prov["theme"] == PRIMARY
    assert prov["themes"] is None
    assert prov["theme_combo"] is None
    assert prov["panel_flag"] is None
    assert "Also layering" not in (prov.get("scene_prompt") or "")


# ------------------------------------------------------- copy sidecar lines
def test_build_copy_sidecar_emits_combo_and_extra_lines() -> None:
    combo = generate.combine_themes([PRIMARY, EXTRA])
    prov = {"theme_combo": {k: combo[k] for k in ("primary", "extras", "copy_lines")},
            "panel_flag": None, "copy_headline": "Wild Mornings"}
    sidecar = generate.build_copy_sidecar(prov, "wild mornings", {}, PRIMARY, "power-cakes")
    assert f"theme combo: {PRIMARY} + {EXTRA}" in sidecar["txt"]
    assert f"extra framing ({EXTRA})" in sidecar["txt"]
    assert "Family Size" in sidecar["txt"]
    assert "field,value" in sidecar["csv"]
    assert "theme_combo" in sidecar["csv"]
    assert f"extra_framing.{EXTRA}" in sidecar["csv"]


def test_build_copy_sidecar_emits_panel_flag() -> None:
    prov = {"theme_combo": None, "panel_flag": "theme-mismatch: unknown theme(s): bogus",
            "copy_headline": "Wild Mornings"}
    sidecar = generate.build_copy_sidecar(prov, "wild mornings", {}, None, "power-cakes")
    assert "panel flag: theme-mismatch" in sidecar["txt"]
    assert "panel_flag" in sidecar["csv"]


def test_build_copy_sidecar_legacy_provenance_unchanged() -> None:
    sidecar = generate.build_copy_sidecar({}, "wild mornings", {}, PRIMARY, "power-cakes")
    assert "theme combo" not in sidecar["txt"]
    assert "panel flag" not in sidecar["txt"]
    assert json.loads(json.dumps(sidecar))  # JSON-serializable
