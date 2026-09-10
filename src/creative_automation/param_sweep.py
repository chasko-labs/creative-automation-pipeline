"""Reusable diffusion parameter-sweep harness.

You cannot tune a diffusion parameter blind. This module renders a controlled sweep of
ONE parameter across N values against the REAL production invoke path
(generate._stability_control_hero — never a re-implementation), gets an objective
per-output read from a pluggable vision judge, and reports a comparison matrix.

First invocation: ROSITAR text-bleed (control_strength). Second: seed_value, to measure
how often a stochastic text hallucination appears across many renders. The harness is
generic — the same code serves the orange-sky gap, cfg_scale, seed choice, and future
model swaps with zero new code, because the judge is an injectable Callable, the swept
param is named at call time, and its values are coerced to the right type per param.

Public surface:
  SweepResult                 — one render + its per-assertion verdicts
  sweep_param(*, param, ...)  — drive a sweep of any wired param, return list[SweepResult]
  sweep_control_strength(...) — back-compat alias for sweep_param(param="control_strength")
  default_not_nova_act_judge  — the default judge (local qwen VQA via not-nova-act)
  main()                      — thin CLI wrapper (python -m creative_automation.param_sweep)

Wired params (SWEEP_PARAMS): each maps a --param name to the coercion applied to its
values. control_strength -> float, seed_value -> int. Adding a new sweepable param is a
one-line entry here plus a matching keyword override on _stability_control_hero.

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

# Exception set the sweep survives per-render. generate.py resolves these names either to
# real botocore classes or to its offline stub subclasses of Exception; referencing them
# through the generate module keeps this harness honest to whatever generate resolved
# rather than re-importing botocore (which may be absent in local-only mode). Any of these
# from a single _stability_control_hero call is recorded ok=False and the loop continues.
# Exception is included as the final catch-all so no invoke raise ever aborts the batch.
_INVOKE_ERRORS: tuple[type[BaseException], ...] = (
    generate.ReadTimeoutError,
    generate.ConnectTimeoutError,
    generate.ClientError,
    generate.BotoCoreError,
    Exception,
)

# Judge contract: (image_path, question) -> (verdict, detail)
Judge = Callable[[Path, str], tuple[bool, str]]

# Wired sweepable params: --param name -> value coercion. Each key must have a matching
# keyword override on generate._stability_control_hero. control_strength is a float
# guidance term; seed_value is the integer RNG seed (vary it to measure how often a
# stochastic hallucination like the ROSITAR signpost appears across renders).
SWEEP_PARAMS: dict[str, Callable[[str], object]] = {
    "control_strength": float,
    "seed_value": int,
}

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

    value: float | int
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


def sweep_param(
    *,
    param: str,
    seed: Path,
    prompt: str,
    values: list[float | int],
    out_dir: Path,
    assertions: dict[str, str] | None = None,
    judge: Judge | None = None,
) -> list[SweepResult]:
    """Sweep any wired `param` across `values` against the production invoke path.

    Per value: call generate._stability_control_hero with the override passed as the
    keyword named by `param` (**{param: value}), write to out_dir/<param>-<value>.png,
    then run each assertion through the judge. Records ok + path + per-assertion verdicts.
    Prints a matrix to stdout and writes out_dir/sweep-summary.json. Returns the list of
    SweepResult.

    `param` must be a key of SWEEP_PARAMS; each value is coerced to that param's type
    (float for control_strength, int for seed_value) before it reaches the invoke. The
    caller may pass already-typed values or raw strings — both coerce cleanly.

    assertions = {label: question}; judge is the pluggable read. Defaults to local qwen
    VQA via not-nova-act. A render that returns None is recorded ok=False and its
    assertions are skipped (nothing to judge).

    ROBUSTNESS: the production invoke (generate._stability_control_hero) uses the rung-B
    fail-fast client that RE-RAISES ReadTimeoutError/ConnectTimeoutError, throttle
    ClientError, and other BotoCoreError by design — correct for the production ladder,
    which must classify the fallthrough and drop to rung C. But the sweep's job is to
    survey many renders, so no single render may abort the batch. The invoke is wrapped:
    any raise is RECORDED as ok=False with the exception text in notes and the loop
    CONTINUES to the next value. The exception types are referenced through the generate
    module so the harness stays honest to whatever generate resolved (real botocore vs
    its offline stub classes) — plus a bare Exception catch so nothing escapes.
    """
    if param not in SWEEP_PARAMS:
        raise ValueError(
            f"unsupported sweep param {param!r}; wired params: {sorted(SWEEP_PARAMS)}"
        )
    coerce = SWEEP_PARAMS[param]
    assertions = assertions or {}
    judge = judge or default_not_nova_act_judge
    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[SweepResult] = []

    for raw in values:
        value = coerce(raw)
        out_path = out_dir / f"{param}-{value}.png"
        verdicts: dict[str, bool] = {}
        note_parts: list[str] = []
        try:
            rendered = generate._stability_control_hero(
                seed, prompt, out_path=out_path, **{param: value}
            )
        except _INVOKE_ERRORS as exc:  # noqa: BLE001 — no single render may kill the sweep
            rendered = None
            note_parts.append(f"render raised {type(exc).__name__}: {exc}")
        ok = rendered is not None
        if ok:
            for label, question in assertions.items():
                verdict, detail = judge(out_path, question)
                verdicts[label] = verdict
                note_parts.append(f"{label}: {detail}")
        elif not note_parts:
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

    ok_count = sum(1 for r in results if r.ok)
    print(f"\n{ok_count}/{len(results)} renders ok")
    _print_matrix(param, results, list(assertions))
    _write_sidecar(param, out_dir, prompt, seed, results, list(assertions))
    return results


def sweep_control_strength(
    *,
    seed: Path,
    prompt: str,
    values: list[float],
    out_dir: Path,
    assertions: dict[str, str] | None = None,
    judge: Judge | None = None,
) -> list[SweepResult]:
    """Back-compat alias: sweep_param(param="control_strength", ...).

    Kept so existing callers and the ROSITAR text-bleed workflow keep working unchanged.
    New code should call sweep_param directly and name the param.
    """
    return sweep_param(
        param="control_strength",
        seed=seed,
        prompt=prompt,
        values=list(values),
        out_dir=out_dir,
        assertions=assertions,
        judge=judge,
    )


def _print_matrix(param: str, results: list[SweepResult], labels: list[str]) -> None:
    """Print value -> ok + per-assertion verdict matrix to stdout.

    Display polarity fix: each assertion prints its raw boolean verdict as true/false,
    not a yes/no that reads like pass/fail. For an assertion phrased as a question
    (no_text = "is there text?") a verdict of false is the *good* outcome — printing the
    literal boolean keeps the matrix from being misread. The JSON sidecar carries the same
    booleans, so the display now matches the detail.
    """
    header = [param, "ok", *labels]
    rows = [header]
    for r in results:
        row = [str(r.value), "yes" if r.ok else "NO"]
        row.extend("true" if r.verdicts.get(lbl) else "false" for lbl in labels)
        rows.append(row)
    widths = [max(len(row[i]) for row in rows) for i in range(len(header))]
    print(f"\nsweep matrix ({param}); assertion cells are the raw verdict (true/false):")
    for i, row in enumerate(rows):
        line = "  ".join(cell.ljust(widths[j]) for j, cell in enumerate(row))
        print(f"  {line}")
        if i == 0:
            print(f"  {'  '.join('-' * w for w in widths)}")


def _write_sidecar(
    param: str,
    out_dir: Path,
    prompt: str,
    seed: Path,
    results: list[SweepResult],
    labels: list[str],
) -> Path:
    """Write out_dir/sweep-summary.json with the full run record."""
    sidecar = out_dir / "sweep-summary.json"
    payload = {
        "param": param,
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
        choices=sorted(SWEEP_PARAMS),
        help="parameter to sweep (control_strength=float, seed_value=int)",
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

    coerce = SWEEP_PARAMS[args.param]
    try:
        values = [coerce(v.strip()) for v in args.values.split(",") if v.strip()]
    except ValueError as exc:
        raise SystemExit(
            f"--values must be a comma list of {coerce.__name__} for --param {args.param}: {exc}"
        ) from exc

    assertions = _parse_assertions(args.assertions)

    results = sweep_param(
        param=args.param,
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
