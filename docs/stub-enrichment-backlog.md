# Stub enrichment backlog (triaged 2026-09-22)

308 catalog records have no description and at most one ingredient line.
Each brand page address was fetched and checked for a brand recipe data block.

## Counts (corrected: first version overstated the dead)

- 122 enrichable: live brand recipe page with full data block
  (ingredients, steps, times, yield, dish photo), each schema parsed
  and validated. Listed below.
- 154 unknown: the brand site started refusing requests halfway
  through triage (first 154 catalog-order requests: 122 enrichable;
  last 154: all errors). These were never actually checked — do NOT
  treat them as dead.
- 28 likely dead: errors from before the block began, all taxonomy
  or category addresses (for example /scones and /donuts). Probably
  genuine 404s, but re-verify on the slow re-run before acting.
- 4 structural: flapjacks-buttermilk, muffins, quick-breads
  (product and collection pages, not recipes) and pancake-bites
  (points at the blog index). Leave them.

Re-triage the 154 unknown + 28 likely-dead slowly (pauses between
requests, back off on the first refused request) before enriching
past the 122 confirmed ids. Do not hammer the brand site.

## Priority

Most of the 122 never win a month cell or season-table slot (the
served ones were already enriched) — this is latent quality, not live
breakage. Enrich in small batches per the runbook
(docs/recipe-registry-enrichment.md), re-running the check script
and the emit after each batch: new ingredient words shift picks.

## Enrichable ids (machine-checked against the triage output)

acai-bowl, air-fryer-chicken-and-waffles, air-fryer-oats, almond-butter-banana-bars
angel-food-cake, apple-brown-sugar-power-waffles, apple-bundt-cake, apple-butter-pancakes
apple-cinnamon-and-oat-muffins, apple-cinnamon-compote-pancakes, apple-cinnamon-flapjack-bake, apple-cinnamon-oat-pecan-sheet-pan-flapjack
apple-cinnamon-rolls, apple-cranberry-crumble, apple-fritter-bread, apple-pie
apple-stack-cake, apple-stuffed-kodiak-blueberry-muffins, avocado-brownies, avocado-waffle-toast
bacon-flapjack-dippers, bagels, baked-fish-and-chips, baked-pear-cardamom-porridge
baked-pizza-muffins, baked-vanilla-doughnuts, banana-bread-1, banana-bread-bites
banana-chocolate-chip-muffins, banana-cream-waffle-parfait, blood-orange-chocolate-tart, blueberry-cheesecake-baked-oatmeal
blueberry-hand-pies, blueberry-scone, breakfast-enchilada-casserole, breakfast-nachos
breakfast-sausage-dippers, brownie-milkshake, brownie-trifle, caramel-apple-pie
caramel-brownie-bites, cheddar-crackers-with-garlic-herb-dip, chicken-strips-breading, chicken-waffle-sliders
chinese-scallion-pancakes, chocolate-banana-cookies, chocolate-chip-breakfast-cookies, chocolate-chip-coffee-cake-muffins
chocolate-chip-donut-holes, chocolate-covered-strawberry-brownie-cup, chocolate-covered-waffle-pops, chocolate-jelly-donut-baked-oats
churro-bites, cinnamon-pancake-french-toast, cinnamon-rolls, cobbler-topping
cookie-dough-dip, dark-chocolate-banana-bread, dark-chocolate-cherry-scones, dark-chocolate-pumpkin-cookies
double-chocolate-cookies, easter-egg-pancakes, egg-nog-cupcakes, energy-balls
flag-muffins, football-whoopie-pies, fruit-pizza, gingerbread-cookie-bars
golden-milk-pancakes, hamburger-buns, heart-filled-pancakes, heart-shaped-brownies
heart-shaped-hand-pies, heart-shaped-pizza, holiday-stuffing, holiday-sugar-cookies
hot-honey-chicken-and-waffle-casserole, huevos-rancheros-waffles, ice-cream-sandwich, kodiak-cakes-blueberry-yogurt-muffins
local-honey-pancakes, lunch-wraps, maple-bacon-donuts, mint-chocolate-brownies
mountain-berry-parfait, mozzarella-sticks, pb-j-rollup, peanut-butter-chocolate-mug-cake
pecan-pie, pizza-crust, pizza-waffles, probiotic-pancakes
protein-biscuits, protein-cookies, protein-flatbread, protein-granola
protein-packed-blueberry-lemon-waffles, protein-packed-maple-waffles, protein-pizza-dough, pumpkin-chocolate-chip-muffin-top-cookies
pumpkin-pie, pumpkin-spice-donuts, pumpkin-spice-pancakes, single-serve-lemon-poppyseed-blueberry-muffin
single-serve-quiche-lorraine-cup, smores-brookies, strawberry-jelly-roll, strawberry-pie
strawberry-shortcake-cookies, strawberry-shortcake-parfait, summer-berry-pancake-muffins, summer-fruit-bruschetta
toasted-coconut-pumpkin-donuts, trail-mix, tres-leches-cake, veggie-cheese-tart
waffle-breakfast-sandwich, waffle-cut-outs, waffle-french-toast, waffle-pb-j
wheat-rolls, white-chocolate-macadamia-nut-cookies
