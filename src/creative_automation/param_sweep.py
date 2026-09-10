"""Reusable diffusion parameter-sweep harness.

You cannot tune a diffusion parameter blind. This module renders a controlled sweep of
ONE parameter across N values against the REAL production invoke path
(generate._stability_control_hero — never a re-implementation), gets an objective
per-output read from a pluggable vision judge, and reports a comparison matrix.

First invocation: ROSITAR text-bleed (control_strength). But the harness is generic —
the same code serves the orange-sky gap, cfg_scale, seed choice, and future model swaps
with zero new code, because the judge is an injectable Callable and the swept values are
just a list of floats.

Public surface:
  SweepResult                 — one render + its per-assertion verdicts
  sweep_control_strength(...) — drive the sweep, return list[SweepResult], write sidecar
  default_not_nova_act_judge  — the default judge (local qwen VQA via not-nova-act)
  main()                      — thin CLI wrapper (python -m creative_automation.param_sweep)

The judge contract:
  Callable[[Path, str], tuple[bool, str]]
  given (image_path, question) -> (verdict_bool, detail_note)
Swap it for anything (a mock in tests, a Bedrock call, an HTTP client to :8171) without
touching the sweep logic.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import generate

# Judge contract: (image_path, question) -> (verdict, detail)
Judge = Callable[[Path, str], tuple[bool, str]]

# Default judge shells the not-nova-act assert_visual path (local qwen3-vl VQA via
# ollama). NOT_NOVA_ACT_DIR points at the checkout; assert_visual reads the PNG and
# returns a TRUE/FALSE verdict with no AWS, no API key. To route through the running
# not-nova-act MCP server on :8171 instead of a fresh subprocess, inject a judge that
# posts to browser_assert_visual_tool at http://localhost:8171 — the harness does not
# care which judge it gets, only that it satisfies the Judge contract.
NOT_NOVA_ACT_DIR = os.getenv(
    "NOT_NOVA_ACT_DIR", str(Path.home() / "code" / "heraldstack" / "not-nova-act")
)


@dataclass
class SweepResult:
    """One swept value: the render it produced and the judge verdicts on it."""

    value: float
    out_path: Path
    ok: bool
    verdicts: dict[str, bool] = field(default_factory=dict)
    notes: str = ""


def default_not_nova_act_judge(image_path: Path, question: str) -> tuple[bool, str]:
    """Default judge: local qwen VQA verdict via the not-nova-act assert_visual path.

    Shells `uv run` inside the not-nova-act checkout so we reuse its exact assert_visual
    logic (qwen3-vl:8b through ollama, TRUE/FALSE + reason) without vendoring it. Returns
    (verdict, detail). On any failure returns (False, error) so the matrix records the
    miss rather than crashing the sweep.

    Point this at the live :8171 MCP server instead by injecting your own judge — see the
    module docstring. This subprocess path is the documented default because it needs no
    MCP session handshake.
    """
    snippet = (
        "import json,sys;"
        "from not_nova_act.analyze import assert_visual;"
        "print(json.dumps(assert_visual(sys.argv[1], sys.argv[2])))"
    )
    try:
        proc = subprocess.run(
            ["uv", "run", "python", "-c", snippet, str(image_path), question],
            cwd=NOT_NOVA_ACT_DIR,
            capture_output=True,
            text=True,
            timeout=320,
            check=False,
        )
        if proc.returncode != 0:
            return False, f"judge exited {proc.returncode}: {proc.stderr.strip()[:300]}"
        # assert_visual prints one JSON line; take the last non-empty stdout line.
        line = [ln for ln in proc.stdout.splitlines() if ln.strip()][-1]
        out = json.loads(line)
        if out.get("status") != "completed":
            return False, f"judge error: {out.get('error_message', out)}"
        return bool(out.get("verdict", False)), str(out.get("detail", ""))[:500]
    except Exception as exc:  # noqa: BLE001 — a broken judge must not kill the sweep
        return False, f"judge invocation failed: {exc}"


def sweep_control_strength(
    *,
    seed: Path,
    prompt: str,
    values: list[float],
    out_dir: Path,
    assertions: dict[str, str] | None = None,
    judge: Judge | None = None,
) -> list[SweepResult]:
    """Sweep control_strength across `values` against the production invoke path.

    Per value: call generate._stability_control_hero with the override control_strength,
    write to out_dir/cs-<value>.png, then run each assertion through the judge. Records
    ok + path + per-assertion verdicts. Prints a matrix to stdout and writes
    out_dir/sweep-summary.json. Returns the list of SweepResult.

    assertions = {label: question}; judge is the pluggable read. Defaults to local qwen
    VQA via not-nova-act. A render that returns None is recorded ok=False and its
    assertions are skipped (nothing to judge).
    """
    assertions = assertions or {}
    judge = judge or default_not_nova_act_judge
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[SweepResult] = []

    for value in values:
        out_path = out_dir / f"cs-{value}.png"
        rendered = generate._stability_control_hero(
            seed, prompt, out_path=out_path, control_strength=value
        )
        ok = rendered is not None
        verdicts: dict[str, bool] = {}
        note_parts: list[str] = []
        if ok:
            for label, question in assertions.items():
                verdict, detail = judge(out_path, question)
                verdicts[label] = verdict
                note_parts.append(f"{label}: {detail}")
        else:
            note_parts.append("render returned None (see stderr for the exact Bedrock error)")
        results.append(
            SweepResult(
                value=value,
                out_path=out_path,
                ok=ok,
                verdicts=verdicts,
                notes=" | ".join(note_parts),
            )
        )

    _print_matrix(results, list(assertions))
    _write_sidecar(out_dir, prompt, seed, results, list(assertions))
    return results


def _print_matrix(results: list[SweepResult], labels: list[str]) -> None:
    """Print value -> ok + per-assertion verdict matrix to stdout."""
    header = ["control_strength", "ok", *labels]
    rows = [header]
    for r in results:
        row = [str(r.value), "yes" if r.ok else "NO"]
        row.extend("yes" if r.verdicts.get(lbl) else "no" for lbl in labels)
        rows.append(row)
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    print("\nsweep matrix (control_strength):")
    for i, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row))
        print(f"  {line}")
        if i == 0:
            print(f"  {'  '.join('-' * w for w in widths)}")


def _write_sidecar(
    out_dir: Path,
    prompt: str,
    seed: Path,
    results: list[SweepResult],
    labels: list[str],
) -> Path:
    """Write out_dir/sweep-summary.json with the full run record."""
    sidecar = out_dir / "sweep-summary.json"
    payload = {
        "param": "control_strength",
        "seed": str(seed),
        "prompt": prompt,
        "assertions": labels,
        "results": [
            {**asdict(r), "out_path": str(r.out_path)} for r in results
        ],
    }
    sidecar.write_text(json.dumps(payload, indent=2))
    return sidecar


def _parse_assertions(pairs: list[str] | None) -> dict[str, str]:
    """Turn repeatable --assert label=question tokens into {label: question}."""
    out: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"--assert must be label=question, got: {pair!r}")
        label, question = pair.split("=", 1)
        out[label.strip()] = question.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    """Thin CLI wrapper. See module docstring for the judge-injection story."""
    parser = argparse.ArgumentParser(
        prog="python -m creative_automation.param_sweep",
        description="Reusable diffusion parameter-sweep harness (ROSITAR is the first use).",
    )
    parser.add_argument("--seed", required=True, type=Path, help="seed image path (hero.png)")
    parser.add_argument("--prompt", required=True, help="restyle subject prompt")
    parser.add_argument(
        "--param",
        default="control_strength",
        choices=["control_strength"],
        help="parameter to sweep (only control_strength wired today)",
    )
    parser.add_argument(
        "--values", required=True, help="comma list of values, e.g. 0.7,0.55,0.4"
    )
    parser.add_argument("--out", required=True, type=Path, help="output dir for renders")
    parser.add_argument(
        "--assert",
        dest="assertions",
        action="append",
        metavar="LABEL=QUESTION",
        help="repeatable visual assertion, e.g. no_text=\"Is there any text?\"",
    )
    args = parser.parse_args(argv)

    try:
        values = [float(v) for v in args.values.split(",") if v.strip()]
    except ValueError as exc:
        raise SystemExit(f"--values must be a comma list of floats: {exc}") from exc

    assertions = _parse_assertions(args.assertions)

    if args.param != "control_strength":  # defensive; choices already gate this
        raise SystemExit(f"unsupported --param {args.param}")

    results = sweep_control_strength(
        seed=args.seed,
        prompt=args.prompt,
        values=values,
        out_dir=args.out,
        assertions=assertions,
    )
    # Non-zero exit if every render failed — a signal for CI / callers.
    return 0 if any(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
