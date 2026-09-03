# Literal Inventory — every button, token, endpoint, and resource

> The explicit companion to [SYSTEM-OVERVIEW.md](SYSTEM-OVERVIEW.md). That doc explains the system conceptually; this one names the literal parts — actual UI element IDs, actual token names and hex values, actual backend module and endpoint signatures, and actual AWS resource identifiers with live console links. Every AWS fact below was verified against account `946179428633` (us-east-1) live, not read from templates. Verification date: 2026-09-03.

Status labels used throughout:

- `LIVE` — deployed and confirmed present in the account by an API call
- `CODE` — exists in the repo and runs locally, no deployed cloud resource
- `PLANNED` — described in design docs, not yet built

---

## 1. Frontend — literal UI inventory

Single-page app: `web/kodiak-posts-for-todays-frontier/index.html` (1294 lines). Version `0.4.1-28d0c98-20260902` (from `webmcp.json` and the footer `data-mcp-version`). Offline-first — opens over `file://` with no server. Hosted at CloudFront `d37333alc7ojpl.cloudfront.net` (`LIVE`, see section 5).

### 1.1 Buttons — actual element IDs and actions

| element id          | class        | label / purpose                                                       | wiring                                                    |
| ------------------- | ------------ | --------------------------------------------------------------------- | --------------------------------------------------------- |
| `useLocationBtn`    | `btn orange` | "Use my location" — haversine nearest market                          | geolocation -> `locationStatus`                           |
| `showAllBtn`        | `btn ghost`  | show all markets                                                      | reveals full market list                                  |
| `seeNearYouBtn`     | (cta)        | "See near you" demo trigger                                           | Park City demo path                                       |
| `promptUpload`      | `ff-iconbtn` | upload image/document into the brief                                  | file picker, `aria-label` set                             |
| `generateCampaign`  | `ff-go`      | THE single generate button — fans to all formats + localized variants | `data-mcp="generate"`                                     |
| `chipUpload`        | `ff-chip`    | upload as a prompt chip                                               | file input                                                |
| `pathExisting`      | `btn ghost`  | campaign path: build off existing assets                              | `aria-pressed="true"` default                             |
| `pathAdd`           | `btn ghost`  | campaign path: add new assets                                         | `aria-pressed="false"`                                    |
| `pathAuto`          | `btn ghost`  | campaign path: auto-generate                                          | `aria-pressed="false"`                                    |
| `randomProducts`    | `btn ghost`  | pick random SKUs                                                      | fills `productChooser`                                    |
| `downloadPack`      | `btn ghost`  | download ISO-labeled zip from S3                                      | `data-mcp="download-pack"` -> `GET /assets/pack/{market}` |
| `suggestedBtn`      | `btn orange` | show suggested creative                                               | -> `suggestedPreview`                                     |
| `suggestedDownload` | `btn ghost`  | download suggested                                                    |                                                           |
| `scoreRefresh`      | `btn ghost`  | refresh design-system scorecard                                       | recomputes `scoreGrid`                                    |

Plus prompt-chip buttons (`ff-chip`) carrying literal `data-brief` seeds: recipe cards, Costco bulk, riff-past-content, Zac Efron athletic morning, Bears/Keep It Wild, Keep It Wild program.

### 1.2 Components — the `data-mcp` island surface

The UI is instrumented as WebMCP islands (declared in `web/kodiak-posts-for-todays-frontier/webmcp.json`). Each is a live, agent-inspectable component:

| island id                                  | selector                       | backing source                                                         |
| ------------------------------------------ | ------------------------------ | ---------------------------------------------------------------------- |
| `places`                                   | `[data-mcp='places']`          | `data/localization/store-finder-markets.json` (73 markets)             |
| `products`                                 | `[data-mcp='products']`        | `data/products/kodiak-full-catalog.json` (88 SKUs, 20 Amazon listings) |
| `campaign-brief` / `campaign-brief.prompt` | `#campaignBrief`               | the one-line brief input                                               |
| `generate`                                 | `#generateCampaign`            | fan-out trigger                                                        |
| `assets`                                   | `[data-mcp='assets']`          | upload widget -> `POST /assets/upload`                                 |
| `download-pack`                            | `[data-mcp='download-pack']`   | `GET /assets/pack/{market}`                                            |
| `local-flavor`                             | `[data-mcp='local-flavor']`    | derived per season/source, not selectable                              |
| `preview.compose`                          | `[data-mcp='preview.compose']` | pipeline preview, EN + localized                                       |
| `design-system`                            | `#design-system`               | scorecards vs tokens + style guide                                     |
| `footer.version`                           | `[data-mcp='footer.version']`  | version `0.4.1-28d0c98-20260902`                                       |
| `library.browse`                           | `[data-mcp='library.browse']`  | `GET /library/assets` -> `asset_api`                                   |
| `library.report`                           | `[data-mcp='library.report']`  | `GET /library/report` -> `asset_api`                                   |

Console inspection hooks: `KODIAK_VERSION`, `KODIAK_WEBMCP`, `document.querySelectorAll('[data-mcp]')`, `data-testid` markers (`app-version`, `shop-cart-sync`, `csm-cookie-consent`, `marquee-tool`, `cart-drawer`).

### 1.3 Gated action

The full-dispatch button carries a literal gate: `alert('Gated: Full dispatch would fan to all 73 markets x per-retailer (Target/Walmart/Costco/Publix) x EN+top2 languages via pipeline.py - approve sample to dispatch')`. Sample-first is enforced in the UI, not just the backend.

---

## 2. Design tokens — literal names and values

Source: `design/tokens/kodiak.json` (W3C Design Tokens Format, Style Dictionary compatible). CSS is Panda-generated into `web/.../design/styles.css` (preflight custom properties + aspect-ratio vars).

### 2.1 Brand palette (the three frontier colors)

| token path                         | hex       | usage                                                |
| ---------------------------------- | --------- | ---------------------------------------------------- |
| `kodiak.color.brand.bearBrown`     | `#3B2316` | primary — headings, backgrounds, bear logo backdrop  |
| `kodiak.color.brand.blazeOrange`   | `#E8530E` | accent / CTA — buttons, accent bar, protein callouts |
| `kodiak.color.brand.frontierGreen` | `#1A3C34` | secondary — borders, outdoor narrative               |

### 2.2 Neutral ramp (Bear Brown + kraft parchment derived)

| token          | hex       | name                                |
| -------------- | --------- | ----------------------------------- |
| `neutral.0`    | `#FFFFFF` | White                               |
| `neutral.50`   | `#FFF8F0` | Parchment — primary page background |
| `neutral.100`  | `#F4EDE6` | Oatmeal — card / kraft bag          |
| `neutral.200`  | `#E8DDD3` | Stone Light — divider               |
| `neutral.300`  | `#D9CFC6` | Stone — border, disabled            |
| `neutral.400`  | `#B8A99E` | Driftwood — placeholder             |
| `neutral.500`  | `#8C7A70` | Taupe — secondary text              |
| `neutral.600`  | `#6B5A53` | Canyon — muted body                 |
| `neutral.700`  | `#5A4A42` | Espresso — body alt                 |
| `neutral.800`  | `#2E1D14` | Burnt Umber                         |
| `neutral.900`  | `#1A1110` | Ink — darkest text                  |
| `neutral.1000` | `#000000` | Black                               |

Semantic aliases: `background.default -> neutral.50`, `background.inverse -> bearBrown`, `background.accent -> blazeOrange`. Aspect-ratio tokens: square `1/1`, wide `16/9`, portrait `3/4`. Swatch PNGs live under `docs/assets/swatches/`.

---

## 3. Backend — literal module and endpoint inventory

35 Python modules in `src/creative_automation/`, 8278 lines total. Largest: `campaign.py` (665), `api.py` (556), `gateway.py` (447), `context_pack.py` (437), `spin.py` (418), `asset_library.py` (416), `pipeline.py` (390), `dam.py` (351).

### 3.1 HTTP endpoints — all three FastAPI apps

`api.py` — Kodiak Creative Pipeline (19 routes):

```
GET  /health                                            POST /pipeline/run (RunResponse)
POST /brief/validate                                    GET  /search
POST /embed                                             GET  /assets/{product}/hero
POST /assets/sync                                       GET  /retail/stores
POST /retail/ingest/nielsen                             POST /enhance/hero
GET  /campaigns                                         GET  /assets/location/{market}/direct
GET  /assets/location/{market}/retailer/{retailer}/preview
GET  /assets/pack/{market}      (zip download)          POST /assets/upload   (multipart)
POST /campaigns/run-fanned                              GET  /campaigns/job/{job_id}
POST /suggest/run                                       POST /hooks/shopify-product
```

`asset_api.py` — Kodiak Asset Library v1.0.0:

```
POST /library/assets  (201)     GET /library/assets      GET /library/assets/{asset_id}
POST /library/assets/{asset_id}/select                   GET /library/health   GET /library/report
```

`reference_api.py` — Kodiak Reference Library v1.0.0:

```
GET /health    GET /search    GET /reference/{ref_id}    POST /embed
```

### 3.2 Agent-callable tools — status `CODE`, not a live gateway

Important correction to the conceptual overview: the seven tools are **registered in `src/creative_automation/gateway.py` and dispatchable locally** (stdin JSON or `dispatch_tool()`), and mirrored by the manifest `.agents/mcp-kodiak-gateway.json`. There is **no deployed Bedrock AgentCore Gateway** — a live check returned zero gateways, zero agent runtimes, zero Bedrock agents in the account (see section 5.4). So the correct label is `CODE`: the tool registry runs on the machine, the cloud gateway is `PLANNED`.

Discovery contract `list_tools()`; invocation contract `dispatch_tool(name, args) -> {ok, result}`. Every tool composes an already-built local unit and is offline-safe (a miss returns a note, never raises).

| tool                   | composes                                 | required input                  |
| ---------------------- | ---------------------------------------- | ------------------------------- |
| `context_pack`         | `context_pack.build_context_pack`        | market or full brief            |
| `retailer_lookup`      | `retailers.resolve_retailer`             | name (costco / publix / target) |
| `dam_hero_lookup`      | `dam.find_hero_asset`                    | product                         |
| `asset_library_browse` | `asset_library.AssetLibrary.list_assets` | (optional kind filter)          |
| `recipe_card_plan`     | `recipe_card.build_recipe_card`          | market                          |
| `monthly_ingredient`   | `locales.resolve_this_month`             | market                          |
| `run_campaign_tool`    | `runtime.handle_campaign_request`        | brief                           |

---

## 4. Data — literal counts

| store                        | identifier                               | live count                                |
| ---------------------------- | ---------------------------------------- | ----------------------------------------- |
| product catalog              | `data/products/kodiak-full-catalog.json` | 88 SKUs, 20 Amazon listings               |
| markets                      | `store-finder-markets.json`              | 73 markets                                |
| training vectors             | `data/vectors/kodiak-embeddings.jsonl`   | 3144 vectors (1024-dim, Titan v2:0)       |
| sample prompts               | `data/prompts/blog-sample-prompts.jsonl` | 635 prompts                               |
| DynamoDB localization-memory | `kodiak-creatives-localization-memory`   | 0 items (`LIVE` table, seeded at runtime) |
| DynamoDB retail-network      | `kodiak-creatives-retail-network`        | 0 items (`LIVE` table, GSI `byMarket`)    |

Both DynamoDB tables exist and are empty today (0 rows, live-scanned) — they populate on first campaign run and via the learning loop. The seeded localization knowledge is **not** in DynamoDB yet; it lives as a corpus in S3 (`brands/kodiak/localization/`) that feeds the Bedrock Knowledge Base. That is the retrieval source at generation time; DynamoDB is the write-back memory that fills as campaigns run.

### 4.1 Seeded localization — real records, live-read from S3

Pulled live from `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/localization/localization-training-data.jsonl`. Each record is `{text, metadata}` where `text` is the retrieval string and `metadata` carries structured fields (`place, market, retailer, audience, message, zip, cue, brand, source`). Six real seeded markets:

| market            | place                        | audience                                           | message                                                            | photo cue                                                     |
| ----------------- | ---------------------------- | -------------------------------------------------- | ------------------------------------------------------------------ | ------------------------------------------------------------- |
| `US-MW-WASATCH`   | Park City, Wasatch Mountains | outdoor families, ski + hike households            | Keep It Wild — protein-packed whole grains for today's frontier    | Wasatch alpenglow, pine, boulder, snow at dawn                |
| `US-SW-LASCRUCES` | Las Cruces + Alamogordo NM   | green chile families, Hatch roast households 28-45 | Green chile meets grizzly — protein for your Las Cruces frontier   | roasted Hatch green chile in flapjacks, Organ Mountains bench |
| `US-SW-ALBQ`      | Albuquerque NM               | high desert families, adobe morning                | Desert dawn flapjacks — 14 grams for your high desert day          | red chile and pinon, enamel mug on portal                     |
| `US-SC-AUSTIN`    | Austin TX                    | breakfast taco families, keep-it-weird hosts       | Breakfast tacos meet flapjacks — whole grains that keep up         | salsa over flapjacks, food truck corner                       |
| `US-SE-FL`        | Miami + Orlando FL           | Cuban and Puerto Rican families, porch breakfasts  | Family frontier — protein for your Florida morning                 | guava and cafe con leche beside stack                         |
| `US-SE-COAST`     | Savannah + Charleston        | porch families, Gullah seasonality                 | Southern porch stack — protein-packed whole grains for your family | peach and pecan                                               |

Every field above is verbatim from the live corpus (source tag `regional-cultural-database`). These are the rows Nova retrieves as the context pack — the "winning message + audience + photo cue for this market" the architecture doc describes.

### 4.2 Locality deep-seed — Park City 84098

A single market can carry a much deeper seed. Live-read `brands/kodiak/localization/park-city-84098.json` (schema `locality-v1`, generated 2026-09-02) carries: market `US-MW-PARKCITY-84098`, Summit County / Wasatch Back, coordinates `40.6461, -111.498`, named retailer storefronts (Target + Walmart Kimball Junction on UT-224, Smith's on Kearns Blvd, plus a natural-channel halo), and structured `audience_segments` — e.g. "mountain families" age 30-48 with cues `weekend griddle`, `Bear Bites in lunchboxes`, `cast iron at cabin`, `enamel mugs`. This is the granularity that lets the same three products produce a Park-City-specific ad distinct from an Austin one.

### 4.3 Seeded photos and renders — real DAM objects

The DAM holds 296 objects under `brands/kodiak/` (live count). Seeded source heroes and generated renders both live there:

- source heroes (`LIVE`): `brands/kodiak/heroes/power-cakes/hero-real.png`, `.../bear-bites/hero.png`, `.../oatmeal-cup/hero.png`, plus the bear logo `brands/kodiak/logos/kodiak-bear.png`
- generated renders (`LIVE`), organized by campaign / product / ratio, e.g. the Costco campaign: `brands/kodiak/renders/docs-assets/kodiak-costco/power-cakes/1x1/power-cakes_1x1.png`, `.../9x16/power-cakes_9x16.png`, `.../16x9/power-cakes_16x9.png`, plus a `preview.html` per campaign
- seeded campaigns present in renders: `kodiak-costco`, `kodiak-diner`, `kodiak-holiday` (and more — 296 objects total)
- brand-lore raw ingest (`LIVE`): `brands/kodiak/raw-ingest/kodiakcakes/` holds the source imagery and case studies (recipe photography, nutrition-fact panels, the Forbes/Graphic Packaging brand references)

Committed copies of the preview renders also ship in-repo under `docs/assets/previews/` (kodiak-costco, kodiak-diner, kodiak-holiday, kodiak-target, kodiak-publix, kodiak-on-the-go, kodiak-trail, kodiak-subscription) so the seeded output is visible in GitHub without S3 access — see [visual gallery](../visual-gallery.md).

---

## 5. AWS resources — literal identifiers, live-verified

Account `946179428633`, region `us-east-1`. Every row confirmed by a live API call on 2026-09-03.

### 5.1 Storage — S3 (`LIVE`)

| bucket                                            | role                                                             |
| ------------------------------------------------- | ---------------------------------------------------------------- |
| `chasko-creative-dam-946179428633-us-east-1`      | the DAM — style library, heroes, renders, references, `library/` |
| `frontier-bryanchasko-com`                        | static website origin                                            |
| `kodiak-creatives-cf-logs-946179428633-us-east-1` | CloudFront access logs                                           |
| `kodiak-creatives-logs-946179428633-us-east-1`    | pipeline log bucket                                              |

### 5.2 Content delivery — CloudFront (`LIVE`)

Distribution `E3GEX8LSRX6OYS`, domain `d37333alc7ojpl.cloudfront.net`, status **Deployed**, enabled. Aliases: `frontier.bryanchasko.com`, `kodiak.bryanchasko.com`.

- Console: `https://us-east-1.console.aws.amazon.com/cloudfront/v4/home#/distributions/E3GEX8LSRX6OYS`

### 5.3 Databases — DynamoDB (`LIVE`)

| table                                  | keys                          | billing                  |
| -------------------------------------- | ----------------------------- | ------------------------ |
| `kodiak-creatives-localization-memory` | PK `market`                   | PAY_PER_REQUEST, PITR on |
| `kodiak-creatives-retail-network`      | PK `store_id`, GSI `byMarket` | PAY_PER_REQUEST          |

### 5.4 Models — Bedrock (`LIVE` access) and AgentCore (`PLANNED`)

Confirmed available in the account: `amazon.titan-embed-text-v2:0` (the only embedder), `amazon.nova-micro-v1:0`, `amazon.nova-lite-v1:0`, `amazon.nova-canvas-v1:0`, plus the newer `amazon.nova-2-lite-v1:0` and `amazon.nova-2-multimodal-embeddings-v1:0`. No third-party models used in the product.

AgentCore deployment status, live-checked: `ListGateways` = 0, `ListAgentRuntimes` = 0, `bedrock-agent ListAgents` = 0. The runtime/gateway wrap is `PLANNED`; the local pipeline is the live path.

### 5.5 CI/CD — CodeBuild (`LIVE`)

- Project: `kodiak-creatives-ci`
- Service role: `arn:aws:iam::946179428633:role/kodiak-creatives-ci-role` (created 2026-09-03 18:42 UTC)
- Builds run to date: 31
- Gate: `ruff check .` -> `pytest -x -q` -> `cfn-lint infra/template.yaml` (fail-fast, `RUN_SLOW=false`)
- Console: `https://us-east-1.console.aws.amazon.com/codesuite/codebuild/946179428633/projects/kodiak-creatives-ci`

### 5.6 Observability — CloudWatch Logs + X-Ray (`LIVE`)

- Log group: `/kodiak/creative-pipeline`, 30-day retention
- X-Ray sampling rule: `kodiak-creative`, service `kodiak-creative*`, fixed rate `0.10`, priority `9000`
- Real traces in the last 6h: 1 (trace `1-6a99c470-a01ef2a0f003da37183f4fcc`, no error)
- The one real trace, deep-linked: `https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#xray:traces/1-6a99c470-a01ef2a0f003da37183f4fcc?~(query~()~context~(timeRange~(delta~21600000)))`
- X-Ray traces console (all): `https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#xray:traces/query`
- Log group console: `https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logsV2:log-groups/log-group/$252Fkodiak$252Fcreative-pipeline`

---

## 6. Status summary — what is live vs code vs planned

| capability                                  | status         | evidence                                                |
| ------------------------------------------- | -------------- | ------------------------------------------------------- |
| frontend SPA (offline + hosted)             | `LIVE`         | CloudFront E3GEX8LSRX6OYS Deployed                      |
| S3 DAM + logs + website + CF-logs buckets   | `LIVE`         | 4 buckets confirmed                                     |
| DynamoDB tables (empty, seed at runtime)    | `LIVE`         | 2 tables, 0 rows (live-scanned)                         |
| seeded localization corpus (6+ markets)     | `LIVE`         | S3 `localization-training-data.jsonl`, feeds Bedrock KB |
| seeded photos + renders (296 DAM objects)   | `LIVE`         | `brands/kodiak/` heroes + renders + raw-ingest          |
| CodeBuild CI gate                           | `LIVE`         | 31 builds, role since 18:42 UTC                         |
| CloudWatch Logs + X-Ray                     | `LIVE`         | log group + rule + 1 real trace                         |
| Bedrock Nova + Titan access                 | `LIVE`         | ListFoundationModels                                    |
| local pipeline `run_pipeline()`             | `LIVE` (local) | `tests/test_e2e.py`                                     |
| 7 gateway tools                             | `CODE`         | registered in gateway.py, no deployed gateway           |
| AgentCore Gateway / Runtime / Bedrock Agent | `PLANNED`      | live check: 0 / 0 / 0                                   |
| AgentCore Memory, Nova Act visual QA        | `PLANNED`      | design docs only                                        |

---

## Related

- [SYSTEM-OVERVIEW.md](SYSTEM-OVERVIEW.md) — conceptual explainer + diagrams
- [Bedrock AgentCore Architecture](../bedrock-agentcore-architecture.md) — RAG data flow
- [Team lanes](team-lanes.md) · [Dispatch guideline](dispatch-guideline.md)
- [Observability runbook](../observability-runbook.md) — X-Ray + structured logging usage
