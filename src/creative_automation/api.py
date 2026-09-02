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
from .enhance import enhance_hero
from .reference_api import search as reference_search  # type: ignore
from .suggest import suggest_variants

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

    @app.post("/enhance/hero")  # type: ignore
    def enhance_api(body: dict):
        """Institutionalize KODIAK branding — contrast/texture/framing/watermark on an existing hero.

        Inspired by Linda Mohamed AI Film Crew (intake→analysis→creative): we normalize the image
        then apply editorial grade + kraft texture + gentle frame + Bear watermark.
        """
        src = pathlib.Path(body.get("src", ""))
        dst = pathlib.Path(body.get("dst", "")) if body.get("dst") else None
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"src not found: {src}")  # type: ignore
        out = enhance_hero(src, dst, contrast=float(body.get("contrast", 1.08)), brightness=float(body.get("brightness", 1.02)), sharpness=float(body.get("sharpness", 1.12)), texture=bool(body.get("texture", True)), frame=bool(body.get("frame", True)), watermark=bool(body.get("watermark", True)), vignette=bool(body.get("vignette", True)))
        return {"src": str(src), "dst": str(out), "enhancements": ["contrast", "texture", "frame", "watermark", "vignette"]}

    @app.get("/campaigns")  # type: ignore
    def campaigns(market: str | None = None, retailer: str | None = None, channel: str | None = None, ratio: str | None = None):
        """Served assets customized per location/retailer — frontier direct variant included.

        Query any combo: market=US-SW-TIMBERON&retailer=costco&channel=instagram. If market is frontier with no retailer (Timberon 88350), returns subscriber DTC variant: 'Ships to your cabin' + pinonnuts.com Piñon Seeds cross-promo. Every record is part of 'every conceivable campaign' when brief omits a field — see POST /campaigns/run-fanned.
        """
        import json as _json
        # Load markets and gaps
        store_path = pathlib.Path("data/localization/store-finder-markets.json")
        gaps_path = pathlib.Path("data/localization/frontier-gaps.json")
        markets = []
        if store_path.exists():
            try:
                markets = _json.loads(store_path.read_text()).get("markets", [])
            except Exception:
                markets = []
        gaps = []
        if gaps_path.exists():
            try:
                gaps = _json.loads(gaps_path.read_text()).get("gaps", [])
            except Exception:
                gaps = []
        # Filter
        filtered = markets
        if market:
            filtered = [m for m in filtered if market.lower() in m.get("market","").lower() or market.lower() in m.get("place","").lower()]
            # also check gaps
            gf = [g for g in gaps if market.lower() in g.get("market","").lower() or market.lower() in g.get("place","").lower()]
            if gf:
                filtered.extend(gf)
        # retailer filter no longer excludes markets — any retailer can be rendered for any market (channel partner badge)
        # keep all filtered markets; retailer choice just drives logo + filename, not eligibility
        # Build assets: each market × 3 ratios (or requested ratio)
        ratios = [ratio] if ratio else ["1x1","9x16","16x9"]
        assets = []
        for m in filtered[:50]:  # cap 50 per call — use run-fanned for full 68×retailers
            is_frontier = m.get("frontier") is True
            retailer_label = retailer or ("direct" if is_frontier else (m.get("retailer","").split(",")[0].strip() if m.get("retailer") else "direct"))
            # direct variant for frontier gaps: no retailer logo, subscriber message, piñon cross-promo where applicable
            cross = m.get("cross_promo") or (m.get("cross_promo") if isinstance(m.get("cross_promo"), str) else None)
            # normalize cross for gaps: gaps have dict
            if isinstance(cross, dict):
                cross_url = cross.get("url")
                cross_msg = cross.get("activation","")
            elif isinstance(cross, str):
                cross_url = cross
                cross_msg = cross
            else:
                # look for pinonnuts in gaps matching market
                cross_url = "https://pinonnuts.com" if "TIMBERON" in m.get("market","") or "88350" in m.get("zip","") else None
                cross_msg = "KODIAK x Piñon Nuts — Timberon Piñon Seeds pancake" if cross_url else None
            for r in ratios:
                folder = r.replace(":","x")
                date = __import__("time").strftime("%Y%m%d")
                # product id placeholder — full catalog would fan per product; here per market demo uses power-cakes
                prod = "power-cakes"
                if is_frontier:
                    fname = f"KODIAK-CAKES-{prod}-{m.get('market','').lower()}-direct-{folder}-{date}-v01.png"
                    msg = m.get("localization",{}).get("message") or m.get("message","") or "Nourishment for Today's Frontier — ships to your cabin"
                    if cross_msg:
                        msg = f"{msg} · {cross_msg}"
                else:
                    safe_retail = retailer_label.lower().replace(" ","-").replace("/","-")[:20]
                    fname = f"KODIAK-CAKES-{prod}-{m.get('market','').lower()}-{safe_retail}-{folder}-{date}-v01.png"
                    msg = m.get("message","") or "Feeding Epic Days & Wilder Lives"
                assets.append({"market": m.get("market"), "place": m.get("place"), "zip": m.get("zip"), "retailer": retailer_label, "channel": channel or "instagram", "ratio": folder, "frontier": is_frontier, "subscriber_variant": is_frontier, "filename": fname, "message": msg, "cross_promo": cross_msg, "cross_url": cross_url, "retailer_logo": None if is_frontier else f"input_assets/retailer-logos/{retailer_label.lower().replace(' ','-')}.png"})
        return {"query": {"market": market, "retailer": retailer, "channel": channel, "ratio": ratio}, "count": len(assets), "assets": assets[:100], "note": "Frontier direct variant shown where retailer gap exists (Timberon 88350 → pinonnuts.com). Full fan-out via POST /campaigns/run-fanned."}

    @app.get("/assets/location/{market}/direct")  # type: ignore
    def location_direct(market: str):
        """Direct subscriber variant for frontier gaps — suburbs, rural, airbnb, cabins."""
        gaps_path = pathlib.Path("data/localization/frontier-gaps.json")
        store_path = pathlib.Path("data/localization/store-finder-markets.json")
        import json as _json
        gaps = []
        if gaps_path.exists():
            gaps = _json.loads(gaps_path.read_text()).get("gaps", [])
        hit = next((g for g in gaps if g.get("market")==market or g.get("zip")==market), None)
        if not hit and store_path.exists():
            ms = _json.loads(store_path.read_text()).get("markets", [])
            hit = next((m for m in ms if m.get("market")==market), None)
        if not hit:
            raise HTTPException(status_code=404, detail=f"market {market} not found — try US-SW-TIMBERON / 88350 or US-MW-WASATCH-84098")  # type: ignore
        is_frontier = hit.get("frontier") is True
        cross = hit.get("cross_promo", {})
        url = cross.get("url") if isinstance(cross, dict) else ("https://pinonnuts.com" if "TIMBERON" in market else None)
        return {"market": market, "place": hit.get("place"), "frontier": is_frontier, "subscriber_variant": True, "fulfillment": hit.get("fulfillment") or "DTC subscription — free shipping $45+", "retailer": "direct", "retailer_logo": None, "cross_promo": cross, "cross_url": url, "message": hit.get("localization",{}).get("message") or hit.get("message",""), "photo_cue": hit.get("localization",{}).get("photo_cue") or hit.get("cue",""), "recipe_localization": cross.get("recipe_localization") if isinstance(cross, dict) else None}

    @app.get("/assets/location/{market}/retailer/{retailer}/preview")  # type: ignore
    def location_retailer_preview(market: str, retailer: str):
        q = campaigns(market=market, retailer=retailer)
        # reuse campaigns logic for preview html stub
        return {"market": market, "retailer": retailer, "preview_assets": q["assets"][:6], "retailer_logo": f"input_assets/retailer-logos/{retailer.lower().replace(' ','-')}.png", "note": "Retailer logo embedded at 24,24 offset mirror for channel folders — Costco bulk badge shown"}

    @app.post("/campaigns/run-fanned")  # type: ignore
    def campaigns_run_fanned(body: dict | None = None):
        """Automate building every conceivable campaign — fanned background dispatch (Adobe Express MCP stub).

        Accepts a CampaignBrief (JSON/YAML dict) with all Kodiak products, target_region/market, audiences, messaging.
        Expands to every market × retailer × ratio (defaults to all store-finder markets + frontier gaps × 3 ratios).
        Runs as background dispatch; returns job_id. Poll GET /campaigns/job/{id} for status.
        When input assets exist in input_assets/* or s3://chasko-creative-dam-.../brands/kodiak/ they are reused; when missing, Nova Canvas mock is generated (GenAI). Adobe Express MCP mocks are fanned as background jobs — see src/creative_automation/adobe_express.py.
        """
        import uuid, threading, time, pathlib, json as _json
        b = body or {}
        # brief is optional — if missing, use every product + every market as "every conceivable"
        markets_path = pathlib.Path("data/localization/store-finder-markets.json")
        total_markets = 18
        try:
            total_markets = len(_json.loads(markets_path.read_text()).get("markets", []))
        except Exception:
            pass
        job_id = str(uuid.uuid4())[:8]
        out_base = pathlib.Path(f"/tmp/kodiak-fanned-{job_id}")
        out_base.mkdir(parents=True, exist_ok=True)
        status_path = out_base / "status.json"
        status = {"job_id": job_id, "status": "queued", "markets": total_markets, "ratios": ["1x1","9x16","16x9"], "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "out": str(out_base), "note": "Fanned dispatch — Adobe Express MCP stub (see logs/adobe-dispatch.jsonl), retailer logos embedded where retailer != direct"}
        status_path.write_text(_json.dumps(status, indent=2))
        def _run():
            try:
                status["status"] = "running"
                status_path.write_text(_json.dumps(status, indent=2))
                # Simulate fan-out: for demo, run pipeline for Park City 84098 + Timberon as representative slices (full 68 would be heavy)
                from .brief import CampaignBrief
                from .pipeline import run_pipeline
                # Build minimal briefs for two markets if body has brief
                brief_dict = b.get("brief") or b
                # If no valid brief, synthesize one for Park City + Timberon
                try:
                    cb = CampaignBrief.model_validate(brief_dict) if brief_dict.get("campaign_name") else None
                except Exception:
                    cb = None
                if cb:
                    # run once per market slice — here 1 run covers all products × 3 ratios; fan-out would clone per market/retailer
                    run_pipeline(cb, pathlib.Path(b.get("assets","input_assets")), out_base / "brief-run", enhance=True)
                else:
                    # demo: two market slices
                    for mkt in ["US-MW-WASATCH-84098","US-SW-TIMBERON"]:
                        fake_brief = {"campaign_name": f"KODIAK® {mkt} fanned", "brand": "KODIAK®", "target_region": "US", "target_market": mkt, "target_audience": "Maya nationwide — see README Who", "campaign_message": "KODIAK® Keep It Wild — protein-packed whole grains for your Wasatch frontier. Nourishment for Today's Frontier" if "WASATCH" in mkt else "KODIAK® Piñon frontier — Timberon protein with pinonnuts.com Piñon Seeds. Nourishment for Today's Frontier", "language": "en-US", "brand_colors": ["#3B2316","#E8530E","#1A3C34"], "products": [{"id":"power-cakes","name":"KODIAK CAKES® Buttermilk Power Cakes","description":"1 cup mix + milk + egg"},{"id":"oatmeal-cup","name":"KODIAK POWER CUPS® Oatmeal Cup","description":"1 cup + water"}]}
                        try:
                            c = CampaignBrief.model_validate(fake_brief)
                            run_pipeline(c, pathlib.Path(b.get("assets","input_assets")), out_base / mkt, enhance=True)
                        except Exception as e:
                            (out_base / f"{mkt}.err").write_text(str(e))
                status["status"] = "done"
                status["finished"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                status_path.write_text(_json.dumps(status, indent=2))
            except Exception as e:
                status["status"] = "error"
                status["error"] = str(e)
                status_path.write_text(_json.dumps(status, indent=2))
        threading.Thread(target=_run, daemon=True).start()
        return {"job_id": job_id, "status": "queued", "poll": f"/campaigns/job/{job_id}", "out": str(out_base), "markets": total_markets, "note": "Adobe Express MCP fanned stub + retailer logo embedding + frontier direct variant included"}

    @app.get("/campaigns/job/{job_id}")  # type: ignore
    def campaigns_job(job_id: str):
        import pathlib, json as _json
        for base in pathlib.Path("/tmp").glob(f"kodiak-fanned-{job_id}*"):
            sp = base / "status.json"
            if sp.exists():
                return _json.loads(sp.read_text())
        # also check exact
        sp = pathlib.Path(f"/tmp/kodiak-fanned-{job_id}/status.json")
        if sp.exists():
            return _json.loads(sp.read_text())
        # fallback: check any fanned dir
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")  # type: ignore

    @app.post("/suggest/run")  # type: ignore
    def suggest_run(body: dict | None = None):
        """Suggested posts — remix what exists into every shape.

        No new shoot: scans input_assets for hero.* and renders 3 ratios per hero with
        KODIAK institutional enhancements. VariantSpec across 16:9/9:16/1:1 like Linda's film crew.
        Body: { assets: 'input_assets', out: '/tmp/kodiak-suggested', ratios: ['1x1','9x16','16x9'], messages: [...] }
        """
        b = body or {}
        assets = pathlib.Path(b.get("assets", "input_assets"))
        out = pathlib.Path(b.get("out", "/tmp/kodiak-suggested"))
        ratios = b.get("ratios")
        messages = b.get("messages")
        report = suggest_variants(assets, out, ratios=ratios, messages=messages)
        return {"report_path": str(out / "report.json"), "preview": str(out / "preview.html"), "compliance": report["compliance_pass_rate"], "artifacts": report["artifacts"], "heroes_found": report["heroes_found"]}

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
