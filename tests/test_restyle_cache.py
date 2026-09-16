"""Restyle-cache wall arithmetic: a cached bg skips Bedrock; set bases never restyle fresh."""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from creative_automation import dam, generate


class _StubS3Error(Exception):
    """Module-local stub error so fakes never raise vanilla Exception (TRY002)."""


def _local_box(tmp_path: Path) -> Path:
    box = tmp_path / "box.png"
    box.write_bytes(_png_bytes((300, 400), color=(200, 30, 30)))
    return box


def _png_bytes(size=(1080, 1080), color=(180, 90, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def test_cache_key_deterministic_and_sensitive() -> None:
    a = generate._restyle_cache_key(b"seed", "p", "b", "r", "a", None)
    b = generate._restyle_cache_key(b"seed", "p", "b", "r", "a", None)
    c = generate._restyle_cache_key(b"seed", "p", "b2", "r", "a", None)
    assert a == b
    assert a != c
    assert a.startswith(generate._RESTYLE_CACHE_PREFIX) and a.endswith(".png")
    # IAM guard: the Lambda role only allows renders/* + library/* — the cache MUST live there.
    assert generate._RESTYLE_CACHE_PREFIX.startswith("brands/kodiak/renders/")


def test_cache_hit_skips_bedrock(tmp_path: Path, monkeypatch) -> None:
    # seed resolves, S3 serves a cached restyle -> no Bedrock calls at all,
    # provenance records the cache source. This is the full-mode wall fix.
    seed = tmp_path / "seed.png"
    seed.write_bytes(_png_bytes())
    cached_bytes = _png_bytes(color=(10, 20, 30))

    calls: list[str] = []

    class _S3:
        def download_file(self, bucket, key, dest):
            assert key.startswith(generate._RESTYLE_CACHE_PREFIX)
            Path(dest).write_bytes(cached_bytes)

        def put_object(self, **kwargs):
            calls.append("put")

    class _Boto:
        def client(self, name):
            assert name == "s3"
            return _S3()

    monkeypatch.setattr(generate, "boto3", _Boto())
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(dam, "resolve_packshot", lambda pid: _local_box(tmp_path))
    monkeypatch.setattr(
        generate, "_nova_pro_scene_prompt",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )
    monkeypatch.setattr(
        generate, "_stability_control_hero",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")),
    )

    out = tmp_path / "hero.png"
    _result, _source, prov = generate.generate_hero(
        product_id="banana-muffin-quick-bread-mix",
        product_name="Banana Muffin Mix",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        bare_base=True,  # set-base call: never restyles fresh even on a miss
    )
    assert prov["bg_restyle"] is True
    assert prov["bg_restyle_source"] == "cache"
    assert out.exists()


def test_set_base_miss_uses_raw_seed(tmp_path: Path, monkeypatch) -> None:
    # cache miss on a set base -> raw seed, NO fresh restyle (wall holds).
    seed = tmp_path / "seed.png"
    seed.write_bytes(_png_bytes())

    class _S3:
        def download_file(self, bucket, key, dest):
            raise _StubS3Error("NoSuchKey")

        def put_object(self, **kwargs):
            raise AssertionError("set base must not upload")

    class _Boto:
        def client(self, name):
            return _S3()

    monkeypatch.setattr(generate, "boto3", _Boto())
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_dam_photo", lambda pid: None)
    monkeypatch.setattr(dam, "resolve_packshot", lambda pid: _local_box(tmp_path))
    monkeypatch.setattr(
        generate, "_nova_pro_scene_prompt",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("set base must not restyle")),
    )
    monkeypatch.setattr(
        generate, "_stability_control_hero",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("set base must not restyle")),
    )

    out = tmp_path / "hero.png"
    _result, _source, prov = generate.generate_hero(
        product_id="banana-muffin-quick-bread-mix",
        product_name="Banana Muffin Mix",
        brief_msg="wild mornings",
        region="us",
        audience="active families",
        out_path=out,
        bare_base=True,
    )
    assert prov["bg_restyle"] is False
    assert out.exists()
