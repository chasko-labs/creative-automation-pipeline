"""dHash-64 B-to-C similarity gate + scene-prompt-source provenance.

No real AWS: _stability_control_hero is stubbed to write a near (pass) or far
(fail) image so the gate verdict is deterministic. Seed resolution is stubbed to
a local solid-color PNG; the director kill-switch + caption are stubbed so no
network is touched.
"""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image

from creative_automation import generate


def _png(path: Path, size=(64, 64), color=(180, 90, 30)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    path.write_bytes(buf.getvalue())
    return path


def _half_split(path: Path) -> Path:
    """Far-from-solid image: left half dark, right half bright (dHash ~32 from solid)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (64, 64))
    px = img.load()
    for y in range(64):
        for x in range(64):
            px[x, y] = (10, 10, 10) if x < 32 else (245, 245, 245)
    img.save(path, "PNG")
    return path


def _ladder_stubs(monkeypatch, seed: Path) -> None:
    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate, "_nova_pro_scene_prompt", lambda *a, **k: "wild frontier restyle")
    monkeypatch.setattr(generate, "_nova_pro_caption", lambda *a, **k: None)
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "0")


def _hero_kwargs(tmp_path: Path) -> dict:
    return dict(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="frontier breakfast",
        region="US-CO-DENVER",
        audience="families",
        out_path=tmp_path / "hero.png",
    )


# ---------------------------------------------------------------- hash primitives
def test_dhash_identical_is_zero(tmp_path: Path) -> None:
    seed = _png(tmp_path / "seed.png")
    assert generate.hamming_distance(generate.dhash64(seed), generate.dhash64(seed)) == 0


def test_dhash_far_pair_exceeds_threshold(tmp_path: Path) -> None:
    seed = _png(tmp_path / "seed.png")
    far = _half_split(tmp_path / "far.png")
    dist = generate.hamming_distance(generate.dhash64(seed), generate.dhash64(far))
    # Half-split is ~32, well above the original 8 calibration but below the
    # seasonal 64; we assert it exceeds the original 8 to prove the fixture is far,
    # not necessarily that it exceeds the current seasonal gate.
    assert dist > 8


def test_similarity_distance_none_on_unreadable(tmp_path: Path) -> None:
    seed = _png(tmp_path / "seed.png")
    assert generate._similarity_distance(seed, tmp_path / "missing.png") is None


def test_kill_switch_reads_env(monkeypatch) -> None:
    monkeypatch.setenv("KODIAK_SIMILARITY_GATE", "0")
    assert generate._similarity_gate_enabled() is False
    monkeypatch.setenv("KODIAK_SIMILARITY_GATE", "1")
    assert generate._similarity_gate_enabled() is True


# ---------------------------------------------------------------- gate verdicts
def test_gate_pass_ships_rung_b(tmp_path: Path, monkeypatch) -> None:
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)

    def _near(s, _p, o, **_k):
        return _png(o, color=(180, 90, 30))

    monkeypatch.setattr(generate, "_stability_control_hero", _near)
    _, source, prov = generate.generate_hero(**_hero_kwargs(tmp_path))
    assert source == generate.STABILITY_SOURCE
    assert prov["rung"] == "B"
    assert prov["similarity_gate"] == "pass"
    assert prov["similarity_distance"] <= prov["similarity_threshold"] == generate.SIMILARITY_GATE_THRESHOLD
    assert prov["scene_prompt_source"] == "nova"


def test_gate_fail_falls_to_rung_c(tmp_path: Path, monkeypatch) -> None:
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)
    # Force distance > current threshold so the preserve-mode gate rejects this fixture.
    monkeypatch.setattr(generate, "_similarity_distance", lambda s, c: generate.SIMILARITY_GATE_THRESHOLD + 1)
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, _prompt, out, **_ignored: _half_split(out))
    _, source, prov = generate.generate_hero(**_hero_kwargs(tmp_path))
    assert source == "bedrock:nova-pro"
    assert prov["rung"] == "C"
    assert prov["similarity_gate"] == "fail"
    assert prov["fallthrough_reason"] == "similarity-gate"
    assert prov["similarity_distance"] > generate.SIMILARITY_GATE_THRESHOLD


def test_gate_disabled_ships_drifted_b(tmp_path: Path, monkeypatch) -> None:
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)
    monkeypatch.setenv("KODIAK_SIMILARITY_GATE", "0")
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, _prompt, out, **_ignored: _half_split(out))
    _, source, prov = generate.generate_hero(**_hero_kwargs(tmp_path))
    assert source == generate.STABILITY_SOURCE
    assert prov["rung"] == "B"
    assert prov["similarity_gate"] == "disabled"


def test_gate_boundary_distance_equals_threshold_passes(tmp_path: Path, monkeypatch) -> None:
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, _prompt, out, **_ignored: _png(out))
    monkeypatch.setattr(
        generate, "_similarity_distance", lambda s, c: generate.SIMILARITY_GATE_THRESHOLD
    )
    _, source, prov = generate.generate_hero(**_hero_kwargs(tmp_path))
    assert prov["similarity_gate"] == "pass"
    assert source == generate.STABILITY_SOURCE


# ------------------------------------------------------- two-mode gate
def test_preserve_mode_rejects_calibrated_drift(tmp_path: Path, monkeypatch) -> None:
    # No season/theme: a distance-30 restyle is drift, rejected at the
    # calibrated default 8 even though diverge mode would accept it.
    assert generate.SIMILARITY_GATE_THRESHOLD == 8
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)
    monkeypatch.setattr(generate, "_similarity_distance", lambda seed, candidate: 30)
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, _prompt, out, **_ignored: _half_split(out))
    _, source, prov = generate.generate_hero(**_hero_kwargs(tmp_path))
    assert prov["similarity_mode"] == "preserve"
    assert prov["similarity_gate"] == "fail"
    assert prov["rung"] == "C"


def test_diverge_mode_accepts_far_restyle(tmp_path: Path, monkeypatch) -> None:
    # Season requested: the same distance-30 restyle is the brief, not drift.
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)
    monkeypatch.setattr(generate, "_similarity_distance", lambda seed, candidate: 30)
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, _prompt, out, **_ignored: _half_split(out))
    kwargs = _hero_kwargs(tmp_path)
    kwargs["season"] = "october"
    _, source, prov = generate.generate_hero(**kwargs)
    assert prov["similarity_mode"] == "diverge"
    assert prov["similarity_gate"] == "pass"
    assert prov["rung"] == "B"


def test_diverge_mode_retries_seed_echo(tmp_path: Path, monkeypatch) -> None:
    # Season requested but the model echoed the seed (distance 0): one retry
    # with the next seed, then accept. Sibling file keeps the first restyle.
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)

    def _echo(seed, _prompt, out, **_ignored):
        return _png(out, color=(180, 90, 30))

    monkeypatch.setattr(generate, "_stability_control_hero", _echo)
    kwargs = _hero_kwargs(tmp_path)
    kwargs["season"] = "october"
    _, source, prov = generate.generate_hero(**kwargs)
    assert prov["similarity_mode"] == "diverge"
    assert prov["similarity_gate"] == "retry-accept"
    assert prov["similarity_retry_seed"] == prov["seed"]
    assert prov["similarity_retry_distance"] is not None
    assert source == generate.STABILITY_SOURCE


# ------------------------------------------------------- scene-prompt-source
def test_scene_prompt_source_default_branch(tmp_path: Path, monkeypatch) -> None:
    seed = _png(tmp_path / "seed.png")
    _ladder_stubs(monkeypatch, seed)
    # Nova stub returns the deterministic default verbatim -> default branch.
    monkeypatch.setattr(
        generate,
        "_nova_pro_scene_prompt",
        lambda s, pn, bm, r, a, t, *e: generate._default_scene_prompt(pn, bm, r, a, t),
    )
    monkeypatch.setattr(generate, "_stability_control_hero", lambda seed, _prompt, out, **_ignored: _png(out))
    _, _, prov = generate.generate_hero(**_hero_kwargs(tmp_path))
    assert prov["scene_prompt_source"] == "default"
