"""Native-ratio diffusion pass — each campaign tile gets its own composition.

Covers _stability_native_ratio (frames the resolved seed photo to the ratio's
own dims, then runs the rung-B restyle; unknown ratio / unreadable seed / failed
invoke degrade to None, never raise), the rung-B native fan-out (1x1 plus one
restyle per sibling ratio fire concurrently; a dead sibling never kills the
1x1; outcomes land honestly in provenance native_ratios), and the generate_hero
seed_local stash.
All Bedrock calls are monkeypatched — nothing hits AWS.
"""
from __future__ import annotations

import base64
import io
import json
from pathlib import Path

from PIL import Image

from creative_automation import generate


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


# --------------------------------------------- rung-B native fan-out
def _ladder_harness(monkeypatch, tmp_path: Path, seed: Path):
    monkeypatch.setenv("KODIAK_DETERMINISTIC", "1")
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


def test_fanout_composes_all_five_frames_concurrently(
    tmp_path: Path, monkeypatch
) -> None:
    seed = _make_seed(tmp_path / "seed.png")
    _ladder_harness(monkeypatch, tmp_path, seed)
    calls: list = []

    def _fake_native(seed_local, scene, ratio, dest, **kwargs):
        calls.append((ratio, kwargs.get("seed_value")))
        Path(dest).write_bytes(_png_bytes(generate._NATIVE_RATIO_DIMS[ratio]))
        return Path(dest)

    monkeypatch.setattr(generate, "_stability_native_ratio", _fake_native)
    siblings = {r: tmp_path / f"sib-{r}.png" for r in ("4x5", "9x16", "16x9", "blog")}
    out = tmp_path / "hero.png"
    _result, _source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings on the frontier",
        region="us",
        audience="active families",
        out_path=out,
        ratio="1x1",
        layers={},
        market="us",
        season="October",
        native_siblings={r: str(p) for r, p in siblings.items()},
    )
    assert out.exists()
    for ratio, path in siblings.items():
        assert path.exists(), ratio
        assert Image.open(path).size == generate._NATIVE_RATIO_DIMS[ratio]
    assert prov["native_ratios"] == {r: "stability-restyle-native" for r in siblings}
    assert len({c[1] for c in calls}) == 4  # stepped per-ratio seeds


def test_fanout_dead_sibling_keeps_the_1x1(tmp_path: Path, monkeypatch) -> None:
    seed = _make_seed(tmp_path / "seed.png")
    _ladder_harness(monkeypatch, tmp_path, seed)

    def _flake(seed_local, scene, ratio, dest, **kwargs):
        if ratio == "16x9":
            raise RuntimeError("bedrock hiccup")
        Path(dest).write_bytes(_png_bytes(generate._NATIVE_RATIO_DIMS[ratio]))
        return Path(dest)

    monkeypatch.setattr(generate, "_stability_native_ratio", _flake)
    siblings = {r: tmp_path / f"sib-{r}.png" for r in ("4x5", "9x16", "16x9", "blog")}
    out = tmp_path / "hero.png"
    _result, _source, prov = generate.generate_hero(
        product_id="power-cakes",
        product_name="Power Cakes",
        brief_msg="wild mornings on the frontier",
        region="us",
        audience="active families",
        out_path=out,
        ratio="1x1",
        layers={},
        market="us",
        season="October",
        native_siblings={r: str(p) for r, p in siblings.items()},
    )
    assert out.exists()  # the 1x1 never dies with a sibling
    assert prov["native_ratios"]["16x9"] == "native-error: RuntimeError"
    assert prov["native_ratios"]["4x5"] == "stability-restyle-native"


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
