# Kodiak Context — 2026-09-03

> Persisted context for `bryanchasko.com` / Kodiak frontier work. Sources: prior sweeps 2026-09-03 — DNS/ACM/CF/Route53, repo inventory `c3cde53`, web artifacts, infra/cost.

## 1. DNS Fix — kodiak.bryanchasko.com

### Current state (verified 2026-09-03)

- **dig kodiak.bryanchasko.com → NXDOMAIN** (SOA `ns-1222.awsdns-24.org`); no A/AAAA/CNAME present.
- **ACM (946179428633 us-east-1)** `arn:aws:acm:us-east-1:946179428633:certificate/5da84625-8072-4923-9e9e-b0907419419f`
  - Domain: `kodiak.bryanchasko.com` + SAN `*.bryanchasko.com`
  - Status: `PENDING_VALIDATION`, `InUseBy: []`, Created `2026-09-03T00:20:22.787Z`
  - **Validation CNAMEs required (not yet in Route53):**
    - `_d35db8fae3ee32365940b83ac8e90ff5.kodiak.bryanchasko.com. CNAME _fcfeaa5be31f2beb303bdbbf4a840bea.jkddzztszm.acm-validations.aws.`
    - `_1d23a374d1dfafff64357a45563ccd80.bryanchasko.com. CNAME _5679236fe6d67c32e082bcd27eeb7ebc.jkddzztszm.acm-validations.aws.`
  - `validation_cnames_present_in_route53: false`
- **CloudFront 946179428633** `E3GEX8LSRX6OYS` / `d37333alc7ojpl.cloudfront.net` — Status `Deployed`
  - Aliases: `["frontier.bryanchasko.com"]` — `kodiak_alias_present: false`
  - Viewer cert: `arn:aws:acm:us-east-1:946179428633:certificate/4f438942-bf67-4d2e-adef-965530c22445` (frontier, ISSUED) — `kodiak_cert_not_attached: true`
  - Comment: `KODIAK Frontier — unlisted, password cakes, noindex — frontier.bryanchasko.com pending cert`
- **Route53 211125425201**
  - Active zone: `Z09216723VDB0N04DM9LL bryanchasko.com` (16 records, NS `ns-1222.awsdns-24.org/ns-1845.awsdns-38.co.uk/ns-380.awsdns-47.com/ns-796.awsdns-35.net`) — delegated (`dig NS` matches)
  - Inactive zone: `Z09211563O43GHEAV4NJY bryanchasko.com` (Terraform, 8 records)
  - `frontier.bryanchasko.com A Alias d37333alc7ojpl.cloudfront.net` present in Z09216723VDB0N04DM9LL and resolves; `kodiak` has no record.

### Fix steps (ordered)

1. **Create ACM validation CNAMEs** in active zone `Z09216723VDB0N04DM9LL` (Route53 ChangeResourceRecordSets, Type CNAME, TTL 300):
   ```text
   _d35db8fae3ee32365940b83ac8e90ff5.kodiak.bryanchasko.com → _fcfeaa5be31f2beb303bdbbf4a840bea.jkddzztszm.acm-validations.aws.
   _1d23a374d1dfafff64357a45563ccd80.bryanchasko.com → _5679236fe6d67c32e082bcd27eeb7ebc.jkddzztszm.acm-validations.aws.
   ```
2. **Wait for ACM ISSUED**: `aws acm describe-certificate --certificate-arn arn:aws:acm:us-east-1:946179428633:certificate/5da84625-8072-4923-9e9e-b0907419419f --region us-east-1` → `Status: ISSUED`. Verify via `dig CNAME _d35db8fae3…` propagates.
3. **Attach kodiak alias to CloudFront** `E3GEX8LSRX6OYS`: `Aliases += kodiak.bryanchasko.com`, `ViewerCertificate.ACMCertificateArn = 5da84625…`, `SSLSupportMethod sni-only`, `MinimumProtocolVersion TLSv1.2_2021`. Wait `Status Deployed`.
4. **Create Route53 alias for kodiak** in Z09216723VDB0N04DM9LL:
   - `kodiak.bryanchasko.com A Alias → d37333alc7ojpl.cloudfront.net` (HostedZoneId `Z2FDTNDATAQYW2` for CF) + `AAAA Alias` same target, EvaluateTargetHealth false.
5. **Verify**: `dig kodiak.bryanchasko.com` → CF edge IPs; `curl -I https://kodiak.bryanchasko.com` 200; `openssl s_client -connect kodiak.bryanchasko.com:443 -servername kodiak.bryanchasko.com` shows new cert SANs.
6. **Cleanup**: confirm inactive zone Z09211563O43GHEAV4NJY not authoritative; optionally delete or keep Terraform state unchanged.

## 2. Repo State — c3cde53 (HEAD c3cde53fce59 / main, up-to-date with origin/main)

- **web/kodiak-posts-for-todays-frontier/index.html**: 89,461 bytes at c3cde53 (759 lines; workspace now 89,947 bytes / 88K). Commit `c3cde53` fix: assets JSON/YAML brief attach, 88 SKUs not 12, 23 profiles → GitHub, Park City & Wasatch Back 3 samples auto-render. Diff `c3cde53^..c3cde53`: 1 file 26+/11-.
- **data/products/kodiak-full-catalog.json**: UNTRACKED at c3cde53 and HEAD (exists on disk 110K). Dict keys `metadata/products/amazon_listings/brand_lore`; `products=88` SKUs (handles with images, category, price_usd, url). metadata counts: 88 sitemap_product_urls, 84 non-gift, 88 pages HTML, collections flapjack-waffle-mix 11, cups 16, frozen 17 etc. Also `frontier-gaps.json`, `store-finder-markets.json` in data/products/. Not in `git ls-tree` at c3cde53 (added Sep 2 untracked).
- **data/localization/market-languages.json**: 45,990 bytes, dict with metadata `total_markets 73, total_variants_per_market 3, total_localized_variants 219, auto_produce true`. Source `store-finder-markets.json` + Census ACS S1601 + 2020 PL94. 73 markets (El Paso ES, Burlington FR, SF ZH etc haversine).
- **design/tokens/kodiak.json**: W3C DTFM + Style Dictionary. `kodiak.color.brand bearBrown #3B2316, blazeOrange #E8530E, frontierGreen #1A3C34`; neutrals warm 0 #FFFFFF upward; 8pt base scale semantic aliases (compose.py 48px = xl32+lg24).
- **docs/ux-personas-kodiak-complete.md**: 215 lines, ~41 card/persona hits, 6 `##` sections (Brand Management Park City, Creative/Design brown box, Growth/Digital Commerce, Community/Partnerships Bear in Wild, Shopper Marketing hubs, Technical Integration living Swagger). Sprint anchor notes 23 baselines at kodiak-recipes.json + 345 recipe pages.
- **src/creative_automation/**: at c3cde53: `api.py, brief.py, cli.py, compliance.py, compose.py, dam.py, embeddings.py, enhance.py, generate.py, glimmer.py, __init__.py, localize.py, pipeline.py, reference_api.py, suggest.py, token_loader.py, tokens/__init__` (+ tests). Pipeline composes HTML previews from tokens + products + personas.
- **Untracked / gitignored**: `data/` catalog/market files, `web/` built artifacts, infra local state — intentional; do not commit without DVC/S3 decision.

## 3. Web Requirements

### web/kodiak-posts-for-todays-frontier/index.html (760 lines, 89947 bytes / 88K, v0.4.1-28d0c98-20260902) + glimmer-proxy.js (4.1K)

- **HEAD 200 verified**: `<!doctype html>`, Typekit `zjt4wyq`, `kodiak-version` meta, webmcp manifest (`places/products/recipes/market-languages/brief-yaml/preview`), cakes password gate (`?cakes=1` bypass), design tokens `--brown/kraft/bear-mark/mountain`, `gin+museo-sans/kodiak_sans`.
- **Structure**: header (bear mark, mountain, nav), hero, frontier gaps, product grid (88 SKUs rendered via JS from catalog), persona cards, market selector (73 markets), preview composer canvas, footer with version.
- **Data bindings**: fetches `data/products/kodiak-full-catalog.json`, `data/products/frontier-gaps.json`, `data/localization/market-languages.json`, `data/products/store-finder-markets.json` — relative paths; requires S3/CloudFront origin or local `python -m http.server`.
- **Security/SEO**: `noindex, nofollow` (unlisted), password `cakes` gate via JS (client-side, not auth), frontier comment `unlisted, password cakes`.
- **Requirements**: serve via CloudFront `frontier.bryanchasko.com` (current) and `kodiak` alias after DNS fix; CORS allowed for `*.bryanchasko.com`; cache `index.html` no-cache, assets immutable.

## 4. Glimmer

- **src/creative_automation/glimmer.py** + **web/kodiak-posts-for-todays-frontier/glimmer-proxy.js (4.1K)** — proxy between preview canvas and generation pipeline.
- **Purpose**: real-time style transfer / token-aware image glimmer (overlay brand tokens on product/lifestyle images), bridges `enhance.py` / `generate.py` (Bedrock Nova Canvas) to DOM canvas.
- **Web integration**: `glimmer-proxy.js` loaded in `index.html`, listens to `postMessage` from compose preview, forwards to `/glimmer` endpoint (api.py → Bedrock). Handles `kodiak.json` tokens, `kodiak-shading.json` references.
- **Tokens**: reads `design/tokens/kodiak.json` via `token_loader.py` → CSS vars `--kodiak-*`; glimmer applies bearBrown/blazeOrange/frontierGreen with shading presets.
- **State at c3cde53**: functional locally; production requires ACM+CF alias + API Gateway/Lambda (`reference_api.py`) wiring.

## 5. Infra + Cost (sweep snapshot)

- **Single CloudFormation** `infra/template.yaml` (162 lines) at `/home/bryanchasko/code/chasko-labs/creative-automation-pipeline/infra/template.yaml`
  - Stack: `chasko-creative-dam-946179428633-us-east-1` (S3 `StyleLibraryBucket`) + DynamoDB `kodiak-creatives-localization-memory` (market/place_message_id) + DynamoDB `kodiak-creatives-retail-n…` (retail nodes) — single file creates entire stack.
  - S3 + DynamoDB on-demand (low cost), CF `E3GEX8LSRX6OYS` + Route53 + ACM (free).
- **VALKEY / supervisor**: localized memory cached in Valkey (keys `kodiak:...`), supervisor manages pipeline workers — filesystem + Valkey + supervisor infra noted in sweep 4.
- **Cost**: S3 storage < $1/mo, DynamoDB on-demand ~ $0, CloudFront data transfer minimal (preview traffic), Bedrock Nova Canvas on-demand generation.

## 6. Open Tasks

- **Recipe DB**: 23 baselines at `kodiak-recipes.json` → 345 recipe pages; DB schema + seeding + preview integration pending.
- **Newsletter**: `docs/newsletter-breakdown.md` (2056 bytes, Sep 2 23:15) outlines segmentation; automation pipeline for weekly frontier gaps newsletter open.
- **Scorecards**: creative scorecards (compliance.py / suggest.py) — brand compliance scoring per market, not yet wired to web.
- **Rust helper**: `rust helper` (likely `src/helper` or WASM image processor for glimmer/compose) — scaffold pending; referenced in open tasks list.
- **ec3d283b**: commit `ec3d283b` — referenced as anchor for regression or feature branch; verify diff vs `c3cde53` before merging.
- **DNS**: complete kodiak fix above (ACM validation → CF alias → Route53 alias → verify). Blocks public `kodiak.bryanchasko.com` launch.

---

_Generated 2026-09-03 from parallel sweeps. File: `docs/kodiak-context-2026-09-03.md`. S3Vectors upsert attempted (gracefully ignored if creds absent)._
