# Training the Reference Library — Nova Multimodal Embeddings, Background Agents, and Agent-Friendly Search

> Marketing teams write one line. Behind it, a lot of context is turned into numbers so the next "Las Cruces green chile flapjacks" suggestion already knows what worked in Las Cruces last time. This page explains how we build that memory — with real code you can copy — using only Amazon models and current standards checked via Context7 and the AWS Managed Control Plane.

Current models (checked 2025-09-02 via `aws bedrock list-foundation-models --by-output-modality EMBEDDING` in `us-east-1`): **`amazon.nova-2-multimodal-embeddings-v1:0`** for everything (text, image, or text+image together), fallback **`amazon.titan-embed-text-v2:0`** for text-only when multimodal is not enabled. Dimensions **`1024`** (also available 3072 / 384 / 256 — blog: https://aws.amazon.com/blogs/aws/amazon-nova-multimodal-embeddings-now-available-in-amazon-bedrock/). That blog plus S3 Vectors doc are the two sources that shape this page.

## What gets learned — the three piles that become one index

We don't learn from scratch. The foundation is the full Kodiak dump you demanded — 736 pack shots + 77 pages from `sitemap_products_1.xml` etc. mirrored to `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/raw-ingest/kodiakcakes/` (815 objects). On top of that:

1. **Design pile** — `design/tokens/kodiak.json` (Bear Brown #3B2316, Blaze Orange #E8530E, Frontier Green #1A3C34, slab 56/64/72, Keep It Wild voice), plus `references/keep-it-wild/` and `references/brand-inventory.json` (Amazon store 19CF7868-DF80-4939-932A, kodiakcakes.com collections, Brandfetch colors #B51E14 Thunderbird etc.)
2. **Reference pile** — `data/raw-ingest/kodiakcakes/images/` real pack shots (Buttermilk Power Cakes Front, Kodiak Cups, granola, frozen), Instagram 20 samples at `instagram.json`, TikTok samples, Forbes + Graphic Packaging case study PDF at `brand-lore/`
3. **Training pile** — `data/localization/localization-training-data.jsonl` — 18 seeded regions from `docs/regional-cultural-database.md` plus every campaign that runs (green chile Las Cruces is the exemplar, but also Publix porch, Target fuel your frontier, on-the-go busy mornings). Each row is `Place: … Market: US-SW-LASCRUCES Audience: Green chile families Message: Green chile meets grizzly Photo cue: Roasted Hatch …` — that is the growing training row the next suggestion pulls.

All three piles are turned into the same shape: a 1024-number vector. Text alone, image alone, or text and image together — one model, one index. That is why "green chile families" finds a prior Las Cruces win by meaning, not by spelling.

## How Nova multimodal embeddings work — current standards

- **Unified single model.** Nova 2 multimodal embeddings understands text, images, and documents through one model (blog, 2025). You send text, or an image as base64, or both interleaved, and you get back one vector. That vector lives with its metadata (which format it was, which collection, which market) in S3 Vectors — Amazon's managed vector bucket (not a regular S3 bucket, not OpenSearch Serverless unless you choose it). Blog: *S3 Vectors provides a simple way to store and query embeddings; when adding an embedding use metadata to specify the original format and the content being indexed.*
- **Four sizes, we keep 1024.** Nova 2 offers 3072 / 1024 / 384 / 256 dims. The blog and the Knowledge Bases doc (`amazon.nova-2-multimodal-embeddings-v1:0` with S3 Vectors, example uses 1024) both call out 1024 as the practical balance — larger grabs more nuance, smaller saves storage and speed. For S3 Vectors we create the index at 1024, cosine distance, float32. Knowledge Bases can also auto-create it.
- **API is bedrock-runtime InvokeModel, not Converse.** Embeddings are data plane, not chat. Many shells confuse the two and get `Malformed input`. For Nova multimodal the body is `taskType: SINGLE_EMBEDDING` with `singleEmbeddingParams: {embeddingDimension: 1024, text: {truncationMode: END, value: ...}}` or with `images: [{format: png, source: {bytes: base64}}]` and optional text alongside for interleaved. Titan Embed is the text fallback — body `{inputText: string, dimensions: 1024, normalize: true}` — used only when Nova 2 is not enabled in the region.
- **No third-party models, ever.** Embedding check is `aws bedrock list-foundation-models --by-output-modality EMBEDDING --region us-east-1` shows `amazon.nova-2-multimodal-embeddings-v1:0` and `amazon.titan-embed-text-v2:0` among a few others — we allow only those two per the Model Selection Guide. Inference profile is not needed for embeddings (on-demand is fine), unlike chat models where you would use `us.` prefix.
- **Docs we always check.** Context7 MCP for Bedrock standards + AWS Managed Control Plane read-only for quotas/model access. Those are cited in every change so the standards don't drift.

## Background agents — how the reference library stays fresh without blocking marketing

Three small agents walk the library in the background (cron or AgentCore scheduled, not in Maya's way). Each is the same Python entry point with a different slice:

```bash
# Design tokens + Keep It Wild voice — usually 10 to 15 items
uv run python scripts/embed-reference-library.py --design --out data/vectors

# Real pack shots as images — start small, then expand
uv run python scripts/embed-reference-library.py --images --limit 20 --out data/vectors

# The growing training memory — 18 seeded plus every campaign that ran, the piece you said to store
uv run python scripts/embed-reference-library.py --training --out data/vectors

# All three at once — what AgentCore will run on a schedule (mock when no creds, real with AWS_PROFILE=bryanchasko-kiro)
uv run python scripts/embed-reference-library.py --all --out data/vectors
# short alias used by CI
AWS_PROFILE=bryanchasko-kiro uv run python scripts/embed-reference-library.py --all
```

What each does under the hood is the same: `src/creative_automation/embeddings.py` calls `bedrock-runtime.invoke_model(modelId=amazon.nova-2-multimodal-embeddings-v1:0, ...)` with `embeddingDimension: 1024`, normalizes to unit length, and appends one line to `data/vectors/kodiak-embeddings.jsonl` with `{id, type, source, dim: 1024, model: actual-model-used, vector: [1024 floats]}` plus `data/vectors/manifest.json` with the model and count. When `AWS_PROFILE` and credentials are missing, the same code returns a deterministic hash-seeded mock vector (same shape, same file) so marketing can see the flow without AWS — `mock:titan-nova` in the manifest tells you it was a rehearsal.

**AgentCore mapping you asked for:** these three become long-running AgentCore Runtime tasks with S3 as the event source (new image lands in `raw-ingest/`, changed token, new `localization-training-data.jsonl` line). Gateway exposes the photo library and retail network as tools; Memory remembers that Diego's Las Cruces green chile win came back high.

## What lands in S3 Vectors / Knowledge Bases — the single searchable index

The JSONL is the bulk input. On S3 the path is `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/vectors/kodiak-embeddings.jsonl` after `aws s3 sync data/vectors/ s3://.../brands/kodiak/vectors/`. Two ways to make it queryable:

- **Simplest — Bedrock Knowledge Base with S3 Vectors** (no servers): create a vector bucket (`vectorBucketArn`, not a regular bucket — see `https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_S3VectorsConfiguration.html`), create an index at 1024 dims cosine, create a knowledge base pointing at `s3://.../brands/kodiak/vectors/` as data source with embedding model `amazon.nova-2-multimodal-embeddings-v1:0`, start ingestion job, then `aws bedrock-agent-runtime retrieve --knowledge-base-id $KB --retrieval-query '{"text": "What worked for green chile families?"}'` or `retrieve-and-generate` with `modelArn: arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-micro-v1:0`. Per the skill file we always check S3 Vectors docs + `knowledge-bases-setup.md` before choosing chunking (semantic, advanced parsing for PDFs with tables like the Graphic Packaging case study).
- **Direct — S3 Vectors without Knowledge Bases** (for custom post-processing): `s3vectors:PutVectors`, `s3vectors:QueryVectors` against `arn:aws:s3vectors:us-east-1:946179428633:bucket/kodiak-vectors/index/kodiak-embeddings` — useful when you want raw chunks before feeding a different model.

The manifest records the exact model and dim so a mismatched index (for example S3 Vectors still at Titan 1536) fails fast instead of silently.

## Agent-friendly ways to ask the memory — code samples that actually run

Marketing never writes JSON. An assistant does. Three shapes all answer `What worked for green chile families?` by meaning:

### 1. Same search from the shell (uses Nova when creds exist, mock otherwise — same file shape)

```python
from creative_automation.reference_api import search
hits = search("What worked for green chile families?", k=3)
for h in hits:
    print(h["id"], round(h["score"], 3), h["source"][:120])
# -> training:US-SW-LASCRUCES 0.912 Place: Las Cruces + Alamogordo, New Mexico Market: US-SW-LASCRUCES ...
```

### 2. HTTP from Maya's browser or Diego's phone (FastAPI)

```bash
# local — no creds needed for the server itself (vectors may be mock until you run embed)
uv run python -m creative_automation.reference_api &
curl "http://127.0.0.1:8182/search?q=green%20chile%20families&k=3" | jq .
# -> {query: "green chile families", k:3, hits: [{id: "training:US-SW-LASCRUCES", type: "text", source: "Place: Las Cruces ... Green chile meets grizzly ...", score: 0.912}], model: "amazon.nova-2-multimodal-embeddings-v1:0 (or mock fallback)"}

curl -X POST http://127.0.0.1:8182/embed -H 'Content-Type: application/json' \
  -d '{"text":"Fuel your frontier with 14g protein","image_path":"data/raw-ingest/kodiakcakes/images/705599011627_FlapjackMix_Buttermilk_Front_1.png"}' | jq .model

# S3 Vectors direct (when bucket exists, dedidated vector bucket) — see AWS doc for exact storage config
# aws s3vectors query-vectors --vector-bucket-arn arn:aws:s3vectors:us-east-1:946179428633:bucket/kodiak-vectors --index-name kodiak-embeddings --query-vector '{"float32": [...1024...]}' --top-k 5
```

### 3. From any agent via MCP (no HTTP at all)

`$HOME/.agents/mcp-kodiak-reference.json` exposes `kodiak_reference_search` and `kodiak_reference_embed` as local MCP tools. In Muse or Kiro the agent simply calls:

```json
{ "tool": "kodiak_reference_search", "arguments": { "q": "What worked for green chile families?", "k": 3 } }
{ "tool": "kodiak_reference_embed", "arguments": { "text": "Green chile flapjacks in Las Cruces", "image_path": "data/raw-ingest/kodiakcakes/images/705599011627_FlapjackMix_Buttermilk_Front_1.png" } }
```

That MCP server is the same Python code — `reference_api.py` — wrapped as a tool. No third-party model, no second index.

## How this feeds the campaign the next time

Next time Maya picks `target_market: US-SW-LASCRUCES`, the pipeline that used to just paste the headline now does:

```python
# inside src/creative_automation/pipeline.py before compose (future wire, mock today)
from creative_automation.reference_api import search
ctx = search("Las Cruces green chile flapjacks", k=3)
suggested_message = ctx[0]["source"]  # "Green chile meets grizzly — ..."
suggested_cue = ctx[0]["metadata"]["cue"] if "metadata" in ctx[0] else "Roasted Hatch ..."
# then Nova Micro rewrites it with the pack, Nova Canvas picks the photo cue
```

Today that wire is described here; the library it reads is already built by `scripts/embed-reference-library.py`. The ton of context the earlier architecture diagram showed going into Nova — winning message for this market, audience words that worked there, photo cue, brand rules, ingredient truth, store set — is exactly the context those three background agents embedded.

## Running it end to end — copy these

```bash
# 1. Check models and creds are ready (Context7 + AWS MCP say check first)
aws --version
AWS_PROFILE=bryanchasko-kiro aws bedrock list-foundation-models --by-output-modality EMBEDDING --region us-east-1 --query "modelSummaries[].modelId"
aws sso login --profile bryanchasko-kiro --use-device-code   # headless host needs --use-device-code

# 2. Build the three piles into one index (local — mock if no creds, real Nova 2 multimodal when creds exist)
uv run python scripts/embed-reference-library.py --all --out data/vectors  # 18 localizations + design + 20 images → manifest + kodiak-embeddings.jsonl

# 3. Search the memory like marketing will — three ways, same hit
uv run python -c "from creative_automation.reference_api import search; print(search('green chile families', k=2)[0]['id'])"
curl "http://127.0.0.1:8182/search?q=porch%20breakfast&k=3"  # after uv run python -m creative_automation.reference_api
# via MCP in Muse: call kodiak_reference_search with q "What worked for green chile families?"

# 4. Push the index where the knowledge base reads it (regular S3 for the source — vector bucket is created by Bedrock)
aws s3 sync data/vectors/ s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/vectors/ --region us-east-1 --profile bryanchasko-kiro

# 5. Verify (no hallucinating success)
cat data/vectors/manifest.json | jq .model,.dim,.count
cat data/vectors/kodiak-embeddings.jsonl | wc -l
uv run python -m creative_automation.reference_api --help 2>&1 | head
```

Costs: Nova 2 multimodal is on-demand per 1K tokens/pixels (see pricing), Titan fallback is cheaper for text-only; batch via `embed_batch` with 20 images then 50 then all scales linearly. Throttle guard: skill says always set `maxTokens` explicitly and use adaptive retry `Config(retries={max_attempts: 5, mode: adaptive})` — embeddings benefit similarly; we batch at 20.

Standards checked via Context7 and the AWS Managed Control Plane docs at `~/.agents/skills/amazon-bedrock/references/` and the blog you linked before each change. When the next Muse model drifts the body shape, the check that must run is `aws bedrock list-foundation-models` and the blog URL you sent — not our memory.
