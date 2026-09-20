## Goal

Bring the KODIAK app to production quality: generated preview matches the
placeholder promise (5 tiles, 3 localizations, honored selections), no mocks
reported as success, no dark paths as production paths.

## Success Criteria

- SF/Halloween/Costco repro produces 5 tiles, season-tagged recipe, logo
  overlay, zero aisle pixels, copy matching pixels.
- Every sprint item merges with tests + docs + kodiak-dev receipt.
- Zero open impediments; every NO-GO item has an owner and unblock action.

## Context And Current Facts

- `dev` == `main` == `origin` at `8d9cca3`; prod serves current build with the
  elk-rut 9:16 tile verified live.
- Parity spec: `docs/plans/2026-09-20-preview-parity-spec.md` (5 defects).
- First confidence round rated 7 items GO; skeptic verification held only 1
  (seed_key 9/10), conditionally held 2 (declutter 7, voice 7 co-flag), and
  downgraded 4 to NO-GO. Bar finding: round one credited plumbing and partial
  prior art instead of shippable target state.

## Constraints And Non-goals

- No new dark flags without an enablement item in the same sprint.
- No mocks reported as success; mocked unit tests stay separate from live
  receipts.
- Coach eval graduation, studio presets, facet chips stay LATER.

## Key Decisions

- Retailer directions never enter pixel prompts; logo overlay only (decided).
- Preview fills 5 tiles via server-side pillow-pad within the 22s wall;
  outpaint moves into preview later (recommended).
- Season becomes a structured request field; brief-text leak stripped or
  display-only.
- Voice enablement ships behind its flag with pre-warm on; fallback copy
  stays until voice is live, then becomes the exception path.

## Recommended Approach

Enter sprint with the 3 held items; run the 6 impediment unblocks as the
dispatch queue. Re-rate each NO-GO item when its unblock lands.

## Work Plan

ENTER (GO):
1. orin / staged-DAM seed_key priority end to end — 9/10. No impediment.
2. liora / declutter removal-only pass — 7/10. Non-blocking caveat: Nova Act
   driver needs API key; chromium fallback acceptable.
3. voss / voice enablement in wall budget — 7/10 CONDITIONAL on co-flag
   deploy. Unblock first: enable EventBridge pre-warm (currently
   disabled-by-default, cold invokes degrade silently).

UNBLOCK QUEUE (NO-GO + intervention):
4. orin / hollow carousel + riff cue — 5/10. implementation/frontend: slots
   render with 1-2 products; cue writes to hidden dialog node.
5. orin / similarity gate + scene-prompt provenance — 5/10. knowledge:
   select metric/threshold, calibrate B→C gate on staged renders.
6. orin / rung-B source labels — 5/10. implementation/contract: backend and
   frontend engine keys mismatch; no origin field exists either side.
7. stratia / retailer overlay — GO with 4 marks. Costco, Target, Walmart,
   Publix ingested to brands/retailers/logos/ + MANIFEST.json; Kroger, HEB,
   Whole Foods fall back to copy sidecar line (no overlay) until toolkit
   files land. No gating: sprint moves with what exists.
8. stratia / multi-theme combination + panel flags — 6/10. knowledge: needs
   frontend request contract + panel-flag inventory + retailer PNGs.
9. scribe / season field + pairing — 4/10. better-fit-agent: data-model
   owner adds season to recipe schema + pairing index first.
10. scribe / brand injection into fallback — 4/10. data-authoring +
    research: no machine-readable brand-copy source; iso-naming vs
    clean_brand_copy mark-stripping undecided.
11. voss / image-model re-verify — 5/10. mcp-access: live Bedrock invokes +
    receipts in us-east-1.
12. voss / test rewrites — 6/10. tooling: retailer-frontier-pairs dedupe
    across 61 markets first.

## Validation Plan

- Repro from the parity spec; assert tiles, localizations, overlay,
  recipe season tag.
- `npx vitest run tests/vitest/` (38 files green today); pytest pack +
  rewritten lambda/retailer/recipe/contract suites per item.
- kodiak-dev receipt with viewed pixels per merged item.
- Re-rate NO-GO items post-unblock before sprint entry.

## Risks / Rollback

- Voice enablement risks wall fallthrough: co-flag deploy, pre-warm first,
  rollback is flag-off (pixels unaffected).
- Retailer overlay carries trademark exposure: default disabled until
  per-retailer permission lands.
- Similarity gate miscalibration fails good renders: calibrate on staged
  renders before enabling the fail path.

## Open Questions

- Who owns the data-model season-schema item (scribe blocked on it)?
- Proceed with pillow-pad (design spec + QA only from liora) under a python
  implementer, or defer 5-tile parity one sprint?
- Legal owner for retailer co-marketing permissions?

## Sources

None — all claims verified against repo bodies this session; no external
research used.
