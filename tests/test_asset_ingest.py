"""ingest_asset / embed_and_store — embed-on-ingest wiring, OFFLINE + cred-free.

add_asset stays authoritative for classify/dedup/persist; ingest adds a best-effort embed to
S3 Vectors after the object + sidecar are committed. Every case here injects a FakeS3 (same stub
shape as test_asset_library.py) and monkeypatches the embeddings module, so no Bedrock and no
S3 Vectors are ever touched. The invariant under test: an embed failure NEVER loses the asset and
NEVER raises — it degrades to embed_status="embed_pending".
"""
from __future__ import annotations

import io

from creative_automation import asset_ingest as ingest
from creative_automation.asset_library import AssetKind, AssetLibrary
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


class RecordingEmbed:
    """Records embed_image / vector_exists / put_vector calls; scriptable outcomes.

    Substituted for the embeddings module attributes ingest calls by name, so the ingest path is
    exercised with no AWS. put_ok drives the put_vector return; exists drives the dedup gate;
    raise_on_embed forces embed_image to blow up (the exception-degrade path).
    """

    def __init__(self, *, put_ok: bool = True, exists: bool = False, raise_on_embed: bool = False):
        self.put_ok = put_ok
        self.exists = exists
        self.raise_on_embed = raise_on_embed
        self.embed_calls: list[str] = []
        self.exists_calls: list[str] = []
        self.put_calls: list[tuple[str, dict]] = []

    def embed_image(self, image_path, text_hint=None, dim=1024):
        self.embed_calls.append(str(image_path))
        if self.raise_on_embed:
            raise RuntimeError("bedrock exploded")
        return [0.1, 0.2, 0.3], "mock:nova-image"

    def vector_exists(self, key, *, bucket=None, index=None):
        self.exists_calls.append(key)
        return self.exists

    def put_vector(self, vector, key, metadata=None, *, bucket=None, index=None):
        self.put_calls.append((key, metadata or {}))
        return self.put_ok


def _lib() -> tuple[AssetLibrary, FakeS3]:
    fake = FakeS3()
    obs = Observer("test", xray_enabled=False)
    return AssetLibrary(bucket="test-bucket", s3_client=fake, obs=obs), fake


def _patch_embed(monkeypatch, rec: RecordingEmbed) -> None:
    monkeypatch.setattr(ingest.embeddings, "embed_image", rec.embed_image)
    monkeypatch.setattr(ingest.embeddings, "vector_exists", rec.vector_exists)
    monkeypatch.setattr(ingest.embeddings, "put_vector", rec.put_vector)


def test_ingest_raster_calls_put_vector_with_key_equals_asset_id(monkeypatch):
    lib, fake = _lib()
    rec = RecordingEmbed(put_ok=True, exists=False)
    _patch_embed(monkeypatch, rec)

    ref, status = ingest.ingest_asset(lib, data=b"png-bytes", filename="hero.png")

    assert ref.kind == AssetKind.RASTER
    assert status == ingest.EMBED_EMBEDDED
    # exactly one put_vector, keyed by the asset id, with the expected metadata
    assert len(rec.put_calls) == 1
    key, meta = rec.put_calls[0]
    assert key == ref.asset_id
    assert meta["asset_id"] == ref.asset_id
    assert meta["filename"] == "hero.png"
    assert meta["kind"] == "raster"
    assert meta["sha256"] == ref.sha256
    # the asset itself is persisted (object + sidecar)
    assert ref.s3_key in fake.store
    assert f"brands/kodiak/library/{ref.asset_id}/asset.json" in fake.store


def test_ingest_vector_exists_skips_put_vector(monkeypatch):
    lib, _ = _lib()
    rec = RecordingEmbed(put_ok=True, exists=True)  # dedup gate: vector already present
    _patch_embed(monkeypatch, rec)

    ref, status = ingest.ingest_asset(lib, data=b"svg-bytes", filename="logo.svg")

    assert status == ingest.EMBED_SKIPPED_DEDUP
    assert rec.exists_calls == [ref.asset_id]
    assert rec.put_calls == []  # skipped — no re-embed of a known key
    assert rec.embed_calls == []  # short-circuits before embed_image too


def test_ingest_put_vector_false_degrades_to_embed_pending(monkeypatch):
    lib, fake = _lib()
    rec = RecordingEmbed(put_ok=False, exists=False)  # write to S3 Vectors fails
    _patch_embed(monkeypatch, rec)

    ref, status = ingest.ingest_asset(lib, data=b"png-bytes", filename="hero.png")

    assert status == ingest.EMBED_PENDING
    # asset still fully persisted despite the embed miss
    assert ref.s3_key in fake.store
    assert f"brands/kodiak/library/{ref.asset_id}/asset.json" in fake.store


def test_ingest_embed_raise_degrades_to_embed_pending_no_exception(monkeypatch):
    lib, fake = _lib()
    rec = RecordingEmbed(raise_on_embed=True, exists=False)  # embed_image raises
    _patch_embed(monkeypatch, rec)

    # must not raise
    ref, status = ingest.ingest_asset(lib, data=b"png-bytes", filename="hero.png")

    assert status == ingest.EMBED_PENDING
    assert rec.put_calls == []  # never reached put after the embed raise
    assert ref.s3_key in fake.store


def test_ingest_sha256_dedup_returns_existing_ref_no_second_embed(monkeypatch):
    lib, _ = _lib()
    rec = RecordingEmbed(put_ok=True, exists=False)
    _patch_embed(monkeypatch, rec)

    first_ref, first_status = ingest.ingest_asset(lib, data=b"same-bytes", filename="a.png")
    assert first_status == ingest.EMBED_EMBEDDED
    assert len(rec.put_calls) == 1

    # exact sha256 duplicate — add_asset returns the existing ref. The second ingest now finds the
    # vector present (simulate: flip the exists gate) so it must NOT embed a second time.
    rec.exists = True
    second_ref, second_status = ingest.ingest_asset(lib, data=b"same-bytes", filename="a-again.png")

    assert second_ref.asset_id == first_ref.asset_id
    assert second_status == ingest.EMBED_SKIPPED_DEDUP
    assert len(rec.put_calls) == 1  # still only the first put — no second embed


def test_ingest_doc_kind_not_embeddable(monkeypatch):
    lib, _ = _lib()
    rec = RecordingEmbed()
    _patch_embed(monkeypatch, rec)

    ref, status = ingest.ingest_asset(lib, data=b"pdf-bytes", filename="guide.pdf")

    assert ref.kind == AssetKind.DOC
    assert status == ingest.EMBED_NOT_EMBEDDABLE
    assert rec.embed_calls == []
    assert rec.put_calls == []


def test_ingest_embed_disabled_skips_embed(monkeypatch):
    lib, _ = _lib()
    rec = RecordingEmbed()
    _patch_embed(monkeypatch, rec)

    ref, status = ingest.ingest_asset(lib, data=b"png-bytes", filename="hero.png", embed=False)

    assert status == ingest.EMBED_DISABLED
    assert rec.put_calls == []
    assert rec.embed_calls == []
