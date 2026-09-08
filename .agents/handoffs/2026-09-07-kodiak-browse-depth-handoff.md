# kodiak browse-depth handoff — 2026-09-07 (evening)

repo root: /home/bryanchasko/code/chasko-labs/creative-automation-pipeline
create-page source: web/kodiak-posts-for-todays-frontier/ (index.html, design/components.css, js/*.js)

## git state (coordinates, observed)
- branch: main — CLEAN except `?? .agents/handoffs/` (leave it)
- git log --oneline -2:
  - a0548ab feat(kodiak-dam): browse depth — product-line facet + per-platform publish tags <- THIS session, deployed
  - 9993901 redesign campaign-input as scope-first guided brainstorming flow
- origin/main == a0548ab (pushed via orin, hooks green, never --no-verify)

## live AWS truth (observed output, not config)
- CloudFront E3GEX8LSRX6OYS: domain d37333alc7ojpl.cloudfront.net
- live version meta: 0.1.028-9993901-20260907
  (curl https://d37333alc7ojpl.cloudfront.net/index.html | grep kodiak-version)
- DAM Lambda kodiak-creatives-generate-GenerateLambda-aXnlH2VlmxEM image (us-east-1, bryanchasko-kiro):
  sha256:709752c6c60ff45e0fb24b382e9b649d333f9c0ca3f1417ae2be3a8a57b89ff8, State=Active
  -> rollback ref: sha256:1e9c23651994c17fb61959b311edf7d600392064358fb8b7145e9c6587214726
  -> deploy-frontier.sh does NOT ship the Lambda; backend = ECR push + update-function-code
  -> docker build MUST pass --provenance=false --sbom=false (Lambda rejects OCI attestations)
- live /assets/library products: 200, 1688 total, tiles carry product_line + platforms + urls
- live ideas tab: 573 renders, platforms [] (pre-tag stock — correct, tagging starts with this image)
- llms.txt live at 200 text/markdown; assets/kraft-paper-texture.png 200; fonts/NotoSans-Latin.woff2 200
  (old design/assets/* and design/fonts/* paths are unreferenced now — their 404s are expected)

## what shipped this session (backend spike, live-verified)
- product-line facet: dam_library._load_product_line_index inverts sku-photo-map
  (photo_key + fallbacks) to catalog category. photo claims outrank fallback claims,
  majority wins, alphabetical tiebreak. tiles carry product_line, None when unknown.
- per-platform axis: generate_lambda._upload_render writes x-amz-meta-platforms from
  req_platforms (default all seven PLATFORMS; insta alias; S3-safe chars only).
  dam.head_metadata reads it; ideas tiles expose platforms. preview path untagged (copy deferred).
- infra/generate.Dockerfile ships kodiak-full-catalog.json (112KB) — without it the index soft-empties.
- scripts/deploy-frontier.sh uploads llms.txt now (FILES list, text/markdown).
- design/components.css asset refs fixed to ../assets and ../fonts (URL-only, no visual change).
- 4 parked nova-act harnesses landed lint-clean in tests/nova-act/ (not pytest-collected).
- tests: new tests/test_dam_library.py; platform-tag tests appended to test_generate_lambda.py.
  full suite 412 passed, whole-tree ruff clean.

## decisions LOCKED (do not re-ask)
- default scope = local/single-market.
- chip accumulation = managed-region sentinel, never textarea overwrite.
- per-season ingredient chips OUT — flavorMap is market-keyed, 5 markets. leave it.
- browse tiles: product_line is SINGULAR (primary). 9 shared photos span categories;
  majority + alpha tiebreak is the documented rule, not a bug. do not "fix" to a list
  without bryan asking.
- publish tags use canonical slugs (PLATFORMS + blog); insta accepted as input alias only.
- park nova-act scripts in /tmp before any push. ruff lints the whole tree. never --no-verify.
- commit through orin (git+CI dispatcher subagent). never push with untracked scripts in tree.

## genuinely OPEN (next session candidates)
- NEXT TASK (one line): run the declutter backlog as one removal-only simplification pass
  and close #17, #18, #19, #20, #21, #30, #31 — remove only, add nothing, no facet
  chips until the page is google-simple. verify each live via Nova Act first; the
  iteration-4 redesign may have already killed some, close those on sight.
- facet chips UI for product_line + platforms AFTER the simplification pass (data is live).
- follow-ups, not this pass: #23 type-scale + brand-font, #24 harden core flow + E1-E9 gate,
  #32 auto-produce wrong markets (El Paso/Burlington).
- s3vectors bridge SSO token broken (store fails "Token for kiro-sso does not exist") —
  findings are in valkey (kodiak:sprint:current, kodiak:spike:backend-depth, kodiak:spike:backend-live).
- system python3.12 botocore cannot load the kiro-sso token (AWS CLI 2.35 can) —
  use AWS CLI or Lambda role creds for live probes, not system python boto3.
- aws s3api --metadata needs JSON form on CLI 2.35 (shorthand comma-split breaks).

## ENV notes
- SSO cache under ~/.aws/sso/cache is bryanchasko-owned, sts works. if s3vectors/valkey
  MCP fail, check for a stale root-owned cache file first, then: aws sso login --sso-session kiro-sso.
