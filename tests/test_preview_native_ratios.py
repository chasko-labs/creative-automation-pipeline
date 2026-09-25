"""Native-ratio diffusion pass — each campaign tile gets its own composition.

Covers _stability_native_ratio (frames the resolved seed photo to the ratio's
own dims, then runs the rung-B restyle; unknown ratio / unreadable seed / failed
invoke degrade to None, never raise), _preview_native_tiles (four parallel
compositions land; thin clock and rung-off skip with honest books; a dead worker
never kills the set), and the generate_hero seed_local stash the pass reads.
All Bedrock calls are monkeypatched — nothing hits AWS.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from creative_automation import generate
from creative_automation import generate_lambda


def _png_bytes(size: tuple[int, int] = (1080, 1080), color=(180, 90, 30)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def _make_seed(path: Path, size: tuple[int, int] = (1200, 900)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_png_bytes(size))
    return path


# --------------------------------------------- _stability_native_ratio
def test_native_ratio_frames_seed_to_ratio_dims(tmp_path: Path, monkeypatch) -> None:
    seed = _make_seed(tmp_path / "seed.png")
    seen: dict = {}

    def _fake_control(seed_path, prompt, out_path, **kwargs):
        seen["seed_size"] = Image.open(seed_path).size
        seen["kwargs"] = kwargs
        Path(out_path).write_bytes(_png_bytes(seen["seed_size"], color=(10, 200, 120)))
        return Path(out_path)

    monkeypatch.setattr(generate, "_stability_control_hero", _fake_control)
    dest = tmp_path / "tile-9x16.png"
    got = generate._stability_native_ratio(
        seed, "spooky cats", "9x16", dest, seed_value=7, control_strength=0.4
    )
    assert got is not None and Path(got).exists()
    assert Image.open(got).size == (1080, 1920)
    assert seen["seed_size"] == (1080, 1920)
    assert seen["kwargs"]["seed_value"] == 7


def test_native_ratio_unknown_slug_and_missing_seed_are_none(
    tmp_path: Path, monkeypatch
) -> None:
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(
        generate,
        "_stability_control_hero",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not invoke")),
    )
    assert generate._stability_native_ratio(seed, "x", "nope", tmp_path / "o.png") is None
    assert (
        generate._stability_native_ratio(tmp_path / "gone.png", "x", "1x1", tmp_path / "o.png")
        is None
    )


def test_native_ratio_failed_invoke_is_none(tmp_path: Path, monkeypatch) -> None:
    seed = _make_seed(tmp_path / "seed.png")
    monkeypatch.setattr(generate, "_stability_control_hero", lambda *a, **k: None)
    assert generate._stability_native_ratio(seed, "x", "4x5", tmp_path / "o.png") is None


# --------------------------------------------- _preview_native_tiles
def _prov() -> dict:
    return {}


def test_native_tiles_land_all_four_in_parallel(tmp_path: Path, monkeypatch) -> None:
    calls: list = []

    def _fake_native(seed_local, scene, ratio, dest, **kwargs):
        calls.append((ratio, kwargs.get("seed_value")))
        Path(dest).write_bytes(_png_bytes(generate._NATIVE_RATIO_DIMS[ratio]))
        return Path(dest)

    monkeypatch.setattr(generate_lambda, "_stability_native_ratio", _fake_native)
    monkeypatch.setattr(generate_lambda, "_STABILITY_RUNG_ON", True)
    prov = _prov()
    landed = generate_lambda._preview_native_tiles(
        "/tmp/seed.png",
        "spooky cats",
        tmp_path,
        seed_base=100,
        control_strength=0.4,
        remaining_ms_fn=lambda: 60000.0,
        provenance=prov,
    )
    assert set(landed) == {"4x5", "9x16", "16x9", "blog"}
    for ratio, path in landed.items():
        assert Image.open(path).size == generate._NATIVE_RATIO_DIMS[ratio]
    assert [c[0] for c in calls].__class__ is list and len(calls) == 4
    assert len({c[1] for c in calls}) == 4  # stepped per-ratio seeds
    assert prov["native_degraded"] == {}


def test_native_tiles_skip_on_thin_clock_and_rung_off(tmp_path: Path, monkeypatch) -> None:
    def _boom(*a, **k):
        raise AssertionError("must not invoke")

    monkeypatch.setattr(generate_lambda, "_stability_native_ratio", _boom)
    monkeypatch.setattr(generate_lambda, "_STABILITY_RUNG_ON", True)
    prov = _prov()
    assert (
        generate_lambda._preview_native_tiles(
            "/tmp/seed.png", "s", tmp_path, seed_base=None,
            control_strength=None, remaining_ms_fn=lambda: 100.0, provenance=prov,
        )
        == {}
    )
    assert set(prov["native_degraded"]) == {"4x5", "9x16", "16x9", "blog"}

    monkeypatch.setattr(generate_lambda, "_STABILITY_RUNG_ON", False)
    prov2 = _prov()
    assert (
        generate_lambda._preview_native_tiles(
            "/tmp/seed.png", "s", tmp_path, seed_base=None,
            control_strength=None, remaining_ms_fn=lambda: 60000.0, provenance=prov2,
        )
        == {}
    )
    assert set(prov2["native_degraded"]) == {"4x5", "9x16", "16x9", "blog"}


def test_native_tiles_dead_worker_lands_the_rest(tmp_path: Path, monkeypatch) -> None:
    def _flake(seed_local, scene, ratio, dest, **kwargs):
        if ratio == "16x9":
            raise RuntimeError("bedrock hiccup")
        Path(dest).write_bytes(_png_bytes(generate._NATIVE_RATIO_DIMS[ratio]))
        return Path(dest)

    monkeypatch.setattr(generate_lambda, "_stability_native_ratio", _flake)
    monkeypatch.setattr(generate_lambda, "_STABILITY_RUNG_ON", True)
    prov = _prov()
    landed = generate_lambda._preview_native_tiles(
        "/tmp/seed.png", "s", tmp_path, seed_base=None,
        control_strength=None, remaining_ms_fn=lambda: 60000.0, provenance=prov,
    )
    assert set(landed) == {"4x5", "9x16", "blog"}
    assert prov["native_degraded"]["16x9"].startswith("native-error")


# --------------------------------------------- seed_local stash
def test_generate_hero_stashes_seed_local(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("KODIAK_DETERMINISTIC", "1")
    seed = _make_seed(tmp_path / "seed.png")
    canned = base64.b64encode(_png_bytes(color=(10, 200, 120))).decode("ascii")

    class _Fake:
        def invoke_model(self, **kwargs):
            payload = json.dumps({"images": [canned]}).encode("utf-8")
            return {"body": io.BytesIO(payload)}

        def converse(self, **kwargs):
            return {"output": {"message": {"content": [{"text": "Keep It Wild"}]}}}

    monkeypatch.setattr(generate, "_resolve_theme_photo", lambda slug: None)
    monkeypatch.setattr(generate, "_resolve_asset_photo", lambda pid: None)
    monkeypatch.setattr(generate, "_find_source_asset", lambda pid, name: seed)
    monkeypatch.setattr(generate.boto3, "client", lambda *a, **k: _Fake())

    _result, _source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings on the frontier",
        region="us",
        audience="active families",
        out_path=tmp_path / "hero.png",
        ratio="1x1",
        layers={},
        market="us",
        season="October",
    )
    assert prov.get("seed_local") == str(seed)
