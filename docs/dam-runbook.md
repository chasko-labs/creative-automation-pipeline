# DAM S3 Sync + Fallback Runbook

Local mock remains default so pipeline works with zero AWS creds (reviewer ergonomics). S3 is opt-in via env.

## Bucket architecture

- Bucket env: `DAM_S3_BUCKET` (e.g. `chasko-labs-dam-dev`) + `DAM_S3_PREFIX=dam/` (default) or single `DAM_S3_URI=s3://bucket/dam/`
- Region: `DAM_S3_REGION` else `BEDROCK_REGION` / `AWS_REGION` (default `us-east-1`)
- Layout (mirrors `input_assets/`):

```
s3://$DAM_S3_BUCKET/dam/
  brand/logo.png
  hydrating-serum/hero.png
  radiant-moisturizer/hero.jpg
  glow-mist/main.webp
  ...
input_assets/           # local mirror — same layout, gitignored except samples
  brand/logo.png
  hydrating-serum/hero.png
```

Product lookup order in `src/creative_automation/dam.py`: `find_hero_asset` / `find_brand_logo` try S3 first (download + cache to `input_assets/<product_id>/...`), then local fallback. `explicit` may be local path or `s3://bucket/dam/product/hero.png`.

## Env

```bash
export DAM_S3_BUCKET=chasko-labs-dam-dev
export DAM_S3_PREFIX=dam/            # optional, default dam/
# or:
export DAM_S3_URI=s3://chasko-labs-dam-dev/dam
export AWS_REGION=us-east-1
# creds via SSO / env / role
aws sts get-caller-identity
```

## Sync commands (runbook)

Pull S3 -> local (before `creative-auto` run, or in CI/agentcore cold start):

```bash
aws s3 sync s3://$DAM_S3_BUCKET/dam input_assets --delete --only-show-errors --region $AWS_REGION
# dry-run first:
aws s3 sync s3://$DAM_S3_BUCKET/dam input_assets --delete --dryrun --region $AWS_REGION
```

Push local -> S3 (publish new hero/logo):

```bash
aws s3 sync input_assets s3://$DAM_S3_BUCKET/dam --delete --only-show-errors --region $AWS_REGION
# single file:
aws s3 cp input_assets/brand/logo.png s3://$DAM_S3_BUCKET/dam/brand/logo.png --region $AWS_REGION
```

Bulk helper in code (no CLI, for Lambda/AgentCore):

```python
from pathlib import Path
from creative_automation.dam import sync_dam_from_s3
sync_dam_from_s3(Path("input_assets"))  # uses same env, boto3 paginator
```

## Pipeline usage

```bash
# local only (default) — uses committed input_assets samples, generates missing heros via mock/bedrock
pip install -e .
python -m creative_automation.cli --brief briefs/example.yaml --assets input_assets --out output

# S3-first — missing local assets auto-fetched from S3; no extra flags
DAM_S3_BUCKET=chasko-labs-dam-dev python -m creative_automation.cli --brief briefs/example.yaml --assets input_assets --out output

# explicit S3 hero in brief: hero_asset: s3://bucket/dam/power-cakes/hero.png
```

## Failure modes (S3Vectors is not DAM)

- Result 4's S3Vectors fallback is for report/search, not assets — don't conflate.
- If S3 creds/bucket unavailable or `boto3` missing: code logs `[dam] s3 fetch miss` and falls back to local `find_*` with no error.
- If S3 key not found: local glob fallback; if product dir empty: hero generated via `generate_hero` (Nova Pro composition on a real asset, else mock — Nova Canvas is retired and not a path).
- Large sync: prefer `aws s3 sync` (CLI) over `sync_dam_from_s3` (boto3 loop) — CLI handles multipart, retries, delete.

## Verify

```bash
DAM_S3_BUCKET=... python -c "from pathlib import Path; from creative_automation.dam import find_hero_asset, find_brand_logo; print(find_hero_asset('hydrating-serum', Path('input_assets'))); print(find_brand_logo(Path('input_assets')))"
ls -R input_assets
# expect cache files after first S3 hit
```
