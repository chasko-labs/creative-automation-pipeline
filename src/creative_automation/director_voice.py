"""Director-voice headline cluster — extracted from generate.py.

Grounded-director headline path: kill-switch, layout parse, house style,
military quarantine, offline scrub, per-request opt-in, and the bounded
_director_headline_text call (memo + leak-and-drain executor). generate.py
re-exports every name here so existing importers and tests keep working;
this module owns the code.
"""
from __future__ import annotations

import concurrent.futures
import os
import re

# Refusal guard: a live voice model can still decline (junk retrieved examples make
# refusal likely — PROVEN IN PROD 2026-09-08: hash-laden asset titles as in-voice
# examples produced "I Can't Fulfill This Request" as the campaign headline). A
# refusal is a failed attempt, not a headline — fall back to stock Nova.
_REFUSAL_PHRASES = (
    "i can't",
    "i cannot",
    "i'm sorry",
    "i am sorry",
    "as an ai",
    "unable to",
    "can't fulfill",
    "can't help",
    "won't be able",
)


# Lines containing these never reach the render — model meta-preambles, not copy.
_PREAMBLE_PATTERNS = (
    "here are",
    "here is",
    "here's a",
    "requested",
    "headline options",
    "options:",
    "explanation:",
    # chatty-instruction-model openers/closers (Nova Micro narrates its work:
    # "Sure, here's a rephrased version…" … "This version captures the essence…").
    "sure,",
    "rephrased version",
    "captures the essence",
)


_DIRECTOR_TIMEOUT_S = float(os.getenv("GENERATE_DIRECTOR_TIMEOUT_S", "8"))


_DIRECTOR_LIVE_SOURCE = "bedrock:kodiak-artdirector"


_LAYOUT_INLINE_RE = re.compile(r"\s*LAYOUT\s*:\s*(left|right|center)\s*$", re.IGNORECASE)


def _director_enabled() -> bool:
    """Kill-switch for the grounded-director headline path. OFF unless opted in.

    Requires BOTH flags: KODIAK_DIRECTOR_GROUNDED (legacy per-path switch,
    default true) AND KODIAK_ARTDIRECTOR_ENABLED (primary voice switch,
    default false). Cost incident 2026-09-23: flipping only the primary flag
    left this path live because it keyed off the legacy flag alone — every
    voice path must short-circuit on the one primary boolean.
    """
    grounded = os.getenv("KODIAK_DIRECTOR_GROUNDED", "true").strip().lower() in (
        "1", "true", "yes", "on",
    )
    primary = os.getenv("KODIAK_ARTDIRECTOR_ENABLED", "false").strip().lower() in (
        "1", "true", "yes", "on",
    )
    return grounded and primary


def _parse_layout(caption: str) -> tuple[str, str]:
    """Split Nova Pro text into (headline, side) where side in {left,right,center}."""
    headline, side = "", "center"
    for line in caption.splitlines():
        s = line.strip()
        if not s:
            continue
        m = _LAYOUT_INLINE_RE.search(s)
        if m:
            side = m.group(1).lower()
            s = _LAYOUT_INLINE_RE.sub("", s).strip().strip('"')
            if s and not headline:
                headline = s
            continue
        if s.upper().startswith("LAYOUT:"):
            val = s.split(":", 1)[1].strip().lower()
            if val in ("left", "right", "center"):
                side = val
        elif not headline:
            headline = s.strip('"')
    return headline[:48], side


def _title_case_headline(text: str) -> str:
    """House-style headline: Title Case, no trailing period.

    str.title() mangles apostrophes ("Today's" -> "Today'S"), so capitalize per
    word-match instead. Model-written headlines only — the raw user-brief
    fallback stays byte-for-byte the user's words.
    """
    s = (text or "").strip().rstrip(".").strip()
    return re.sub(
        r"[A-Za-z]+(?:'[A-Za-z]+)?",
        lambda m: m.group(0)[0].upper() + m.group(0)[1:].lower(),
        s,
    )


def _sanitize_military_headline(text: str) -> str | None:
    """Strip military/recruitment language; return None if unrecoverable.

    The grounded director and stock Nova both occasionally emit 'LISTEN UP'
    style commanding language despite prompt bans. Quarantine here so no
    military headline reaches provenance or pixels. Warm agricultural frontier
    only.
    """
    if not text:
        return None
    low = text.lower()
    # Any military/recruitment trigger quarantines the line for resample/fallback
    banned = ("listen up", "recruit", "attention ", "muster", "enlist")
    if any(b in low for b in banned):
        # Try to salvage by stripping the banned prefix phrase and leading interjections
        # e.g. "Alright, Listen Up, Kid. Summer In San Diego..." -> "Summer In San Diego..."
        stripped = re.sub(r"(?i)\b(listen up|recruit|attention|muster|enlist)\b[,\s]*", "", text)
        stripped = re.sub(r"(?i)^\s*(alright|okay|hey|listen)[,\s]+", "", stripped)
        stripped = re.sub(r"(?i)\b(kid|partner|recruit)\b[,\.\s!]*", "", stripped) if "listen up" in low else stripped
        stripped = stripped.strip(" ,.-!\t\n\"'")
        # Collapse double spaces and strip leading punctuation left from the cut
        stripped = re.sub(r"\s{2,}", " ", stripped)
        stripped = stripped.lstrip(" !,.-\"'")
        if stripped and len(stripped.split()) >= 2 and not any(b in stripped.lower() for b in banned):
            # If the salvage starts with punctuation or is still a sentence fragment
            # starting with "You're" from a conversational ramble, quarantine it
            # and let the caller fall back to the warm frontier brief headline
            if stripped[:1] in "!?,." or stripped.lower().startswith("you're"):
                return None
            return _title_case_headline(stripped)
        return None
    return text


def _scrub_director_line(text: str, examples: list[dict]) -> str | None:
    """Extract one render-safe line from raw voice-model output.

    The fine-tuned model wraps lines in markdown (**bold**, "quotes"), prepends
    meta-preambles ("Here are the requested responses:"), and sometimes echoes
    an in-ask example back instead of writing. Any of those reaching the render
    is a defect, so: strip markup, drop preamble/bullet lines, take the first
    substantial line, and reject example-echoes (>=70% word overlap with any
    example). Returns None when nothing render-safe remains (caller resamples
    or falls back to stock Nova).
    """
    t = text.replace("**", "").replace("*", "").replace('"', "").replace("#", "")
    lines = [ln.strip(" -\u2022\t") for ln in t.strip().splitlines()]
    lines = [ln for ln in lines if len(ln.split()) >= 2]
    lines = [
        ln
        for ln in lines
        if not any(p in ln.lower() for p in _PREAMBLE_PATTERNS)
    ]
    if not lines:
        return None
    line = lines[0].strip()
    words = {w.strip(",.!?;:").lower() for w in line.split()} - {""}
    for example in examples:
        example_words = {
            w.strip(",.!?;:").lower()
            for w in str(example.get("caption", "")).split()
        } - {""}
        if example_words and words and len(words & example_words) / len(words) >= 0.7:
            return None
    return line or None


def _voice_requested(value: object) -> bool:
    """Per-request voice opt-in (cost incident 2026-09-23).

    Default requests never touch a voice model, whatever the env flags say —
    the caller must opt in explicitly per request. Env flags remain as the
    kill-switch (both must allow AND the request must ask).
    """
    return str(value or "").strip().lower() in ("1", "true", "yes", "on")


def _director_headline_text(
    product_name: str, brief_msg: str, region: str, audience: str,
    art_director: bool = False, report: dict | None = None,
    market: str | None = None, season: str | None = None,
) -> str | None:
    """Grounded-director headline: retrieve brand voice, direct, normalize.

    The concept loop in one bounded call: embed the request -> top-k corpus
    captions -> trained voice model directs with those examples in-ask ->
    scrub + layout-parse + house-style normalize. Returns None on ANY failure
    (no examples, offline mock source, refusal, unscrubbable output, timeout,
    exception) so the caller falls back to the stock Nova caption. The mock
    source is refused explicitly — a mock transport must never write a
    production headline. A refused/scrubbed trio resamples ONCE with the single
    best example (PROVEN IN PROD 2026-09-08: trios of fragment-grade captions
    decline while the top-1 alone complies); a dead transport does not
    resample — it falls straight through to Nova.
    """
    import sys as _sys

    def _dnote(msg: str) -> None:
        print(f"[director] {msg}", file=_sys.stderr)

    if not _director_enabled():
        _dnote("skip: kill-switch off")
        return None
    if not art_director:
        _dnote("skip: no per-request opt-in")
        return None
    # Memo (PROVEN IN PROD 2026-09-08): generate_hero_set runs the headline
    # pipeline TWICE per pack (base hero + set headline) with the same brief —
    # the second run re-pays embed + up to two voice invokes (~14s) and burns
    # the 22s wall to rung D. Same inputs deterministically yield the same
    # voice line, so memoize per warm container (capped FIFO). A memo hit costs
    # ~0 and bypasses the budget gate + executor below. The kill-switch stays
    # above the memo so an ops flip takes effect immediately.
    global _DIRECTOR_MEMO
    try:
        _ = _DIRECTOR_MEMO
    except NameError:
        _DIRECTOR_MEMO = {}
    # Uniqueness fix 3: the memo key salts market + season, so the same
    # brief in June and October (or Cincinnati and Seattle) re-derives
    # instead of replaying one memoized line. Identical full requests
    # (the twice-per-pack double call) still hit.
    memo_key = (product_name, brief_msg, region, audience, market or "", season or "")
    # Paid-voice attempt counter for the UI ("refining…" while attempts > 1).
    # Memo hits cost zero new calls. Reported out via `report` when provided.
    attempts = {"n": 0}
    if memo_key in _DIRECTOR_MEMO:
        _dnote("memo hit")
        if report is not None:
            report["voice_attempts"] = 0
            report["voice_source"] = "memo"
        cached = _DIRECTOR_MEMO[memo_key]
        # Sanitize even memo hits — a warm container may hold a pre-fix military line
        sanitized = _sanitize_military_headline(cached)
        if sanitized is None:
            _dnote(f"memo military filtered ({cached[:60]!r}) — miss")
            # bust the poisoned memo entry so the next call re-derives a clean line
            try:
                del _DIRECTOR_MEMO[memo_key]
            except KeyError:
                pass
            return None
        if sanitized != cached:
            _dnote(f"memo military stripped: {cached[:60]!r} -> {sanitized[:60]!r}")
            _DIRECTOR_MEMO[memo_key] = sanitized
            return sanitized
        return cached
    try:
        from . import art_director, director_memory
    except ImportError as e:
        _dnote(f"skip: import failed ({e})")
        return None

    def _attempt() -> str | None:
        query = f"{product_name} {brief_msg} {region} {audience} {market or ''} {season or ''}".strip()
        examples, model_used = director_memory.retrieve(query, k=3)
        if not examples:
            _dnote(f"no examples (embed={model_used})")
            return None
        _dnote(f"retrieved {len(examples)} examples via {model_used}")
        locale_ask = ""
        if market and str(market).strip():
            locale_ask += f" Market {str(market).strip()}."
        if season and str(season).strip():
            locale_ask += f" Season {str(season).strip()}."
        ask = (
            f"Write one short on-brand headline (max 6 words) for {product_name}: "
            f"{brief_msg}. Region {region}, audience {audience}.{locale_ask}"
        )
        samples = [examples[:3]]
        if len(examples[:1]) < len(examples[:3]):
            samples.append(examples[:1])
        for sample in samples:
            if not sample:
                break
            attempts["n"] += 1
            result = art_director.art_direct_grounded(
                ask, "adventurous", examples=sample
            )
            if not isinstance(result, dict) or result.get("source") != _DIRECTOR_LIVE_SOURCE:
                _dnote(f"voice not live (source={(result or {}).get('source')})")
                return None
            text = str(result.get("text", "")).strip()
            if not text:
                continue
            if any(phrase in text.lower() for phrase in _REFUSAL_PHRASES):
                _dnote(f"voice refused ({text[:60]!r}) — resampling")
                continue
            line = _scrub_director_line(text, sample)
            if line is None:
                _dnote(f"voice output unusable ({text[:60]!r}) — resampling")
                continue
            headline, _side = _parse_layout(line)
            normed = _title_case_headline(headline)
            sanitized = _sanitize_military_headline(normed)
            if sanitized is None:
                _dnote(f"voice military filtered ({normed[:60]!r}) — resampling")
                continue
            if sanitized:
                return sanitized
        return None

    # Leak-and-drain on timeout (same contract generate_lambda documents for its own
    # inner director timeout): exiting a `with` executor would shutdown(wait=True) and
    # block until the abandoned worker finishes its retries — the timeout would be a
    # lie and the wall would burn. shutdown(wait=False) abandons the worker; it writes
    # nothing shared, retries out, and drains harmlessly.
    try:
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    except Exception:  # noqa: BLE001 — tribunal alloc must never break the voice
        return None
    try:
        fut = executor.submit(_attempt)
        try:
            outcome = fut.result(timeout=_DIRECTOR_TIMEOUT_S)
        except Exception:  # noqa: BLE001 — worker outcome None on any failure
            outcome = None
    finally:
        executor.shutdown(wait=False)
    # Memoize only live successes: a cold-model timeout (outcome None) must not poison
    # later warm invocations in the same container — they retry the voice fresh and
    # degrade to the Nova caption only if the voice fails again.
    if report is not None:
        report["voice_attempts"] = attempts["n"]
        report["voice_source"] = _DIRECTOR_LIVE_SOURCE if outcome is not None else None
    if outcome is not None:
        _DIRECTOR_MEMO[memo_key] = outcome
    while len(_DIRECTOR_MEMO) > 64:
        _DIRECTOR_MEMO.pop(next(iter(_DIRECTOR_MEMO)))
    return outcome

