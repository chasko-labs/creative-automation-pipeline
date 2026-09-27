"""Preview-attempt ledger: every completed preview persists one small JSON record.

The reviewable answer to "what did we run and what did it produce" — browsable
in the asset store instead of living only in logs. The write is best-effort by
contract: it must never fail a preview.
"""
from __future__ import annotations

import json

from creative_automation import asset_store


class _FakeS3:
    def __init__(self) -> None:
        self.puts: list[dict] = []

    def put_object(self, Bucket: str, Key: str, Body: bytes, ContentType: str) -> dict:
        self.puts.append({"Bucket": Bucket, "Key": Key, "Body": Body, "ContentType": ContentType})
        return {}


class _BoomS3:
    def put_object(self, **kwargs) -> dict:
        raise RuntimeError("s3 down")


def _online(monkeypatch, client) -> None:
    monkeypatch.setattr(asset_store, "_s3_enabled", lambda: True)
    monkeypatch.setattr(asset_store, "_s3_bucket_and_prefix", lambda: ("dam-bucket", "brands/kodiak/"))
    monkeypatch.setattr(asset_store, "_s3_client", lambda: client)


def test_record_writes_one_json_object(monkeypatch) -> None:
    fake = _FakeS3()
    _online(monkeypatch, fake)
    uri = asset_store.record_preview_attempt({"brief": "nyc muffins", "market": "US-NE-MANHATTAN"})
    assert uri is not None and uri.startswith("s3://dam-bucket/brands/kodiak/preview-attempts/")
    assert len(fake.puts) == 1
    put = fake.puts[0]
    assert put["ContentType"] == "application/json"
    body = json.loads(put["Body"].decode())
    assert body["brief"] == "nyc muffins"
    assert body["market"] == "US-NE-MANHATTAN"
    assert body["recorded_at"]


def test_record_never_raises(monkeypatch) -> None:
    _online(monkeypatch, _BoomS3())
    assert asset_store.record_preview_attempt({"brief": "x"}) is None


def test_record_skipped_when_store_offline(monkeypatch) -> None:
    monkeypatch.setattr(asset_store, "_s3_enabled", lambda: False)
    assert asset_store.record_preview_attempt({"brief": "x"}) is None
