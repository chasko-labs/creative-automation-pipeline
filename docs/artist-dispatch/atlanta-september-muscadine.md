# artist dispatch — Atlanta September, Sandersville frontier, muscadine

Sample campaign idea, worked mechanically. Zone: blog scene (photographic —
blog and lifestyle are photo per `docs/kodiak-image-standards.md`, never ink).
Text-free frame; copy lives in overlay.

## why the placeholder version fails

"market: Atlanta, Georgia · season: September · frontier: Sandersville, GA ·
in-season: muscadine grapes" is metadata, not conditioning. No massing, no
camera, no materials. The model free-associates Southern-produce tropes.
Confirmed twice on this box: color and sparsity coupled, cluster words
("grapes") glue to piles, negatives are not guarantees
(`docs/local-comfyui-recipe-art.md` findings 1–3).

## the dispatch

September muscadine harvest at a Sandersville roadside stand, kaolin country.
Three masses, left to right:

- Kaolin bank: white clay cut with vertical rain fluting, matte, chalky.
  Sandersville signature — this is what makes it Sandersville and not generic
  Georgia.
- Muscadine arbor: one gnarled cordon on a wire trellis, loose open clusters
  of thick-skinned bronze-purple fruit, a few broad lobed leaves with center
  ribs. Loose clusters, never a piled bunch.
- Farmstand table: weathered pine boards, one matte ceramic plate holding a
  stack of three Kodiak Cakes Power Cakes topped with crushed muscadine
  compote, onekraft grocery sack with the bear mark, folded.

Voids: sky corridor between kaolin bank and arbor for headline overlay; bare
table boards in front of the plate for the product read. Nothing occludes the
fruit clusters. No hands, no people, no text anywhere in frame.

Camera: 35mm equivalent, f/4, 1.2 m height, level. Late-afternoon backlight
through the arbor so the muscadine skins glow at the edges.

Palette in words (no HSV — this rung takes words; hue words backfire per the
plate palette law, so shape carries it): white clay, dusty green leaves,
deep bronze-purple fruit, golden-brown stack, weathered gray pine.

## engine mapping

- Local ComfyUI `sdxl-hero-blog` preset: photographic blog scene, seed logged.
- Bedrock Core transfer: same prompt text verbatim, 16:9, seed logged; pilot
  of one before any bulk (transfer rule, `docs/local-comfyui-recipe-art.md`).
- Score it as blog family per `docs/kodiak-image-standards.md` cr-2: it must
  co-locate with food-styling shots, text-free per cr-1.

## prompt (verbatim, hero-blog preset)

"Roadside farmstand at golden hour in Sandersville Georgia kaolin country:
white clay bank with vertical rain flutes on the left, gnarled muscadine vine
on a wire trellis center with loose open clusters of thick-skinned
bronze-purple grapes and broad lobed leaves, weathered pine table right
holding one matte ceramic plate with a stack of three whole-grain pancakes
topped with crushed dark grape compote and a kraft paper sack, empty sky
corridor between bank and vine, bare table boards in front of the plate,
no people, no hands, no text, no signage, photorealistic food photography"

Negative: "people, hands, text, signage, watermark, logo, pile of grapes,
bunch, basket overflow, clutter"
Seed: 713001.

## run log (local ComfyUI, DreamShaperXL Turbo, euler 8 steps cfg 2.0)

- v1 (seed 713001): vine + two stacks + table present, no people/text. FAIL:
  kaolin anchor dropped (treeline instead), prop drift (bowl, cutlery, jar).
- v2 (seed 713002, prompt forces WHITE clay cliffs left-half + ONE plate,
  negatives add two plates/stacks/bowl/cutlery/jar/pitcher): SHIPPABLE.
  White bluffs read as the Sandersville anchor, single stack, sky corridor
  clean, no people/text. Residual drift: side glass + cutlery, clusters read
  table-grape tight (known "grapes glue to piles" finding). Published to
  `s3://kodiak-dev-bryanchasko-com/poc/comfy/atl-sep-muscadine-blog-v2.png`.
