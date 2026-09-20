# Season-26 pairings (gh #313)

The seasonal dropdown offers 26 options (12 months + 4 seasons + 10 holidays).
Every option resolves through `src/creative_automation/season_pairing.py` to a
real record in `data/recipes/kodiak-recipes.json` — none lands on the static
default (`apple-cinnamon-compote`).

## Months → season keys (mechanical)

Each month reuses its meteorological season's table entry:

| Months | Season key | Record |
|---|---|---|
| January, February, December | winter | pear-spice-muffins-draft |
| March, April, May | spring | single-serve-lemon-ricotta-flapjack-cup |
| June, July, August | summer | cherry-pie-bars |
| September, October, November | fall | pumpkin-oat-muffins |

## Holidays → dedicated pairings

Curated per record name plus occasion judgment. Reasons stay name-based — no
invented ingredients (several records carry only a name/category).

| Holiday | Record | Reason |
|---|---|---|
| Christmas | christmas-tree-waffles | Christmas Tree Waffles is the catalog's Christmas-named waffle record |
| Holiday season | holiday-sugar-cookies | Holiday Sugar Cookies is the catalog's holiday-named cookie record |
| Halloween | baked-halloween-doughnuts | Baked Halloween Doughnuts is the catalog's Halloween-named record |
| Easter | easter-egg-pancakes | Easter Egg Pancakes is the catalog's Easter-named pancake record |
| Thanksgiving | pumpkin-pie | Pumpkin Pie is the catalog's harvest pie for the Thanksgiving table |
| Fourth of July | smores-brookies | S'mores Brookies is the catalog's campfire cookout record for the Fourth of July |
| Memorial Day | grilled-peaches-and-granola | Grilled Peaches & Granola is the catalog's grill-out record for Memorial Day |
| Labor Day | single-serve-s-mores-brownie | Single-Serve S'mores Brownie is the catalog's campfire record for the Labor Day cookout |
| Valentine's Day | berry-chia-pudding | Berry Chia Pudding is the catalog's berry breakfast record for Valentine's Day |
| New Year | apple-cider-donuts | Apple Cider Donuts is the catalog's cider record for the New Year toast |

## Honesty notes

- Holiday records are thin (most carry name/category only; `berry-chia-pudding`
  and `single-serve-s-mores-brownie` are full). Pairing reasons therefore cite
  the record name, never contents. Full records are never truncated into the
  preview tease — the tease keeps its static shape while the panel names the
  pairing (`tests/test_preview_campaign_data.py` pattern).
- Garbage (unknown strings, blanks, non-strings) lands on the static default
  quietly — never raises, never claims a table hit.
- Frontend `market-disclosure.js` prunes any option outside the paired set;
  `tests/test_season_26.py::test_dropdown_audit_every_option_resolves_or_is_pruned`
  parses the dropdown arrays and fails if any offered option stops resolving.

## Verification

- `python3 -m pytest tests/test_season_26.py tests/test_season_pairing.py tests/test_preview_campaign_data.py`
- Live dev-Lambda receipts per pairing posted on gh #313.
