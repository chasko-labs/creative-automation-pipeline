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
