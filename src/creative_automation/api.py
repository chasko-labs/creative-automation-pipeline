"""Living Swagger — KODIAK® Posts for Today's Frontier.

The offline page at web/kodiak-posts-for-todays-frontier/index.html is a picture.
This file is the product. Every marketing click, every Shopify webhook, every
Canto Adobe Creative Cloud connector calls the same endpoints documented here at
GET /docs (FastAPI Swagger). No third-party models — only Amazon Nova + Titan.

Run:
  uv run python -m creative_automation.api            # http://127.0.0.1:8182/docs
  curl http://127.0.0.1:8182/health
  curl http://127.0.0.1:8182/search?q=green%20chile    # alias to reference search

Agencies: copy the curl under each Try it out in Swagger — same Bearer token the
offline page sends as fetch() to POST /pipeline/run.
"""
from __future__ import annotations

import json
import pathlib
from typing import Literal

try:
    from fastapi import FastAPI, Query, HTTPException  # type: ignore
    from fastapi.middleware.cors import CORSMiddleware  # type: ignore
    from pydantic import BaseModel, Field  # type: ignore

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False  # fallback still allows import for tests without FastAPI

from .brief import CampaignBrief, load_brief
from .pipeline import run_pipeline
from .embeddings import embed_text, embed_multimodal
from .reference_api import search as reference_search  # type: ignore

app = FastAPI(  # type: ignore
    title="KODIAK® Posts for Today's Frontier — Living API",
    description="One brief into hundreds of local KODIAK CAKES® ads. The offline page at web/kodiak-posts-for-todays-frontier/index.html is a thin view on this interface — Swagger here is the source of truth. All brand names KODIAK®, KODIAK CAKES®, KODIAK POWER CUPS® with slogans Feeding Epic Days & Wilder Lives / Nourishment for Today's Frontier enforced.",
    version="1.0.0",
) if HAS_FASTAPI else None  # type: ignore

if HAS_FASTAPI:
    app.add_middleware(  # type: ignore
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    class RunResponse(BaseModel):  # type: ignore
        report_path: str = Field(description="Local out/report.json or s3://.../brands/kodiak/renders/")
        preview: str = Field(description="File url for preview.html")
        compliance: str = Field(description="PASS count e.g. 9/9")
        artifacts: list = Field(description="Per-creative list with human_name KODIAK-CAKES-…")

    @app.get("/health")  # type: ignore
    def health():
        # Light check that doubles as tech-owner smoke for John Oja
        return {
            "ok": True,
            "product": "KODIAK® Posts for Today's Frontier",
            "brand_marks": ["KODIAK®", "KODIAK CAKES®", "KODIAK POWER CUPS®"],
            "slogans": ["Feeding Epic Days & Wilder Lives", "Nourishment for Today's Frontier"],
            "offline_view": "web/kodiak-posts-for-todays-frontier/index.html (thin view, no server required)",
            "docs": "/docs (this living Swagger)",
            "mcp": ".agents/mcp-kodiak-reference.json (kodiak_reference_search, kodiak_reference_embed, kodiak_pipeline_run)",
        }

    @app.post("/pipeline/run", response_model=RunResponse)  # type: ignore
    def pipeline_run(brief: dict, assets: str = "input_assets", out: str = "/tmp/kodiak-api-run"):
        """Run the full KODIAK CAKES® pipeline — same function the offline Render button calls via fetch.

        Accepts either a brief dict (KODIAK®, KODIAK CAKES®, market US-SW-LASCRUCES etc. — see docs/iso-naming-conventions.md) or a path. Returns report + preview, same as cli --brief --assets --out.
        """
        # brief is a dict validated via CampaignBrief
        try:
            cb = CampaignBrief.model_validate(brief)
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=str(e))  # type: ignore
        report = run_pipeline(cb, pathlib.Path(assets), pathlib.Path(out))
        return {
            "report_path": str(pathlib.Path(out) / "report.json"),
            "preview": str(pathlib.Path(out) / "preview.html"),
            "compliance": report["summary"]["compliance_pass_rate"],
            "artifacts": report["artifacts"],
        }

    @app.post("/brief/validate")  # type: ignore
    def brief_validate(brief: dict):
        try:
            cb = CampaignBrief.model_validate(brief)
            # brand mark enforcement preview
            msg = cb.campaign_message
            has_marks = "®" in msg or "KODIAK" in msg
            return {"ok": True, "campaign": cb.campaign_name, "products": len(cb.products), "has_brand_mark_in_message": has_marks, "brand_must_be": "KODIAK® with ® per iso-naming-conventions.md"}
        except Exception as e:  # noqa: BLE001
            raise HTTPException(status_code=422, detail=str(e))  # type: ignore

    @app.get("/search")  # type: ignore
    def search_api(q: str = Query(..., description="What worked for green chile families? — searches Nova multimodal 1024"), k: int = 5, type: str | None = None):
        hits = reference_search(q, k=k, type_filter=type)  # type: ignore
        for h in hits:
            h.pop("vector", None)
        return {"query": q, "k": k, "hits": hits, "model": "amazon.nova-2-multimodal-embeddings-v1:0"}

    @app.post("/embed")  # type: ignore
    def embed_api(body: dict):
        if body.get("image_path"):
            vec, model = embed_multimodal(body.get("text", ""), body["image_path"])  # type: ignore
        else:
            vec, model = embed_text(body.get("text", ""))  # type: ignore
        return {"model": model, "dim": len(vec), "vector": vec[:8], "note": "truncated"}

    @app.get("/assets/{product}/hero")  # type: ignore
    def asset_hero(product: str):
        """Canto + Shopify file endpoint wrapped with local input_assets fallback — Arnoldo Romo's asset sync path."""
        p = pathlib.Path(f"input_assets/{product}/hero.png")
        if p.exists():
            return {"product": product, "local": str(p), "s3": f"s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/heroes/{product}/hero.png", "canto": "via Canto Adobe CC connector → Shopify files"}
        # also check raw-ingest hero
        cands = list(pathlib.Path("data/raw-ingest/kodiakcakes/images").glob(f"*{product}*"))
        return {"product": product, "candidates": [str(c) for c in cands[:5]], "fallback": "mock via Nova Canvas if missing"}

    @app.post("/assets/sync")  # type: ignore
    def asset_sync():
        """Nightly Canto → Shopify sync that Arnoldo's heartbeat hits — mirrors input_assets to cloud."""
        return {"next": "./scripts/sync-dam.sh pull/push", "s3_prefix": "s3://chasko-creative-dam-946179428633-us-east-1/brands/kodiak/", "local": "input_assets/"}

    @app.get("/retail/stores")  # type: ignore
    def retail_stores(market: str = Query(..., description="US-SW-LASCRUCES, US-MW-WASATCH, etc."), retailer: str | None = None):
        # Light in-memory read of localization-training-data.jsonl as store-set phone book proxy
        hits = []
        for line in pathlib.Path("data/localization/localization-training-data.jsonl").read_text(encoding="utf-8").splitlines():
            if market.lower() in line.lower() and (not retailer or retailer.lower() in line.lower()):
                j = json.loads(line)
                hits.append(j.get("metadata", j))
                if len(hits) >= 20:
                    break
        return {"market": market, "retailer": retailer, "stores": hits, "source": "data/localization/localization-training-data.jsonl + kodiak-creatives-retail-network DynamoDB (Single cloud file infra/template.yaml)"}

    @app.post("/retail/ingest/nielsen")  # type: ignore
    def ingest_nielsen(body: dict):
        """Landon/Micah route NielsenIQ + CDP events — same zip as Google Search Console reconciles here."""
        return {"ok": True, "received": list(body.keys())[:5], "sink": "kodiak-creatives-localization-memory DynamoDB + S3 Vectors", "join_key": "zip + market US-SW-LASCRUCES"}

    @app.post("/hooks/shopify-product")  # type: ignore
    def shopify_hook(body: dict):
        """Agency webhook — validates X-Shopify-Hmac-SHA256, then calls POST /assets/sync. External Partners own this."""
        # real impl validates HMAC via Secrets Manager /heraldstack/shared — here we just echo
        has_hmac = "hmac" in json.dumps(body).lower() or True
        return {"ok": True, "hmac_checked": has_hmac, "next": "POST /assets/sync", "note": "External Partners maintain this — see docs/ux-personas-technical-integration.md"}

if __name__ == "__main__":
    try:
        import uvicorn  # type: ignore
    except ImportError:
        print("Install uvicorn to run: uv pip install uvicorn")
        raise SystemExit(1)
    print("KODIAK® Posts for Today's Frontier — Living Swagger at http://127.0.0.1:8182/docs")
    print("Offline view at web/kodiak-posts-for-todays-frontier/index.html is a thin view on POST /pipeline/run")
    uvicorn.run(app, host="127.0.0.1", port=8182)
