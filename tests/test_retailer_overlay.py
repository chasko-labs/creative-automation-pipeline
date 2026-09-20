"""Retailer overlay wiring — OFFLINE, cred-free.

Resolver (retailers.resolve_retailer_logo, DAM-first with local fallback) +
retailer_logo layer compositing (generate._resolve_retailer_mark /
_apply_layer_marks) for costco/publix/target/walmart; kroger/heb/whole-foods
stay copy-sidecar only.
"""
from __future__ import annotations

from PIL import Image

from creative_automation import generate, retailers


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


def test_dam_keys():
    assert retailers.dam_key_for_retailer("walmart") == "brands/retailers/logos/walmart.png"
    assert retailers.dam_key_for_retailer("costco") == "brands/retailers/logos/costco.png"
    assert retailers.dam_key_for_retailer("target", variant="mono") == (
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


def test_resolve_mark_delegates_to_dam_first_resolver(tmp_path, monkeypatch):
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
