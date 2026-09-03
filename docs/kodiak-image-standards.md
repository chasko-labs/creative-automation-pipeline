# kodiak image standards — derived from the real nova vectors

match before jazz. this spec is built from clustering 3048 real image embeddings (`amazon.nova-2-multimodal-embeddings-v1:0`, 1024-dim), not from assumptions about the brand.

honesty gate up front: vectors carry no pixels. every standard below is metadata-informed — cluster cohesion (how tightly nova groups the images) plus the metadata that co-occurs inside each cluster. no claim here is a pixel measurement. confidence levels are attached to every inferred visual pattern.

## findings

- clustered 3048 image vectors into 12 visual groups by cosine similarity (spherical k-means, numpy-only, deterministic seed)
- channel population: catalog 2332, blog 644, amazon 46, instagram 25, tiktok 1
- in-image-text: 644 rows explicitly flagged `in_image_text=false`, 0 flagged true, 2404 rows do not carry the field. the false flags are all on the 644 blog rows — those are the rows the ingest pipeline evaluated for baked-in text, and every one came back clean (confidence high for blog; the catalog/amazon/social rows are unlabeled, so no-text there is inferred from the product-shot nature of the source, confidence medium)
- the catalog channel dominates (2332 of 3048); these are packaging/product renders whose caption+product fields are filename-derived, so their text signal is weak and clustering leans almost entirely on the nova vector geometry
- blog + instagram rows carry real human text (captions, recipe titles, tags, alt text, hashtags) — that is where subject/composition terms are trustworthy

## clusters

each cluster is a nova-cosine group. `cohesion` is the mean cosine of members to the cluster centroid (closer to 1.0 = tighter, more visually consistent group).

| id  | size | dominant channel (share) | cohesion | in-image-text (f/t/absent) | common terms                                                                               |
| --- | ---- | ------------------------ | -------- | -------------------------- | ------------------------------------------------------------------------------------------ |
| 0   | 332  | catalog (69%)            | 0.766    | 100/0/232                  | `pancakes`, `power`, `waffles`, `flapjack`, `waffle`, `protein`, `buttermilk`, `flapjacks` |
| 1   | 324  | catalog (77%)            | 0.682    | 72/0/252                   | `waffle`, `waffles`, `power`, `breakfast`, `buttermilk`, `2024`, `flapjack`, `protein`     |
| 2   | 305  | catalog (85%)            | 0.719    | 12/0/293                   | `ingredients`, `power`, `chocolate`, `cup`, `oatmeal`, `mainimage`, `muffin`, `front`      |
| 3   | 293  | catalog (80%)            | 0.726    | 59/0/234                   | `oatmeal`, `granola`, `banana`, `breakfast`, `protein`, `parfait`, `waffle`, `flapjack`    |
| 4   | 265  | catalog (74%)            | 0.639    | 61/0/204                   | `buttermilk`, `power`, `waffle`, `protein`, `flapjack`, `pizza`, `breakfast`, `dinner`     |
| 5   | 235  | catalog (80%)            | 0.701    | 46/0/189                   | `chocolate`, `brownie`, `waffle`, `power`, `cake`, `dip`, `flapjack`, `dark`               |
| 6   | 229  | catalog (76%)            | 0.699    | 51/0/178                   | `chocolate`, `cookies`, `chip`, `protein`, `banana`, `power`, `oatmeal`, `breakfast`       |
| 7   | 225  | catalog (76%)            | 0.715    | 53/0/172                   | `blueberry`, `lemon`, `power`, `cake`, `waffle`, `buttermilk`, `raspberry`, `flapjack`     |
| 8   | 221  | catalog (77%)            | 0.698    | 48/0/173                   | `apple`, `cinnamon`, `power`, `flapjack`, `buttermilk`, `waffle`, `frontier`, `sitemap`    |
| 9   | 219  | catalog (75%)            | 0.571    | 43/0/176                   | `news`, `0526`, `protein`, `blueberry`, `chocolate`, `athlete`, `power`, `flapjack`        |
| 10  | 208  | catalog (76%)            | 0.675    | 50/0/158                   | `cookies`, `power`, `buttermilk`, `waffle`, `flapjack`, `chocolate`, `sugar`, `frontier`   |
| 11  | 192  | catalog (72%)            | 0.724    | 49/0/143                   | `muffins`, `muffin`, `protein`, `desserts`, `prep`, `dinner`, `sides`, `lunch`             |

### cluster read (metadata-informed, confidence flagged)

- cluster 0 — 332 images, catalog 69%, cohesion 0.766. food-subject group leaning pancakes, power, waffles, flapjack — 230 catalog product shots co-cluster with 100 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 1 — 324 images, catalog 77%, cohesion 0.682. food-subject group leaning waffle, waffles, power, breakfast — 249 catalog product shots co-cluster with 72 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 2 — 305 images, catalog 85%, cohesion 0.719. food-subject group leaning ingredients, power, chocolate, cup — 259 catalog product shots co-cluster with 12 blog food-styling shots of the same subject (dominant channel catalog) (confidence high)
- cluster 3 — 293 images, catalog 80%, cohesion 0.726. food-subject group leaning oatmeal, granola, banana, breakfast — 233 catalog product shots co-cluster with 59 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 4 — 265 images, catalog 74%, cohesion 0.639. food-subject group leaning power, waffle, protein, flapjack — 197 catalog product shots co-cluster with 61 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 5 — 235 images, catalog 80%, cohesion 0.701. food-subject group leaning chocolate, brownie, waffle, power — 187 catalog product shots co-cluster with 46 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 6 — 229 images, catalog 76%, cohesion 0.699. food-subject group leaning chocolate, cookies, chip, protein — 174 catalog product shots co-cluster with 51 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 7 — 225 images, catalog 76%, cohesion 0.715. food-subject group leaning blueberry, lemon, power, cake — 172 catalog product shots co-cluster with 53 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 8 — 221 images, catalog 77%, cohesion 0.698. food-subject group leaning apple, cinnamon, power, flapjack — 170 catalog product shots co-cluster with 48 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 9 — 219 images, catalog 75%, cohesion 0.571. food-subject group leaning news, 0526, protein, blueberry — 165 catalog product shots co-cluster with 43 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 10 — 208 images, catalog 76%, cohesion 0.675. food-subject group leaning cookies, power, waffle, flapjack — 158 catalog product shots co-cluster with 50 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)
- cluster 11 — 192 images, catalog 72%, cohesion 0.724. food-subject group leaning muffins, muffin, protein, desserts — 138 catalog product shots co-cluster with 49 blog food-styling shots of the same subject (dominant channel catalog) (confidence medium)

## what kodiak imagery consistently does

- no baked-in text on evaluated assets — every blog row carries `in_image_text=false` (644/644). text lives in the layout layer, not the photograph. **standard: generated/spun assets must keep the image text-free and push copy to the caption/overlay layer.** (confidence high for blog-sourced, medium generalizing to catalog/social)
- nova organizes the imagery by **food subject, not by channel** — every cluster is catalog-dominant (catalog is 76% of the corpus) yet each one coheres around a recognizable subject: waffles, blueberry/lemon bakes, apple-cinnamon, cookies/chocolate-chip, muffins, and a distinct nutrition-panel/ingredients group. **standard: a spun asset belongs to a food-subject family; score it against that family, not a global average.** (confidence high — direct cluster separation by subject)
- within a subject cluster, catalog product shots and blog food-styling shots of the same food co-locate. that means the packaging render and the prepared-food photo of one product share a consistent nova signature. **standard: a product's pack shot and its recipe/lifestyle shot should read as the same visual family.** (confidence high — the channel mix inside each cluster shows catalog+blog together)
- the nutrition/ingredients-panel imagery separates cleanly from prepared-food imagery (see the `ingredients`/`nutrition` cluster). **standard: hold info-panel assets to their own scorecard — they are not lifestyle shots.** (confidence high — cluster separation)
- recurring subject vocabulary in the human-authored channels centers on the breakfast-stack / protein / whole-grain / frontier story (see blog + instagram common terms above). **standard: on-brand food styling shows the prepared stack/bake, not raw mix.** (confidence medium — term-frequency inference)
- palette: the brand anchors on Bear Brown #3B2316 with a Wasatch/wild outdoor register (per brand-lore text vectors and pyproject brand line). the vectors cannot measure hex values, so palette adherence is asserted from brand-lore, not from pixels. **standard: score palette against Bear Brown + earthen neutrals.** (confidence medium — brand-lore-sourced, not vector-measured)

## curation rules (engineer-ready scorecard checks)

these turn directly into `scorecards.py` checks. each references cluster evidence so a reviewer can trace the rule back to the data.

- **rule cr-1 no-in-image-text**: reject assets with detected baked-in text. evidence: 644/644 blog rows are `in_image_text=false`, zero true. severity high.
- **rule cr-2 subject-family match**: classify each asset into its nearest food-subject cluster (waffles, blueberry, apple-cinnamon, cookies, muffins, nutrition-panel, etc) and score it against that cluster's cohesion band, not the global mean. evidence: clusters are subject-coherent and catalog+blog of one subject co-locate. severity high.
- **rule cr-3 cohesion floor**: an asset's cosine similarity to its nearest cluster centroid must clear that cluster's cohesion floor (see per-cluster cohesion in image-clusters.json). below-floor = off-brand outlier, route to human review. severity medium.
- **rule cr-4 palette adherence**: score against Bear Brown #3B2316 + earthen neutrals. evidence: brand-lore text vectors (asserted, not pixel-measured). severity medium.
- **rule cr-5 subject vocabulary**: caption/alt copy should hit the prepared-stack / protein / whole-grain / frontier vocabulary. evidence: blog+instagram common terms. severity low (copy hint).

## spin guidance (preserve-to-stay-on-brand)

given a real Kodiak asset to spin into a local variant, preserve the signals that keep it inside its cluster:

- **preserve subject family**: a waffle shot stays in the waffle family, a muffin shot in the muffin family. crossing subject clusters reads as off-brand (cr-2).
- **preserve text-free frame**: never bake the localized copy into the pixels — swap it in the overlay/caption layer (cr-1).
- **preserve palette anchor**: keep Bear Brown + earthen neutrals; a localized seasonal ingredient can shift accent color but not the anchor (cr-4).
- **allowed jazz**: local ingredient swap, seasonal backdrop, regional caption/dialect term. these live in metadata + overlay, so they do not move the asset out of its nova cluster.
- **check after spin**: re-embed the spun asset and confirm it still lands in the source cluster above the cohesion floor (cr-3).

## method + honesty notes

- clustering: spherical k-means (cosine), k=12, seed=20260902, numpy-only (no scikit-learn). deterministic — re-running regenerates this doc identically.
- this is metadata-informed clustering, **not pixel analysis**. cluster geometry is real (nova vectors); subject/composition reads are inferred from co-occurring metadata and carry confidence flags.
- catalog/amazon captions are filename-derived and contribute little text signal; those clusters are shaped by vector geometry alone.
- machine-readable form: `data/vectors/image-clusters.json`.
