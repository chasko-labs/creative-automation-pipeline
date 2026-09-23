#!/usr/bin/env bash
set -euo pipefail
# S3 asset store sync — local <-> s3://$ASSET_STORE_S3_BUCKET/$ASSET_STORE_S3_PREFIX  (default dam/ legacy, or brands/kodiak/ for style library)
# mirrors workflow plan: design/tokens <-> s3 tokens, input_assets <-> s3 heroes/logos, output -> s3 renders

BUCKET="${ASSET_STORE_S3_BUCKET:-}"
PREFIX="${ASSET_STORE_S3_PREFIX:-brands/kodiak/}"
REGION="${ASSET_STORE_S3_REGION:-${AWS_REGION:-us-east-1}}"

if [[ -z "$BUCKET" ]]; then
  echo "[sync-asset-store] ASSET_STORE_S3_BUCKET not set — skipping s3 sync (local fallback). Set ASSET_STORE_S3_BUCKET to enable."
  echo "  example: ASSET_STORE_S3_BUCKET=chasko-creative-dam-dev ASSET_STORE_S3_PREFIX=brands/kodiak/ $0 pull"
  exit 0
fi

CMD="${1:-help}"
case "$CMD" in
  pull)
    echo "[sync-asset-store] pulling s3://$BUCKET/$PREFIX -> local"
    aws s3 sync "s3://$BUCKET/${PREFIX}tokens/" design/tokens/ --region "$REGION" --only-show-errors || true
    aws s3 sync "s3://$BUCKET/${PREFIX}heroes/" input_assets/ --region "$REGION" --only-show-errors || true
    aws s3 sync "s3://$BUCKET/${PREFIX}logos/" input_assets/brand/ --region "$REGION" --only-show-errors || true
    aws s3 sync "s3://$BUCKET/${PREFIX}references/" references/ --region "$REGION" --only-show-errors || true
    ;;
  push)
    echo "[sync-asset-store] pushing local -> s3://$BUCKET/$PREFIX"
    aws s3 sync design/tokens/ "s3://$BUCKET/${PREFIX}tokens/" --region "$REGION" --only-show-errors
    aws s3 sync input_assets/ "s3://$BUCKET/${PREFIX}heroes/" --region "$REGION" --only-show-errors --exclude "brand/*"
    aws s3 sync input_assets/brand/ "s3://$BUCKET/${PREFIX}logos/" --region "$REGION" --only-show-errors
    aws s3 sync references/ "s3://$BUCKET/${PREFIX}references/" --region "$REGION" --only-show-errors
    ;;
  push-renders)
    OUT="${2:-output_kodiak}"
    echo "[sync-asset-store] pushing renders $OUT -> s3://$BUCKET/${PREFIX}renders/"
    aws s3 sync "$OUT" "s3://$BUCKET/${PREFIX}renders/" --region "$REGION" --only-show-errors
    ;;
  help|*)
    echo "usage: $0 pull|push|push-renders [output_dir]"
    echo "  pull         s3 -> local (tokens, heroes, logos, references)"
    echo "  push         local -> s3 (publish style library)"
    echo "  push-renders output_kodiak -> s3 renders/"
    ;;
esac
