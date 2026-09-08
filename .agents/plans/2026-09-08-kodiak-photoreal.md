## Goal

Photoreal campaign images on kodiak.bryanchasko.com on every Create: rung A/B photographic output by default, fallback sightings near zero, in-scene gibberish gone.

## Success Criteria

- A standard brief POST /generate returns `source` rung A or B with viewed photographic pixels, 5 consecutive runs.
- No `brand-floor` on standard briefs for a week after ship (counted from the surfaced labels, not anecdotes).
- Zero in-scene gibberish on shipped renders; all readable text comes from verbatim overlays.
- The team stops relitigating model availability (state recorded once, with pointers).

## Context And Current Facts

Correction (Bryan, tonight): the Canvas lockout diagnosis was wrong — the account had a billing issue, now resolved. Every prior Canvas/Titan denial receipt is confounded and must be re-tested, not quoted. Billing fixes can also need fresh role assumption before taking effect.

Other live receipts (still standing until re-tested):

- Rung B (Nova Pro art-direction + Stability restyle) verified live in production with viewed pixels (`final-rungB.png`): cabin-shoot photography, correct overlays.
- `amazon.nova-canvas-v1:0` invoked tonight pre-fix: denied (LEGACY). Under re-test per the correction.
- Prompt suppression of in-scene text deployed and tested live: failed (control-structure preserves sign shapes; "KUTTAK", "FOWER CARSS"). Erase/inpaint needs pixel masks with no detector available. Search-replace erased the box itself.
- Commit `41f991f` shipped (1024px JPEG seeds for Nova, 1280px Stability ceiling) after proving 15 MB seeds starved every vision call (Converse drops payloads over ~3.75 MB).

Standing state:

- Ladder #114-#118: A packshot / B Stability (12s cap) / C Pillow / D brand-floor, 22s wall, 503 structurally impossible. CDK grants in `infra-cdk/lib/generate-stack.ts:84` (Nova Pro) and `:102-116` (Stability profiles, 3 regions).
- Valkey: `kodiak:bedrock-image-verdict:2026-09` (now STALE — superseded by Unit 0's receipt), `kodiak:stability-enablement:2026-09`, `kodiak:never-fail-ladder:2026-09-05`.
- I cannot invoke AWS from here (CLI present, SSO device-code required); the team runs all live proofs.

## Constraints And Non-goals

- Website-first. The localhost canvas stand-in is out of scope.
- No new text-detector/mask infra this round.
- PR-only, harness-green, version-bump deploy per repo rules. Never `--no-verify` without explicit operator permission.

## Key Decisions

1. Unit 0 re-tests Canvas and Titan access live before any other conclusion is quoted. The plan branches on its receipt (see Unit 0).
2. Until Unit 0 lands, rung B Stability restyle remains the primary path (proven with pixels). No work waits on Unit 0 except Units 4-5.
3. Gibberish fix is textless scenes as primary; the source of those scenes (generated via Canvas/Titan vs acquired seeds) is decided by Unit 0's receipt. Rejected regardless: prompt suppression (failed live), erase (no masks), search-replace (destroys box art).
4. Every render declares its rung via the `source` label surfaced in the preview UI (#173 proposal). Fallback sightings become counted facts, never again anecdotes.
5. Rung time budgets are tuned from measurement, and the 22s wall itself is never touched (availability over quality per #118 discipline).

## Recommended Approach

Re-prove availability first (billing changed the ground), lock the proven path in parallel, then raise the ceiling down whichever branch the receipt opens.

## Work Plan

- Unit 0, re-verify image-model access post-billing-fix (kodiak team, first, blocks Units 4-5 only): fresh role assumption, then minimal live invokes of `amazon.nova-canvas-v1:0` and the Titan image models plus `list-foundation-models` in us-east-1. Paste full receipts (success PNG or full error text) to the issue. Branch A: Canvas (or Titan) invokes → wire a text-to-image rung generating textless lifestyle scenes, verbatim box composited on top; gibberish solved structurally. Branch B: still denied → textless acquired seeds per Unit 5, Titan question closed with the new receipt.
- Unit 1, lock rung B (parallel with Unit 0, no new deps): confirm Lambda serves the latest image; fire 5 consecutive standard-brief POSTs; record all five `source` labels. Any D is a quality signal to investigate, not an incident.
- Unit 2, surface source labels in the preview UI (closes #173): each preview renders its `source`; fallback renders carry a visible badge.
- Unit 3, harness gate: extend `tests/nova-act/run.py` with a check asserting the standard brief yields rung A or B; keep the sabotage negative control.
- Unit 4, wire the winning ceiling (follows Unit 0): Branch A → text-to-image rung behind the same wall/budget discipline, viewed verification. Branch B → close with receipt, no further discussion.
- Unit 5, textless scenes (follows Unit 0): Branch A → generate 3 pilot scenes; Branch B → acquire 3 pilot scenes (stock first). Viewed verification, zero gibberish required either way.
- Unit 6, record state: overwrite the stale verdict Valkey key with Unit 0's receipt plus a pipeline.html refresh (Canvas status in plain words, Nova Act disambiguation) so the history is read, not remembered.

## Validation Plan

- Unit 0: pasted receipts — invoke output or full error text, plus model list. No receipt, no branch decision.
- Unit 1: five POSTs, all 200, all source A/B, pixels viewed. Commands: standard-brief curl + `jq .source`, presigned-URL download, view.
- Unit 2: manual — preview shows label; a forced-fallback brief shows the badge.
- Unit 3: `python tests/nova-act/run.py` green including the new check; sabotage run exits nonzero.
- Unit 4: Branch A — three generated scenes viewed photographic; Branch B — closure receipt on the issue.
- Unit 5: three restyles viewed, zero in-scene text, overlays verbatim.
- Unit 6: read-back of the page and the Valkey key.

Highest-risk validation: Unit 0's receipt — it decides the ceiling for the entire plan.

## Risks / Rollback

- Billing propagation delay: re-assume roles before invoking; a denial within minutes of the fix proves nothing — wait, re-assume, re-test, then record.
- Rung B latency against the 24s wall: measure first via Unit 1 labels; the wall does not move.
- Stability throttling: fail-fast timeouts already bound it; the D floor stays intact. Rollback is the previous Lambda image tag.
- Generated-scene brand drift (Branch A): verbatim box + overlay text stay the brand carriers; scenes are backdrops until proven otherwise.

## Open Questions

- Pilot seed sourcing if Branch B: licensed stock or commissioned shoot for the first 3 textless scenes? Default: stock pilot (reversible, fast).
