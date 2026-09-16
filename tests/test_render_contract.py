"""Render contract — issues #196/#199/#200.

Default Create returns a clean standalone image + copy sidecars; layers compose
thoughtfully only when selected (default OFF). layers=None preserves the legacy
ladder (packshot-first + baked overlay); ANY dict selects the clean contract.

Offline: no AWS. Seed/packshot resolution is monkeypatched; rung B's Bedrock
client is never reached (no seed, or rung A short-circuits first).
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

from PIL import Image

from creative_automation import dam, generate_lambda
from creative_automation import generate as generate_mod
from creative_automation.compose import compose_creative


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


def _isolate_from_seeds(monkeypatch):
    """No theme/sku/disk seed — the ladder sees only what each test stages."""
    monkeypatch.setattr(generate_mod, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate_mod, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(generate_mod, "_find_source_asset", lambda pid, name: None)


def _hero_kwargs(tmp_path: Path, **over) -> dict:
    kw = {
        "product_id": "banana-muffin-quick-bread-mix",
        "product_name": "Banana Muffin and Quick Bread Mix",
        "brief_msg": "Fuel your frontier morning",
        "region": "us",
        "audience": "active families",
        "out_path": tmp_path / "hero.png",
        "idx": 0,
    }
    kw.update(over)
    return kw


# --------------------------------------------------------------------------- #
# normalize_layers
# --------------------------------------------------------------------------- #
def test_layers_none_stays_none_legacy():
    assert generate_mod.normalize_layers(None) is None


def test_layers_empty_dict_selects_clean_contract():
    assert generate_mod.normalize_layers({}) == {}


def test_layers_drops_unknown_keys():
    norm = generate_mod.normalize_layers(
        {"product_image": True, "drop_shadow": True, "retailer": "Costco "}
    )
    assert norm == {"product_image": True, "retailer": "costco"}


def test_layers_blank_retailer_dropped():
    assert generate_mod.normalize_layers({"retailer": "  "}) == {}


# --------------------------------------------------------------------------- #
# build_copy_sidecar (#199)
# --------------------------------------------------------------------------- #
def test_sidecar_txt_and_csv_carry_copy():
    prov = {"copy_headline": "Fuel Your Frontier Morning", "headline": None}
    platform_copy = {
        "instagram": {
            "headline": "Wild Mornings",
            "body": "Stack up",
            "hashtags": ["#KeepItWild"],
            "source": "fallback",
        }
    }
    sidecar = generate_mod.build_copy_sidecar(
        prov, "Fuel your frontier morning", platform_copy, theme=None,
        product="banana-muffin-quick-bread-mix",
    )
    assert "Fuel Your Frontier Morning" in sidecar["txt"]
    assert "[instagram]" in sidecar["txt"]
    rows = list(csv.reader(io.StringIO(sidecar["csv"])))
    assert rows[0] == ["field", "value"]
    by_field = {r[0]: r[1] for r in rows[1:]}
    assert by_field["headline"] == "Fuel Your Frontier Morning"
    assert by_field["instagram.body"] == "Stack up"
    assert by_field["instagram.hashtags"] == "#KeepItWild"


def test_sidecar_falls_back_to_brief():
    sidecar = generate_mod.build_copy_sidecar({}, "a bear eating pancakes")
    assert "a bear eating pancakes" in sidecar["txt"]
    assert "a bear eating pancakes" in sidecar["csv"]


# --------------------------------------------------------------------------- #
# compose_creative placement (#200 — never center-pasted when layered)
# --------------------------------------------------------------------------- #
def test_thirds_placement_avoids_center(tmp_path):
    bg = tmp_path / "bg.png"
    box = tmp_path / "box.png"
    Image.new("RGB", (1080, 1080), (10, 20, 200)).save(bg, "PNG")
    Image.new("RGBA", (400, 600), (200, 120, 40, 255)).save(box, "PNG")

    centered = compose_creative(
        bg, tmp_path / "centered.png", "", "1x1", product_layer=box, bare=True,
    )
    layered = compose_creative(
        bg, tmp_path / "layered.png", "", "1x1", product_layer=box, bare=True,
        placement="thirds",
    )
    box_rgb = (200, 120, 40)
    with Image.open(centered).convert("RGB") as im:
        assert im.getpixel((400, 500)) == box_rgb  # center-frame box covers x=400
    with Image.open(layered).convert("RGB") as im:
        assert im.getpixel((400, 500)) != box_rgb  # thirds box starts right of x=400
        assert im.getpixel((600, 500)) == box_rgb  # but still on-canvas, composed


# --------------------------------------------------------------------------- #
# generate_hero clean contract (#199)
# --------------------------------------------------------------------------- #
def test_clean_default_skips_packshot_probe(tmp_path, monkeypatch):
    """layers={} never even resolves a box: no probe, no paste, no baked text."""
    _isolate_from_seeds(monkeypatch)
    probes = {"n": 0}

    def _probe(pid, **kwargs):
        probes["n"] += 1
        return _make_box_png(tmp_path / "box.png")

    monkeypatch.setattr(dam, "resolve_packshot", _probe)

    result, _source, prov = generate_mod.generate_hero(**_hero_kwargs(tmp_path, layers={}))

    assert result.exists()
    assert probes["n"] == 0
    assert prov["clean"] is True
    assert prov["layers"] == {}
    assert prov["rung"] == "D"  # no seed, no box -> brand floor, still real pixels
    assert prov["overlay_applied"] is False
    assert prov["headline"] is None
    assert prov["copy_headline"]  # copy ships as sidecar, not pixels


def test_clean_product_layer_pastes_without_baked_text(tmp_path, monkeypatch):
    """Selected product_image layer: rung A composite, thirds placement, no text bar."""
    monkeypatch.setattr(dam, "fetch_dam_key", _local_box_fetch(tmp_path))
    _isolate_from_seeds(monkeypatch)
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero", lambda s, p, o: None
    )

    result, _source, prov = generate_mod.generate_hero(
        **_hero_kwargs(tmp_path, layers={"product_image": True})
    )

    assert result.exists()
    assert prov["rung"] == "A"
    assert prov["packshot"] is not None
    assert prov["overlay_applied"] is False
    assert prov["headline"] is None
    assert prov["copy_headline"]
    # thirds placement: the box sits right of center-frame (see placement unit test).
    with Image.open(result).convert("RGB") as im:
        assert im.getpixel((120, 500)) != (200, 120, 40)


def test_legacy_none_keeps_packshot_and_overlay(tmp_path, monkeypatch):
    """layers=None preserves the legacy ladder byte-for-behavior."""
    monkeypatch.setattr(dam, "fetch_dam_key", _local_box_fetch(tmp_path))
    _isolate_from_seeds(monkeypatch)
    monkeypatch.setattr(
        generate_mod, "_stability_control_hero", lambda s, p, o: None
    )

    result, _source, prov = generate_mod.generate_hero(**_hero_kwargs(tmp_path))

    assert result.exists()
    assert prov["rung"] == "A"
    assert prov["clean"] is False
    assert prov["overlay_applied"] is True
    assert prov["headline"]


# --------------------------------------------------------------------------- #
# layer marks (#200)
# --------------------------------------------------------------------------- #
def test_partner_mark_applies_when_selected(tmp_path):
    base = tmp_path / "base.png"
    Image.new("RGB", (1080, 1080), (30, 40, 50)).save(base, "PNG")
    prov: dict = {}
    generate_mod._apply_layer_marks(base, {"partner_logo": True}, prov)
    assert prov.get("layer_marks") == ["partner_logo"]
    with Image.open(base).convert("RGB") as im:
        # bottom-left mark region is no longer the flat base fill
        assert im.getpixel((60, 1020)) != (30, 40, 50)


def test_unresolved_retailer_ships_clean(tmp_path):
    base = tmp_path / "base.png"
    Image.new("RGB", (1080, 1080), (30, 40, 50)).save(base, "PNG")
    before = base.read_bytes()
    prov: dict = {}
    generate_mod._apply_layer_marks(base, {"retailer": "costco"}, prov)
    assert prov.get("retailer_layer") == "unresolved:costco"
    assert "layer_marks" not in prov
    assert base.read_bytes() == before  # clean image untouched


# --------------------------------------------------------------------------- #
# lambda surfaces layers + sidecars (#199)
# --------------------------------------------------------------------------- #
class _FakeS3:
    def put_object(self, **kwargs) -> dict:
        return {}

    def generate_presigned_url(self, op, Params, ExpiresIn) -> str:
        return f"https://presigned.example/{Params['Key']}?exp={ExpiresIn}"


def _stub_preview_hero(**kwargs):
    from PIL import Image as _Image

    out = Path(kwargs["out_path"])
    out.parent.mkdir(parents=True, exist_ok=True)
    _Image.new("RGB", (1080, 1080), (10, 20, 30)).save(out, "PNG")
    prov = {
        "engine": "pillow-compose",
        "rung": "C",
        "copy_headline": "Fuel Your Frontier Morning",
        "headline": None,
        "overlay_applied": False,
        "ratios": {"1x1": "primary"},
    }
    _stub_preview_hero.seen = kwargs
    return out, "bedrock:nova-pro", prov


def test_preview_defaults_to_clean_with_sidecars(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(generate_lambda, "generate_hero", _stub_preview_hero)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: _FakeS3())

    import json as _json

    event = {"body": _json.dumps({"prompt": "a bear eating pancakes"})}
    resp = generate_lambda.handler(event, None)
    assert resp["statusCode"] == 200
    body = _json.loads(resp["body"])
    assert body["ok"] is True
    # default Create: clean contract, no baked overlay, copy as sidecars
    assert body["layers"] == {}
    assert _stub_preview_hero.seen["layers"] == {}
    assert _stub_preview_hero.seen["brand_overlay"] is False
    assert "Fuel Your Frontier Morning" in body["copy_sidecar"]["txt"]
    rows = list(csv.reader(io.StringIO(body["copy_sidecar"]["csv"])))
    assert rows[0] == ["field", "value"]
