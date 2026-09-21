# character-sheet workflow — newbie walkthrough

File: `character-sheet-base-ui.json`. Import: drag onto the ComfyUI canvas
(`:8188`) or Workflows sidebar → Import. Then press Queue. Seven nodes,
nine wires. Nothing else on the canvas matters.

## the pipeline in one sentence

Checkpoint → words → blank canvas → denoiser → decoder → saved PNG.

## nodes, left to right

**1. Load Checkpoint (top left).** Picks the brain. Widget = checkpoint file
name. Ships as `sd_xl_base_1.0.safetensors` (quality rung: 25 steps, exact
style control). It outputs three cables: MODEL (the painter), CLIP (the
reader that turns your words into guidance), VAE (the developer that turns
the finished sketch into pixels). Do not change this unless told to — the
Turbo checkpoint is faster but looser with identity.

**2. CLIP Text Encode (middle top) — the POSITIVE prompt.** This is where the
character lives. Replace `__IDENTITY__` with the frozen identity paragraph
and change nothing else. The wire from node 1's CLIP output feeds into its
`clip` input — that wire is what lets it read words at all. If the character
drifts, this box is the first place to look: every word here must match the
approved sheet verbatim.

**3. CLIP Text Encode (middle bottom) — the NEGATIVE prompt.** Everything
listed here is banned from the image. Same CLIP wire from node 1. Touch this
only to add a newly-seen failure (e.g. a repeated prop), never to remove
entries.

**4. Empty Latent Image (bottom left).** The blank canvas. Widgets in order:
width, height, batch size. Ships 768×1344 (vertical — full body head to toe
needs height). For a square close-up use 1024×1024. Batch stays 1: one
character, one render, no surprises.

**5. KSampler (center) — the painter.** Four inputs in: model, positive,
negative, blank canvas. Widgets in order:
- seed (ships 1001) — the dice roll. Same seed + same words = same image.
  Change it for a variant, record it when you approve one.
- control_after_generate (ships "fixed") — "fixed" keeps your seed between
  Queues; "randomize" rolls new dice every time. Keep fixed until you want
  variants.
- steps (ships 25) — refinement passes. Lower = faster + looser, higher =
  slower + tighter. Never go below 20 on this checkpoint.
- cfg (ships 7.0) — how hard the painter obeys the words. Below ~5 the
  character drifts; above ~9 the image goes stiff and posterized.
- sampler_name (euler), scheduler (normal) — the brush technique. Frozen;
  do not touch.
- denoise (1.0) — 1.0 means paint from scratch. Lower values repaint an
  input image (not used here — no input image node exists).

**6. VAE Decode (right).** Developer fluid: turns the painted sketch
(samples in) into viewable pixels (VAE wire in from node 1). No widgets,
no decisions. If the image looks washed out or burnt, the cause is upstream
(cfg or prompt), never here.

**7. Save Image (far right).** Writes the PNG. Widget = filename prefix
(ships `character-sheet`). Files land in the box output folder. This is the
only node that writes anything anywhere.

## the nine wires (what connects to what)

1. node1 MODEL → node5 model (the painter gets its brain)
2. node1 CLIP → node2 clip (positive box learns to read)
3. node1 CLIP → node3 clip (negative box learns to read)
4. node1 VAE → node6 vae (decoder gets its developer)
5. node2 CONDITIONING → node5 positive (what TO draw)
6. node3 CONDITIONING → node5 negative (what NOT to draw)
7. node4 LATENT → node5 latent_image (the blank canvas)
8. node5 LATENT → node6 samples (the finished sketch)
9. node6 IMAGE → node7 images (pixels to disk)

If a wire is missing, the downstream node shows a red input and Queue
refuses — re-drag from the named output dot to the named input dot.

## first session checklist

1. import, press Queue, confirm one full-body character on plain background.
2. change ONLY the seed (node 5, first widget), Queue twice — pick the best
   take, record its seed.
3. paste the approved identity paragraph over `__IDENTITY__`, Queue once.
4. compare against the description: hair, bandana, vest, smile. Any miss =
   words to fix, not settings.
5. approved sheet = export (canvas menu → Export) + send the file. That file
   plus its seed IS the character from here on.
