#!/usr/bin/env python3
"""Existence gate: never generate art for a covered subject.

Usage: python scripts/check-ingredient-art.py "sweet corn" [--s3-pool]
Prints SKIP:<location> when the subject is already covered, else GO.
Checks, in order:
  1. input_assets/sprint2-ingredients/<slug>.png (this program's plates)
  2. input_assets product dirs (committed heroes)
  3. data/products/sku-photo-map.json handles
  4. S3 pilot pool s3://kodiak-dev-bryanchasko-com/poc/comfy/ (--s3-pool, needs creds)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from creative_automation.recipe_art import art_slug_candidates  # noqa: E402

SPRINT2 = ROOT / "input_assets" / "sprint2-ingredients"
SKU_MAP = ROOT / "data" / "products" / "sku-photo-map.json"
POOL_BUCKET = "kodiak-dev-bryanchasko-com"
POOL_PREFIX = "poc/comfy/"


def check(subject: str, s3_pool: bool = False) -> str:
    slugs = art_slug_candidates(subject)
    for slug in slugs:
        p = SPRINT2 / f"{slug}.png"
        if p.exists():
            return f"SKIP:sprint2-plates/{slug}.png"
    if SKU_MAP.exists():
        handles = json.loads(SKU_MAP.read_text())
        names = handles if isinstance(handles, list) else list(handles.keys())
        lowered = " ".join(names).lower()
        for slug in slugs:
            if slug.replace("-", " ") in lowered or slug.replace("-", "") in lowered.replace(" ", ""):
                return f"SKIP:sku-photo-map:{slug}"
    for slug in slugs:
        hits = sorted((ROOT / "input_assets").glob(f"*/{slug}.png"))
        hits = [h for h in hits if "sprint2" not in h.parts]
        if hits:
            return f"SKIP:{hits[0].relative_to(ROOT)}"
    if s3_pool:
        import boto3

        s3 = boto3.client("s3")
        token = None
        while True:
            kw = {"Bucket": POOL_BUCKET, "Prefix": POOL_PREFIX}
            if token:
                kw["ContinuationToken"] = token
            resp = s3.list_objects_v2(**kw)
            for obj in resp.get("Contents", []):
                stem = obj["Key"].rsplit("/", 1)[-1].lower()
                for slug in slugs:
                    if slug in stem or slug.replace("-", "") in stem.replace("-", ""):
                        return f"SKIP:s3-pool:{obj['Key']}"
            token = resp.get("NextContinuationToken")
            if not token:
                break
    return "GO"


if __name__ == "__main__":
    subject = sys.argv[1] if len(sys.argv) > 1 else ""
    if not subject:
        print("usage: check-ingredient-art.py <subject> [--s3-pool]")
        sys.exit(2)
    print(check(subject, s3_pool="--s3-pool" in sys.argv))
