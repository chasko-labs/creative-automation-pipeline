"""Spin toolkit tests — OFFLINE Pillow fallbacks only.

Must pass without AWS creds and without KODIAK_BEDROCK_EDIT set. Each test builds a
synthetic image (a subject blob on a flat background) so the deterministic fallbacks
have something to matte / crop / grade.
"""
from pathlib import Path

from PIL import Image

from creative_automation import cli, retailers, spin


def _make_subject(path: Path, size=(400, 300), bg=(220, 220, 220)) -> Path:
    """Flat background with an off-center colored subject rectangle."""
    img = Image.new("RGB", size, bg)
    for y in range(80, 220):
        for x in range(120, 300):
            img.putpixel((x, y), (200, 60, 30))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")
    return path


# ------------------------------------------------------------------ background
def test_remove_background_transparent_produces_alpha(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    out = spin.remove_background(src, "transparent", out=tmp_path / "freed.png")
    assert out.exists()
    img = Image.open(out)
    assert img.mode == "RGBA"
    alpha = img.getchannel("A")
    lo, hi = alpha.getextrema()
    # flat border should matte toward transparent, subject stays opaque
    assert lo == 0, "background did not matte to transparent"
    assert hi == 255, "subject alpha lost"


def test_remove_background_solid_fill_is_opaque_kodiak_color(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    out = spin.remove_background(src, "solid", fill="bear-brown", out=tmp_path / "solid.png")
    img = Image.open(out).convert("RGBA")
    # fully opaque everywhere (subject over solid plate)
    assert img.getchannel("A").getextrema() == (255, 255)
    # a corner pixel should be bear-brown (#3B2316)
    assert img.convert("RGB").getpixel((0, 0)) == (59, 35, 22)


def test_remove_background_image_plate(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    plate = tmp_path / "plate.png"
    Image.new("RGB", (400, 300), (10, 60, 52)).save(plate, "PNG")
    out = spin.remove_background(src, "image", bg_image=plate, out=tmp_path / "onplate.png")
    img = Image.open(out).convert("RGBA")
    assert img.getchannel("A").getextrema() == (255, 255)


# ------------------------------------------------------------------ batch crop
def test_batch_crop_produces_correct_dims_per_ratio(tmp_path):
    srcs = [_make_subject(tmp_path / f"a{i}.png") for i in range(3)]
    out_dir = tmp_path / "cropped"
    written = spin.batch_crop([str(s) for s in srcs], ["1x1", "9x16", "16x9"], out_dir)
    assert len(written) == 9  # 3 files x 3 ratios
    expected = {"1x1": (1080, 1080), "9x16": (1080, 1920), "16x9": (1920, 1080)}
    for w in written:
        ratio = w.stem.split(".")[-1]
        assert Image.open(w).size == expected[ratio], f"{w} wrong dims"


def test_batch_crop_accepts_directory(tmp_path):
    src_dir = tmp_path / "assets"
    for i in range(2):
        _make_subject(src_dir / f"img{i}.png")
    written = spin.batch_crop(src_dir, ["1x1"], tmp_path / "out")
    assert len(written) == 2
    assert all(Image.open(w).size == (1080, 1080) for w in written)


# ------------------------------------------------------------------ color grade
def test_color_grade_default_applies_texture_and_changes_pixels(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    before = Image.open(src).convert("RGB")
    out = spin.color_grade(src, out=tmp_path / "graded.png")
    after = Image.open(out).convert("RGB")
    assert after.size == before.size
    # grade must alter the image (texture + warm tone)
    assert after.tobytes() != before.tobytes()


def test_color_grade_named_presets_all_resolve(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    for preset in spin.COLOR_GRADE_PRESETS:
        out = spin.color_grade(src, preset, out=tmp_path / f"{preset}.png")
        assert out.exists()


def test_color_grade_unknown_preset_raises(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    try:
        spin.color_grade(src, "not-a-preset", out=tmp_path / "x.png")
    except ValueError as e:
        assert "unknown preset" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown preset")


# ------------------------------------------------------------------ chain
def test_spin_asset_chains_free_crop_grade(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    out = spin.spin_asset(src, ratio="1x1", bg_mode="solid", fill="parchment", out_dir=tmp_path / "spin")
    assert out.exists()
    assert Image.open(out).size == (1080, 1080)


# ------------------------------------------------------------------ retailers
def test_resolve_retailer_reports_missing_svg(tmp_path):
    r = retailers.resolve_retailer("Costco", store_address="123 Main", logo_dir=tmp_path)
    assert r.name == "costco"
    assert r.missing is True
    assert r.svg_exists is False
    assert r.store_address == "123 Main"
    assert any("missing preferred SVG" in n for n in r.notes)


def test_resolve_retailer_prefers_svg_over_png(tmp_path):
    (tmp_path / "publix.svg").write_text("<svg/>", encoding="utf-8")
    (tmp_path / "publix.png").write_bytes(b"\x89PNG")
    r = retailers.resolve_retailer("publix", logo_dir=tmp_path)
    assert r.asset_path == tmp_path / "publix.svg"
    assert r.missing is False


def test_resolve_retailer_unknown_raises():
    try:
        retailers.resolve_retailer("walmart")
    except ValueError as e:
        assert "unknown retailer" in str(e)
    else:
        raise AssertionError("expected ValueError for unknown retailer")


def test_missing_logos_lists_all_when_dir_empty(tmp_path):
    assert set(retailers.missing_logos(logo_dir=tmp_path)) == {"costco", "publix", "target"}


# ------------------------------------------------------------------ CLI
def test_cli_spin_crop_subcommand(tmp_path):
    src = _make_subject(tmp_path / "hero.png")
    out = tmp_path / "cliout"
    rc = cli.main(["spin", "--src", str(src), "--op", "crop", "--ratios", "1x1", "--out", str(out)])
    assert rc == 0
    assert (out / "hero.1x1.png").exists()


def test_cli_spin_bedrock_gate_off_by_default(monkeypatch):
    monkeypatch.delenv("KODIAK_BEDROCK_EDIT", raising=False)
    assert spin._bedrock_edit_enabled() is False
