# Bedrock invoke receipts — voice enablement sprint (2026-09-20)

Live invoke evidence captured with `AWS_PROFILE=bryanchasko-kiro` (account
946179428633) from the sprint worktree. One minimal-cost invoke per model;
budgets kept tiny (Nova Pro `maxTokens: 32`, Stability seed 256x256 PNG,
voice `maxTokens: 256`). Probe script is throwaway (`/tmp/capture_bedrock_receipts.py`,
not committed); this doc is the durable receipt.

## 1. Nova Pro art-direction (us-east-1, Converse)

- model: `amazon.nova-pro-v1:0`
- api: `Converse`, `HTTP 200`, `retry_attempts: 0`
- request id: `095568ed-540c-4f46-bcdc-0bae0c51b1ba`
- latency: **1.35s** (well inside the 6s Nova fail-fast read timeout)
- stop: `end_turn`, usage: 10 in / 11 out / 21 total tokens
- output: "Morning feast: Kodiak pancakes, berries, joy."

## 2. Stability control-structure restyle (us-east-1 inference profile, InvokeModel)

- model: `us.stability.stable-image-control-structure-v1:0`
- api: `InvokeModel`, `HTTP 200`, `retry_attempts: 0`
- request id: `54f6fdbc-bf49-4621-b2b9-79c7a3afcca7`
- latency: **8.18s** (inside the 12s Bedrock fail-fast read timeout +
  inside the 13s `_B_STABILITY_MS` rung-B reservation)
- result: 139,411-byte PNG, `seed` echo `[42]` (locked-seed consistency holds)
- schema note: `output_format` must be lowercase `"png"` — `"PNG"` raises
  `ValidationException`. `src/creative_automation/generate.py:1181` already
  sends lowercase; the probe initially hit this and was corrected to match.

## 3. Art-director voice (us-west-2 imported model, Converse)

- model: `arn:aws:bedrock:us-west-2:946179428633:imported-model/cx15b77k5nge`
- first probe: `ModelNotReadyException` ("Model is not ready for inference") —
  the documented scale-to-zero cold start, caught live.
- after ~2 min of warming retries: `HTTP 200`, latency **0.48s** warm,
  stop `end_turn`, usage 64 in / 76 out / 140 total tokens
- request id: `22c058fd-4447-49c5-be54-814eea17a3a7`
- output (adventurous voice, trained `### Instruction: / ### Response:` shape):
  "The sun's rays creep over the horizon ... The call of the wild is loud,
  and you answer."

### What the voice receipt proves about the wall design

A cold imported model needs **minutes**, not seconds, to warm — so the
in-request fast probe (`RETRY_ATTEMPTS=2` x `RETRY_SLEEP_SECONDS=2s`, worst
case ~2s of sleep) will correctly miss a cold model and degrade voice-off,
and the 6s `KODIAK_ARTDIRECTOR_TIMEOUT_S` inner bound will correctly abandon
it. Warmth is the pre-warm Scheduler's job (`artDirectorPrewarm`, DISABLED by
default alongside the dark voice flag), not the request path's. The receipt
sequence above — cold miss, then 0.48s warm hit — is the design working as
documented in `src/creative_automation/art_director.py:71-80`.

## Flag defaults (unchanged — prod defaults not flipped)

- `KODIAK_ARTDIRECTOR_ENABLED` default `false` (dark voice) —
  `src/creative_automation/generate_lambda.py:86`
- `artDirectorPrewarm` Scheduler `DISABLED` unless `-c artDirectorPrewarm=on` —
  `infra-cdk/lib/generate-stack.ts:286`
- `KODIAK_DIRECTOR_GROUNDED` default `true` (grounded headline kill-switch,
  per-call read so ops can flip without redeploy) — `src/creative_automation/generate.py:160`
- `KODIAK_ENABLE_STABILITY_RUNG` default `1` (generative rung on) —
  `src/creative_automation/generate.py:83`
- Wall composition pinned by `tests/test_voice_flags.py`: inner voice 6s <
  outer wall 22s; director sleep worst case 2s <= inner 6s; voice collect 2s <
  inner 6s.
