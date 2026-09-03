"""Content-safety gate for AI-generated user-facing TEXT.

No profanity, political content, slurs, or off-brand corporate-tone filler reaches
recipe cards, captions, or shopping lists. Imagery avoids text entirely
(in_image_text stays false), so this gate covers the text layer only.

The blocklist is a static JSON registry (data/safety/blocklist.json) \u2014 pure file
read, no network boundary. Matching is word-boundary, case-insensitive, per category.
Placeholder seed entries (wrapped in __SEED_ONLY__) are skipped at load so they can
never match real copy.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

BLOCKLIST_PATH = Path(__file__).parents[2] / "data" / "safety" / "blocklist.json"

CATEGORIES = ("profanity", "political", "slurs", "corporate_tone")

# the string substituted for a flagged term by redact(); exported so callers can
# detect that a redaction occurred without re-scanning (the returned text is clean).
REDACTION_MARKER = "[redacted]"

_SEED_MARKER = "__SEED_ONLY__"


@lru_cache(maxsize=4)
def _compiled(path: str | None = None) -> dict[str, list[tuple[str, re.Pattern[str]]]]:
    """Load blocklist and compile one word-boundary pattern per term, per category."""
    p = Path(path) if path else BLOCKLIST_PATH
    with p.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    compiled: dict[str, list[tuple[str, re.Pattern[str]]]] = {}
    for cat in CATEGORIES:
        terms = raw.get(cat, [])
        rules: list[tuple[str, re.Pattern[str]]] = []
        for term in terms:
            if not term or _SEED_MARKER in term:
                continue
            # word-boundary match so "ass" does not trip inside "pass"/"grass";
            # multi-word phrases match with flexible internal whitespace
            escaped = r"\s+".join(re.escape(part) for part in term.split())
            pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
            rules.append((term, pattern))
        compiled[cat] = rules
    return compiled


def check_text(text: str, path: str | None = None) -> dict:
    """Scan text against the blocklist.

    Returns {clean: bool, flagged: [{term, category}]}. clean is True only when
    nothing matched across every category.
    """
    flagged: list[dict[str, str]] = []
    if not text:
        return {"clean": True, "flagged": flagged}
    rules = _compiled(path)
    seen: set[tuple[str, str]] = set()
    for cat, cat_rules in rules.items():
        for term, pattern in cat_rules:
            if pattern.search(text) and (term, cat) not in seen:
                flagged.append({"term": term, "category": cat})
                seen.add((term, cat))
    return {"clean": len(flagged) == 0, "flagged": flagged}


def redact(text: str, replacement: str = REDACTION_MARKER, path: str | None = None) -> str:
    """Return text with every flagged term replaced by ``replacement``."""
    if not text:
        return text
    rules = _compiled(path)
    out = text
    for cat_rules in rules.values():
        for _term, pattern in cat_rules:
            out = pattern.sub(replacement, out)
    return out


class UnsafeTextError(ValueError):
    """Raised when text must be rejected outright by the pipeline gate."""

    def __init__(self, text: str, flagged: list[dict[str, str]]):
        self.text = text
        self.flagged = flagged
        terms = ", ".join(f"{f['term']}({f['category']})" for f in flagged)
        super().__init__(f"content-safety gate rejected text; flagged: {terms}")


def reject_if_unsafe(text: str, path: str | None = None) -> str:
    """Gate helper: return text unchanged if clean, else raise UnsafeTextError."""
    result = check_text(text, path)
    if not result["clean"]:
        raise UnsafeTextError(text, result["flagged"])
    return text
