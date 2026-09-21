#!/usr/bin/env python3
"""Queue one photographic blog-scene render on local ComfyUI (SDXL Turbo).

Usage: python scripts/comfy_blog_scene.py <seed> <pos_file> <neg_file> [prefix]
Writes the finished PNG into input_assets/blog/ (the pool), never /tmp.
Graph template: comfyui-workflows/kodiak-blog-scene-turbo.json (7 nodes).
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "input_assets" / "blog"
WORKFLOW = ROOT / "comfyui-workflows" / "kodiak-blog-scene-turbo.json"


def api(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        COMFY + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def main() -> None:
    seed = int(sys.argv[1])
    pos = Path(sys.argv[2]).read_text().strip()
    neg = Path(sys.argv[3]).read_text().strip()
    prefix = sys.argv[4] if len(sys.argv) > 4 else "blog-scene"
    wf = json.loads(WORKFLOW.read_text())
    wf["2"]["inputs"]["text"] = pos
    wf["3"]["inputs"]["text"] = neg
    wf["5"]["inputs"]["seed"] = seed
    wf["7"]["inputs"]["filename_prefix"] = prefix
    pid = api("/prompt", {"prompt": wf})["prompt_id"]
    print(f"queued {pid} (seed {seed})", flush=True)
    for _ in range(100):
        time.sleep(10)
        hist = api(f"/history/{pid}")
        if pid in hist:
            outs = hist[pid]["outputs"]["7"]["images"]
            print(json.dumps(outs))
            return
    print("TIMEOUT waiting for history", flush=True)
    sys.exit(1)


if __name__ == "__main__":
    main()
