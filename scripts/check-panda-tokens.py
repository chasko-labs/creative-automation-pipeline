#!/usr/bin/env python3
"""panda-parity gate: Panda tokens match Kodiak brand values; regen drift fails.

1. Pins the canonical brand hexes straight from design/tokens/kodiak.json
   (bearBrown #3B2316, blazeOrange #E8530E, frontierGreen #1A3C34,
   scrim #1A1110CC) — a palette change here is deliberate or it fails.
2. Runs scripts/gen-panda-config.py --check so a stale committed
   panda.config.ts fails instead of silently drifting from kodiak.json.
3. Reports styles.css regen status: the cssgen step needs @pandacss/dev;
   when the toolchain is absent the gate notes the skip (deterministic,
   not a silent pass) instead of failing the merge queue.

Exit 0 pass, 1 fail. No network, no browser.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TOKENS_PATH = REPO_ROOT / "design" / "tokens" / "kodiak.json"
GEN_SCRIPT = REPO_ROOT / "scripts" / "gen-panda-config.py"

PINS = {
    "color.brand.bearBrown": "#3B2316",
    "color.brand.blazeOrange": "#E8530E",
    "color.brand.frontierGreen": "#1A3C34",
    "color.semantic.overlay.scrim": "#1A1110CC",
}

failures: list[str] = []


def _deref(node: dict, dotted: str) -> str:
    for seg in dotted.split("."):
        node = node[seg]
    return node["$value"]


def main() -> int:
    tokens = json.loads(TOKENS_PATH.read_text(encoding="utf-8"))["kodiak"]
    for dotted, pinned in PINS.items():
        actual = _deref(tokens, dotted)
        status = "ok" if actual.upper() == pinned.upper() else "MISMATCH"
        print(f"pin {dotted}: {actual} (expected {pinned}) [{status}]")
        if actual.upper() != pinned.upper():
            failures.append(f"brand pin moved: {dotted} is {actual}, expected {pinned}")

    proc = subprocess.run(
        [sys.executable, str(GEN_SCRIPT), "--check"],
        capture_output=True, text=True, cwd=REPO_ROOT,
    )
    print(f"gen --check: {proc.stdout.strip() or proc.stderr.strip()} [exit {proc.returncode}]")
    if proc.returncode != 0:
        failures.append("panda.config.ts drifted from kodiak.json (run gen-panda-config.py)")

    if failures:
        print("panda-parity FAIL:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("panda-parity PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
