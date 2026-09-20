## Goal

Harden the sprint batch on dev: close every edge break the analysts proved,
then work the carryover queue. No new features until the batch is edge-clean.

## Success Criteria

- All 9 edge breaks fixed with targeted probes + repo tests green.
- Carryover items each meet the sprint DoD (implement + tests + docs +
  kodiak-dev receipt, no mocks as success, no new dark flags).
- Plan approval before execution starts.

## Context And Current Facts

- `dev` == `main` == `origin` at `9332fab`; dev serves the batch (verified).
- Edge analysts proved 9 breaks, all reproducible, none theoretical.
- Carryover: voice flip, outpaint-in-preview, 3 missing marks, runbook
  lines, prod deploy, coach + studio items.

## Constraints And Non-goals

- Stay on dev. No prod deploy inside this sprint.
- No stakeholder gates: owners decide open points, record them.
- Coach eval graduation stays LATER.

## Key Decisions

- RATIO_DIMS is the single size table: missing key degrades the pad, never
  the preview.
- Provenance matches shipped tiles exactly, partial or full.
- Pillow-verifies every mark before compositing, both cache locations.
- Registered-mark stripping stays as decided (ascii generated/social).

## Recommended Approach

Edge breaks first (severity order), carryover second. One owner per item,
same fanout discipline as last sprint.

## Work Plan

EDGE (owner / size):
1. Missing RATIO_DIMS key 500s preview — Backend / M. Pad skipped +
   pad_degraded KeyError, preview stays 200.
2. Stale ratios claim on partial upload — Backend / S. Provenance matches
   shipped tiles + upload entry in pad_degraded.
3. Logo cache poisoning (/tmp + logo_dir) — Backend / M. Pillow-verify
   before trust; tests cover both locations.
4. Unwritable out_dir breaks never-503 — Backend / M. Degrade to rung D or
   recorded degrade, never uncaught 500.
5. clean_brand_copy retains (R)/marks — Backend / M. Strip all registered
   forms to the clean name; bare KODIAK(R) unchanged.
6. Riff cue stays hidden after unstage — Frontend / S. Re-show via
   refreshRiffCue.
7. Engine-label object renders [object Object] — Frontend / S. Non-string
   yields 'not reported'.
8. season_for_month rejects full ISO dates — Backend / S. Accept
   YYYY-MM-DD.
9. Empty product + season ignores season table — Backend / S. Serve
   season-table pick.

CARRYOVER (owner / size):
10. Voice flip + pre-warm on — Backend / M.
11. Outpaint into preview — Backend / M.
12. Kroger/HEB/WFM marks — Backend / M. Copy-only until toolkit files land.
13. Prod deploy of batch — DevOps / M.
14. Per-item runbook lines — Docs / S.
15. Coach items — Frontend/Backend / M.
16. Studio items (carousel count, theme-mismatch skew) — Frontend / S.

## Validation Plan

- Targeted probe per edge item + repo tests for the touched area.
- Full pytest (737 baseline) + vitest (40/243, exclude `.muse/**`).
- kodiak-dev receipt with viewed pixels per merged item.

## Risks / Rollback

- Outpaint-in-preview risks the 22s wall: budget-gated, pads stay fallback.
- Voice flip risks cold-start fallthrough: co-flag + pre-warm first.
- Rollback per item is revert of its single diff.

## Open Questions

- None blocking. Owners record decisions as DECISION lines.

## Sources

None — edge probes and repo bodies this session; no external research.
