"""Precomputed-localization memory — DynamoDB read helper for the kodiak-creatives-localization-memory table.

The scale path for POST /localize: 73 markets x 3 variants = 219 precomputed localized
strings live in DynamoDB and most reads should hit here rather than call a live model.

Transport boundary (named, not hidden): one DynamoDB get_item against a single-table key
shape. Offline / no-table / no-creds is a documented path, not a swallowed exception — every
guard returns None so the caller (localize_service) falls through to live MT or the offline
mock. Mirrors dam.py's graceful S3-disabled fallback: defensive boto3 import, env-driven
region + table name, bounded client, never raises.

Key shape (the contract the precompute WRITER and this reader must agree on):

    partition key  pk = "MARKET#<market>"       e.g. "MARKET#US-SW-LASCRUCES"
    sort key       sk = "LANG#<lang_code>#MSG#<message_key>"

message_key is a stable hash of the source text (sha1 hex, first 16 chars) so the same
source string maps to the same item regardless of whitespace/casing drift upstream. The
stored item carries the localized text under attribute `text` plus `provider` / `source`
provenance the endpoint returns verbatim.
"""
from __future__ import annotations

import hashlib
import os

try:
    import boto3
    from botocore.config import Config as _BotoConfig
    from botocore.exceptions import BotoCoreError, ClientError
except ImportError:  # boto3 optional — offline / CI still works, get_precomputed returns None
    boto3 = None  # type: ignore
    _BotoConfig = None  # type: ignore

# env-driven region + table, same resolution order localize.py / dam.py use
DYNAMODB_REGION = os.getenv(
    "LOCALIZATION_MEMORY_REGION",
    os.getenv("BEDROCK_REGION", os.getenv("AWS_REGION", "us-east-1")),
)
LOCALIZATION_MEMORY_TABLE = os.getenv(
    "LOCALIZATION_MEMORY_TABLE", "kodiak-creatives-localization-memory"
)


def message_key(text: str) -> str:
    """Stable short key for a source string — sha1 hex first 16 chars.

    Hashing (not the raw text) keeps the sort key bounded and free of DynamoDB-illegal
    characters, and normalizes leading/trailing whitespace so upstream drift does not
    fork the same headline into two items. The precompute writer MUST key with this same
    function so reads and writes land on the same item.
    """
    normalized = (text or "").strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:16]


def build_key(market: str, lang_code: str, text: str) -> dict[str, str]:
    """Return the {pk, sk} item key for a (market, lang, source-text) tuple."""
    return {
        "pk": f"MARKET#{market}",
        "sk": f"LANG#{lang_code}#MSG#{message_key(text)}",
    }


def _has_creds() -> bool:
    """Cheap, network-free credential gate — same env-var-only rationale as text_rewriter.

    boto3's credential resolution can trigger multi-second IMDS/SSO lookups; checking env
    vars keeps CI fast and prevents a live DynamoDB call when no creds are configured.
    """
    return bool(
        os.getenv("AWS_ACCESS_KEY_ID")
        or os.getenv("AWS_PROFILE")
        or os.getenv("AWS_SESSION_TOKEN")
        or os.getenv("AWS_CONTAINER_CREDENTIALS_RELATIVE_URI")
    )


def _table_enabled() -> bool:
    return bool(boto3 is not None and _has_creds())


def _client():
    """Bounded DynamoDB client, or None when disabled. Fail-fast timeouts like dam.py."""
    if not _table_enabled():
        return None
    try:
        cfg = None
        if _BotoConfig is not None:
            cfg = _BotoConfig(
                connect_timeout=int(os.getenv("LOCALIZATION_MEMORY_CONNECT_TIMEOUT_S", "1")),
                read_timeout=int(os.getenv("LOCALIZATION_MEMORY_READ_TIMEOUT_S", "2")),
                retries={"max_attempts": 1, "mode": "standard"},
            )
        return boto3.client("dynamodb", region_name=DYNAMODB_REGION, config=cfg)
    except Exception:  # noqa: BLE001 — client init failure degrades to offline path
        return None


def get_precomputed(text: str, market: str, lang_code: str) -> dict | None:
    """Return a precomputed localized variant for (market, lang, text), else None.

    Returns {text, provider, source} on a hit — provider defaults to "precomputed" and
    source to "dynamodb" so the caller can return the item verbatim. Any miss, disabled
    table, or transport failure returns None (documented fallback), never raises.
    """
    client = _client()
    if client is None:
        return None
    key = build_key(market, lang_code, text)
    try:
        resp = client.get_item(
            TableName=LOCALIZATION_MEMORY_TABLE,
            Key={"pk": {"S": key["pk"]}, "sk": {"S": key["sk"]}},
        )
    except (ClientError, BotoCoreError, Exception) as e:  # noqa: BLE001 — documented fallback
        print(f"[localize_memory] get_item miss for {key['pk']}/{key['sk']}: {e}")
        return None
    item = resp.get("Item")
    if not item:
        return None
    localized = item.get("text", {}).get("S")
    if not localized:
        return None
    return {
        "text": localized,
        "provider": item.get("provider", {}).get("S", "precomputed"),
        "source": item.get("source", {}).get("S", "dynamodb"),
    }
