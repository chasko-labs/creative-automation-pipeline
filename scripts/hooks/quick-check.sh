#!/usr/bin/env bash
# quick-check -- bounded no-network developer loop
# runs lint, unit, token parity, data mirror parity, and the targeted
# python integration set. no browser automation, no cloud calls, no
# generation, no synchronization, no infrastructure deployment.
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# run_lane names each lane and propagates its exit status explicitly.
# set -e alone does not surface which lane failed, and a swallowed
# non-zero from a wrapped npm/pytest run must still abort the loop.
run_lane() {
  local lane="$1"
  shift
  echo "$lane"
  local status=0
  "$@" || status=$?
  if [ "$status" -ne 0 ]; then
    echo "quick-check: FAILED lane -- $lane" >&2
    exit "$status"
  fi
}

run_lane "quick-check 1/5 ruff (pinned, offline)" uvx --offline ruff@0.15.12 check .
run_lane "quick-check 2/5 vitest unit suite" npm run test:unit
run_lane "quick-check 3/5 panda token parity" npm run tokens:check
run_lane "quick-check 4/5 data mirror parity" python3 scripts/build-frontier-mapping.py --check
run_lane "quick-check 5/5 targeted python integration set" npm run test:integration:fast

echo "quick-check: all fast local checks passed"
