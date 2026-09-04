# retailer-logo sourcing spec

sourcing + technical spec for the retailer logo assets the Kodiak composed-preview pipeline needs to composite retailer lockups. this is a SPEC and a legal action-item, not an asset drop. no trademarked logo is fabricated, downloaded, or bundled here.

## readiness statement (read first)

retailer lockup is BLOCKED on legitimately-sourced logo assets plus co-marketing permission. the pipeline should treat the retailer layer as optional and OFF by default until real assets land at the DAM path below. composed previews render correctly without retailer marks - the retailer lockup is an enhancement layer, not a dependency of the base composite

## current state

- the DAM holds ZERO retailer logos. the only brand mark present under the Kodiak logo paths is `kodiak-bear.png` / `kodiak-primary-logo_optimized.png` (Kodiak's own marks, not retailer marks)
- every region record in `tools/kodiak-scoreboard/regions/*.json` names retailers in its `retailers[]` block, and the pipeline compose path already accepts a `retailer_logo` param (compose.py `compose_creative`), so the compositing slot exists - it just has nothing to load

## retailers referenced across the scoreboard

derived from the `retailers[]` block of every region record. banner-to-parent notes matter because Smith's is a Kroger banner and Safeway is an Albertsons banner - the trademark owner is the parent for sourcing purposes

| retailer   | slug       | referenced in regions                                               | role range                | banner / parent note                                |
| ---------- | ---------- | ------------------------------------------------------------------- | ------------------------- | --------------------------------------------------- |
| Costco     | costco     | park-city, seattle, pescadero, neah-bay                             | halo / home / gap-nearest | Costco Wholesale                                    |
| Publix     | publix     | southeast-publix                                                    | home                      | Publix Super Markets                                |
| Target     | target     | albuquerque, park-city, southeast-publix, seattle, las-cruces       | primary                   | Target Corporation                                  |
| Walmart    | walmart    | albuquerque, park-city, southeast-publix, las-cruces, neah-bay      | primary / gap-nearest     | Walmart Inc                                         |
| Albertsons | albertsons | las-cruces (home); Safeway banner in pescadero, neah-bay            | home / gap-nearest        | Albertsons Companies (Safeway is its banner)        |
| Smith's    | smiths     | albuquerque (home), park-city (home)                                | home                      | Kroger banner - source the Smith's Food & Drug mark |
| Kroger     | kroger     | southeast-publix (secondary)                                        | secondary                 | The Kroger Co                                       |
| Amazon     | amazon     | pescadero (Amazon.com), seattle (Amazon Subscribe & Save), neah-bay | halo / secondary          | Amazon.com Inc                                      |

these eight cover every retailer named in the scoreboard region set. Smith's + Kroger can share sourcing effort (same parent) but need distinct marks - Smith's uses its own banner wordmark, not the Kroger logo

## DAM path convention

the compose spec expects each retailer mark at a predictable slug-keyed path in the DAM:

```
brands/kodiak/logos/retailers/<retailer-slug>.png
```

concrete targets once assets are legitimately obtained:

```
brands/kodiak/logos/retailers/costco.png
brands/kodiak/logos/retailers/publix.png
brands/kodiak/logos/retailers/target.png
brands/kodiak/logos/retailers/walmart.png
brands/kodiak/logos/retailers/albertsons.png
brands/kodiak/logos/retailers/smiths.png
brands/kodiak/logos/retailers/kroger.png
brands/kodiak/logos/retailers/amazon.png
```

### convention reconciliation (must resolve before wiring)

the pipeline's existing `retailers.py` uses a DIFFERENT convention: `input_assets/retailer-logos/<retailer>.svg` (local, SVG-first with png/text-band degradation in `lockup.py`). two conventions exist:

- brief / DAM convention: `brands/kodiak/logos/retailers/<slug>.png` (S3 DAM, transparent PNG)
- pipeline-local convention: `input_assets/retailer-logos/<slug>.svg` (repo-local, SVG)

recommendation: make the DAM path the canonical source of truth and have `retailers.py` resolve DAM-first (fetch `brands/kodiak/logos/retailers/<slug>.png` via the same verbatim-key fetch the packshot layer uses), falling back to the local `input_assets/retailer-logos/` dir for offline dev. add a monochrome variant path `brands/kodiak/logos/retailers/<slug>-mono.png` for dark/light lockup selection. do NOT ship two divergent asset stores - pick DAM as primary

## legal / sourcing note (per retailer, non-negotiable)

retailer brand logos are registered trademarks owned by each retailer. they are NOT public-domain and NOT free to scrape from a storefront, favicon, press page, or image search. every mark below must be obtained through the retailer's official brand/partner asset portal or a signed co-marketing / vendor brand-guidelines kit, and used only within the terms of that agreement

- Costco: obtain via Costco supplier/vendor brand guidelines; Costco tightly controls co-branding and generally restricts logo use in supplier marketing without explicit sign-off
- Publix: obtain via Publix vendor/partner brand assets; Publix co-marketing requires category-team approval
- Target: obtain via Target Partners Online / vendor brand portal; Target has a formal partner brand-asset kit with clear-space rules
- Walmart: obtain via Walmart supplier brand guidelines (Retail Link / supplier onboarding); logo use in supplier creative requires approval
- Albertsons: obtain via Albertsons Companies vendor brand assets (covers the Safeway banner too); request both the Albertsons and Safeway marks if both banners appear in a region
- Smith's: obtain via Kroger vendor brand assets (Kroger owns the Smith's Food & Drug banner); request the Smith's banner mark specifically, not the generic Kroger logo
- Kroger: obtain via Kroger vendor/partner brand portal
- Amazon: obtain via Amazon brand usage guidelines / Vendor Central brand assets; the "Amazon" smile wordmark and "Subscribe & Save" lockup have strict usage rules and often require program-specific permission

this is a legal / partnerships action item. it does NOT auto-download and it is NOT an engineering task to "just grab the PNGs." flag to the co-marketing / partnerships owner. until a signed usage right exists per retailer, that retailer's lockup stays off

## technical spec per asset (once legitimately obtained)

apply to every `<retailer-slug>.png` delivered to the DAM path:

- format: transparent-background PNG (alpha channel), lossless. an SVG master is preferred upstream; export the DAM PNG from the vector master
- color: deliver a full-color primary variant AND a monochrome (single-color, typically white-knockout and/or solid-black) variant. the monochrome variant is for dark-lockup placement where full color would clash with the region palette or the message bar
  - full color: `brands/kodiak/logos/retailers/<slug>.png`
  - monochrome: `brands/kodiak/logos/retailers/<slug>-mono.png`
- minimum dimensions: at least 512 px on the logo's longest edge at delivery, so the compose downscale (retailer block sits ~18% of canvas width on the 1080-1920 px canvases) never upscales. horizontal wordmark logos: min 512x160; square/badge marks (Target bullseye, Walmart spark): min 512x512
- resolution / density: export at 2x the largest composite placement so retina/high-DPI previews stay crisp
- safe-area / clear-space: preserve each retailer's published minimum clear space (usually expressed as a fraction of the logo's cap-height or mark diameter - e.g. Target's bullseye clear space, Walmart's spark clear space). bake the clear space into the transparent PNG canvas so the compositor never crops into the protected zone. never stretch, recolor outside the approved variants, rotate, add effects, or place on a busy background that violates the retailer's contrast rule
- placement backing: the compose retailer block already draws a white backing plate behind the mark (compose.py retailer_logo block) - use the monochrome or full-color variant depending on whether the backing plate is present and the region palette behind it

## enforcement / guardrail

- no retailer mark is committed to this repo, the pipeline repo, or the DAM without a documented usage right. `governance/secret-handling` does not cover trademarks, but the same discipline applies: assets with usage constraints do not get bundled casually
- the pipeline default: `retailer_layer_enabled = false` until the eight DAM paths are populated with legitimately-sourced, spec-compliant assets. a composed preview must never block or error on a missing retailer logo - it renders without the lockup and logs the retailer slug as unavailable
