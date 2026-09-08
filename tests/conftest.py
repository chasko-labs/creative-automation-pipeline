"""Suite-wide hermetic defaults.

The grounded-director headline path is live-capable (Bedrock embed + voice-model
invoke) and budget-gated — unit tests must never touch it implicitly. Force the
kill-switch OFF for every test; tests covering the grounded loop opt back in
explicitly with monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "true") plus
mocked retrieve/director transports.
"""
from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _grounded_director_off_by_default(monkeypatch):
    monkeypatch.setenv("KODIAK_DIRECTOR_GROUNDED", "false")
