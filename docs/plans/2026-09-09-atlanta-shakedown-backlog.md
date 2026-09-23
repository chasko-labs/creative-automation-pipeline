# Atlanta shakedown backlog — 2026-09-09

Source: owner's Atlanta, Georgia end-to-end test (Winter, 3 random products,
preview → full generate → export zip). Shipped first: tour, trilingual resting
copy, oatmeal-cup swap, multi-product fix, wordmarks, cover frames, gate
determinism (commit on main). Below is the decomposed remainder, in attack
order. Each unit ships independently behind the standard gates (vitest,
mapping --check, panda-parity, render gate, deploy + curl-verify).

## Standing copy laws (new — enforce in generators, not just tests)

- `KODIAK` the word is FORBIDDEN in generated copy. Logo lockups only.
  Social voice uses hashtags (`#kodiakcakes` style) or the retailer's own tags.
- Allowed namings: `Kodiak Cakes`, `Kodiak Park City`. Bare `Kodiak` nowhere.

## B — copy brand law enforcement

- Where: `src/creative_automation/platform_copy.py`, `src/creative_automation/localize.py`,
  frontend `flavorMap` (generate.js), tests `campaign-copy.test.mjs`, `copy-first-281.test.mjs`.
- What: post-generation filter + prompt-level guidance so no headline/body ships
  bare `KODIAK`; add failing-first tests with the Atlanta examples
  ("Warm Up Your Winter Nights With Kodiak" must not survive).
- Validate: pytest copy tests + vitest copy tests green.

## C — about + coach face-lift (exact, owner-dictated)

- About copy becomes: "Here to brainstorm with you through creation of a
  Kodiak Cakes campaign. Here's how things work behind the scenes:" + existing
  reference links. (Never bare `Kodiak` per the law above.)
- Coach ask box restyle; button reads "ask about this automation tool".
- Files: index.html about section, coach-about.js / coach-insights.js, CSS.
- Validate: screenshots 1600px + 390px eyeballed.

## D — preview generation path (deepest work)

- Today: preview stops at Rung A packshot-verbatim (3 squares). Must call the
  real image path per ratio (Nova Pro / Stability control-structure) so the
  preview demonstrates 1:1, 4:5, 9:16, 16:9 with composed imagery.
- Spanish + market-localized second language (Korean for Atlanta) surface IN
  the preview, not only after full generate.
- Validate: Atlanta re-test shows 4 distinct ratios + ES/KO lines in preview.

## E — recipe tease + retailer proof (preview definition of done)

- Preview must tease the requested recipe card and show retailer proof —
  Publix in Atlanta is the required DoD demonstration (Localized Publix
  theme exists in THEME_LABELS; wire it into preview output).
- Copy needs platform meat (X/Facebook voice), not just a headline + brief echo.
- Validate: Atlanta preview shows recipe tease + Publix variant.

## F — layout law: reserved real estate, no inner scrollbars

- Campaign-asset download buttons fall out of frame today. Every section
  reserves its real estate; the ONLY scrollbar is the main page scroll.
- Files: asset pack renderers (generate.js), CSS overflow audit (any
  `overflow:auto` on a section becomes layout, not scroll).
- Validate: 1600px + 390px screenshots, every button reachable without
  inner scrolling.

## G — heuristics "how it was done" restore

- The provenance/steps panel was the best part of the page and regressed away.
  Restore a heuristics readout (rung badges exist at generate.js ~line 572 —
  extend, don't reinvent): what ran, what rung, what localized, per asset.
- Validate: Atlanta generate shows the readout; vitest structural test.

## H — export pack: true campaign messaging

- Zip/csv/txt today: 4 images + weak copy sidecar (`downloadSidecar` in
  generate.js ~line 470 reads backend `copy_sidecar`/`platform_copy`).
- Must include: full campaign messaging (not headline echo), multilingual
  variants, local recipe, retailer fields as `field,value` rows in the CSV.
- Backend + frontend joint work: extend sidecar producers, keep
  `KODIAK-copy.csv` / `.txt` filenames.
- Validate: build Atlanta pack, open csv/txt, check fields per language +
  recipe + retailer rows.

## I — asset browser: thumbnails, not full files

- Owner diagnosis confirmed: the asset store grid (`prompt-chips.js` ~line 871+)
  lazy-loads via IntersectionObserver with 150px decode hints — good
  foundation, do NOT overhaul — but `data-src` is the FULL presigned file.
- Serve thumbnail variants in the grid (backend thumb URLs or resized
  derivatives); hand the pipeline the full asset only on select
  (select path at ~line 1072 already carries `url` + `key` — split into
  thumb/full).
- Reference bryanchasko.com/mom for serving patterns; learn, don't copy.
- Validate: Browse past assets opens fast on a cold cache; selection still
  composes the full file.

## J — Ideas tab: rank by strength, omit slop

- Ideas (904+) currently unranked: mock-hero slop (orange oval placeholder)
  sits beside keepers (bear cake, muffin table).
- Add a strength score to the library items (backend `/assets/library`
  response or a local curation list — prefer data over hardcoded ids where
  possible), sort strongest-first, omit below-threshold slop from the grid.
- The grayscale/sepia treatment on some ideas tiles presumably marks
  something — confirm what before changing it.
- Validate: Ideas opens with the bear/muffin keepers first, no mock ovals.

## L — adversarial coach with Apply (replaces "Why this works")

- Today `coach-insights.js` renders "Why this works" bullets that inform
  nothing and go nowhere (odd title, no campaign effect). Replace with an
  adversarial recommender: the coach critiques the CURRENT brief/market/
  season/products (off-season pick? missing retailer? weak brief?) and
  returns discrete recommendations, each with its own Apply.
- Apply (only on explicit approval per item, or apply-all) writes into the
  real controls — brief text + input event, market select + change, theme
  cards, product checkboxes — then reruns Create so the preview visibly
  changes. Reuse the resume-card-era wiring pattern (set value + dispatch
  real events so all dependents re-run); never set state behind the UI's back.
- Retitle: section reads as campaign counsel, not trivia (name TBD with owner).
- Coach endpoint contract extends `/insights` (or new action) with structured
  {recommendations:[{label, reason, patch:{brief?, market?, theme?, products?}}]}.
  Frontend applies patches through the same code paths as user input.
- No auto-apply, no auto-fetch changes (still one click, still never blocks
  Create/Download). KODIAK copy law applies to recommended brief text.
- Validate: seed a weak Atlanta brief, coach counters with Publix + recipe
  angle, Apply rewrites the brief + reruns preview; vitest asserts patch
  application via real events.
- RAG INFUSION (endpoint half — frontend already accepts the shape): the
  `/insights` backend fuses `context_pack.py` (deterministic: market,
  retailer, ingredient, languages, image clusters, sample prompts, brand
  rules — no network, no new deps) with Bedrock KB retrieval over past
  social posts + brand standards, and returns `recommendations[]` patches.
  Retrieval mode `retrieve` (raw chunks, custom prompt via Converse with
  explicit maxTokens) keeps the design-director voice under our control;
  KB needs S3-backed ingestion with GetObject/ListBucket on its role.
  Sources in-repo: `data/vectors/` embeddings, `references/` inventory,
  `scripts/embed-*.py`. Frontend renders server patches preferred, local
  rules as fallback — already implemented in `coach-counsel.js`.

## K — Recipes means recipe cards

- The `recipes` tab currently holds food/table/kitchen photography — those
  belong in `food`/`table`/`kitchen` (new tabs or lifestyle sub-filters).
- `Recipes` must mean recipe cards: ingredients-as-listed cards. Develop the
  recipe-card pipeline output (design + data) so real cards display among
  past assets. This is the important part — don't stub it.
- Validate: Recipes tab shows ingredient-listed cards; food photography
  lives under its own taxonomy.

