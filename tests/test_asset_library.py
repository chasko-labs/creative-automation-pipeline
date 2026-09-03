"""AssetLibrary tests — fake in-memory S3, add/dedup/list/select, offline degrade. No AWS."""
from __future__ import annotations

import io

import pytest

from creative_automation import asset_library
from creative_automation.asset_library import (
    AssetKind,
    AssetLibrary,
    AssetNotSelectable,
    UnsupportedAssetKind,
    classify,
)
from creative_automation.observability import Observer


class FakeS3:
    """In-memory S3 stub: key -> bytes, supporting put/get/list_objects_v2 with Delimiter."""

    def __init__(self) -> None:
        self.store: dict[str, bytes] = {}

    def put_object(self, *, Bucket: str, Key: str, Body: bytes, ContentType: str = "") -> dict:
        self.store[Key] = Body if isinstance(Body, bytes) else bytes(Body)
        return {}

    def get_object(self, *, Bucket: str, Key: str) -> dict:
        if Key not in self.store:
            raise KeyError(Key)
        return {"Body": io.BytesIO(self.store[Key])}

    def list_objects_v2(
        self,
        *,
        Bucket: str,
        Prefix: str = "",
        Delimiter: str | None = None,
        MaxKeys: int = 1000,
        ContinuationToken: str | None = None,
    ) -> dict:
        keys = sorted(k for k in self.store if k.startswith(Prefix))
        if Delimiter:
            prefixes: list[str] = []
            seen: set[str] = set()
            for k in keys:
                rest = k[len(Prefix):]
                head = rest.split(Delimiter, 1)[0]
                cp = f"{Prefix}{head}{Delimiter}"
                if cp not in seen:
                    seen.add(cp)
                    prefixes.append(cp)
            return {"CommonPrefixes": [{"Prefix": p} for p in prefixes], "IsTruncated": False}
        return {"Contents": [{"Key": k} for k in keys], "IsTruncated": False}


def _lib() -> tuple[AssetLibrary, FakeS3]:
    fake = FakeS3()
    obs = Observer("test", xray_enabled=False)
    return AssetLibrary(bucket="test-bucket", s3_client=fake, obs=obs), fake


def test_classify_maps_each_extension() -> None:
    assert classify("a.png") == AssetKind.RASTER
    assert classify("a.jpg") == AssetKind.RASTER
    assert classify("a.jpeg") == AssetKind.RASTER
    assert classify("a.webp") == AssetKind.RASTER
    assert classify("a.svg") == AssetKind.VECTOR
    assert classify("a.pdf") == AssetKind.DOC
    assert classify("a.txt") == AssetKind.COPY
    assert classify("a.md") == AssetKind.COPY


def test_add_asset_stores_object_and_sidecar() -> None:
    lib, fake = _lib()
    ref = lib.add_asset(data=b"hello", filename="brief.md", tags=["Brand Voice", "kodiak"])
    assert ref.kind == AssetKind.COPY
    assert ref.s3_key == f"brands/kodiak/library/{ref.asset_id}/brief.md"
    assert ref.sha256 == __import__("hashlib").sha256(b"hello").hexdigest()
    assert ref.tags == ["brand-voice", "kodiak"]
    # object + sidecar both written
    assert ref.s3_key in fake.store
    assert f"brands/kodiak/library/{ref.asset_id}/asset.json" in fake.store


def test_add_asset_dedup_returns_same_id() -> None:
    lib, fake = _lib()
    first = lib.add_asset(data=b"same-bytes", filename="a.png")
    dirs_after_first = {k.split("/")[3] for k in fake.store if k.startswith("brands/kodiak/library/")}
    second = lib.add_asset(data=b"same-bytes", filename="a-again.png")
    dirs_after_second = {k.split("/")[3] for k in fake.store if k.startswith("brands/kodiak/library/")}
    assert first.asset_id == second.asset_id
    assert dirs_after_first == dirs_after_second  # no new object dir


def test_add_unsupported_kind_raises_and_logs_reject() -> None:
    lib, _ = _lib()
    with pytest.raises(UnsupportedAssetKind):
        lib.add_asset(data=b"x", filename="malware.exe")
    assert lib.obs.counts().get("asset.reject") == 1


def test_list_assets_filters_by_kind() -> None:
    lib, _ = _lib()
    lib.add_asset(data=b"png-bytes", filename="hero.png")
    lib.add_asset(data=b"doc-bytes", filename="guide.pdf")
    all_page = lib.list_assets()
    assert len(all_page.items) == 2
    raster_page = lib.list_assets(kind=AssetKind.RASTER)
    assert len(raster_page.items) == 1
    assert raster_page.items[0].kind == AssetKind.RASTER


def test_select_for_campaign_raster_ok_doc_and_missing_rejected() -> None:
    lib, _ = _lib()
    raster = lib.add_asset(data=b"png-bytes", filename="hero.png")
    vector = lib.add_asset(data=b"svg-bytes", filename="logo.svg")
    doc = lib.add_asset(data=b"pdf-bytes", filename="guide.pdf")

    assert lib.select_for_campaign(raster.asset_id).asset_id == raster.asset_id
    assert lib.select_for_campaign(vector.asset_id).asset_id == vector.asset_id
    with pytest.raises(AssetNotSelectable):
        lib.select_for_campaign(doc.asset_id)
    with pytest.raises(AssetNotSelectable):
        lib.select_for_campaign("does-not-exist")


def test_get_asset_roundtrip() -> None:
    lib, _ = _lib()
    ref = lib.add_asset(data=b"copy", filename="voice.txt")
    fetched = lib.get_asset(ref.asset_id)
    assert fetched is not None
    assert fetched.asset_id == ref.asset_id
    assert fetched.sha256 == ref.sha256


def test_offline_degrade_no_s3(monkeypatch: pytest.MonkeyPatch) -> None:
    # simulate boto3 absence: _build_s3_client returns None -> no-s3 degraded mode
    monkeypatch.setattr(asset_library, "HAS_BOTO3", False)
    obs = Observer("test", xray_enabled=False)
    lib = AssetLibrary(bucket="test-bucket", s3_client=None, obs=obs)
    assert lib.s3_enabled is False
    # classify still works
    assert classify("a.png") == AssetKind.RASTER
    # list degrades to empty
    page = lib.list_assets()
    assert page.items == []
    assert page.next_cursor is None
    # writes raise a clear RuntimeError
    with pytest.raises(RuntimeError):
        lib.add_asset(data=b"x", filename="a.png")


def test_health_reports_counts() -> None:
    lib, _ = _lib()
    lib.add_asset(data=b"png-bytes", filename="hero.png")
    health = lib.health()
    assert health["ok"] is True
    assert health["bucket"] == "test-bucket"
    assert health["s3_enabled"] is True
    assert health["count"] == 1
