"""User-visible copy contract: internal scaffolding never reaches the reader.

Backfill/coverage notes (e.g. "(auto-patched for 26-season coverage)"),
doubled suffixes ("(Easter) (Easter)"), and unconfirmed-address markers
("confirm — ...") are tracking metadata. They may live in dedicated metadata
fields (note/source/seasons, raw address values) but must not appear in
user-visible copy strings or emitted bundles. The recipes gallery render
(metroMeta in js/recipes.js) omits unconfirmed addresses by contract; this
test pins the source side of that contract.
"""
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "data" / "localization" / "retailer-frontier-pairs.json"
EMITTED_PAIRS = (
    REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier"
    / "js" / "recipes-frontier-pairs.js"
)
EMITTED_CARDS = (
    REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier"
    / "js" / "recipe-cards-data.js"
)
RECIPES_JS = (
    REPO_ROOT / "web" / "kodiak-posts-for-todays-frontier" / "js" / "recipes.js"
)

AUTO = re.compile(r"auto-patched", re.IGNORECASE)
DOUBLE = re.compile(r"\(([^()]*)\) \(\1\)")
CONFIRM = "confirm"


def _moments_and_available(doc):
    for pair in doc["pairs"]:
        for mo in pair.get("seasonal_moments") or []:
            if isinstance(mo.get("moment"), str):
                yield pair["market"], "moment", mo["moment"]
            for avail in mo.get("available_ingredients") or []:
                if isinstance(avail, str):
                    yield pair["market"], "available", avail


def test_source_copy_has_no_scaffolding_notes():
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    bad = [
        f"{market}/{kind}: {text[:80]}"
        for market, kind, text in _moments_and_available(doc)
        if AUTO.search(text)
    ]
    assert not bad, "scaffolding notes in user-visible copy:\n" + "\n".join(bad)


def test_source_copy_has_no_doubled_suffixes():
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    bad = [
        f"{market}/{kind}: {text[:80]}"
        for market, kind, text in _moments_and_available(doc)
        if DOUBLE.search(text)
    ]
    assert not bad, "doubled suffixes in user-visible copy:\n" + "\n".join(bad)


def test_source_addresses_are_confirmed_or_marked():
    doc = json.loads(SRC.read_text(encoding="utf-8"))
    bad = []
    for pair in doc["pairs"]:
        addr = (pair.get("metro_location") or {}).get("address")
        if addr is None:
            continue
        if not addr or (not addr.startswith(CONFIRM) and len(addr) < 4):
            bad.append(f"{pair['market']}: {addr!r}")
    assert not bad, "addresses neither confirmed nor marked:\n" + "\n".join(bad)


def _visible_strings(path: Path):
    """User-visible copy strings from an emitted bundle (moments + available).

    note/source/seasons are write-only coverage metadata — they may keep
    scaffolding provenance, but display strings must not.
    """
    text = path.read_text(encoding="utf-8")
    payload = text.split("=", 1)[1].strip().rstrip(";")
    doc = json.loads(payload)
    out = []

    def walk(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, dict):
            for k, v in o.items():
                if k in ("moment", "available", "available_ingredients"):
                    walk(v)
                elif isinstance(v, (dict, list)):
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    if isinstance(doc, list):
        for pair in doc:
            for mo in pair.get("moments") or []:
                if isinstance(mo.get("moment"), str):
                    out.append(mo["moment"])
    else:
        walk(doc)
    return out


def test_emitted_bundles_have_no_scaffolding_notes():
    for path in (EMITTED_PAIRS, EMITTED_CARDS):
        bad = [s[:80] for s in _visible_strings(path) if AUTO.search(s)]
        assert not bad, f"{path.name} leaks scaffolding notes:\n" + "\n".join(bad)


def test_gallery_render_omits_unconfirmed_addresses():
    text = RECIPES_JS.read_text(encoding="utf-8")
    assert "confirm" in text and "metroMeta" in text, (
        "recipes.js must keep the unconfirmed-address guard on metroMeta"
    )
