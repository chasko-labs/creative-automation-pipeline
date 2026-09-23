#!/usr/bin/env python3
"""Publish campaign pool renders to the asset store ideas prefix (Browse past assets).

Target: brands/kodiak/renders/campaign/<market>/<file>.png — the ideas tab
lists this prefix verbatim. HEAD-first idempotency: existing keys are
skipped, so re-runs cost nothing.

Usage: AWS_PROFILE=bryanchasko-kiro python scripts/publish_campaign_to_asset_store.py [--limit N]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "input_assets" / "campaign"
DEST_PREFIX = "brands/kodiak/renders/campaign/"
sys.path.insert(0, str(ROOT / "src"))
from creative_automation.asset_store import _s3_bucket_and_prefix  # noqa: E402

BUCKET, _ = _s3_bucket_and_prefix()
if not BUCKET:
    print("no asset store bucket configured (ASSET_STORE_S3_BUCKET/ASSET_STORE_S3_URI)", file=sys.stderr)
    raise SystemExit(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    files = sorted(POOL.glob("*/*.png"))
    if args.limit is not None:
        files = files[: args.limit]
    client = boto3.Session(profile_name=os.environ.get("AWS_PROFILE", "bryanchasko-kiro")).client(
        "s3", config=Config(retries={"max_attempts": 5, "mode": "adaptive"})
    )
    done = skipped = 0
    for f in files:
        key = DEST_PREFIX + f.parent.name + "/" + f.name
        try:
            client.head_object(Bucket=BUCKET, Key=key)
            skipped += 1
            continue
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") not in ("404", "NoSuchKey", "NotFound"):
                print(f"HEAD failed {key}: {e}", file=sys.stderr)
                continue
        except Exception as e:  # noqa: BLE001 — report and move on
            print(f"HEAD failed {key}: {e}", file=sys.stderr)
            continue
        try:
            client.put_object(
                Bucket=BUCKET, Key=key, Body=f.read_bytes(), ContentType="image/png"
            )
            done += 1
        except Exception as e:  # noqa: BLE001 — report and move on
            print(f"PUT failed {key}: {e}", file=sys.stderr)
            continue
        if (done + skipped) % 20 == 0:
            print(f"[{done + skipped}/{len(files)}] put={done} skipped={skipped}", flush=True)
    print(f"done: put={done} skipped={skipped} total={len(files)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
