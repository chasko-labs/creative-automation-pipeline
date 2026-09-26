"""Suite-wide hermetic defaults.

The grounded-director headline path is live-capable (Bedrock embed + voice-model
invoke) and budget-gated — unit tests must never touch it implicitly. Force the
kill-switch OFF for every test; tests covering the grounded loop opt back in
explicitly with monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "true") AND
monkeypatch.setenv("KODIAK_ARTDIRECTOR_ENABLED", "true") plus mocked
retrieve/director transports (both flags required since 2026-09-23).
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _grounded_director_off_by_default(monkeypatch):
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "false")


@pytest.fixture(autouse=True)
def _live_translate_offline_by_default(monkeypatch):
    """Live translation attempts (Bedrock Nova Micro, Translate API) burn
    ~1s socket timeouts per call in hermetic runs — 16 offender/lang combos
    cost 32s of connect timeouts just to fail into the offline fallback the
    tests assert. Default all three transports to instant-None; tests
    covering a live path stub these names explicitly already."""
    from creative_automation import localize as _localize
    from creative_automation import translate as _translate

    monkeypatch.setattr(_localize, "_try_bedrock_translate", lambda *a, **k: None)
    monkeypatch.setattr(_localize, "_try_translate_api", lambda *a, **k: None)
    monkeypatch.setattr(_translate, "_try_aws_translate", lambda *a, **k: None)
