"""Retailer overlay wiring — OFFLINE, cred-free.

Resolver (retailers.resolve_retailer_logo, asset-store-first with local fallback) +
retailer_logo layer compositing (generate._resolve_retailer_mark /
_apply_layer_marks) for costco/publix/target/walmart; kroger/heb/whole-foods
stay copy-sidecar only.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import asset_store, generate, retailers


def test_overlay_sets():
    assert set(retailers.OVERLAY_RETAILERS) == {"costco", "publix", "target", "walmart"}
    assert set(retailers.COPY_ONLY_RETAILERS) == {"kroger", "heb", "whole-foods"}


def test_normalize_overlay_retailer():
    assert retailers.normalize_overlay_retailer("Costco") == "costco"
    assert retailers.normalize_overlay_retailer("Publix") == "publix"
    assert retailers.normalize_overlay_retailer("Target") == "target"
    assert retailers.normalize_overlay_retailer("Walmart") == "walmart"
    assert retailers.normalize_overlay_retailer("Wal-Mart Supercenter") == "walmart"
    assert retailers.normalize_overlay_retailer("kroger") == "kroger"
    assert retailers.normalize_overlay_retailer("H-E-B") == "heb"
    assert retailers.normalize_overlay_retailer("Whole Foods Market") == "whole-foods"
    # subscription is fulfillment, never a mark; unknown names stay unknown.
    assert retailers.normalize_overlay_retailer("subscription") is None
    assert retailers.normalize_overlay_retailer("Safeway") is None
    # chooser contract untouched: walmart/kroger still unknown to normalize_retailer.
    assert retailers.normalize_retailer("walmart") is None
    assert retailers.normalize_retailer("kroger") is None


def test_asset_store_keys():
    assert retailers.asset_key_for_retailer("walmart") == "brands/retailers/logos/walmart.png"
    assert retailers.asset_key_for_retailer("costco") == "brands/retailers/logos/costco.png"
    assert retailers.asset_key_for_retailer("target", variant="mono") == (
        "brands/retailers/logos/target-mono.png"
    )


def test_resolve_logo_offline_missing_is_none(tmp_path):
    # empty logo dir + S3 disabled -> None, never raises, never fabricates.
    assert retailers.resolve_retailer_logo("walmart", logo_dir=tmp_path) is None
    assert retailers.resolve_retailer_logo("costco", logo_dir=tmp_path) is None


def test_resolve_logo_copy_only_never_resolves_even_with_file(tmp_path):
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(tmp_path / "kroger.png", "PNG")
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(tmp_path / "heb.png", "PNG")
    Image.new("RGBA", (64, 64), (255, 0, 0, 255)).save(tmp_path / "whole-foods.png", "PNG")
    assert retailers.resolve_retailer_logo("kroger", logo_dir=tmp_path) is None
    assert retailers.resolve_retailer_logo("heb", logo_dir=tmp_path) is None
    assert retailers.resolve_retailer_logo("whole-foods", logo_dir=tmp_path) is None
    assert retailers.resolve_retailer_logo("nope", logo_dir=tmp_path) is None


def test_resolve_logo_local_fallback(tmp_path):
    Image.new("RGBA", (200, 80), (0, 90, 180, 255)).save(tmp_path / "walmart.png", "PNG")
    hit = retailers.resolve_retailer_logo("walmart", logo_dir=tmp_path)
    assert hit == tmp_path / "walmart.png"


def test_resolve_mark_delegates_to_asset_store_first_resolver(tmp_path, monkeypatch):
    Image.new("RGBA", (200, 80), (0, 90, 180, 255)).save(tmp_path / "target.png", "PNG")
    monkeypatch.setattr(retailers, "LOGO_DIR", tmp_path)
    assert generate._resolve_retailer_mark("target") == tmp_path / "target.png"
    # copy-only + unknown slugs resolve to None -> clean image ships.
    assert generate._resolve_retailer_mark("kroger") is None
    assert generate._resolve_retailer_mark("heb") is None
    assert generate._resolve_retailer_mark("whole-foods") is None
    assert generate._resolve_retailer_mark("safeway") is None


def test_layer_marks_missing_retailer_ships_clean_with_provenance(tmp_path, monkeypatch):
    base = tmp_path / "clean.png"
    Image.new("RGB", (400, 400), (120, 160, 140)).save(base, "PNG")
    before = base.read_bytes()
    prov: dict = {}
    empty = tmp_path / "empty-logos"
    empty.mkdir()
    monkeypatch.setattr(retailers, "LOGO_DIR", empty)
    monkeypatch.setattr(generate, "_RETAILER_LOGO_CACHE", {}) if hasattr(generate, "_RETAILER_LOGO_CACHE") else None
    generate._apply_layer_marks(base, {"retailer": "walmart"}, prov)
    assert base.read_bytes() == before
    assert prov.get("retailer_layer") == "unresolved:walmart"


def test_layer_marks_composites_mark_bottom_right(tmp_path, monkeypatch):
    base = tmp_path / "clean.png"
    Image.new("RGB", (400, 400), (10, 10, 10)).save(base, "PNG")
    Image.new("RGBA", (200, 80), (255, 255, 255, 255)).save(tmp_path / "walmart.png", "PNG")
    monkeypatch.setattr(retailers, "LOGO_DIR", tmp_path)
    prov: dict = {}
    generate._apply_layer_marks(base, {"retailer": "walmart"}, prov)
    assert prov.get("layer_marks") == ["retailer:walmart"]
    img = Image.open(base).convert("RGB")
    w, h = img.size
    # lockup geometry: bottom-right carries the white backing plate now.
    assert img.getpixel((w - 5, h - 5)) == (255, 255, 255)
    # top-left untouched.
    assert img.getpixel((5, 5)) == (10, 10, 10)


# ------------------------------------------------- Pillow verification (sprint-2)
# Garbage bytes in EITHER mark source (the asset store /tmp cache or the repo-local
# logo_dir) resolve to None — the render ships clean with the copy-sidecar
# retailer line, never a paste-time blowup.
_GARBAGE = b"\x00\x01garbage-not-an-image" * 64
_TRUNCATED_PNG = (
    b"\x89PNG\r\n\x1a\n" + b"\x00\x01truncated" * 64  # valid header, junk body
)


def _isolate_resolution(monkeypatch, tmp_path):
    """Offline + hermetic: asset store fetch stubbed, logo sources are tmp dirs."""
    cache = tmp_path / "cache"
    cache.mkdir()
    empty = tmp_path / "empty-logos"
    empty.mkdir()
    monkeypatch.setattr(retailers, "RETAILER_LOGO_CACHE_DIR", cache)
    monkeypatch.setattr(asset_store, "fetch_asset_key", lambda key, dest: None)
    return cache, empty


def test_resolve_logo_garbage_bytes_in_logo_dir_is_none(tmp_path, monkeypatch):
    _isolate_resolution(monkeypatch, tmp_path)
    (tmp_path / "walmart.png").write_bytes(_GARBAGE)
    (tmp_path / "costco.png").write_bytes(_TRUNCATED_PNG)
    assert retailers.resolve_retailer_logo("walmart", logo_dir=tmp_path) is None
    assert retailers.resolve_retailer_logo("costco", logo_dir=tmp_path) is None


def test_resolve_logo_garbage_bytes_in_asset_store_cache_is_none(tmp_path, monkeypatch):
    _cache, empty = _isolate_resolution(monkeypatch, tmp_path)

    def _garbage_fetch(key: str, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_GARBAGE)
        return dest

    monkeypatch.setattr(asset_store, "fetch_asset_key", _garbage_fetch)
    # garbage in the asset store cache + empty local dir -> None, never raises.
    assert retailers.resolve_retailer_logo("walmart", logo_dir=empty) is None


def test_resolve_logo_asset_store_garbage_falls_back_to_valid_local(tmp_path, monkeypatch):
    _cache, _empty = _isolate_resolution(monkeypatch, tmp_path)

    def _garbage_fetch(key: str, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(_TRUNCATED_PNG)
        return dest

    monkeypatch.setattr(asset_store, "fetch_asset_key", _garbage_fetch)
    Image.new("RGBA", (200, 80), (0, 90, 180, 255)).save(tmp_path / "walmart.png", "PNG")
    # the corrupt cache entry is skipped; the valid local mark still resolves.
    assert retailers.resolve_retailer_logo("walmart", logo_dir=tmp_path) == (
        tmp_path / "walmart.png"
    )


def test_resolve_logo_asset_store_valid_hit_still_resolves(tmp_path, monkeypatch):
    _cache, empty = _isolate_resolution(monkeypatch, tmp_path)

    def _valid_fetch(key: str, dest: Path):
        dest.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGBA", (200, 80), (0, 90, 180, 255)).save(dest, "PNG")
        return dest

    monkeypatch.setattr(asset_store, "fetch_asset_key", _valid_fetch)
    # verification is not a blanket reject: a decodable asset store mark still resolves.
    assert retailers.resolve_retailer_logo("walmart", logo_dir=empty) == (
        retailers.RETAILER_LOGO_CACHE_DIR / "walmart.png"
    )


def test_layer_marks_garbage_mark_ships_clean(tmp_path, monkeypatch):
    # end to end: a garbage mark file never reaches the canvas — the clean
    # image ships untouched and the layer is recorded unresolved.
    base = tmp_path / "clean.png"
    Image.new("RGB", (400, 400), (120, 160, 140)).save(base, "PNG")
    before = base.read_bytes()
    (tmp_path / "walmart.png").write_bytes(_GARBAGE)
    monkeypatch.setattr(retailers, "LOGO_DIR", tmp_path)
    monkeypatch.setattr(asset_store, "fetch_asset_key", lambda key, dest: None)
    prov: dict = {}
    generate._apply_layer_marks(base, {"retailer": "walmart"}, prov)
    assert base.read_bytes() == before
    assert prov.get("retailer_layer") == "unresolved:walmart"


# ------------------------------------------- unwritable out_dir (sprint-2 ladder)
# An unwritable out_dir degrades to rung D at a recorded tmp fallback — never
# an uncaught OSError / 500. The out_dir is blocked deterministically with a
# regular file (no chmod, so it holds whatever uid runs the suite).
def _isolate_ladder(monkeypatch):
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: None)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)


def test_generate_hero_unwritable_out_dir_degrades_to_rung_d(tmp_path, monkeypatch):
    _isolate_ladder(monkeypatch)
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"x")
    out = blocker / "hero.png"
    # must NOT raise.
    result, source, prov = generate.generate_hero(
        product_id="no-such-sku",
        product_name="No Such Product",
        brief_msg="frontier trail energy",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert Image.open(result).size == (1080, 1080)
    assert source == generate.BRAND_FLOOR_SOURCE == "brand-floor"
    assert prov["rung"] == "D"
    degrade = prov.get("out_dir_degrade")
    assert degrade is not None
    assert degrade["requested"] == str(out)
    assert Path(degrade["actual"]) == result


def test_generate_hero_rung_d_save_failure_retries_tmp(tmp_path, monkeypatch):
    # Late write failure (read-only dir: mkdir passed, save denied) — rung D
    # retries once at a recorded tmp fallback instead of raising.
    _isolate_ladder(monkeypatch)
    real_floor = generate._brand_floor
    calls = {"n": 0}

    def _flaky(product_name, ratio, out_path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("read-only directory")
        return real_floor(product_name, ratio, out_path)

    monkeypatch.setattr(generate, "_brand_floor", _flaky)
    out = tmp_path / "hero.png"
    result, source, prov = generate.generate_hero(
        product_id="no-such-sku",
        product_name="No Such Product",
        brief_msg="frontier trail energy",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert calls["n"] == 2
    assert result.exists()
    assert prov["rung"] == "D"
    assert prov["out_dir_degrade"]["requested"] == str(out)


def test_generate_hero_set_unwritable_out_dir_degrades(tmp_path, monkeypatch):
    _isolate_ladder(monkeypatch)
    monkeypatch.setattr(
        generate, "_headline_for", lambda *a, **k: ("Wild Mornings", None)
    )
    monkeypatch.setattr(generate, "_STABILITY_RUNG_ON", False)
    blocker = tmp_path / "blocker"
    blocker.write_bytes(b"x")
    out_dir = blocker / "set"
    renders, _source, prov = generate.generate_hero_set(
        product_id="no-such-sku",
        product_name="No Such Product",
        brief_msg="frontier trail energy",
        region="us",
        audience="active families",
        out_dir=out_dir,
    )
    assert len(renders) == 4
    for r in renders:
        assert Path(r["path"]).exists()
    assert prov.get("out_dir_degrade", {}).get("requested") == str(out_dir)
