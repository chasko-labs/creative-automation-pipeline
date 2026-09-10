"""KB corpus grounding: committed data/kb-corpus regenerates byte-identical."""
from __future__ import annotations

import importlib.util
import pathlib


def _load_builder():
    path = pathlib.Path(__file__).parents[1] / "scripts" / "build-kb-corpus.py"
    spec = importlib.util.spec_from_file_location("build_kb_corpus", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build = _load_builder().build


def test_corpus_regenerates_byte_identical() -> None:
    out = pathlib.Path("data/kb-corpus")
    assert out.is_dir(), "run python3 scripts/build-kb-corpus.py"
    fresh = build()
    on_disk = {p.name for p in out.glob("*.md")}
    assert set(fresh) == on_disk, f"stale corpus: {set(fresh) ^ on_disk}"
    for name, text in fresh.items():
        assert (out / name).read_text(encoding="utf-8") == text, name


def test_corpus_covers_voice_law_and_lore() -> None:
    out = pathlib.Path("data/kb-corpus")
    names = {p.name for p in out.glob("*.md")}
    assert any(n.startswith("social-voice-instagram") for n in names)
    assert "copy-law.md" in names
    assert any(n.startswith("brand-lore-") for n in names)
    assert any(n.startswith("standards-") for n in names)
    insta = " ".join(
        (out / n).read_text(encoding="utf-8")
        for n in names
        if n.startswith("social-voice-instagram")
    )
    assert "@kodiakcakes" in insta
    assert "#KodiakCakes" in insta


def test_corpus_carries_no_emails() -> None:
    import re

    rx = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    for path in pathlib.Path("data/kb-corpus").glob("*.md"):
        assert rx.search(path.read_text(encoding="utf-8")) is None, path.name


def test_every_page_fits_vector_metadata_cap() -> None:
    # Bedrock mirrors doc text into AMAZON_BEDROCK_TEXT filterable metadata
    # (2048-byte S3 Vectors cap) — pages must stay well under it.
    import pathlib

    for path in pathlib.Path("data/kb-corpus").glob("*.md"):
        assert len(path.read_bytes()) <= 1151, path.name
