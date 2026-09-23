5. **Save and learn.** Assets land organized by product and ratio: `output_kodiak/power-cakes/1x1/power-cakes_1x1.png` and so on, plus `output_kodiak/report.json`, `report.jsonl` (one JSON line per creative — product, ratio, region, hero_source asset library vs mock vs bedrock, compliance pass), and `output_kodiak/preview.html`. Local lives in `output_*`; with creds, `scripts/sync-asset-store.sh push-renders output_kodiak` mirrors to `s3://.../brands/kodiak/renders/`.

6. **Style library stays in sync.** Tokens, references, logos, and templates live in S3 under `brands/kodiak/` and mirror to `design/tokens/`, `references/`, `input_assets/` locally. `./scripts/sync-asset-store.sh pull` before a run, `push` after you publish a new token or Keep It Wild reference. Infra is `infra/s3-dam.tf` (versioned, KMS, public-blocked, lifecycle to IA/Glacier/Deep Archive).

**To see it yourself from a fresh shell:**
