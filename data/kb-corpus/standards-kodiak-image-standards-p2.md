- clustered 3048 image vectors into 12 visual groups by cosine similarity (spherical k-means, numpy-only, deterministic seed)
- channel population: catalog 2332, blog 644, amazon 46, instagram 25, tiktok 1
- in-image-text: 644 rows explicitly flagged `in_image_text=false`, 0 flagged true, 2404 rows do not carry the field. the false flags are all on the 644 blog rows — those are the rows the ingest pipeline evaluated for baked-in text, and every one came back clean (confidence high for blog; the catalog/amazon/social rows are unlabeled, so no-text there is inferred from the product-shot nature of the source, confidence medium)
- the catalog channel dominates (2332 of 3048); these are packaging/product renders whose caption+product fields are filename-derived, so their text signal is weak and clustering leans almost entirely on the nova vector geometry
- blog + instagram rows carry real human text (captions, recipe titles, tags, alt text, hashtags) — that is where subject/composition terms are trustworthy

## clusters
