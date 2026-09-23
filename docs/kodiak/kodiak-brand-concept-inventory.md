# kodiak-brand-concept-inventory

full brand-concept audit of kodiakcakes.com and the scraped brand-lore/social corpus, mapped to concrete creative-automation-pipeline adoption actions. read-only planning doc. no pipeline code changed here. this becomes the source-of-truth inventory the pipeline team pulls from.

- target brand: kodiak cakes (kodiakcakes.com, shopify store `kodiakcakes.myshopify.com`)
- our pipeline repo: `chasko-labs/creative-automation-pipeline`
- our front end: `web/kodiak-posts-for-todays-frontier/index.html`
- scraped corpus: `~/code/chasko-labs/creative-automation-pipeline/data/raw-ingest/kodiakcakes/`
- asset store bucket for served assets: `chasko-creative-dam-946179428633-us-east-1`, prefix `brands/kodiak/raw-ingest/kodiakcakes/images/`
- companion specs already in this dir: `compose-fix-spec.md` (serve real packshots), `zac-efron-campaign-fix-spec.md` (serve real Zac assets)

confirmed vs inferred is marked per line. no hex or font is asserted without a source. anything unverified says so.

## methodology (second, per english-writing-standards)

- read our own token source of truth `web/kodiak-posts-for-todays-frontier/design/tokens/kodiak.json` and the compiled `design/styles.css`
- read the scraped brand-lore text extractions (`data/raw-ingest/kodiakcakes/brand-lore/*.txt`), the scraped mission + keepitwild pages, the scraped LTO oatmeal page raw HTML (`pages/135_pages_lto-oatmeal.html`), and the full scraped image inventory (`images/`)
- cross-referenced live web sources (forbes, vitalground.org, utahbusiness, ksltv) for Zac Efron CBO and Keep It Wild / Vital Ground facts
- the ceros LTO microsite could not be rendered (JS/canvas shell only over `web_fetch`) — flagged in the asset section

confidence key: `confirmed` = verified against live site, scraped raw HTML, or our own token file. `inferred` = reasonable from corpus but not directly sourced. `unconfirmed` = could not verify this pass.

## top brand concepts and pipeline actions (summary matrix)

| #   | concept                                                   | where it appears (source)                                                                              | pipeline action                                                                                                                              | confidence                 |
| --- | --------------------------------------------------------- | ------------------------------------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- |
| 1   | growling bear-head mark / "bear sightings" motif          | ceros CDN bear-head png; logo_256x256 logomark in corpus; newsletter "recent bear sightings at Kodiak" | add bear-head as optional `compose.py` brand overlay layer (corner lockup), gated by a `bear_overlay` flag; a "bear sightings" motif variant | confirmed                  |
| 2   | Keep It Wild conservation program + Vital Ground co-badge | vitalground.org partnership pages; brand-lore FAQ; nav "Keep it Wild"                                  | add a Keep It Wild footer lockup variant + optional Vital Ground co-badge overlay; wire to a `conservation` campaign flag                    | confirmed                  |
| 3   | Zac Efron Chief Brand Officer treatment                   | forbes/utahbusiness/nosh; scraped LTO page; corpus Zac stills                                          | CBO persona-card template; serve real licensed Zac stills verbatim (see `zac-efron-campaign-fix-spec.md`)                                    | confirmed                  |
| 4   | athlete roster treatment                                  | `blogs/athletes/*` scraped; 14+ athlete stills in corpus                                               | athlete persona-card template (name + discipline + real still), same serve-verbatim pattern as CBO                                           | confirmed                  |
| 5   | LTO (limited-time-offer) product pattern                  | scraped `pages/lto-oatmeal.html`; ceros microsite; "crafted with Zac"                                  | LTO layout preset: "crafted with [athlete/CBO]" ribbon + signature slot + LTO badge; ceros-style hero                                        | confirmed                  |
| 6   | brand color system                                        | our `design/tokens/kodiak.json`; live LTO page inline CSS                                              | keep bearBrown/parchment/oatmeal; reconcile accent (live uses signal red `#b51e14`, our token uses blaze orange `#E8530E`)                   | confirmed (see color note) |
| 7   | typography / type treatment                               | live typekit `zjt4wyq.css`; corpus font files; our index.html                                          | headline gin (uppercase, tracked), body museo-sans, roar/kodiak_sans UI; FIX stale token typography block                                    | confirmed                  |
| 8   | voice / taglines                                          | mission page, newsletter, brand-lore, LTO meta                                                         | tagline library keyed to campaign type; footer + headline copy presets                                                                       | confirmed                  |
| 9   | brown-kraft-box packaging identity                        | graphicpkg case study; "brown box with the growling bear"                                              | keep kraft procedural texture; ensure real box packshots served (see `compose-fix-spec.md`)                                                  | confirmed                  |
| 10  | recurring photography style                               | corpus lifestyle stills (wheat, Wasatch, trail, family, cast iron)                                     | curated brand-background pool for served-asset composites; scene-hint vocabulary                                                             | confirmed                  |
| 11  | frontier / pioneer narrative + bear culture pillars       | mission page; forbes platform-brand interview                                                          | narrative vocabulary for Nova Pro art-director prompts + headline generation                                                                 | confirmed                  |
| 12  | origin story (1982 red wagon, Shark Tank, Park City)      | brand-ambassador guide; forbes; LTO schema                                                             | optional "since 1982" / heritage badge for heritage campaigns                                                                                | confirmed                  |

## 1. growling bear-head mark ("bear sightings" motif)

what it is: kodiak's core logomark is a growling kodiak-bear head. it anchors the brand and shows up as a standalone mark distinct from the wordmark. the newsletter signup copy across the site reads "be the first to hear about exclusive news, promotions, recipes and recent bear sightings at Kodiak" — a playful framing that treats the bear as a recurring character, not just a logo.

where it appears (sources):

- ceros CDN full-res mark (confirmed, provided by Bryan): `https://media.ceros.com/kodiak-cakes/images/2024/12/19/ed9cbf26e4db9cc44cfe014316fb0841/bear-head.png` — drop the `&width=` query param for full resolution
- our scraped corpus holds a bear logomark raster: `data/raw-ingest/kodiakcakes/images/logo_256x256_a145607b-6231-4f75-a693-802b2650db1f.png` (confirmed present; visual content is the small square logomark — inferred to be the bear mark from filename + dimensions, worth an eyeball before use)
- newsletter "recent bear sightings" copy: scraped `brand-lore/our-mission.txt`, `brand-lore/keepitwild.txt`, `brand-lore/ba-training-tools.txt` (confirmed)
- packaging identity "the brown box with the growling bear": graphicpkg case study (confirmed, see concept 9)

pipeline action:

- add the bear-head as an optional composable brand overlay in `compose.py` — a new layer analogous to the existing `brand_logo` param, gated by a `bear_overlay: bool | path` flag. default corner slot (top-left or bottom-right, inside the safe area, not crossing the message bar at `H*0.68`)
- expose a "bear sightings" motif variant: the bear-head peeking / partially cropped at a frame edge, matching the playful newsletter voice. this is a placement preset over the same asset, not a new asset
- serve the real mark verbatim (fetch from asset store or the ceros full-res URL), never generate a bear face — same serve-not-synthesize guardrail as the Zac spec
- confidence: confirmed for the concept and the ceros URL; the exact local logomark file should be visually confirmed before wiring

## 2. Keep It Wild conservation program (Vital Ground co-badge)

what it is: "Kodiak Keep It Wild" is kodiak's conservation campaign, started 2022, that raises money for grizzly bears and the wild habitats they live in. the framing: bears are a keystone species — protect the bear, protect the whole ecosystem. kodiak partners with the Vital Ground Foundation (grizzly habitat protection across the six designated recovery zones in the lower 48) plus a rotating artist and conservation org, producing limited-edition gear where proceeds are donated.

where it appears (sources):

- brand-lore FAQ explaining Keep It Wild + keystone-species rationale: scraped `brand-lore/kodiak-brand-lore-knowledge-base.txt` (confirmed)
- Vital Ground partnership, grizzly recovery zones, animal ambassadors (Bart the Bear II, Tank the Bear): [vitalground.org Kodiak partnership](https://www.vitalground.org/vital-ground-kodiak-cakes-grizzly-conservation-partnership/), [Kodiak + Zac Keep It Wild](https://www.vitalground.org/kodiak-zac-efron-keep-it-wild-help-grizzlies/) (confirmed; content rephrased for licensing compliance)
- artist Aaron Draplin designed Keep It Wild merch; the 2022 drop generated ~$115,000 for habitat conservation; a separate effort raised $100,000 for Montana's Rocky Mountain Front: [vitalground.org — Kodiak Commits in a Big Way](https://www.vitalground.org/kodiak-helps-keep-it-wild-zac-efron/), [furthers investment](https://www.vitalground.org/kodiak-cakes-furthers-investment-in-grizzly-conservation/) (confirmed; figures per Vital Ground)
- site nav carries a persistent "Keep it Wild" entry: scraped mission/keepitwild pages (confirmed)
- our own `compose.py` already puts "Keep It Wild" in the footer lockup (confirmed via `compose-fix-spec.md` reference)

campaign visual language (inferred from corpus + Vital Ground pages): rugged outdoor/wildlife photography, grizzly-country landscapes, hand-illustrated artist merch aesthetic (Draplin's bold line-art style), earth-tone palette. the scraped keepitwild page body is thin (JS-rendered), so the exact current campaign lockup art is unconfirmed and would need a browser render.

pipeline action:

- add a Keep It Wild footer lockup as a selectable footer variant (the current footer already says "Keep It Wild" — extend it to an optional full KIW lockup with the conservation framing)
- add an optional Vital Ground co-badge overlay layer, gated behind a `conservation` campaign flag, served verbatim (Vital Ground mark must be sourced — not in our corpus today, flag as a sourcing gap)
- add a Keep It Wild scene-hint vocabulary for the art-director prompt (grizzly country, wild habitat, keystone-species framing) for conservation-themed generated backgrounds
- confidence: confirmed for the program, partner, and framing; current-year campaign art is unconfirmed (browser-render blocked)

## 3. athlete / Chief Brand Officer treatment

what it is: kodiak fronts the brand with real athletes and, at the top, Zac Efron as Chief Brand Officer. Efron joined June 2022 as the company's first CBO plus board member and shareholder (kodiak was acquired by private-equity group L Catterton, reported ~$800M, 2021). the shared pitch is "food with a purpose" — real food, outdoors, giving back. Efron co-created the LTO oatmeal (concept 5).

where it appears (sources):

- Zac Efron CBO + board + shareholder: [forbes](https://www.forbes.com/sites/douglasyu/2022/06/14/zac-efron-on-joining-l-cattertons-kodiak-cakes-as-chief-brand-officer-and-board-member-it-feels-like-food-with-a-purpose/), [utahbusiness press release](https://www.utahbusiness.com/press-releases/2022/06/14/zac-efron-joins-kodiak-cakes-executive-team/), [nosh](https://www.nosh.com/food-wire/2022/zac-efron-appointed-kodiaks-newest-board-member-and-chief-brand-officer/) (confirmed; content rephrased for licensing compliance)
- athlete roster — scraped `blogs/athletes/*` pages: Courtney Dauwalter, Emily Harrington, Alex Howes, Caleb Olson, Christopher Blevins, Natalia Grossman, Keegan Swenson, Meg Fisher, plus ambassador Sierra Jewitt and speedskater Casey Dawson (confirmed via scraped page filenames)
- real athlete/CBO stills in our corpus (confirmed present, `data/raw-ingest/kodiakcakes/images/`):
  - Zac Efron: `2023-Cooking-with-Zac-2636_1_59086e86-8776-4fbe-980a-9167bc5e19fb.jpg`, `ea373ffadae2--2024-Zac-Waffle-Nachos-2992-1-1-3eb394_8b59e8.jpg`
  - Courtney Dauwalter: `Courtney-Dauwalter.jpg`
  - Christopher Blevins: `Christopher-Blevins.jpg`
  - Emily Harrington: `Emily_El_Cap_Climb_1_2_fc5a6848-...jpg`, `Kodiak_Athlete_Emily_Harrington_0525_0044.jpg`, `2020.9_Emily_Harrington_Athlete-187.jpg`
  - Alex Howes: `2022-Alex-Howes_001_1.jpg`, `Kodiak_Q1_2025_Alex_Howes_1124_0578.jpg`
  - Caleb Olson: `Kodiak_Athlete_Caleb_Olson_0825_0186.jpg`
  - Natalia Grossman: `24.7.9.Natalia.Grossman.Kodiak-67.jpg`
  - Karissa Schweizer: `2020.6_Karissa_Schweizer_Athlete-769.jpg`
  - Sam Watson: `KodiakCakes-SamWatson-Athlete.jpg`
  - Meg Fisher: `meg-fischer.png`
  - Jennifer Lichter: `Kodiak-Athlete-Jennifer-Lichter.jpg`
  - Sarah Glover (chef/ambassador): `2022_Sarah-Glover-Shoot_23_...jpg`, `2023-Sarah-Glover-Orange-Oatmeal-5573_1.jpg`

how they present partners (inferred): each athlete gets a blog profile with name + discipline + a shot of them in their sport, tied back to fueling with kodiak. CBO copy names the role explicitly ("Chief Brand Officer"). the tone is aspirational-active, not celebrity-gloss.

pipeline action:

- CBO/athlete persona-card template: a reusable layout component (name, role/discipline, real still, one-line fuel narrative). consumed by the frontend as a subtitle/card and by the composite as an optional foreground layer
- serve real licensed stills verbatim, never synthesize a face — this is already speced in detail for Zac in `zac-efron-campaign-fix-spec.md`; generalize the same asset-serve manifest pattern to the athlete roster (a `theme -> licensed_stills[]` manifest keyed per person)
- confidence: confirmed for CBO, roster, and the real stills

## 4. LTO (limited-time-offer) product patterns

what it is: kodiak runs limited-time-offer product drops on dedicated ceros microsites, with a "crafted with [name]" framing, a signature graphic, and the featured product. the current live example is the LTO oatmeal Zac Efron crafted — "Apple Brown Sugar Pecan" with his chosen ingredients (chia, pumpkin, cranberry seeds), sold exclusively at Walmart.

where it appears (sources):

- scraped LTO page `pages/135_pages_lto-oatmeal.html` — meta description (confirmed): "When you combine Zac's passion for oats and the Kodiak crew's mission to feed wilder lives, you get a hearty packet of a 'fair-winner' oatmeal. Exclusively at Walmart!"
- ceros microsite embed (confirmed URL, render blocked): `https://view.ceros.com/kodiak-cakes/lto-oatmeal-lp` — holds two Zac videos, his signature, and the LTO product per Bryan's brief
- Zac co-created the recipe with chia/pumpkin/cranberry seeds: [ksltv](https://ksltv.com/local-news/utah-based-kodiak-cakes-launches-new-oatmeal-with-help-of-chief-brand-officer-zac-efron/724098/) (confirmed; rephrased for compliance)
- the exact LTO SKU (Apple Brown Sugar Pecan) is NOT in our product catalog today — `zac-efron-campaign-fix-spec.md` flags this; closest existing SKU is `maple-pecan-overnight-oats` (UPC 705599020797, packshot present: `705599020797-Kodiak_Cakes-Maple_Pecan-Overnight_Oats-Pouch-...png`) (confirmed)

ceros microsite format (inferred): full-bleed video-led hero, scroll-driven canvas, signature overlay, single hero product, "crafted with" attribution. it is a JS/canvas experience — not scrapeable as static HTML.

pipeline action:

- add an LTO layout preset: "crafted with [athlete/CBO]" ribbon + optional signature-graphic slot (corner) + optional "limited time" / "exclusively at [retailer]" badge
- wire the LTO preset to auto-default the featured product when a CBO/athlete theme is selected (the Zac spec already details the `data-preselect` wiring in `index.html`)
- when the real LTO SKU is added to the catalog, serve its real packshot verbatim (concept 9 + `compose-fix-spec.md`)
- confidence: confirmed for the pattern and the current LTO; the ceros interior assets need a browser render (see asset section)

## 5. brand color system + typography

### color — confirmed, with one accent reconciliation

our own token source of truth (`web/kodiak-posts-for-todays-frontier/design/tokens/kodiak.json`, confirmed) defines the frontier palette exactly as Bryan's brief states:

| token          | hex       | role                                                | source                     |
| -------------- | --------- | --------------------------------------------------- | -------------------------- |
| Bear Brown     | `#3B2316` | primary — headings, backgrounds, bear-logo backdrop | our token file (confirmed) |
| Blaze Orange   | `#E8530E` | accent / CTA / protein callouts                     | our token file (confirmed) |
| Frontier Green | `#1A3C34` | secondary / evergreen / nature                      | our token file (confirmed) |
| Parchment      | `#FFF8F0` | warm paper page background                          | our token file (confirmed) |
| Oatmeal        | `#F4EDE6` | card / kraft bag                                    | our token file (confirmed) |
| Ink            | `#1A1110` | darkest text                                        | our token file (confirmed) |

the token file also carries approximate CMYK/Pantone/HSL for the three brand colors (e.g. Bear Brown Pantone 4975 C approx, Blaze Orange Pantone 1655 C approx) — these are self-described as approximate, treat as `inferred` not `confirmed`.

accent reconciliation (important, confirmed):

- the LIVE LTO page inline CSS (scraped `pages/135_pages_lto-oatmeal.html`, confirmed) uses:
  - text/primary `#382316` (a bear-brown that is ONE DIGIT off our `#3B2316` — live is `#382316`, our token is `#3B2316`)
  - background primary `#f8eddf` (parchment; close to our `#FFF8F0` but not identical)
  - primary button / signal color `#b51e14` (a deep signal RED)
  - safari pinned-tab mask color `#2c231b`
- so the live site's CTA/accent is a signal RED `#b51e14`, NOT the blaze orange `#E8530E` in our token system. our `index.html` already reconciles this with a `--colors-brand-signal-red` token aliased to `--red` and a production-red note (confirmed in index.html `:root` comments)
- takeaway: kodiak's live production palette centers Bear Brown `#382316` + parchment `#f8eddf` + signal red `#b51e14`. blaze orange `#E8530E` is a valid kodiak accent (it appears in packaging and protein callouts) but is not the live web CTA color. the pipeline should treat BOTH as legitimate: blaze orange for protein/energy accents, signal red for web CTA parity.

pipeline action (color):

- keep the token-driven palette; it is correct and single-sourced
- document the accent duality explicitly in the token file: `blazeOrange` = protein/energy accent, `signalRed #b51e14` = live web CTA. our index.html already has the signal-red token; ensure `kodiak.json` also carries it so print/compose stays in sync (today `kodiak.json` has no `signalRed` entry — gap, `inferred` from index.html only)
- align the exact bear-brown: decide whether canonical is `#3B2316` (our token) or `#382316` (live). they render nearly identically but a one-digit drift is worth resolving. recommend matching live `#382316` for parity, or documenting the intentional difference

### typography — confirmed, with a stale-token finding

live site + our front end both load the same Adobe Typekit kit `https://use.typekit.net/zjt4wyq.css` (confirmed — present in both live LTO raw HTML and our index.html head).

live custom fonts (confirmed, from scraped LTO page `@font-face` block):

- `Roar` (roar-sans.ttf / roar-sans-italic.ttf) — emphasis / callouts
- `kodiak_sans` (kodiak-sans.otf / kodiak-sans-oblique.otf) — UI
- `NOOMKC-Regular` (NOOM-KCLC-Regular.otf)

our front end type treatment (confirmed, from `index.html` `<style>`):

- headlines: `gin` (from the typekit kit) — 800 weight, uppercase, `letter-spacing:.06em`, ink-trap simulation. h1 `clamp(28px,4vw,44px)`
- body: `museo-sans` (300/500/700/900 from the kit)
- emphasis: `Roar` (protein bursts, callouts)
- UI (nav/buttons/badges): `kodiak_sans`
- epic headlines: `.epic-tracking` = `letter-spacing:0.45em` uppercase gin

STALE-TOKEN FINDING (confirmed): our `design/tokens/kodiak.json` typography block lists headline = `Rockwell, Clarendon, American Typewriter, Georgia, serif` and body = `Inter, Helvetica Neue, Arial`. that does NOT match what the site actually renders (gin + museo-sans + Roar + kodiak_sans from typekit). the token file's font stack is stale relative to `index.html`. this is a real drift to fix — the compose pipeline reads type intent from tokens, so it may be composing Rockwell/Inter fallbacks while the front end renders gin/museo-sans.

pipeline action (typography):

- update `kodiak.json` typography `fontFamily.headline` to lead with `gin` and `fontFamily.body` to lead with `museo-sans`, matching the live typekit and our index.html — so tokens, front end, and compose all agree
- the slab-serif fallbacks (Rockwell/Clarendon/Georgia) are a reasonable server-side fallback for compose.py where typekit is unavailable, but the primary must be the real brand faces. keep the fallbacks, fix the primaries
- confidence: confirmed (both the live faces and the stale token are directly sourced)

## 6. voice / taglines

what it is: kodiak's voice is frontier-rugged, playful, bear-forward, aspirational-active. confirmed taglines and lines (sources in the matrix below).

| line                                                                                                                                                       | source                                                                 | confidence |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------- | ---------- |
| "Keep It Wild"                                                                                                                                             | site nav, footer, campaign name; our compose.py footer                 | confirmed  |
| "Feeding Epic Days & Wilder Lives" (TM)                                                                                                                    | [kodiakcakes.com homepage title](http://www.kodiakcakes.com/index.php) | confirmed  |
| "Nourishment for Today's Frontier" / "inspire healthier eating and active living with nourishment for today's frontier"                                    | scraped `brand-lore/our-mission.txt`                                   | confirmed  |
| "recent bear sightings at Kodiak"                                                                                                                          | scraped newsletter copy (mission, keepitwild, ba-training-tools)       | confirmed  |
| "Whole Grains Taste Better" (R)                                                                                                                            | scraped mission page                                                   | confirmed  |
| "Fuel for Conquering Your Frontier"                                                                                                                        | scraped mission page                                                   | confirmed  |
| "feed wilder lives"                                                                                                                                        | scraped LTO page meta                                                  | confirmed  |
| culture pillars (bear terms): "leave the growl behind", "bear together", "forge a fresh trail", "clawing through", "get out of the bear den"; "bear bucks" | forbes platform-brand interview (scraped)                              | confirmed  |
| origin voice: 1982, Penny Clark, red wagon, Shark Tank (sharks passed), Park City                                                                          | brand-ambassador guide + forbes (scraped)                              | confirmed  |

pipeline action:

- build a tagline library keyed to campaign type: conservation -> "Keep It Wild"; general brand -> "Feeding Epic Days & Wilder Lives" / "Nourishment for Today's Frontier"; product/protein -> "Whole Grains Taste Better", "Fuel for Conquering Your Frontier"; newsletter/social playful -> "recent bear sightings"
- feed the frontier + bear-culture vocabulary into the Nova Pro art-director + headline-generation prompts so generated copy lands on-brand
- confidence: confirmed for all listed lines

## 7. brown-kraft-box / "brown box with the growling bear" packaging identity

what it is: kodiak's shelf identity is the uncoated brown kraft box with the growling bear and hand-illustrated graphics. consumers literally call it "the brown box with the growling bear". the substrate is 20pt Uncoated Recycled Board (URB), 100% recycled fiber, printed with UV inks + matte acrylic coating so graphics pop on the natural brown board. the brown-box choice is a deliberate sustainability + honest/natural signal (most competitors use coated white board).

where it appears (sources):

- graphic packaging international case study, scraped `brand-lore/kodiak-brand-lore-knowledge-base.txt` and `brand-lore/graphicpkg-case.html` (confirmed): "the brown box with the growling bear", 20pt URB, UV inks + matte acrylic coating
- [graphicpkg.com case study](https://www.graphicpkg.com/resources/kodiak-cakes-packaging-helps-to-convey-the-companys-brand-values/) (confirmed; rephrased for compliance)
- 215 real `705599*` product packshots in our corpus (confirmed present in `images/`)

pipeline action:

- keep the kraft procedural texture our front end + compose already use (kraft gradients, paper-fiber svg hairlines) — it correctly evokes the URB brown box
- ensure real product boxes are served verbatim rather than generated, so a real box never renders as generic food — already speced in `compose-fix-spec.md` (link the 215 `705599*` packshots to SKUs, serve-first precedence)
- optional: a "brown box" background treatment preset (kraft-brown fill) for packaging-forward creatives
- confidence: confirmed

## 8. recurring photography style

what it is: kodiak's photography leans into cast-iron cooking, the Wasatch/mountain-town outdoors, trail and camp scenes, wheat fields, and active families — the "rustic mountain-town natural food brand" look (their own framing per the packaging case study).

where it appears (confirmed corpus filenames, `data/raw-ingest/kodiakcakes/images/`):

- wheat fields: `2020.8_Idaho_Wheat_Fields_00063_...jpg`, `Kodiak-FJ_W_Mix-Wheat_Fields_Photography-2026-R1.jpg`
- Wasatch / climbing lifestyle: `2023-Climbing-Lifestyle-2396-1-...jpg`, `Emily_El_Cap_Climb_...jpg`
- cast iron: `01ab36da4a86--2024-06-11-Kodiak-Cast-Iron-Pizza-...jpg`, `859_blogs_recipes_cast-iron-pizza.html`
- trail / camp: `9fdf22f99cea--Kodiak-Recipe-Camp-Stove-Oatmeal-...jpg`, `Kodiak_Recipe_Campfire_Baked_Apple_Oats_...jpg`
- active family: `Kodiak_Q3_Family_Hiking_Camping_Lake_...jpg`, `2023-Outdoor-Cooking-Family-Lifestyle-2051_...jpg`

pipeline action:

- curate a brand-background pool from these real lifestyle stills for served-asset composites (the background layer that a real packshot or athlete still composites over)
- build a scene-hint vocabulary (Wasatch morning trailhead, cast-iron protein stack, wheat field, camp stove, active family) for generated backgrounds when a real background is not resolved
- confidence: confirmed (filenames directly in corpus)

## 9. frontier / pioneer narrative + bear culture (supporting concept)

what it is: the brand story is "restoring the real food tradition" — frontier explorers from the Yukon to the High Sierra relied on real, whole, high-carb/protein/fiber food, and kodiak is that food for "today's frontier". internally the culture is all bear terms (concept 6). the bear name itself: Joel and Jon Clark chose the kodiak bear as the emblem of bravery and daring, which also seeded the conservation passion (bears = keystone species).

where it appears: scraped `brand-lore/our-mission.txt` ("RESTORING THE REAL FOOD TRADITION", "rugged old pioneers"), forbes platform-brand interview, brand-ambassador guide (confirmed).

pipeline action: this is the narrative substrate for concepts 1, 6, 8. feed it into art-director + copy prompts; no standalone asset.

## 10. origin story / heritage (supporting concept)

what it is: founded 1982 by Penny Clark; sons Joel + Jon Clark turned mom's whole-wheat pancake recipe into a business; 8-year-old Joel sold homemade flapjack mix from a red wagon; famously pitched on Shark Tank (the sharks passed); headquartered Park City, Utah.

where it appears: scraped brand-ambassador guide, forbes, LTO page schema (Shark Tank references) (confirmed).

pipeline action: optional heritage badge ("since 1982") / red-wagon motif for heritage or storytelling campaigns. low priority.

## ceros-and-cdn-asset-urls

real kodiak asset URLs captured for the follow-up full-res pull. flagged by whether a direct URL was obtained or whether a browser render (blocked on nova-mcp infra fix) is required.

### direct URLs (fetchable now, no render needed)

| asset                              | url                                                                                                     | notes                                                                    | confidence |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------- |
| growling bear-head mark (full res) | `https://media.ceros.com/kodiak-cakes/images/2024/12/19/ed9cbf26e4db9cc44cfe014316fb0841/bear-head.png` | drop the `&width=` param for full resolution (Bryan-provided, confirmed) | confirmed  |
| primary logo (raster)              | `https://kodiakcakes.com/cdn/shop/files/kodiak-primary-logo_optimized.png?v=1724851354`                 | append `&width=600` for larger; from LTO page + schema.org logo          | confirmed  |
| primary logo (vector)              | `https://kodiakcakes.com/cdn/shop/files/Logo.svg?v=1732722394`                                          | SVG wordmark/logo, from LTO page preload                                 | confirmed  |
| kodiak_sans font                   | `https://kodiakcakes.com/cdn/shop/t/97/assets/kodiak-sans.otf`                                          | brand UI font (also -oblique variant)                                    | confirmed  |
| Roar font                          | `https://kodiakcakes.com/cdn/shop/t/97/assets/roar-sans.ttf`                                            | brand emphasis font (also -italic)                                       | confirmed  |
| typekit kit                        | `https://use.typekit.net/zjt4wyq.css`                                                                   | gin + museo-sans + more                                                  | confirmed  |

### real assets already in our local corpus (no pull needed — already downloaded)

these are confirmed present at `~/code/chasko-labs/creative-automation-pipeline/data/raw-ingest/kodiakcakes/images/` and mirrored (or mirror-able) to the asset store at `brands/kodiak/raw-ingest/kodiakcakes/images/`:

| asset                                              | local filename                                                                                | confidence                                                      |
| -------------------------------------------------- | --------------------------------------------------------------------------------------------- | --------------------------------------------------------------- |
| bear logomark (verify visually)                    | `logo_256x256_a145607b-6231-4f75-a693-802b2650db1f.png`                                       | confirmed present; content inferred                             |
| primary logo                                       | `kodiak-primary-logo_optimized.png`                                                           | confirmed                                                       |
| Zac Efron still (cooking)                          | `2023-Cooking-with-Zac-2636_1_59086e86-8776-4fbe-980a-9167bc5e19fb.jpg`                       | confirmed                                                       |
| Zac Efron still (waffle nachos)                    | `ea373ffadae2--2024-Zac-Waffle-Nachos-2992-1-1-3eb394_8b59e8.jpg`                             | confirmed                                                       |
| Courtney Dauwalter                                 | `Courtney-Dauwalter.jpg`                                                                      | confirmed                                                       |
| Christopher Blevins                                | `Christopher-Blevins.jpg`                                                                     | confirmed                                                       |
| Emily Harrington                                   | `Emily_El_Cap_Climb_1_2_fc5a6848-87d1-4247-9367-5b94db94595e.jpg`                             | confirmed                                                       |
| Alex Howes                                         | `2022-Alex-Howes_001_1.jpg`                                                                   | confirmed                                                       |
| Caleb Olson                                        | `Kodiak_Athlete_Caleb_Olson_0825_0186.jpg`                                                    | confirmed                                                       |
| Natalia Grossman                                   | `24.7.9.Natalia.Grossman.Kodiak-67.jpg`                                                       | confirmed                                                       |
| Karissa Schweizer                                  | `2020.6_Karissa_Schweizer_Athlete-769.jpg`                                                    | confirmed                                                       |
| Sam Watson                                         | `KodiakCakes-SamWatson-Athlete.jpg`                                                           | confirmed                                                       |
| Meg Fisher                                         | `meg-fischer.png`                                                                             | confirmed                                                       |
| Jennifer Lichter                                   | `Kodiak-Athlete-Jennifer-Lichter.jpg`                                                         | confirmed                                                       |
| LTO-adjacent packshot (Maple Pecan Overnight Oats) | `705599020797-Kodiak_Cakes-Maple_Pecan-Overnight_Oats-Pouch-PCH-00XX_2079_01-Pouch_Front.png` | confirmed (closest SKU to the real Apple Brown Sugar Pecan LTO) |
| wheat field bg                                     | `2020.8_Idaho_Wheat_Fields_00063_0bb83592-...jpg`                                             | confirmed                                                       |
| climbing lifestyle bg                              | `691a3449573d--2023-Climbing-Lifestyle-2396-1-c7f269_64edf1.jpg`                              | confirmed                                                       |
| family hiking/camping bg                           | `Kodiak_Q3_Family_Hiking_Camping_Lake_0626_2151_c20677e0-...jpg`                              | confirmed                                                       |
| 215 product packshots                              | `705599*` (see full list in corpus)                                                           | confirmed                                                       |

### browser-render required (blocked on nova-mcp infra fix)

| target                               | url                                                                                                                                                  | what it holds                                                                   | blocker                                                                                                                                                                                                                     |
| ------------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| LTO ceros microsite                  | `https://view.ceros.com/kodiak-cakes/lto-oatmeal-lp`                                                                                                 | 2 Zac videos, Zac signature graphic, Apple Brown Sugar Pecan LTO product image  | `web_fetch` returns a 121-byte JS/canvas shell — no asset URLs in static HTML. needs a real browser render (nova-mcp / playwright) to capture the `media.ceros.com/kodiak-cakes/...` asset URLs the canvas loads at runtime |
| ceros CDN asset enumeration          | `https://media.ceros.com/kodiak-cakes/...`                                                                                                           | additional Zac stills, signature, LTO product renders beyond the bear-head      | CDN is not directory-listable; specific asset paths are only discoverable from the rendered ceros manifest (same render blocker)                                                                                            |
| current Keep It Wild campaign lockup | `https://kodiakcakes.com/pages/keepitwild` (redirects to a `kiw-*` quarterly page) + `https://interactive.kodiakcakes.com/conservation-updated-1015` | current-year KIW lockup art, Draplin merch, Vital Ground co-badge current usage | scraped page body is JS-rendered/thin; needs a browser render to capture current campaign art + the Vital Ground mark                                                                                                       |

honest flags:

- the bear-head full-res URL, both logos, and the two Zac stills are all directly obtainable now (URLs above or already in corpus). no render needed for those.
- the Zac SIGNATURE graphic and the LTO PRODUCT render on the ceros microsite have NO discoverable direct URL from static HTML — those specifically need the browser render.
- the Vital Ground co-badge is NOT in our corpus and has no captured URL — sourcing it is a separate task (a co-brand asset request, not a scrape).

## open gaps for the pipeline team (not fabricated — flagged as unknown)

- canonical bear-brown: `#3B2316` (our token) vs `#382316` (live) — decide and single-source
- `signalRed #b51e14` exists in index.html but NOT in `design/tokens/kodiak.json` — add it so compose/print stay in sync
- `kodiak.json` typography is stale (Rockwell/Inter) vs live/index.html (gin/museo-sans) — update
- Apple Brown Sugar Pecan LTO SKU is not in the product catalog — add it (see `zac-efron-campaign-fix-spec.md`)
- Vital Ground co-badge asset — source separately (co-brand request)
- ceros interior assets (Zac signature, LTO product render) — capture via browser render once nova-mcp is fixed
