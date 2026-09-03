"""Retailer-lockup compositor tests — OFFLINE, Pillow-only.

Covers the cr-1 carve-out: the one sanctioned text-in-image path. All logos are
currently MISSING (input_assets/retailer-logos/ empty), so these exercise the
graceful text-only degradation band. No AWS creds, no cairosvg required.
"""
from pathlib import Path

from PIL import Image

from creative_automation import cli, lockup
from creative_automation.enhance import _hex
from creative_automation.naming import ISO_NAME_RE


def _make_base(path: Path, size=(1080, 1080), bg=(120, 160, 140)) -> Path:
    """A flat base image to composite the lockup onto."""
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", size, bg).save(path, "PNG")
    return path


def _band_has_text(out_path: Path, band_frac: float = 0.16) -> bool:
    """True if the bottom band carries text pixels (parchment) over the scrim.

    The band is a bear-brown scrim; baked address/name text is parchment (#FFF8F0).
    Presence of near-parchment pixels inside the band proves text was rendered.
    """
    img = Image.open(out_path).convert("RGB")
    w, h = img.size
    band_top = int(h * (1 - band_frac))
    px = img.load()
    target = _hex("#FFF8F0")
    for y in range(band_top, h):
        for x in range(0, w):
            r, g, b = px[x, y]
            if abs(r - target[0]) < 30 and abs(g - target[1]) < 30 and abs(b - target[2]) < 30:
                return True
    return False


def test_costco_lockup_with_sf_seed_produces_iso_named_output(tmp_path):
    base = _make_base(tmp_path / "hero.png")
    # empty logo_dir -> all logos missing -> text-band degradation
    result = lockup.compose_retailer_lockup(base, "costco", logo_dir=tmp_path)

    out = result["out_path"]
    assert out.exists(), "lockup output file was not written"
    # iso-named via naming.build_iso_name (channel retailer-lockup)
    assert ISO_NAME_RE.match(out.name), f"{out.name} is not iso-named"
    # SF seed address resolved from STORE_ADDRESS_SEEDS (costco:san-francisco)
    assert result["store_address"] is not None
    assert "San Francisco" in result["store_address"]
    assert result["retailer"] == "costco"


def test_warnings_flag_missing_logo(tmp_path):
    base = _make_base(tmp_path / "hero.png")
    result = lockup.compose_retailer_lockup(base, "costco", logo_dir=tmp_path)
    # logo dir empty -> source is text-only band, warning names the drop path
    assert result["logo_source"] == "none"
    assert any("MISSING" in w for w in result["warnings"])
    assert any("retailer-logos/costco.svg" in w for w in result["warnings"])


def test_store_address_text_is_present_on_output(tmp_path):
    """The sanctioned cr-1 exception: address text IS baked onto the image."""
    base = _make_base(tmp_path / "hero.png")
    result = lockup.compose_retailer_lockup(
        base, "costco", store_address="Costco — 450 10th St, San Francisco, CA 94103",
        logo_dir=tmp_path,
    )
    assert result["store_address"] == "Costco — 450 10th St, San Francisco, CA 94103"
    assert _band_has_text(result["out_path"]), "store-address text not found in band"


def test_module_documents_itself_as_cr1_carveout():
    assert "cr-1 carve-out" in (lockup.__doc__ or ""), "module docstring must name the cr-1 carve-out"
    assert "cr-1 carve-out" in (lockup.compose_retailer_lockup.__doc__ or ""), \
        "compose_retailer_lockup docstring must name the cr-1 carve-out"


def test_unknown_retailer_raises_cleanly(tmp_path):
    base = _make_base(tmp_path / "hero.png")
    try:
        lockup.compose_retailer_lockup(base, "walmart", logo_dir=tmp_path)
    except ValueError as e:
        assert "unknown retailer" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown retailer")


def test_unknown_position_raises(tmp_path):
    base = _make_base(tmp_path / "hero.png")
    try:
        lockup.compose_retailer_lockup(base, "costco", position="left", logo_dir=tmp_path)
    except ValueError as e:
        assert "unknown position" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown position")


def test_missing_base_image_raises(tmp_path):
    try:
        lockup.compose_retailer_lockup(tmp_path / "nope.png", "costco", logo_dir=tmp_path)
    except FileNotFoundError:
        pass
    else:
        raise AssertionError("expected FileNotFoundError for missing base image")


def test_png_fallback_used_when_only_png_present(tmp_path):
    base = _make_base(tmp_path / "hero.png")
    # a real readable PNG logo present, no SVG -> png source path
    Image.new("RGBA", (200, 80), (255, 0, 0, 255)).save(tmp_path / "target.png", "PNG")
    result = lockup.compose_retailer_lockup(base, "target", logo_dir=tmp_path)
    assert result["logo_source"] == "png"
    assert result["out_path"].exists()


def test_cli_lockup_subcommand(tmp_path):
    base = _make_base(tmp_path / "hero.png")
    out = tmp_path / "lockup.png"
    rc = cli.main([
        "lockup", "--src", str(base), "--retailer", "costco",
        "--store-address", "Costco — 450 10th St, San Francisco, CA 94103",
        "--out", str(out),
    ])
    assert rc == 0
    assert out.exists()
