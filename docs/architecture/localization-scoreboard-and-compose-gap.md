# localization scoreboard + composed-preview gap notes

> cross-team contribution from the tooling side. part 1 documents three concrete gaps observed in a live composed-preview run so the pipeline team has a reproducible starting point. part 2 proposes a per-region "scoreboard" data standard that fixes the regional-flair gap and unifies the fragmented localization files. reference data (schema + 7 seeded regions) already exists in a companion tooling repo and is offered for adoption — it does not live in this repo yet. framed as observations, not blame.

## part 1 — the compose gap (diagnosed from a live preview)

a real preview run — las cruces + alamogordo, june, blueberry / chocolate-fudge / banana muffin SKUs — produced three "nova pro composed hero" images. all three shared the same shortfall: the composed asset was a generic hero with none of the local, retailer, or product signal that the input data actually carried. concretely:

- no regional flair — no adobe, no organ mountains, no green-chile cue. the output reads as a generic muffin hero that could be any market.
- no retailer context — nothing in the frame ties the asset to the retailer for that market, even though retailer is known per market.
- no product image — the SKU packshot does not appear in the composed asset. the hero references the SKU by name/text only.

these are three separable gaps. observations below, each with a recommendation.

### gap 1 — product-image embedding

the composed hero references the selected SKU by name/text but does not appear to composite the real product packshot into the frame. the DAM holds roughly 200 real `705599*` packshots that are clean-background — close to ideal for compositing.

recommendation: `compose.py` pulls the DAM packshot for the selected SKU and composites it into the hero rather than relying on the generator to hallucinate a product. clean-background packshots make this a straight composite step, not a generative one.

### gap 2 — regional flair

the composed output is not consuming any region design layer because none exists in the data yet (see part 2). today the region cue is a single string. there is no textures / colors / building-materials input for the generator or compositor to condition on, so "las cruces in june" and "anywhere in june" produce the same frame.

recommendation: introduce a per-region visual layer (the `design_palette` in part 2) and feed it into the compose/generate step as structured input, distinct from the fixed brand palette.

### gap 3 — retailer context

no retailer lockup is embedded in the composed asset despite retailer being known per market.

recommendation: embed the retailer lockup for the market's retailer during compose, sourced from the same per-region record proposed in part 2 (`retailers[]`).

## part 2 — the proposed regional automation scoreboard (fix for gap 2)

a unified per-region "scoreboard" schema has been designed to replace the fragmented localization inputs with one record per region. rather than reproduce the full schema here, the concept: today the localization signal is spread across `localization-table-seed`, `market-languages`, `local-flavor`, `retailer-frontier-pairs`, and `frontier-gaps`. the scoreboard folds all of that into a single record per region covering:

- `city_center` and `featured_frontier`
- `languages` + `cultural_notes`
- `design_palette` — `textures`, `colors` (with hex), `building_materials`, `landscape_motifs`. this is the region visual layer, distinct from the fixed brand palette. this is the input gap 2 is missing.
- `seasonal[]` keyed by holiday-season, each with `in_season_produce` + `where_to_buy`
- `retailers[]`
- `campaign_type_fit` scored across the 7 canonical campaign types: recipe-cards, localized-costco, riff-on-past-content, zac-efron, bears, keep-it-wild, us-ski-and-snowboard

### where the reference data lives today

the schema plus 7 fully-seeded example regions were authored in a companion tooling repo at `heraldstack-mcp/tools/kodiak-scoreboard/` as reference data the pipeline team can adopt. the seeded regions: park city, las cruces, albuquerque, seattle, southeast/publix, pescadero, neah bay — 6 ready-to-rock, neah bay consent-gated. these do not live in this pipeline repo; they are offered for adoption.

### recommended pipeline home

- `data/localization/regional-scoreboard.json`, keyed by `market_code`, validated by the schema.
- a builder that composes the existing 6 fragment files into the scoreboard record and flags per-field readiness.
- `local_flavor_for()` and the brief flow stay intact — the scoreboard is an additive data layer, not a rewrite of the brief path.

### two systemic non-data gaps

these are not fixed by data alone:

- us-ski-and-snowboard has no brief scaffold. park city is the default demo market for it. recommendation: add `briefs/kodiak-us-ski.yaml`.
- the localized-costco brief has no publix-heartland variant. a variant would serve the southeast market.

### brand-fit caveat on color

all `design_palette` hex values are perceptual approximations and are flagged for brand-fit review. region color must never fight the fixed kodiak brand palette (bearBrown / blazeOrange / frontierGreen / parchment / oatmeal). treat region hex as a candidate accent set pending review, not a committed value.
