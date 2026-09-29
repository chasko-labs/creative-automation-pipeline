"""POST /assets/pack put-path regression (#285) — no real AWS.

Root cause pinned: the generate lambda role granted brands/kodiak/renders/*
but _handle_pack PUTs the finished zip to brands/kodiak/packs/*, so the live
put failed AccessDenied and the endpoint 500'd ("pack upload failed"). These
tests drive _handle_pack with a stub S3 client: the happy path proves the zip
lands under the packs/ prefix with a presigned URL, and the denied-put path
proves the fault surfaces as a 500 (never a crash) — the signal that sent us
to the IAM grant.
"""
from __future__ import annotations

import io as _io
import json
import zipfile

from creative_automation import generate_lambda


class _CannedS3Error(Exception):
    """Module-local stub error so canned stand-ins never raise vanilla Exception (TRY002)."""


class _CannedS3:
    def __init__(self, objects=None, deny_put=False):
        self.objects = objects or {}
        self.deny_put = deny_put
        self.puts = []

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise _CannedS3Error(f"NoSuchKey: {Key}")
        return {"Body": _io.BytesIO(self.objects[Key])}

    def put_object(self, **kwargs):
        if self.deny_put:
            raise _CannedS3Error("AccessDenied: not authorized for brands/kodiak/packs/*")
        self.puts.append(kwargs)
        return {}

    def generate_presigned_url(self, op, Params, ExpiresIn):
        return f"https://asset_store.example/{Params['Key']}?presigned=1"


def _pack_event(files, extras=None):
    return {
        "rawPath": "/assets/pack",
        "requestContext": {"http": {"method": "POST", "path": "/assets/pack"}},
        "body": json.dumps({"files": files, "extras": extras or []}),
    }


def test_handle_pack_puts_zip_under_packs_prefix(monkeypatch):
    key = "brands/kodiak/renders/abc123.png"
    canned = _CannedS3(objects={key: b"\x89PNG\r\n\x1a\ncanned"})
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: canned)
    resp = generate_lambda.handler(
        _pack_event([{"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/{key}", "ratio": "1x1"}],
                    extras=[{"name": "copy.txt", "text": "headline"}]),
        None,
    )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert body["ok"] is True
    assert body["zip_url"].startswith("https://asset_store.example/")
    assert len(canned.puts) == 1
    put = canned.puts[0]
    assert put["Key"].startswith("brands/kodiak/packs/")
    assert put["Key"].endswith(".zip")
    assert put["ContentType"] == "application/zip"
    zf = zipfile.ZipFile(_io.BytesIO(put["Body"]))
    names = zf.namelist()
    assert any(n.endswith(("-1X1-", ".png")) or "-1x1-" in n.lower() for n in names)
    assert any(n.endswith("copy.txt") for n in names)


def test_handle_pack_put_denied_surfaces_500(monkeypatch):
    # the live #285 fault: role lacks packs/* so the put raises AccessDenied.
    key = "brands/kodiak/renders/abc123.png"
    canned = _CannedS3(objects={key: b"\x89PNG\r\n\x1a\ncanned"}, deny_put=True)
    monkeypatch.setattr(generate_lambda.boto3, "client", lambda *a, **k: canned)
    resp = generate_lambda.handler(
        _pack_event([{"s3_uri": f"s3://{generate_lambda.ASSET_STORE_S3_BUCKET}/{key}"}]),
        None,
    )
    assert resp["statusCode"] == 500
    assert json.loads(resp["body"])["error"] == "pack upload failed"
