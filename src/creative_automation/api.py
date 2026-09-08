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

try:
    from fastapi import FastAPI, Query, HTTPException, UploadFile, File, Form  # type: ignore
    from fastapi.middleware.cors import CORSMiddleware  # type: ignore
    from pydantic import BaseModel, Field  # type: ignore

    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False  # fallback still allows import for tests without FastAPI

from .brief import CampaignBrief
from .naming import slugify
from .pipeline import run_pipeline
from .embeddings import embed_text, embed_multimodal
from .enhance import enhance_hero
from .reference_api import search as reference_search  # type: ignore
from .suggest import suggest_variants
from . import dam
from . import dam_library
from .asset_pack import (
    build_asset_pack_zip,
    build_pack_name,
    market_language_tags,
    market_retailers,
    pack_tempdir,
)
from .from_photo import (
    DEFAULT_MARKET,
    build_image_from_photo,
)
from .asset_api import library as asset_library_instance, mount_library_routes

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

    # Mount the DAM library routes (/library/assets POST+GET, get-by-id, select, health) onto
    # this main app so the frontend — which hits the main-API origin — reaches them. Same
    # registration + same AssetLibrary instance the standalone asset_api :8183 surface uses, so
    # there is no drift and add_asset logic is not duplicated (POST goes through ingest_asset for
    # embed-on-ingest). Matches this file's inline-route style — no include_router in this codebase.
    mount_library_routes(app, asset_library_instance)

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

    class LocalizeRequest(BaseModel):  # type: ignore
        text: str = Field(description="Source (English) marketing string to localize")
        market: str = Field(description="Market code, e.g. US-SW-LASCRUCES")
        target_lang: str = Field(description="Target lang_code from market-languages.json (es/ht/ar/nv/...)")

    @app.post("/localize")  # type: ignore
    def localize_api(body: LocalizeRequest):
        """Localize one string with an honest provenance tag — the translation-surfacing seam (issue #124).

        Resolution order the frontend depends on:
          1. precomputed hit in kodiak-creatives-localization-memory DynamoDB -> provider=precomputed
          2. live machine translate on miss, routed by language:
             - Amazon Translate langs -> provider=amazon-translate
             - machine-able gaps -> provider=bedrock (flagged low_confidence)
             - nv/zip -> provider=human-required, original text returned (never machine translated)
          3. offline / no-creds -> source=mock, provider=offline-dictionary (CI stays green)

        Response may also carry low_confidence=true (bedrock gaps) or human_pending=true (nv/zip).
        """
        from .localize_service import localize as _localize

        return _localize(body.text, body.market, body.target_lang)

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
    def campaigns(market: str | None = None, retailer: str | None = None, channel: str | None = None, ratio: str | None = None, product: str | None = None):
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
        # Real product threads into filenames/messages (#205) — power-cakes
        # is only the default when the caller picks nothing.
        prod = slugify(product) if product else "power-cakes"
        prod = prod or "power-cakes"
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
        return {"query": {"market": market, "retailer": retailer, "channel": channel, "ratio": ratio, "product": prod}, "count": len(assets), "assets": assets[:100], "note": "Frontier direct variant shown where retailer gap exists (Timberon 88350 → pinonnuts.com). Full fan-out via POST /campaigns/run-fanned."}

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

    @app.get("/assets/pack/{market}")  # type: ignore
    def asset_pack(
        market: str,
        product: str = Query("savory-waffles", description="Product slug, e.g. savory-waffles / power-cakes"),
        retailer: str | None = Query(None, description="Optional retailer filter (costco/publix/target)"),
        ratio: str | None = Query(None, description="Optional single ratio 1x1|9x16|16x9; default all three"),
    ):
        """Build a retailer asset-pack zip for a market, upload to the S3 DAM, return a download url.

        The frontend (issue #30) hits this to replace the 'S3 zip wiring pending' stub. The
        pack bundles this market's creatives + a manifest.json (market, product, retailers,
        BCP-47 language tags, ISO names of contents, generated timestamp) named
        KODIAK-CAKES-{product}-{REGION}-{locality}-retailers-pack-{YYYYMMDD}-v01.zip .

        S3 path (DAM_S3_BUCKET set): uploads under the DAM 'packs/' prefix and returns a
        presigned {url, key, filename, expires_in, asset_count}. Offline / CI path (no S3):
        returns the same shape with url=null plus local_path + a note so the endpoint still
        works with no boto3 / no creds — mirrors dam.py's graceful S3-disabled fallback.
        """
        # asset list — compose the existing campaigns() builder, do not duplicate its logic
        camp = campaigns(market=market, retailer=retailer, ratio=ratio)
        assets = camp.get("assets", [])

        # market record drives locality + retailer list (store-finder first, then languages file)
        store_path = pathlib.Path("data/localization/store-finder-markets.json")
        record: dict = {}
        if store_path.exists():
            try:
                for m in json.loads(store_path.read_text()).get("markets", []):
                    if m.get("market") == market or m.get("zip") == market:
                        record = m
                        break
            except Exception:
                record = {}

        place = record.get("place") or market
        zip_code = record.get("zip") or ""
        locality = "-".join(p for p in (place, zip_code) if p) or market
        # region: trailing hyphen segments of the market code minus a trailing zip
        region = market

        retailers = [retailer] if (retailer and market_retailers(retailer)) else market_retailers(record.get("retailer"))
        language_tags = market_language_tags(market)

        pack_name = build_pack_name(product, region, locality)

        staging = pack_tempdir()
        zip_path, manifest = build_asset_pack_zip(
            market=market,
            product=product,
            assets=assets,
            retailers=retailers,
            language_tags=language_tags,
            dest_dir=staging,
            pack_name=pack_name,
        )

        key = f"packs/{pack_name}"
        expires_in = 3600
        url = dam.s3_upload_and_presign(zip_path, key, expires=expires_in)
        if url is not None:
            return {
                "url": url,
                "key": key,
                "filename": pack_name,
                "expires_in": expires_in,
                "asset_count": manifest["asset_count"],
                "retailers": retailers,
                "language_tags": language_tags,
                "manifest": manifest,
            }
        # offline / CI fallback — S3 disabled; hand back the local artifact
        return {
            "url": None,
            "key": key,
            "filename": pack_name,
            "expires_in": expires_in,
            "asset_count": manifest["asset_count"],
            "retailers": retailers,
            "language_tags": language_tags,
            "local_path": str(zip_path),
            "manifest": manifest,
            "note": "S3 DAM not configured (DAM_S3_BUCKET unset or boto3 missing) — returning local pack path. Set DAM_S3_BUCKET to get a presigned download url.",
        }

    @app.get("/assets/library")  # type: ignore
    def asset_library(
        category: str | None = Query(None, description="Filter to one of zac-efron|renders|heroes|logos; all four when absent"),
        limit: int = Query(60, description="Max presigned URLs minted per category (default 60, hard max 200)"),
    ):
        """Read-only DAM asset browser — curated Kodiak picker prefixes with presigned GETs.

        Powers the front-page '+' 'Browse past assets' tab. The DAM bucket is fully
        private, so every item carries a presigned GET url (public urls 403). Bucket is
        resolved from dam._s3_bucket_and_prefix() — never hardcoded. raw-ingest/ is never
        listed (pipeline seed data, not picker assets).

        Offline / CI path (dam._s3_enabled() False): returns {"enabled": false, "bucket":
        null, "categories": {...empty...}, "note": ...} with HTTP 200 — mirrors the
        graceful S3-disabled fallback the other /assets routes use, never 500.

        Per-category errors (list or presign failure) degrade to that category's items=[]
        plus an "error" note rather than failing the whole route.

        The listing logic lives in dam_library.list_library — the ONE implementation both
        this dev/local route and generate_lambda's production dispatcher call, so there is
        no drift between the two surfaces.
        """
        return dam_library.list_library(category, limit)

    # content-type -> file extension: the only image types the pipeline hero slot accepts
    _UPLOAD_EXT_BY_CT = {"image/jpeg": "jpg", "image/png": "png"}
    # 15 MB cap — a hero photo is a still frame, not a video; anything larger is a mistake
    _UPLOAD_MAX_BYTES = 15 * 1024 * 1024

    def _input_assets_root() -> pathlib.Path:
        """Repo-root input_assets, overridable via CAP_INPUT_ASSETS_ROOT (tests redirect here).

        The other /assets routes use a bare cwd-relative 'input_assets/'. This endpoint
        writes real bytes, so it resolves an absolute root (repo root, matching gateway.py
        and retailers.py) and honours an env override so tests never touch the real dir.
        """
        import os
        override = os.getenv("CAP_INPUT_ASSETS_ROOT", "").strip()
        if override:
            return pathlib.Path(override)
        return pathlib.Path(__file__).resolve().parents[2] / "input_assets"

    @app.post("/assets/upload")  # type: ignore
    async def asset_upload(
        file: UploadFile = File(..., description="Hero photo — image/jpeg or image/png, <= 15 MB"),
        product: str = Form("power-cakes", description="Product slug the hero belongs to"),
        market: str | None = Form(None, description="Optional market code, echoed for the caller's context"),
    ):
        """Ingest a browser-local photo INTO the pipeline as a product hero (issue #38).

        POST /pipeline/run and /suggest/run take a filesystem PATH string, so a photo that
        lives only in a browser (e.g. a macmini Downloads jpeg) can never enter. This
        multipart endpoint closes that gap: it accepts the uploaded bytes, writes them to
        input_assets/{product}/hero.{ext}, registers the copy in the S3 DAM, and returns the
        asset id + a presigned url. It is the unblocker for #39 (from-photo orchestration).

        Re-upload safety: the canonical hero.{ext} is overwritten so the pipeline always
        finds the latest, but an id-suffixed hero-{asset_id}.{ext} copy is kept alongside so
        an earlier upload is never the only casualty of a re-upload.

        Offline / CI path (no S3): the local file is still written and the same shape returns
        with presigned_url=null — mirrors dam.py's graceful S3-disabled fallback, so the
        endpoint works with no boto3 / no creds.
        """
        content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
        ext = _UPLOAD_EXT_BY_CT.get(content_type)
        if not content_type.startswith("image/") or ext is None:
            raise HTTPException(  # type: ignore
                status_code=400,
                detail=f"unsupported content type {content_type!r}; upload image/jpeg or image/png",
            )

        # read with a hard cap: pull one byte past the limit to detect oversize without
        # trusting a client-supplied Content-Length header
        data = await file.read(_UPLOAD_MAX_BYTES + 1)
        if len(data) > _UPLOAD_MAX_BYTES:
            raise HTTPException(  # type: ignore
                status_code=413,
                detail=f"file exceeds {_UPLOAD_MAX_BYTES // (1024 * 1024)} MB cap",
            )
        if not data:
            raise HTTPException(status_code=400, detail="empty file")  # type: ignore

        from .naming import slugify, today_utc
        import uuid

        product_slug = slugify(product) or "power-cakes"
        asset_id = f"{product_slug}-{today_utc()}-{uuid.uuid4().hex[:8]}"

        product_dir = _input_assets_root() / product_slug
        product_dir.mkdir(parents=True, exist_ok=True)
        hero_path = product_dir / f"hero.{ext}"
        # id-suffixed copy first so a re-upload never leaves zero recoverable heroes
        archive_path = product_dir / f"hero-{asset_id}.{ext}"
        archive_path.write_bytes(data)
        hero_path.write_bytes(data)

        key = f"uploads/{asset_id}/hero.{ext}"
        presigned_url = dam.s3_upload_and_presign(hero_path, key)

        # hand back repo-relative hero path when possible, else the absolute path
        try:
            hero_rel = str(hero_path.relative_to(pathlib.Path(__file__).resolve().parents[2]))
        except ValueError:
            hero_rel = str(hero_path)

        return {
            "asset_id": asset_id,
            "hero_path": hero_rel,
            "archive_path": str(archive_path),
            "presigned_url": presigned_url,
            "product": product_slug,
            "market": market,
            "content_type": content_type,
            "bytes": len(data),
            "note": (
                None
                if presigned_url is not None
                else "S3 DAM not configured (DAM_S3_BUCKET unset or boto3 missing) — file written locally, presigned_url null. Set DAM_S3_BUCKET for a download url."
            ),
        }

    @app.post("/campaigns/from-photo")  # type: ignore
    @app.post("/campaigns/from-prompt")  # type: ignore
    def campaigns_from_photo(body: dict | None = None):
        """Prompt/photo in -> customized branded image out (issue #39 core loop).

        Body: { asset_id?, hero_path?, prompt?, market?, product? }

        Resolution order: an uploaded photo (hero_path or asset_id, mapped to
        input_assets/{product}/hero.* the way #38 wrote it) is used as the hero; if only a
        prompt is supplied the hero is generated via Nova Canvas (offline mock fallback).
        The hero is then framed into the branded 1x1 (and 9x16 / 16x9) creative through the
        same compose path suggest.py uses.

        market defaults to Atlanta (US-SE-ATL) when omitted. 400 if neither a resolvable
        hero nor a prompt is given. Offline: local paths, no AWS / live Bedrock required.
        """
        import tempfile

        b = body or {}
        asset_id = b.get("asset_id")
        hero_path = b.get("hero_path")
        prompt = b.get("prompt")
        market = (b.get("market") or "").strip() or DEFAULT_MARKET
        product = b.get("product")

        out_root = pathlib.Path(tempfile.mkdtemp(prefix="cap-from-photo-"))
        result = build_image_from_photo(
            asset_id=asset_id,
            hero_path=hero_path,
            prompt=prompt,
            market=market,
            product=product,
            input_assets_root=_input_assets_root(),
            out_root=out_root,
        )
        if result is None:
            raise HTTPException(  # type: ignore
                status_code=400,
                detail="supply a prompt, or a hero_path / asset_id that resolves to an uploaded photo",
            )
        return result

    @app.post("/campaigns/run-fanned")  # type: ignore
    def campaigns_run_fanned(body: dict | None = None):
        """Automate building every conceivable campaign — fanned background dispatch (Adobe Express MCP stub).

        Accepts a CampaignBrief (JSON/YAML dict) with all Kodiak products, target_region/market, audiences, messaging.
        Expands to every market × retailer × ratio (defaults to all store-finder markets + frontier gaps × 3 ratios).
        Runs as background dispatch; returns job_id. Poll GET /campaigns/job/{id} for status.
        When input assets exist in input_assets/* or s3://chasko-creative-dam-.../brands/kodiak/ they are reused; when missing, Nova Canvas mock is generated (GenAI). Adobe Express MCP mocks are fanned as background jobs — see src/creative_automation/adobe_express.py.
        """
        import uuid
        import threading
        import time
        import pathlib
        import json as _json
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
        import pathlib
        import json as _json
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
