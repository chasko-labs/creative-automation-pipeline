# Procedural Naming and Writing Standards — KODIAK® Frontier System

> How we name every file, every variant, and every line so the 100th local ad is as findable as the first. Plain language for marketing teams. No short forms in this doc — every rule writes its full words. Technical checks run by the pipeline enforce these rules automatically (see `src/creative_automation/compliance.py` and `src/creative_automation/token_loader.py`).

Every ad variant must pass procedural checks before it reaches the store phone book. Short forms are band in docs. Brand names are always written with their registered marks. Slogans carry their fixed punctuation.

---

## 1. Brand Names — Always Written With Registration, Never Shortened

The bear protects real food. Write the names exactly like this, every time — in idea sheets, ad headlines, photo captions, file names, folder names, and store lists:

- **KODIAK®** — the master brand. Use when talking about the family, the promise, the frontier. Example: "KODIAK® keeps the grain whole."
- **KODIAK CAKES®** — the company and the product family in consumer facing copy. Example: "KODIAK CAKES® Buttermilk Power Cakes." Do not shorten to "Kodiak" without the mark in any headline that leaves the building.
- **KODIAK POWER CUPS®** — the cup line. Always two words after the brand, always with the mark, always capitalized. Example: "KODIAK POWER CUPS® Chocolate Chip Oat." Do not write "power cups" lower case, do not drop the mark, do not separate "Power Cups" from KODIAK.

Enforcement: The compliance checker scans headline text for bare `Kodiak` and `Power Cups` without ® and flags them as style failures (same level as missing bear logo). The style tokens at `design/tokens/kodiak.json` under `kodiak.brand.names` carry the canonical spellings. Any brief that submits a headline missing the mark gets a preview badge in `report.json` that says brand presentation — not a pass. Correct and rerun.

Why the extra care: KODIAK, KODIAK CAKES, and KODIAK POWER CUPS are registered brand names. Consistent presentation is what keeps the brown box with the growling bear recognizable from the shelf to the story frame.

---

## 2. Slogans and Taglines — Fixed Words, Fixed Punctuation

Use exactly as written. Do not paraphrase, do not swap words, do not change order. These are the only two taglines approved for external creative:

- **"Feeding Epic Days & Wilder Lives"** — capital F, E, D, W, L, ampersand between Days and Wilder, no period at the end. Example: `Feeding Epic Days & Wilder Lives` centered under the product name on packaging and on seasonal sprints.
- **"Nourishment for Today's Frontier"** — capital N and F, apostrophe in Today's, no extra comma. Example: "Nourishment for Today's Frontier" in the footer alongside `KODIAK® • kodiakcakes.com • Keep It Wild` or as the subhead when the headline is product forward like "Green chile meets grizzly — protein flapjacks for your Las Cruces frontier."

Any ad that rewrites these (for example "Feed Epic Days" or "Nourishment for Todays Frontier" without the apostrophe) fails the brand check until corrected.

---

## 3. Logos and Visual Symbols — The KODIAK Bear Silhouette and Packaging Design Features

- **The KODIAK Bear silhouette logo** — the growling bear alone or the bear and the KODIAK wordmark together in slab type. Files live at `input_assets/brand/logo.png` and mirror to cloud storage `brands/kodiak/logos/kodiak-bear.png` (+ svg). Wordmark alone without the bear is not a substitute on social ads.
- **Product packaging design features** — the brown kraft box with the growling bear, the warm orange 8-point bar at the bottom, the parchment swatch #FFF8F0 as the page ground, and the slab headline type. These are the visual symbols marketing will recognize as the brown box in thumbnail. Every rendered ad must carry them — checked by `docs/training-process.md` Nova multimodal embeddings that know what the brown box looks like by meaning.

Clear space, size, reversal, and prohibited handling are documented in `docs/kodiak-style-guide.md` section 2 (clear space 0.25× width, size 24,24 offset, minimum 32 by 80, reversal only on Bear Brown / Frontier Green / Ink / Black). Any ad with a stretched, rotated, color-locked, or busy-background bear without scrim is a brand style failure.

---

## 4. File and Folder Naming — So the Hundredth Local Ad Is Findable (International Write Date)

We scale to hundreds of localities — Las Cruces NM Target was only one example of one place. To keep that scale searchable under international date standards, we use one pattern for every variant that lands on disk, in cloud storage, and in the training table:

```
KODIAK-CAKES-{PRODUCT}-{REGION}-{LOCALITY}-{CHANNEL}-{RATIO}-{DATE}-{VERSION}
```

- **PRODUCT** — from the recipe database `data/recipes/kodiak-recipes.json` — exactly `power-cakes`, `protein-biscuits`, `savory-waffles`, `muffin`, `granola-bar`, etc. Lower case, hyphen between words, no spaces.
- **REGION** — two letters for country plus state or province plus market — for example `US-NM`, `US-TX`, `US-SW-LASCRUCES`, `FR-IDF`. Always upper case with hyphens.
- **LOCALITY** — city and store cluster written without spaces — for example `las-cruces-target`, `alamogordo-walmart-albertsons`, `alamogordo+las-cruces-green-chile`, `park-city-wasatch`, `brooklyn-navy-yard`. Lower case, hyphen delimited.
- **CHANNEL** — where the ad runs — for example `instagram`, `facebook`, `display`, `diner-board`, `table-tent`, `subscription-email`, `in-store-endcap`. Lower case.
- **RATIO** — exactly `1x1`, `9x16`, or `16x9` (not `1:1`). The `x` matches the canvas dimensions in `kodiak.dimension.canvas` at 1080×1080, 1080×1920, 1920×1080.
- **DATE** — eight digits, year first: `YYYYMMDD` per `ISO 8601` date format — for example `20250902` for September 2, 2026. Never `MM-DD-YY`.
- **VERSION** — `v01`, `v02` ... zero padded — for re-renders of the same place.

Example full name for the green chile story you named as one local case among hundreds:

```
KODIAK-CAKES-savory-waffles-US-NM-las-cruces-target-instagram-9x16-20250902-v01.png
KODIAK-CAKES-power-cakes-US-NM-las-cruces-target-instagram-1x1-20250902-v01.png
KODIAK-CAKES-protein-biscuits-US-NM-alamogordo-diner-board-16x9-20250902-v01.png
```

This pattern is enforced when the pipeline writes to cloud storage — `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/renders/{product}/{ratio}/{PRODUCT}_{RATIO}.png` is the machine layout, and the human `KODIAK-CAKES-...` name is stored alongside it in `report.jsonl` as `human_name`. Both contain the same 7 parts.

Headers inside files also carry international writing: dates as `YYYY-MM-DD`, times as `HH:MM:SS` with `Z` for coordinated universal time, numbers with thousands commas per `ISO 8000` style, language tags as `en-US`, `fr-FR` under `BCP 47` (not naked `en`).

---

## 5. How We Proceduralize the Scale to Hundreds — The Same 7 Fields Every Time

No locality is special. Las Cruces green chile was one variant type among hundreds — the system treats Brooklyn Navy Yard, Austin, Miami, and Park City the same way.

Every locality gets one row in `data/localization/localization-training-data.jsonl` plus the vector copy at `s3://.../brands/kodiak/vectors/` and the lookup row at `kodiak-creatives-localization-memory` with these seven fields — in this order, spelled this way:

1. `market` — upper case — for example `US-SW-LASCRUCES`
2. `place` — `Las Cruces + Alamogordo, New Mexico`
3. `retailer` — `Target, Walmart, Albertsons` plus small independents and `diner on US-70`
4. `audience` — plain words — for example `Green chile families 28-45`
5. `message` — the single line with brand names enforced — for example `"KODIAK® Green chile meets grizzly — protein flapjacks for your Las Cruces frontier. Feeding Epic Days & Wilder Lives"`
6. `peppers` — regional pepper — for example `Hatch green chile roasted, diced`
7. `cheeses` — regional cheese — for example `Oaxaca crumble`

Add the peppers and cheeses from `data/recipes/kodiak-recipes.json` — savory waffles carry `Hatch green chile (Las Cruces), jalapeño (Austin), chipotle (Miami), poblano (Albuquerque)` plus `cheddar, pepper jack, oaxaca, cotija, gruyère`. Bagels, cornbread, chicken strips, protein biscuits, pizza crust all do the same. When Maya picks Las Cruces, the assistant searches `search("green chile flapjacks")` and returns the prior row by meaning, and Nova rewrites the line so the next Las Cruces ad already sounds like Las Cruces.

The background agents at `scripts/embed-reference-library.py` run `amazon.nova-2-multimodal-embeddings-v1:0` at 1024 numbers over design, reference, and training piles nightly — same file shape whether it was design green or a real photo already in cloud storage.

---

## 6. Who Checks This — Procedural Enforcement, Not Tribal Memory

- **At write time:** `src/creative_automation/compliance.py` flags bare `Kodiak` without ®, missing slogan punctuation, logo clear space breach, or busy-background bear without scrim.
- **At render time:** `src/creative_automation/pipeline.py:_write_preview` stamps `KODIAK® • kodiakcakes.com • Keep It Wild` in the footer — trademark present on every scale.
- **At vector time:** `scripts/embed-reference-library.py` records exact model `amazon.nova-2-multimodal-embeddings-v1:0` and dimension `1024` in `data/vectors/manifest.json` so a mismatched index fails fast.
- **At deploy time:** `CONTRIBUTING.md` requires a pull request under 500 lines with place, store group, and the line you want to try — labeled with persona `brand`, `field`, or `media` — plus three screenshots (one per ratio) so marketing reviews words and engineering reviews logic. Human docs must be updated if you touched the experience.

Every new locality — from Las Cruces to the next hundred you add — follows these seven fields, this file pattern, and this mark check. That is how the system scales without drift.
