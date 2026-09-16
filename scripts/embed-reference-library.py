#!/usr/bin/env python3
"""Background agents that run Nova multimodal embeddings for the design / reference / training library.

Each agent walks one slice, calls Nova (or mock fallback), and writes vectors ready for
S3 Vectors + Bedrock Knowledge Base. No third-party models — only
amazon.nova-2-multimodal-embeddings-v1:0 (1024 dims) with Titan fallback.

Run locally (mock when no creds, real when AWS_PROFILE=bryanchasko-kiro):
  uv run python scripts/embed-reference-library.py --all --out data/vectors
  uv run python scripts/embed-reference-library.py --design --out data/vectors
  uv run python scripts/embed-reference-library.py --images --limit 20
  AWS_PROFILE=bryanchasko-kiro uv run python scripts/embed-reference-library.py --all

Agent-friendly: exits 0 on success, writes data/vectors/kodiak-embeddings.jsonl + manifest.json.
S3 Vectors ingest (when bucket exists):
  aws s3 sync data/vectors/ s3://$DAM_S3_BUCKET/brands/kodiak/vectors/ --region us-east-1
"""
from __future__ import annotations

import argparse
import json
import pathlib

from creative_automation.embeddings import EMBED_DIM, EMBED_MODEL, embed_batch


def collect_design() -> list[dict]:
    # From design/tokens + keep-it-wild refs — token voice + color story
    items = []
    for p in pathlib.Path("design/tokens").glob("*.json"):
        txt = p.read_text(encoding="utf-8")
        items.append({"id": f"design:{p.name}", "type": "text", "text": f"Design tokens {p.name}: {txt[:8000]}"})
    for p in pathlib.Path("references/keep-it-wild").glob("*.json"):
        items.append({"id": f"ref:{p.name}", "type": "text", "text": p.read_text(encoding="utf-8")[:8000]})
    # also color story as interleaved text
    items.append({"id": "design:palette-story", "type": "text", "text": "Kodiak palette Bear Brown #3B2316 Blaze Orange #E8530E Frontier Green #1A3C34 Parchment #FFF8F0 — Wasatch dawn, brown kraft box with growling bear, Keep It Wild with Vital Ground, 14g protein 100% whole grains"})
    return items


def collect_images(limit: int | None = 20) -> list[dict]:
    import pathlib as pl
    imgs = sorted(pl.Path("data/raw-ingest/kodiakcakes/images").glob("*"))
    out = []
    for i, p in enumerate(imgs):
        if limit and i >= limit:
            break
        # interleaved: real image + caption from filename
        out.append({"id": f"image:{p.name}", "type": "image", "path": str(p), "text": p.stem.replace("_", " ").replace("-", " ")})
    return out


def collect_training() -> list[dict]:
    items = []
    for p in pathlib.Path("data/localization").glob("*.jsonl"):
        for line in p.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            j = json.loads(line)
            txt = j.get("text") or json.dumps(j)[:8000]
            items.append({"id": f"training:{j.get('metadata',{}).get('market', p.name)}", "type": "text", "text": txt})
    # also brand inventory
    if pathlib.Path("references/brand-inventory.json").exists():
        items.append({"id": "brand:inventory", "type": "text", "text": pathlib.Path("references/brand-inventory.json").read_text(encoding="utf-8")[:8000]})
    return items


def main():
    ap = argparse.ArgumentParser(description="Embed Kodiak reference library with Nova multimodal")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--design", action="store_true", help="design tokens + keep-it-wild")
    ap.add_argument("--images", action="store_true", help="raw-ingest images as multimodal")
    ap.add_argument("--training", action="store_true", help="localization training jsonl")
    ap.add_argument("--limit", type=int, default=20, help="image limit when --images")
    ap.add_argument("--out", default="data/vectors")
    ap.add_argument("--dim", type=int, default=EMBED_DIM)
    args = ap.parse_args()

    if not any([args.all, args.design, args.images, args.training]):
        args.all = True

    items: list[dict] = []
    if args.all or args.design:
        d = collect_design()
        print(f"[embed] design {len(d)} items")
        items.extend(d)
    if args.all or args.images:
        d = collect_images(limit=args.limit)
        print(f"[embed] images {len(d)} items (limit {args.limit})")
        items.extend(d)
    if args.all or args.training:
        d = collect_training()
        print(f"[embed] training {len(d)} items")
        items.extend(d)

    print(f"[embed] total {len(items)} -> model {EMBED_MODEL} dim {args.dim} out {args.out}")
    jsonl = embed_batch(items, out_dir=args.out, dim=args.dim)
    print(f"[embed] wrote {jsonl} ({jsonl.stat().st_size} bytes) manifest {pathlib.Path(args.out)/'manifest.json'}")
    print("[embed] S3 Vectors note: dedicated vector bucket, not regular S3 — see https://docs.aws.amazon.com/bedrock/latest/APIReference/API_agent_S3VectorsConfiguration.html")
    print("[embed] Next: retrieve via S3 Vectors QueryVectors or Bedrock Knowledge Base retrieve — see docs/training-process.md")


if __name__ == "__main__":
    main()
