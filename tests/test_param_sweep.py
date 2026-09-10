"""Unit tests for the param_sweep harness — matrix logic + JSON sidecar only.

No live render, no live judge. generate._stability_control_hero is mocked to write a
stub PNG, and a fake in-process judge returns scripted verdicts. This proves the sweep
wiring (per-value invoke, per-assertion judge dispatch, matrix, sidecar) without spending
a single billable Bedrock render.
"""

from __future__ import annotations

import json
from pathlib import Path

from creative_automation import generate, param_sweep


def _fake_render(seed, prompt, out_path, *, control_strength=None, seed_value=None):
    """Stand in for the production invoke: write a stub PNG, echo control_strength."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"\x89PNG\r\n\x1a\n" + str(control_strength).encode())
    return out_path


def test_sweep_matrix_and_sidecar(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(generate, "_stability_control_hero", _fake_render)

    # Fake judge: no_text passes only at the lowest strength; product always recognizable.
    def fake_judge(image_path: Path, question: str) -> tuple[bool, str]:
        value_tag = image_path.stem.split("-")[-1]
        if "text" in question.lower():
            return (float(value_tag) <= 0.4, f"text-check at cs={value_tag}")
        return (True, f"fidelity-check at cs={value_tag}")

    results = param_sweep.sweep_control_strength(
        seed=tmp_path / "hero.png",
        prompt="a product on a rustic table",
        values=[0.7, 0.55, 0.4],
        out_dir=tmp_path / "sweep",
        assertions={
            "no_text": "Is there any text or lettering in this image?",
            "product_recognizable": "Is the product clearly visible and undistorted?",
        },
        judge=fake_judge,
    )

    assert [r.value for r in results] == [0.7, 0.55, 0.4]
    assert all(r.ok for r in results)
    # no_text flips true only at 0.4
    verdicts_by_value = {r.value: r.verdicts for r in results}
    assert verdicts_by_value[0.7]["no_text"] is False
    assert verdicts_by_value[0.55]["no_text"] is False
    assert verdicts_by_value[0.4]["no_text"] is True
    assert all(v["product_recognizable"] for v in verdicts_by_value.values())

    # each render lands on disk with the value encoded in the name
    for r in results:
        assert r.out_path.exists()
        assert r.out_path.name == f"cs-{r.value}.png"

    # sidecar written and faithful
    sidecar = tmp_path / "sweep" / "sweep-summary.json"
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text())
    assert payload["param"] == "control_strength"
    assert payload["assertions"] == ["no_text", "product_recognizable"]
    assert len(payload["results"]) == 3
    assert payload["results"][2]["value"] == 0.4
    assert payload["results"][2]["verdicts"]["no_text"] is True


def test_sweep_records_failed_render(monkeypatch, tmp_path: Path) -> None:
    # production invoke returns None (Bedrock error / downgrade path)
    monkeypatch.setattr(
        generate,
        "_stability_control_hero",
        lambda s, p, out_path, *, control_strength=None, seed_value=None: None,
    )

    def never_called_judge(image_path: Path, question: str) -> tuple[bool, str]:
        raise AssertionError("judge must not run when the render failed")

    results = param_sweep.sweep_control_strength(
        seed=tmp_path / "hero.png",
        prompt="x",
        values=[0.7],
        out_dir=tmp_path / "sweep",
        assertions={"no_text": "Any text?"},
        judge=never_called_judge,
    )

    assert len(results) == 1
    assert results[0].ok is False
    assert results[0].verdicts == {}
    assert "render returned None" in results[0].notes


def test_parse_assertions() -> None:
    parsed = param_sweep._parse_assertions(["no_text=Is there any text?", "sky=Orange sky?"])
    assert parsed == {"no_text": "Is there any text?", "sky": "Orange sky?"}


def test_cli_exit_nonzero_when_all_fail(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        generate,
        "_stability_control_hero",
        lambda s, p, out_path, *, control_strength=None, seed_value=None: None,
    )
    seed = tmp_path / "hero.png"
    seed.write_bytes(b"stub")
    rc = param_sweep.main(
        [
            "--seed",
            str(seed),
            "--prompt",
            "x",
            "--values",
            "0.7",
            "--out",
            str(tmp_path / "out"),
            "--assert",
            "no_text=Any text?",
        ]
    )
    assert rc == 1
