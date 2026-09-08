## Goal

Make a picked past asset actually drive the campaign. Today picking anything in Browse-past-assets (e.g. apple stack cake) plus Create returns the default buttermilk box with no trace of the pick — the pick never leaves the browser. After this plan, a staged DAM asset rides into the request as the seed, provenance names it, the empty pre-generate carousel stops rendering hollow squares, and Park City default behavior is confirmed as designed (no action).

## Success Criteria

- Stage a DAM asset, hit Create: the response provenance carries `seed_selection: staged-dam-asset` plus the asset key, and the render is visibly derived from the staged photo (not the buttermilk default).
- Stage nothing, hit Create: byte-identical behavior to today (default slug, current ladder, no new keys required).
- Staged-asset fetch fails (bad key, S3 denied): silent fallback to current seed resolution; rung never fails, 503 still unreachable.
- Fresh page load shows no hollow carousel squares; the carousel renders only once renders exist, with downloads working as today.
- Riff chip with no staged asset: generation proceeds normally with a visible non-blocking cue to pick a past asset; nothing is silently substituted.

## Context And Current Facts

- DAM picks never reach the request. `selectedProducts` (`generate.js:267`) reads only `#productChooser .sku-check:checked`; DAM picks go through `chooseTile` → `stageDamAsset` (prompt-chips.js) into the staging tray/brief text. With no SKU checked, `primarySlug` falls to `DEFAULT_MAPPED_SLUG = buttermilk-power-cakes-flapjack-waffle-mix` (generate.js:325) — the designed fast default, executed on the wrong input. That is the entire apple-stack-cake mystery: the backend never saw it.
- Backend has no staged-asset input. `generate_hero` seed order is theme photo → sku-mapped DAM photo → disk probe (generate.py seed block); nothing reads a caller-supplied DAM key. `fetch_dam_key` already exists for exactly this fetch.
- Riff chip (`data-theme="riff-on-past-content"`, index.html:217) is a label with no retrieval behind it (established in the studio-ceiling plan as Unit 4, unbuilt). An unknown theme misses `_resolve_theme_photo` and falls through harmlessly.
- Empty carousel: 3 hollow `.ff-carousel-slot` divs render pre-generate (verified live DOM + screenshot 2026-09-08); the populated post-generate carousel with per-asset downloads already works (PR #180 e2e, do not regress).
- Park City: the "— Park City default" provenance label the user saw IS the shipped El Paso fix working as designed. No action; recorded so nobody re-opens it.
- Live headline on the user's render ("Bulk Up: Family-Sized Adventure Fuel!") is Title Case with no trailing period — the 0.1.038 grounded-director normalize path working in production.

## Constraints And Non-goals

- PR-only, harness-green, version-bump deploy per repo rules; never --no-verify without explicit operator permission.
- No behavior change when no asset is staged; the never-503 contract holds; compose-fix invariant untouched (staged asset is a SEED photo, never a verbatim box — box pasting still only fires for mapped packshots).
- Non-goal: similarity retrieval over past renders (brief-embedding → nearest DAM render) needs a QueryVectors helper embeddings.py does not have — separate follow-up issue, not this PR.
- Non-goal: DAM thumbnail 400s, dupes, hash-labels (issue #189, separate); empty-carousel work must not touch the populated carousel download path.

## Key Decisions

1. Staged asset becomes the priority seed, not a product override. It does not touch packshot resolution, so unmapped picks (apple stack cake) take the generative ladder from their own photo instead of the buttermilk default. Rejected alternative: mapping picks into `product` — would corrupt packshot semantics and the compose-fix invariant.
2. Transport is a new optional request key (`seed_key`), not reuse of `product` or `theme`. Absent key = today's code path untouched.
3. Riff chip stays honest: with a staged asset it directs the seed (provenance `riff_on`); without one it generates normally plus a visible cue. Rejected: blocking Create or silently substituting the default.
4. Empty carousel slots are simply not rendered pre-results (container renders on first results), not restyled. Rejected: removing the carousel — post-generate downloads depend on it.

## Recommended Approach

One small PR, backend-first: add the `seed_key` input and priority seed resolution with provenance, then thread the staged key through the frontend request, gate the empty carousel on results, and cover all three with mocked tests. Smallest slice that makes a pick visible in pixels.

## Work Plan

1. Backend `seed_key` → priority seed (src/creative_automation/generate.py, generate_lambda.py): accept optional `seed_key` from the request body; after theme-photo resolution and before sku-mapped lookup, `fetch_dam_key(seed_key)` into the seed slot; on any failure log to stderr and continue current resolution. Provenance: `seed_selection: staged-dam-asset`, `seed_source: <key stem>`, plus `riff_on: <key>` when theme is riff-on-past-content. Assumption: staged key is a full DAM key (matches fetch_dam_key contract, no prefix join — same as the asset browser contract in dam.presign_get docstring).
2. Frontend threading (generate.js oneGenerate/campaign-sections.js full path, prompt-chips.js staging): include the staged asset key in the request body when a DAM asset is staged (read from the existing selectedKey/staging state — implementer wires the exact read, no new global if a DOM read suffices); non-blocking cue near the riff chip when riff is active with nothing staged; render the carousel container only when renders exist.
3. Tests: `seed_key` happy path (mocked fetch_dam_key → seed used, provenance keys set), fetch-failure fallback (mock raises → current behavior, rung intact), no-key regression (existing suite covers; conftest kill-switch posture unchanged). Update affected ladder/multisize expectations only if the priority seed alters them.
4. Docs line: pipeline.html DAM card gains one clause that staged picks seed the render (keeps the page honest; matches the #176-179 runbook standard).

## Validation Plan

- `ruff check` on touched files; `uv run pytest -q` on the ladder/generate/director test files, then full `uv run pytest -x -q` (suite baseline 465 green).
- Live (team runs, needs AWS): stage apple stack cake → Create → assert provenance `seed_selection == staged-dam-asset` and viewed pixels derived from the staged photo; no-key Create → provenance identical to today; bogus `seed_key` via curl → 200 with fallback seed, never 4xx/5xx.
- Live UI: fresh load shows zero hollow carousel slots; post-generate carousel + all four per-asset downloads intact; riff-without-asset shows the cue and still generates.
- Highest-risk check: the staged-key read on the frontend (tray state vs request body) — verify with the Network tab that `seed_key` actually ships, not just that the tray shows a chip.

## Risks / Rollback

- Staged key from another user's session or a stale presigned reference: fetch failure path covers it (log + fallback); keys are read per request, never cached server-side.
- Frontend/backend version skew (new frontend, old Lambda): `seed_key` is optional and ignored by old backends — safe to ship web first.
- Rollback: revert the single PR; kill-switch not needed since absent key = old behavior. Lambda redeploy returns to previous image; no data migration involved.

## Open Questions

None. Market default, thumbnail 400s, and similarity retrieval are all investigated and assigned elsewhere (above); every remaining choice is a workspace fact.
