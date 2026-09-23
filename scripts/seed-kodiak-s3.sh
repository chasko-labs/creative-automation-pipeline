#!/usr/bin/env bash
set -euo pipefail
# Seed Kodiak style library to S3 — idempotent, local-first
BUCKET="${ASSET_STORE_S3_BUCKET:?set ASSET_STORE_S3_BUCKET}"
PREFIX="${ASSET_STORE_S3_PREFIX:-brands/kodiak/}"
REGION="${ASSET_STORE_S3_REGION:-${AWS_REGION:-us-east-1}}"

echo "[seed] seeding kodiak tokens + references -> s3://$BUCKET/$PREFIX"
aws s3 cp design/tokens/kodiak.json "s3://$BUCKET/${PREFIX}tokens/kodiak.tokens.json" --region "$REGION"
aws s3 sync references/ "s3://$BUCKET/${PREFIX}references/" --region "$REGION" --only-show-errors
aws s3 cp input_assets/brand/logo.png "s3://$BUCKET/${PREFIX}logos/kodiak-bear.png" --region "$REGION" || true
# nova canvas seeds would be uploaded here after generation:
# aws s3 sync output_kodiak/_work/ "s3://$BUCKET/${PREFIX}heroes/_seed/nova-canvas/" --region "$REGION"
echo "[seed] done. verify: aws s3 ls s3://$BUCKET/$PREFIX --recursive --region $REGION | head -n 30"
