# Existing as a Brainstorming Machine — the corpus is the product

> A vision doc grounded in files that already exist on `main`. The pipeline did not just build a fallback image bank — it mechanically laid down a gold-standard historical corpus of real Kodiak Cakes assets and text, then embedded most of it. This doc argues that corpus should be a first-class front-end mode called **Existing**: a way to query what the brand has already done, set role models, and seed new work. The retrieval spine for it is already in the code. Surfacing it is wiring, not building.

Audience: the pipeline team deciding what to ship next, and anyone who needs to see why the scrape is an asset rather than exhaust. Every count and every file path below is verified against the repo and the DAM bucket, not intent. For the system as a whole, start at [SYSTEM-OVERVIEW.md](SYSTEM-OVERVIEW.md); for the DAM write-path this loop folds back into, see [asset library + observability](asset-library-and-observability.md).

- Account: `946179428633` (bryanchasko-kiro), region `us-east-1`
- Live corpus root: `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/raw-ingest/kodiakcakes/`
- Local mirror: `data/raw-ingest/kodiakcakes/`

---

## 1. What the machine already laid down

The ingest run walked kodiakcakes.com, its retail surfaces, and its social channels, and wrote a durable, queryable base. This is a historical record of what the brand looks like when it is being itself — product on white, product in a kitchen, product in a season. Counts are verified against `data/raw-ingest/kodiakcakes/counts.json`, the on-disk directory listings, and `data/vectors/manifest.json`.

| surface        | what it is                                          | count                 | source                                                                                                                                                        |
| -------------- | --------------------------------------------------- | --------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| product images | the scrape — product, lifestyle, seasonal shots     | 2355                  | `counts.json` (`images: 2355`), `images/`                                                                                                                     |
| blog images    | editorial + recipe imagery                          | 644                   | `blog-images/`                                                                                                                                                |
| amazon images  | retail listing imagery                              | 46                    | `amazon-images/`                                                                                                                                              |
| social pulls   | per-channel deep manifests                          | 8 channels            | `insta-deep.json`, `tiktok-deep.json`, `youtube-deep.json`, `facebook-deep.json`, `pinterest-deep.json`, `x-deep.json`, `linkedin-deep.json`, `web-deep.json` |
| youtube deep   | video pull with SRT transcripts (searchable text)   | `youtube-deep/`       | `youtube-deep/*.srt` + `*.json`                                                                                                                               |
| brand lore     | ambassador guides, store copy, print guides         | `brand-lore/`         | `brand-lore/` (html + txt + pdf + manifest)                                                                                                                   |
| tailoring spec | the per-brand ingest recipe that produced the above | `tailoring-spec.json` | `tailoring-spec.json`                                                                                                                                         |
| S3 live copy   | the product image scrape mirrored to the DAM        | ~2328 objects         | `s3://.../brands/kodiak/raw-ingest/kodiakcakes/images/`                                                                                                       |

Of that base, **3146 rows are already embedded** — `data/vectors/manifest.json` reports `count: 3146`, `model: amazon.nova-2-multimodal-embeddings-v1:0`, `dim: 1024`. That number is the whole argument: the corpus is not raw material waiting for a project. It is a live index waiting for a search box.

The social manifests, the youtube SRT transcripts, and the brand-lore folder are **text**. That matters — text is directly answerable. A question like "what is Kodiak's Park City story?" has a real, sourced answer sitting in those files today, retrievable without generating a single new pixel.

---

## 2. Two lenses on why this is the creative act

### The Factory — the artist as director

Warhol's Factory reframed the artist as a production director rather than a painter. His own line — that he wanted to be a machine — was not resignation, it was method: choose the source image, fix the palette, define the procedure, and let the photo-silkscreen assembly line run off infinite on-brand variations of the same subject (paraphrased from [Sotheby's on Warhol's process](https://www.sothebys.com/en/articles/andy-warhol-and-his-process) and the [Andy Warhol Foundation](https://www.warholfoundation.org/warhol/)). The creative decisions live in source selection, palette, and procedure — not in each individual pull.

That is precisely the shape of this pipeline. The gold-standard scrape is the source library. The brand tokens and the compose step are the palette and the registration. `run_pipeline()` is the assembly line. And the off-register variation — the small drift between one pull and the next — is not a defect to sand out; in the Factory it became the signature. Here it becomes range: the same recipe card, restyled per market and per season, each one recognizably Kodiak and none identical.

### The reality engine — one light motif

Borrow one image from the Marvel shelf and set it down gently: a machine that opens doorways to any point in a history and to any alternative version of it — Reed Richards at a gate that reaches sideways into what could have been. The **Existing** mode is that gate pointed at the brand's own past. Step through to what Kodiak actually did for fall 2023, or step sideways into the variation it did not ship. The motif is framing only; the substance is retrieval plus generation.

---

## 3. The retrieval spine already exists

The single most important fact in this doc: the "query Existing" capability is not a new build. It is already in `src/creative_automation/reference_api.py` and has been since the reference library shipped.

- `GET /search?q=...&k=...&type=text|image|multimodal` — verified in `reference_api.py`, FastAPI app titled "Kodiak Reference Library" v1.0.0. It embeds the query, cosine-ranks against the loaded vectors, strips the raw vectors from the response, and returns scored hits with their `source` and `type`.
- `search(query, k, type_filter)` — the same logic as a plain Python function, so it is callable in-process by the pipeline and by tests, not only over HTTP.
- `kodiak_reference_search` — the agent-callable MCP tool registered in `.agents/mcp-kodiak-reference.json`, so a Muse / kiro agent can query the corpus with no HTTP hop. Confirmed in the manifest and wired through `src/creative_automation/api.py`.
- Keyword fallback — when vectors are thin or a query is hashtag/locale specific, `_keyword_fallback` greps the localization, recipe, and hashtag files so the answer degrades to real grep hits instead of an empty list.

The embedding layer under it is `src/creative_automation/embeddings.py`: Amazon Nova-2 multimodal embeddings (`amazon.nova-2-multimodal-embeddings-v1:0`), dimension **1024**, purpose `GENERIC_INDEX` (built to be a vector-store index across all modalities), with a Titan text fallback. The write-path that lets new work rejoin the base is `src/creative_automation/asset_library.py` — the `AssetLibrary` service that classifies by `AssetKind`, dedups by sha256, and writes object + sidecar into the DAM.

So the front end already has an endpoint that answers "what has the brand done that looks or reads like this?" against 3146 embedded rows. Existing is a mode built on that endpoint. Nothing in section 4 requires a new retrieval engine.

---

## 4. How to hit this hard out the gate

Concrete moves, ordered so the fastest win ships first. Each names the real surface it stands on.

### 4.1 Surface Existing as a first-class front-end mode

Add a search box in the front end that calls the reference API `/search` directly. Its result is not a generation — it is the real historical asset with its metadata, caption, or transcript snippet attached, presented as an answer: "here is what Kodiak already did." Because the corpus is already embedded (3146 rows) and the endpoint already ranks and returns, this is UI plus one fetch. It is wiring, not building. Put it beside the generate box, not behind it — Existing is the first thing a director should reach for.

### 4.2 Make the corpus answer historical questions

The youtube SRT transcripts, the eight social `-deep.json` manifests, and the `brand-lore/` folder are text. Embed and expose them through the same `/search` so a question like "what is Kodiak's Park City story?" or "what worked for fall?" returns real, sourced passages — the actual caption, the actual transcript line, the actual ambassador-guide paragraph — rather than a model's guess. This is the difference between a brand memory and a brand hallucination: the answer cites a file that exists. The embed path (`embed_text`, `embed_batch` in `embeddings.py`) and the retrieval path (`search`) both already exist; this move points them at the text surfaces that are not yet fully indexed.

### 4.3 Role models and examples per category

A director wants exemplars, not a firehose. Tag the gold-standard asset per category — the best recipe card, the strongest seasonal hero, the cleanest lifestyle shot — so "show me exemplar recipe-card examples" returns the best real ones instead of all 2355. The heraldstack GPU harness (a separate repo) already produced a category-to-asset index as a companion file, `tools/kodiak-seed-gen/asset-catalog.json`; the pipeline can consume it as a plain input to seed these tags, alongside the harness brand-fit scorer and season-awareness signals (section 5). Exemplar selection turns Existing from a search into a curated set of role models.

### 4.4 Augment, do not replace — the brainstorming loop

The loop that makes this a brainstorming machine rather than an archive:

- **query Existing** — the director asks the corpus a question through `/search`
- **pick a role-model asset** — choose one of the returned exemplars as the reference to work from
- **riff** — generate a new variation against it: a control-structure restyle, a new season, a new market. This is the generate path (Nova Pro composition, RAG-grounded) already live in the pipeline
- **score** — the new variation is measured against the brand-cluster space (the harness brand-fit scorer, consumed as a signal)
- **fold back** — if it scores well, write it into the queryable base via `AssetLibrary.add_asset`, so the next director's Existing query can find it

Every good new variation makes the base larger and better. Call it the regeneration cradle: the corpus heals and grows with use instead of decaying. The human stays the director at every step — the machine executes the variations, the director chooses source, palette, and which results earn a place back in the base.

### 4.5 Consume the harness contributions as files

The heraldstack GPU harness produced three mechanical, queryable inputs the pipeline can treat as plain files, no coupling required:

- a category asset-catalog (`tools/kodiak-seed-gen/asset-catalog.json`) — feeds 4.3 exemplar tagging
- a brand-fit scorer — feeds 4.4 scoring, so "is this on-brand?" is a number, not a vibe
- season-awareness — lets Existing and the riff loop reason about fall / holiday / summer without a human labeling each asset

These are the director's instruments. The harness built them offline on GPU; the pipeline reads them.

---

## 5. Live today vs next

The maturity view, same discipline as the system overview: what stands on a verified surface now, and what section 4 adds.

| capability                                      | status | evidence                                                            |
| ----------------------------------------------- | ------ | ------------------------------------------------------------------- |
| historical corpus scraped + mirrored to DAM     | live   | `data/raw-ingest/kodiakcakes/`, `counts.json`, S3 raw-ingest prefix |
| corpus embedded (3146 rows, Nova-2, 1024-dim)   | live   | `data/vectors/manifest.json`                                        |
| `/search` retrieval endpoint + `search()` + MCP | live   | `reference_api.py`, `.agents/mcp-kodiak-reference.json`             |
| keyword fallback for thin-vector queries        | live   | `_keyword_fallback` in `reference_api.py`                           |
| DAM write-path to fold new work back in         | live   | `AssetLibrary` in `asset_library.py`                                |
| Existing as a front-end mode (search box UI)    | next   | section 4.1 — wiring over the live endpoint                         |
| transcripts + social + lore embedded for Q&A    | next   | section 4.2 — text surfaces into the same index                     |
| per-category role-model tagging                 | next   | section 4.3 — consume harness `asset-catalog.json`                  |
| riff -> score -> fold-back loop                 | next   | section 4.4 — generate + brand-fit scorer + `add_asset`             |

---

## The rule in one sentence

The scrape is not fallback imagery — it is a gold-standard, mostly-embedded corpus with a retrieval spine already in `reference_api.py`, so the front end should surface **Existing** as a first-class mode where a director queries what the brand already did, picks a role model, riffs a new on-brand variation against it, and folds the good ones back into a base that compounds over time.
