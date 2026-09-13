# agentcore backlog — kodiak pipeline agentic tooling

> decomposition of docs/bedrock-agentcore-architecture.md into buildable, independently-shippable units. team-pipeline lane. amazon-first only (nova, titan, nova canvas, bedrock agentcore). the local `run_pipeline()` stays the live fallback at every step — agentcore wraps it, never replaces it.

## the north star

two campaign prompts define done (from the PO):

- SF Bay Area power-cakes campaign for bay-area retailers + a frontier no-cal subscription variant; recipe cards from september bay-area farmers-market ingredients; retailer logos as svg; no in-image text except a costco-logo-with-local-address lockup
- Atlanta Publix (Plaza Midtown, 950 W Peachtree St NW) + Sandersville frontier sister; retailer list + monthly local ingredient

the agentic tooling exists to turn ONE of those sentences into the full multi-asset, multi-platform, multi-language campaign — matching Kodiak's existing look first.

## what is already built (foundation — done this sprint)

| capability                          | where                                                             | status |
| ----------------------------------- | ----------------------------------------------------------------- | ------ |
| real nova training data             | data/vectors/kodiak-embeddings.jsonl (3144 real vectors)          | done   |
| design-standards from clustering    | docs/kodiak-image-standards.md + data/vectors/image-clusters.json | done   |
| sample-prompt library               | data/prompts/blog-sample-prompts.jsonl (635 prompts)              | done   |
| iso naming (single source of truth) | src/creative_automation/naming.py                                 | done   |
| spin toolkit (bg/crop/grade)        | src/creative_automation/spin.py                                   | done   |
| retailer svg lookup                 | src/creative_automation/retailers.py                              | done   |
| retailer-frontier pairing           | data/localization/retailer-frontier-pairs.json + locales.py       | done   |
| content-safety gate                 | src/creative_automation/safety.py                                 | done   |
| dialect knowledge bases             | data/localization/dialect/\*.jsonl                                | done   |
| reference search api                | src/creative_automation/reference_api.py                          | done   |

## the backlog — decomposed, dependency-ordered

each unit is small enough to ship as one PR under ~500 lines. `[dep: X]` = depends on unit X. no unit blocks on the frontend or platform teams except where a seam is named.

### epic A — retrieval spine (the RAG context pack)

- **A1 vector index + query** [dep: platform provisions herald-vectors-nova 1024-dim index]: load the 3144 vectors into s3 vectors; expose a `query(text|image, filters) -> top-k` over cosine. wraps the existing reference_api search. seam: platform owns the index dim, pipeline matches EMBED_DIM=1024.
- **A2 context-pack builder**: given a brief (place + audience + one line), assemble the few-hundred-word pack the architecture doc describes — winning message for the market (localization memory), nearest cluster + cohesion floor (image-clusters.json), brand rules, ingredient truth, retailer set (retailer-frontier-pairs), dialect terms for the market's top languages. pure python, reads the done artifacts. THE core primitive.
- **A3 sample-prompt retrieval**: given a subject or product, return the closest blog sample prompts (from blog-sample-prompts.jsonl) so the UI prompt-browser and the generator both draw from real Kodiak descriptions. [dep: A1]

### epic B — generation (nova text + image, spin)

- **B1 nova text rewriter**: wrap nova micro/lite Converse to rewrite a headline for a market using the A2 context pack + dialect terms; every output passes safety.check_text before returning. [dep: A2]
- **B2 nova canvas generator hardening**: the existing generate.py path — confirm real nova canvas calls, seed-locked, clean background, text-free frame per cr-1. add the cluster-cohesion check post-generate (re-embed, confirm it lands in the target food-subject cluster above floor). [dep: design-standards done]
- **B3 spin-from-real-asset**: chain spin.spin_asset (free subject -> crop -> grade) then B2's cohesion check, so a Zac Efron / food / Park City photo becomes an on-brand spun asset that stays in its subject family. [dep: B2, spin done]
- **B4 recipe-card generator**: given a market + month, pull the monthly local ingredient (locales.resolve_this_month) + a matching recipe, generate a recipe card whose TEXT layer passes safety + uses the right dialect terms, image layer stays text-free. [dep: B1, locale done]

### epic C — agentcore runtime wrap

- **C1 runtime wrap**: wrap run_pipeline() as a bedrock agentcore runtime (serverless), local pipeline stays the fallback. no behavior change, just the hosting surface. [dep: B1..B4 stable]
- **C2 gateway tools**: expose dam photo-fetch + retail/frontier lookup + retailer-svg lookup as agentcore gateway tools the agent can call. [dep: C1]
- **C3 memory**: agentcore memory so a market's winning campaign is remembered cross-session (the "Diego's Las Cruces green chile win" pattern) and written back to localization memory. [dep: C1]
- **C4 local browser evidence**: repository-owned Playwright and pixel checks open preview.html at the 3 viewports, write structured evidence, and remain explicit boutique testing. The check never invokes a hosted browser service or agent visual verification. [dep: C1]
- **C5 identity**: agentcore identity so the agent acts on behalf of Maya/Priya via identity center. [dep: C1, platform iam]

### epic D — campaign orchestration (the north-star acceptance)

- **D1 campaign fan-out**: one brief -> all products x all platforms x all market languages, each asset iso-named, safety-gated, cohesion-checked. the thing that makes the SF and Atlanta prompts work end to end. [dep: B1..B4]
- **D2 retailer lockup compositor**: the ONE sanctioned text-in-image path — place a retailer svg + local store address (costco example) as an explicit overlay op, never in the default spin. [dep: retailers done]
- **D3 north-star acceptance tests**: the SF Bay + Atlanta prompts as end-to-end tests that assert the full asset set is produced, named, safe, on-brand. [dep: D1, D2]

## suggested build order (shortest path to a working campaign)

A2 (context pack, no deps, reads done artifacts) -> B1 (text) + B4 (recipe cards) -> D1 (fan-out) -> D3 (acceptance). A1/vector-index and the C-epic agentcore wrap run in parallel once platform provisions the index; the local pipeline is the fallback so the C-epic is not on the critical path to a first working campaign.

## the rule in one sentence

build the retrieval spine (A2 context pack) first because every generation + orchestration unit consumes it; wrap in agentcore last because the local pipeline is always the working fallback
