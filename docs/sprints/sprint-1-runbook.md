# Sprint runbook — shipped items at `9332fab` (2026-09-20)

One operate/verify/recover line-set per shipped sprint item. All commands run
from the repo root, offline unless marked LIVE. Source of truth is the code +
tests named per item, not this file.

## 1. staged-asset store seed_key end-to-end

- Operate: pass `seed_key: brands/kodiak/renders/<past-hero>.png` in the
  `/generate` preview or full request; the handler forwards it verbatim to
  `generate_hero` / `generate_hero_set` (`src/creative_automation/generate_lambda.py`).
- Verify: `python3 -m pytest tests/test_staged_seed_key.py -q`; response
  provenance carries `seed_selection: staged-dam-asset`.
- Recover: a dead staged pick falls through to the normal seed path with
  HTTP 200 — never 503. If you see 503 on preview, the regression is in the
  handler, not the asset store.

## 2. campaign carousel + riff cue

- Operate: `renderCampaignCarousel(renders, source)` in
  `web/kodiak-posts-for-todays-frontier/js/campaign-sections.js` mounts the
  `#campaignAssetsCarousel` container only when renders with `image_url`
  exist; reset removes the container instead of leaving an emptied shell.
- Verify: `npx vitest run tests/vitest/carousel-riff-cue.test.mjs`.
- Recover: hollow `ff-carousel-slot` shells or a cue written to a hidden
  dialog node means the on-demand mount regressed — check the
  `image_url` filter first.

## 3. engine-key contract + origin field

- Operate: every `generate_hero` envelope carries `engine` in
  `{packshot-composite (A), stability-restyle (B), pillow-compose (C),
  brand-floor (D)}` and `origin: "backend"`, including the wall-timeout
  floor envelope in `generate_lambda.py`.
- Verify: `python3 -m pytest tests/test_engine_origin.py -q` and
  `npx vitest run tests/vitest/engine-origin.test.mjs` — backend and
  frontend keys must match exactly.
- Recover: a new engine key anywhere must be added to BOTH sides plus both
  suites; frontend rendering an unknown engine badge is the tripwire.

## 4. dHash similarity gate + scene-prompt provenance

- Operate: rung B output is gated by `dhash64` Hamming distance against the
  seed; threshold is `SIMILARITY_GATE_THRESHOLD`
  (`src/creative_automation/generate.py`, default `8`, env
  `KODIAK_SIMILARITY_THRESHOLD`). Provenance records the verdict +
  `scene_prompt` source.
- Verify: `python3 -m pytest tests/test_similarity_gate.py -q`.
- Recover: good renders failing the gate = threshold miscalibration —
  recalibrate on staged renders (`brands/kodiak/renders/`), never just
  raise the number; the suite pins far-pair distance above threshold.

## 5. multi-theme combination

- Operate: `combine_themes([primary, ...extras])` in `generate.py` — the
  primary drives seed + scene, extras layer on as overlay marks (retailer
  extras: mark-only, `scene == ""`, never pixel text) and copy-sidecar
  framing lines. Unknown themes raise `panel_flag`
  (`theme-mismatch: unknown theme(s): ...`), never an exception.
- Verify: `python3 -m pytest tests/test_theme_combo.py tests/test_theme_asset_map.py -q`.
- Recover: a theme that changes pixels instead of layering means a retailer
  slug leaked into `_THEME_SCENE_HINT` — see item 8, defect 1.

## 6. brand_copy source + fallback injection

- Operate: `src/creative_automation/brand_copy.py` is the single source of
  truth for fallback voice (taglines `Feeding Epic Days & Wilder Lives` /
  `Nourishment for Today's Frontier` / `Keep It Wild`, ascii `Kodiak Cakes`,
  approved claims, prohibited-claim hints). `platform_copy` fallback frames
  read from here; generated/social copy uses ascii naming because models
  garble (R) glyphs — registered forms stay on locked surfaces (packaging,
  logo lockups, pipeline footer stamp).
- Verify: `python3 -m pytest tests/test_brand_copy.py tests/test_atlanta_copy_law.py -q`.
- Recover: bare `KODIAK` or a (R) artifact in fallback copy = the
  `clean_brand_copy` normalization path regressed; check the frame source,
  not each call site.

## 7. season pairing

- Operate: `src/creative_automation/season_pairing.py` pairs a STRUCTURED
  `season` request field to a curated recipe (`SEASON_RECIPE_PAIRINGS`;
  static `DEFAULT_PAIRING` apple-cinnamon-compote otherwise). Free brief
  text is display-only and never inspected — a season word in marketing
  copy cannot hijack the pairing.
- Verify: `python3 -m pytest tests/test_season_pairing.py tests/test_recipe_season.py tests/test_season_dedupe.py -q`.
- Recover: wrong-season card = check the structured `season` field reached
  the pairing call; off-season copy words are innocent by design.

## 8. retailer overlay wiring (asset-store-first)

- Operate: overlay marks resolve asset-store-first
  (`brands/retailers/logos/<slug>.png`, mono variant `<slug>-mono.png` via
  `retailers.asset_key_for_retailer`) with repo-local
  `input_assets/retailer-logos/` raster fallback; missing marks resolve to
  `None` and the render ships clean. Composable marks: costco, publix,
  target, walmart. Retailer direction NEVER enters pixel prompts
  (`_THEME_SCENE_HINT` has no retailer entries) — direction ships as the
  composited mark + the copy-sidecar framing line.
- Verify: `python3 -m pytest tests/test_retailer_overlay.py tests/test_retailer_direction.py -q`.
- Recover: aisle/pack pseudo-text baked into pixels = scene-hint leak
  (defect 1); a missing mark on an overlay retailer = check asset key, then
  local fallback, then `RETAILER_LOGO_CACHE_DIR` (`/tmp/kodiak-assets/retailer-logos`).

## 8b. copy-only retailers — kroger / heb / whole-foods (TOOLKIT POINTERS)

These three stay COPY-ONLY: direction ships as the copy-sidecar
retailer-framing line only, never as pixels. `resolve_retailer_logo`
returns `None` for them even when a file is present (pinned by
`test_resolve_logo_copy_only_never_resolves_even_with_file`).

- Toolkit pointers (where the mark WILL resolve when files land — no code
  change needed, `asset_key_for_retailer` already computes them):
  - kroger → `brands/retailers/logos/kroger.png` (mono: `kroger-mono.png`)
  - heb → `brands/retailers/logos/heb.png` (mono: `heb-mono.png`)
  - whole-foods → `brands/retailers/logos/whole-foods.png` (mono: `whole-foods-mono.png`)
  - offline-dev fallback mirrors: `input_assets/retailer-logos/<slug>.png`
- Enablement (only with per-retailer co-marketing permission on file):
  drop the transparent PNG (lossless, ≥512px longest edge) at the asset key
  above, then move the slug from `COPY_ONLY_RETAILERS` to
  `OVERLAY_RETAILERS` in `src/creative_automation/retailers.py` with tests.
  Until then: no overlay, no pixel text — copy line only.
- Verify: `python3 -m pytest tests/test_retailer_overlay.py::test_resolve_logo_copy_only_never_resolves_even_with_file tests/test_retailer_direction.py -q`.

## 9. voice enablement receipts + wall budget

- Operate: art-director voice ships DARK (`KODIAK_ARTDIRECTOR_ENABLED`
  default false; `artDirectorPrewarm` Scheduler DISABLED). Wall composition:
  inner voice 6s < outer wall 22s; director retry worst-case sleep 2s ≤
  inner 6s; post-render voice collect 2s < inner 6s. A cold imported model
  needs minutes to warm — the in-request probe correctly misses cold and
  degrades voice-off; warmth is the pre-warm Scheduler's job, not the
  request path's.
- Verify: `python3 -m pytest tests/test_voice_flags.py -q`; live receipts
  in `docs/architecture/bedrock-invoke-receipts-2026-09-20.md` (Nova Pro
  1.35s, Stability 8.18s, voice 0.48s warm after cold miss).
- Recover: voice silently off in prod = check the flag AND the pre-warm
  Scheduler state; rollback is flag-off (pixels unaffected).
- LIVE cost note: Bedrock invokes bill to bryanchasko-kiro — keep probes
  minimal (`maxTokens: 32` Nova, 256px Stability seed) as in the receipts doc.

## 10. five-tile preview pads within the wall

- Operate: `generate_lambda` renders one 1x1 hero, then server-side Pillow
  cover-pads it to 4x5 / 9x16 / 16x9 / blog under the 22s
  `GENERATE_WALL_TIMEOUT_S` — zero extra model calls. Canvases:
  1x1 1080², 4x5 1080x1350, 9x16 1080x1920, 16x9 1920x1080; delivery order
  1x1-first; frontend `TILE_ORDER` (blog/1x1/16x9/4x5/9x16) in
  `js/frontier-contracts.js` = delivery ratios + static blog tile.
- Verify: `python3 -m pytest tests/test_render_ratios.py tests/test_render_contract.py tests/test_generate_lambda.py -q`.
- Recover: a missing tile = check `_PREVIEW_PAD_RATIOS`
  (`generate_lambda.py:66`) and the pad loop (~line 1076); a pad never fails the render — it is
  skipped, not fatal.

## 11. test rewrites + retailer-frontier-pairs dedupe

- Operate: `tests/test_season_dedupe.py` reads the source of truth
  (`data/localization/retailer-frontier-pairs.json` monthly maps, NOT the
  emitted JS) and fails on any repeated featured ingredient within a
  market year. Do not weaken the test — fix the data until it passes.
- Verify: `python3 -m pytest tests/test_season_dedupe.py tests/test_recipe_season.py tests/test_datapaths.py -q` — green at this commit
  (the 61-market / 249-repeat-cell backlog measured 2026-09-15 is fixed).
- Recover: new repeats = edit the monthly maps in the JSON source, then
  re-emit; never patch the emitted JS to hide them.
