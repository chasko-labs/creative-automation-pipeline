"""Engine-key contract + origin field on the /generate provenance seam.

Pinned contract (owner orin):
  engine ∈ {packshot-composite (A), stability-restyle (B),
            pillow-compose (C), brand-floor (D)}
  origin == "backend" on every envelope generate_hero returns, and on the
  wall-timeout floor envelope in generate_lambda.

Rung B (live Bedrock) is not exercised here — no network in CI. Rungs A/C/D
run offline and must each carry the contract.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import asset_store
from creative_automation import generate as generate_mod

ENGINE_KEYS = {
    "packshot-composite",
    "stability-restyle",
    "pillow-compose",
    "brand-floor",
}


def _make_box_png(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", (400, 600), (200, 120, 40, 255)).save(path, "PNG")
    return path


def _local_box_fetch(_tmp: Path):
    def _fetch(key: str, dest: Path):
        if key and "705599" in key.rsplit("/", 1)[-1]:
            return _make_box_png(Path(dest))
        return None

    return _fetch


def _hero_kwargs(tmp_path, **over):
    kw = dict(
        product_id="banana-muffin-quick-bread-mix",
        product_name="Banana Muffin and Quick Bread Mix",
        brief_msg="Fuel your frontier morning",
        region="us",
        audience="active families",
        out_path=tmp_path / "hero.png",
        idx=0,
    )
    kw.update(over)
    return kw


def _no_seed(monkeypatch, seed=None):
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: seed)


def test_rung_a_carries_engine_key_and_origin(tmp_path, monkeypatch):
    monkeypatch.setattr(asset_store, "fetch_asset_key", _local_box_fetch(tmp_path))
    _no_seed(monkeypatch)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o: None)

    _, _, prov = generate_mod.generate_hero(**_hero_kwargs(tmp_path))

    assert prov["rung"] == "A"
    assert prov["engine"] == "packshot-composite"
    assert prov["engine"] in ENGINE_KEYS
    assert prov["origin"] == "backend"


def test_rung_c_carries_engine_key_and_origin(tmp_path, monkeypatch):
    seed = tmp_path / "seed.png"
    Image.new("RGB", (1024, 1024), (180, 90, 30)).save(seed, "PNG")
    _no_seed(monkeypatch, seed=seed)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o: None)
    # force the ladder past rung B (stability rung off -> straight to C)
    monkeypatch.setattr(generate_mod, "_STABILITY_RUNG_ON", False)

    _, _, prov = generate_mod.generate_hero(
        **_hero_kwargs(tmp_path, product_id="totally-made-up-sku-xyz")
    )

    assert prov["rung"] == "C"
    assert prov["engine"] == "pillow-compose"
    assert prov["engine"] in ENGINE_KEYS
    assert prov["origin"] == "backend"


def test_rung_d_carries_engine_key_and_origin(tmp_path, monkeypatch):
    _no_seed(monkeypatch)
    monkeypatch.setattr(asset_store, "resolve_packshot", lambda pid, asset_root=None: None)
    monkeypatch.setattr(generate_mod, "_stability_control_hero", lambda s, p, o: None)

    _, _, prov = generate_mod.generate_hero(
        **_hero_kwargs(tmp_path, product_id="no-such-sku", product_name="No Such Product")
    )

    assert prov["rung"] == "D"
    assert prov["engine"] == "brand-floor"
    assert prov["engine"] in ENGINE_KEYS
    assert prov["origin"] == "backend"
