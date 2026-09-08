## Goal

Turn the darkroom into a studio: campaigns the pipeline shoots, not just restyles. Fresh scenes from a line of text, a locked brand mascot in every frame, ratios composed for the frame, campaigns that learn from past campaigns, and a coherence floor under all of it.

## Success Criteria

- A text brief with no seed photo produces a photographic scene (text-to-image rung live, viewed).
- The Kodiak bear appears recognizably identical across 3 different scenes (mascot lock, viewed side by side).
- 16:9 and 9:16 are outpainted compositions, not crops (viewed: no amputated subjects, no stretched fills).
- "Riff on past content" retrieves real past DAM renders by similarity and visibly informs the new brief.
- A headline that contradicts its image fails the coherence check (proven with a deliberate mismatch probe).
- Three themes (cabin, market, campfire) each carry their own locked look — distinguishable at a glance, all on-brand.

## Context And Current Facts

- DoD v2 is the floor and stands (photographic 4-ratio packs, badges A/B, harness green, scorecard A, stamp read-back). This plan is the ceiling above it.
- Tonight's receipts: rung B restyles verified live; no text-to-image model in account 946179428633 (Canvas LEGACY denied, Titan image EOL, Reel LEGACY — all re-tested post-billing-fix, Branch B, on #173).
- Granted but unwired: `stability.stable-outpaint-v1:0` across 3 regions (`generate-stack.ts:113-116`); Nova multimodal embed pipeline (dedup live, retrieval never built).
- Control-structure at 0.7 preserves seed composition — restyles vary, never invent. Prompt suppression of in-scene text failed live; verbatim overlays remain the only text path.
- I cannot invoke AWS from here (CLI present, SSO device-code required); the team runs all live proofs.

## Constraints And Non-goals

- AWS-first: off-Bedrock rendering only on a receipt showing Bedrock can't cover it.
- Website-first; PR-only, harness-green, version-bump deploy; never `--no-verify` without explicit operator permission.
- No new text-detector/mask infra this round.

## Key Decisions

1. The text-to-image question is one decision — which model, in which account, on whose bill (Unit 1). No rendering architecture is chosen before its receipt.
2. The mascot is the DAM bear PNG — decided, no alternatives. One bear, fixed descriptors, reused across scenes (Unit 2).
3. Ratios are composed via outpainting, never cropped (Unit 3).
4. Memory is retrieval over the DAM, not a slogan (Unit 4).
5. Coherence is a gate: claim-vs-scene mismatch fails the pack (Unit 5).
6. Range is per-theme locked presets, never one global preset and never unlocked free-styling (Unit 6).
7. All spend is Bryan's. If Unit 1 approves off-Bedrock rendering, GPU spend goes to the jitsi account first, kiro account second, tagged and alerted. Decided, no further question.

## Recommended Approach

Prove the renderer first (Unit 1 decides everything downstream), then lock the subject, compose the frames, add memory, gate coherence, and widen range last.

## Work Plan

- Unit 1, text-to-image decision (kodiak team, first, blocks nothing else but informs Units 2-6): invoke-probe every candidate — Titan Image Generator v2 / Stable Image Core enablement in 946179428633, model listings in the other accounts and regions, serverless GPU price/latency probe. Output: one chosen path with an invoke receipt (viewed pixels) pasted to the issue, or a closure receipt (all denied — ceiling stays restyle-only, acknowledged in writing).
- Unit 2, mascot lock (parallel with Unit 1): freeze the DAM bear PNG plus a fixed descriptor block in the style sandwich subject slot; generate the same mascot across cabin, market, and campfire scenes; viewed side-by-side proof of identity.
- Unit 3, outpaint ratios (parallel): wire `stable-outpaint-v1:0` so 16:9 and 9:16 extend the 1:1 hero; viewed proof on all three pilots, no amputations, no stretch fills.
- Unit 4, retrieval memory: "Riff on past content" embeds the brief and returns the top similar DAM renders into the art-direction context; proven with a brief whose riff visibly changes the output versus the same brief without it.
- Unit 5, coherence critic: Nova Pro vision checks headline against image; a deliberate mismatch probe (e.g., "blueberry" headline on a campfire-pot scene) must fail the pack; sabotage control kept green-to-red honest.
- Unit 6, theme range: three locked presets (cabin / market / campfire), each style-sandwiched and seed-disciplined independently; same brief across all three yields three distinguishable, all-on-brand campaigns.
- Unit 7, record state: Valkey key plus pipeline.html refresh so the studio ceiling is read, not remembered.

## Validation Plan

- Unit 1: invoke receipt (pixels) or closure receipt (full error texts) on the issue. No receipt, no downstream rendering choice.
- Unit 2: three scenes viewed side by side, same bear. A stranger could pick the mascot out of a lineup.
- Unit 3: three pilots × three ratios viewed; crop-detector check (edge-continuity) passes where a crop would fail.
- Unit 4: A/B proof — same brief with and without riff produces visibly different, visibly informed output; retrieved render IDs logged.
- Unit 5: mismatch probe fails the pack; matching pack passes; sabotage control exits nonzero.
- Unit 6: same brief, three themes, three distinguishable on-brand packs viewed.
- Unit 7: read-back of the page and the Valkey key.

Highest-risk validation: Unit 1's receipt — it decides whether the studio gets built or the ceiling stays acknowledged.

## Risks / Rollback

- Unit 1 returns all-denied: plan collapses to Units 2-6 on restyle rails (mascot, outpaint, memory, critic, range all still work on restyles). Record the cap in writing; stop asking.
- Mascot drift across scenes: tighten descriptors, then strength; if unfixable on restyle rails, mascot waits for the text-to-image rung.
- Outpaint cost/latency vs the 22s wall: measure per-ratio; wall does not move — slow ratios ship async or not at all.
- Rollback throughout is the previous Lambda image tag plus the D floor, which stays intact.

## Open Questions

None. Both review questions were decided: mascot is the DAM bear; all spend is Bryan's (jitsi account first, kiro second).
