# Kodiak creative-automation walkthrough — speaker notes (~24 min, 15 slides)

Cheat sheet: one brief fans out to hundreds of local ads; brand floor is
deterministic; offline reviewer box is fail-closed. Punchlines: (1) model
draws pixels, never logo or type; (2) restyle cache stops paying twice;
(3) graceful degradation, never silent invention. If asked what is next:
backlog inventory, 39 open, every item numbered.

## Slide 1 — One brief in, hundreds of local ads out (contract)

Open with the 30-second contract: what it is (one brief fans out to
every market, ratio, and language), who it is for (the brand manager, the field ambassador, the performance lead),
what good looks like (launch-ready in 10 minutes; the pipeline never
invents brand truth, it stages it). Definitions: a campaign is one brief
plus products plus markets; launch-ready means composed,
compliance-passed, packed per persona. Provenance: weekly loop in `docs/ux-persona-kodiak.md:59-63`,
brief contract in `briefs/kodiak.yaml:2-12` (brand KODIAK, Keep-It-Wild
campaign, three 14g-protein products). Talk it through: the brand manager writes the
Park City brief Monday morning; by mid-morning the field ambassador has a
vertical story with their town in it and the performance lead has one
report row per region. Friday the win becomes
a training-data row the next run suggests first. Transition: but what does
the reviewer actually touch? Run: open the live page resting state.

## Slide 2 — What the app does: brief to preview (live flow)

Say: four steps, no build, no login. Definitions: brief is the YAML intent;
generate is the Amazon Bedrock hero ladder (the hero photo is the
model-drawn backdrop image); preview is the composed ratios plus report. Provenance: courtesy gate `kodiak_gate=cakes` in
`web/kodiak-posts-for-todays-frontier/index.html:27-28` (comment says NOT
security), resting showcase at `index.html:431-469` (five ratios, baked
EN/ES/PT copy), 8 islands and flow string in `webmcp.json:59`. Talk it
through: load the page, dismiss the gate once per tab, pick products, hit
generate, read the preview. Note the resting state renders with zero
network — baked art index, relative JSON, no fetch on load. Fallback per
demo: if generate dies, the resting render still proves offline-first;
the reviewer ZIP is the dead-venue equivalent covered later in the talk. Serve it with
the static server on `:8099`; dev API lives at `127.0.0.1:8182/docs`.
Transition: who is each pixel for? Run: show the Park City default market.

## Slide 3 — Built for three roles (persona tour)

Say: one zip, three doors. Definitions: a pack is the persona's slice
(ratios plus copy plus rollup); the win bar is idea sheet to launch-ready
in 10 minutes. Provenance: `docs/ux-persona-kodiak.md:5-56`, pack mapping
in `src/creative_automation/persona_pack.py:73-103` (brand manager all
ratios plus `platform-copy.json` at `:84-89`; field ambassador 9x16 at
`:90-96`; performance lead 1x1 plus `manifest.rollup` at `:97-114`).
Talk it through: the brand manager gets three finished ads with bear
corner, orange bar, legible band, green badges; the field ambassador gets
a post that feels like Park City with town name and map button; the
performance lead gets one master post with per-viewer town plus one
budget per city group. Behind
the three stands a 23-card roster across 5 hubs plus a technical hub.
Transition: what feeds all three? Run: open `market-languages.json`.

## Slide 4 — Seeded data: 82 markets, 503 recipes (data grain)

Say plainly: markets drive everything. Definitions: market grain is the
7-field code; top-2 non-English per market comes with ACS percentages.
Provenance: `data/localization/market-languages.json:2-18`
(`total_markets: 82` at `:5`); Park City `US-MW-PARKCITY-84098` es 5.8 /
pt 1.2; seed row `data/localization/park-city/park-city-84098.json`;
recipes in `data/recipes/kodiak-recipes.json` (503 entries counted live);
localization memory seeds plus 22-row training JSONL; deterministic seeds
in `data/seeding/matrix-oh-oc.json`. Talk it through: Park City is both
the tastes-like-home demo and the localization proof — trailhead
flapjacks copy plus a Wasatch alpenglow photo cue, both seeded in
`data/localization/park-city/park-city-84098.json`. Caveat on stage:
persona docs say 23 baselines but the file holds 503 — reframe as 23 hero
originals plus hundreds of localized drafts. Transition:
data is honest, so pixels must be too. Run: open
`design/tokens/kodiak.json`.

## Slide 5 — Brand fidelity: tokens to pixels (bear stays bear)

Say: three links, no shortcuts. Definitions: tokens are the JSON source of
truth; compose is deterministic Pillow assembly; compliance is the
pass-or-fail vote. Provenance: `design/tokens/kodiak.json:8-40` (Bear
Brown `#3B2316`, Blaze Orange `#E8530E`, Frontier Green `#1A3C34`; canvas
sizes at `:824-837`; pad 48px, bar 68%, logo 24px, accent 8px at
`:666-685`); overlay spec in `src/creative_automation/compose.py:338-366`
(scrim bottom 32%, headline, bear top-left, blaze bar); gates in
`src/creative_automation/compliance.py:39-74` (palette probe, logo check,
combined verdict); voice in `src/creative_automation/brand_copy.py:30-60`;
footer stamp `KODIAK(R) - kodiakcakes.com - Keep It Wild` per
`persona_pack.py:156`. Talk it through: S3-first token load with local
fallback (`token_loader.py:9-52`); the model supplies hero pixels ONLY.
Efron beat (gh#251, Sep 4-8): ingested `partner-libraries.json` with a
licensed-only digital asset library (DAM, the private art bucket) photo
policy, two approved shoot keys, and two
shot-list gaps; the refusal had two faces, a silent generic stack while
the receipt claimed the theme, and a hard filter trip on raw real-person
names (`scene_prompts.py:85-95`, `generate_lambda.py:2433`); removal
landed Sep 8 (`3505de8`, 16 files, +177/-553) after 4-5 days of
build-then-remove plus hardening passes (`02ada6b`, `0d79c5d`); no
per-theme dollar ledger exists, so no dollar figure is claimed. What
survived as law: no named-person themes, the retired-name scrub,
match-or-abstain (use the approved photo or use none) with the
theme-mismatch flag, bear law, and the
mascot-lock identity pattern. Transition: where does this chain run?
Run: open `pipeline.py:64`.

## Slide 6 — Seven stages, always returns a finished tile (pipeline)

Say: brief to report in seven hops. Definitions: hero is the model-drawn
backdrop; ladder A-D is restyle, Amazon Nova art-direction, Pillow image
library compose, deterministic floor; rung D is a guaranteed fallback
tile, so generate always returns a finished tile and never fails open
with an error.
Provenance: `src/creative_automation/pipeline.py:64-310` (localize per
language at `:30-61` via market-languages, safety redact at `:169-178`,
outputs report.json plus jsonl plus preview.html); ladder and
run-to-completion in `src/creative_automation/generate.py:1-118`;
localize chain (Nova Micro, Translate, offline dict, tagged fallback) in
`src/creative_automation/localize.py:65-133`; recipe two-layer card in
`src/creative_automation/recipe_card.py:1-64`. Talk it through: each
language times each ratio through compose and checks; auto-translations
attach best-effort. Nova Canvas is legacy-flagged; the proof run stays open (#51).
Transition: what metal does it run on? Run: open `infra-cdk/config.ts`.

## Slide 7 — Infrastructure map (DAM, Lambda, hosting, data)

Say: read left to right. Definitions: DAM is the Digital Asset
Management private art bucket; adopt-in-place means prod hosting was
imported, not rebuilt. Provenance:
`infra-cdk/config.ts` (DAM bucket, vectors index, tables, prod plus dev
sites); `infra-cdk/generate-stack.ts` (container Lambda from ECR,
300s/3008MB, public Function URL, X-Ray; IAM for Nova, Stability,
Translate, DynamoDB, self-invoke); `infra-cdk/hosting-stack.ts:32-40,137-165`
(API behaviors to ApiGw origin); `infra-cdk/data-stack.ts` (log bucket,
2 tables, DAM lifecycle to DEEP_ARCHIVE, TLS-only). Talk it through:
static site, behavior fan-out, container Lambda, DAM plus tables plus
vectors. Pre-warm was removed after the 2026-09-23 ~$38/day
imported-model incident — the lower of two unreconciled repo figures
(range $38-82/day) — (`generate-stack.ts:343-348`). Transition: how do
the surfaces meet? Run: `curl` the dev `/docs`.

## Slide 8 — Integration points (one impl, every surface)

Say: callable or not shippable. Definitions: Living Swagger is the FastAPI
dev server with browseable docs; the ONE impl rule means Lambda and API
share `asset_browser.list_library` (the one shared function both surfaces
call); AgentCore C2 is command-and-control, 6 thin tools over finished
units; Scar is the cut-after-rot incident note. Provenance:
`src/creative_automation/api.py:80-647` (`/pipeline/run`, `/search`,
`/localize`, `/assets/pack`, `/assets/upload` jpeg/png <=15MB,
`/campaigns/run-fanned`); `generate_lambda.py:92-119,2180-2247` (PREVIEW
vs FULL, 26s wall, 280s worker); `gateway.py:53-367` (6 AgentCore C2
tools, ok/result contract). Talk it through: CloudFront behaviors proxy
`/generate`, `/localize`, `/jobs`, `/assets/pack`, `/campaigns/*` to the
ApiGw origin; dev Function URL goes direct unsigned; DAM reads only via
presigned URLs. Same JSON in CLI, API, and MCP. Scar: bespoke art
surfaces rotted and were cut — art band retired (`ed785f1`), frontier
collapsed to one screen plus a gated 3d marquee with static fallback
(`3f71087`); shared forest cap and static fallback remain. Transition: the first
hard tradeoff. Run: submit PREVIEW, watch the wall.

## Slide 9 — Decision: async jobs (sync preview, queue the real)

Say: the Gateway cap is fixed, so preview buys immediacy and jobs buy
completeness. Definitions: PREVIEW is 1 live square hero plus 4 derived
tiles; FULL is the complete set plus pack builder; 202-queue-poll is POST
`/jobs`, get an id, poll it. Provenance:
`src/creative_automation/generate_lambda.py:92-119` (26s structural wall,
ThreadPoolExecutor plus rung-D floor) and `:2180-2247` (280s worker).
Talk it through: 9x16/16x9 live outpaint only when budget passes;
otherwise derived tiles. Scar: prod fell through to the brand floor on a
cold-model serial chain past the 22s wall, so the wall went
gateway-correct 26s (`0147071`). Sync only for brand floors; everything
real goes through the queue. Never hold a sync call past the wall.
Transition: each tile costs money. Run: show a cached re-render at 0
invokes.

## Slide 10 — Decision: cost gate (every tile is a Bedrock invoke)

Say: the ~$38/day lesson (lower of two unreconciled repo figures; range
$38-82/day) is why cache is a default, not an option.
Definitions: restyle cache is content-addressed on seed plus prompt;
run-to-completion means finish the rung instead of timing out early.
Provenance: `src/creative_automation/generate.py:107-118`
(`GENERATE_RUN_TO_COMPLETION=1` default, 24s soft budget only when 0);
cache counter at `brands/kodiak/renders/restyle-cache/` code-done 9-30, live hit-rate pending (#308);
models in play (Amazon Bedrock-hosted Nova Pro, Nova Micro
pay-per-token, Stability AI image model control-structure plus outpaint
plus Core, multimodal embeddings, Titan fallback; idle Qwen import deleted 9-30 (#309); imported Llama art-director
voice-model endpoint deleted 9-23 with the code path retained and
re-import To Be Decided).
Talk it through: Nova Pro plus Stability plus Micro per live tile;
voice-flag-off and cache absorb repeats. Dollar anatomy: about $0.07 per tile (Stability restyle), about $1.18 per full 13-tile set; September warm-time $245 dwarfed about $17 of image spend; a public full-campaign gate would bill $1.18 per run times traffic. The $38/day lesson cost a full
incident day 2026-09-23 and six hardening commits (`4575cfd` cost stop,
`ac62017` voice gate, `0172e2d` hardening, `351f6c2` prewarm deleted,
`6c25386` IAM narrow, `bdfa2e3` inference profile); everything expensive
is off by default with per-request opt-in. Nova Canvas proof still open
(#51). Transition: what the static host cannot do. Run: open issue #318.

## Slide 11 — Decision: static limits (dumb host, thinking API)

Say: limits as design, not apology. Definitions: offline-first means the
resting page renders with zero network; copy-only retailer means names and
words allowed, logo mark forbidden. Provenance: offline path
(`js/campaign-art-index.js:1-2`, `js/generate.js:187-193,4`,
`js/data-core.js:48`); upload plus from-photo bridge in the #37 epic
(upload live PR#48, orchestration pending); copy law
(`localize.py:65-133`, clean_brand_copy, never bare KODIAK); retailer
marks versus copy-only in `src/creative_automation/retailers.py:28-51,64-115,168-210`
(costco/publix/target/walmart marks via asset-store PNGs, never
fabricated; kroger/heb/whole-foods/albertsons plus banners copy-only).
Talk it through: a missing translation degrades loudly with a tagged
fallback; a missing logo stays missing. Scar: idea-honesty night
(`5839df7`) — campaign copy named the brief idea while pixels went
generic, with 1 suite failure unidentified at ship; now `_brief_idea`
harvests ecology and unmatched ideas paint a B0 original (the
text-to-image original rung for no-seed briefs, never a fallback
restyle). Demo graceful degradation live, never silent invention.
Transition: hand them the box. Run: open START-HERE.html.

## Slide 12 — Reviewer package: offline, fail-closed (trust)

Say: a box that works in a dead venue. Definitions: fail-closed means a
missing video is a hard error, never warn-and-skip; auto-unlock means the
packaged `file://` copy skips the courtesy gate the hosted site keeps.
Provenance: `scripts/build-reviewer-package.sh:1-244` (archive at
`:41-44`, gate patch at `:56-78`, START-HERE at `:91-190`, video fetch at
`:197-207`, ZIP verify at `:218-233`, publish echo-only at `:241-244`);
`scripts/gen-doc-site.py:1-272` (self-contained html, link rewriter at
`:182-202`, token-derived palette at `:72-102`); send/get review page
`scripts/build_kodiak_review.py:1-223`, ledger
`preview/kodiak-review/ledger.json:1-9` (67 attempts, 22 approved, 45
rejected-retry, 44 slugs). Talk it through: launcher, rendered docs, full
source, verified MP4. Full packager run intentionally never executed here
(no DRY_RUN mode). Transition: where to read in the source. Run: open the
review ledger.

## Slide 13 — Code tour (reading order, not the tree)

Say: five files, in this order. Definitions: doc-as-code means the
contract lives in the module header. Provenance:
`src/creative_automation/pipeline.py:64-310` (stages),
`generate.py:1-118` (ladder plus cache), `compose.py:1-62,338-366`
(contract plus overlay), `retailers.py:28-51` (chooser),
`token_loader.py:9-52` plus `compliance.py:39-74` (tokens plus gates);
`briefs/kodiak.yaml:2-12` as the entry ticket. Talk it through: pipeline
first, then generate, compose, localize, retailers. The compose header
states the model-supplies-pixels-only law where nobody can miss it.
Transition: what landed this week. Run: `git log --oneline -5`.

## Slide 14 — Just shipped: v0.1.033 (cache proven in main)

Say: repeat renders stop paying twice. Definitions: restyle cache hit
means seed plus prompt already rendered; shipped means merged to main, with
the live hit-rate check still to come so the claim stays honest.
Baseline beside the win: before, every repeat render paid Bedrock again;
after, cache-hit repeats pay 0 invokes, live hit-rate pending (#308).
Provenance: version stamp in
`web/kodiak-posts-for-todays-frontier/index.html:10`
(`v0.1.033-401301d-20260930`); restyle counter #308 code-done 9-30, live rate pending; upload live
PR#48; idle Qwen import deleted 9-30 (#309);
imported Llama voice-model endpoint deleted 9-23 (code retained),
re-import To Be Decided;
Real User Monitoring (RUM) app monitor live, client snippet pending (#28).
Talk it through: name
what is live versus pending so the room trusts the board. Production-today
close: cache counter code-done in main, RUM monitor live; Canvas proof
(#51) stays open and stated, not promised. Transition: the invitation. Run: questions.

## Slide 15 — Close: try it, read it, question it

Say: one runnable command, one reading path, one question back. Definitions:
the reading path is pipeline, compose, backlog. Provenance: live site
plus `START-HERE.html`; dev `:8099` and `:8182/docs`; closer line from
`src/creative_automation/persona_pack.py:117-159` ("Keep It Wild.
Nourishment for Today's Frontier."). Talk it through: run brief to preview
tonight; read `pipeline.py:64-310`, then `compose.py:1-62`, then the
inventory. The reviewer ZIP START-HERE.html is the one-pager: live URL,
one runnable command, reading path, and the dead-venue fallback. Thank
them and take questions. Run: questions.


