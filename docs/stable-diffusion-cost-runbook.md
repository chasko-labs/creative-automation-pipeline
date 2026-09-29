# stable diffusion cost + utilization runbook

source: image-generation cost/utilization audit, Sept 2026 (account bryanchasko-kiro, 946179428633). this doc records what the image spend is, where the real cost risk sits, and what is built-but-unused. it is a reference, not a change — tracked work lives in issues #308-311.

## scope discipline for this sprint

every remediation from this runbook deploys to `kodiak-dev.bryanchasko.com` only. nothing promotes to `kodiak.bryanchasko.com` (prod) this sprint. the deploy contract is authoritative in [`kodiak-environments.md`](kodiak-environments.md): a named branch deploys to the shared dev host via `scripts/deploy-frontier.sh dev`, `main` deploys to prod only after approval, and a git push alone never deploys.

## what the image money is

the pipeline's Mode 1 hero path (see [`training-process.md`](training-process.md) and `src/creative_automation/generate.py`) is a seed-driven restyle, not text-to-image from scratch: a real DAM lifestyle photo seeds a Bedrock Stability control-structure restyle (control strength 0.7) under a Nova Pro art-direction prompt, then a deterministic Pillow brand overlay lands the bear, the blaze bar, and the kraft texture.

Sept 2026 spend, per Cost Explorer usage-type detail:

| line | volume | spend | per-image |
| --- | --- | --- | --- |
| Stability control-structure (restyle workhorse) | ~260 images | ~$14.80 | ~$0.07 |
| Stability outpaint (9:16 / 16:9 ratio extends) | ~60 images | ~$2.44 | ~$0.06 |
| Stability search-replace | 1 image | $0.07 | — |
| Stable Image Core (base text-to-image, us-west-2) | 1 image | $0.04 | — |
| Nova Pro / Nova Micro / Nova 2 embeddings | — | ~$0 | Amazon-model credit absorbs |
| Custom Model Import (kodiak-artdirector-1b) | 240 inference units + storage | ~$0 | credit-absorbed today |

total image spend ~$17, effectively all Stability, because Stability on Bedrock is a third-party Marketplace product and does not receive the Amazon-model credit treatment. the spend is pay-per-image with no idle burn — it returns to zero when generation stops.

## what is actually worth watching (ranked)

the four items below are all cheap-or-free to investigate. each has a tracking issue.

- restyle-cache hit rate (#308) — the highest-leverage image-cost check. the content-addressed cache exists (`generate.py` `_restyle_cache_*`, prefix `brands/kodiak/renders/restyle-cache/`, correctly scoped under the GenerateLambda `renders/*` grant in `infra-cdk/lib/generate-stack.ts`). repeated same-seed batches (Sept 8: 96 images) suggest param sweeps that should be cache-eligible. verify the cache returns hits rather than silently missing.
- Custom Model Import cost surface (#309) — two imported models sit resident in us-west-2: `kodiak-artdirector-1b` (llama, live, wired in `art_director.py`) and `herald-qwen3-1p7b-voss-v1` (qwen3, not referenced by this pipeline). CMU bills per active 5-minute window plus per-model storage — the line that bills first once credits lapse. decide whether qwen3 stays resident and whether pre-warm vs cold-start is right per environment.
- embedding retrieval wire (#310) — the Nova 2 multimodal index is built and populated (8,794 image embeddings, 1024-dim, S3 Vectors) and `reference_api.search()` works, but no call to it exists in `pipeline.py`, `compose.py`, or `campaign.py`. `training-process.md` marks it "future wire, mock today". built capacity, unrealized value — not a cost problem.
- base text-to-image access gate (#311) — only the seed-driven control-structure edit model is granted. the base generators (stable-image-core, stable-image-ultra, sd3-5-large) exist only in us-west-2 and are not access-granted. correctly gated for hero shots (control-structure preserves real pack geometry); base generation is only worth requesting for seed/background creation, and only against a us-west-2 region split.

## how to re-pull the numbers

read-only, safe to run any time. requires a valid `bryanchasko-kiro` profile.

```bash
# image spend by usage type, current month
aws ce get-cost-and-usage \
  --time-period Start=2026-09-01,End=2026-09-30 \
  --granularity MONTHLY --metrics UnblendedCost UsageQuantity \
  --group-by Type=DIMENSION,Key=USAGE_TYPE \
  --filter '{"Dimensions":{"Key":"SERVICE","Values":["Stability AI Image Services (Amazon Bedrock Edition)","Stable Image Core (Amazon Bedrock Edition)"]}}' \
  --region us-east-1 --profile bryanchasko-kiro

# imported models resident in us-west-2
aws bedrock list-imported-models --region us-west-2 --profile bryanchasko-kiro

# confirm no on-Bedrock customization jobs (training was off-Bedrock, imported)
aws bedrock list-model-customization-jobs --region us-west-2 --profile bryanchasko-kiro
```

## the rule in one sentence

the Stable Diffusion spend is small, pay-per-use, and self-limiting — the real watch-items are the restyle-cache hit rate, the resident Custom Model Import footprint, and the unwired embedding retrieval, all tracked in #308-311 and all fixed on dev before prod.
