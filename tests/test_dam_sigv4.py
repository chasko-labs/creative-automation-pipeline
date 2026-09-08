"""SigV4 gate (#189): DAM S3 client must force signature_version=s3v4.

KMS-SSE buckets reject SigV2 presigns with 400 InvalidArgument; dam.presign_get
URLs must be SigV4 (X-Amz-Algorithm). Asserts the client Config carries s3v4.
"""
from __future__ import annotations

from creative_automation import dam


def test_s3_client_forces_sigv4(monkeypatch) -> None:
    monkeypatch.setenv("DAM_S3_BUCKET", "test-dam-bucket")
    captured: dict = {}

    class _FakeConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(dam, "_BotoConfig", _FakeConfig)

    def _fake_client(service, region_name=None, config=None):
        assert service == "s3"
        return ("ok", region_name, config)

    monkeypatch.setattr(dam.boto3, "client", _fake_client)
    result = dam._s3_client()
    assert result[0] == "ok"
    assert captured.get("signature_version") == "s3v4", (
        f"dam._s3_client Config must set signature_version='s3v4', got {captured!r}"
    )


def test_presign_get_uses_sigv4_client(monkeypatch) -> None:
    """presign_get must route through the SigV4 _s3_client (no bespoke client)."""
    import inspect

    src = inspect.getsource(dam.presign_get)
    assert "_s3_client()" in src, "presign_get must use the shared SigV4 _s3_client()"
    assert 'boto3.client("s3"' not in src, "presign_get must not build its own unsigned client"
