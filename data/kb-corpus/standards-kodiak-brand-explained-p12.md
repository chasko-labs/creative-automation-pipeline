```bash
cd ~/code/chasko-labs/creative-automation-pipeline
uv run pytest -q                               # 3 passed
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/kodiak-human
open /tmp/kodiak-human/preview.html            # human view
cat /tmp/kodiak-human/report.json | head -n 60
```

Or with the live bucket:

```bash
export AWS_PROFILE=bryanchasko-kiro
export ASSET_STORE_S3_BUCKET=chasko-creative-dam-946179428633-us-east-1 ASSET_STORE_S3_PREFIX=brands/kodiak/
./scripts/sync-asset-store.sh pull
ASSET_STORE_S3_BUCKET=... uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak
aws s3 ls s3://$ASSET_STORE_S3_BUCKET/brands/kodiak/ --recursive | head -n 20
```

The brand you see in S3 and in `design/tokens/` is the same brand you see in `output_kodiak/preview.html` — one system, rendered three ways, ready for the next retail corridor.
