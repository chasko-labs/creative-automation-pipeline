#!/usr/bin/env python3
"""Seed campaign cells on Stable Image Core: market x season x dish.

One photographic blog-scene render per cell into input_assets/campaign/.
Skips cells whose PNG already exists (existence gate). Appends one JSON
line per finished cell to the run manifest.

Usage: python scripts/seed_campaign_cells.py --cells data/seeding/matrix-oh-oc.json [--only-market US-OH-DAYTON] [--limit N]
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import os
import sys
import time
from pathlib import Path

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

ROOT = Path(__file__).resolve().parent.parent
MODEL_ID = "stability.stable-image-core-v1:1"
REGION = "us-west-2"
OUT_ROOT = ROOT / "input_assets" / "campaign"

NEGATIVE = (
    "people, human face, hands, text, signature, watermark, logo, "
    "plate, bowl, fork, spoon, table setting, dark background, 3d render"
)

MARKET_CUE = {
    "US-OH-CINCINNATI": "brick market halls of Findlay Market, Ohio River valley morning light",
    "US-OH-DAYTON": "brick downtown and market sheds, Miami Valley maple country light",
    "US-OH-LEBANON": "historic downtown and orchard rows, Warren County harvest light",
    "US-CA-OCEANSIDE": "mission-revival downtown and pier, coastal marine-layer morning light",
    "US-SE-ATL": "Georgia peach and pecan country, Southern porch light, pine skyline",
    "US-GA-SENOIA": "Coweta farm country, brick main street, peach rows and pecan groves",
    "US-MW-WASATCH": "Wasatch valley floor with crimson sumac, elk at dawn, Weber River, first frost light",
}

SEASON_ANCHOR = {
    "Fall": "harvest table with pumpkins and amber afternoon light",
    "Halloween": "pumpkins and autumn dusk glow, brand-safe, no horror",
    "Thanksgiving": "warm harvest spread, interior golden light",
    "Christmas": "evergreen sprigs and warm winter light, no santa, no ornaments text",
    "Easter": "spring blossoms and soft morning light",
    "Fourth of July": "summer berries and bright picnic daylight",
}

DISH_GEO = {
    "waffle": "one square grid waffle with deep pockets, syrup poured, blueberries",
    "muffin": "one domed blueberry muffin in a paper cup, crumb visible",
    "oatmeal-cup": "one oatmeal cup, creamy oats with berry topping",
    "brownie": "one square fudge brownie slab, dense crumb",
    "bars": "one unwrapped chewy oat bar, oats and chocolate chips visible",
}


def client():
    session = boto3.Session(
        profile_name=os.environ.get("AWS_PROFILE", "bryanchasko-kiro"),
        region_name=REGION,
    )
    return session.client(
        "bedrock-runtime",
        config=Config(
            retries={"max_attempts": 5, "mode": "adaptive"},
            connect_timeout=10,
            read_timeout=300,
        ),
    )


def prompt_for(cell: dict) -> str:
    return (
        "photorealistic food photography, {dish}, {season}, {market}, "
        "farmstand table, generous empty negative space for overlay copy, "
        "natural light, text-free frame"
    ).format(
        dish=DISH_GEO[cell["dish"]],
        season=SEASON_ANCHOR[cell["season"]],
        market=MARKET_CUE[cell["market"]],
    )


def render_one(br_client, cell: dict, out_root: Path) -> dict:
    dest = out_root / cell["market"] / f"{cell['season']}-{cell['dish']}.png".lower().replace(" ", "-")
    if dest.exists():
        return {"cell": cell, "status": "skipped-exists", "path": str(dest)}
    body = {
        "prompt": prompt_for(cell),
        "negative_prompt": NEGATIVE,
        "aspect_ratio": "16:9",
        "output_format": "png",
        "seed": cell["seed"],
    }
    try:
        resp = br_client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    except br_client.exceptions.ThrottlingException:
        time.sleep(15)
        resp = br_client.invoke_model(modelId=MODEL_ID, body=json.dumps(body))
    payload = json.loads(resp["body"].read())
    if (payload.get("finish_reasons") or [None])[0] is not None:
        return {"cell": cell, "status": "blocked",
                "reason": payload.get("finish_reasons")}
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
    img = Image.open(io.BytesIO(base64.b64decode(payload["images"][0]))).convert("RGB")
    meta = PngInfo()
    meta.add_text("prompt", prompt_for(cell))
    meta.add_text("cell", json.dumps(cell))
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, pnginfo=meta)
    return {"cell": cell, "status": "seeded", "path": str(dest)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cells", required=True)
    ap.add_argument("--only-market", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--manifest", default=None)
    args = ap.parse_args()

    try:
        cells = json.loads((ROOT / args.cells).read_text())
    except (OSError, ValueError) as e:
        print(f"cannot read cells: {e}", file=sys.stderr)
        return 2
    if args.only_market:
        cells = [c for c in cells if c["market"] == args.only_market]
    if args.limit is not None:
        cells = cells[: args.limit]

    try:
        br = client()
    except ClientError as e:
        print(f"bedrock client failed: {e}", file=sys.stderr)
        return 1

    manifest = Path(args.manifest) if args.manifest else OUT_ROOT / "run-manifest.jsonl"
    done = 0
    with manifest.open("a") as mf:
        for cell in cells:
            rec = render_one(br, cell, OUT_ROOT)
            mf.write(json.dumps(rec) + "\n")
            mf.flush()
            done += 1
            print(f"[{done}/{len(cells)}] {rec['status']} {cell['market']} {cell['season']} {cell['dish']}",
                  flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
