"""S3 DAM fallback for hero source discovery — no real AWS.

The Lambda container ships with no assets baked in, so _find_source_asset must
pull the real hero from S3 (s3://<bucket>/brands/kodiak/heroes/<product>/
hero-real.png|hero.png) when the local filesystem misses. These tests monkeypatch
the dam S3 primitives (_s3_enabled / _s3_download) rather than hit S3, mirroring
the monkeypatch style in test_generate_lambda.py and test_asset_pack.py.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import dam, generate


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (200, 120, 40)).save(path, "PNG")


# --------------------------------------------------------------- fetch_hero_to_tmp
def test_fetch_hero_to_tmp_offline_returns_none(monkeypatch, tmp_path: Path) -> None:
    """S3 disabled (no DAM_S3_BUCKET / boto3) -> None, no raise, no download."""
    monkeypatch.setattr(dam, "_s3_enabled", lambda: False)
    called = {"n": 0}
    monkeypatch.setattr(dam, "_s3_download", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or True)
    assert dam.fetch_hero_to_tmp("power-cakes", cache_root=tmp_path) is None
    assert called["n"] == 0


def test_fetch_hero_to_tmp_prefers_hero_real(monkeypatch, tmp_path: Path) -> None:
    """hero-real.png is tried before hero.png and resolved to the /tmp cache path."""
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")
    requested: list[str] = []

    def fake_download(bucket: str, key: str, dest: Path) -> bool:
        requested.append(key)
        if key.endswith("hero-real.png"):
            _write_png(dest)
            return True
        return False

    monkeypatch.setattr(dam, "_s3_download", fake_download)
    hit = dam.fetch_hero_to_tmp("power-cakes", cache_root=tmp_path)
    assert hit is not None and hit.exists()
    assert hit == tmp_path / "power-cakes" / "hero-real.png"
    # the retouched real asset under the heroes prefix is attempted, and no hero.*
    # key is ever requested (hero-real wins before the loop advances to hero)
    assert "brands/kodiak/heroes/power-cakes/hero-real.png" in requested
    assert all("hero-real" in k for k in requested)


def test_fetch_hero_to_tmp_falls_back_to_hero(monkeypatch, tmp_path: Path) -> None:
    """No hero-real.* present -> hero.png is downloaded instead."""
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")

    def fake_download(bucket: str, key: str, dest: Path) -> bool:
        if key.endswith("hero.png"):
            _write_png(dest)
            return True
        return False

    monkeypatch.setattr(dam, "_s3_download", fake_download)
    hit = dam.fetch_hero_to_tmp("bear-bites", cache_root=tmp_path)
    assert hit is not None and hit.name == "hero.png"


def test_fetch_hero_to_tmp_miss_returns_none(monkeypatch, tmp_path: Path) -> None:
    """S3 enabled but product genuinely has no asset -> None (mock is last resort)."""
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")
    monkeypatch.setattr(dam, "_s3_download", lambda *a, **k: False)
    assert dam.fetch_hero_to_tmp("no-such-product", cache_root=tmp_path) is None


# --------------------------------------------------------------- _find_source_asset
def test_find_source_asset_local_miss_s3_hit(monkeypatch, tmp_path: Path) -> None:
    """Local disk misses but S3 has the asset -> _find_source_asset returns the /tmp path."""
    # run from an empty cwd so the local input_assets / data/raw-ingest checks miss
    monkeypatch.chdir(tmp_path)
    cached = tmp_path / "cache" / "power-cakes" / "hero-real.png"
    _write_png(cached)
    monkeypatch.setattr("creative_automation.dam.fetch_hero_to_tmp", lambda product_id: cached)

    got = generate._find_source_asset("power-cakes", "Power Cakes")
    assert got == cached


def test_find_source_asset_local_miss_s3_miss(monkeypatch, tmp_path: Path) -> None:
    """Both local and S3 miss -> None (caller degrades to mock)."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("creative_automation.dam.fetch_hero_to_tmp", lambda product_id: None)
    assert generate._find_source_asset("power-cakes", "Power Cakes") is None


def test_find_source_asset_s3_discovery_never_raises(monkeypatch, tmp_path: Path) -> None:
    """A boto3/S3 explosion inside discovery is swallowed -> None, not a raise."""
    monkeypatch.chdir(tmp_path)

    def boom(product_id: str) -> Path:
        raise RuntimeError("simulated boto3 failure")

    monkeypatch.setattr("creative_automation.dam.fetch_hero_to_tmp", boom)
    assert generate._find_source_asset("power-cakes", "Power Cakes") is None


# --------------------------------------------------------------- generate_hero source
def test_generate_hero_s3_asset_yields_nova_pro(monkeypatch, tmp_path: Path) -> None:
    """Local miss + S3 hit -> compose runs on the real asset -> source 'bedrock:nova-pro'.

    Nova Pro caption is stubbed to None (offline), which still composes on the real
    asset per generate_hero's contract, so the source is bedrock:nova-pro not mock.
    """
    monkeypatch.chdir(tmp_path)
    src = tmp_path / "cache" / "power-cakes" / "hero-real.png"
    _write_png(src)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, pname: src)
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "out.png"
    result, source = generate_hero_call(out)
    assert result.exists()
    assert source == "bedrock:nova-pro"


def test_generate_hero_no_asset_yields_fallback_label(monkeypatch, tmp_path: Path) -> None:
    """Requested product IS the default hero and both local + S3 miss -> true last
    resort. Never 'mock'/'preview' — the non-shaming fallback label reaches the UI.
    The default-hero retry is skipped because product_id == DEFAULT_HERO_PRODUCT.
    """
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    def track(pid, pname):
        calls.append(pid)
        return None

    monkeypatch.setattr(generate, "_find_source_asset", track)
    out = tmp_path / "out.png"
    result, source = generate_hero_call(out)
    assert result.exists()
    assert source == "bedrock:nova-pro-fallback"
    assert "mock" not in source and "preview" not in source
    # power-cakes IS the default hero, so discovery is attempted exactly once
    assert calls == ["power-cakes"]


def test_generate_hero_missing_product_composes_on_default_hero(monkeypatch, tmp_path: Path) -> None:
    """A NON-default SKU with no asset of its own but WITH the default brand hero
    available -> compose on power-cakes -> source 'bedrock:nova-pro', not a placeholder.
    """
    monkeypatch.chdir(tmp_path)
    default_src = tmp_path / "cache" / "power-cakes" / "hero-real.png"
    _write_png(default_src)

    def discover(pid, pname):
        # the requested SKU has nothing; only the default brand hero resolves
        return default_src if pid == generate.DEFAULT_HERO_PRODUCT else None

    monkeypatch.setattr(generate, "_find_source_asset", discover)
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)

    out = tmp_path / "out.png"
    result, source = generate.generate_hero(
        product_id="bear-bites-limited",
        product_name="Bear Bites Limited",
        brief_msg="frontier trail energy",
        region="us",
        audience="active families",
        out_path=out,
        idx=0,
    )
    assert result.exists()
    assert source == "bedrock:nova-pro"


def generate_hero_call(out_path: Path):
    """Thin wrapper to keep the two generate_hero tests DRY."""
    return generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="frontier trail energy",
        region="us",
        audience="active families",
        out_path=out_path,
        idx=0,
    )
