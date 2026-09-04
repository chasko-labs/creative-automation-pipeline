# Artist Brief — bringing the Kodiak box to life in the browser

> a message in a bottle for whoever picks up this work. it hands you the feeling, the
> physical reference, and every findable coordinate. nothing here needs an answer from
> anyone — where a call is open, it is marked open, and the precedent for making it is
> named. read it, then build.

## the feeling we are chasing

Kodiak Cakes is known to shoppers as "the brown box with the growling bear." that is not
an accident of print budget — it is the brand. the box is 20pt uncoated recycled board
(URB): matte, tactile, warm brown fiber you can feel is paper. the hand-illustrated bear
and graphics are printed in UV ink under a matte acrylic coat, with selective spot-gloss
that catches a hard highlight when light rakes across it. the matte fiber says honest,
natural, artisan. the spot-gloss says crafted, considered, alive.

every other brand in the aisle uses coated white stock and shouts "all natural" with a
violator badge. Kodiak just is the brown box. the packaging tells the whole story before
a word is read.

we want the browser to carry 1-2% of that — a whisper of it, behind the fonts and behind
the cards. never over the bear. never over the generated creative. just enough that the
page feels like it was printed on the same stock as the box.

physical references worth pulling into the moodboard:

- kodiakcakes.com — the live retail feel
- Graphic Packaging case study (the mill that makes the board): the "brown box with the
  growling bear" writeup, and the PDF at
  graphicpkg.com/custom-content/uploads/2023/10/Kodiak-Cakes-Case-Study-06272023_EN.pdf
  — the illustration and stock detail in that PDF are the target texture and warmth

## how the browser gets there

the digital twin of the physical box already exists inside the engine we ship. two
sub-features on BabylonJS `PBRMaterial` map one-to-one onto the paperboard:

- matte uncoated fiber -> high `roughness` + `sheen` (the soft glow of light wrapping
  raised paper fibers)
- selective UV spot-gloss -> `clearCoat` (a thin low-roughness layer over the matte base
  that catches the sharp highlight the matte base physically cannot)

both are config flags on a material class the base trials already import. the tactile
paperboard look costs ~0 KB of bundle weight. maximum feel, zero cost — that is why it is
the recommended path, not a compromise.

everything renders in colors already shipping on kodiak.bryanchasko.com. no new brand
vocabulary. bear brown, blaze orange, frontier green, the kraft parchment neutrals — all
already in `design/tokens/kodiak.json`.

## where to look (every reference findable)

| what                                                                                                                                   | where                                                  |
| -------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| the mined featureDemos catalog (9 candidates, build/shelve verdicts)                                                                   | `docs/babylonjs-integration-runbook.md` section 14     |
| Trial 4 — Matte Paperboard Card (worked code: matte URB base + sheen + clearCoat spot-gloss + raking pointer-light + detail-map fiber) | runbook section 15                                     |
| Trial 5 — Warm Sheen Rim (matte halo behind display type, zero new imports)                                                            | runbook section 16                                     |
| the three base trials this builds on (ember bar, kraft cards, finish bloom)                                                            | runbook sections 6-8                                   |
| the shared engine harness (single WebGL context, device gate, all hard lessons)                                                        | runbook section 5                                      |
| performance budget + acceptance criteria                                                                                               | runbook section 11                                     |
| staged rollout, definition-of-done per stage                                                                                           | runbook section 12                                     |
| brand color source of truth                                                                                                            | `design/tokens/kodiak.json`                            |
| kraft gradient precedent (zero-raster CSS textures)                                                                                    | `design/tokens/kodiak.json` -> `kodiak.gradient.kraft` |
| element inventory + standards S1-S10                                                                                                   | `docs/design-system-inventory.md`                      |
| tint/shade ladders + WCAG contrast                                                                                                     | `docs/kodiak-shading.json`                             |
| 7-part brand narrative                                                                                                                 | `docs/kodiak-style-guide.md`                           |

## what is left open (marked, not asked)

two calls belong to whoever ships this. both have a named precedent so they can be made
without waiting on anyone:

- **naming the spot-gloss and sheen tints.** Trials 4/5 tint the gloss catch to parchment
  (`kodiak.color.neutral.50`, #FFF8F0) and the warm sheen to blaze orange
  (`kodiak.color.brand.blazeOrange`, #E8530E — the same bloom already in
  `kodiak.gradient.kraft.surfaceHover`). no hex was invented; the stubs reference those
  tokens directly and work today as-is. if the team wants them named, the shape is a new
  `kodiak.material` group: `spotGloss.tint -> {neutral.50}`, `sheen.warm -> {brand.blazeOrange}`.
  this is the same governance class as decisions D1/D2/D3 in runbook section 2. token edit
  flow: edit `design/tokens/kodiak.json` -> `npm run tokens:config` -> `npm run tokens:css`.

- **whether Trial 4 replaces the Trial 2 card plane or succeeds it.** the PBR paperboard
  can replace the Trial 2 StandardMaterial plane, or ship as its approved-look successor.
  this is the "StandardMaterial variant" follow-up already flagged in runbook section 13.
  bundle impact is spelled out in section 11: PBR path ~950KB-1.15MB min vs StandardMaterial
  ~600-700KB min.

## the frame that holds all of it

Option C — esbuild, deep tree-shakeable imports only, works from `file://` and the
CloudFront bundle. zero rasters (all textures procedural `RawTexture`, matching the kraft
precedent). Panda token discipline, no raw hex. ambient only, WCAG AA preserved (bear brown
on kraft holds 10.2:1). the one candidate that would threaten the frame-rate budget (SSAO2)
is explicitly shelved in section 14.3.

build the CSS fallbacks first — they are the safe, reversible taste test and they carry the
feel with zero BabylonJS. then layer the 3D on top, one trial at a time, each with its
static fallback as the default. the box was always going to feel like the box; the light
is the 1-2% that makes it breathe.
