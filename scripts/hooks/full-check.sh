#!/usr/bin/env bash
#
# full gate -- the deliberate pre-merge checkpoint, NOT a per-push tax.
# run this before opening or merging a PR. mirrors buildspec.yml gates.
# (the per-push hook already covers gate 1, ruff).
#
# stack order: deterministic first, model judgment second.
#   vitest (token css, no browser) -> panda-parity + kodiak-parity ->
#   targeted chromium (spectrum-a11y, render-baseline) ->
#   full matrix (pytest -x, nova-act live smoke) + cfn-lint
#
# usage:  scripts/hooks/full-check.sh
# ---------------------------------------------------------------------------
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

echo "full-check 1/6 vitest (token css, pinned)"
npm run test:vitest

echo "full-check 2/6 panda-parity"
python3 scripts/check-panda-tokens.py

echo "full-check 3/6 kodiak-parity (pytest)"
uv run --with pytest pytest -q tests/test_kodiak_parity.py tests/test_token_drift.py

echo "full-check 4/6 spectrum-a11y (chromium)"
node scripts/check-spectrum.mjs

echo "full-check 5/6 render-baseline (chromium)"
node scripts/check-brand-render.mjs

echo "full-check 6/6 pytest -x + cfn-lint + nova-act smoke"
uv run --with pytest pytest -x -q
cfn-lint infra/template.yaml
python3 tests/nova-act/run.py

echo "full-check: all gates passed -- safe to merge"
