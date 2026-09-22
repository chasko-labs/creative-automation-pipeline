# Recipe registry enrichment runbook

How to complete a stub record in `data/recipes/kodiak-recipes.json`
without fabricating. Learned across the September 2026 QA-sweep fires.

## Source hierarchy (never invent)

1. The brand's own blog page (`kodiak_page`) `Recipe` JSON-LD block:
   ingredients, steps, times, yield, hero photo. Parse the saved page,
   don't transcribe by hand.
2. If the page is gone (404, e.g. savory-waffles) the stub STAYS a stub.
3. Product taxonomy pages (e.g. flapjacks-buttermilk) are not recipes;
   they get no times/serves and no enrichment.

## Field conventions (registry law)

- `prepTime`/`cookTime`: `"N mins"` strings; bare digits ONLY where the
  source gives bare numbers (single-serve oatmeal cups: `"5"`/`"1"`).
  Card meta bars render values verbatim — bare digits ship as "Prep: 10".
  See `scripts/seed_recipe_card_meta.py` (2026-09-15, the sanctioned
  predecessor: JSON-LD + visible labels must agree, local model third check).
- `product`: exact catalog strings (`KODIAK® ...` forms included).
  Fix wrong-mix records (Buttermilk stamped on Pumpkin/Cinnamon-Oat
  recipes), but know product tokens feed overlap matching — re-run the
  sweep after any change.
- `ingredients`: clean HTML entities, split `\r\n` junk lines, drop
  whitespace-only lines; keep section headers (`Donuts:`, `Glaze:`);
  drop chef's asides (`*Pro Tip:` lines are not ingredients).
- `base`: `"; ".join(ingredients)` — deterministic, no invention.
- `image`: repo-relative local path ONLY (`web/.../assets/recipe-heroes/`);
  `_hero_panel` renders local files and ignores remote URLs, so remote
  URLs only buy overlap-tiebreak bias. HEAD-check any remote URL before
  trusting it (chicken-parmigiana's CDN photo 404'd). Spot-check
  downloaded photos on pixels before wiring.
- `featured_for`: singular/plural follows siblings; every entry must
  name produce the recipe genuinely suits — curation is matching truth.

## Draft honesty

Hand-authored records ship as `UNTESTED`: description starts
`[DRAFT - UNTESTED]`, tag `draft-untested`, author `hand-draft`.
Kitchen-test before publishing. Drafts may rotate in cells but a draft
holding a season-table slot (pear-spice winter) is a product smell —
flag it, don't polish it.

## Mirrors and known drift

- `kodiak-recipes.jsonl` is a training-table export with NO in-repo
  generator and NO in-repo consumer (only the id-parity test). It drifts:
  ~69/503 rows stale as of 2026-09-22 (product `KODIAK®` prefixing,
  older renames). Do NOT hand-edit rows to "fix" drift — rebuild only
  with an authoritative renderer or leave it alone.
- Round-trip rule for full-file rewrites: `json.dump(indent=2,
  ensure_ascii=True)` is byte-clean; `ensure_ascii=False` churns escapes.
  Prefer span-scoped surgery for single records.

## Verify every enrichment fire

1. `python3 /tmp/qa_sweep.py` — fails 0, no new repetition warnings.
2. `uv run pytest tests/test_season_pairing.py tests/test_recipe_card.py`
   (full suite for product/token changes).
3. Regen `recipe_cards_emit` when picks OR card meta change; the emit
   embeds both. Deploy only on a clean tree.
