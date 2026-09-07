# One-shot briefing — Kodiak creative-automation-pipeline, next sprint

Paste the block below as the opening prompt of a fresh `kiro-cli` session launched as
`poltergeist-harald-core-anchor` on rocm-aibox, cwd `~/code/chasko-labs/creative-automation-pipeline`.
It is self-contained: it carries the verified ground truth, the six tracks, the decisions that gate
work, and the dispatch-by-domain map so the anchor can drive without re-discovering the codebase.

---

launch as poltergeist-harald-core-anchor. project: chasko-labs/creative-automation-pipeline
(repo at ~/code/chasko-labs/creative-automation-pipeline on rocm-aibox). the previous sprint MERGED to
main (merge commit 5759453, PR #140) — start from a clean main, cut a fresh feature branch, dispatch to
ghosts, do not solo-debug, do not ask permission on reversible work. CI is a LOCAL pre-push gate (no
CodeBuild required). every deploy goes through scripts/deploy-frontier.sh which REFUSES on version drift —
run scripts/bump-version.sh before every deploy. all repo writes via ghost-orin-ci-cd; front-end/CSS via
ghost-liora; MV3/vanilla-JS source via ghost-ellow-mv3-coder; AWS/Bedrock/infra via
poltergeist-stratia-aws-infra + poltergeist-myrren-nova-inference; commit/deploy/PR via ghost-orin-ci-cd.
never push to main; land everything on a branch + PR and hold the merge for Bryan + a validator PASS.

GROUND TRUTH (verified last sprint — do NOT re-assume these are greenfield):
- Art Director model is ALREADY imported + live: src/creative_automation/art_director.py, imported-model
  ARN arn:aws:bedrock:us-west-2:946179428633:imported-model/cx15b77k5nge, region us-west-2, account
  bryanchasko-kiro (946179428633). It produces VOICE/COPY (adventurous|nourishing), NOT imagery. It is
  wired in code but NOTHING calls it from /generate (grep: only art_director imports art_director).
  Overridable via env KODIAK_ARTDIRECTOR_MODEL_ARN / KODIAK_ARTDIRECTOR_REGION.
- Asset-ingest backend EXISTS but is NOT routed: src/creative_automation/asset_api.py (POST /library/assets)
  + asset_library.py (classify -> sha256 -> exact-dedup -> S3 put + JSON sidecar). grep api.py for
  library/assets / asset_api / add_asset returns NOTHING — it is written but not mounted on the running API.
- Embeddings already target amazon.nova-2-multimodal-embeddings-v1:0 (1024 dims, Titan text fallback) in
  src/creative_automation/embeddings.py; batch-only today (embed_batch over curated dirs) — add_asset never
  calls it.
- The generate path is a container-image Lambda (infra-cdk/lib/generate-stack.ts), us-east-1, IAM scoped to
  exactly THREE models: nova-pro-v1:0 + 2 Stability models. It has NO grant for the us-west-2 imported model.
- /generate returns 200 live. /localize returns 403 at the deployed edge (route EXISTS in api.py:132 +
  localize_service.py + localize_memory.py with 219 precomputed variants) — the edge config rejects it, so
  live translated TEXT does not render yet; the frontend already degrades honestly to EN-source.
- DAM bucket chasko-creative-dam-946179428633-us-east-1 is FULLY PRIVATE (all public-access blocks true,
  no CloudFront OAC). Contents under brands/kodiak/: zac-efron/ (5), renders/ (496 past campaigns),
  heroes/ (5), logos/ (2), raw-ingest/kodiakcakes/images/ (1000+ product boxes), tokens/, vectors/.
- The two pages are hand-authored VANILLA JS, one HTML file each (index.html = the app; details.html =
  design-system reference), served from CloudFront. NOT React — ignore React-specific advice, translate to
  vanilla JS. Localization is already a first-class rendered feature (per-market top_languages[] drive
  #marketLangLine / #featuredFrontier / #locPreview / tile captions; live /localize wired with honest
  offline degrade; community-review languages nv/zip never machine-translated).

SIX TRACKS (sequence roughly top-to-bottom; tracks 5-6 can run parallel to 1-4):

1. ART DIRECTOR wire + gate (dispatch: poltergeist-myrren-nova-inference architecture -> ghost-orin for the
   CDK IAM edit + ghost-ellow/python for the generate handler). Add a 4th bedrock:InvokeModel IAM statement
   to the generate Lambda role for the us-west-2 imported-model ARN. Insert the art-director VOICE step
   BEFORE hero composition (its output becomes the on-image message / feeds the nova-pro scene prompt). Ship
   DARK behind an env flag (KODIAK_ARTDIRECTOR_ENABLED=false default) — no feature-flag system exists, use
   an env-var gate on the generate Lambda. Preserve the isolated-region env pattern (never fall back to
   AWS_REGION). BLOCKING DECISION FOR BRYAN: is "the new Art Director model" the live cx15b77k5nge, a
   re-import (env-var swap + re-import job), or a DIFFERENT-MODALITY model (scene/imagery — that is a genuine
   new module, do NOT overload voice-only art_director.py)? Everything downstream forks here.

2. USER-ASSET INGEST + EMBED + DEDUP (dispatch: ghost-orin route + python; myrren for the embed/dedup shape).
   Route asset_api.py /library/assets into api.py; wire the front-page "+" upload (currently stages
   client-side only via window.__userAssets, threads only NAMES) to actually POST /library/assets and get
   back an asset_id. Pipeline: SYNC upload returns 201 fast (classify + sha256 exact-dedup + S3 put +
   sidecar); ASYNC worker does perceptual-hash near-dup check -> Nova 2 multimodal embed (1024d) ->
   write vector -> extract metadata -> status. DEDUP FIRST, before spending a Nova invoke. Idempotent on
   asset_id (S3 events can double-fire). Never lose an upload because embedding failed (status=embed_pending,
   retry). BLOCKING DECISIONS FOR BRYAN: vector store target (S3 Vectors [new bucket, queryable, low cost,
   code already anticipates it] vs append-only JSONL [does not scale for similarity-dedup] vs OpenSearch/
   pgvector [scales, more cost/ops]); dedup depth (exact-only vs +perceptual vs +embedding-similarity) and
   the thresholds (pHash Hamming cutoff, cosine cutoff); async trigger (S3 ObjectCreated->Lambda vs
   SQS-from-API); whether a DynamoDB dedup index lands this sprint (the O(list) sidecar scan is a scaling
   cliff); whether a second Nova call for labels/caption is in scope or the vector alone IS the
   "understanding."

3. DAM ASSET BROWSER — the "/assets route" path Bryan chose (live, uses the backend's existing S3 creds).
   Add a backend route that lists brands/kodiak/{zac-efron,renders,heroes,logos} and returns presigned GET
   URLs; the front-page "+" gains a "Browse past assets" tab that reads it and stages a chosen asset into
   the tray like a local upload. EXCLUDE the 1000+ raw-ingest boxes from the human picker (pipeline seed
   data, not campaign-building assets). This also incidentally fixes the heroes/*/hero.png references since
   real heroes become reachable. (dispatch: poltergeist-stratia-aws-infra + ghost-orin for the route,
   ghost-ellow for the browser UI.)

4. /localize 403 EDGE FIX (dispatch: poltergeist-stratia-aws-infra). The route exists; the deployed
   CloudFront/API-Gateway edge returns 403. Diagnose the edge config (behavior/method/auth) so POST /localize
   reaches the backend the way POST /generate does. When fixed, the already-built localization frontend
   renders real ES/PT/etc text instead of EN-source degrade. Verify with a live curl POST /localize expecting
   200 + translated text.

5. BROWSER PERFORMANCE + RESILIENCE, both pages, VANILLA JS (dispatch: ghost-liora + ghost-ellow):
   - Page Lifecycle API: on visibilitychange==='hidden' + the freeze event, persist in-flight state to
     localStorage (assembled #campaignBrief incl the two-way selection suffix, selected market/season/
     products). Rehydrate on cold-boot when Chrome Memory Saver discarded the tab. GOTCHA: blob: object URLs
     for staged uploads do NOT survive a discard — persist a re-derivation note / re-prompt, do not assume
     the blob is restorable.
   - DOM slimming: content-visibility:auto (native CSS, no library) for the 73-market listbox, autocomplete
     results, localized rows, render-set/preview tiles.
   - Leak audit checklist: the generate elapsed setInterval tick (always cleared in finally?), per-tile
     Image() onload/onerror handlers when render() clears #preview innerHTML, URL.revokeObjectURL on removed
     staged assets, window/document listeners + the ?debug=layout overlay's resize/scroll listeners. The page
     is never "unmounted" but re-renders regions repeatedly — that is the leak surface.
   - Measure before/after with DevTools Performance Monitor (DOM nodes, listeners, JS heap) + heap snapshots.

6. REGEX-AWARENESS + ERROR/EXCEPTION HANDLING (dispatch: ghost-ellow):
   - Recognize typed patterns in the prompt/inputs: a ZIP -> resolve to market, a product-ish token -> SKU
     suggestion (autocomplete already does product/market matching — extend it), a URL, an @mention. Recognize
     uploaded file types (image/*, pdf, docx, yaml/json briefs) and route/validate accordingly.
   - Defensive try/catch + USER-FACING error states (not silent console spew) around: the upload path, the
     autocomplete, the generate fetch (already has timeout+degrade — audit for coverage), and every JSON.parse
     of fetched data (market-languages, platform-matrix, catalog, localize response).

CROSS-CUTTING (state in the plan, enforce in review):
- COST IS A REAL AWS BILL on bryanchasko-kiro. kiro-tier-unlimited (a haunting rule) does NOT cover Bedrock
  invoke, provisioned throughput, S3 Vectors, or SageMaker. Price provisioned-throughput (art director latency
  mitigation) and per-upload Nova invoke (ingest) as real line items before committing.
- REGION SPLIT is load-bearing: art-director model us-west-2, generate Lambda + embeddings us-east-1. Preserve
  the isolated-region env pattern; any cross-region invoke needs the explicit IAM grant.
- VERSION + DEPLOY DISCIPLINE: scripts/bump-version.sh stamps 8 version tokens across index.html/webmcp.json/
  llms.txt; deploy-frontier.sh refuses on drift and syncs assets/ data/ fonts/ design/ + invalidates /*.
- NOVA-ACT / browser verification: the headless verifier's browser transport was flaky last sprint (nova-mcp
  unbound); if live rendered verification is needed, confirm the browser tool is bound at session start or
  fall back to source-level + curl verification and say so.

FIRST MOVES for the anchor: (1) get Bryan's answers to the track-1 model-identity decision and the track-2
vector-store/dedup decisions — those gate the two biggest tracks; (2) while waiting, land tracks 4 (/localize
403), 5 (browser perf), and 6 (regex/error handling) which have no blocking decisions; (3) cut the branch,
dispatch by the domain map above, bump+deploy+PR per track, hold the merge for Bryan.
