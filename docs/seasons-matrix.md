# seasons matrix — canonical seasons for the cards matrix

Every `seasonal_moment` in `data/localization/retailer-frontier-pairs.json`
carries `seasons` (1-3 canonical codes) and `months` (month numbers). The
244 free-text moment names collapse to these 11 canonical seasons, so the
cards matrix can group, filter, and campaign by season instead of by
un-normalized strings ("Thanksgiving" vs "Thanksgiving / winter holidays"
vs "Thanksgiving/winter" are all the same season now).

## canonical seasons

| code | label | months | holidays |
| --- | --- | --- | --- |
| DEEP_WINTER | Deep winter | Jan-Feb | — |
| MARDI_GRAS | Mardi Gras season | Feb | Mardi Gras |
| MAPLE | Maple / sap run | Feb-Mar | — |
| SPRING | Spring | Apr-May | Easter |
| EARLY_SUMMER | Early summer | Jun | — |
| HIGH_SUMMER | High summer | Jul | July 4th |
| LATE_SUMMER | Late summer | Aug | — |
| FALL_HARVEST | Fall harvest | Sep-Oct | Halloween |
| THANKSGIVING | Thanksgiving | Nov | Thanksgiving |
| WINTER_HOLIDAYS | Winter holidays | Dec | Christmas |

Coverage (350 moments, 2026-09-15): FALL_HARVEST 155, WINTER_HOLIDAYS 128,
DEEP_WINTER 111, HIGH_SUMMER 80, SPRING 69, MAPLE 69, THANKSGIVING 65,
EARLY_SUMMER 60, LATE_SUMMER 56, MARDI_GRAS 1. Zero untagged.

## tagging rule (in order)

1. Holiday keywords in the name (thanksgiving, christmas, halloween,
   easter, july 4th, mardi gras, ...).
2. Parenthesized month ranges in the name (`(Sep-Oct)`, `(Jun-Nov)`).
3. Ingredient-month join: months where that market's `monthly_ingredients`
   grow the moment's `available_ingredients` — data-driven, no guessing.
4. Bare season words (spring, high/late summer, fall, ski/winter, maple).

A moment spanning two seasons keeps both (e.g. "Deep-winter storage /
holidays (Dec-Feb)" is DEEP_WINTER + WINTER_HOLIDAYS). Status
(confirmed/proposed) is untouched — season tagging never upgrades
confidence.

## where it flows

- cards: each card's `seasonal_moment` entries now include `seasons`, so
  the matrix is season-addressable per card per month.
- recipes brainstorm snapshot (`js/recipes-frontier-pairs.js`): compact
  moments include `seasons` + `months`.
