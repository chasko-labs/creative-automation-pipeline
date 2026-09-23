"""The emitted frontier-pairs JS must carry every brief-facing field.

Regression guard: the emitter once dropped favorite_flavors, starving all
82 market-month briefs of taste detail (Manhattan/Halloween showed no
flavors parenthetical) while the source JSON and its bar test stayed green.
This test renders the emit in-memory and asserts the shipped fields survive.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import emit_frontier_pairs_js as emitter


def _emitted_pairs():
    body = emitter.render()
    payload = body.split("window.KODIAK_FRONTIER_PAIRS = ", 1)[1].rstrip().rstrip(";")
    return json.loads(payload)


def test_emit_carries_favorite_flavors():
    pairs = {p["market"]: p for p in _emitted_pairs()}
    manhattan = pairs["US-NE-MANHATTAN"]
    applefest = next(
        mo for mo in manhattan["moments"] if "Applefest" in mo["moment"]
    )
    assert applefest["favorite_flavors"] == ["apple cinnamon", "cider", "caramel apple"], (
        f"Applefest flavors lost in emit: {applefest}"
    )


def test_emit_flavors_match_source():
    source = {
        p["market"]: p
        for p in json.loads(emitter.SRC.read_text(encoding="utf-8"))["pairs"]
    }
    emitted = {p["market"]: p for p in _emitted_pairs()}
    checked = 0
    for market, srec in source.items():
        erec = emitted[market]
        for smo in srec.get("seasonal_moments") or []:
            want = smo.get("favorite_flavors") or []
            if not want:
                continue
            emo = next(
                mo for mo in erec["moments"] if mo["moment"] == smo["moment"]
            )
            assert emo["favorite_flavors"] == want, (
                f"{market} moment {smo['moment']!r}: flavors {emo['favorite_flavors']} != {want}"
            )
            checked += 1
    assert checked > 100, f"expected broad flavor coverage, checked {checked}"


def test_emit_in_sync_with_checked_in_js():
    assert emitter.main.__defaults__ is None  # main() takes no args; --check via argv
    import sys as _sys
    argv, _sys.argv = _sys.argv, ["emit_frontier_pairs_js.py", "--check"]
    try:
        assert emitter.main() == 0, "checked-in pairs JS drifted from source; re-run emit"
    finally:
        _sys.argv = argv
