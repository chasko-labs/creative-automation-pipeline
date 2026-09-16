"""Resumable LOCAL-ComfyUI batch worker for the recipe-art gap backlog.

Frozen recipe (docs/local-comfyui-recipe-art.md, approved 2026-09-14/15):
  checkpoint sd_xl_base_1.0.safetensors, euler, 25 steps, cfg 7.0,
  scheduler normal, denoise 1.0, POS_MONO tail + NEG_MONO_STRONG tail.

Cost control: LOCAL ComfyUI only (http://127.0.0.1:8188). No Bedrock calls.

GPU sharing (MANDATORY): the fc-pool valkey on port 16379 holds `gpu_lock`.
  The lock is acquired per-render and released between renders; a best-effort
  POST /free unloads models so fc-pool burst work always wins. Never hold
  the GPU continuously.

Resume: state lives in output/recipe-art-batch-queue.json
  ({key: {subject, zone, seed, status, attempts, path}}). Re-running the
  script continues from the first non-done item. Safe to kill and restart.

Finished renders are written straight into output/recipe-art/<slug>/<zone>.png
  — the same layout generate_recipe_art uses — so the existing emit path
  (recipe_cards_emit.seed_recipe_art) picks them up with no changes.

Usage:
  python scripts/recipe_art_local_batch.py --build-queue   # (re)build queue
  python scripts/recipe_art_local_batch.py                 # render loop
"""
from __future__ import annotations

import hashlib
import json
import os
import socket
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))
from creative_automation.recipe_art import (
    _COVERAGE_CEILING,
    _NEGATIVE_STRONG,
    _ZONE_PROMPT,
    _dark_coverage,
    _subject_class_clause,
    art_slug_candidates,
    slugify,
)

COMFY = "http://127.0.0.1:8188"
# Port 16379 is normally an SSM tunnel to the shared valkey; when that tunnel
# goes stale (accepts TCP, never answers) the lock acquire blackholes. A local
# lock server on 6379 (same default fc-pool uses) keeps the batch moving; set
# VALKEY_PORT=16379 to go back to the tunnel once it is healthy.
VALKEY_HOST, VALKEY_PORT = "127.0.0.1", int(os.environ.get("VALKEY_PORT", "16379"))
GPU_LOCK_KEY = "gpu_lock"
QUEUE_PATH = ROOT / "output" / "recipe-art-batch-queue.json"
OUT_ROOT = ROOT / "output" / "recipe-art"

CKPT = "sd_xl_base_1.0.safetensors"
STEPS, CFG, SAMPLER, SCHEDULER = 25, 7.0, "euler", "normal"
POS_MONO = (
    ", pure black ink outlines only, absolutely no color, no fill, no shading, "
    "stark white background, coloring book outline style, flat white fills, "
    "no yellow tint anywhere"
)
ZONE_SIZE = {
    "raw_ingredient": (1344, 768),
    "technique": (1344, 768),
    "finished_plate": (1344, 896),
}
# The one shipped-DAM gap: emitted cards reference this subject, no art exists.
KNOWN_RAW_GAP = "Waialua coffee (harvest) and papaya"


def _seed(slug: str, zone: str) -> int:
    d = hashlib.sha256(f"{slug}/{zone}".encode()).hexdigest()
    return int(d, 16) % 2147483646


def build_queue() -> dict:
    subjects = sorted(p.name for p in OUT_ROOT.iterdir() if p.is_dir())
    subjects += [slugify(KNOWN_RAW_GAP)]
    q: dict = {}
    for subj_dir in subjects:
        for zone in ("raw_ingredient", "technique", "finished_plate"):
            key = f"{subj_dir}/{zone}"
            if (OUT_ROOT / subj_dir / f"{zone}.png").exists():
                q[key] = {"subject": subj_dir, "zone": zone, "status": "done"}
            else:
                disp = KNOWN_RAW_GAP if subj_dir == slugify(KNOWN_RAW_GAP) else subj_dir
                q[key] = {
                    "subject": subj_dir,
                    "display": disp,
                    "zone": zone,
                    "seed": _seed(subj_dir, zone),
                    "status": "pending",
                    "attempts": 0,
                }
    QUEUE_PATH.write_text(json.dumps(q, indent=1))
    return q


def _valkey(*args: str) -> str:
    cmd = f"*{len(args)}\r\n" + "".join(
        f"${len(a)}\r\n{a}\r\n" for a in args
    )
    s = socket.create_connection((VALKEY_HOST, VALKEY_PORT), timeout=5)
    s.settimeout(10)  # a stale tunnel answers TCP but never RESP; fail loud
    try:
        s.sendall(cmd.encode())
        return s.recv(4096).decode()
    finally:
        s.close()


def gpu_acquire(wait_s: int = 600) -> None:
    deadline = time.time() + wait_s
    while time.time() < deadline:
        if _valkey("SET", GPU_LOCK_KEY, "recipe-art", "NX", "EX", "600").startswith(
            "+OK"
        ):
            return
        time.sleep(10)
    raise RuntimeError("gpu_lock not acquired within wait window")


def gpu_release() -> None:
    try:
        _valkey("DEL", GPU_LOCK_KEY)
    except OSError:
        pass


def _api(path: str, payload=None, timeout: int = 900):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        COMFY + path, data=data, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        raw = r.read()
    return json.loads(raw) if raw else None


def _workflow(subject: str, zone: str, seed: int) -> dict:
    w, h = ZONE_SIZE[zone]
    class_clause = _subject_class_clause(subject) if zone == "raw_ingredient" else ""
    pos = _ZONE_PROMPT[zone].format(subject=subject) + class_clause + POS_MONO
    neg = _NEGATIVE_STRONG
    return {
        "1": {"inputs": {"ckpt_name": CKPT}, "class_type": "CheckpointLoaderSimple"},
        "2": {"inputs": {"text": pos, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "3": {"inputs": {"text": neg, "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "4": {
            "inputs": {"width": w, "height": h, "batch_size": 1},
            "class_type": "EmptyLatentImage",
        },
        "5": {
            "inputs": {
                "seed": seed,
                "steps": STEPS,
                "cfg": CFG,
                "sampler_name": SAMPLER,
                "scheduler": SCHEDULER,
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
            "class_type": "KSampler",
        },
        "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]},
              "class_type": "VAEDecode"},
        "7": {"inputs": {"images": ["6", 0],
                         "filename_prefix": f"batch-{slugify(subject)}-{zone}"},
              "class_type": "SaveImage"},
    }


def render_one(item: dict) -> Path:
    import io as _io

    from PIL import Image

    pid = _api("/prompt", {"prompt": _workflow(item["display"], item["zone"],
                                                item["seed"] + item["attempts"])})["prompt_id"]
    while True:
        hist = _api(f"/history/{pid}", timeout=60)
        if pid in hist:
            break
        time.sleep(15)
    info = hist[pid]["outputs"]["7"]["images"][0]
    url = (f"{COMFY}/view?filename={info['filename']}"
           f"&subfolder={info['subfolder']}&type={info['type']}")
    with urllib.request.urlopen(url, timeout=300) as r:
        img = Image.open(_io.BytesIO(r.read())).convert("RGB")
    if _dark_coverage(img) > _COVERAGE_CEILING:
        raise ValueError(f"coverage gate rejected {item['subject']}/{item['zone']}")
    slug = art_slug_candidates(item["display"])[0]
    out = OUT_ROOT / slug / f"{item['zone']}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "PNG")
    return out


def main() -> None:
    if "--build-queue" in sys.argv:
        q = build_queue()
        pend = sum(1 for v in q.values() if v.get("status") == "pending")
        print(f"queue: {len(q)} items, {pend} pending -> {QUEUE_PATH}")
        return
    q = json.loads(QUEUE_PATH.read_text())
    for key, item in q.items():
        if item.get("status") == "done":
            continue
        item.setdefault("seed", _seed(item["subject"], item["zone"]))
        item.setdefault("display", item["subject"])
        item.setdefault("attempts", 0)
        try:
            gpu_acquire()
            try:
                out = render_one(item)
            finally:
                try:
                    _api("/free", {}, timeout=60)
                except Exception as e:  # noqa: BLE001 — best-effort GPU free probe; release follows regardless
                    print(f"[{key}] ComfyUI /free probe skipped: {e}", flush=True)
                gpu_release()
        except Exception as e:  # noqa: BLE001 — record and continue to next item
            item["attempts"] = item.get("attempts", 0) + 1
            item["status"] = f"failed: {e}"
            print(f"[{key}] FAILED ({item['status']})", flush=True)
        else:
            item["status"] = "done"
            item["path"] = str(out)
            print(f"[{key}] done -> {out}", flush=True)
        QUEUE_PATH.write_text(json.dumps(q, indent=1))


if __name__ == "__main__":
    main()
