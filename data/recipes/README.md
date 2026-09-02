# KPI Recipe Database

Baseline recipes Kodiak can localize across the frontier. 23 baselines from your list plus site-verified (345 recipe pages in raw-ingest). Each entry has a Kodiak product, a base formula, and localization slots for regional peppers and cheeses.

## Green chile star
See `flapjacks-buttermilk`, `protein-biscuits`, `savory-waffles`, `cornbread-substitute`, `bagels` — each carries Las Cruces NM Target example: Hatch green chile + Oaxaca, message Green chile meets grizzly. Build that green chile flapjacks campaign to flex pipeline localization chops.

## How campaigns consume
Brief picks `product` + `region` (e.g., US-SW-LASCRUCES) + `peppers` + `cheeses` → pipeline embeds via Nova multimodal, retrieves past wins for that market, composes 1x1/9x16/16x9 with bear at 24,24. Data lives vectorized at `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/recipes/` as training data, queryable via API `GET /search?q=green chile`.
