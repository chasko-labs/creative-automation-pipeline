#!/usr/bin/env python3
"""Run a ComfyUI ink-plate batch sequentially with household courtesy.

Usage: python scripts/comfy_batch.py <items.json> <manifest-out.json>
       [--batch LABEL] [--skip-existing]

items.json: [{slug, seed, subject}] — subjects in batch A/B craft (counts +
geometry, ending "<ingredient> as the hero ingredient").
Manifest envelope mirrors batches A/B: {batch, stylePrefix, generated,
failed, items:[manifest lines]}.

Courtesy: waits (up to 30 min per item) while the shared queue is busy,
15s breather between renders for GPU cooldown. --skip-existing resumes an
interrupted batch: slugs already marked rendered in an existing manifest-out
are skipped.
"""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

COMFY = "http://127.0.0.1:8188"
ROOT = Path(__file__).resolve().parent.parent
DRIVER = ROOT / "scripts" / "comfy_ink_plate.py"
STYLE_PREFIX = (
    "black ink illustration on a plain white background, frontier ink style, "
    "hand-drawn linework with dense crosshatching, stipple dots and fine "
    "parallel shading, shapes and counts only, faces left white with one "
    "small white highlight gap per piece, single hero ingredient study "
    "centered with wide spacing, no plate, no fork, no hand"
)


def queue_busy() -> bool:
    try:
        with urllib.request.urlopen(f"{COMFY}/queue", timeout=15) as r:
            q = json.loads(r.read())
        return bool(q.get("queue_running") or q.get("queue_pending"))
    except Exception:
        return True


def wait_for_idle(item: str) -> None:
    for _ in range(180):
        if not queue_busy():
            return
        print(f"[{item}] queue busy, waiting…", flush=True)
        time.sleep(10)
    raise SystemExit(f"[{item}] queue stayed busy 30min, aborting batch")


def main() -> int:
    args = sys.argv[1:]
    if len(args) < 2:
        print("usage: comfy_batch.py <items.json> <manifest-out.json> [--batch L] [--skip-existing]")
        return 2
    items = json.loads(Path(args[0]).read_text())
    manifest_out = Path(args[1])
    label = "batch"
    if "--batch" in args:
        label = args[args.index("--batch") + 1]
    skip = "--skip-existing" in args

    done: dict[str, dict] = {}
    if skip and manifest_out.exists():
        try:
            for it in json.loads(manifest_out.read_text()).get("items", []):
                if it.get("status") == "rendered":
                    done[it["slug"]] = it
        except Exception:
            pass

    results: list[dict] = list(done.values())
    failed = 0
    for it in items:
        if it["slug"] in done:
            print(f"[{it['slug']}] skipping (already rendered)", flush=True)
            continue
        wait_for_idle(it["slug"])
        print(f"[{it['slug']}] rendering seed {it['seed']}…", flush=True)
        try:
            proc = subprocess.run(
                ["python", str(DRIVER), it["slug"], str(it["seed"]), it["subject"]],
                capture_output=True,
                text=True,
                timeout=900,
            )
            line = next(
                (ln for ln in proc.stdout.splitlines() if ln.startswith("{")),
                "",
            )
            if proc.returncode == 0 and line:
                results.append(json.loads(line))
                print(f"[{it['slug']}] done", flush=True)
            else:
                failed += 1
                print(f"[{it['slug']}] FAILED: {proc.stderr[-500:]}", flush=True)
        except Exception as e:  # noqa: BLE001 — one bad item never sinks the batch
            failed += 1
            print(f"[{it['slug']}] FAILED: {e}", flush=True)
        manifest_out.write_text(
            json.dumps(
                {
                    "batch": label,
                    "stylePrefix": STYLE_PREFIX,
                    "generated": len(results),
                    "failed": failed,
                    "items": results,
                },
                indent=1,
            )
        )
        time.sleep(15)
    print(f"batch done: {len(results)} rendered, {failed} failed", flush=True)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
