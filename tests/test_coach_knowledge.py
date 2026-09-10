"""Coach knowledge grounding: committed knowledge.md regenerates byte-identical."""
from __future__ import annotations

import importlib.util
import pathlib


def _load_builder():
    path = pathlib.Path(__file__).parents[1] / "scripts" / "build-coach-knowledge.py"
    spec = importlib.util.spec_from_file_location("build_coach_knowledge", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = _load_builder().build


def test_knowledge_regenerates_byte_identical() -> None:
    committed = pathlib.Path("coach/knowledge.md").read_text(encoding="utf-8")
    assert build() == committed


def test_knowledge_covers_every_shipped_theme() -> None:
    import json

    slugs = json.loads(pathlib.Path("data/products/theme-asset-map.json").read_text())["map"]
    text = pathlib.Path("coach/knowledge.md").read_text(encoding="utf-8")
    for slug in slugs:
        assert slug in text, f"theme missing from coach grounding: {slug}"
    assert "zac-efron" not in text


def test_knowledge_carries_brand_law_voice_and_pipeline() -> None:
    import pathlib

    text = pathlib.Path("coach/knowledge.md").read_text(encoding="utf-8")
    assert "## Brand standards (copy law" in text
    assert "bare Kodiak appears nowhere" in text
    assert "## Past social voice" in text
    assert "@kodiakcakes" in text
    assert "#KodiakCakes" in text
    assert "## Pipeline tools" in text
    assert "compliance.py" in text


def test_knowledge_fits_lambda_slice_budget() -> None:
    import pathlib

    # coach/index.mjs slices knowledge to 12000 chars for the zip prompt.
    assert len(pathlib.Path("coach/knowledge.md").read_text(encoding="utf-8")) < 9000


def test_knowledge_fuses_context_pack() -> None:
    import pathlib

    text = pathlib.Path("coach/knowledge.md").read_text(encoding="utf-8")
    assert "## Context pack (deterministic grounding" in text
    assert "- brand rules: no text or logo inside the image (cr-1)" in text
    assert "image topics (12 clusters)" in text
    assert "sample voice 1" in text
    assert "74 markets" in text
