"""Runtime data-root resolver — makes data/ files reachable in every install layout.

The package reads static JSON under data/ (localization pairs, market languages, dialect
tables). In a repo checkout Path(__file__).parents[2] IS the repo root and data/ sits
beside src/. In the Lambda container the package is `pip install .`ed into site-packages,
so parents[2] resolves to the site-packages parent (/var/lang/lib/python3.11) and
parents[2]/data does not exist — the exact cause of the observed
`[Errno 2] No such file or directory: '/var/lang/lib/python3.11/data/localization/
retailer-frontier-pairs.json'` fallback. This resolver picks the first data root that
actually exists so the same code works locally and in the image.

Candidate order (first existing wins):
  a. $CAP_DATA_ROOT (Lambda points this at the shipped copy in /var/task/data)
  b. Path(__file__).parents[2]/data (repo checkout — src/ and data/ are siblings)
  c. /var/task/data (LAMBDA_TASK_ROOT default when the env var is unset)
"""
from __future__ import annotations

import os
from pathlib import Path

_REPO_DATA = Path(__file__).resolve().parents[2] / "data"
_LAMBDA_DATA = Path("/var/task/data")


def data_root() -> Path:
    """Return the data/ directory that exists under the current install layout.

    Falls back to the repo-checkout path even if absent, so a downstream load failure
    names a sensible path in its error message rather than a phantom one.
    """
    candidates: list[Path] = []
    env = os.getenv("CAP_DATA_ROOT")
    if env:
        candidates.append(Path(env))
    candidates.append(_REPO_DATA)
    candidates.append(_LAMBDA_DATA)
    for c in candidates:
        if c.exists():
            return c
    return _REPO_DATA


def data_path(*parts: str) -> Path:
    """Join parts onto the resolved data root (e.g. data_path('localization', 'x.json'))."""
    return data_root().joinpath(*parts)
