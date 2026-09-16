"""Retailer asset-pack builder + /assets/pack/{market} endpoint — OFFLINE, cred-free.

Every assertion runs with no S3 and no boto3 creds: dam.s3_upload_and_presign returns
None when DAM_S3_BUCKET is unset, so the endpoint takes its local-path fallback. The
zip/manifest/naming logic is pure stdlib and importable without FastAPI, mirroring how
the rest of the suite exercises the no-S3 / no-FastAPI graceful paths.
"""
import json
import zipfile
from pathlib import Path

import pytest

from creative_automation import dam
from creative_automation.asset_pack import (
    PACK_NAME_RE,
    build_asset_pack_zip,
    build_pack_name,
    market_language_tags,
    market_retailers,
)

try:
    from creative_automation.api import HAS_FASTAPI, app
except ImportError:  # pragma: no cover - import guard
    HAS_FASTAPI = False
    app = None


# --------------------------------------------------------------- pack naming
def test_build_pack_name_matches_regex_and_expected_format():
    name = build_pack_name("savory-waffles", "US-UT", "park-city-84098", date="20260903", version="v01")
    assert name == "KODIAK-CAKES-savory-waffles-US-UT-park-city-84098-retailers-pack-20260903-v01.zip"
    assert PACK_NAME_RE.match(name)


def test_build_pack_name_normalizes_loose_inputs():
    name = build_pack_name("Savory Waffles", "us-mw", "Park City / 84098", date="20260903", version=2)
    assert name == "KODIAK-CAKES-savory-waffles-US-MW-park-city-84098-retailers-pack-20260903-v02.zip"
    assert PACK_NAME_RE.match(name)


def test_build_pack_name_defaults_are_safe():
    # empty product/locality fall back rather than producing an invalid name
    name = build_pack_name("", "US", "", date="20260903")
    assert PACK_NAME_RE.match(name)


# --------------------------------------------------------------- language tags
def test_market_language_tags_leads_with_en_us_and_adds_top_langs():
    tags = market_language_tags("US-MW-PARKCITY-84098")
    assert tags[0] == "en-US"
    # Park City top_languages are es + pt per market-languages.json
    assert "es-US" in tags
    assert "pt-US" in tags


def test_market_language_tags_unknown_market_is_en_us_only():
    assert market_language_tags("US-XX-NOWHERE-00000") == ["en-US"]


# --------------------------------------------------------------- retailer resolution
def test_market_retailers_resolves_known_and_drops_unknown():
    # Park City field: "Target (Kimball Junction), Walmart (Kimball Junction), Smith's Food & Drug (Park City)"
    field = "Target (Kimball Junction), Walmart (Kimball Junction), Smith's Food & Drug (Park City)"
    retailers = market_retailers(field)
    assert retailers == ["target"]  # walmart + smith's are not sanctioned lockup retailers


def test_market_retailers_empty_field_is_empty_list():
    assert market_retailers(None) == []
    assert market_retailers("") == []


# --------------------------------------------------------------- zip builder (offline)
def test_build_asset_pack_zip_writes_manifest_and_records_missing(tmp_path):
    assets = [
        {"filename": "KODIAK-CAKES-savory-waffles-us-mw-target-1x1-20260903-v01.png"},
        {"filename": "KODIAK-CAKES-savory-waffles-us-mw-target-9x16-20260903-v01.png"},
    ]
    pack_name = build_pack_name("savory-waffles", "US-UT", "park-city-84098", date="20260903")
    zip_path, manifest = build_asset_pack_zip(
        market="US-MW-PARKCITY-84098",
        product="savory-waffles",
        assets=assets,
        retailers=["target"],
        language_tags=["en-US", "es-US"],
        dest_dir=tmp_path,
        pack_name=pack_name,
        generated="20260903",
    )
    assert zip_path.exists()
    assert zip_path.name == pack_name
    # manifest shape
    assert manifest["market"] == "US-MW-PARKCITY-84098"
    assert manifest["product"] == "savory-waffles"
    assert manifest["retailers"] == ["target"]
    assert manifest["language_tags"] == ["en-US", "es-US"]
    assert manifest["asset_count"] == 2
    # no rendered creatives on disk in CI -> both recorded as missing, none as contents
    assert manifest["contents"] == []
    assert len(manifest["missing"]) == 2
    # the zip always carries manifest.json and round-trips
    with zipfile.ZipFile(zip_path) as zf:
        assert "manifest.json" in zf.namelist()
        loaded = json.loads(zf.read("manifest.json"))
    assert loaded == manifest


def test_build_asset_pack_zip_includes_present_files(tmp_path):
    # a rendered creative that exists on disk (explicit path) must land in the zip
    rendered = tmp_path / "rendered.png"
    rendered.write_bytes(b"\x89PNG\r\n\x1a\n fake")
    fname = "KODIAK-CAKES-savory-waffles-us-mw-target-1x1-20260903-v01.png"
    assets = [{"filename": fname, "path": str(rendered)}]
    pack_name = build_pack_name("savory-waffles", "US-UT", "park-city-84098", date="20260903")
    zip_path, manifest = build_asset_pack_zip(
        market="US-MW-PARKCITY-84098",
        product="savory-waffles",
        assets=assets,
        retailers=["target"],
        language_tags=["en-US"],
        dest_dir=tmp_path,
        pack_name=pack_name,
    )
    assert manifest["contents"] == [fname]
    assert manifest["missing"] == []
    with zipfile.ZipFile(zip_path) as zf:
        assert fname in zf.namelist()


# --------------------------------------------------------------- dam helper (offline)
def test_s3_upload_and_presign_returns_none_when_disabled(tmp_path, monkeypatch):
    # ensure no DAM bucket configured -> S3 disabled -> None (graceful offline)
    monkeypatch.delenv("DAM_S3_BUCKET", raising=False)
    monkeypatch.delenv("DAM_S3_URI", raising=False)
    artifact = tmp_path / "pack.zip"
    artifact.write_bytes(b"PK\x03\x04 fake zip")
    assert dam.s3_upload_and_presign(artifact, "packs/pack.zip") is None


# --------------------------------------------------------------- endpoint (offline fallback)
@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_pack_endpoint_offline_fallback(monkeypatch):
    from fastapi.testclient import TestClient

    # force S3 disabled so the endpoint takes the local-path fallback branch
    monkeypatch.delenv("DAM_S3_BUCKET", raising=False)
    monkeypatch.delenv("DAM_S3_URI", raising=False)

    client = TestClient(app)
    resp = client.get("/assets/pack/US-MW-PARKCITY-84098", params={"product": "savory-waffles"})
    assert resp.status_code == 200
    body = resp.json()
    # offline fallback contract
    assert body["url"] is None
    assert body["key"].startswith("packs/")
    assert body["filename"].endswith(".zip")
    assert PACK_NAME_RE.match(body["filename"])
    assert body["expires_in"] == 3600
    assert isinstance(body["asset_count"], int)
    assert body["language_tags"][0] == "en-US"
    assert "local_path" in body and Path(body["local_path"]).exists()
    assert "manifest" in body
    # the produced local zip is a real archive with a manifest
    with zipfile.ZipFile(body["local_path"]) as zf:
        assert "manifest.json" in zf.namelist()


@pytest.mark.skipif(not HAS_FASTAPI, reason="FastAPI not installed")
def test_pack_endpoint_single_ratio_query(monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.delenv("DAM_S3_BUCKET", raising=False)
    monkeypatch.delenv("DAM_S3_URI", raising=False)
    client = TestClient(app)
    resp = client.get("/assets/pack/US-MW-PARKCITY-84098", params={"ratio": "1x1"})
    assert resp.status_code == 200
    assert resp.json()["filename"].endswith(".zip")
