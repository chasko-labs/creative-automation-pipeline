# Kodiak campaign creator — coach knowledge

## Themes (chip slug: brief)
- kodiak-subscription: Kodiak subscription campaign — front-door delivery cadence for loyal households, pantry always stocked.
- localized-costco: Localized Costco campaign — bulk Family Size value for the warehouse aisle, Park City / Wasatch Back framing.
- localized-publix: Localized Publix campaign — neighborhood-market warmth for the Southern family table, framed to the selected market.
- localized-target: Localized Target campaign — everyday-family aisle value for the one-trip basket, framed to the selected market.
- recipe-cards: Recipe cards for Park City families — protein-packed whole grain recipes styled as shareable cards. Keep It Wild.
- riff-on-past-content: Riff on past content — remix our existing heroes into fresh variants across all three ratios.
- us-ski-snowboard: US Ski & Snowboard partnership (Milano Cortina 2026) — Kodiak Kitchen at the USANA Center of Excellence in Park City. Winter Wasatch athlete-fuel, podium energy. Partner-brand campaign — honor the real partnership, generic athlete imagery only, no likeness or endorsement over-implication.
- wild-grizzly-bears: Wild Grizzly Bears — lean into the KODIAK Bear, wild frontier tone, protein for epic days, Keep It Wild conservation with Vital Ground.

## Retailer copy framings (ship in the copy sidecar)
- kodiak-subscription: subscription cadence — front-door delivery, pantry always stocked
- localized-costco: bulk Family Size value — warehouse-club aisle, stock-up trip
- localized-publix: neighborhood warmth — southern family table
- localized-target: everyday-family aisle — one-trip basket, modern everyday value

## Brand standards (copy law — hard rules, never negotiable)
- the word KODIAK (all caps) never ships in copy, except inside a hashtag token
- title-case Kodiak only as Kodiak Cakes or Kodiak Park City; bare Kodiak appears nowhere
- social voice uses #kodiakcakes-style hashtags, never invented translations or frontier data
- thin-month event suggestions are UNVERIFIED until confirmed — say so plainly
- canon: tests/test_atlanta_copy_law.py, src/creative_automation/platform_copy.py

## Past social voice (observed @kodiakcakes — steer toward this)
- instagram @kodiakcakes (458,000 followers): 🐻 Feeding Epic Days and Wilder Lives 🥞 100% Whole Grains 💪 Protein-packed
- primary tags: #KodiakCakes #KeepItWild #FeedingEpicDays
- secondary tags: #VitalGround #BearBites #ProteinPacked #KodiaksFindTheGood
- post window: Morning 7-10am MT / 9-11am ET (breakfast window) + secondary evening 5-7pm MT for athlete/trail content
- recent cadence (12 observed): 2026-09-01 Reel (Leadville 100 map); 2026-08-27 Reel (blueberry muffin); 2026-08-26 Carousel
- tiktok @kodiakcakes: Kodiak Cakes — Feeding Epic Days & Wilder Lives; 100% Whole Grains; Protein-packed (mirrors Instagra
- facebook KodiakCakes:

## Context pack (deterministic grounding, fused at build)
- brand rules: no text or logo inside the image (cr-1); palette anchor Bear Brown #3B2316, Blaze Orange #E8530E, Frontier Green #1A3C34; match an existing food-subject cluster above its cohesion floor (cr-2/cr-3); iso-name every asset KODIAK-CAKES-{product}-{region}-{locality}-{channel}-{ratio}-{date}-{version}.png
- image topics (12 clusters): c0 (n=332, catalog): pancakes, power, waffles, flapjack, waffle; c1 (n=324, catalog): waffle, waffles, power, breakfast, buttermilk; c2 (n=305, catalog): ingredients, power, chocolate, cup, oatmeal; c3 (n=293, catalog): oatmeal, granola, banana, breakfast, protein; c4 (n=265, catalog): buttermilk, power, waffle, protein, flapjack; c5 (n=235, catalog): chocolate, brownie, waffle, power, cake; c6 (n=229, catalog): chocolate, cookies, chip, protein, banana; c7 (n=225, catalog): blueberry, lemon, power, cake, waffle; c8 (n=221, catalog): apple, cinnamon, power, flapjack, buttermilk; c9 (n=219, catalog): news, 0526, protein, blueberry, chocolate; c10 (n=208, catalog): cookies, power, buttermilk, waffle, flapjack; c11 (n=192, catalog): muffins, muffin, protein, desserts, prep
- sample voice 1: Sometimes your scrumptious flapjacks call for apple cinnamon compote that’s worth drooling over. Finish your homemade breakfast with a heap of spiced, tart flav
- sample voice 2: Whole grains, refined grains, and enriched grains—what’s the difference? We're breaking this down for you and talking about the benefits of whole grains.
- market languages: 82 markets, 246 localized variants

## Pipeline tools the counsel can steer toward
- 16x9: YouTube player + thumbnail base 1920x1080 → export 1280x720 JPG for thumbnails.set
- 1x1: Community post / cross-post square crop — not uploaded via videos.insert but useful for YouTube Community tab
- 9x16: YouTube Shorts 1080x1920 — 7–18s cutdown, #Shorts tag, vertical hero crop
- dam reuse: DAM hero.mp4 / hero.png at input_assets/power-cakes/ + data/raw-ingest/kodiakcakes/images/* — find_hero_asset() prioritizes DAM before generation
- compliance: src/creative_automation/compliance.py — caption, hashtag, scrim checks run per creative
- recipe cards: Nova-authored copy with deterministic fallback; card template runs in full mode

## How to steer (section map for answers)

- Step 1 "How far this reaches": scope radio — Single market, Nationwide, Full campaign (hero: every market, retailer, theme, partner variant).
- Step 2 market: market control + Location reflectors; Full campaign dims steps 2-3 (already included).
- Step 3 creative direction chips: what-to-make (recipe-cards), retailer (localized-costco, localized-publix, localized-target, kodiak-subscription), creative angle (wild-grizzly-bears, riff-on-past-content), partner (us-ski-snowboard).
- Step 5 Preview: single photographic hero; gated Generate Campaign (step 6) unlocks after first preview; step 7 Assets ships the pack.
- Timeline: Setup + 5/6/7; 5 Preview stays greyed until Create is hit.
- Rung ladder: A/B Nova+Stability, C guaranteed-real compose, D honest brand floor; provenance panel names the rung.
- Recipe cards: Nova-authored copy with deterministic fallback; card template runs in full mode.

## Answer rules for /ask

- Name the exact chip slug, market move, or brief append. Prefer toggle-chip ops.
- Never invent theme names, endpoints, or model names. Unknown topic: say so, no edits.

## Season flavors + event fallback (the "In season here" readout)

- The page resolves every market x every season to a flavor line (curated frontier
  calendars first, regional archetypes second). The /insights payload carries the
  real season + market + products + scope — ground every bullet in those, never riff
  on unselected themes.
- Thin months (archetype-tier lines, shoulder seasons): suggest checking the market's
  farmers-market page and local Facebook events for that month's anchors (harvest
  festivals, roast dates, holiday markets), and say plainly these are UNVERIFIED —
  confirm dates before shipping copy. Never invent event names, dates, or URLs.
- When asked how to get a seasonal result, name the exact move: season select value,
  market chip, or brief append (e.g. "set Season to September for peach peak").
