#!/usr/bin/env bash
# full local gate -- run before opening or merging a pull request
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

echo "full-check 1/10 ruff"
uvx ruff@0.15.12 check .

echo "full-check 2/10 vitest"
npm run test:unit

echo "full-check 3/10 panda token parity"
npm run tokens:check

echo "full-check 4/10 data mirror parity"
python3 scripts/build-frontier-mapping.py --check

echo "full-check 5/10 kodiak parity"
npm run test:integration:fast

echo "full-check 6/10 python unit and integration tests"
npm run test:integration

echo "full-check 7/10 deterministic accessibility browser check"
npm run test:accessibility

echo "full-check 8/10 deterministic render check"
node scripts/check-brand-render.mjs

echo "full-check 9/10 local browser scenarios"
npm run test:browser

echo "full-check 10/10 infrastructure template lint"
cfn-lint infra/template.yaml

echo "full-check: all local checks passed"
