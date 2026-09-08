"""Offline tests for the real-photo scene composer + sku-photo-map resolver.

No network: DAM is disabled (no DAM_S3_BUCKET), the logo fetch is mocked to None,
and the scene composer is fed a small local temp PNG as the "real photo".
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from creative_automation import generate


def _make_photo(path: Path, size: tuple[int, int] = (400, 300)) -> Path:
    """A small non-uniform PNG so cover-fit + scrim still leaves visible variance."""
    img = Image.new("RGB", size, (20, 40, 60))
    # paint some blocks so the image is clearly not a solid color
    for x in range(0, size[0], 40):
        band = (200, 120 + (x % 100), 30 + (x % 60))
        for xx in range(x, min(x + 20, size[0])):
            for yy in range(size[1]):
                img.putpixel((xx, yy), band)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


def test_resolve_dam_photo_known_handle() -> None:
    key = generate._resolve_dam_photo("blueberry-muffin-mix")
    assert key is not None
    assert key.startswith("brands/kodiak/raw-ingest/")


def test_resolve_dam_photo_unknown_handle() -> None:
    assert generate._resolve_dam_photo("nonexistent-sku") is None


def test_compose_scene_canvas_sizes_and_not_solid(tmp_path: Path) -> None:
    photo = _make_photo(tmp_path / "photo.png")
    expected = {"1x1": (1080, 1080), "9x16": (1080, 1920), "16x9": (1920, 1080)}
    for ratio, dims in expected.items():
        out = tmp_path / f"scene-{ratio}.png"
        # no logo param anymore — Kodiak campaigns carry no logo (brand pref)
        result = generate._compose_scene(photo, "Wild Protein Mornings", ratio, out, idx=0)
        assert result.exists()
        with Image.open(result) as img:
            assert img.size == dims
            # real photo shows through: many distinct colors, not a solid fill
            colors = img.convert("RGB").getcolors(maxcolors=100000)
            assert colors is not None
            assert len(colors) > 50


def test_generate_hero_dam_disabled_falls_back_gracefully(tmp_path: Path, monkeypatch) -> None:
    # map entry exists but DAM is disabled (no creds) -> must fall back to disk or
    # mock, never raise. Force fetch_dam_key + disk discovery + logo to None.
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: "brands/kodiak/raw-ingest/x.jpg")
    import creative_automation.dam as dam

    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: None)

    out = tmp_path / "hero.png"
    result, source, _prov = generate.generate_hero(
        product_id="blueberry-muffin-mix",
        product_name="Blueberry Muffin Mix",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    # DAM + disk both unavailable, no packshot -> the ladder's rung D (brand-floor)
    assert source == generate.BRAND_FLOOR_SOURCE
    assert "mock" not in source


def test_resolve_map_path_env_override(tmp_path: Path, monkeypatch) -> None:
    # env var points at a shipped copy -> _resolve_map_path returns it AND the
    # resolver reads that map (mirrors the Lambda /var/task layout).
    map_file = tmp_path / "sku-photo-map.json"
    map_file.write_text(
        json.dumps(
            {
                "map": {
                    "x-sku": {
                        "photo_key": "brands/kodiak/raw-ingest/x.jpg",
                        "image_file": "x.jpg",
                        "channel": "blog",
                        "caption": "c",
                        "score": 1,
                        "fallbacks": [],
                        "matched": True,
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("SKU_PHOTO_MAP_PATH", str(map_file))
    generate._SKU_PHOTO_MAP_CACHE = None
    try:
        assert generate._resolve_map_path() == map_file
        assert generate._resolve_dam_photo("x-sku") == "brands/kodiak/raw-ingest/x.jpg"
    finally:
        generate._SKU_PHOTO_MAP_CACHE = None



# --------------------------------------------------------------- theme-aware generation


def test_resolve_theme_photo_known_theme() -> None:
    key = generate._resolve_theme_photo("zac-efron")
    assert key is not None
    assert key.startswith("brands/kodiak/raw-ingest/")


def test_resolve_theme_photo_unknown_theme() -> None:
    assert generate._resolve_theme_photo("nonexistent") is None


def test_generate_hero_theme_dam_disabled_falls_back_gracefully(tmp_path: Path, monkeypatch) -> None:
    # theme resolves to a real key, but DAM is disabled (fetch -> None) and there is
    # no disk asset -> must fall back to the placeholder, never raise.
    import creative_automation.dam as dam

    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: None)

    out = tmp_path / "hero-theme.png"
    result, source, _prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="athletic mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        theme="zac-efron",
    )
    assert result.exists()
    assert source == generate.BRAND_FLOOR_SOURCE


def test_generate_hero_theme_composes_on_fetched_photo(tmp_path: Path, monkeypatch) -> None:
    # theme resolves and fetch_dam_key returns a real local png. With the Stability
    # engine unavailable (patched -> None), generate_hero downgrades to the Pillow
    # scene composer and reports "bedrock:nova-pro" (the chip theme drove the image).
    photo = _make_photo(tmp_path / "theme-src.png")
    import creative_automation.dam as dam

    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: photo)
    # Nova Pro offline -> caption None -> brief headline used; keep deterministic
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)
    # Stability offline -> None so the compose fallback (bedrock:nova-pro) is exercised
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, prompt, out: None)
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt", lambda *a, **k: "scene")

    out = tmp_path / "hero-theme-ok.png"
    result, source, _prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="athletic mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        theme="zac-efron",
    )
    assert result.exists()
    assert source == "bedrock:nova-pro"


def test_compose_scene_has_no_logo() -> None:
    # off-brand overlay stripped: _fetch_logo removed AND _compose_scene dropped the
    # logo param. Assert both — real, simple, no visual diffing.
    import inspect

    assert not hasattr(generate, "_fetch_logo")
    assert "logo" not in inspect.signature(generate._compose_scene).parameters


def test_generate_hero_theme_none_preserves_product_path(tmp_path: Path, monkeypatch) -> None:
    # regression: theme=None (default) must NOT touch the theme resolver — the product
    # sku-photo-map path drives the image exactly as before.
    photo = _make_photo(tmp_path / "product-src.png")
    import creative_automation.dam as dam

    called = {"theme_resolver": 0}

    def _spy_theme(slug: str):  # pragma: no cover - asserted via counter
        called["theme_resolver"] += 1
        return None

    monkeypatch.setattr(generate, "_resolve_theme_photo", _spy_theme)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: "brands/kodiak/raw-ingest/x.jpg")
    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: photo)
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)
    # Stability offline -> None so the compose fallback (bedrock:nova-pro) is exercised
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, prompt, out: None)
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt", lambda *a, **k: "scene")

    out = tmp_path / "hero-product.png"
    result, source, _prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert source == "bedrock:nova-pro"
    # theme=None short-circuits before the theme resolver is ever consulted
    assert called["theme_resolver"] == 0


def test_theme_photo_seed_skips_nova_scene_prompt(tmp_path: Path, monkeypatch) -> None:
    # Theme-photo fast path: the seed already carries the theme, so rung B must
    # NOT spend a Nova vision call — deterministic default instead, rung C kept.
    photo = _make_photo(tmp_path / "zac-src.png")
    import creative_automation.dam as dam

    monkeypatch.setattr(dam, "fetch_dam_key", lambda key, dest: photo)
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, prompt, out: None)
    calls: list = []
    monkeypatch.setattr(
        generate, "_nova_pro_scene_prompt", lambda *a, **k: calls.append(1) or "scene"
    )

    out = tmp_path / "hero-zac-fast.png"
    result, source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="athletic mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
        theme="zac-efron",
    )
    assert result.exists()
    assert calls == [], "theme-photo seed must skip the Nova scene vision call"
    assert prov["seed_selection"] == "theme-photo"
    assert "athletic-morning" in prov["scene_prompt"]
    assert "untouched" in prov["scene_prompt"]


def test_default_scene_prompt_deterministic_and_themed() -> None:
    a = generate._default_scene_prompt("Power Cakes", "brief", "us", "families", "zac-efron")
    b = generate._default_scene_prompt("Power Cakes", "brief", "us", "families", "zac-efron")
    assert a == b
    assert "Power Cakes" in a and "frontier morning light" in a
    assert "on-brand Kodiak" not in a
    c = generate._default_scene_prompt("Power Cakes", "brief", "us", "families", None)
    assert "brief" in c
