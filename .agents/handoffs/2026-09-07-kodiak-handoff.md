# kodiak create-page handoff — 2026-09-07

repo root: /home/bryanchasko/code/chasko-labs/creative-automation-pipeline
create-page source: web/kodiak-posts-for-todays-frontier/ (index.html, design/components.css, js/*.js)

## git state (coordinates, observed)
- branch: main — CLEAN (git diff-index --quiet HEAD => CLEAN)
- git log --oneline -3:
  - 9993901 redesign campaign-input as scope-first guided brainstorming flow  <- THIS session, deployed
  - 2f33398 chore(kodiak): bump 0.1.025 -> 0.1.026 (DAM Type facet)
  - 9225d7e fix(kodiak-ui): DAM Type facet chips render only on match (#168)
- open PRs: #141 (docs/next-sprint-briefing, OPEN, docs only — NOT code, safe to leave/merge on read)
- deployed == merged: 9993901 is both on origin/main AND live (verified below). no drift.

## live AWS truth (observed output, not config)
- CloudFront E3GEX8LSRX6OYS: Status=Deployed, domain d37333alc7ojpl.cloudfront.net
  (aws cloudfront get-distribution --id E3GEX8LSRX6OYS --profile bryanchasko-kiro)
- live version meta: 0.1.027-2f33398-20260907
  (curl https://d37333alc7ojpl.cloudfront.net/index.html | grep kodiak-version)
- live js/prompt-chips.js serves redesign: 4x __campaignScope refs (not stale cache)
- DAM Lambda kodiak-creatives-generate-GenerateLambda-aXnlH2VlmxEM image (us-east-1, bryanchasko-kiro):
  sha256:1e9c23651994c17fb61959b311edf7d600392064358fb8b7145e9c6587214726
  -> UNCHANGED this session (no backend src/ change). rollback ref in prior summary: sha256:513029c1
  -> deploy-frontier.sh does NOT ship the Lambda; backend changes need separate ECR push + update-function-code

## what shipped this session (iteration-4, live-verified)
scope-first guided brainstorming redesign of the campaign-input card:
- scope radiogroup (nationwide / nationwide-localized / local) is now the FIRST decision; Create +
  full-campaign generate both read window.__campaignScope. removed the 3 post-Create scope buttons.
- 7 theme chips regrouped into 4 clusters (what to make / retailer / creative angle / partner),
  additive multi-select via managed-region sentinel "\u2014 directions:" — does NOT clobber user text.
- #localFlavor un-hidden inline (market-tied seasonal readout "In season here").
- reorder scope->market+season->direction->products->brief; products relabeled "Feature products (up to 3)".
- backend /generate body shape unchanged {prompt,market,product,scope,mode}.
- Nova Act (Bedrock/IAM, acct 946179428633, no API key) verify: ALL 6 criteria PASS, 0 console errors.

## evidence staged locally (/tmp — NOT mac-mini)
- /tmp/kodiak-verify-load-20260907T190153Z.png (post-load full card, real render mean rgb ~203,191,176)
- /tmp/kodiak-verify-chips-scope-20260907T190153Z.png (2-chip + scope-select)
- /tmp/kodiak_novaact_verify.py (verify harness, scratch — not in repo)
- /tmp/kodiak-novaact-parked/*.py (4 iter-3 nova-act harnesses parked; ruff-dirty, gitignore-or-lint candidate)

## decisions LOCKED (do not re-ask)
- default scope = local/single-market — coherent with Park City default + market-tied flavor readout
- chip accumulation = managed-region sentinel, not textarea overwrite — least-fragile, preserves user prose
- per-season ingredient chips WALLED OFF — flavorMap is market-keyed, only 5 markets + _default; building
  season x produce grid would fabricate content. needs data authoring, not a UI pass.
- per-platform DAM axis WALLED OFF — no platform metadata in S3; needs x-amz-meta tagging at publish
- park nova-act scripts in /tmp before push (ruff lints whole tree) — do NOT use --no-verify

## genuinely OPEN (waiting on Bryan / next session)
- durable "browse past assets" depth: product-line facet needs raw-ingest S3 key->catalog join;
  per-platform axis needs x-amz-meta platform tagging. backend-shaped, not CSS.
- llms.txt never deploys (omitted from deploy-frontier.sh upload set; stale in S3 since 2026-09-03; zero render impact)
- 2 cosmetic 404s live: design/assets/kraft-paper-texture.png, design/fonts/NotoSans-Latin.woff2
- 4 parked nova-act harnesses: lint+land in tests/nova-act/ (does not exist yet) OR gitignore

## ENV FIX NEEDED (blocks MCP memory: s3vectors, valkey)
- stale root-owned ~/.aws/sso/cache/<sha1(kiro-sso)>.json blocks botocore/Nova-Act token read
  (AWS CLI works — separate cache). e2e-tester cleared it for its run.
- permanent fix: run as bryanchasko: aws sso login --sso-session kiro-sso
