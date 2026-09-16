"""Cut white backgrounds from recipe-art PNGs (transparent card-ready versions).

Reads output/recipe-art/<slug>/<zone>.png, writes transparent PNGs back over
the same paths (white-bg originals are superseded — the card and print standard
wants drawings sitting naturally on the paper tone, no white boxes).

Usage:
  .venv/bin/python scripts/cutout_recipe_art.py winter-squash
  .venv/bin/python scripts/cutout_recipe_art.py --all   # whole local tree

Requires: rembg + onnxruntime in .venv (pip install rembg onnxruntime).
GPU sharing: rembg runs on CPU (onnxruntime, no CUDA provider installed), so
no gpu_lock is needed — safe to run any time, including beside ComfyUI work.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
OUT_ROOT = ROOT / "output" / "recipe-art"
ALPHA_GAMMA = 1.6  # suppress faint ghost remnants kept by the matte


def cutout(src: Path, dst: Path, session) -> None:
    from PIL import Image
    import numpy as np

    from rembg import remove

    img = Image.open(src).convert("RGB")
    out = remove(img, session=session)
    a = np.array(out.split()[3]).astype(float) / 255.0
    a = (a**ALPHA_GAMMA * 255).astype("uint8")
    out.putalpha(Image.fromarray(a))
    out.save(dst, "PNG")
    print(f"[cutout] {src.relative_to(ROOT)} -> {dst.relative_to(ROOT)}")


def main(argv: list[str]) -> int:
    from rembg import new_session

    if "--all" in argv:
        targets = sorted(OUT_ROOT.glob("*/*.png"))
    else:
        slugs = [a for a in argv if not a.startswith("-")]
        if not slugs:
            print("usage: cutout_recipe_art.py <slug>... | --all")
            return 2
        targets = [p for s in slugs for p in sorted((OUT_ROOT / s).glob("*.png"))]
    if not targets:
        print("[cutout] nothing to process")
        return 1
    session = new_session("u2net")
    for src in targets:
        try:
            cutout(src, src, session)
        except Exception as e:  # noqa: BLE001 — record and continue
            print(f"[cutout] FAILED {src}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
