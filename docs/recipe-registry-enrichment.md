# Recipe catalog enrichment runbook

How to complete a placeholder record in `data/recipes/kodiak-recipes.json`
without inventing anything. Learned across the September 2026 check fires.

## Where content may come from (never invent)

1. The brand's own blog page (`kodiak_page`) `Recipe` data block:
   ingredients, steps, times, yield, dish photo. Parse the saved page,
   don't retype by hand.
2. If the page is gone (savory-waffles returns 404) the record stays a
   one-line placeholder.
3. Product taxonomy pages (flapjacks-buttermilk) are not recipes; they
   get no times, no serving count, no enrichment.

## Field rules (catalog law)

- `prepTime`/`cookTime`: `"N mins"` text; bare digits ONLY where the
  brand page gives bare digits (single-serve oatmeal cups: `"5"`/`"1"`).
  Card meta bars print values word-for-word, so a bare `10` ships as
  "Prep: 10". See `scripts/seed_recipe_card_meta.py` (2026-09-15, the
  earlier sanctioned pass: page data block and visible labels must agree).
- `product`: exact catalog strings (`KODIAK® ...` forms included).
  Fix wrong-mix records (Buttermilk stamped on Pumpkin/Cinnamon-Oat
  recipes), but know product words feed overlap matching — re-run the
  check script after any change.
- `ingredients`: decode HTML entities, split `\r\n` junk lines, drop
  blank lines; keep section headers (`Donuts:`, `Glaze:`); drop chef's
  asides (`*Pro Tip:` lines are not ingredients).
- `base`: `"; ".join(ingredients)` — deterministic, no invention.
- `image`: repo-relative file path ONLY
  (`web/.../assets/recipe-heroes/`); the card renderer displays local
  files and never downloads web addresses, so a web address buys only
  overlap-tiebreak bias, never a displayed photo. Load every downloaded
  photo and look at it before wiring. Check any web address with a
  request first (chicken-parmigiana's brand-server photo returned 404).
- `featured_for`: each entry must name produce the recipe is actually
  built on — curation decides matching, so a loose entry reroutes months.

## Draft honesty

Hand-written records must carry all three untested markers
(`[DRAFT - UNTESTED]` description prefix, `draft-untested` tag, author
containing "untested") so unpublished recipes stay distinguishable from
kitchen-tested ones. A draft holding a season-table slot (pear-spice,
winter) is a product smell — flag it, don't decorate it.

## Copies and known staleness

- `kodiak-recipes.jsonl` is a training-table export with no generating
  script in the repo and no in-repo reader (only the id-parity test).
  About 69 of 503 rows are stale (brand-server photo prefixing, older
  renames). Do NOT hand-edit rows — rebuild only with an authoritative
  renderer or leave the file alone.
- Round-trip rule for full-file rewrites: `json.dump(indent=2,
  ensure_ascii=True)` writes back byte-identical; `ensure_ascii=False`
  rewrites every accented character. Prefer span-scoped edits for single
  records.

## Verify every enrichment fire

1. `python3 /tmp/qa_sweep.py` — zero failures, no new repetition warnings.
2. `uv run pytest tests/test_season_pairing.py tests/test_recipe_card.py`
   (full suite for product/wording changes).
3. Regen `recipe_cards_emit` when picks OR card meta change; the emit
   embeds both. Deploy only on a clean tree.
