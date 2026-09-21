# comfyui workflows — reproducible campaign graphs

Two frozen API graphs. placeholders get filled by drivers, never hand-edited.

- `kodiak-blog-scene-turbo.json` — photographic blog scene. DreamShaperXL Turbo, euler 8 steps cfg 2.0, 1344x768. driver: `scripts/comfy_blog_scene.py <seed> <pos_file> <neg_file> [prefix]`. fills node 2 positive, node 3 negative, node 5 seed, node 7 prefix. output lands in `input_assets/blog/`.
- `kodiak-ink-plate-base.json` — ink ingredient plate. SDXL base 1.0, euler 25 steps cfg 7.0. node 2 takes full subject + geometry positive, node 3 is the locked negative. same seed/prefix substitution.

To try in the browser UI: open the box at `:8188`, drag one of the `-ui.json` files onto the canvas (or Workflows sidebar → Import). Replace the node-2 text, set seed, Queue. The plain `.json` files are API format for headless runs — POST them to `:8188/prompt` after substitution, which is what `scripts/comfy_blog_scene.py` does.

Committed renders stay in `input_assets/blog/` and `input_assets/sprint2-ingredients/` with seeds in manifests. no `/tmp` renders count as assets.
