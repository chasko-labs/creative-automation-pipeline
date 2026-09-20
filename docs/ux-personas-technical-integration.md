# Technical Integration Hub — How KODIAK® Posts for Today's Frontier Calls Into Kodiak Internal Systems

> This hub is the reason we do not want to be "dependent" on our own web page. The offline page at `web/kodiak-posts-for-todays-frontier/index.html` is only a picture of the real product — the real product is the living application programming interface and the managed control plane tool that any web property, any Shopify webhook, or any agency script can call the same way. This page is the living Swagger document for marketing. If a line isn't callable here, it isn't shippable.

Read with the other five hubs at `docs/ux-personas-kodiak-complete.md` — the 1982 red wagon, Wasatch Mountains, and Keep It Wild set the voice for all of them. Every card below writes brand names exactly as **KODIAK®**, **KODIAK CAKES®**, **KODIAK POWER CUPS®** and slogans exactly as **Feeding Epic Days & Wilder Lives** and **Nourishment for Today's Frontier** with the KODIAK Bear silhouette doing the visual lifting — see `docs/iso-naming-conventions.md` for the `KODIAK-CAKES-{PRODUCT}-{REGION}-{LOCALITY}-{CHANNEL}-{RATIO}-{YYYYMMDD}-v01.png` pattern and `docs/kodiak-shading.json` for the brown-dominant ramps that keep the kraft box iconic.

### The cross-functional group that handles standardizing data pipelines

When Kodiak connects inventory to Shopify or routes shopper data to a retailer, the same four chairs sit at the table. Every persona below touches the same single cloud file `infra/template.yaml` and the same living Swagger.

---

### John Oja — Director of eCommerce — Salt Lake City and Remote

**Who he is:** The core technical product owner for web properties. He sits between Park City and remote, owns `kodiakcakes.com` on Shopify Plus, and is the first gate for any outside interface — if it slows checkout by 200 milliseconds, if it touches the direct-to-consumer flow, if it changes site speed in Google Search Console, he says no.

**What that means for this pipeline:** John does not open the brown offline page to make ads. He opens the living Swagger at `src/creative_automation/api.py` → `GET /docs` (FastAPI) and calls `POST /pipeline/run` with a brief payload from the same `briefs/kodiak-green-chile.yaml` that Maya wrote. The pipeline returns `report.json` with `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/renders/` paths — which his Shopify Plus theme then pulls via the asset library at `brands/kodiak/heroes/` (mirrored to `input_assets/` locally). The same call the offline page makes when Diego clicks *Render 3 local ads* is the call John's store locator at `kodiakcakes.com/pages/store-locator` makes when it asks for the nearest Albertsons in Alamogordo — one interface, two skins.

**Pain he protects against:** Last agency connector fetched product photos on every page render, tanking Time to First Byte. Now the pipeline's `token_loader.py` pulls `design/tokens/kodiak.json` once (Bear Brown #3B2316 dominant, Blaze Orange #E8530E only on the 8-point bar) and the store phone book once — `GET /retail/stores?market=US-SW-LASCRUCES` — then caches at the edge. No redundant fetch.

**How we show him we care:** The offline page footer literally says *This page is a picture of the real product — the real product is the living Swagger at `/docs`*. Every button in `web/kodiak-posts-for-todays-frontier/index.html` is a thin wrapper: `Fetch → POST /pipeline/run` with the same JSON the `uv run python -m creative_automation.cli --brief briefs/kodiak-green-chile.yaml --assets input_assets --out output_kodiak-green-chile` writes locally. If the Swagger changes, the page must change or the end-to-end test fails (`tests/test_e2e.py` calls the same `run_pipeline()` the interface calls).

**Sprint anchor:** Approve any webhook or authentication change — Jones' handle on `AWS Secrets Manager` or Shopify `X-Shopify-Hmac-SHA256` — and wire his competitor watch: Aldi press on price-competitive mainstream retail means the Shield of provenance (whole grains, 14 grams, real fruit and nuts) must travel with the image metadata — see Product Expansion and Retail Growth insights below.

---

### Landon Ruud *or* Micah Anderson — Senior eCommerce and Senior Digital Marketing Managers — Park City

Shared power-user role — one owns storefront bundles, the other owns lifecycle — both live inside data feeds.

**Who they are:** The hands inside customer data, NielsenIQ, Google Search Console, customer data platform pipes, and Attentive email and short message automation. They route a shopper who just bought Barney Butter or looked at Drizzled Mini Granola Bars into the next email without writing code.

**What that means:** For them the interface is not `POST /pipeline/run` but `POST /ingest/cdp/event` and `POST /retail/ingest/nielsen` plus `GET /search?q=porch breakfast` that returns the same Nova multimodal hit Maya sees as a headline suggestion. Their addiction is the growing training table at `s3://.../brands/kodiak/localization/memory` plus `data/recipes/kodiak-recipes.jsonl` (already 23 baselines localizable via peppers and cheeses, plus new No Sugar Added Waffles, Overnight Oats, Trail Bars, Frozen Breakfast Sandwiches, Drizzled Mini Granola Bars and Turkey Sausage Breakfast Sandwiches — the upsell bundle you flagged as Product Expansion). The managed control plane tool `kodiak_reference_search` sees the same hit as `GET /search` does — one search engine, two callers.

**Pain they carry:** Last holiday the CDP pipe dropped Las Cruces green chile flapjacks because the market `US-SW-LASCRUCES` was typed `US-SW-LasCruces` once — mixed case. Now `docs/iso-naming-conventions.md` enforces `ISO 8601` date `YYYYMMDD` and upper case market `US-SW-LASCRUCES` at write time to `kodiak-creatives-localization-memory` in DynamoDB.

**How we show them we care:** `POST /retail/ingest/nielsen` and `GET /retail/stores` share the same store-set phone book that Priya builds in `docs/how-we-launch-in-every-town.md` — Business Locations CSV → Store Sets → local bucket — so Nielsen shelf placement and Google Search Console clicks reconcile on the same zip without stitching.

**Sprint anchor:** Wire the next bundle: No Sugar Added Waffles + Overnight Oats + Trail Bars as one shopper checkout upsell — same pipeline, different `briefs/kodiak-onthego.yaml` line, one call shows three packs with the same frontier palette.

---

### Arnoldo Romo — Design Director and Web User Interface — Salt Lake City Area

**Who he is:** Manages how the site looks and that the brown kraft box looks right online. He lives inside Canto and Adobe Creative Cloud connectors — his connectors keep product photos sliding into Shopify without anyone re-uploading the hero `715599011627_FlapjackMix_Buttermilk_Front_1.png` after the 736-image raw ingest at `data/raw-ingest/kodiakcakes/images/`.

**What that means:** For him the interface is `GET /assets/{product}/hero` and `GET /assets/brand/logo` and `POST /assets/sync` — the same path the offline page uses when it does `img.src = "../../input_assets/power-cakes/hero.png"`. In production that same read becomes `GET https://cdn.kodiakcakes.com/.../power-cakes/hero.png` via Canto sync plus Shopify `files` endpoint, both wrapped by `src/creative_automation/dam.py` (local `input_assets/` fallback when the connector sleeps). The Swagger for him lives at `/docs` tag `assets` — living docs show `200 image/png, ETag: ...` so he can bind cache.

**Pain he guards:** Prior pack shot was stretched 105 percent to fill 9×16 — brand style failed but the social post still shipped. Now every render is checked at three viewports (1080×1080, 1080×1920, 1920×1080) by `scripts/nova-act-check.py` before the retail handoff — `nova-act-report.json` must say `REG-001` before the same image can be written to Shopify.

**Bear flex he ships:** The offline tool's mountain divider (`--mountain` SVG at 100% width, 48px, Wasatch ridge in Frontier Green S30 #1A2F29) and kraft grain (`--kraft` at 0.06) are token-driven from `docs/kodiak-shading.json` — same shading that keeps the brown box 60 to 70 percent chroma, orange ≤18 percent except the 8-point bar. The crate he sees in the tool is the crate the shopper sees on the site.

**Sprint anchor:** Keep product photos dynamically fresh — his connector heartbeat calls `POST /assets/sync` nightly so the real pack front stays top contrast without anyone retyping hex.

---

### Adam Berberich — Senior Forward Deployed AI Engineer — Dayton, Ohio

**Who he is:** Embedded with market teams where the pipeline meets real users. He takes the living Swagger and the managed control plane tools into the field — wiring `kodiak_pipeline_run` and `kodiak_reference_search` into whatever the local team already uses — and reports back what breaks outside Park City.

**What that means for this pipeline:** Adam's interface is the same `POST /pipeline/run` plus the MCP tool surface at `.agents/mcp-kodiak-reference.json`. His test is deployment-shaped: a new market onboards with a brief YAML and a place row, no code changes, first preview inside one working session. When onboarding needs an engineer instead of a document, that gap is his finding, filed with the market name attached.

**Pain he protects against:** A pipeline that only its authors can deploy. Every hardcoded market, every undocumented env var, every step that works on one laptop is a deployment failure he catches before a customer does.

**How we show him we care:** The deploy runbooks (`docs/plans/`, `scripts/deploy-frontier.sh`) are tested paths, not folklore — he runs them verbatim on a fresh checkout. Failures get fixed in the script, not explained in chat.

**Sprint anchor:** Own the localized-market onboarding path his findings define; sign off that a new persona city onboards without author intervention.

---

### Ryan Street — Senior Forward Deployed AI Engineer — Remote

**Who he is:** Pairs with Adam on field deployments, leaning toward evaluation: does the output hold up in the market it claims? He runs the generated assets past the persona bars — spelling, marks, locality, provenance — and treats every miss as a pipeline defect with a market tag.

**What that means for this pipeline:** Ryan lives in the receipts: `report.json`, `preview.html`, `nova-act-report.json`, the provenance panel. His loop is generate → verify against the card → file or close. The not-nova-act localized suite (`test_r5_kodiak_localized.py`) is his standing army — city × frontier assertions that run without him watching.

**Pain he protects against:** Demos that pass and deployments that fail. A tile that renders in Park City and breaks in Las Cruces is his catch, and the suite carries it after he moves on.

**How we show him we care:** Every preview carries its provenance on its face — engine per tile, seed, season pairing, copy path — so verification never needs a maintainer on call. Silence is never the delivered state.

**Sprint anchor:** Hold the adversarial bar for the diamond sprint: nothing merges that his checks would flag, or it ships with his filed follow-up attached.

---

### Drew Robinson — Forward Deployed AI Architect — Oceanside, California

**Who he is:** Designs how the pipeline lands inside customer systems — where the Lambda ends and their stack begins, what the data contracts guarantee, how the factory library and the live path stay decoupled. He draws the boxes the deploy engineers stand inside.

**What that means for this pipeline:** Drew's artifacts are the architecture docs (`docs/bedrock-agentcore-architecture.md`, the SPEC-reference-library pattern): lever matrix, interface contracts, the rule that the factory never pushes into a live request. His review question for any change is what it does to the contract — new fields, new failure modes, new couplings — and the answer ships in the diff.

**Pain he protects against:** Architecture by accretion: five seasons of special cases nobody can draw. When the season table grows from 4 to 26, he checks the growth is table-shaped (data + reasons) rather than branch-shaped (ifs per holiday).

**How we show him we care:** Contracts are versioned and written down before code lands (`recipe-card@v1` pattern) — the schema exists before the implementation references it, and the plan names the shape before the sprint starts.

**Sprint anchor:** Approve the season-26 table shape and the farms/coops schema before builders land them; own the contract review on every diamond-sprint merge.

---

### External Agency Partners — Contracted Software Engineers and Solutions Architects (Shopify Plus Agency or Integration Consultancy)

**Who they are:** Because Kodiak keeps heavy engineering outside the house, a third-party Shopify Plus agency or integration shop writes the actual webhooks, handles the `Authorization: Bearer ...` and `X-Shopify-Hmac-SHA256` proof, and keeps the interface endpoints breathing at 3 a.m. They never keep credentials on disk — they read from `aws secretsmanager GetSecretValue` at ` /heraldstack/shared/...` never from a file.

**What that means:** For them every endpoint must be a plain `curl` they can copy from `/docs` and paste into Postman. The whole Swagger is the spec — not the web page. The web page is a view. Example hand-off we give them today (same call the offline page's *Render 3 local ads* button runs):

```bash
curl -X POST http://127.0.0.1:8182/pipeline/run \
  -H "Content-Type: application/json" \
  -d @briefs/kodiak-green-chile.yaml \
  -H "Authorization: Bearer $KODIAK_API_TOKEN"
# → {"report": "s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/renders/KODIAK-CAKES-savory-waffles-...-9x16-20250902-v01.png", "preview": "https://.../preview.html", "compliance": "PASS REG-001"}
```

Shopify Plus plus Adobe Creative Cloud webhook wiring looks the same:

```bash
curl https://kodiakcakes.com/admin/api/2024-01/webhooks.json \
  -H "X-Shopify-Access-Token: $SHOPIFY_TOKEN" \
  -d '{"webhook":{"topic":"products/update","address":"https://api.kodiak-posts.internal/hooks/shopify-product","format":"json"}}'
# handler at POST /hooks/shopify-product validates HMAC, then calls POST /assets/sync
```

**Pain they inherit:** Last vendor stored a token in a repo — rotation broke at Black Friday. Now `infra/template.yaml` keeps the log bucket and the retail network table `kodiak-creatives-retail-network` with point-in-time recovery, and the managed control plane reads the hardware-backed lock at `heraldstack-...:16379` — no token on disk.

**Sprint anchor:** They maintain the interface endpoints — their pull request must touch `src/creative_automation/api.py` (FastAPI) and `CONTRIBUTING.md` gateway plus the end-to-end `tests/test_e2e.py` that exercises `GET /search?q=green chile` alongside `POST /pipeline/run` so living docs and background interface stay in sync. Agency branch protection is enforced via `CODEOWNERS` on `src/creative_automation/dam.py` and `src/creative_automation/token_loader.py`.

---

## What the living application programming interface actually serves today — the store that reads the Swagger reads the truth

Today the interface exposes:

- `POST /pipeline/run` — brief in (brand `KODIAK®` enforced, slogan punctuation checked) → three realized ads (1×1, 9×16, 16×9), bear at 24,24, orange 8-point, scrim `#1A1110CC`, plus `report.json` + `report.jsonl` + `preview.html` — same function the `uv run python -m creative_automation.cli --brief briefs/kodiak-green-chile.yaml ...` calls.
- `GET /search?q=What worked for green chile families?&k=3` and `POST /search` — meaning search via `amazon.nova-2-multimodal-embeddings-v1:0` 1024 (fallback Titan) over `data/vectors/kodiak-embeddings.jsonl` mirrored to `s3://.../brands/kodiak/vectors/` — the same search the offline tool's local `places` filter does by meaning.
- `GET /assets/{product}/hero` and `POST /assets/sync` — Canto + Shopify file endpoint wrapped with local `input_assets/` fallback when the connector sleeps.
- `GET /retail/stores?market=US-SW-LASCRUCES` and `POST /retail/ingest/nielsen` — the phone book Priya built via Business Locations Store Sets plus NielsenIQ shelf placement and Google Search Console clicks reconciled per zip — so `docs/how-we-launch-in-every-town.md` and the shopper marketer's report read the same.

The offline page at `web/kodiak-posts-for-todays-frontier/index.html` is a picture of those same calls — every button is a `fetch()` to one of the four above. If the interface changes, the page must change or the end-to-end verification across `1080×1080`, `1080×1920`, `1920×1080` fails before the `S3 sync` to `brands/kodiak/renders/`.

## Competitive, product, and retail signals this hub already encodes

- **Aldi as price press in mainstream** — brown kraft box must carry whole-grain and protein provenance in the image metadata so the store price strip never erases the frontier difference.
- **Product expansion ready:** No Sugar Added Waffles, Overnight Oats, Trail Bars, Frozen Breakfast Sandwiches, Drizzled Mini Granola Bars, Turkey Sausage Breakfast Sandwiches — already seeded as `briefs/kodiak-onthego.yaml`, `kodiak-trail.yaml`, plus `data/recipes/kodiak-recipes.json` 23 baselines localizable via Hatch green chile / jalapeño / chipotle + cheddar / pepper jack / oaxaca / cotija so any retailer can bundle three breakfast plus shopper occasions with one pipeline run.
- **Retail growth pattern:** Rapid brand plus nature-led plus mid-market revenue base — regional grocery plus natural plus club majors already split as the three density hubs at `docs/target-clients-us-local.md` — Mid-market grocery traction note: the tool writes `human_name` `KODIAK-CAKES-...` alongside cloud `brands/kodiak/renders/{product}/{ratio}/` so small grocer and big club both read the same prefix.
- **Partnership potential:** Joe Burrow Foundation and active social campaigns as cause, influencer-led, and co-branded proof — `community` and `brand partnerships` persona boards share the same `web/kodiak-posts-for-todays-frontier/index.html` tool — marketing owns the first step there without a short form.
- **Digital plus data stack:** NielsenIQ plus Google Search Console already wired as the two data sources behind `GET /retail/ingest/nielsen` plus `GET /retail/stores` — shelf placement plus shopper asks plus online and in-store conversions grow without stitching a spreadsheet.
