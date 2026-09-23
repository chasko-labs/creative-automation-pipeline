# zac-efron-campaign-fix-spec — serve the real licensed Zac asset, never synthesize his face

planning doc for the pipeline team. read-only over creative-automation-pipeline; no pipeline code changed by this spec. this becomes the PR the pipeline team implements.

companion to `compose-fix-spec.md` in this same directory — that spec fixed generic-box-instead-of-real-packshot by serving the real product box verbatim. this spec applies the identical serve-the-real-thing pattern to the Zac Efron campaign.

## the problem in one line

selecting the "Zac Efron" chip renders generic faceless-family output with no Zac, because the pipeline feeds a generic lifestyle photo into a generative restyle keyed on a faceless archetype persona — the real licensed Zac assets Kodiak already owns are never served.

## verified root cause (against live source, this pass)

three compounding defects, all confirmed by reading the source:

- wrong seed. `data/products/theme-asset-map.json` -> `zac-efron.photo_key` is `2023-Outdoor-Cooking-Family-Lifestyle-2051_fe0443fc-...jpg` — a generic family-lifestyle shot. the real Zac still (`2023-Cooking-with-Zac-2636_1_59086e86-...jpg`) sits buried at `pool[4]`, never selected as primary. the metadata claims an "additive athlete/lifestyle filename boost so real licensed brand-athlete photography ranks first" but the primary key is still the generic family photo.
- everything gets restyled. `generate.py :: generate_hero` (L991) resolves a seed (theme photo, else sku-mapped asset photo, else disk) then ALWAYS runs it through `_stability_control_hero` (Bedrock Stability control-structure) at the mode-3 seam (L1091). there is no serve-verbatim path. even if the real Zac photo were the primary seed, control-structure would regenerate it — losing the real likeness and honoring the faceless archetype instead.
- the archetype is faceless-by-design. `generate.py :: _THEME_PERSONA_MAP` (L116) maps `zac-efron -> "energetic athletic young man, morning-fitness lifestyle vibe"`, and `_safe_prompt_text` (L150) strips the literal name "Zac Efron" out of any incoming prompt before it reaches Stability. that name-strip is correct FOR THE GENERATION PATH (a real name trips Stability's content filter), but it is being applied universally — there is no branch that says "for zac-efron, skip generation and serve the real asset".

net effect: the campaign can only ever produce a generated faceless figure. today that figure is seeded from a family photo, so it reads as faceless kids.

### corrections to the intake brief (so the PR is not built on a wrong premise)

- the name-strip and persona logic live in `generate.py`, NOT `campaign.py`. `campaign.py` has zero references to `_THEME_PERSONA_MAP` / `_safe_prompt_text` / `zac`. the intake brief pointed at campaign.py; the actual maps are module-level in generate.py.
- there is no existing `_render_asset` seam that branches on theme for asset-serve. the serve-vs-generate decision point is inside `generate_hero`, at the mode-3 image-engine seam (L1091). that is where the new branch goes.

## fix scope

- image resolution + engine seam in `generate.py` (the serve-vs-generate branch)
- a new `zac-efron` asset manifest (data contract), mirroring `sku-packshot-map.json`
- one line of theme-asset-map primary correction (defense in depth)
- frontend chip copy + product preselect in `index.html`
- no change to the name-strip (`_safe_prompt_text` / `_THEME_PERSONA_MAP`) — it stays exactly as-is for the generation fallback path

## 1. zac campaign resolution path (the core fix)

### corrected precedence for `theme == 'zac-efron'`

precedence is serve-first, generate-only-as-fallback. the guardrail is structural: the serve path pastes real licensed pixels and never invokes a generative model on a face.

```
a. LICENSED-ASSET-SERVE  (DEFAULT, preferred)
   resolve a REAL licensed Zac still from the zac-efron asset manifest.
   composite it VERBATIM as the hero/foreground over a brand background via
   compose.py :: compose_creative(..., product_layer=<zac_still>).
   NO Stability restyle. NO img2img. NO control-structure. NO face synthesis.
   his name/likeness is fine here because these ARE the actual licensed assets,
   not a synthesis. Zac is Chief Brand Officer — his real image is a brand asset
   to serve, exactly like a product box.

b. ARCHETYPE FALLBACK  (only if no licensed asset resolves)
   the existing faceless generative path, corrected: the subject must be an
   ADULT athletic-morning-energy figure, never children. the current bug renders
   faceless kids because the fallback seed is a family-lifestyle photo AND the
   persona text does not exclude kids. fix both (see 1c).

NEVER: generate or synthesize a Zac face by any path (no generated face, no
deepfake, no img2img of his face, no control-structure on a Zac photo).
```

### where the branch goes — `generate.py :: generate_hero`, seed + engine seam

two edits inside `generate_hero` (L991-L1130):

1. seed resolution, add a serve-first check BEFORE the existing theme-photo block (currently L1053-L1069). when `theme == 'zac-efron'` (generalize to "theme has an asset-serve manifest entry"; see section 5), resolve a licensed still from the new manifest via a new `_resolve_served_asset(theme)` helper (shape mirrors `dam.py :: resolve_packshot`). if it resolves to a local path, mark provenance `seed_selection = "licensed-asset-serve"` and set a `serve_verbatim = True` flag.

2. engine seam, at the mode-3 branch (currently L1091 `if seed is not None:`). when `serve_verbatim` is set, bypass `_stability_control_hero` and `_compose_scene` entirely. instead call `compose.py :: compose_creative(hero_path=<brand_bg>, product_layer=<zac_still>, message=<headline>, ratio_key=ratio, ...)` so the real Zac still is pasted verbatim (drop shadow, no cover-fit, no scrim, no enhance) over a brand background. set provenance `engine = "asset-serve-composite"`, `model = "pillow:compose-creative"`, source a new `SERVE_SOURCE = "dam:licensed-asset-serve"`.

the existing theme-photo -> sku-dam -> disk seed chain and the Stability restyle stay untouched for every non-served theme. the fallback (1b) is reached only when `_resolve_served_asset` returns None: seed falls through to the existing chain and restyles as today.

### 1c — correct the faceless fallback (so it is an adult, never kids)

for the fallback-only path, two corrections:

- `_THEME_PERSONA_MAP["zac-efron"]` — keep the name-strip behavior, but make the archetype explicitly adult and exclude children. proposed: `"solo adult athletic man in morning trail-fitness moment, active-lifestyle energy, no children, no family group"`. (used only when generation runs, i.e. no licensed asset resolved.)
- add a `_THEME_SCENE_HINT["zac-efron"]` entry (the map at L126 currently has no zac entry, only `us-ski-snowboard`). proposed scene: `"Wasatch morning trailhead, single adult athlete fueling before the climb, cast-iron protein stack, active-lifestyle energy, generic adult figure only (no children, no real person, no face focus), on-brand Kodiak"`. this folds into both the Nova Pro art-director prompt and the deterministic fallback prompt so the fallback lands adult-and-active even offline.

the name-strip (`_safe_prompt_text`, L150) is NOT changed. it continues to strip "Zac Efron" from any free-text prompt headed to Stability. the serve path never touches Stability, so the real name/likeness on the served asset is unaffected by it.

## 2. zac-efron asset manifest (data contract)

new file, mirroring `docs/architecture/compose-fix/sku-packshot-map.json`. proposed path `data/products/zac-efron-asset-map.json` with an env override `ZAC_ASSET_MAP_PATH` for the Lambda/test layout (same 3-candidate resolve pattern as `_resolve_packshot_map_path`).

shape:

```json
{
  "$schema_note": "Licensed Zac Efron (Kodiak Chief Brand Officer) real-asset manifest. SOURCE data that lets the zac-efron campaign SERVE the real licensed still verbatim instead of generating a faceless archetype. Guardrail: these are the actual licensed assets — served, never synthesized. No generative model is ever run on a Zac face.",
  "provenance": {
    "dam_bucket": "chasko-creative-dam-946179428633-us-east-1",
    "prefix": "brands/kodiak/raw-ingest/kodiakcakes/images/",
    "future_prefix": "brands/kodiak/zac-efron/",
    "note": "additional licensed Zac video stills from the LTO ceros page land at future_prefix in a separate infra-blocked task; this manifest accommodates them by appending to licensed_stills[] / video_posters[]"
  },
  "map": {
    "zac-efron": {
      "role": "Chief Brand Officer",
      "licensed_stills": [
        "brands/kodiak/raw-ingest/kodiakcakes/images/2023-Cooking-with-Zac-2636_1_59086e86-8776-4fbe-980a-9167bc5e19fb.jpg",
        "brands/kodiak/raw-ingest/kodiakcakes/images/ea373ffadae2--2024-Zac-Waffle-Nachos-2992-1-1-3eb394_8b59e8.jpg"
      ],
      "video_posters": [],
      "signature_asset": null,
      "persona_card": null,
      "serve_confidence": "high",
      "background_keys": [
        "brands/kodiak/raw-ingest/kodiakcakes/images/2020.8_Idaho_Wheat_Fields_00063_0bb83592-...jpg"
      ],
      "caption": "Zac Efron, Kodiak Chief Brand Officer"
    }
  }
}
```

field notes:

- `licensed_stills[]` — the real asset keys served verbatim as the foreground. both keys above are confirmed present (the first is already in the theme-asset-map pool; the second is per the intake brief). `_resolve_served_asset` walks these in order, first `fetch_asset_key` hit wins.
- `video_posters[]` — empty now; populated after the ceros grab lands licensed stills at `brands/kodiak/zac-efron/`. resolver treats them as additional `licensed_stills` candidates.
- `signature_asset` — his signature graphic, pending grab. null now; when present, an optional overlay layer (a second `compose_creative` paste in a corner slot).
- `persona_card` — the UX business card being made separately. null now; consumed by the frontend persona subtitle (section 4), not by image generation.
- `background_keys[]` — brand backgrounds the licensed still composites over (wheat field / Wasatch dawn). optional; if empty, `compose_creative` uses its default brand background.
- `serve_confidence` — `high` = confirmed licensed asset present; `medium` = variant; `null` = none, forces the archetype fallback.

## 3. LTO default-flavor logic

when the zac-efron chip is selected, product selection auto-defaults to the LTO oatmeal flavor Zac crafted — "Apple Brown Sugar Pecan Fruit & Nuts oatmeal" (crafted with Zac Efron) — until the user explicitly picks other products or ingredients.

### where it wires — `web/kodiak-posts-for-todays-frontier/index.html`

the chip click handler (IIFE, L1541-L1553) currently sets `briefEl.value` and `window.__activeTheme` but preselects no product. add a per-chip product-preselect step:

- extend each chip with an optional `data-preselect="<product-name>"` attribute; for the zac chip set `data-preselect="Maple Pecan Overnight Oats"` (the closest catalog match today — see the SKU flag below).
- in the click handler, after setting the theme, if `data-preselect` is present, check the matching `#productChooser .sku-check` whose `value` equals that product NAME (checkbox `value` is the product name, not the handle — confirmed at render, L912, and read at L1152). if the catalog has not yet painted that row (it slices to the first 12, L912), re-run `render()` with a filter of the product name first so the row exists, then check it.
- the preselect must be soft: a manual product change or brief edit already clears the theme via `__clearActiveTheme` (L1527) and the productChooser `change` handler (L1562). the preselect only sets the initial default; the user overrides freely.

product handle to preselect today: `maple-pecan-overnight-oats` (name "Maple Pecan Overnight Oats", UPC 705599020797, catalog L1473). `slugify()` (L1170) maps the checked name to this handle via `window.skuCatalog`.

brief text: the corrected chip `data-brief` (section 4 copy options) should reference "crafted with Zac Efron" so the default brief carries the LTO framing until the user overrides.

### SKU flag (needs pipeline-team decision)

the exact "Apple Brown Sugar Pecan Fruit & Nuts" LTO SKU does NOT exist in `data/products/kodiak-full-catalog.json`. the closest match is `maple-pecan-overnight-oats`. two options:

- interim: preselect `maple-pecan-overnight-oats` (pecan-adjacent, real SKU, ships today).
- correct: add the real LTO entry to `kodiak-full-catalog.json` (`handle: apple-brown-sugar-pecan-fruit-nuts-oatmeal` or the real Shopify handle once known, with real UPC + images), then flip `data-preselect` to that name. this is the accurate long-term wiring.

secondary flag: the `maple-pecan-overnight-oats` catalog `description` field is junk — it holds a store-policy Q&A blurb, not a product description. worth a cleanup pass, but out of scope for this fix.

## 4. copy fix

the chip at `index.html:480` currently sets:

```
data-brief="Zac Efron athletic-morning energy — high-protein pre-trail fuel, aspirational active lifestyle. Keep It Wild."
```

this reads as if the campaign IS his energy. rewrite so it reads as HIS fuel, and reflect his Chief Brand Officer role. options (pick one; all correct the framing and the LTO context):

- option A (recommended): `Zac Efron, Kodiak Chief Brand Officer — his athletic-morning fuel: high-protein pre-trail energy, aspirational active lifestyle, crafted with Zac. Keep It Wild.`
- option B: `Featuring Zac Efron, Kodiak Chief Brand Officer — the LTO oatmeal he crafted, high-protein pre-trail fuel for the aspirational active life. Keep It Wild.`
- option C: `Zac Efron for Kodiak (Chief Brand Officer) — his morning trail fuel: high-protein, whole-grain, crafted-with-Zac LTO. Keep It Wild.`

also:

- chip label + `THEME_LABELS['zac-efron']` (L1183) currently read "Zac Efron". consider "Zac Efron — CBO" or leave label short and carry the CBO role in the persona subtitle.
- persona subtitle (fed by `persona_card` once the UX business card lands, section 2) should state his Chief Brand Officer role.

## 5. tailored-layer logic (per-theme asset-serve overrides)

generalize the Zac fix into a reusable pattern: the pipeline supports per-theme "asset-serve" overrides that BYPASS generic generation when the brand owns the real thing.

- the serve-vs-generate decision in `generate_hero` (section 1) keys on "does this theme/product have an asset-serve manifest entry", not a hardcoded `== 'zac-efron'`. `_resolve_served_asset(theme)` returns a local path or None; None falls through to the existing generative chain.
- composition mechanism is the existing `compose.py :: compose_creative(..., product_layer=...)` verbatim-paste (drop shadow, no cover-fit, no scrim, no enhance). controlnet/img2img are explicitly NOT used on served assets; the layering is a deterministic Pillow composite over a brand background. (controlnet/img2img remain available only on the generative fallback path, never on a served real asset.)
- the first two asset-serve members are already real: product packshots (`resolve_packshot`, the compose-fix) and now licensed-person assets (Zac). a third candidate is `bears` — real conservation wildlife stills served verbatim rather than restyled, same manifest shape, same serve-first branch. the bears theme already carries a captive-bear-closeup guardrail in theme-asset-map; an asset-serve manifest would let it serve vetted wild-habitat stills directly.

## exact change set for the PR

| file                                              | change                                                                                                                                                                                                                                                                             |
| ------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/creative_automation/generate.py`             | add `_resolve_served_asset(theme)` (mirror `dam.py :: resolve_packshot`); in `generate_hero` L1053+ add serve-first seed check + `serve_verbatim` flag; at mode-3 seam L1091 bypass Stability and call `compose_creative(product_layer=...)` when served; add `SERVE_SOURCE` label |
| `src/creative_automation/generate.py`             | correct `_THEME_PERSONA_MAP["zac-efron"]` (L116) to adult/no-children; add `_THEME_SCENE_HINT["zac-efron"]` (L126) — fallback path only                                                                                                                                            |
| `data/products/zac-efron-asset-map.json`          | NEW manifest (section 2 shape)                                                                                                                                                                                                                                                     |
| `data/products/theme-asset-map.json`              | flip `zac-efron.photo_key` primary to the real Zac still (defense in depth for the fallback seed)                                                                                                                                                                                  |
| `web/kodiak-posts-for-todays-frontier/index.html` | L480 chip: corrected `data-brief` (section 4) + `data-preselect="Maple Pecan Overnight Oats"`; L1541 handler: check the preselected product; optional CBO label/subtitle                                                                                                           |
| `data/products/kodiak-full-catalog.json`          | (decision) add the real Apple Brown Sugar Pecan LTO SKU, else keep maple-pecan interim                                                                                                                                                                                             |

## ordered resolution precedence (the contract, one place)

for `theme == 'zac-efron'` (and any asset-serve theme):

```
1. _resolve_served_asset(theme) resolves a licensed still
     -> compose_creative(product_layer=<still>) over brand background, VERBATIM
     -> source dam:licensed-asset-serve, engine asset-serve-composite
     -> NO Stability, NO img2img, NO face synthesis
2. no licensed asset resolves
     -> existing seed chain (theme photo -> sku-dam -> disk)
     -> Stability control-structure restyle on the ADULT active-lifestyle
        archetype (corrected persona + scene hint), name-stripped
     -> source bedrock:stability-control-structure
3. Stability unavailable
     -> Pillow _compose_scene on the same seed (unchanged)
4. no seed at all
     -> _mock_hero placeholder (unchanged)
```

## guardrail confirmation

the likeness guardrail holds structurally, not by policy text: the serve path (step 1) pastes real licensed pixels through a deterministic Pillow composite and never invokes any generative model on a face. the name-strip and faceless-archetype logic are untouched and continue to protect the generation fallback (step 2), where no real Zac asset is present. there is no code path in this design that generates, deepfakes, or img2img's a Zac face. serve the real licensed asset; never synthesize the face.
