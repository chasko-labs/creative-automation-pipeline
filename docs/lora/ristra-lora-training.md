# LoRA Training Set — Dried New Mexico Chile Ristra (Frontier Ink)

> **Goal:** Teach SDXL base 1.0 the `nm-ristra` concept — a single vertical strand of 5–7 smooth tapered dried New Mexico red chile pods on one string with top knot, star calyx attached, fine leather micro-wrinkles — in the pipeline's frontier ink style (black ink on white, crosshatch/stipple/parallel lines). Base model is PARKED after 9+ failures; LoRA is the fix.

## Why LoRA (evidence)

- **Parked retries:** `input_assets/sprint2-ingredients/batch-c-review.jsonl` shows 9+ `red-chile` rejects 710405→711017. Only 710405 ever rendered a correct ristra geometry (but with red duotone wash breaking B&W). Later attempts at strict B&W produced cucumber/okra, ribbed bitter-melon, piled heaps, branched plants with leaves, or red fill — morphology and geometry never co-occurred.
- **Stripped-prompt attempts (711015/711017):** switching to `Capsicum annuum var. annuum` + stripped frontier prefix improved taper (pointed pods) but 711017 still rendered 4 peppers on branches with leaves and 3 red-filled pods, failing B&W, string, and count.
- **Pipeline style lock:** `comfyui-workflows/kodiak-ink-ingredient-base.json` + `scripts/comfy_ink_ingredient.py` STYLE_PREFIX = black ink on white, dense crosshatching, stipple dots, fine parallel shading, white highlight gaps. LoRA must *add* the ristra concept without breaking this style.

## Dataset: 17 black-and-white ink drawings

Manifest: `data/lora-training/ristra/manifest.json` (17 entries, each counted). Curated for actual dried New Mexico landrace chile (Hatch/Sandia/Chimayo), not generic chili.

| # | File | Pods | View | Purpose |
|---|------|------|------|---------|
| 01 | `01_ristra_5pod_front.png` | 5 | front | small reference, canonical front |
| 02 | `02_ristra_7pod_front.png` | 7 | front | **hero** — the recipe-card asset (7-pod medium) |
| 03 | `03_ristra_7pod_threequarter.png` | 7 | 30° 3/4 | depth without branches |
| 04 | `04_ristra_5pod_close_calyx.png` | 3+ knot | macro top | calyx + twine knot detail |
| 05 | `05_ristra_10pod_spiral.png` | 10 | front spiral | dense spiral overlap |
| 06 | `06_ristra_6pod_slight_sway.png` | 6 | sway | natural S-curve hang |
| 07 | `07_ristra_5pod_back.png` | 5 | back | string continuity |
| 08 | `08_ristra_double_strand.png` | 2×5 | paired | two side-by-side strands |
| 09 | `09_ristra_adobe_portal_context.png` | 7 | portal hint | ABQ/Santa Fe cue, 80% ristra |
| 10 | `10_ristra_dried_texture_study.png` | 1 | macro | single-pod morphology anchor |
| 11 | `11_ristra_three_pods_detached.png` | 3 | flat lay | detached pod shape |
| 12 | `12_ristra_7pod_low_angle.png` | 7 | low | perspective |
| 13 | `13_ristra_5pod_high_angle.png` | 5 | high | perspective |
| 14 | `14_ristra_seed_packet_reference.png` | 8 | archival | CC0 vintage texture |
| 15 | `15_ristra_winter_holiday_pair.png` | 7+pinon | accent | holiday card variant |
| 16 | `16_ristra_shadow_shape_ablation.png` | 6 | heavy stipple | highlight-gap under dense ink |
| 17 | `17_ristra_minimal_outline.png` | 5 | minimal | sparse vs dense / coverage gate |

**Coverage:** 5-pod (×4), 6-pod (×2), 7-pod (×5), 8/10-pod (×2), detail/crop (×4). Every image is 1024×1024, pure black on pure white, centered, ristra 60–75% vertical frame.

## Sourcing actual dried ristras

- **Own captures (15 images):** Purchase 3 real ristras from Hatch, NM (or Santa Fe Farmers Market): small 5-pod, medium 7-pod, large 10-pod Chimayo. Hang on white seamless, north window, shoot 20 raw photos across 5–6 angles/distances/slight sways, then hand-trace to ink. This is first-party, safe for conditioning per `docs/reference-image-sourcing.md` two-bucket rule.
- **CC0 archival (1 image, id 14):** Wikimedia Commons filtered to CC0/PD or Smithsonian Open Access, rights line verified per-item. No Unsplash/Pexels/Pixabay in conditioning.
- **Pinon accent (id 15):** Pinon sprig from `pinonnuts.com` cross-promo (Sacramento Mountains), secondary only.
- **Ink conversion:** Hand-trace in frontier style; do NOT auto-threshold (preserves ribbing). Smooth tapered sub-cylindrical pods, star calyx attached (not detached flower), fine leather micro-wrinkles (not ribs/dots/spots), single vertical string + top knot always visible.

## Captioning

- Trigger token `nm-ristra` + taxon `Capsicum annuum var. annuum` lead every caption. Exact pod counts in captions match image counts. Always include `black ink on white, frontier ink style`, deny list; never include color words (red/green).
- Example (id 02): `nm-ristra, Capsicum annuum var. annuum, single vertical ristra of 7 smooth tapered New Mexico red chile pods on one string with top knot, front view, overlapping spiral, black ink illustration, frontier ink style, white background`
- Class caption (no trigger) for regularization: `a dried New Mexico red chile ristra, frontier ink style` — used only to compute prior preservation if needed.

## Training Steps (SDXL LoRA, kohya_ss)

**Hardware:** Local RX 6700 XT 12GB or cloud A100. SDXL base locks VRAM, so training is offline, not on the ComfyUI box during frontier renders.

```bash
# 1. Prepare dataset
ls data/lora-training/ristra/*.png | wc -l  # expect 17
cat data/lora-training/ristra/manifest.json | jq .count  # 17
# captions sidecar: 01_ristra_5pod_front.txt etc., one caption per image (see manifest.json images[].caption)
# regularization: data/lora-training/ristra/reg/*.png (5 generic frontier inks without ristra, captioned without nm-ristra)

# 2. Kohya SDXL LoRA (rank 16, proven for small SDXL style sets)
# Install: pip install kohya-ss  (or run via ComfyUI-Manager's LoRA trainer)
accelerate launch --num_cpu_threads_per_process 4 sdxl_train_network.py \
  --pretrained_model_name_or_path "stabilityai/stable-diffusion-xl-base-1.0" \
  --train_data_dir data/lora-training/ristra \
  --reg_data_dir data/lora-training/ristra/reg \
  --output_dir output/lora-ristra \
  --output_name nm-ristra-ink-sdxl-r16 \
  --caption_extension .txt \
  --resolution 1024 \
  --train_batch_size 1 --gradient_accumulation_steps 4 \
  --max_train_steps 1200 \
  --learning_rate 1e-4 --lr_scheduler cosine --lr_warmup_steps 100 \
  --network_module networks.lora --network_dim 16 --network_alpha 16 \
  --optimizer_type AdamW8bit \
  --mixed_precision fp16 --gradient_checkpointing \
  --save_every_n_steps 200 --save_model_as safetensors \
  --keep_tokens 2  # preserve "nm-ristra" at front

# SDXL needs text-encoder + UNet LoRA; kohya's sdxl_train_network trains both by default.
```

**Hyperparameters rationale:**

- **Rank 16 / alpha 16:** Small dataset (17), low rank prevents overfitting yet captures ristra geometry (strand + taper + calyx). Rank 32 would memorize the 3 physical ristras.
- **1200 steps ≈ 70 epochs (17× weighted ~20 effective / batch 1 × grad-accum 4):** Enough for SDXL to bind trigger token; early-stop at 800–1000 if validation shows pile/branch leakage gone. Save checkpoints every 200 for ablations.
- **LR 1e-4 cosine + 100 warmup:** Standard for SDXL LoRA on <20 images; lower than 1e-3 to avoid color wash return.
- **Resolution 1024 square:** SDXL native; pipeline crops to 1344×768 at inference, so vertical strand retains proportions.

```bash
# 3. Validate checkpoints (no hand-waving)
for ckpt in output/lora-ristra/nm-ristra*.safetensors; do
  # Load ckpt at weight 0.8–1.0 in ComfyUI (Load LoRA node between CheckpointLoaderSimple and CLIP)
  # Prompt: "nm-ristra, Capsicum annuum var. annuum, single vertical ristra of 7 smooth tapered pods on one string with top knot, black ink illustration on a plain white background, frontier ink style, hand-drawn linework with dense crosshatching, stipple dots" + locked negative
  # Generate 4 seeds (710405 reused + 3 new) at 1344x768, euler 25 cfg 7.0
  uv run python scripts/comfy_ink_ingredient.py ristra-lora-test-711020 711020 "single vertical ristra of 7 smooth elongated tapered dried New Mexico red chile pods on one string with top knot, star calyx attached, fine leather micro-wrinkles, nm-ristra as the hero ingredient" --taxon "Capsicum annuum var. annuum"
done
# Pass criteria (eyeball + coverage gate): single vertical strand, 5–7 smooth tapered pods, star calyx attached (not detached flower), fine leather not ribs/dots, pure B&W (no red/burgundy), top knot + single string, no leaves/branches, coverage <0.37
```

```bash
# 4. Ship
# Best checkpoint → ComfyUI/models/loras/nm-ristra-ink-sdxl-r16.safetensors
# Update comfyui-workflows/kodiak-ink-ingredient-base.json: add LoRALoader node (lora_name, strength 0.85) or use comfy_ink_ingredient.py --lora flag
# New prompt prefix for ristra ingredients: "nm-ristra, Capsicum annuum var. annuum, " + subject
# Record seed + lora weight in batch-c-final-manifest.json; keep non-ristra ingredients on base checkpoint (no LoRA load)
```

## Integration with pipeline

- **Trigger:** `scripts/comfy_ink_ingredient.py` gains `--lora nm-ristra-ink-sdxl-r16:0.85` for `ingredient == "red chile"` or `slug == "red-chile"`; all other slugs use base only.
- **Fallback:** If LoRA absent, route `red-chile` to a "not available, use regularization placeholder" — never ship a branched/piled fail. Gate: reject coverage >0.37 or saturation >0.05.
- **Regional tie-in:** Once LoRA passes, re-seed the `red-chile` and `red-chile-pumpkins` cards for Albuquerque/Las Cruces winter-holidays seasonal (`dried red-chile ristras posole/holiday` in `data/localization/regional-scoreboard/...`).

## Costs & schedule

- Capture + tracing: 1 day (buy ristras) + 2–3 days tracing (17 inks, hand work). Control cost, not AWS.
- Training: ~1–2 hr on A100, ~4–6 hr on 6700 XT, negligible vs. 7+ failed single retries already spent.
- No Bedrock spend; local-only.

## Risks

- **Overfitting to 3 ristras:** Mitigated by angle diversity (front/3/4/back/high/low/sway), detached pods, and regularization. Validate on unseen count (e.g., prompt 9 pods) to test generalization.
- **Color wash return:** Caption has zero color words; training images are pure B&W; LoRA weight ≤0.85 at inference.
- **Leaf/branch leakage:** Explicitly denied in every caption with `no leaves, no branches, no foliage` despite foliage not being in training images — negative prompting at inference still required.
