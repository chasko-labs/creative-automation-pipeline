"""asset store fetch must use bounded get_object + body.read(), never download_file.

Outer-wall prerequisite (#118): boto3 client.download_file() drives the S3 Transfer
manager with its OWN thread pool, so the botocore read_timeout (which bounds a single
socket read) does NOT bound the overall transfer — a stalled warm connection hangs ~33s
and an abandoned worker leaks a whole Transfer pool. get_object is one bounded HTTP GET
whose body.read() is drained inline, so an abandoned thread is a single safe socket read.
That single-socket property is what makes the handler-level outer wall's leaked-thread
abandonment safe, so this behavior is asserted directly.
"""
from __future__ import annotations

from pathlib import Path

from creative_automation import asset_store


class _FakeBody:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def read(self) -> bytes:
        return self._data


class _FakeS3Client:
    """Records which transfer API is used and serves canned bytes via get_object."""

    def __init__(self) -> None:
        self.get_object_calls: list[dict] = []
        self.download_file_calls: list[tuple] = []

    def get_object(self, Bucket: str, Key: str) -> dict:
        self.get_object_calls.append({"Bucket": Bucket, "Key": Key})
        return {"Body": _FakeBody(b"\x89PNG\r\n\x1a\n-fake-bytes")}

    def download_file(self, bucket, key, dest) -> None:  # pragma: no cover — must not run
        self.download_file_calls.append((bucket, key, dest))
        raise AssertionError("download_file must not be used — Transfer manager reintroduces the hang")


def test_s3_download_uses_get_object_writes_dest(monkeypatch, tmp_path: Path) -> None:
    fake = _FakeS3Client()
    monkeypatch.setattr(asset_store, "_s3_client", lambda: fake)

    dest = tmp_path / "power-cakes" / "hero.png"
    ok = asset_store._s3_download("test-asset_store-bucket", "brands/kodiak/heroes/power-cakes/hero.png", dest)

    assert ok is True
    # get_object was the transfer API — download_file (Transfer manager) never touched
    assert len(fake.get_object_calls) == 1
    assert fake.get_object_calls[0]["Key"].endswith("hero.png")
    assert fake.download_file_calls == []
    # write-to-dest contract preserved: the read bytes landed on disk
    assert dest.exists()
    assert dest.read_bytes() == b"\x89PNG\r\n\x1a\n-fake-bytes"


def test_asset_store_get_object_is_the_only_transfer_api(monkeypatch, tmp_path: Path) -> None:
    # behavioral regression gate: fetch_hero_to_tmp (a real fetch entry point) routes
    # through _s3_download, which must use get_object and never the download_file Transfer
    # manager. The fake client raises from download_file, so any regression fails loud.
    fake = _FakeS3Client()
    monkeypatch.setattr(asset_store, "_s3_client", lambda: fake)
    monkeypatch.setattr(asset_store, "_s3_enabled", lambda: True)
    monkeypatch.setenv("ASSET_STORE_S3_BUCKET", "test-asset_store-bucket")

    hit = asset_store.fetch_hero_to_tmp("power-cakes", cache_root=tmp_path / "cache")
    assert hit is not None and hit.exists()
    assert fake.get_object_calls, "fetch_hero_to_tmp did not use get_object"
    assert fake.download_file_calls == [], "fetch_hero_to_tmp used the download_file Transfer manager"
