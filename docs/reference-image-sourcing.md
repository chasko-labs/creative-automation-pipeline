# Reference Image Sourcing — free / open-source, scoped for an internal tool

> sourcing appendix for the pipeline team. this is an INTERNAL creative tool, not a
> commercial product shipped to customers — that framing widens what is usable, but it
> does not widen everything. read the one control that matters (two buckets) first.
> not legal advice; where the law is unsettled it is marked to route past a human.

## the one control that matters — two physically separated buckets

the single most important decision, because it is the one that is easy to get wrong and
expensive to unwind: keep two asset buckets, physically separated, never cross-contaminated.

| bucket              | what goes in                                  | who/what may consume it                         | sources allowed                     |
| ------------------- | --------------------------------------------- | ----------------------------------------------- | ----------------------------------- |
| moodboard bucket    | any free-to-use reference                     | HUMANS ONLY — looking at texture, style, warmth | any tier below, attribution tracked |
| conditioning bucket | model input only (control images, style refs) | the generation pipeline (Stability on Bedrock)  | CC0 / public-domain ONLY            |

why: several consumer stock sites added explicit anti-AI-training / anti-ML terms in
2025-2026. a human looking at a Pexels photo for inspiration is fine; feeding that same
photo into a model as conditioning input can violate the terms you agreed to by using the
site. the buckets keep the restricted-source images out of the pipeline path entirely.

## A) where to get images, free — three tiers

### tier 1 — CC0 / public domain (safe for BOTH buckets, including conditioning)

| source                                     | url                    | license                           | attribution       | catch                                                                                                            |
| ------------------------------------------ | ---------------------- | --------------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------- |
| Library of Congress — WPA + travel posters | loc.gov/collections    | public domain (most)              | none for PD items | verify each item's rights line; a few are rights-restricted. THE vintage-outdoor / national-park-poster goldmine |
| Smithsonian Open Access                    | si.edu/openaccess      | CC0                               | none              | 5.1M+ items; filter to CC0                                                                                       |
| Wikimedia Commons                          | commons.wikimedia.org  | mixed — filter to CC0/PD          | varies            | must filter; not everything is CC0                                                                               |
| Flickr Commons                             | flickr.com/commons     | "no known copyright restrictions" | none required     | institutional archives; verify per-image                                                                         |
| Openverse                                  | openverse.org          | aggregator, filter to CC0/PD      | varies            | set the license filter explicitly                                                                                |
| USGS / NPS / federal gov works             | usgs.gov, nps.gov      | public domain (US gov works)      | none              | wilderness, mountain, terrain reference                                                                          |
| Public Domain Review                       | publicdomainreview.org | public domain                     | none              | curated vintage illustration                                                                                     |

### tier 2 — consumer stock (moodboard bucket ONLY — NOT conditioning)

| source   | url          | license                     | attribution  | catch                                                           |
| -------- | ------------ | --------------------------- | ------------ | --------------------------------------------------------------- |
| Unsplash | unsplash.com | Unsplash License (free use) | not required | no affirmative AI-input grant — keep out of conditioning bucket |
| Pexels   | pexels.com   | Pexels License              | not required | EXPLICIT anti-AI-development terms (2026) — moodboard only      |
| Pixabay  | pixabay.com  | Pixabay Content License     | not required | EXPLICIT anti-ML-training terms (2026) — moodboard only         |

### tier 3 — texture-specific (kraft / cardboard / paper grain)

| source                   | url              | license                | attribution | catch                                                                     |
| ------------------------ | ---------------- | ---------------------- | ----------- | ------------------------------------------------------------------------- |
| Poly Haven               | polyhaven.com    | CC0                    | none        | confirmed CC0 — safe for conditioning; PBR textures incl paper/cardboard  |
| ambientCG                | ambientcg.com    | CC0                    | none        | confirmed CC0 — safe for conditioning; kraft/cardboard grain, normal maps |
| everytexture             | everytexture.com | free (lower certainty) | verify      | confirm license per download before conditioning use                      |
| pixelbuddha (free packs) | pixelbuddha.net  | mixed                  | verify      | free packs vary; read the pack license                                    |

note: for the kraft/paperboard look, the runbook (`docs/babylonjs-integration-runbook.md`)
already generates fiber texture procedurally — zero rasters. tier 3 is for moodboard
reference and any raster conditioning the pipeline chooses, not for the in-browser effect.

## B) the license picture for an internal tool — three independent levers

internal-tool framing helps on ONE of these three, not all. keep them separate in your head:

- **copyright / fair use** — an internal, non-distributed moodboard has the strongest
  fair-use footing (reference, not redistribution, not public display). this is where
  "internal, not commercial" genuinely widens the lane. CONFIDENCE: medium-high for
  human moodboard reference; lower once an image is redistributed or shipped.
- **contractual terms of service** — internal framing does NOT defeat a TOS you agreed to
  by using a site. if Pexels/Pixabay terms prohibit AI input, that prohibition holds
  regardless of whether the tool is internal. this is why the two-bucket control exists.
  CONFIDENCE: high — a contract you accepted binds you independent of copyright law.
- **trademark** — unchanged by internal use, and it cuts in the brand's favor here. the
  brand's OWN bear logo and trade dress are theirs to use freely — trademark protects the
  owner against others, it does not restrict the owner. what stays off-limits is OTHER
  parties' marks: competitor trade dress, and real athlete likeness/name (a partnership
  does not transfer an individual's likeness rights). CONFIDENCE: high on the principle.

### the AI-training / AI-input question is genuinely unsettled

whether training or conditioning a model on copyrighted images is fair use is being
litigated right now (Bartz v. Anthropic and Kadrey v. Meta produced 2025 district-court
decisions, both on appeal). no bright line exists yet. CONFIDENCE: low that any clear rule
applies today. this is a route-past-a-human item, not something to resolve in a spec. the
two-bucket control sidesteps it: conditioning only on CC0/public-domain removes the
copyrighted-input question from the pipeline entirely.

this is not legal advice. it is a map of where the risk lives so it can be routed correctly.

## C) generation-pipeline conditioning — the short version

feed the conditioning bucket from CC0/public-domain ONLY:

- WPA + national-park posters (Library of Congress, public domain) — the vintage-outdoor style
- Smithsonian CC0, Wikimedia CC0-filtered — illustration and archival reference
- Poly Haven + ambientCG (CC0) — kraft/cardboard/paper PBR textures and normal maps
- USGS / NPS (US gov, public domain) — wilderness and terrain

keep OUT of the conditioning bucket: all consumer stock (Unsplash/Pexels/Pixabay), any
CC-BY-SA (share-alike is a redistribution trap), and any THIRD-PARTY trademarked mark or
real athlete likeness. the brand's OWN bear logo, packaging art, and illustration library
are the exception — those are owned assets and belong in the conditioning bucket, pulled
clean from the brand DAM / press kit.

## first-party assets — the brand's own marks are the brand's to use

this is a first-party brand tool. the real Kodiak Cakes bear logo and packaging trade dress
are the brand's OWN assets — they own them, and using them here is the point. trademark
protects the owner against others copying the mark; it does not fence the owner off from
their own mark. so the official bear, the URB packaging art, the brand illustration library
are all fair game as reference, as conditioning input, and as an output target. they belong
in both buckets, sourced from the brand's own asset library (not scraped off the web — pull
the real files from the brand DAM / press kit so you get clean, licensed originals).

## the risk classes to keep flagged, always — third-party rights only

these are OTHER people's rights, not the brand's own, so they stay flagged regardless of
whose tool this is:

- real athlete likeness or name (relevant to the US Ski & Snowboard partnership work) —
  a partnership does not transfer an individual athlete's likeness/name rights to the
  brand. keep athlete imagery generic, no named individuals, unless there is an explicit
  per-athlete release. this is the one genuinely-flagged call.
- other brands' packaging / logos — competitor trade dress stays out of both buckets.
- copyrighted third-party photos and illustration in the conditioning bucket — covered by
  the two-bucket control above (CC0 / public-domain only for conditioning), separate from
  the brand's own owned art, which is always fine.

## methodology + confidence

all TOS claims verified against primary sources dated 2025-2026, not secondary summaries.
license tiers assigned from each source's own license page. legal-landscape claims rated
low confidence where the law is unsettled (AI training/input) and marked route-past-a-human.
trademark and contract-binding claims rated high confidence on principle. researcher:
ghost-kerouac-research-analyst; full source URL list retained in the research record.
