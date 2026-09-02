# Creative Automation Pipeline — Social Campaigns

poc for fde take-home: campaign brief in -> localized creatives out for 3 aspect ratios, with genai fallback and brand/legal guardrails. runs locally; promotes to bedrock agentcore.

## quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python -m creative_automation.cli --brief briefs/example.yaml --assets input_assets --out output
open output/preview.html
```

json brief works too: `--brief briefs/example.json`. localized: `--lang fr` or set `localized_messages` in brief.

## what it does

- validates brief (pydantic) — at least 2 products, region/market, audience, message
- dam lookup: `input_assets/<product_id>/hero.*` reused if present; else generates hero via bedrock nova canvas (falls back to deterministic pillow mock when no aws creds)
- localizes message: explicit `localized_messages` map wins, else bedrock nova micro translate, else offline dictionary passthrough
- composes 3 ratios: `1x1` (1080x1080), `9x16` (1080x1920), `16x9` (1920x1080) — blurred cover background + centered hero + bottom message bar + logo overlay + brand color accent
- brand/legal checks: logo presence, palette probe, prohibited words list
- writes `output/<product>/<ratio>/<product>_<ratio>.png` + `output/report.json` + `output/report.jsonl` + `output/preview.html`

## example

input `briefs/example.yaml` (3 products: hydrating-serum has real dam asset, other 2 generate):

```
output/
  hydrating-serum/1x1/hydrating-serum_1x1.png  # reused dam hero
  hydrating-serum/9x16/...
  hydrating-serum/16x9/...
  radiant-moisturizer/1x1/...                  # mock generated hero
  ...
  report.json
  preview.html
```

## design decisions

- converse over invokemodel for text (unified format, explicit maxTokens per bedrock guidance); invokemodel only for nova canvas image which has no converse path
- pillow for resize/pad not genai resize — deterministic, cheap, keeps hero identity; genai for missing hero only
- mock fallback is intentional for reviewer ergonomics — pipeline works with zero aws creds; real bedrock path is primary and logs `[generate] bedrock` vs `mock`
- brand check is lightweight (dominant color probe + logo overlay flag) — real prod would use nova act browser automation to visually verify rendered creatives

## bedrock + agentcore leverage

- `BEDROCK_REGION` / `AWS_REGION` env, `BEDROCK_NOVA_CANVAS_MODEL=amazon.nova-canvas-v1:0`, `BEDROCK_NOVA_TEXT_MODEL=amazon.nova-micro-v1:0`
- enable models: `aws bedrock list-foundation-models --region us-east-1`
- promote to agentcore runtime: wrap `run_pipeline()` as agent handler, deploy via `bedrock-agentcore-control` (see docs/agentcore.md)

## assumptions / limits

- local dam is folder; s3 dam would be `aws s3 sync s3://bucket/dam input_assets` or gateway tool
- no video/reel generation in poc; nova reel could extend
- legal list is demo; prod would use bedrock guardrails
- fonts use dejavu if available else default
