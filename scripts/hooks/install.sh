#!/usr/bin/env bash
#
# one-command activation for the local pre-push gate.
# point this repo's hooks at scripts/hooks so a fresh clone gets the pre-push
# gate with a single run. this is a per-repo setting -- it does not touch the
# global core.hooksPath.
#
# usage (after clone):
#   scripts/hooks/install.sh
# ---------------------------------------------------------------------------
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

chmod +x scripts/hooks/pre-push
git config core.hooksPath scripts/hooks

echo "local pre-push gate activated (core.hooksPath -> scripts/hooks)"
echo "the pre-push hook runs ruff (fast lint) before every push; run scripts/hooks/full-check.sh (pytest + cfn-lint) before opening/merging a PR"
