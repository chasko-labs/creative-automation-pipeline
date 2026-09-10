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

    # each render lands on disk with the param+value encoded in the name
    for r in results:
        assert r.out_path.exists()
        assert r.out_path.name == f"control_strength-{r.value}.png"

    # sidecar written and faithful
    sidecar = tmp_path / "sweep" / "sweep-summary.json"
    assert sidecar.exists()
    payload = json.loads(sidecar.read_text())
    assert payload["param"] == "control_strength"
    assert payload["assertions"] == ["no_text", "product_recognizable"]
    assert len(payload["results"]) == 3
    assert payload["results"][2]["value"] == 0.4
    assert payload["results"][2]["verdicts"]["no_text"] is True


def test_sweep_seed_value_dispatch_and_int_coercion(monkeypatch, tmp_path: Path) -> None:
    """seed_value sweep: proves param dispatch, int coercion, per-value out_path naming.

    The frequency probe for the ROSITAR hallucination varies seed_value across many
    renders. This mocks the production invoke to capture exactly which keyword override it
    received per call and asserts seed_value (an int) arrived — no control_strength, no
    live render.
    """
    calls: list[dict] = []

    def capture_render(seed, prompt, out_path, *, control_strength=None, seed_value=None):
        calls.append(
            {
                "out_path": out_path,
                "control_strength": control_strength,
                "seed_value": seed_value,
            }
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x89PNG\r\n\x1a\n" + str(seed_value).encode())
        return out_path

    monkeypatch.setattr(generate, "_stability_control_hero", capture_render)

    # Fake judge keyed off the seed encoded in the filename: hallucination on odd seeds.
    def fake_judge(image_path: Path, question: str) -> tuple[bool, str]:
        seed_tag = int(image_path.stem.split("-")[-1])
        # "has_text" true when the signpost hallucinated (odd seeds in this fixture)
        return (seed_tag % 2 == 1, f"seed={seed_tag}")

    # pass raw strings to prove coercion happens inside the harness
    results = param_sweep.sweep_param(
        param="seed_value",
        seed=tmp_path / "hero.png",
        prompt="a product with a ROSITAR signpost risk",
        values=["1", "2", "3"],
        out_dir=tmp_path / "seedsweep",
        assertions={"has_text": "Is there a ROSITAR signpost or any text?"},
        judge=fake_judge,
    )

    # values coerced to int, in order
    assert [r.value for r in results] == [1, 2, 3]
    assert all(isinstance(r.value, int) for r in results)

    # dispatch drove seed_value (int), never control_strength
    assert [c["seed_value"] for c in calls] == [1, 2, 3]
    assert all(isinstance(c["seed_value"], int) for c in calls)
    assert all(c["control_strength"] is None for c in calls)

    # per-value out_path naming uses the param name and the int value
    for r in results:
        assert r.out_path.exists()
        assert r.out_path.name == f"seed_value-{r.value}.png"

    # verdicts follow the fixture: odd seeds hallucinate text
    verdicts_by_value = {r.value: r.verdicts for r in results}
    assert verdicts_by_value[1]["has_text"] is True
    assert verdicts_by_value[2]["has_text"] is False
    assert verdicts_by_value[3]["has_text"] is True

    # sidecar records the param name as seed_value
    payload = json.loads((tmp_path / "seedsweep" / "sweep-summary.json").read_text())
    assert payload["param"] == "seed_value"
    assert payload["assertions"] == ["has_text"]
    assert [r["value"] for r in payload["results"]] == [1, 2, 3]


def test_sweep_param_rejects_unwired_param(tmp_path: Path) -> None:
    import pytest

    with pytest.raises(ValueError, match="unsupported sweep param"):
        param_sweep.sweep_param(
            param="cfg_scale",
            seed=tmp_path / "hero.png",
            prompt="x",
            values=[1.0],
            out_dir=tmp_path / "out",
        )


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


def test_sweep_survives_raising_render(monkeypatch, tmp_path: Path, capsys) -> None:
    """A per-render RAISE must land ok=False + continue, not abort the batch.

    generate._stability_control_hero uses the rung-B fail-fast client that RE-RAISES on
    timeout/throttle by design (correct for the production ladder). In the sweep harness
    one slow response must NOT kill the queued renders: the raising value is recorded
    ok=False with the exception summary in notes, every other value still renders, the
    loop completes all M values, and the sidecar records all M results. Mocked, zero
    live renders.
    """
    boom_value = 105

    def flaky_render(seed, prompt, out_path, *, control_strength=None, seed_value=None):
        if seed_value == boom_value:
            # mirror the production re-raise: a ReadTimeoutError from the invoke.
            # botocore's ReadTimeoutError takes endpoint_url; the offline stub takes a
            # plain message. Build it the way the resolved class expects so this test is
            # honest to whatever generate resolved.
            try:
                raise generate.ReadTimeoutError(endpoint_url="bedrock", error="seed 105")
            except TypeError:
                raise generate.ReadTimeoutError("read timed out on seed 105") from None
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"\x89PNG\r\n\x1a\n" + str(seed_value).encode())
        return out_path

    monkeypatch.setattr(generate, "_stability_control_hero", flaky_render)

    def fake_judge(image_path: Path, question: str) -> tuple[bool, str]:
        return (True, f"ok {image_path.stem}")

    values = [104, 105, 106]
    results = param_sweep.sweep_param(
        param="seed_value",
        seed=tmp_path / "hero.png",
        prompt="a product with a ROSITAR signpost risk",
        values=values,
        out_dir=tmp_path / "seedsweep",
        assertions={"has_text": "Any text?"},
        judge=fake_judge,
    )

    # loop completed all M values
    assert [r.value for r in results] == values

    by_value = {r.value: r for r in results}

    # the raising value landed ok=False with the exception summary in notes
    assert by_value[105].ok is False
    assert by_value[105].verdicts == {}
    assert "ReadTimeoutError" in by_value[105].notes
    # not the generic None note — this was a raise, not a None return
    assert "render returned None" not in by_value[105].notes
    assert by_value[105].notes.startswith("render raised ")

    # the other values still rendered and were judged
    assert by_value[104].ok is True
    assert by_value[106].ok is True
    assert by_value[104].verdicts == {"has_text": True}
    assert by_value[106].verdicts == {"has_text": True}

    # tally line printed: 2/3 renders ok
    out = capsys.readouterr().out
    assert "2/3 renders ok" in out

    # sidecar recorded all M results even though one failed
    payload = json.loads((tmp_path / "seedsweep" / "sweep-summary.json").read_text())
    assert len(payload["results"]) == 3
    assert [r["value"] for r in payload["results"]] == values
    failed = next(r for r in payload["results"] if r["value"] == 105)
    assert failed["ok"] is False
    assert "ReadTimeoutError" in failed["notes"]


def test_sweep_survives_plain_exception(monkeypatch, tmp_path: Path) -> None:
    """A non-botocore RuntimeError from the invoke is caught too (broad catch-all)."""

    def flaky_render(seed, prompt, out_path, *, control_strength=None, seed_value=None):
        if seed_value == 2:
            raise RuntimeError("unexpected blowup")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"stub")
        return out_path

    monkeypatch.setattr(generate, "_stability_control_hero", flaky_render)

    results = param_sweep.sweep_param(
        param="seed_value",
        seed=tmp_path / "hero.png",
        prompt="x",
        values=[1, 2, 3],
        out_dir=tmp_path / "out",
        judge=lambda p, q: (True, "ok"),
    )

    by_value = {r.value: r for r in results}
    assert [r.value for r in results] == [1, 2, 3]
    assert by_value[1].ok is True
    assert by_value[3].ok is True
    assert by_value[2].ok is False
    assert "RuntimeError" in by_value[2].notes
    assert "unexpected blowup" in by_value[2].notes


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


def test_cli_seed_value_parses_int_values(monkeypatch, tmp_path: Path) -> None:
    """CLI --param seed_value must parse --values as int and dispatch seed_value."""
    calls: list[dict] = []

    def capture_render(seed, prompt, out_path, *, control_strength=None, seed_value=None):
        calls.append({"seed_value": seed_value, "control_strength": control_strength})
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(b"stub")
        return out_path

    monkeypatch.setattr(generate, "_stability_control_hero", capture_render)
    monkeypatch.setattr(
        param_sweep, "default_not_nova_act_judge", lambda p, q: (False, "stub")
    )
    seed = tmp_path / "hero.png"
    seed.write_bytes(b"stub")
    rc = param_sweep.main(
        [
            "--seed",
            str(seed),
            "--prompt",
            "x",
            "--param",
            "seed_value",
            "--values",
            "1,2,3",
            "--out",
            str(tmp_path / "out"),
            "--assert",
            "has_text=Any text?",
        ]
    )
    assert rc == 0
    assert [c["seed_value"] for c in calls] == [1, 2, 3]
    assert all(isinstance(c["seed_value"], int) for c in calls)
    assert all(c["control_strength"] is None for c in calls)


def test_cli_seed_value_rejects_float(monkeypatch, tmp_path: Path) -> None:
    """--values 0.5 with --param seed_value must error (int coercion fails cleanly)."""
    import pytest

    seed = tmp_path / "hero.png"
    seed.write_bytes(b"stub")
    with pytest.raises(SystemExit, match="must be a comma list of int"):
        param_sweep.main(
            [
                "--seed",
                str(seed),
                "--prompt",
                "x",
                "--param",
                "seed_value",
                "--values",
                "0.5",
                "--out",
                str(tmp_path / "out"),
            ]
        )
