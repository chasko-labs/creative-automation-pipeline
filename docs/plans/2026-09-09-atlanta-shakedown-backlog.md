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
