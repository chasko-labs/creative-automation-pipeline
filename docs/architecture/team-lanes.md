# team lanes — creative-automation-pipeline

> three teams work this repo in parallel on the rocm-aibox environment. this doc is the ownership map: who owns which paths, where the seams are, and how a change in one lane reaches another without a collision. read your lane, respect the seams.

## the three teams

| team                    | slug          | owns                                                                                       | drives                                                |
| ----------------------- | ------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------------- |
| pipeline + agentic core | team-pipeline | the engine: training data, bedrock agentcore, python + rust tooling that runs the pipeline | how one brief becomes hundreds of on-brand assets     |
| app frontend            | team-frontend | the surface: web ui, css, the sample-prompt browser, preview rendering, glimmer canvas     | how a marketer picks a prompt and sees a result       |
| infra + data-platform   | team-platform | the ground: aws infra, codebuild ci, s3 dam, s3 vectors index, dns/cloudfront, secrets     | how the whole thing deploys and stays cheap + healthy |

the third team (infra + data-platform) is the one easy to forget — it is the connective tissue that both other teams stand on. without a codebuild project, a vector index, and the dam bucket, the pipeline has nowhere to write and the frontend has nothing to read.

## lane boundaries by path

each path prefix has exactly one owning team. edits outside your lane go through a dispatch to the owning team's coder, not a direct write.

| path                                                                                      | owner                     | notes                                                                                                                                |
| ----------------------------------------------------------------------------------------- | ------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `src/creative_automation/*.py` (engine core)                                              | team-pipeline             | pipeline, compose, enhance, generate, embeddings, dam, spin, retailers, naming, scorecards, compliance, localize, translate, suggest |
| `src/creative_automation/ingest/`                                                         | team-pipeline             | tiktok / youtube / social ingest                                                                                                     |
| `src/creative_automation/api.py`, `reference_api.py`                                      | team-pipeline             | fastapi surface — but the response CONTRACT is shared with team-frontend (see seams)                                                 |
| `rust/kodiak-local/`                                                                      | team-pipeline             | pyo3 accelerator crate                                                                                                               |
| `scripts/embed-*.py`, `scripts/ingest-*.py`, `scripts/*_ingest.py`                        | team-pipeline             | corpus + ingest runners                                                                                                              |
| `data/vectors/`, `data/prompts/`, `data/products/`, `data/recipes/`                       | team-pipeline             | generated training data + sample-prompt library                                                                                      |
| `docs/bedrock-agentcore-architecture.md`, `docs/training-process.md`, `docs/agentcore.md` | team-pipeline             | agentic core design                                                                                                                  |
| `web/kodiak-posts-for-todays-frontier/`                                                   | team-frontend             | index.html, css, glimmer-proxy.js, the ui                                                                                            |
| `src/creative_automation/templates/`                                                      | team-frontend             | jinja/mjml render templates (newsletter etc)                                                                                         |
| `design/tokens/kodiak.json`                                                               | team-frontend             | design tokens — but pipeline READS these (see seams)                                                                                 |
| `docs/kodiak-brand-*.md`, `docs/ux-persona*.md`, `docs/visual-gallery.md`                 | team-frontend             | brand + ux presentation docs                                                                                                         |
| `infra/` (template.yaml, s3-dam.tf, tfstate)                                              | team-platform             | all infrastructure-as-code                                                                                                           |
| `buildspec.yml`, any codebuild config                                                     | team-platform             | ci gate                                                                                                                              |
| `scripts/sync-dam.sh`, `scripts/seed-kodiak-s3.sh`, `scripts/diagnose.sh`                 | team-platform             | dam + ops scripts                                                                                                                    |
| `docs/dam-runbook.md`, `docs/nova-act-runbook.md`                                         | team-platform             | ops runbooks                                                                                                                         |
| `briefs/*.yaml`                                                                           | shared (any team)         | campaign briefs are content, not code — small, low-collision                                                                         |
| `CONTRIBUTING.md`, `docs/architecture/`                                                   | team-pipeline (as anchor) | governance docs; edits announced to all teams                                                                                        |
| `pyproject.toml`, `uv.lock`, `Cargo.toml`                                                 | team-pipeline, coordinate | dependency changes touch everyone — see seams                                                                                        |

## the seams — where lanes touch

a seam is a shared contract between two lanes. changing one side without the other is how you break the other team. every seam has an owner of the CONTRACT (who defines the shape) and consumers.

| seam                                                            | contract owner | consumers                                                                              | the rule                                                                                                                                                         |
| --------------------------------------------------------------- | -------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| design tokens `design/tokens/kodiak.json`                       | team-frontend  | team-pipeline (compose/enhance read colors, dims, type scale via token_loader)         | frontend owns the values; pipeline reads by key never hardcodes. adding a token is safe; renaming/removing a key is a breaking change — announce it              |
| api response shape (`api.py`, `reference_api.py`)               | team-pipeline  | team-frontend (ui fetches search results, prompts, previews)                           | pipeline owns the json shape; changing a field name or removing a field breaks the ui. version the endpoint or announce the field change                         |
| sample-prompt library `data/prompts/blog-sample-prompts.jsonl`  | team-pipeline  | team-frontend (ui renders the prompt browser from it)                                  | pipeline owns the schema (id, prompt, source_url, hero_image, product, recipe, tags, section, in_image_text). frontend reads it. schema changes are a seam event |
| iso naming `src/creative_automation/naming.py` (ISO_NAME_RE)    | team-pipeline  | scorecards, dam paths, s3 keys (team-platform)                                         | single source of truth. the writer and every checker import the same regex. never define a second pattern                                                        |
| dam bucket layout `s3://chasko-creative-dam-.../brands/kodiak/` | team-platform  | team-pipeline (writes renders + vectors), team-frontend (reads assets over cloudfront) | platform owns the bucket + prefixes; pipeline writes under agreed prefixes; frontend reads via cloudfront. changing a prefix is a seam event                     |
| s3 vectors index (herald-vectors-nova, 1024-dim)                | team-platform  | team-pipeline (PutVectors + query)                                                     | platform provisions the index + dim; pipeline must match EMBED_DIM. a dim mismatch fails ingest silently — coordinate the number                                 |
| dependency manifests `pyproject.toml` / `Cargo.toml`            | team-pipeline  | all teams (shared venv on rocm-aibox)                                                  | one lockfile, one venv. adding a dep is a coordinated change — announce before `uv add` so the other teams re-sync                                               |

## what "match before jazz" means for lanes

the product order is: reproduce Kodiak's existing look first, then add local variation. that maps to lanes:

- team-pipeline builds the training data + spin tooling that make a generated asset look like a real Kodiak post (the match)
- team-frontend surfaces the sample prompts + previews so a human can steer toward or away from the match
- team-platform makes the match repeatable and cheap at scale

no team ships "jazz" (novel creative variation) before the match is proven by the scorecards gate.

## the rule in one sentence

each path has one owning team, each shared contract is a named seam with a contract owner, and a change that crosses a lane is a dispatch to the owning team plus a seam announcement — never a quiet direct write
