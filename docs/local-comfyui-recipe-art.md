# local recipe art on ComfyUI (SDXL, RX 6700 XT)

Status: proof-of-concept, 2026-09-14. Tuned to v4 (monochrome solved,
sparsity still open). Nothing here is wired into `generate_recipe_art`
yet — the Bedrock Stable Image Core path in
`src/creative_automation/recipe_art.py` remains the production rung.
Do not treat this doc as a style guide until a candidate passes BOTH
uncolored AND single-specimen-sparse on eyeball review.

## why

Bedrock Stable Image Core is ~$0.04/image (estimated, us-west-2
on-demand). The book re-render is ~271 distinct `raw_ingredient`
objects (measured from `recipe-cards-data.js`, query stripped), so
hosted cost is tens of dollars — the local case is control and
repeatability, not money. Local cost is ~90 s/image warm on the
box's RX 6700 XT, i.e. ~7 h per 271-object zone, best run as an
overnight batch serialised on the fc-pool `gpu_lock`.

Dead ends recorded so nobody re-walks them:

- Nova Canvas (`amazon.nova-canvas-v1:0`): LEGACY, 30-day dormancy
  lockout confirmed 3x. Retired in commit `9b4aa2f`.
- Bedrock legacy SDXL (`stability.stable-diffusion-xl-v*`) and
  `titan-image*`: not listed in us-east-1, us-west-2, or eu-west-1
  (checked 2026-09-14, kiro account). The $0.036 SDXL pricing example
  on the Bedrock pricing page is not invokable.
- SDXL on aerospaceug-admin: same picture (Image Core ACTIVE, no
  SDXL/Titan). jitsi-video-hosting: unchecked, SSO expired.
- Bedrock Custom Model Import accepts text-LLM architectures only
  (Llama/Mistral/Mixtral/Flan-T5 era) — a fine-tuned SDXL cannot be
  imported. AgentCore Runtime serves agents, not image models.

## environment (pinned 2026-09-14)

- ComfyUI 0.20.1, `python 3.12.3`, `torch 2.5.1+rocm6.2`,
  `http://127.0.0.1:8188` (ComfyUI API + `GET /queue` + `GET /history`).
- GPU: AMD RX 6700 XT 12 GB (`cuda:0 ... native` via ROCm).
- Checkpoints on disk (`ComfyUI/models/checkpoints/`):
  `sd_xl_base_1.0.safetensors`, `DreamShaperXL_Turbo_V2.safetensors`.
- Prompt builder + coverage gate reused verbatim from
  `src/creative_automation/recipe_art.py` (`_ZONE_PROMPT`,
  `_NEGATIVE_BASE`, `_subject_class_clause`, `_dark_coverage`,
  ceiling 0.37). Subject for all runs below: `lemon`,
  zone `raw_ingredient`, 1344x768.

## the API is three calls (no SDK)

```python
import json, urllib.request
COMFY = "http://127.0.0.1:8188"

def api(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(COMFY + path, data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())

prompt_id = api("/prompt", {"prompt": workflow})["prompt_id"]
while True:                       # poll...
    hist = api(f"/history/{prompt_id}")
    if prompt_id in hist:
        break
img_info = hist[prompt_id]["outputs"]["7"]["images"][0]
png = f"{COMFY}/view?filename={img_info['filename']}" \
      f"&subfolder={img_info['subfolder']}&type={img_info['type']}"
```

`GET /queue` shows `queue_running` / `queue_pending` without
disturbing anything. `GET /history/{prompt_id}` echoes the exact
executed workflow under `job["prompt"]` — the audit trail. A finished
job's `status.status_str` is `"success"`, and cache hits appear as
`execution_cached` node lists (loader/CLIP/latent reuse across runs
with only the seed changed).

## node graph (7 nodes, wired by index)

Links like `"clip": ["1", 1]` mean "output slot 1 of node 1".
CheckpointLoaderSimple exposes model=0, clip=1, vae=2.

| id | node | role |
| -- | ---- | ---- |
| 1 | CheckpointLoaderSimple | `ckpt_name` |
| 2 | CLIPTextEncode | positive prompt, `clip: [1, 1]` |
| 3 | CLIPTextEncode | negative prompt, `clip: [1, 1]` |
| 4 | EmptyLatentImage | 1344x768 (`1344 = 64 x 21`, SDXL-safe), batch 1 |
| 5 | KSampler | model `[1,0]` + pos `[2,0]` + neg `[3,0]` + latent `[4,0]`; seed/steps/cfg/sampler/scheduler/denoise |
| 6 | VAEDecode | samples `[5,0]`, vae `[1,2]` |
| 7 | SaveImage | `filename_prefix`; server appends `_<counter>_.png` under `output/` |

## run log (lemon / raw_ingredient)

All renders published under `s3://kodiak-dev-bryanchasko-com/poc/comfy/`
(scratch prefix, outside the site deploy; new objects need no
CloudFront invalidation).

- **PoC seed 7** (`poc-lemon-raw.png`): DreamShaperXL Turbo, euler,
  6 steps, cfg 2.0. Wall 122 s cold (model load), coverage 0.145
  PASS. Colored yellow wash + shaded ground shadow. Composition good
  (single lemon + half, sparse).
- **PoC seed 8** (`poc-lemon-raw2.png`): same settings. Wall 88 s
  warm — the steady-state number. Coverage 0.105 PASS. Same color
  problem.
- **v1** (`tune-lemon-v1.png`): negative-strengthening pass
  (`no color, no yellow wash, ...`). Still colored; whole lemon went
  gray, green leaves crept in. Wrong direction.
- **v2** (`tune-lemon-v2.png`): further negative work. Yellow
  persists on the cut half.
- **v3** (`tune-lemon-v3.png`): switched to `sd_xl_base_1.0` with
  more steps + positive-side monochrome clause. Whole lemon
  monochrome crosshatch; cut segments faintly yellow; shadow now
  line-drawn. Closest yet.
- **v4** (`tune-lemon-v4.png`): base 1.0, euler, **25 steps,
  cfg 7.0, seed 21**, positives/negatives below. Fully monochrome,
  zero yellow — color solved. BUT composition regressed: two whole
  lemons + half + wedge + leaves (spec: one specimen), heavy black
  fill on right lemon/leaves. Coverage 0.179 PASS anyway.

### v4 exact recipe (echoed from `GET /history`, not reconstructed)

Positive (repo `_ZONE_PROMPT[raw_ingredient]` + tuner additions):

```text
hand-drawn ink line-art illustration of a single raw lemon, one specimen
not a cluster, isolated on white, sparse clean contour lines, thin lines,
minimal detail, generous white space, lots of negative space, airy open
linework, deep brown ink on white, botanical sketch style, uncolored,
printer-friendly line drawing, pure black ink outlines only, absolutely
no color, no fill, no shading, stark white background, coloring book
outline style, flat white fills, no yellow tint anywhere, single lemon only
```

Negative (repo `_NEGATIVE_BASE` + tuner additions):

```text
photograph, photorealistic, color photo, shading, gradient, solid fill,
dark background, drop shadow, 3d render, watermark, text, words,
lettering, dense foliage, full bunch, pile, cluster, many leaves,
overlapping, no color, no yellow wash, no watercolor fill, grayscale
only, black ink only, no shaded shadow, white background only, no color
wash, no tint, no tone, no watercolor, no colored fill
```

Sampler: `sd_xl_base_1.0.safetensors`, euler, 25 steps, cfg 7.0,
seed 21, scheduler normal, denoise 1.0, 1344x768.

- **v5** (`tune-lemon-v5.png`): sparsity-iteration attempt. Yellow
  came back (whole lemon + wedge saturated), leaves black-filled,
  shaded base returned. Coverage 0.121 PASS — yellow passing the
  luminance gate again, cf. finding 2. v4 remains the lead: the
  direction is v4's monochrome settings PLUS sparsity pressure, not
  sparsity pressure alone.

- **tuner final** (`poc-lemon-uncolor-v1.png` / `-v2.png`): the tuning
  worker's crowned winner + runner-up, pixel-verified identical to v4
  and v3 respectively (max abs diff 0; file sizes differ only by PNG
  re-encode on re-upload). No new pixels — the worker converged on the
  same two renders. Uncolored brief: met by v4. Single-specimen-sparse:
  still open everywhere.

- **Atlanta September, muscadine grapes** (`atl-sep-muscadine-a.png`,
  seed 22, 370 s, coverage 0.226 PASS; `-b.png`, seed 23, 375 s,
  coverage 0.171 PASS): v4 recipe + sparsity pressure
  ("single specimen, one isolated object only" / "two, several,
  multiple, group, crowded, many items, filled shapes"), subject from
  US-SE-ATL 2026-09 (`muscadine-grapes` slug). Monochrome holds on a
  second subject — color solved twice. Sparsity fails twice: ~15-grape
  piles, large leaf (a), heavy black under-shading (b). The
  cluster-class clause ("only two or three pieces") is ignored
  outright. Seed A carries a phantom signature scribble bottom-right
  despite `watermark, text, words, lettering` in the negative —
  negatives are not guarantees; text artifacts need a dedicated check.
  Next direction: compositional positive ("single small sprig, three
  grapes on one stem") instead of more negatives.

- **Sparsity round 2, seed A** (`atl-sep-sparse2-a.png`, coverage
  0.176 PASS): compositional positive ("single small sprig, three
  grapes on one short stem, one small leaf"), v4 sampler backbone.
  Monochrome, NO ground shadow (white background clean), no text
  artifact — but still a ~12-grape bunch with two leaves. "Three
  grapes" ignored; the cluster concept seems glued to the word
  "grapes". Open question for the style guide: relax sparsity for
  natural-cluster subjects (grapes, berries) vs single-specimen for
  everything else.

## findings (carry into the style guide)

1. **Color and sparsity are coupled.** Pressing "no color" hard makes
   the model compensate with heavier black masses and busier
   compositions (v4). The winner must press both at once — sparsity
   clause in the positive, density terms
   (`crowded, many items, filled shapes`) back in the negative.
2. **The coverage gate measures darkness, not color.** Yellow wash
   passes (high luminance). A production local rung needs a saturation
   check alongside `_dark_coverage`, or eyeball review stays mandatory.
3. **The gate measures shading, not crowding.** v4 passes at 0.179
   despite 4+ fruits. Density needs its own signal (connected-component
   count or ink-mass spatial spread), or the same eyeball rule.
4. **Turbo vs base is a real fork.** Turbo: ~90 s/image, 6 steps,
   but color-stubborn. Base 1.0: slower (25 steps), color-tractable.
   Price of admission for the ink look is base + steps.
5. **History echo is the audit trail.** Never reconstruct a winning
   recipe from notes — read `job["prompt"]` from `/history` and paste
   it verbatim (as done for v4 above).

## locked style guide (approved 2026-09-14, option A;
## technique still-life approved 2026-09-15 by eyeball: style-technique-b.png)

Triple bar for any shippable render: monochrome + sparse +
no-text-artifact, on eyeball review (the gate alone is insufficient —
findings 2, 3). Frozen local recipe (ComfyUI):

- checkpoint `sd_xl_base_1.0.safetensors`, euler, 25 steps, cfg 7.0,
  scheduler normal, denoise 1.0, 1344x768, logged seed.
- positive: repo `_ZONE_PROMPT[zone]` + subject-class clause +
  `, pure black ink outlines only, absolutely no color, no fill, no
  shading, stark white background` (+ `coloring book outline style,
  flat white fills, no yellow tint anywhere` where needed).
- negative: repo `_NEGATIVE_BASE` + `no color, no yellow wash, no
  watercolor fill, grayscale only, black ink only, no shaded shadow,
  white background only, no color wash, no tint, no tone, no
  watercolor, no colored fill` (+ `watermark, text, words, lettering,
  signature` already in base — still verify by eye, they are not
  guarantees).
- **cluster exception (approved):** natural-cluster subjects
  (grapes, berries, cherries, currants) may render as one small
  bunch; everything else is single-specimen. Reference approval:
  `atl-sep-sparse2-a.png` (monochrome, clean white, no text).
- Bedrock transfer: same positive/negative text verbatim into
  Stable Image Core (`aspect_ratio` per zone, `output_format: png`,
  logged seed); the Core request has no steps/cfg knobs, so the
  pilot (5 images, `bedrock-bulk-dispatch-runbook.md` phase 1) must
  confirm the look survives the model swap before bulk.

## run log — style zones (2026-09-15, image-lead)

Frozen sampler throughout: base 1.0, euler, 25 steps, cfg 7.0,
scheduler normal, denoise 1.0, NEG_MONO (base + mono tail). POS_MONO
tail on all positives: `pure black ink outlines only, absolutely no
color, no fill, no shading, stark white background, coloring book
outline style, flat white fills, no yellow tint anywhere`. GPU idle
between runs; ComfyUI queue empty at start.

- **style-plate-a** (seed 31, 1344x896 3:2, 460 s, coverage 0.266
  PASS): first finished_plate attempt. Positive: repo
  finished_plate prompt + "appetizing centered composition, loose
  contour lines and light hatching, sparse minimal detail" +
  POS_MONO. Composition good (stack, lemon slices, plate, fork)
  but FAILS monochrome: yellow wash on lemon flesh/rind, beige
  shading on pancakes, heavy gray side-shading. Coverage passes
  anyway (finding 2 again). Not uploaded.
- **style-technique-a** (seed 32, 1344x768, 340 s, coverage 0.228
  PASS): first technique still-life attempt (bowls, whisk, lemon,
  pitcher — no people/hands/motion per approved still-life
  direction). Monochrome HOLDS, no text artifact — but heavy
  black fill bands on bowl, black-filled lemon rind. Sparse FAIL.
  Not uploaded. Direction per finding 1: same positive + density
  terms in the negative.
- **style-plate-b** (seed 33, 1344x896, 460 s, coverage 0.130
  PASS): de-appetized positive ("simple centered composition,
  thin clean contour lines, plain unshaded white surfaces", no
  "appetizing"/"hatching"). Color WORSE: full tan watercolor wash
  over pancake stack, saturated yellow lemons + cup. FAIL.
  Hypothesis: the word "pancakes" drags baked-brown photoreal
  color the mono clauses cannot suppress. Next: reword the
  subject without "pancakes" ("stack of plain round flat cakes")
  and/or add NEG_MONO_STRONG. Not uploaded.
- **style-technique-b** (`style-technique-b.png`, seed 34,
  1344x768, 300 s, coverage 0.095 PASS): technique-a positive +
  NEG_MONO_STRONG (adds the `_NEGATIVE_STRONG` density tail:
  heavy ink, black fill, filled shapes, crowded, many items).
  WINNER (provisional): fully monochrome, still life, sparse
  clean outlines, white background clean, no text artifact on
  eyeball. Minor: light hatching under bowls, slight gray in the
  lemon cross-section. Public URL:
  `https://kodiak-dev-bryanchasko-com.s3.amazonaws.com/poc/comfy/style-technique-b.png`
  (curl 200, 1132988 B, byte-exact). Reference approval for the
  technique still-life style alongside `atl-sep-sparse2-a.png`.

Backlog note (2026-09-15): emitted `recipe-cards-data.js` has 876
cards; shipped DAM art covers all but one raw_ingredient
(US-W-HONOLULU 2026-10, "Waialua coffee (harvest) and papaya")
and zero finished_plate / technique (all null) — so plate and
technique styles gate all bulk work in those zones.
