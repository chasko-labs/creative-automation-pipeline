# Campaign pipeline is data-model driven, not hardwired

This is how the app turns **any** market × **any** of the 26 seasons × **any** free-text campaign idea + **any** of the 88 products into a slick campaign — responsively.

## The models (single sources of truth)

| Model | File | What it holds | How UI stays responsive |
|-------|------|---------------|--------------------------|
| Frontier pairs | `data/localization/retailer-frontier-pairs.json` (76+ pairs, schema `retailer-frontier-pairs.schema.json`) | `market` → `frontier_sister` (place, farmers_market_url), `monthly_ingredients` (12 months `2026-01`..`2026-12` per pair → 912 cells at last count), `seasonal_moments[]` (1427 moment objects, 276 distinct headers, each with `months[]`, `available_ingredients`, `favorite_flavors`, `note`) | Frontend does not `if (market === "Cincinnati")` — it does `KODIAK_FRONTIER_PAIRS.find(p => p.market === selectedMarket)` for **any** of the 76+ the UI lists. No hardwired market branches. |
| Market languages | `data/localization/market-languages.json` (79 markets, 237 variants) | `top_languages`, `auto_produce` | `market-languages.json` → `data-core.js` language chips, localized recipe i18n |
| Regional scoreboard | `data/localization/regional-scoreboard/regions/*.json` (78 regions, built via `scripts/build-regional-scoreboard.py` from `regional-scoreboard.schema.json`) | `city_center` (landmark/notes), `cultural_notes`, `design_palette`, `seasonal[].in_season_produce`, `landscape_motifs` (e.g., pawpaw trees, Wasatch aspen) | `places[].cue` in `web/kodiak-posts-for-todays-frontier/js/data-core.js` is **generated** from these regions + the frontier pair's `cue` — e.g., `US-OH-CINCINNATI` cue `Brick market halls, humid river valley — trillium and bluebells spring, coneflower summer, aster and goldenrod fall; Findlay Market ramps and morels, September pawpaws, black walnuts in December` comes from the Cincinnati region's `landscape_motifs` + `seasonal` produce, not a string in code. |
| Plant ecology | `regional-scoreboard` `landscape_motifs`/`seasonal` + `retailer-frontier-pairs` `seasonal_moments[].note` | e.g., `trillium`/`bluebells`/`coneflower`/`aster`/`goldenrod` for humid river valley, `aspen gold` for Park City, `pawpaw`/`tropical custard` | This is the visual ecology that helps the image prompt — it is **not** a code constant, it is the `cue` + `seasonal` produce that the frontend threads into the Bedrock prompt. Seasonal moments **supplement** `monthly_ingredients`, they do not override it: `monthly_ingredients["2026-09"]` is the source for `in-season: pawpaws`; the moment's `favorite_flavors: ["pawpaw","tropical custard"]` and `landscape_motifs` add `pawpaw trees + Findlay Market` to make it stunning. If we made the moment override the ingredient, September would show `pumpkin spice` instead of `pawpaw` — we keep the ingredient from the monthly grid and append the moment's flavors. |
| Platform matrix | `data/platforms/platform-matrix.json` | 5 ratios → `1x1`, `4x5`, `9x16`, `16x9`, `blog` (1200×630) | `platform-matrix.json` → `generate.js` `showRenderSet` fans to all 5, `extendTallTiles` fills tall. No hardwired ratio. |
| Products | `data/products/kodiak-full-catalog.json` (88 SKUs) | `slug`, `product_image` DAM key | `catalog` → `generate.js` product picker, `DEFAULT_MAPPED_SLUG` only when explicit `product_image` layer checked. |
| Recipes | `data/recipes/kodiak-recipes.json` + `web/.../js/recipe-cards-data.js` (pairs×26 variants — 76×26=1976 at last count, built via `src/creative_automation/recipe_cards_emit.py`) | `featured_for` curation → recipe card per market×season | `recipe-cards-data.js` is **baked** deterministically from the frontier file via `recipe_cards_emit.py` (with `recipe_card.py` resilient qualifier-strip), not hand-edited. Ingredients are **not** regenerated per preview — we respin seeded `featured_for` in production. |

## How a preview stays responsive

1. **Before you hit Create Campaign Preview** — the 5 sizes (`1x1`, `4x5`, `9x16`, `16x9`, `blog`) are **prepopulated from seeded data**, not generated:
   - `recipe-cards-data.js` gives the market×season recipe card (e.g., `Cincinnati September → pawpaws`)
   - `season-flavors.js` + `data-core.js` `places[].cue` gives the ecology/flavor line (`Findlay Market ramps and morels, September pawpaws… trillium and bluebells…`)
   - `market-languages.json` gives the language chips
   No network, no Bedrock yet — instant, deterministic, pairs×26 coverage.

2. **After you hit Create Campaign Preview** — things whirr to life, **real-time per click**:
   - Frontend builds `briefForBedrock = market · season · frontier: Place — Moment · in-season: ingredient (favorite_flavors)` from the data models above (now with `favorite_flavors` threaded from the moment, not just zip/month)
   - `POST /generate` → `src/creative_automation/generate.py` `_default_scene_prompt(brief_msg, …)` keeps that frontier-aware brief verbatim (so `pawpaw, tropical custard, Findlay Market, Lebanon orchard` reaches Stability even when Nova is down) + `_nova_pro_scene_prompt` via Bedrock Converse (`bedrock:nova-pro`) for the social image
   - Each of the 5 ratios is a **fresh Bedrock call** with the same frontier-aware prompt but ratio-specific composition (the `s3_uri` is content-hashed from prompt+market, so September pawpaws `…89ebf99e…` ≠ Halloween apples `…5048493d…` ≠ Dayton tomatoes `…161a49ee…` — verified live on `kodiak-dev` `bedrock:nova-pro` with distinct `s3_uri`s, not the repeated same packshot).

## Why you only saw test markets mentioned

The durable test `tests/test_campaign_preview_standard.py` previously spot-checked 3 markets (`US-OH-CINCINNATI`, `US-OH-DAYTON`, `US-CA-OCEANSIDE`) with hardcoded expected ingredients, which looked like hardwiring. It now loops **all pairs×26** via the schema (`frontierPairs.length >= 76` → 76×26=1976 campaign variants at last count, 12 monthly cells per market, every September has an ingredient, every September moment that exists carries `favorite_flavors`) and samples 5 markets spread across the file (`[0, len/4, len/2, 3*len/4, len-1]`) to prove responsiveness without naming a single market in the logic.

No code branch is `if market === "Cincinnati"`. Every market/season works because every market/season is in the data file and the UI reads that file.
