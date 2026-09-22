#!/usr/bin/env python3
"""Queue one troop character render on local ComfyUI (SDXL base, frozen settings).

Usage:
  python scripts/troop_render.py --batch input_assets/troop-personas/batch-a.json \\
      --scout Avani --kind sheet|headshot [--out-dir input_assets/troop-renders]

Frozen: sd_xl_base_1.0, 25 steps, cfg 7.0, euler/normal, denoise 1.0.
Sheet: 768x1344 seed=sheet_seed. Headshot: 1024x1024 seed=headshot_seed.
Writes <out-dir>/<scout>-<kind>.png + .prompt.json sidecar carrying the
seed and the FULL identity paragraph verbatim (fidelity-checker gate reads it).
Graph: comfyui-workflows/character-sheet-base.json (API format, nodes 1-7).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / "comfyui-workflows" / "character-sheet-base.json"

BASE_NEGATIVE = (
    "photorealistic, 3d render, blurry, extra limbs, extra fingers, "
    "deformed face, off-model, text, signature, watermark, scenery, "
    "crowd, dark background"
)

# background-only lead: style words live in the identity paragraph, where
# per-scout medium (watercolor, halftone, ink) must win. SDXL weights early
# tokens hardest, so the background lock rides up front and repeats at the
# tail — identity in the middle.
STYLE_LEAD = "plain warm-white background with nothing else on it, no frames, no collage, "
POSE_LEAD = (
    "standing simple and upright facing the viewer, arms relaxed at her sides, "
)
SHEET_FRAMING = (
    "standing simple and upright facing the viewer, wide full body shot, "
    "entire figure visible from head to work boots, feet fully inside frame, "
    "plain warm-white background with nothing else on it, no frames, no collage"
)
SHEET_NEGATIVE_EXTRA = (
    ", sitting, seated, kneeling, crouching, leaning on rocks, leaning, "
    "perched, rocks, plants, scenery"
)
HEADSHOT_FRAMING = (
    "head and shoulders portrait, face filling the frame, eyes looking at "
    "the viewer, plain warm-white background with nothing else on it, "
    "no frames, no collage"
)


def api(path: str, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        COMFY + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read())


def get_file(path: str) -> bytes:
    with urllib.request.urlopen(COMFY + path, timeout=600) as r:
        return r.read()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--scout", required=True)
    ap.add_argument("--kind", required=True, choices=["sheet", "headshot"])
    ap.add_argument("--out-dir", default="input_assets/troop-renders")
    ap.add_argument("--seed-offset", type=int, default=0,
                    help="variant rounds: added to the blessed seed, recorded in sidecar")
    args = ap.parse_args()

    doc = json.loads(Path(args.batch).read_text())
    personas = doc if isinstance(doc, list) else doc.get("personas", doc)
    match = [p for p in personas if p["scout"].lower() == args.scout.lower()]
    if not match:
        print(f"ERROR: scout {args.scout!r} not in {args.batch}", flush=True)
        sys.exit(1)
    persona = match[0]

    base_seed = persona["sheet_seed"] if args.kind == "sheet" else persona["headshot_seed"]
    seed = base_seed + args.seed_offset
    if ("glass" not in persona["identity_paragraph"].lower()
            and "goggle" not in persona["identity_paragraph"].lower()):
        # eyewear is opt-IN per persona (e.g. Aarna's wire-rims); everyone
        # else bans it, or the model adds library glasses unprompted.
        persona = {**persona, "negative_additions": [
            *persona.get("negative_additions", []),
            "glasses, eyeglasses, spectacles, goggles, sunglasses",
        ]}
    framing = SHEET_FRAMING if args.kind == "sheet" else HEADSHOT_FRAMING
    size = (768, 1344) if args.kind == "sheet" else (1024, 1024)
    # style + background lead: SDXL weights early tokens hardest, so the
    # lock rides up front and repeats at the tail — identity in the middle.
    if args.kind == "sheet":
        positive = (
            STYLE_LEAD + POSE_LEAD + persona["identity_paragraph"].strip() + ", " + framing
        )
    else:
        positive = STYLE_LEAD + persona["identity_paragraph"].strip() + ", " + framing
    negative = BASE_NEGATIVE + "".join(
        ", " + n for n in persona.get("negative_additions", []) if not n.startswith("seed note")
    )
    if args.kind == "sheet":
        negative += SHEET_NEGATIVE_EXTRA

    wf = json.loads(WORKFLOW.read_text())
    wf["2"]["inputs"]["text"] = positive
    wf["3"]["inputs"]["text"] = negative
    wf["4"]["inputs"]["width"], wf["4"]["inputs"]["height"] = size
    wf["5"]["inputs"]["seed"] = seed
    slug = persona["scout"].lower()
    wf["7"]["inputs"]["filename_prefix"] = f"troop-{slug}-{args.kind}"

    pid = api("/prompt", {"prompt": wf})["prompt_id"]
    print(f"queued {pid} ({slug} {args.kind} seed {seed})", flush=True)
    server_file = None
    for _ in range(120):
        time.sleep(10)
        hist = api(f"/history/{pid}")
        if pid in hist:
            outs = hist[pid]["outputs"]["7"]["images"]
            server_file = outs[0]
            print(json.dumps(outs))
            break
    if server_file is None:
        print("TIMEOUT waiting for history", flush=True)
        sys.exit(1)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Never destroy an eyeballed keeper: rotate prior files aside so a bad
    # lottery roll cannot eat an approved render (or its sidecar).
    stem = f"{slug}-{args.kind}"
    for suffix in (".png", ".prompt.json"):
        cur = out_dir / f"{stem}{suffix}"
        if cur.exists():
            n = 1
            while (out_dir / f"{stem}.prev{n}{suffix}").exists():
                n += 1
            cur.rename(out_dir / f"{stem}.prev{n}{suffix}")
    png = get_file(
        f"/view?filename={server_file['filename']}"
        f"&subfolder={server_file.get('subfolder', '')}&type={server_file.get('type', 'output')}"
    )
    (out_dir / f"{stem}.png").write_bytes(png)
    sidecar = {
        "scout": persona["scout"],
        "kind": args.kind,
        "seed": seed,
        "blessed_seed": base_seed,
        "seed_offset": args.seed_offset,
        "size": list(size),
        "settings": {"checkpoint": "sd_xl_base_1.0.safetensors", "steps": 25,
                     "cfg": 7.0, "sampler": "euler", "scheduler": "normal",
                     "denoise": 1.0},
        "identity_paragraph": persona["identity_paragraph"],
        "signature_palette": persona.get("signature_palette", {}),
        "workflow": "comfyui-workflows/character-sheet-base.json",
        "comfy_prompt_id": pid,
        "comfy_output_filename": server_file["filename"],
    }
    (out_dir / f"{stem}.prompt.json").write_text(json.dumps(sidecar, indent=2))
    print(f"wrote {stem}.png + .prompt.json", flush=True)


if __name__ == "__main__":
    main()
