"""DAM fetch cache must write to a writable /tmp root, never read-only input_assets.

Root-cause repair for the Lambda /generate 503: _s3_try_fetch_product_asset cached
fetched S3 assets under the RELATIVE input_assets root, which resolves under the
read-only /var/task on Lambda. dest.parent.mkdir then raised Errno 30 for every
candidate key, the ~16-candidate retry loop ran ~37s, and API Gateway's 30s timeout
returned 503. See dam.py::_dam_cache_root / _s3_download.

These tests monkeypatch the S3 primitives (no real AWS) and simulate a read-only
input_assets to prove: (1) the fetch write lands under the /tmp cache root, (2) a
read-only input_assets no longer breaks the fetch, (3) local reads from input_assets
still resolve via the find_hero_asset glob, (4) the mkdir guard degrades gracefully.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from creative_automation import dam


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 64), (200, 120, 40)).save(path, "PNG")


# --------------------------------------------------------------- cache-root resolver
def test_dam_cache_root_defaults_to_tmp(monkeypatch) -> None:
    """No override -> /tmp/kodiak-assets, never the relative read-only input_assets."""
    monkeypatch.delenv("DAM_CACHE_ROOT", raising=False)
    root = dam._dam_cache_root()
    assert str(root).startswith("/tmp/"), f"cache root not under /tmp: {root}"
    assert root != Path("input_assets")


def test_dam_cache_root_honors_env_override(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DAM_CACHE_ROOT", str(tmp_path / "custom-cache"))
    assert dam._dam_cache_root() == tmp_path / "custom-cache"


# -------------------------------------------- fetch writes to /tmp cache, not dam_root
def test_fetch_product_asset_writes_under_tmp_cache_not_dam_root(monkeypatch, tmp_path: Path) -> None:
    """The S3 download lands under _dam_cache_root(), not the caller's dam_root."""
    cache = tmp_path / "tmp-cache"
    monkeypatch.setattr(dam, "_dam_cache_root", lambda: cache)
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")

    def fake_download(bucket: str, key: str, dest: Path) -> bool:
        # mirror the real _s3_download mkdir so we prove the dest parent is writable
        dest.parent.mkdir(parents=True, exist_ok=True)
        if key.endswith("hero.png"):
            _write_png(dest)
            return True
        return False

    monkeypatch.setattr(dam, "_s3_download", fake_download)

    dam_root = tmp_path / "input_assets"  # caller's read root (would be read-only on Lambda)
    hit = dam._s3_try_fetch_product_asset("power-cakes", dam_root)
    assert hit is not None and hit.exists()
    # the write landed under the /tmp cache root, NOT under dam_root
    assert str(hit).startswith(str(cache)), f"fetch wrote outside cache root: {hit}"
    assert dam_root not in hit.parents, "fetch wrote into the read-only dam_root"


def test_fetch_survives_readonly_input_assets(monkeypatch, tmp_path: Path) -> None:
    """Simulated read-only input_assets: the fetch still succeeds via the /tmp cache."""
    cache = tmp_path / "tmp-cache"
    readonly_root = tmp_path / "input_assets"
    readonly_root.mkdir()
    readonly_root.chmod(0o555)  # read + execute, no write — the Lambda /var/task shape
    monkeypatch.setattr(dam, "_dam_cache_root", lambda: cache)
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")

    def fake_download(bucket: str, key: str, dest: Path) -> bool:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if key.endswith("hero.png"):
            _write_png(dest)
            return True
        return False

    monkeypatch.setattr(dam, "_s3_download", fake_download)
    try:
        hit = dam._s3_try_fetch_product_asset("power-cakes", readonly_root)
        assert hit is not None and hit.exists(), "fetch broke on read-only input_assets"
        assert str(hit).startswith(str(cache))
    finally:
        readonly_root.chmod(0o755)  # restore so tmp_path cleanup can remove it


def test_s3_download_mkdir_guard_degrades_gracefully(monkeypatch, tmp_path: Path) -> None:
    """A read-only dest parent makes _s3_download return False, not raise Errno 30."""
    readonly = tmp_path / "ro"
    readonly.mkdir()
    readonly.chmod(0o555)
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setattr(dam, "_s3_client", lambda: object())  # non-None so we reach mkdir
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")
    try:
        # dest under the read-only dir -> mkdir raises OSError internally -> False, no raise
        ok = dam._s3_download("test-dam-bucket", "dam/x/hero.png", readonly / "x" / "hero.png")
        assert ok is False
    finally:
        readonly.chmod(0o755)


# -------------------------------------------------- local reads from input_assets work
def test_local_read_from_input_assets_still_resolves(monkeypatch, tmp_path: Path) -> None:
    """find_hero_asset glob still reads a committed local asset under dam_root."""
    monkeypatch.setattr(dam, "_s3_enabled", lambda: False)  # S3 off -> pure local path
    dam_root = tmp_path / "input_assets"
    local_hero = dam_root / "power-cakes" / "hero.png"
    _write_png(local_hero)
    hit = dam.find_hero_asset("power-cakes", dam_root)
    assert hit == local_hero, f"local read did not resolve committed asset: {hit}"


def test_presynced_local_hit_preferred_over_download(monkeypatch, tmp_path: Path) -> None:
    """A pre-synced asset under dam_root is returned; its key is never downloaded."""
    cache = tmp_path / "tmp-cache"
    monkeypatch.setattr(dam, "_dam_cache_root", lambda: cache)
    monkeypatch.setattr(dam, "_s3_enabled", lambda: True)
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")
    dam_root = tmp_path / "input_assets"
    presynced = dam_root / "power-cakes" / "hero.png"
    _write_png(presynced)

    downloads: list[str] = []
    monkeypatch.setattr(dam, "_s3_download", lambda b, k, d: downloads.append(k) or False)

    hit = dam._s3_try_fetch_product_asset("power-cakes", dam_root)
    # the pre-synced local copy is returned (read from dam_root, no cache write for it)
    assert hit == presynced
    # and the hero.png key itself was never downloaded — the local copy short-circuited it
    assert not any(k.endswith("hero.png") for k in downloads), (
        f"downloaded hero.png despite a pre-synced local hit: {downloads}"
    )
