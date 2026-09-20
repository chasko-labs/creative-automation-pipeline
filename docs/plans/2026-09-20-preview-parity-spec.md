# Campaign preview parity spec — expected behavior vs today

Date: 2026-09-20. Trigger: San Francisco / Halloween / Localized Costco run
produced a warehouse-aisle art dispatch, a grizzly-mountain hero under
fog-city copy, an unseasonal recipe, and 1 image where the placeholder shows 5.

## Big picture

The static placeholder shows 5 sizes with 3 localizations. "Create Campaign
Preview" must produce the same shape with generated pixels: same tile count,
same language count, same checked selections honored. Today it produces 1
hero, copy describing a different image, and dropped selections.

## Defect 1 — retailer direction draws the store

Decided: never draw the store. No warehouse, aisle, pallets, or retail
setting words in any pixel prompt. A retailer direction resolves to a logo
lockup overlay only.

Today: `_THEME_SCENE_HINT` (`src/creative_automation/generate.py:477-543`)
dispatches aisle scene text per retailer slug, folded into the restyle prompt
by `_default_scene_prompt` (`:1033`) and `_nova_pro_scene_prompt` (`:1060`),
via `_stability_control_hero` (`:2601`). The prompt also emits the malformed
"Featuring localized costco." Delete all of it.

Work: delete the retailer entries from `_THEME_SCENE_HINT` —
`localized-costco`, `localized-publix`, `localized-target`, bare `target`,
`walmart`, `whole-foods`, `publix`, `kroger`, `heb` (no bare `costco` exists;
`kodiak-subscription` at `:513` is not a retailer and stays); add
a retailer overlay resolver (slug -> mark asset + lockup geometry); gate it on
an explicit `retailer_logo` request layer, mirroring the `partner_logo` layer
at `generate.js:348`. Keep `_THEME_COPY_HINT` (`:555`) — retailer framing
stays in the copy sidecar.

## Defect 2 — restyle ignored seed and prompt

Expected: hero derives from the resolved seed. Provenance records which scene
prompt drove the call (Nova Pro output vs deterministic fallback). A
seed-similarity floor fails the render to rung C instead of shipping unrelated
pixels.

Today: seed `0272fd970269--2-09b132_e70c8e` (pulled from the DAM — a waffle-iron
photo, no bear, no mountains) plus an aisle restyle prompt at control 0.7
produced a grizzly on a log in the mountains. Seed resolution worked
(`seed_selection: theme-photo`); the pixels match neither seed nor prompt.

Narrowed: theme-photo seeds take a fast path (`:2562`) that skips Nova, so
the SF run used the deterministic default scene — forensics now point at
Stability dropping the conditioning (or a wrong control image), not a rogue
Nova scene. Confirm against the run log.

Work: record scene-prompt source in provenance on both branches (Nova output
vs default); add the similarity gate regardless.

## Defect 3 — multiple checked angles collapse to one, silently

Expected: every checked angle affects the output under a defined combination
rule, or the UI enforces single-select. Checked-but-ignored selections raise
a panel flag.

Today: the request carries exactly one `theme` key (`generate.js:1129`,
singular `data.get("theme")` server-side). The theme catalog itself is
multi-theme; the collapse is per-request — most-recently-checked wins
(`prompt-chips.js:167`), and the fan-out sends one themed request
(`generate.js:1103`). The run had retailer + grizzly + riff + ski-partner
checked; only `localized-costco` rode the request. The grizzly pixels did not
come from the checked grizzly angle (see defect 2).

Work: define combination semantics — one primary theme drives seed + scene;
additional angles map to overlay layers (partner mark already does this) or
copy lines; anything unmapped raises a flag on the existing mismatch path
(`generate.js:592`).

## Defect 4 — preview renders 1 size, placeholder shows 5

Expected: generated preview fills all 5 tiles (1x1, 4x5, 9x16, 16x9, blog)
with the same 3 localizations. Tile and language counts are contract.

Today: `_handle_preview` (`generate_lambda.py:1024`) renders one 1x1 hero and
marks the rest `deferred` to fit the 22s wall.

Work: pillow-pad the 1x1 into all 5 tiles server-side in preview mode (fits
the wall today); move outpaint into preview later behind a looser budget if
padded tiles degrade. `provenance.ratios` must list every shipped tile.

## Defect 5 — recipe ignores season

Expected: surfaced recipe is paired on market x season (Halloween SF →
pumpkin/apple, not egg bake).

Today: season leaks into the brief as plain text (`generate.js:633`) but
the request body carries no `season` key (`:1129`), and recipe selection never
reads it — `_recipe_card_defaults` (`generate.py:1680`) is product-only,
`_author_recipe_fields` (`:1730`) takes brief/region with no season parameter.

Work: add a structured `season` field to the generate request (strip the
brief-text leak or keep it as display only); frontend sends the active
season, the Nova prompt requires a season-appropriate dish, a season-indexed
pairing table covers the offline/default path with the static product default
as last resort. Record the pairing reason in provenance next to the title.

## Verification

- Repro: SF Bay Area / Halloween / Localized Costco + grizzly + ski angles,
  Create Campaign Preview; assert 5 tiles, 3 localizations, logo overlay
  present, zero aisle pixels, season-tagged recipe.
- Suites: `tests/test_asset_pack.py`, `tests/vitest/` (no breaks expected
  in the 4 files checked: theme-asset-map, season-flavors, frontier-contracts,
  asset-pack), plus 4 new suites: retailer-direction (scene-hint deletion +
  overlay resolution), generate-lambda preview-1x1 tile count, recipe-author
  season param, render-contract ratios.
