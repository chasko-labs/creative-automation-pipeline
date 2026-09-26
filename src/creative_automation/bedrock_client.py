"""Shared Bedrock data-plane client — extracted from generate.py.

Fail-fast Converse client plus its timeout/region settings. bedrock_client
owns the guarded boto import (with offline shims); stability_rungs and
generate.py import from here. Outside code imports bedrock_client directly.
"""
from __future__ import annotations

import os

# Attempt boto3 import lazily — local-only mode still works without it
try:
    import boto3
    from botocore.config import Config as _BotoConfig
    from botocore.exceptions import (
        BotoCoreError,
        ClientError,
        ConnectTimeoutError,
        ReadTimeoutError,
    )
except ImportError:
    boto3 = None  # type: ignore
    _BotoConfig = None  # type: ignore

    # Offline/no-boto shims so except-tuples stay valid without boto.
    class BotoCoreError(Exception):  # type: ignore[no-redef]
        pass

    class ClientError(Exception):  # type: ignore[no-redef]
        pass

    class ReadTimeoutError(Exception):  # type: ignore[no-redef]
        pass

    class ConnectTimeoutError(Exception):  # type: ignore[no-redef]
        pass


# Bedrock fail-fast: a dedicated bedrock-runtime client for the rung-B invoke_model only,
# built with an explicit botocore Config so the old "38s then 503" becomes "12s then fall
# to C". NO retries — a retry inside a 30s gateway cap is a budget killer.
BEDROCK_READ_TIMEOUT_S = int(os.getenv("BEDROCK_READ_TIMEOUT_S", "12"))


BEDROCK_CONNECT_TIMEOUT_S = int(os.getenv("BEDROCK_CONNECT_TIMEOUT_S", "3"))


# us-west-2 needs an inference profile for Nova Pro; us-east-1 invokes directly.
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")


def _bedrock_failfast_client(read_timeout: int | None = None):
    """Fail-fast bedrock-runtime client for EVERY Bedrock invoke in the request path.

    Explicit botocore Config: connect_timeout=3s, retries max_attempts=0, and a read
    timeout that defaults to the Stability cap (BEDROCK_READ_TIMEOUT_S=12s) but can be
    overridden — the two Nova Pro Converse calls pass BEDROCK_NOVA_READ_TIMEOUT_S (6s) so
    caption + scene-prompt + stability all fit under the ~24s soft budget. NO retries,
    because a retry inside the 30s gateway cap is a budget killer. This is the ONLY way a
    bedrock-runtime client is built in rung B — no bare boto3.client anywhere in the path,
    which is the fix for the 33s silent gap (an uncapped Nova Pro Converse call).
    """
    cfg = _BotoConfig(
        read_timeout=read_timeout if read_timeout is not None else BEDROCK_READ_TIMEOUT_S,
        connect_timeout=BEDROCK_CONNECT_TIMEOUT_S,
        retries={"max_attempts": 0, "mode": "standard"},
    )
    return boto3.client("bedrock-runtime", region_name=BEDROCK_REGION, config=cfg)

