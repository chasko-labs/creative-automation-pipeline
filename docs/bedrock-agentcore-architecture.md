# Bedrock AgentCore Architecture — Kodiak Frontier Creative System (Planned and Live)

> One cloud setup, hundreds of local ads. A lot of context goes into every Nova call — we never use third party models, only Amazon models (Nova family, Titan Embed).

```mermaid
flowchart TB
    %% Human entry — plain language, marketing owns the first step
    Maya["Maya — Brand Manager<br/>Park City"] --> Brief["One-page brief<br/>place + audience + one line"]
    Diego["Diego — Field Ambassador<br/>Las Cruces / Alamogordo"] --> Brief
    Priya["Priya — Paid Media Lead<br/>Central"] --> StoreBook["Store phone book<br/>Business Locations CSV<br/>Store Sets"]

    Brief --> IdeaSheet["Idea sheet<br/>kodiak.yaml<br/>kodiak-publix / target / costco<br/>on-the-go / diner / subscription"]

    %% Storage — style and photos, versioned, private
    subgraph CloudStorage["Cloud Storage — Style Library (Live: s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/)"]
        Tokens["Style tokens<br/>design/tokens/kodiak.json<br/>Bear Brown #3B2316<br/>Blaze Orange #E8530E<br/>Frontier Green #1A3C34"]
        Photos["Photo library<br/>input_assets/power-cakes/hero.png<br/>board logos<br/>Wasatch heroes"]
        Refs["References<br/>keep-it-wild<br/>photo direction, voice, prompts kodiak-01..08<br/>templates 1x1/9x16/16x9"]
    end

    %% Regional memory — place, audience, message — the training data that learns
    subgraph RegionalMemory["Regional Memory — What Worked Per Place"]
        TableLoc["Lookup table<br/>DynamoDB: kodiak-creatives-localization-memory<br/>market → place + audience + message + cue + zip"]
        TableStores["Retail network<br/>DynamoDB: kodiak-creatives-retail-network<br/>store_id → street + city + zip + store set<br/>Walmart + Albertsons Alamogordo<br/>Target Las Cruces, diners"]
        VectorLocal["Searchable knowledge<br/>S3 Vectors + Bedrock Knowledge Base<br/>localization-training-data.jsonl<br/>18 places + Las Cruces green chile<br/>plus every campaign that runs"]
    end

    %% Ingest — where brand knowledge and Amazon store come from
    BrandFetch["Brand inventory<br/>kodiakcakes.com + Amazon store<br/>19CF7868-DF80-4939-932A<br/>collections, ingredients,<br/>subscription 15% over 45"] --> CloudStorage
    BrandFetch --> VectorLocal
    StoreLocator["Store locator<br/>kodiakcakes.com/pages/store-locator<br/>Alamogordo example"] --> TableStores

    %% Bedrock Knowledge Base — RAG, the big context box around Nova
    subgraph BedrockKB["Bedrock Knowledge Base — Retrieval Augmented Generation<br/>(vector store: S3 Vectors, embedding: Titan Embed Text v2:0, chunking: semantic)"]
        Ingest["Ingest job<br/>S3 → chunk → embed → vector"]
        Retrieve["Retrieve<br/>query: place + audience + message"]
        Rerank["Rerank + filter<br/>by market / retailer"]
    end

    %% What feeds the Knowledge Base
    CloudStorage --> Ingest
    RegionalMemory --> Ingest
    BrandFetch --> Ingest

    %% AgentCore — the runtime that holds it together
    subgraph AgentCore["Bedrock AgentCore — Planned Runtime (Live fallback is local pipeline)"]
        Runtime["AgentCore Runtime<br/>serverless, auto scale<br/>wraps run_pipeline()"]
        Gateway["AgentCore Gateway<br/>store list + photo fetch as tools<br/>(photo library, retail network)"]
        Memory["AgentCore Memory<br/>short turn + long cross-session<br/>Diego's Las Cruces green chile win remembered"]
        Browser["AgentCore Browser<br/>Nova Act visual check<br/>3 viewports 1080x1080 / 1080x1920 / 1920x1080"]
        Identity["AgentCore Identity<br/>acts on behalf of Maya/Priya<br/>via Identity Center"]
    end

    %% The RAG context that goes into Nova — ton of context, not just the brief line
    IdeaSheet --> Retrieve
    TableStores --> Retrieve
    Tokens --> Retrieve
    Refs --> Retrieve

    Retrieve --> Rerank --> ContextPack["Context pack for Nova<br/>— winning message for this market<br/>— audience words that worked there<br/>— photo cue that won (kodiak-04 green chile bench)<br/>— brand rules (bear @24,24, 8px orange bar, scrim)<br/>— ingredient truth (100% whole grains, 14g, non-GMO)<br/>— store set nearby (Las Cruces Target + Alamogordo)"]

    ContextPack --> NovaText["Nova Micro / Lite<br/>Converse API, maxTokens explicit<br/>rewrites headline for this market<br/>keeps Kodiak voice<br/>no third party models"]
    ContextPack --> NovaImage["Nova Canvas<br/>InvokeModel, 1024x1024 cfg 7.5<br/>seed 42-49, prompts kodiak-01..08<br/>clean background, sky negative space<br/>no third party models"]

    %% Embeddings — Titan only
    VectorLocal -.-> EmbedModel["Titan Embed Text v2:0<br/>only embedding model<br/>used for knowledge base"]
    Ingest -.-> EmbedModel

    %% Compose — deterministic, not another model
    NovaText --> Compose["Compose — deterministic Pillow<br/>blurred Wasatch cover + 0.18 scrim<br/>hero contain, message bar 32%@68%<br/>slab 56/64/72, orange bar, bear logo<br/>from tokens, not hard-coded"]
    NovaImage --> Compose
    Photos --> Compose
    Tokens --> Compose

    %% Checks
    Compose --> Checks["Brand + legal check<br/>bear present, palette #3B2316/#E8530E/#1A3C34<br/>no guaranteed/miracle/FDA<br/>blocks 17% class action repeat"]

    %% Output
    Checks --> Renders["Renders<br/>output_kodiak/{product}/{1x1,9x16,16x9}/<br/>report.json + report.jsonl<br/>preview.html with PASS badges"]
    Renders --> S3Renders["Cloud renders<br/>brands/kodiak/renders/"]
    Renders --> LogBucket["Log bucket<br/>kodiak-creatives-logs"]

    %% Learning loop back to memory
    Renders --> TableLoc
    Renders --> VectorLocal

    %% Retail handoff — Meta copy
    Priya --> MetaSetup["Meta Business Locations<br/>upload store list CSV<br/>organize Store Sets<br/>Advantage Budget OFF<br/>one local bucket per place<br/>one post reused via Existing Post<br/>dynamic {{store.city}} + map + Get Directions"]
    Renders -.-> MetaSetup
    TableStores -.-> MetaSetup

    %% Small + diner + subscription stay in same phone book
    TableStores -.-> Diner["Diners within 5 miles<br/>co-brand skillet + Bear Bites side<br/>1x1 table tent + 16x9 menu board"]
    TableStores -.-> Subscription["Home delivery subscription<br/>15% off, free ship over 45<br/>kodiakcakes.com/pages/subscriptions"]

    %% Cloud formation holds it all
    CloudFormation["Single Cloud Formation file<br/>infra/template.yaml<br/>buckets + tables + log bucket<br/>retains on delete<br/>validated cfn-lint + validate-template"] -.-> CloudStorage
    CloudFormation -.-> TableLoc
    CloudFormation -.-> TableStores
    CloudFormation -.-> LogBucket

    %% Human view
    Maya -.-> BrandView["Human brand view<br/>kodiak-brand-explained.md<br/>kodiak-brand-view.html<br/>ux-persona-kodiak.md"]
```

## How the ton of context around Nova actually works — in plain words

Marketing writes one line like "Green chile meets grizzly — protein for your Las Cruces frontier." That line alone is not enough. Before the system asks Nova to do anything, it pulls a pack of what already worked in that place:

- **From the lookup table** — the last winning audience and line for market `US-SW-LASCRUCES` (green chile families 28 to 45, Hatch roast, Organ Mountains bench photo cue).
- **From searchable knowledge** — the 18 seeded places plus every campaign that has run since, found by meaning not just exact words, so "green chile families" also finds Albuquerque red chile and Hatch season.
- **From the style library** — the three frontier colors, the bear clear space and size, the scrim at 68 percent, the slab sizes per ratio, and the legal guardrail that blocks over-claiming protein.
- **From the store phone book** — the actual Target on the north side of Las Cruces and the Walmart and Albertsons in Alamogordo that the store locator already shows, plus the small independent on Main and the diner on US-70 if Maya added them.
- **From brand truth** — ingredients and subscriptions copied from kodiakcakes.com and the Amazon brand store (100 percent whole grains, protein, non genetically modified, real fruit and nuts and seeds, colors from natural sources, 15 percent off plus free shipping over 45 for home delivery).

That pack — a few hundred words, five to eight retrieved snippets — is added to the prompt that goes to Nova. Nova Micro (or Lite) rewrites the headline so it sounds like Kodiak in Las Cruces, not Kodiak in Minneapolis. Nova Canvas builds a frontier photo that leaves sky empty for the line and never puts text or a logo inside the image itself. **We never use third party models** — embedding is always Titan Embed Text v2:0, text and image generation are always Nova family models via Bedrock. The knowledge base chunking is semantic, FM-based for tables, and the vector store is S3 Vectors (managed, no servers to run).

The compose step does not use another model at all — it is deterministic code that places the hero, dims the Wasatch cover, puts the line over the dark band, adds the bear at 24,24 and the orange bar, all from tokens. That is why the same three products can make hundreds of different local ads without looking different in brand terms.

## Why this mirrors the single cloud file you asked for

`infra/template.yaml` creates the cloud storage bucket (`chasko-creative-dam-946179428633-us-east-1`, live via the earlier `s3-dam.tf` and now wrapped), the localization memory table, the retail network table (store sets + city clusters + small grocers + diners), and the log bucket — all with retain on delete, versioning, private block, and key encryption. The knowledge base itself is a Bedrock resource that points at the same bucket prefix `brands/kodiak/` where `data/localization/localization-training-data.jsonl` and `references/keep-it-wild/` already live. Tests at `tests/test_e2e.py` prove the pack goes end to end: one brief in, three sizes out, bear and palette pass, Las Cruces green chile row is found.

## Live today vs planned

- **Live today** — local pipeline via `uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak`, style library mirrored to cloud storage at `s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/` via `scripts/sync-dam.sh`, report and preview written locally and synced to `brands/kodiak/renders/`.
- **Planned on top of live** — wrap `run_pipeline()` as an AgentCore Runtime, expose photo fetch and store lookup as Gateway tools, give it Memory so Diego's Las Cruces green chile win is remembered cross-session, let Browser via Nova Act open `preview.html` at the three viewports and block the retail handoff if the bear or bar fails. The diagram above shows the planned blocks in the same place as the live ones — no second account, no hidden stack.

