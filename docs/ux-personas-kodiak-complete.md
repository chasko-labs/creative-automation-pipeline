# Who Uses KODIAK® Posts for Today's Frontier — 23 Persona Cards That Shape Every Sprint

> Every hub below runs a different part of KODIAK® — the brown box with the growling bear, 14 grams of protein, 100% whole grains, feeding epic days. If a story doesn't serve one card here, it doesn't go in the sprint. Forward facing by design — link this page directly in planning and in the store phone book onboarding.

Read the quick hub view first: [Brand Management](#brand-management), [Creative, Design and Operations](#creative-design-and-operations), [Growth and Digital Commerce](#growth-and-digital-commerce), [Community and Brand Partnerships](#community-and-brand-partnerships), [Shopper Marketing and Sales Hubs](#shopper-marketing-and-sales-hubs). The 1982 red wagon, Wasatch Mountains, and Keep It Wild set the voice for all of them — see `docs/kodiak-brand-explained.md` for the story that every card below protects.

Every card writes brand names exactly as KODIAK®, KODIAK CAKES®, KODIAK POWER CUPS® and slogans exactly as **Feeding Epic Days & Wilder Lives** and **Nourishment for Today's Frontier** with the KODIAK Bear silhouette doing the visual lifting — see `docs/iso-naming-conventions.md` for the 7-field variant pattern `KODIAK-CAKES-{PRODUCT}-{REGION}-{LOCALITY}-{CHANNEL}-{RATIO}-{YYYYMMDD}-v01.png` and `docs/kodiak-shading.json` for the brown-dominant shading that keeps the kraft box iconic.

---

## Brand Management — Park City

### Aaron Robinson — Senior Director of Brand Management — Park City, Utah

- **Focus:** Portfolio steward for KODIAK®. Decides which frontier story — Wasatch, trail, family porch, green chile — scales to hundreds of towns.
- **Goals:** One promise across flapjacks, muffins, oatmeal, energy balls, savory waffles with regional peppers and cheeses — and that promise reads as KODIAK CAKES®, not as a generic grocery trick.
- **Pain:** Last launch needed agency to move the bear logo 20 pixels — two weeks, 30 sizes, drift.
- **How this system serves his experience:** He approves the single style library at `design/tokens/kodiak.json` (Bear Brown #3B2316 dominant, Blaze Orange #E8530E only on the 8-point bar, Parchment #FFF8F0 ground) mirrored to `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/` and the lookup row that remembers `market: US-SW-LASCRUCES → Green chile meets grizzly`. No extra file per town — the pipeline reuses the real brown box photo via `input_assets/power-cakes/hero.png` or generates via Nova Canvas only when missing.
- **Success:** A Park City brief with `brand: KODIAK®` in `briefs/kodiak.yaml` passes `src/creative_automation/compliance.py` on first run and shows `KODIAK® • kodiakcakes.com • Keep It Wild` in every footer without a second touch.
- **Bear flex he sees:** Bear at 24,24 watermark monogram on every internal tool header — `var(--bear-mark)` at `24px 24px / 24px` — keeps KODIAK® name dominant even in the tool chrome.
- **Sprint anchor:** Approve scale change (18 → 200 localities) — same 7 fields, `ISO 8601` date, `BCP 47` language tag, no drift.

### Madison Roberts — Director of Brand Management — Park City, Utah *and* Rebecka Fitzkee — Director of Brand Management — Park City, Utah

Shared role, two owners — both run parallel sprints for different retail clusters so the 200-locality load never queues on one person. Persona copy is identical, calendar splits.

- **Focus:** Two directors split the three store groups — one owns friendly southern supermarkets + big membership stores, the other owns style-forward national chain + small grocers + diners. Both own the 1982 red wagon to shark tank to 26,000 doors narrative.
- **Goals:** Launch a Publix-family and a Target Gen Z campaign the same Monday with zero cross contamination of voice.
- **How served:** Brand + market paired filtering in `data/localization/localization-training-data.jsonl` — searching `search("Porch breakfast")` returns Publix wins, `search("clean label active")` returns Target wins — and `KODIAK CAKES®` spelling enforced by `docs/iso-naming-conventions.md` section 1.
- **Bear flex:** Kraft texture panel (`--kraft` `repeating-linear-gradient` + 3% noise tinted Bear Brown T20 #624E42 at 0.06) appears only on product-story cards when their cluster is active — keeps box iconic by never tinting the pack itself.

### Eli Curtis — Brand Manager — Park City, Utah

- **Focus:** Day to day owners of flipjack, muffin, oatmeal, waffle ice cream sandwich lines. Lives in `kodiak.brand.inventory.json` and the Amazon store 19CF7868-DF80-4939-932A aisle parity.
- **Goals:** Ingredients page truth — non genetically modified, no artificial flavors, real fruit and nuts — reads identically on the pack front and on the tall story frame; 14 grams of protein never overclaimed per the 2021 caution.
- **Pain:** Copy variants diverge after translation — French or high desert green chile rewrites lose the protein callout.
- **How served:** Brief `campaign_message` is checked for slogan punctuation `Feeding Epic Days & Wilder Lives` and for `14g` vs `14 grams` parity before Nova Micro rewrite. Photo library path is single source `brands/kodiak/heroes/{power-cakes,bear-bites,oatmeal-cup}/hero.png` plus 8 Nova prompts at `references/keep-it-wild/`.
- **Sprint anchor:** Recipe database at `data/recipes/kodiak-recipes.json` — 23 baselines localizable via peppers and cheeses (flapjacks, savory waffles, pizza crust all carry Hatch green chile slot), linked to product pages.

### Sarah Brooks — Product Marketing Manager — Park City, Utah

- **Focus:** Launch cadence — what ships when across bulk, lunchbox, and dine-out.
- **Goals:** One campaign can feed bulk family in Seattle and lunchbox parent in Savannah without forking the master.
- **How served:** Single master post via `docs/how-we-launch-in-every-town.md` — one Post ID reused across ad sets via `Use Existing Post`, budget per local bucket intact because Advantage Campaign Budget stays off. She sets ten dollars for Las Cruces and it stays in Las Cruces.
- **Bear flex:** Mountain silhouette divider (`--mountain` SVG at 100% width, 48px, Wasatch ridge in Frontier Green S30 #1A2F29) sits between editorial blocks — brand wayfinding without extra hue, so brown pack stays contrast king.

### Emily Pearson — Associate Brand Manager — Park City, Utah

- **Focus:** Detail craft — KODIAK POWER CUPS® line, oatmeal cup, minute muffin cup — the small pack that must read at table-tent size.
- **Goals:** `KODIAK POWER CUPS®` — always two words after the brand, always with ®, always capital — reads clean at 140w @24,24 even on a 1×1 table tent.
- **Pain:** Prior small pack lost legibility when orange was used for body text on parchment (3.1:1 fails 4.5:1).
- **How served:** Token `kodiak.logo` branch enforces 24,24 offset, 140w default, 80w min, and scrim rule `only on #3B2316 / #1A3C34 / #1A1110 / #000` with `#1A1110CC` at 80 percent — checked by `scripts/browser-check.py` at 3 viewports (1080×1080, 1080×1920, 1920×1080). Body text stays Bear Brown or Frontier Green on parchment (10.2:1, 12.1:1, never Blaze Orange).
- **Sprint anchor:** Table-tent and diner board previews via `web/kodiak-posts-for-todays-frontier/index.html` — offline, no server, she renders 3 local ads with one click and downloads `KODIAK-CAKES-…-table-tent-1x1-YYYYMMDD-v01.png`.

### Elizabeth Hilgemann — Consumer Insights Manager — Park City, Utah

- **Focus:** What real shoppers said — not what the agency guessed.
- **Goals:** Tie every local variant (Las Cruces green chile plus Oaxaca crumble) back to a lift signal per market — direction taps, saves, subscription joins.
- **How served:** `data/localization/localization-training-data.jsonl` grows one row per creative per place (market, place, retailer, audience, message, peppers, cheeses, cue, zip) and embeds via `amazon.nova-2-multimodal-embeddings-v1:0` at 1024 into `data/vectors/kodiak-embeddings.jsonl` mirrored to `s3://.../brands/kodiak/vectors/` — `search("What worked for green chile families?")` returns top-k past wins by meaning via `kodiak_reference_search` MCP. No third-party models.
- **Sprint anchor:** Post-campaign ingest job adds the outcome columns so the next Las Cruces run suggests `Green chile meets grizzly` first.

### Nina Palazzolo — Senior Category Insights Manager — Salt Lake City Area

- **Focus:** Category halo — how flapjacks lift oatmeal, baking, and frozen together at shelf.
- **Goals:** One frontier pantry story that reads across breakfast, lunchbox, and dine-out without flattening regional nuance.
- **How served:** `references/keep-it-wild/photography-direction.json` keeps Wasatch dawn alpenglow with sky negative space at top for text vs roasted Hatch green chile flapjacks scaled same template — same 6-piece frontier, different sky. She watches `data/vectors/manifest.json` counts to confirm the index covers design, reference, and training piles.

---

## Creative, Design and Operations — Where the Brown Box Is Protected

### Brett Miller — Vice President of Creative — Park City, Utah

- **Focus:** Keeps the brown kraft box with the growling bear untouchable. Owns `docs/kodiak-style-guide.md` 7-part (story, logo, palette, type, photo, packaging, voice).
- **Goals:** Orange never owns body text, green never outshines the box, bear never stretched. Every ad that leaves looks like it came off the same press.
- **How served:** Shading table at `docs/kodiak-shading.json` (14KB) — tints to #4F382C/#624E42/#766357, shades to #382115/#311E14 — plus dominance rule brown 60 to 70 percent chroma, orange ≤ 18 percent or 8-point bar solid. All tints/shades are pre-baked hexes from `design/tokens/kodiak.json`.
- **Bear flex he ships:** Orange Glow protein halo — `radial-gradient(closest-side, rgba(232,83,14,0.18), transparent 70%)` at 280px behind each front-of-pack render, solid fallback `#FBDAC7`, pack shadow `0 8px 24px #311E1433` — brown name lifts, orange never touches KODIAK® lettering.
- **Sprint anchor:** Approve every shading change — his sign off blocks merge via `CONTRIBUTING.md`.

### Arnoldo Romo — Design Director — Salt Lake City Area

- **Focus:** Visual execution — slab 56/64/72, parchment ground, bear at 24,24, 8-point Blaze bar.
- **Goals:** The 1×1 square, 9×16 tall, 16×9 wide are not three designs — one idea stretched correctly with the same kraft box.
- **How served:** Token `kodiak.dimension.canvas` holds `1x1 1080×1080, 9×16 1080×1920, 16x9 1920×1080` plus safe 48, logo 24, accent 8, message bar 68 percent — consumed by `src/creative_automation/compose.py` directly. No hard-coded sizes in code.
- **Bear flex:** Kraft panel on product story cards and parchment ground on pages — oatmeal story gets `var(--kraft)` grain at 0.06 so pack reads warm without losing contrast.

### Sam Featherstone — Associate Creative Director, Content — Park City, Utah

- **Focus:** Frontier stories — 345 recipe pages (muffins, scones, quick breads, chicken strips breading) from `data/raw-ingest/kodiakcakes/pages/` turned into ad concepts.
- **Goals:** Every blog recipe can become an ad without reshooting — the photo cue plus Nova Canvas prompts `kodiak-01..08` do it.
- **How served:** `kodiak-nova-canvas-references.json` supplies clean background, soft shadow, 1024, no text inside image — Nova builds frontier hero around the real pack.
- **Sprint anchor:** Content calendar is the recipe database — 23 baselines at `data/recipes/kodiak-recipes.json` localizable via regional peppers and cheeses.

### Amber Kirkham — Senior Project Analyst, Marketing Operations — Park City, Utah

- **Focus:** Velocity without drift — hundreds of localities, one tracking spine.
- **Goals:** From 18 seeded places to the next 200 — same 7 fields, same `YYYYMMDD` version, zero orphan files.
- **How served:** `docs/iso-naming-conventions.md` section 4 pattern `KODIAK-CAKES-{PRODUCT}-{REGION}-{LOCALITY}-{CHANNEL}-{RATIO}-{YYYYMMDD}-v01.png` enforced at write time to cloud storage `brands/kodiak/renders/{product}/{ratio}/` alongside `report.jsonl`. `uv run pytest -q` runs 6 end-to-end checks including Las Cruces green chile.
- **Sprint anchor:** Change management — her feedback portal fields `people served, samples handed` map to the same 7 localization fields so sample events and social posts share a code.

---

## Growth and Digital Commerce — Direct Home, One Click to Cart

### Cory Bayers — Chief Marketing Officer — Park City and Remote

- **Focus:** Whole funnel — retail shelf to direct home subscription at https://kodiakcakes.com/pages/subscriptions (15 percent off plus free shipping over 45).
- **Goals:** Retail and subscription never undercut each other's story — same frontier, different door.
- **How served:** Brief `brand: KODIAK®` plus channel `subscription-email` vs `retail` board — same head line, different call to action, same bear. Dashboard reads retail `report.jsonl` alongside subscription `orders` without re-tagging.
- **Sprint anchor:** Approve every market expansion — his go/no-go reads `docs/bedrock-agentcore-architecture.md` mermaid that shows phone book → store sets → one post → dynamic `{{store.city}}` + map → Get Directions.

### Casi Reichardt — Head of Channel Marketing — eCommerce, Shopper, CRM — Park City, Utah

- **Focus:** Shopper, customer relations, lifecycle — the three channels where one name must be spelled the same: KODIAK® in email, shopper post, and carton.
- **Goals:** The home delivery line `Subscribe and save — 15 percent off plus free shipping over 45` travels from site to inbox to cup without retypesetting the carton.
- **How served:** `references/brand-inventory.json` copy is single source for `kodiakcakes.com/collections/all` plus Amazon brand store 19CF7868-DF80-4939-932A plus `s3://.../raw-ingest/` — one hierarchy, mirrored.
- **Bear flex:** Subscription email hero reuses Hero Depth Stack — scrim `#1A1110CC` at top under white KODIAK® reversal, bottom fade to Alpine Haze `#DCE8E0`, left 8-point blaze vertical — three brand tones in one stack, pack stays top contrast.

### John Oja — Director of eCommerce — Salt Lake City and Remote

- **Focus:** Store that never sleeps — cart, upsell, 15 percent off trail.
- **Goals:** Free shipping threshold `Spend $45 or more` reads identically in the cart banner and on the tall story ad — no floating `free shipping on orders over 45` case drift.
- **How served:** Tokens carry cart copy as `kodiak.brand.promo` — single edit propagates to `docs/kodiak-brand-view.html`, to the offline tool header, and to the `preview.html` footer.
- **Sprint anchor:** Shopify theme check — his preview shows real kit pack shot from `data/raw-ingest/kodiakcakes/images/705599011627_FlapjackMix_Buttermilk_Front_1.png` (resized 1024), not the mock ellipse.

### Landon Ruud — Senior eCommerce Manager — Park City, Utah

- **Focus:** Flavor and bundle operations — what is in stock, what substitutes, what ships free when a pouch is out at no charge.
- **Goals:** The shop portal `Start & stop at any time — add or remove products, cancel, renew` — reads exact and matches the ad promise.
- **How served:** `data/recipes/kodiak-recipes.json` product links carry `kodiak_page` URLs so Landon can hand Maya the exact collection link for Amazon and direct mix in one click.
- **Bear flex:** Warm amber `#FF8A3D` focus ring on product selectors — protein halo without touching bear mark.

### Micah Anderson — Senior Digital Marketing Manager — Park City, Utah

- **Focus:** Paid social that feels handmade per town — map card on, dynamic city, Get Directions working.
- **Goals:** One Post ID per product, many local doors — same care as a national hero but localized as `Find us today at your nearest town — {{store.city}}!` with the right zip.
- **How served:** The three-phase flow at `docs/how-we-launch-in-every-town.md` — phone book once, store sets per retailer or city cluster, Advantage Campaign Budget off so Las Cruces budget stays in Las Cruces. The pipeline's `report.jsonl` becomes his spend mirror.
- **Sprint anchor:** He watches headless verify screenshots — verified via Playwright at `1080×1080, 1080×1920, 1920×1080`, 6 cards per preview, load 8 to 30 milliseconds, card count and scrim read — before handoff to the store.

---

## Community and Brand Partnerships — Bear in the Wild

### Boman Farrer — Senior Director of Marketing — Salt Lake City Area

- **Focus:** Keep It Wild platform — Vital Ground, portfolio bets in grocery.
- **Goals:** Every social dollar carries `Keep It Wild` alongside `Feeding Epic Days & Wilder Lives` without drowning the product.
- **How served:** Campaign `KODIAK® — Keep It Wild Frontier` plus photography direction `references/keep-it-wild/photography-direction.json` (Wasatch dawn alpenglow, pine/boulder, sky negative space for text, cubs on trail bench). Grizzly-safe photo rule inside.
- **Sprint anchor:** Campaign `keep-it-wild` prompt group Nova Canvas `kodiak-01..08` seeded in `design/tokens/kodiak.json`.

### Mackenzie Wilmarth — Senior Marketing Manager (Social, Email, Short Message) — Park City, Utah

- **Focus:** Voice that travels from feed to inbox to text — adventurous, nourishing, rugged, short Wasatch sentences.
- **Goals:** Instagram minus handshake minus "aurora glow on every card" — frontier, not tech slop.
- **How served:** `docs/iso-naming-conventions.md` slogans fixed punctuation — `Feeding Epic Days & Wilder Lives` and `Nourishment for Today's Frontier` blocked from paraphrase until corrected.
- **Bear flex:** Frontier Haze + Ink Scrim depth stack on the hero at `Hero Depth Stack` spec — top scrim `#1A1110CC` under white KODIAK® reversal, bottom fade to Alpine Haze `#DCE8E0`, 8-point blaze vertical — so the tall story post reads at thumb speed.

### Julie McDermott — Senior Community Manager — Park City, Utah

- **Focus:** Answers, not ads — comments, tags, reposts, bear sightings.
- **Goals:** When someone tags green chile flapjacks in Las Cruces, the reply carries the recipe cue that same town liked last time.
- **How served:** Search `kodiak_reference_search` via MCP `{"q":"What worked for green chile families?"}` returns Las Cruces row by meaning in under 200 milliseconds — her reply copies that line plus the `kodiak-04-bear-bites-cubs` cue.
- **Sprint anchor:** Community calendar shares the same `web/kodiak-posts-for-todays-frontier/index.html` offline tool — marketing owns the first step there without a short form.

### Ella Ratliff — Athlete Partnerships Manager — Salt Lake City Area

- **Focus:** High-profile outdoor athlete activations — the bear moves like they do.
- **Goals:** Power Waffles beyond breakfast blog (5 toaster waffle recipes) stays true to pack — no stretch, no busy background without scrim.
- **How served:** Pack shot `Power Waffles` and `Keep It Wild` photo specs share the same `KODIAK Bear silhouette` reversal rules — only on Brown/Green/Ink/Black.
- **Sprint anchor:** Athlete reads match `docs/kodiak-nova-canvas-references.json` clean pack hero (soft shadow, 1024, no text) so the athlete and the pack share the frame without fighting.

### Kelly King — Influencer Partnerships Manager — Park City, Utah

- **Focus:** Outdoor and recipe creators — handoffs that still look like the brown box.
- **Goals:** Influencer posts carry the same 8-point Blaze bar and parchment wash so a repost is recognizable at thumbnail crop.
- **How served:** `docs/training-process.md` runnable code `embed_text` / `embed_image` via `amazon.nova-2-multimodal-embeddings-v1:0` at 1024 turns creator image + caption into the same index Maya searches — `GET /search?q=porch%20breakfast` finds creator's peach cobbler too.
- **Bear flex:** Bear at 24,24 is never stretched — checked by `scripts/browser-check.py` across 3 viewports before any repost goes live.

---

## Shopper Marketing and Sales Hubs — Where Hundreds Become Real

### Ali Fluke — Associate Director, Shopper Marketing — Chicago, IL and Cincinnati, OH

- **Focus:** Grocery chain co-branding dollars — Chicago Jewel-Osco, Cincinnati Kroger — same budget story, two city skins.
- **Goals:** Co-branding dollars track to chain and to market plus locality minus double work.
- **How served:** Region slash market plus locality in file name and in table — `KODIAK-CAKES-power-cakes-US-MW-lake-county-target-instagram-9x16-20250902-v01.png` carries USD+city+chain, `report.jsonl` carries `human_name` plus machine prefix `brands/kodiak/renders/{product}/{ratio}/`. One row per creative per place.
- **Sprint anchor:** She writes the shopper brief that starts in plain language at `docs/how-we-launch-in-every-town.md` step one — the phone book row already has street, city, zip, phone, store number.

### Ashley La Barbera — Vice President of Sales — Minneapolis Area

- **Focus:** Shelf throughline — Amazon to direct to store.
- **Goals:** `Find us on Amazon` at `kodiakcakes.com/find-us-on-amazon` and `Find us in-store` zip finder plus `s3://.../raw-ingest/kodiakcakes/` 815 objects tell the same inventory story.
- **How served:** `references/brand-inventory.json` is single source for Paris-scale, retail, and training — no drift between `kodiakcakes.com/collections/all` and `19CF7868-DF80-4939-932A` Amazon store rows.
- **Bear flex:** Brown box dominance protected even in the store map — `Store Locator Map` pin is Blaze Orange, never brown, so the shelf pack stays the iconic brown in thumbnail.

### Quin Taylor — Field Marketing Specialist — Denver, Colorado and Austin, Texas

- **Focus:** Boots on the ground — Denver King Soopers and Austin H-E-B plus the Target on the hill and the Target downtown.
- **Goals:** Sample event in Denver, share a story in Austin that feels like Austin — same day, two local ads, no agency wait.
- **How served:** The offline tool at `web/kodiak-posts-for-todays-frontier/index.html` — `Render 3 local ads` with Las Cruces green chile or Austin jalapeño cheddar savory waffles via regional peppers and cheeses, download idea sheet plus three ratio PNGs plus `KODIAK-CAKES-…-YYYYMMDD-v01.png` names — all from `data/recipes/kodiak-recipes.json` 23 baselines localizable via peppers and cheeses, no fetch to a server. Field phone renders with real brown box `input_assets/power-cakes/hero.png` or falls to kraft placeholder if offline — same code. Plus the three density hubs she lives in: Chicago Jewel-Osco, Cincinnati Kroger, Denver King Soopers.
- **Sprint anchor:** Her field report (`people served, samples handed`) from `Brand_Ambassador_Print_Guide.pdf` writes the same 7 localization fields the social post did — sample events and social share a code.

---


---

## Technical Integration — The Living Swagger Is the Product (Offline Page Is the Picture)

> If a line isn't callable here, it isn't shippable. See the four cards at `docs/ux-personas-technical-integration.md` — **John Oja** (Director of eCommerce, Shopify Plus and site speed owner who approves any interface that touches checkout), **Landon Ruud or Micah Anderson** (Senior eCommerce and Digital Marketing, customer data platform plus NielsenIQ plus Attentive), **Arnoldo Romo** (Design Director, Canto plus Adobe Creative Cloud asset sync), **External Agency Partners** (Shopify Plus agency that writes the webhooks, handles `Authorization: Bearer` and `X-Shopify-Hmac-SHA256`, maintains endpoints). The offline page's *Render 3 local ads* button is a thin `fetch()` to `POST /pipeline/run` with the same JSON that `uv run python -m creative_automation.cli --brief briefs/kodiak-green-chile.yaml` writes locally — the Swagger at `src/creative_automation/api.py` → `GET /docs` is the source of truth, the managed control plane server at `.agents/mcp-kodiak-reference.json` exposes `kodiak_pipeline_run`, `kodiak_reference_search`, `kodiak_retail_stores`, `kodiak_asset_hero` with the same report and preview.

## How the sprint reads these cards

Planning at `README.md` links here: `[Who runs this — 23 persona cards](docs/ux-personas-kodiak-complete.md)`. Before a sprint, product marketing picks one or two cards — for example **Las Cruces green chile = Diego + Madison/Rebecka + Sarah** — and the board shows those names next to the scope so the person and the place stay tied. After a sprint, the preview at `output_kodiak-green-chile/preview.html` plus `browser-report.json` carry the PASS badge that the bear, bar, and legibility for that persona passed at `REG-001` before the retail handoff. If a card's experience is missing from the plan, the missing persona is named before the board closes.
