"""Offline tests for the real-photo scene composer + sku-photo-map resolver.

No network: DAM is disabled (no DAM_S3_BUCKET), the logo fetch is mocked to None,
and the scene composer is fed a small local temp PNG as the "real photo".
"""
from __future__ import annotations

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
        # logo=None -> no DAM/network; explicit to keep offline-deterministic
        result = generate._compose_scene(photo, "Wild Protein Mornings", ratio, out, idx=0, logo=None)
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
    monkeypatch.setattr(generate, "_fetch_logo", lambda: None)

    out = tmp_path / "hero.png"
    result, source = generate.generate_hero(
        product_id="blueberry-muffin-mix",
        product_name="Blueberry Muffin Mix",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    # DAM + disk both unavailable -> true last-resort placeholder label
    assert source == generate.FALLBACK_SOURCE
    assert "mock" not in source
