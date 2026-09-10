"""Build the coach KB corpus: deterministic RAG docs from committed sources.

Renders data/kb-corpus/*.md from the raw-ingest social deeps (voice, cadence,
hashtags, formats) and copies brand-lore + standards docs verbatim. Bedrock KB
S3 ingestion silently skips unsupported formats (JSON is unsupported), hence
the markdown rendering. A test asserts the committed corpus regenerates
byte-identical, so retrieval grounding can never drift from the repo.

Usage:
  python3 scripts/build-kb-corpus.py [--sync-s3 s3://bucket/prefix/]

PII stance: sources are public marketing posts and published brand guides —
no customer data. The builder scans the output for email/phone patterns and
fails closed if any appear.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
INGEST = ROOT / "data" / "raw-ingest" / "kodiakcakes"
LORE = INGEST / "brand-lore"
OUT = ROOT / "data" / "kb-corpus"

# Brand-lore .txt files worth ingesting (plain extractions only — the .html
# and .html.txt triplets are the same content twice more).
LORE_FILES = (
    "kodiak-brand-lore-knowledge-base.txt",
    "Brand_Ambassador_Print_Guide.txt",
    "our-mission.txt",
    "keepitwild.txt",
    "kirnani-product-positioning.txt",
    "graphicpkg-packaging-brand-values.txt",
    "forbes-platform-brand.txt",
    "kodiak-cakes-case-study.txt",
)

# Committed standards docs worth ingesting.
DOC_FILES = (
    "docs/kodiak-image-standards.md",
    "docs/kodiak-brand-explained.md",
)

COPY_LAW_MD = """# Copy law (hard rules — canon tests/test_atlanta_copy_law.py)

- The word KODIAK (all caps) never ships in generated copy, except inside a hashtag token.
- Title-case Kodiak appears only as "Kodiak Cakes" or "Kodiak Park City"; bare Kodiak appears nowhere.
- Social voice uses #kodiakcakes-style hashtags.
- No invented translations or frontier data; thin-month event suggestions are UNVERIFIED until confirmed.
"""

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_PII_RES = (
    _EMAIL_RE,
    re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"),
)


def _clean(text: object, limit: int = 0) -> str:
    s = re.sub(r"\s+", " ", str(text or "")).strip()
    return s[:limit] if limit else s


# PDF-extraction control bytes ride along in lore sources and make Bedrock's
# format sniffer reject the page — strip them (keep newline + tab).
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize(text: str) -> str:
    return _CONTROL_RE.sub("", text)


def _deep(name: str) -> dict:
    return json.loads((INGEST / name).read_text(encoding="utf-8"))


def _social_docs() -> dict[str, str]:
    docs: dict[str, str] = {}
    insta = _deep("insta-deep.json")
    cadence = (insta.get("posting_cadence", {}) or {}).get("observed_dates_2026", [])
    tags = insta.get("hashtag_families", {}) or {}
    fams = tags.get("families", {}) or {}
    docs["social-voice-instagram.md"] = "\n".join([
        f"# Instagram voice — {insta.get('handle', '')} ({insta.get('followers', 0):,} followers)",
        "",
        f"Bio: {_clean(insta.get('bio'))}",
        f"Highlights: {', '.join(insta.get('highlights', []))}",
        f"Posting window: {_clean((insta.get('when_they_post', {}) or {}).get('time_of_day'))}",
        f"Recent cadence ({len(cadence)} observed 2026): {'; '.join(cadence[:12])}",
        f"Primary tags: {' '.join(tags.get('primary_brand', []))}",
        f"Secondary tags: {' '.join(tags.get('secondary_brand', []))}",
        "",
        *[f"## Tag family {name}: {' '.join(f.get('tags', []))} — {_clean(f.get('use'), 200)}"
          for name, f in sorted(fams.items())],
        "",
        f"Feed spec: {_clean((insta.get('aspect', {}) or {}).get('feed_photo'))}",
        f"Reels spec: {_clean((insta.get('aspect', {}) or {}).get('reels'))}",
        "",
    ])
    for name, title in (("tiktok-deep.json", "TikTok"), ("facebook-deep.json", "Facebook")):
        deep = _deep(name)
        docs[f"social-voice-{title.lower()}.md"] = "\n".join([
            f"# {title} voice — {deep.get('handle') or deep.get('title', '')}",
            "",
            f"Bio: {_clean(deep.get('bio'))}",
            f"Posting window: {_clean((deep.get('when_they_post', {}) or {}).get('time_of_day'))}",
            f"Tags: {' '.join(((deep.get('hashtag_families', {}) or {}).get('primary_brand', [])))}",
            "",
        ])
    yt = _deep("youtube-deep.json")
    docs["social-voice-youtube.md"] = "\n".join([
        f"# YouTube — {(yt.get('channel', {}) or {}).get('handle', '@kodiakcakes')}",
        "",
        f"Cadence: {_clean(yt.get('posting_cadence'))}",
        f"Formats: {_clean(yt.get('formats'))}",
        f"Top content: {_clean(yt.get('top_content'), 600)}",
        "",
    ])
    pin = _deep("pinterest-deep.json")
    audited = ((pin.get("boards", {}) or {}).get("audited", []) or [])[:12]
    docs["social-voice-pinterest.md"] = "\n".join([
        f"# Pinterest — {((pin.get('profile', {}) or {}).get('handle', ''))}",
        "",
        f"Pinning strategy: {_clean(pin.get('pinning_strategy'), 400)}",
        *[f"## Board {b.get('name', '')}: {_clean(b.get('theme'), 200)}" for b in audited],
        "",
    ])
    return docs


# Byte budget: the metadata cap counts UTF-8 bytes, and lore carries
# multibyte markers — so every measure here is encoded length.
PAGE_LIMIT = 1150


def _bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def _paginate(name: str, text: str) -> dict[str, str]:
    """Split long docs into paragraph-bounded pages.

    Bedrock mirrors doc text into AMAZON_BEDROCK_TEXT filterable metadata
    (2048-byte S3 Vectors cap); server-side chunking keeps overflowing it,
    so pages are pre-split here and ingested with chunking NONE. Small docs
    pass through untouched under their own name.
    """
    if _bytes(text) <= PAGE_LIMIT:
        return {name: text}
    pages: dict[str, str] = {}
    stem = pathlib.Path(name).stem
    current: list[str] = []
    size = 0
    n = 1
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    # Scraped lore can be one giant paragraph — split those by sentence,
    # then hard-slice anything still oversize. Every page must fit the
    # metadata cap with room to spare.
    units: list[str] = []
    for para in paras:
        para = para.strip()
        if _bytes(para) <= PAGE_LIMIT:
            units.append(para)
            continue
        for sent in re.split(r"(?<=[.!?])\s+", para):
            sent = sent.strip()
            if not sent:
                continue
            while _bytes(sent) > PAGE_LIMIT:
                cut = PAGE_LIMIT
                while cut > 0 and _bytes(sent[:cut]) > PAGE_LIMIT:
                    cut -= 1
                units.append(sent[:cut])
                sent = sent[cut:]
            if sent:
                units.append(sent)
    for unit in units:
        if current and size + _bytes(unit) + 2 > PAGE_LIMIT:
            pages[f"{stem}-p{n}.md"] = "\n\n".join(current).rstrip() + "\n"
            n += 1
            current, size = [], 0
        current.append(unit)
        size += _bytes(unit) + 2
    if current:
        pages[f"{stem}-p{n}.md"] = "\n\n".join(current).rstrip() + "\n"
    for page in pages.values():
        assert _bytes(page) <= PAGE_LIMIT + 1, f"oversize page in {name}"
    return pages


def build() -> dict[str, str]:
    docs = _social_docs()
    docs["copy-law.md"] = COPY_LAW_MD
    for name in LORE_FILES:
        src = LORE / name
        if src.exists():
            docs[f"brand-lore-{pathlib.Path(name).stem}.md"] = src.read_text(encoding="utf-8").rstrip() + "\n"
    for name in DOC_FILES:
        src = ROOT / name
        if src.exists():
            docs[f"standards-{pathlib.Path(name).stem}.md"] = src.read_text(encoding="utf-8").rstrip() + "\n"
    for name in docs:
        # Pre-ingestion redaction: corporate contact emails carry no
        # retrieval value, so mask them rather than dropping whole docs.
        docs[name] = _EMAIL_RE.sub("[redacted]", _sanitize(docs[name]))
    paged: dict[str, str] = {}
    for name, text in docs.items():
        paged.update(_paginate(name, text))
    for name, text in paged.items():
        for rx in _PII_RES:
            if rx.search(text):
                raise SystemExit(f"PII pattern in {name} — refusing to build corpus")
    return paged


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sync-s3", default=None, help="s3://bucket/prefix to sync data/kb-corpus/ into")
    args = ap.parse_args()
    docs = build()
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.md"):
        if stale.name not in docs:
            stale.unlink()
    for name, text in docs.items():
        (OUT / name).write_text(text, encoding="utf-8")
    print(f"wrote {len(docs)} docs to {OUT}")
    if args.sync_s3:
        cmd = ["aws", "s3", "sync", str(OUT) + "/", args.sync_s3, "--region", "us-east-1",
               "--profile", "bryanchasko-kiro", "--delete", "--exclude", "*", "--include", "*.md"]
        print("[corpus] s3 sync:", " ".join(cmd))
        rc = subprocess.run(cmd, check=False).returncode
        print(f"[corpus] s3 sync exit {rc}")
        return rc
    return 0


if __name__ == "__main__":
    sys.exit(main())
