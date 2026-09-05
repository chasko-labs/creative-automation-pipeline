#!/usr/bin/env bash
#
# full gate -- the deliberate pre-merge checkpoint, NOT a per-push tax.
# run this before opening or merging a PR. mirrors buildspec.yml gates 2+3
# (the per-push hook already covers gate 1, ruff).
#
#   gate 2  uv run --with pytest pytest -x -q   (fast unit tests)
#   gate 3  cfn-lint infra/template.yaml        (template safety)
#
# usage:  scripts/hooks/full-check.sh
# ---------------------------------------------------------------------------
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

echo "full-check 1/2 pytest -x"
uv run --with pytest pytest -x -q

echo "full-check 2/2 cfn-lint"
cfn-lint infra/template.yaml

echo "full-check: all gates passed -- safe to merge"
