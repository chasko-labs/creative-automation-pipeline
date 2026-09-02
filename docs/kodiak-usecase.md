# kodiak as use case — american founded/run, local footprint

why kodiak: park city ut 1982 joel clark red wagon -> 1995 incorporation -> 2014 shark tank $3.6m-> $6.7m -> #1 at target beating aunt jemima by 20% -> 26k doors (target/walmart/costco/publix/safeway) -> 2021 l catterton majority. bain insurgent since 2016, scale insurgent pattern (now mature). portfolio fan-out (power cakes, bear bites, oatmeal cups, frozen waffles, bars) strains any style guide — growth amplifies structural gaps.

pipeline maps local footprint without leaving us:
- brief `target_market: US-MW` (midwest mountain) vs `US-SE` (publix southeast) — same campaign, different retailer/region creative
- dam: `power-cakes/hero.png` reused (real shoot), `bear-bites` + `oatmeal-cup` generated via nova canvas (mock now, bedrock when creds)
- 3 ratios per product x 2 regions = 18 creatives, each with kodiak palette #3B2316/#E8530E/#1A3C34 + bear logo overlay + "protein-packed" claim gated (avoid 17% class action repeat)
- local proof: keep it wild with vital ground foundation + zac efron — wild/frontier narrative localizes per corridor (wasatch ski vs southeast family breakfast)

run:
```
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak
open output_kodiak/preview.html
# se variant:
uv run python -m creative_automation.cli --brief briefs/kodiak-se.yaml --assets input_assets --out output_kodiak_se
```

outputs verified: 9 + 9 creatives, 9/9 pass each, hero_source dam for power-cakes, mock for other 2, regions US-MW vs US-SE distinct in report.jsonl for bi loop per dma/retailer.

next beat: retailer-specific pack for publix (southeast family) vs target (gen z health) vs costco (bulk family) — same brief, different message tweaks.
