#!/usr/bin/env python3
"""Queue one frontier ink ingredient render on local ComfyUI (SDXL base 1.0).

Usage: python scripts/comfy_ink_ingredient.py <slug> <seed> <subject> [--taxon TAXON]
       [--ingredient NAME] [--prefix PREFIX]
Writes the finished PNG into input_assets/sprint2-ingredients/<slug>.png
(the pool), never /tmp. Prints one JSON manifest line for the batch manifest.
Graph template: comfyui-workflows/kodiak-ink-ingredient-base.json (7 nodes).
Node 3 (negative) is LOCKED by the template — only nodes 2/5/7 are filled.

Queue etiquette (shared box, docs/gpu-sharing-protocol.md): refuses when the
queue is busy, /tmp/comfy_pause is present, the shared valkey gpu_lock is
held, or free VRAM is under 2GB, so other residents' loads are never evicted
and the GPU is never crammed. Pass --force to override the queue check only
(never the lock, the pause file, or VRAM). Never sets the lock.

Subject style (matches batches A/B): counts + geometry + white-face notes,
ending "<ingredient> as the hero ingredient".
RULE: the scientific (binomial) name is the primary identifier and leads the
prompt (--taxon, e.g. "Cucurbita pepo"), linked back to the common ingredient
/ recipe name. Never use a place or farm name as the subject: the model knows
species, not locations. One species per ingredient, no compounds: two species
in one prompt renders mutants, not reusable assets.
"""

import json
import socket
import sys
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
VALKEY_HOST = "127.0.0.1"
VALKEY_PORT = 16379
LOCK_KEY = "gpu_lock"  # exact fc-pool key, shared per docs/gpu-sharing-protocol.md
PAUSE_FILE = Path("/tmp/comfy_pause")
ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "input_assets" / "sprint2-ingredients"
WORKFLOW = ROOT / "comfyui-workflows" / "kodiak-ink-ingredient-base.json"
# SDXL weights stay resident in the server; a render's working set fits in ~2GB.
# Housemate inference servers (not trainers) share this box, so allocation
# pressure fails our own job first rather than evicting theirs.
MIN_FREE_VRAM = 2 * 1024**3

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


def lock_holder() -> str | None:
    """Owner of the shared gpu_lock, or None when free/unreachable.

    Raw-socket RESP so the driver needs no client lib. An unreachable
    valkey warns (courtesy best-effort); the queue + VRAM gates below
    still hold.
    """
    try:
        s = socket.create_connection((VALKEY_HOST, VALKEY_PORT), timeout=10)
        with s:
            s.sendall(f"GET {LOCK_KEY}\r\n".encode())
            raw = s.recv(4096)
    except OSError as e:
        print(f"warning: valkey unreachable ({e}); lock check best-effort", flush=True)
        return None
    if raw.startswith(b"$-1") or raw.startswith(b"*-0"):
        return None
    return raw.decode("utf-8", "replace").strip()


def check_box(force: bool) -> None:
    if PAUSE_FILE.exists():
        raise SystemExit("refusing: /tmp/comfy_pause is present (holder asked us to wait)")
    holder = lock_holder()
    if holder is not None:
        raise SystemExit(f"refusing: gpu_lock held by {holder!r} (never set it, never stomp it)")
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
        raise SystemExit("usage: comfy_ink_ingredient.py <slug> <seed> <subject> [--prefix P]")
    slug, seed, subject = args[0], int(args[1]), args[2].strip()
    prefix = "kodiak-ink-ingredient"
    if "--prefix" in args:
        prefix = args[args.index("--prefix") + 1]
    taxon = ""
    if "--taxon" in args:
        taxon = args[args.index("--taxon") + 1].strip()
    ingredient = ""
    if "--ingredient" in args:
        ingredient = args[args.index("--ingredient") + 1].strip()

    check_box(force)
    wf = json.loads(WORKFLOW.read_text())
    # Taxon leads: the model knows species, not places or farm names.
    positive = f"{STYLE_PREFIX}, {taxon}, {subject}" if taxon else f"{STYLE_PREFIX}, {subject}"
    wf["2"]["inputs"]["text"] = positive
    wf["5"]["inputs"]["seed"] = seed
    # Server-side output carries the slug: kodiak-ink-ingredient-<slug>_00001_.png,
    # never a bare counter name.
    wf["7"]["inputs"]["filename_prefix"] = f"{prefix}-{slug}"
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
                "ingredient": ingredient or subject.split(",")[0].strip(),
                "taxon": taxon,
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
