## Goal

Unify section-4 selectors around checkboxes, remove redundant and artifact copy, clarify the verification caveat, enrich the page background, fix about-art gaps, and fill the seasonal database through fanned-out research. All color and style work flows through the Panda token toolchain; no hand-slapped hex, no inline styles.

## Success Criteria

- Partner collapses to ONE checkbox: the pill and its mark flag merge into a single control carrying both the brief clause and the layer consequence (mark preview stays inline). The sync bridge is deleted, not preserved.
- Retailer becomes three checkboxes: Costco, Publix, All localized retailers. Each checkbox IS the selection and the mark driver (most-recent wins); the separate mark flag disappears. All means brief-level multi-retailer framing across the backend-supported moods (target, walmart, publix, kroger, heb, whole-foods); albertsons rides brief-text only until a scene mood lands.
- Every creative-direction selector is one checkbox owning brief + layer consequences; `syncLayersFromChips`/`syncChipsFromLayers` are deleted; the layers contract is unchanged (single-slug retailer mark).
- Artifact copy is gone: "never center-pasted" and "Copy always ships as sidecar text/CSV downloads — never baked into pixels."
- The caveat reads "(months unverified)" with a UI legend, and the research fan-out replaces unverified entries with sourced months where the web can confirm them.
- Page background carries layered light + grain; about art sits flush with no gap above; peaks no longer clip; inter-section caps shrink page-wide.
- `generate()` produces identical `layers{}` output for equivalent selections before and after; builder `--check` green.
- Vitest 126+ passes, affected pytest green, desktop + 390px renders verified, deploy verified live.

## Context And Current Facts

- Section 4 today, verified this run: retailer row is 3 pills + 1 mark checkbox (`index.html:284-290`); partner row is 1 pill + 1 mark checkbox + mark preview (`index.html:297-306`); product flag is 1 checkbox + the sidecar hint line (`index.html:335-336`). The pill↔flag two-way sync lives in `js/prompt-chips.js` (`activeRetailerValue:199`, `syncLayersFromChips`, `syncChipsFromLayers`); ids and `data-theme` slugs are pinned by `tests/vitest/scope-cluster-218.test.mjs:94-110`.
- Chip-state consumers that the merge must migrate, verified this run (`grep ff-chip|aria-pressed|__activeTheme|data-theme`): `prompt-chips.js` core (toggle, brief assembly, retailer value, reset/restore), `autocomplete.js:97` (suggestion apply), `coach-about.js:47,105` (theme collection + confirm-to-apply), `coach-insights.js:66` (payload theme), `generate.js:454,730` (theme read + run-lock), `lifecycle-persist.js:146` (snapshot/restore). asset store facet chips (`prompt-chips.js:748-882`) are a separate system, out of scope.
- Backend contract, verified this run: `normalize_layers` keeps `retailer` as ONE non-empty slug string (`src/creative_automation/generate.py:1848-1867`); one mark per image is by design. Scene moods exist for target, walmart, whole-foods, publix, kroger, heb, plus the localized trio and subscription (`generate.py:429-487`); albertsons has no mood key.
- About art, verified this run: `.ff-about-art{margin:var(--spacing-sm) 0 0}` plus `.ff-about-range{margin:2px 0 10px}` (`design/components.css:769-770,983`) stack the gap the user sees; peaks reach y=30/36 in a 120-tall `xMidYMid slice` viewBox (`index.html:474`), so wide crops clip them.
- Page background today is one radial + one linear (`components.css:1238`); grain tokens (`--wood` et al.) exist and are already used on the CTA.
- Caveat strings live in `featuredFrontierDetail` seasons/farmersMarket fields (`js/data-core.js`) and surface through `featuredFrontierFor().text` into readouts and the backend hint; 69 entries carry them.

## Constraints And Non-goals

- Create Campaign Preview button untouched (approved). Numbering stays 4.1/4.2/4.3.
- No backend contract changes: `normalize_layers` single-slug rule stands; no new Lambda endpoints; coach untouched.
- No new dependencies, no Spectrum runtime, no bundler. Token-bridge seam intact.
- Assumption (reversible): frontier-green accent + bear-brown fills carry the new checkbox cards, matching the de-redded system.

## Key Decisions

1. "All localized retailers" is brief-level, not a layers value. The backend composes one mark per image by design, so All expands the brief directions across the existing retailer moods and the mark follows the most-recent checked retailer — the same rule as today. Rejected: multi-mark compose (contradicts the contract) and a fake "all" slug (the resolver would drop it to None).
2. One control per concept, sync bridge deleted. Each checkbox card carries `data-theme` + `data-brief` (+ layer meaning for retailer/partner/product); checking it adds the brief clause AND drives the layer value through the existing `__activeDirections`/`__activeTheme` machinery (most-recent wins). `syncLayersFromChips`/`syncChipsFromLayers` and the standalone mark flags are deleted; every consumer in the Context list is migrated to the checkbox query. Rejected: keeping pills (user ruled them out) and keeping both controls with a preserved sync (the duality is the entire risk — choosing already implies the layer in both directions, so the second control carries zero information).
3. Albertsons ships as brief-text only, flagged as a backend follow-up (add a scene mood key), never as a silent omission.
4. The caveat becomes "(months unverified)" plus a one-line legend near the season readout; the research fan-out runs NOW (not at campaign time) and fills what the web can confirm. Entries the web cannot confirm keep an honest fallback, never a guess.
5. Background enrichment reuses house tokens (kraft gradients, wood grain, top-light) at low alpha; reduced-motion guards stay.
6. About art goes flush (`margin:0` both sides), peaks redrawn ~15% shorter in path data, section caps reduced via the shared spacing tokens so every section benefits equally.

## Recommended Approach

One UI agent does the selector + background + art work sequentially (all three touch `index.html`/`components.css`, so one writer, two commits); six read-only region research agents gather farmers-market names/URLs and harvest months in parallel; one integration agent applies research to `data-core.js`, rewords caveats, regenerates both backend JSONs, and updates tests. I verify, then ship through the standard chain.

## Work Plan

- Unit 1 — selector unification (markup + CSS + state migration + test updates). Partner pill+flag merge to one checkbox with inline mark preview; retailer trio as checkboxes (mark = any-checked, value = most-recent) + All option driving brief directions; what-to-make and angle clusters converted to styled checkbox cards; artifact copy deleted; sync functions deleted; all 7 consumer files migrated to the checkbox query; `__selectedLayers`/`__activeRetailerValue` semantics preserved. Commit separately.
- Unit 2 — background + art (CSS + SVG path data). Layered background, flush about art, shorter peaks, reduced section caps. Commit separately.
- Unit 3a — research fan-out (6 read-only agents: West, Mountain, South-Central, Southeast, Midwest, Northeast; ~11 towns each). Each returns town → {farmers-market name + URL, item → month windows} with sources; unconfirmable stays unconfirmed.
- Unit 3b — integration (applies research to `featuredFrontierDetail`, rewords residual caveats, runs builder for both JSONs, updates affected pins). Equivalence check on `layers{}` before/after.
- Unit 4 — verify + ship. Vitest full, pytest mapping/flavor/locales suites, builder `--check`, desktop + 390px renders, bump/commit/push/deploy/curl.

## Validation Plan

- `npx vitest run` — 126+ pass, including updated scope-cluster pins (slugs preserved on checkboxes, sync-function pins removed, zero `.ff-chip[data-theme]` references remain outside asset store facets) and a layers-equivalence test (brief+layers output for each concept before/after identical; All-retailers brief text; retailer switch; restore-path re-check).
- `python3 -m pytest tests/test_market_featured_frontiers.py tests/test_locales.py tests/test_local_flavor.py` green; `scripts/build-frontier-mapping.py --check` clean.
- Headless render past the gate: partner row is one control, retailer row is three checkboxes, artifact copy absent, background layered with no banding, about art flush with unclipped peaks, 390px zero spill, zero page errors.
- Live: curl new selectors + version stamp agreement post-invalidation.

## Risks / Rollback

- Risk: a consumer migration misses a chip query (7 files). Mitigation: the Context list names every one; a repo-wide grep for `.ff-chip[data-theme]`, `aria-pressed`, `__activeTheme` outside asset store facets must come back clean; equivalence matrix + restore-path probe gate it. Rollback: revert Unit 1 commit (Unit 2 is independent CSS/SVG).
- Risk: research returns guesses dressed as facts. Mitigation: agents must cite a source URL per month window; integration keeps the unverified fallback wherever sources fail; builder asserts no sharing, tests assert month ranges.
- Risk: background layering bands on wide screens. Mitigation: low-alpha token gradients only; screenshot proof at 1600px before ship.

## Open Questions

None — contracts, copy targets, art geometry, and research scope are all grounded above. Albertsons scene mood is logged as backend follow-up, not a blocker.

Saved at `/home/bryanchasko/code/chasko-labs/creative-automation-pipeline/docs/plans/2026-09-09-unify-selectors-caveats-art.md`.
