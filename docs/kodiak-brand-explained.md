# Kodiak — Human Story, Brand View, and How We'll Run Campaigns

> Plain language for anyone who hasn't lived in the pipeline repo. Technical style guide is at `docs/kodiak-style-guide.md`; design tokens live at `design/tokens/kodiak.json` and in S3 at `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/`.

---

## The Kodiak story in one minute

An 8-year-old in Park City, Utah — Joel Clark — sold his mom's hand-milled whole wheat flapjack mix door-to-door from a little red wagon in 1982. That recipe became a family business. His brother Jon incorporated it as Kodiak Cakes in 1995, Joel took over in 1997 while finishing an economics degree at the University of Utah, kept the lights on with side jobs, later earned an Oxford MBA, and never left the Wasatch Mountains.

The mission never changed: real food, 100% whole grains, protein you can feel. The line on every pack is the promise: **"Nourishment for Today's Frontier"** and more recently **"Keep It Wild."** It's a Park City brand — Wasatch alpenglow, pine and boulder, cast iron and enamel mugs, kids in beanies called "cubs," and a bear that actually means something.

The inflection points you can see in the aisles:

- **2014 — Shark Tank.** $3.6M in sales in 2013 to $6.7M in 2014. They turned down the deal, but the episode plus the new Buttermilk Power Cakes (14g protein) put them at #1 in Target — beating Aunt Jemima by 20%. That opened Walmart, Costco, Publix, Safeway.
- **Now — 26,000 doors** and growing. From a flapjack mix to a frontier pantry: Power Cakes, frozen waffles, oatmeal cups, baking mixes, granola bars, Bear Bites graham crackers for cubs, syrups.
- **2021 — L. Catterton** took a majority stake. Founders and the earlier investors stayed on. It's still run from Park City by Joel and president Cameron Smith.
- **2022 on — Keep It Wild.** Annual conservation campaign with the Vital Ground Foundation to protect grizzly habitat, fronted by Chief Brand Officer Zac Efron. Every pack, every campaign, and every social ad ties back to that wild.

Kodiak is what Bain calls a scale insurgent — a challenger that grew up without losing challenger velocity. That's exactly why it fits the "hundreds of localized social campaigns a month" problem. The portfolio grew faster than any style guide could.

---

## What the brand looks and sounds like — viewable here

You can see the live brand without leaving this repo:

- **Logo and palette:** `input_assets/brand/logo.png` (bear + KODIAK wordmark) and `design/tokens/kodiak.json` — Bear Brown #3B2316, Blaze Orange #E8530E, Frontier Green #1A3C34, parchment #FFF8F0, scrim #1A1110CC for the message bar. The same three colors drive the generated heroes when no photo exists.
- **Photography and mood:** `references/keep-it-wild/` — Wasatch dawn with sky left empty for text, rugged pioneers (modern family in flannel and beanies, not costumes, flipping cakes on cast iron), grizzlies at a respectful distance or just tracks (no captive bear close-ups — the brand learned that lesson in 2022), and post-hike tables with steam rising, a stack that says 14g.
- **Voice:** Adventurous and verbs-forward ("Fuel your frontier"), nourishing and honest (whole-grain, 14g, heirloom recipe), rugged but warm (short Wasatch sentences). The one approved headline for this pipeline is *"Protein-packed whole grains for today's frontier."* We flag anything that promises guaranteed weight loss or FDA-approved cures — Kodiak lived a 2021 class action on protein claims and doesn't need a repeat.
- **3-ratio templates:** `references/templates/social-3ratio.json` — every social ad, no matter the size, is built from the same six pieces: blurred Wasatch cover, hero centered at (W-fw)/2, 8% down, 48px outer pad, message bar at 68% down, logo 140px wide at 24,24, and a 8px Blaze Orange bar at the bottom. 1:1 is 1080×1080, 9:16 is 1080×1920 for Stories/Reels, 16:9 is 1920×1080 for feed video. The docs at `docs/kodiak-style-guide.md` spell it out with tokens.

Open `output_kodiak/preview.html` or `/tmp/kodiak-verify/preview.html` after any run — that's thebrand, rendered.

---

## The campaigns we plan to run — why each needs its own local twist

Kodiak is already national, so "local footprint" doesn't mean entering a new country. It means winning one retail corridor at a time. The same three products need different stories in different aisles.

### 1. Keep It Wild — the always-on brand campaign
*Hero product:* Buttermilk Power Cakes (the original, the asset store has a real hero photo).
*Idea:* Every pack funds grizzly habitat via Vital Ground. Social ads carry the wild, not just the food — Wasatch dawn hero, bear-safe photography, co-badge in the footer, and the tagline "Keep It Wild."
*Where it localizes:* Wasatch ski towns in winter (snow, cabin, Vital Ground acreage counter), southeast family porches in spring (Publix humidity-green, Bear Bites for cubs). Same system, different sky. Nova Canvas prompts `kodiak-01` and `kodiak-06` seed these.

### 2. Frontier Breakfast — the retail velocity campaign
*Hero products:* Power Cakes, Bear Bites, Protein Oatmeal Cup (three SKUs = three heroes; Power Cakes reuses a asset photo, the other two generate when no hero exists).
*Idea:* "Protein-packed whole grains for today's frontier" — the honest claim that moves boxes. Each retailer gets its own pack: Publix in the southeast (family breakfast, porch light), Target in the Midwest (Gen Z health, clean light), Costco bulk (family value, bigger stack). That's 3 products × 3 ratios × 3 retailers = 27 variants before we even change language.
*Where it localizes:* US-MW (mountain haze, Wasatch) vs US-SE (Publix porch) — we already have two briefs `briefs/kodiak.yaml` (US-MW) and `briefs/kodiak-se.yaml` (US-SE) that render 9 + 9 creatives with different `region` tags in `report.jsonl` so merch can see what drove lift per corridor.

### 3. Retailer and seasonal sprints — the hundreds-per-month engine
*Next up:* Back-to-school (Bear Bites in lunchboxes, 9:16 Stories), trail season (oatmeal cup on a rocky overlook, 16:9), holiday baking (Power Cakes cast-iron stack, 1:1). Each is the same six-piece template with a swapped hero prompt (`kodiak-04` for cubs on a trail bench, `kodiak-05` for oatmeal at sunrise) and a swapped accent — orange for protein, green for evergreen.

All three campaign types share the same brand check: logo present, blaze orange 8px bar at the bottom, palette probe for #3B2316/#E8530E/#1A3C34, and legal gate for protein claims. That check is our interim style guide until Kodiak publishes a formal one per retailer.

---

## How we'll produce the assets — the loop you can watch

You don't need AWS credentials to see it work, but the path is the same with or without S3.

1. **Brief in.** A YAML or JSON file names the campaign, the three products, the target market (e.g., US-MW vs US-SE), the audience, and one headline. `briefs/kodiak.yaml` is the source you can edit.

2. **Dam first, generate only if missing.** The pipeline looks in `input_assets/power-cakes/hero.png` (real photo, reused) first, then in S3 at `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/power-cakes/hero.png` if `ASSET_STORE_S3_BUCKET` is set, then generates a new hero if nothing is there. When it generates, it uses the frontier palette from the tokens and either a deterministic Pillow mock or, with credentials, Amazon Bedrock Nova Canvas (`amazon.nova-canvas-v1:0` in us-east-1, 1024×1024, cfgScale 7.5) seeded from the eight prompts in `references/keep-it-wild/nova-canvas-prompts.json`.

3. **Compose to three ratios deterministically.** Pillow does the layout, not another model, so the bear stays the bear. Every hero is covered to the ratio (ImageOps.fit), dimmed 0.18 with the token scrim #1A1110CC, contained at min(W*0.82/hw, H*0.58/hh) centered at 8% down, then overlayed with the headline (slab 56px at 1:1, 64px at 9:16, 72px at 16:9, max 3 lines, stroke 2), the Kodiak footer ("KODIAK • kodiakcakes.com • Keep It Wild" at 22/24px uppercase), the bear logo at 24,24, and the 8px Blaze Orange bar. Colors, spacing, and type all come from `design/tokens/kodiak.json` via `token_loader.py` (S3 first, local fallback). That's `s3://.../tokens/kodiak.tokens.json` in production.

4. **Check the brand and the law.** Every rendered PNG runs through logo presence, palette presence (does the image actually contain bear brown / blaze orange / frontier green), and prohibited words ("guaranteed," "miracle," "FDA approved," etc.). A failing creative still renders but is marked fail in the report — that's how we keep the 17% class action from recurring.

5. **Save and learn.** Assets land organized by product and ratio: `output_kodiak/power-cakes/1x1/power-cakes_1x1.png` and so on, plus `output_kodiak/report.json`, `report.jsonl` (one JSON line per creative — product, ratio, region, hero_source asset library vs mock vs bedrock, compliance pass), and `output_kodiak/preview.html`. Local lives in `output_*`; with creds, `scripts/sync-asset-store.sh push-renders output_kodiak` mirrors to `s3://.../brands/kodiak/renders/`.

6. **Style library stays in sync.** Tokens, references, logos, and templates live in S3 under `brands/kodiak/` and mirror to `design/tokens/`, `references/`, `input_assets/` locally. `./scripts/sync-asset-store.sh pull` before a run, `push` after you publish a new token or Keep It Wild reference. Infra is `infra/s3-dam.tf` (versioned, KMS, public-blocked, lifecycle to IA/Glacier/Deep Archive).

**To see it yourself from a fresh shell:**

```bash
cd ~/code/chasko-labs/creative-automation-pipeline
uv run pytest -q                               # 3 passed
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/kodiak-human
open /tmp/kodiak-human/preview.html            # human view
cat /tmp/kodiak-human/report.json | head -n 60
```

Or with the live bucket:

```bash
export AWS_PROFILE=bryanchasko-kiro
export ASSET_STORE_S3_BUCKET=chasko-creative-dam-946179428633-us-east-1 ASSET_STORE_S3_PREFIX=brands/kodiak/
./scripts/sync-asset-store.sh pull
ASSET_STORE_S3_BUCKET=... uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak
aws s3 ls s3://$ASSET_STORE_S3_BUCKET/brands/kodiak/ --recursive | head -n 20
```

The brand you see in S3 and in `design/tokens/` is the same brand you see in `output_kodiak/preview.html` — one system, rendered three ways, ready for the next retail corridor.
