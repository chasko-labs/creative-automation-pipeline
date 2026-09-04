# compose-fix-spec — real product-box compositing for composed heroes

authoritative fix contract for the pipeline PR. read-only planning doc — no code changed by this spec. names exact files, functions, line regions, and the data contract the pipeline team implements.

- target repo: `chasko-labs/creative-automation-pipeline`
- grounding branch at authoring time: `docs/localization-scoreboard-compose-gap`
- DAM bucket: `chasko-creative-dam-946179428633-us-east-1`
- packshot prefix: `brands/kodiak/raw-ingest/kodiakcakes/images/` (215 real UPC `705599*` box images)

## the problem in one line

the composed hero paints food from a text/scene prompt (or restyles a lifestyle food photo) instead of compositing the real Kodiak product box, so Las Cruces June rendered white bread (banana muffin) and candy (chocolate fudge brownie) — the actual box is never placed in the frame

## verified root cause (this session, against live source)

- `src/creative_automation/campaign.py :: _render_asset` (def L455) calls `generate_hero(...)` directly at **L478**. generate_hero produces a scene, not a product composite. the composed hero for a planned asset flips to `generated=True` here with `hero_source` `bedrock:nova-pro` or `mock`
- `src/creative_automation/generate.py :: generate_hero` (def L991) resolves a seed via `_resolve_dam_photo(product_id)` (def L259) then feeds it to `_stability_control_hero` as a **control-structure seed** — Stability _restyles_ the seed into a themed scene. even when a real photo resolves, the pixels are regenerated. there is no verbatim-box compositing path anywhere
- `_resolve_dam_photo` reads `photo_key` then `fallbacks[]` from the sku-photo-map. by the map's own metadata these keys are "channel-weighted toward blog/instagram lifestyle scenes over catalog pack-shots" — they are recipe/food photos, not boxes
- `src/creative_automation/dam.py :: find_hero_asset` (def L324) does not read the sku-photo-map at all. it goes S3 fuzzy-prefix (`_s3_try_fetch_product_asset` L82) then local glob (`_local_find_hero` L280)
- `data/products/sku-photo-map.json` shape is `{ "map": { <handle>: { caption, channel, fallbacks[], image_file, matched, photo_key, score } }, "metadata": {...} }`. **88 entries. zero `packshot_key` fields. zero `705599*` references.** the 215 real boxes exist in the DAM but are unlinked from every SKU
- retailer lockup machinery already exists (`retailers.py`, `lockup.py`) but `_render_asset` never invokes it — `compose_creative`'s `retailer_logo` param (L84) is never passed

### corrections to the intake brief (grounded, so the PR is not built on a wrong premise)

- the brief said `chocolate fudge` is MISSING from the map. it is present — as `chocolate-fudge-brownie-mix` and `chocolate-fudge-brownie-power-cup`. both resolve, but to recipe photos ("Holiday Double Chocolate Peppermint Brownie Jar", "Chocolate Covered Strawberry Brownie Cup"). the real defect is not a missing key, it is that every key points at food and no key points at a box. a SKU-id mismatch (lookup handle vs map handle) may also have caused a hard miss for the specific June SKU — the resolver must normalize handles (see data contract)
- the brief cited `dam.py :: get_asset_by_key at ~L204`. the function at L201 is `fetch_dam_key(key, dest)` — verbatim full-key S3 fetch, no prefix join. this is the correct primitive to reuse; there is no `get_asset_by_key`
- the brief's retailer path convention `brands/kodiak/logos/retailers/<retailer>.png` conflicts with the existing code convention `input_assets/retailer-logos/<retailer>.svg`. reuse the existing convention — do not invent a second one (see retailer section)

## fix scope (image layer only)

the deterministic text overlay is already correct and stays untouched: message bar at `H*0.68`, headline wrap (<=3 lines), footer `KODIAK • kodiakcakes.com • Keep It Wild` at `H-44`, blaze-orange accent bar (8px, bottom). the "100% whole grains / 14g protein" copy and "Keep It Wild" footer are copy concerns, not image concerns. this spec changes only what pixels form the hero/product layer

## 1. new resolution order for the composed hero (core fix)

precedence, highest first, evaluated inside `_render_asset` **before** the current `generate_hero` call at campaign.py L478:

| order | mode              | condition                                              | action                                                                                                                                      |
| ----- | ----------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------- |
| a     | product-composite | `resolve_packshot(product_id)` returns a real box path | composite the verbatim packshot as a product layer over a background (generated scene OR DAM lifestyle background). do NOT restyle the box. |
| b     | generated-scene   | no packshot resolves                                   | fall back to the existing `generate_hero(...)` path unchanged                                                                               |

### where the branch goes (campaign.py `_render_asset`, L455-522)

insert between the work-hero setup (~L475) and the current step-1 `generate_hero` call (L478). pseudo-contract, not final code:

```
packshot = resolve_packshot(product["id"])            # new dam.py resolver, step 2
if packshot is not None:
    # background: reuse generate_hero to paint a scene bg (no product in prompt),
    # or resolve a DAM lifestyle key as a flat background
    bg_path = _resolve_scene_background(product, campaign_message, market, audience, work_hero, idx)
    compose_creative(
        hero_path=bg_path,
        out_path=iso_path,
        message=asset["headline"],
        ratio_key=asset["ratio"],
        product_layer=packshot,          # NEW compose param, section 3
        retailer_logo=_resolve_retailer_logo(brief, market),  # section 4
    )
    hero_source = "dam:packshot-composite"
else:
    # existing generated-scene path (L478 onward) unchanged
    ...
```

the enhance step (L489) applies to the background only when in product-composite mode; the packshot itself must NOT be contrast/texture-mutated (it is a fixed brand asset). the post-render cohesion check (`_cohesion_check`, L394) runs unchanged on the final ISO.

## 2. SKU -> packshot data contract

extend the existing `data/products/sku-photo-map.json` — do not create a new file. add a `packshot_key` field to each entry and (where known) a `lifestyle_keys` alias. keep `photo_key`/`fallbacks` as the lifestyle-background source so nothing regresses.

extended entry shape (backward compatible — new fields optional):

```json
{
  "map": {
    "<sku-handle>": {
      "caption": "…",
      "channel": "blog",
      "packshot_key": "brands/kodiak/raw-ingest/kodiakcakes/images/705599XXXXXX_<box>.jpg",
      "lifestyle_keys": [
        "brands/kodiak/raw-ingest/kodiakcakes/images/<lifestyle-1>.jpg"
      ],
      "photo_key": "brands/kodiak/raw-ingest/kodiakcakes/images/<lifestyle>.jpg",
      "fallbacks": ["…"],
      "image_file": "…",
      "matched": true,
      "score": 129.0
    }
  },
  "metadata": { "packshot_source": "705599* UPC-prefixed boxes", "…": "…" }
}
```

field semantics:

- `packshot_key` — full verbatim DAM key to the real product BOX image (`705599*`). the box layer. REQUIRED for product-composite mode to trigger
- `lifestyle_keys[]` — real DAM lifestyle scene keys usable as the composited background (superset/alias of `photo_key`+`fallbacks`; may be omitted, resolver falls back to `photo_key`/`fallbacks`)
- `caption` — unchanged
- existing fields (`photo_key`, `fallbacks`, `channel`, `image_file`, `matched`, `score`) — unchanged

### new resolver: `dam.py :: resolve_packshot(product_id) -> Optional[Path]`

place alongside `fetch_dam_key` (L201). it MUST read the manifest first (unlike `find_hero_asset`). fallback chain, in order:

| step | source                                      | mechanism                                                                                        |
| ---- | ------------------------------------------- | ------------------------------------------------------------------------------------------------ |
| 1    | manifest `packshot_key`                     | `fetch_dam_key(packshot_key, /tmp/kodiak-assets/packshot/<name>)` (verbatim key, no prefix join) |
| 2    | manifest `fallbacks[]` that look like boxes | same `fetch_dam_key` per candidate                                                               |
| 3    | fuzzy glob                                  | existing `find_hero_asset(product_id, dam_root)` (S3 prefix + local glob)                        |
| 4    | none                                        | return `None` -> caller falls to generated-scene mode                                            |

handle normalization: the resolver must normalize the incoming `product_id` to the map handle (lowercase, spaces -> hyphens) so "chocolate fudge" matches `chocolate-fudge-brownie-*`. reuse the slug logic already in generate.py `_find_source_asset` (L377). where one product_id maps to multiple box variants (mix vs power-cup), prefer exact-handle match, then longest-prefix match.

the map loader already exists (`generate.py :: _load_sku_photo_map` L240, `_resolve_map_path` L218 with `$SKU_PHOTO_MAP_PATH` env + repo + packaged candidates). `resolve_packshot` should reuse that loader (import it or lift it to a shared module) rather than re-reading the file, to keep one cache + one path-resolution policy.

## 3. product-box compositing (compose.py)

add an optional `product_layer: Path | None = None` param to `compose_creative` (current signature L84 already carries `brand_logo`, `brand_colors`, `retailer_logo`). when set, composite the verbatim box after the background fill (L114) and before the message bar (L138), so text and accent bar stay on top.

placement + treatment (deterministic, token-friendly):

- scale: contain to `min(W*0.62/box_w, (H*bar_top_frac)*0.72/box_h)` so the box sits in the upper safe area above the message bar (`bar_top = H*0.68`) without ever crossing it. box occupies roughly the same vertical band the current fg hero uses (paste anchor near `H*0.08`), horizontally centered
- drop shadow: soft offset (`+8px, +8px`, gaussian blur ~12px, ~40% black alpha) rendered on an RGBA scratch layer, composited under the box, so the box reads as a physical object over the scene
- safe-area: box bottom edge must stay >= 24px above `bar_top`; box top >= `logoOffset` (token, default 24px) below the KODIAK bear logo slot (top-left). never overlap the accent bar or footer
- the box is `alpha_composite`/`paste`d verbatim — NO cover-fit, NO scrim blend, NO enhance. the whole point is that a real box cannot render as bread or candy

compose-mode flag: expose behavior as `product_layer` being non-None (on) vs None (off). callers in product-composite mode pass the packshot; generated-scene mode passes None and the current fg-hero paste (L114) stands. document the flag in the compose_creative docstring.

## 4. retailer lockup

reuse the existing machinery — do not build a parallel one:

- resolution: `retailers.py :: resolve_retailer(name)` (aliases costco/publix/target, `LOGO_DIR = input_assets/retailer-logos/`), degradation via `lockup.py :: compose_retailer_lockup` (svg -> png -> text band)
- asset convention: **keep** `input_assets/retailer-logos/<retailer>.svg` (vector preferred) with `<retailer>.png` raster fallback. the intake brief's `brands/kodiak/logos/retailers/<retailer>.png` is a reasonable DAM S3 mirror location, but the in-code convention is the local `input_assets/retailer-logos/` dir — if a DAM-hosted source is desired, add it as a fetch step that caches INTO `input_assets/retailer-logos/`, keeping the resolver contract unchanged
- activation: only when the brief/market carries a retailer. wire `_render_asset` to derive the retailer from the brief (normalize via `retailers.normalize_retailer`) and pass either `retailer_logo=<resolved path>` into `compose_creative` (L84 param, currently never passed) OR post-process the ISO through `compose_retailer_lockup`. prefer the single `compose_creative` path so all layers land in one pass; `compose_retailer_lockup` remains the standalone/address-band variant
- placement: bottom-right, ~18% width, white backing, kept inside `bar_top+20 .. H-8` — this is already implemented at compose.py L182-203, just unreached
- **SOURCE GAP (separate deliverable):** zero retailer logos exist in the DAM today (only kodiak-bear.png + kodiak logos). `retailers.missing_logos()` will list all three (costco/publix/target) as missing. sourcing the vector marks is a distinct task from this pipeline PR. until sourced, `compose_retailer_lockup` degrades to a clean text band (retailer name + optional store address) — acceptable interim, not the target state

## 5. accuracy win (structural, not incidental)

compositing a verbatim box structurally eliminates the "wrong food" class of defect. a pasted `705599*` box image cannot render as white bread or candy because no generative step touches those pixels. this is why product-composite must be precedence-a, not an equal-weight option — generated scenes are the fallback, the real box is the default whenever one resolves. target: the actual Kodiak box appears in the frame at least whenever a packshot resolves for the SKU

## exact change set for the PR

| file                                  | function / region                                                | change                                                                                                                                                     |
| ------------------------------------- | ---------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `data/products/sku-photo-map.json`    | every `map` entry                                                | add `packshot_key` (705599\* box key) + optional `lifestyle_keys[]`; link the 215 boxes to their SKUs; keep existing fields                                |
| `src/creative_automation/dam.py`      | new `resolve_packshot(product_id)` near `fetch_dam_key` (L201)   | manifest-first resolver; chain packshot_key -> fallbacks -> `find_hero_asset` fuzzy -> None; handle normalization                                          |
| `src/creative_automation/campaign.py` | `_render_asset` (L455-522), branch before `generate_hero` (L478) | precedence: product-composite when packshot resolves, else existing generated-scene; pass `product_layer` + `retailer_logo` into `compose_creative` (L505) |
| `src/creative_automation/compose.py`  | `compose_creative` (L84)                                         | add `product_layer: Path                                                                                                                                   | None`param; composite verbatim box with drop shadow + safe-area above`bar_top`; wire the already-present `retailer_logo` path |
| `src/creative_automation/generate.py` | `_load_sku_photo_map` (L240) / `_resolve_map_path` (L218)        | reuse from `resolve_packshot` (shared loader/cache); no behavior change to generate_hero itself                                                            |
| retailer logo assets                  | `input_assets/retailer-logos/*.svg`                              | SEPARATE deliverable — source costco/publix/target vectors; not in this PR                                                                                 |

## ordered resolution precedence (the contract, one place)

1. product-composite: `resolve_packshot(product_id)` resolves -> composite verbatim box over scene/lifestyle background
   - packshot source order: manifest `packshot_key` -> manifest `fallbacks[]` -> fuzzy `find_hero_asset` -> (none)
2. generated-scene: no packshot -> existing `generate_hero(...)` unchanged
3. retailer lockup layer applied on top when brief/market carries a known retailer (interim: text band until logo assets sourced)
4. deterministic text overlay (message bar, headline, footer, accent bar) always applied last — unchanged

read-only spec. implementation lands via the pipeline team's PR against `creative-automation-pipeline`.
