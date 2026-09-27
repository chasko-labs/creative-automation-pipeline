#!/usr/bin/env python3
"""Queue one frontier ink-plate render on local ComfyUI (SDXL base 1.0).

Usage: python scripts/comfy_ink_plate.py <slug> <seed> <subject> [--prefix PREFIX]
Writes the finished PNG into input_assets/sprint2-ingredients/<slug>.png
(the pool), never /tmp. Prints one JSON manifest line for the batch manifest.
Graph template: comfyui-workflows/kodiak-ink-plate-base.json (7 nodes).
Node 3 (negative) is LOCKED by the template — only nodes 2/5/7 are filled.

Queue etiquette (shared box): refuses when the queue is busy or free VRAM is
under 3GB, so other residents' loads are never evicted and the GPU is never
crammed. Pass --force to override the queue check (still never overrides VRAM).

Subject style (matches batches A/B): counts + geometry + white-face notes,
ending "<ingredient> as the hero ingredient".
"""

import json
import sys
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "input_assets" / "sprint2-ingredients"
WORKFLOW = ROOT / "comfyui-workflows" / "kodiak-ink-plate-base.json"
MIN_FREE_VRAM = 3 * 1024**3

STYLE_PREFIX = (
    "black ink illustration on a plain white background, frontier ink style, "
    "hand-drawn linework with dense crosshatching, stipple dots and fine "
    "parallel shading, shapes and counts only, faces left white with one "
    "small white highlight gap per piece, single hero ingredient study "
    "centered with wide spacing, no plate, no fork, no hand"
)


def api(path, payload=None, raw=False):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        COMFY + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        body = r.read()
        return body if raw else json.loads(body)


def check_box(force: bool) -> None:
    q = api("/queue")
    if (q.get("queue_running") or q.get("queue_pending")) and not force:
        raise SystemExit("refusing: ComfyUI queue is busy (use --force to override)")
    try:
        stats = api("/system_stats")
        free = stats["devices"][0].get("vram_free", 0)
    except Exception:
        free = 0
    if free and free < MIN_FREE_VRAM:
        raise SystemExit(
            f"refusing: only {free / 1024**3:.1f}GB VRAM free "
            f"(need {MIN_FREE_VRAM / 1024**3:.0f}GB)"
        )


def main() -> None:
    args = [a for a in sys.argv[1:] if a != "--force"]
    force = "--force" in sys.argv[1:]
    if len(args) < 3:
        raise SystemExit("usage: comfy_ink_plate.py <slug> <seed> <subject> [--prefix P]")
    slug, seed, subject = args[0], int(args[1]), args[2].strip()
    prefix = "kodiak-ink-plate"
    if "--prefix" in args:
        prefix = args[args.index("--prefix") + 1]

    check_box(force)
    wf = json.loads(WORKFLOW.read_text())
    positive = f"{STYLE_PREFIX}, {subject}"
    wf["2"]["inputs"]["text"] = positive
    wf["5"]["inputs"]["seed"] = seed
    wf["7"]["inputs"]["filename_prefix"] = prefix
    negative = wf["3"]["inputs"]["text"]

    pid = api("/prompt", {"prompt": wf})["prompt_id"]
    print(f"queued {pid} (seed {seed})", flush=True)
    outs = None
    for _ in range(60):
        time.sleep(10)
        hist = api(f"/history/{pid}")
        if pid in hist:
            outs = hist[pid]["outputs"]["7"]["images"]
            break
    if not outs:
        print("TIMEOUT waiting for history", flush=True)
        sys.exit(1)
    img = outs[0]
    # /view returns bytes, not JSON: fetch raw.
    import urllib.parse

    qs = urllib.parse.urlencode(
        {
            "filename": img["filename"],
            "subfolder": img.get("subfolder", ""),
            "type": img.get("type", "output"),
        }
    )
    with urllib.request.urlopen(f"{COMFY}/view?{qs}", timeout=600) as r:
        raw = r.read()
    dest = POOL / f"{slug}.png"
    dest.write_bytes(raw)
    print(
        json.dumps(
            {
                "slug": slug,
                "ingredient": subject.split(",")[0].strip(),
                "seed": seed,
                "file": f"{slug}.png",
                "bytes": len(raw),
                "prompt": positive,
                "negative_prompt": negative,
                "status": "rendered",
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
