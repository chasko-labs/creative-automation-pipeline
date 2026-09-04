"""Tests for the runtime data-root resolver (FIX 2: missing data file in Lambda image).

CloudWatch showed the localization chain erroring to fallback with
`[Errno 2] No such file or directory: '/var/lang/lib/python3.11/data/localization/
retailer-frontier-pairs.json'` — under the Lambda install layout (pip install . into
site-packages) Path(__file__).parents[2]/data does not exist. _datapaths.data_root()
resolves the data dir robustly (env override, repo checkout, /var/task/data) so the
file is reachable both locally and in the image.
"""
from __future__ import annotations

import json
from pathlib import Path

from creative_automation import _datapaths


def test_data_root_finds_repo_checkout_layout() -> None:
    # in the repo checkout, data/ sits beside src/ (parents[2]/data) and must resolve.
    root = _datapaths.data_root()
    assert root.exists()
    assert root.name == "data"


def test_retailer_frontier_pairs_resolves_and_loads() -> None:
    # the exact file that errored in the Lambda: it must resolve from the layout AND
    # parse without the /var/lang error.
    pairs = _datapaths.data_path("localization", "retailer-frontier-pairs.json")
    assert pairs.exists(), f"expected {pairs} to exist under the resolved data root"
    data = json.loads(pairs.read_text(encoding="utf-8"))
    assert "pairs" in data


def test_env_override_wins(monkeypatch, tmp_path: Path) -> None:
    # CAP_DATA_ROOT (the Lambda points this at /var/task/data) is the first candidate.
    fake = tmp_path / "shipped-data"
    (fake / "localization").mkdir(parents=True)
    (fake / "localization" / "retailer-frontier-pairs.json").write_text('{"pairs": []}')
    monkeypatch.setenv("CAP_DATA_ROOT", str(fake))
    assert _datapaths.data_root() == fake
    resolved = _datapaths.data_path("localization", "retailer-frontier-pairs.json")
    assert resolved == fake / "localization" / "retailer-frontier-pairs.json"
    assert resolved.exists()


def test_locales_uses_resolved_pairs_path() -> None:
    # the resolver is wired into locales.PAIRS_PATH — the runtime path the handler drives.
    from creative_automation import locales

    assert locales.PAIRS_PATH.exists()
    assert locales.PAIRS_PATH.name == "retailer-frontier-pairs.json"
    # and it loads without raising (the fallback error was a load failure)
    pair = locales.resolve_pair("us")
    assert pair is None or hasattr(pair, "market")
