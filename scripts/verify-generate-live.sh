#!/usr/bin/env bash
# Post-deploy live check for the /generate backend.
#
# WHY this retries: after update-function-code + `wait function-updated`, the
# first live invoke can still land on a draining pre-update container and
# report a stale provenance (seen twice: dish None while recipe is right).
# A single-shot curl then cries wolf. This polls until the fresh code proves
# itself (dish names the paired recipe) or the attempts run out.
#
# Usage:
#   ./scripts/verify-generate-live.sh [season] [max_attempts]
#   GENERATE_API_URL=https://... ./scripts/verify-generate-live.sh halloween
#
# Env:
#   GENERATE_API_URL  generate endpoint (default: the kodiak-generate-api default stage)
set -euo pipefail

SEASON="${1:-christmas}"
MAX_ATTEMPTS="${2:-10}"
SLEEP_S=20
API_URL="${GENERATE_API_URL:-https://mcaptnm7vh.execute-api.us-east-1.amazonaws.com/generate}"

attempt=1
while [[ "$attempt" -le "$MAX_ATTEMPTS" ]]; do
  body="$(curl -s -m 150 -X POST "$API_URL" \
    -H 'Content-Type: application/json' \
    -d "{\"prompt\":\"deploy-verify\",\"market\":\"Manhattan, New York\",\"product\":\"power-cakes\",\"season\":\"$SEASON\"}")" || body=""
  verdict="$(DISH_BODY="$body" python3 -c "
import json, os
try:
    d = json.loads(os.environ.get('DISH_BODY') or '')
except Exception:
    print('unparseable')
    raise SystemExit
if not (isinstance(d, dict) and d.get('ok') is True):
    print('not-ok')
    raise SystemExit
p = d.get('provenance') or {}
dish = (p.get('dish') or '').strip()
recipe = (p.get('recipe') or '').strip()
print('pass' if dish and dish == recipe else 'stale: dish=%r recipe=%r' % (dish, recipe))
")"
  echo "[verify-generate-live] attempt $attempt/$MAX_ATTEMPTS season=$SEASON -> $verdict"
  if [[ "$verdict" == "pass" ]]; then
    echo "[verify-generate-live] LIVE: dish and recipe agree on season=$SEASON"
    exit 0
  fi
  attempt=$((attempt + 1))
  [[ "$attempt" -le "$MAX_ATTEMPTS" ]] && sleep "$SLEEP_S"
done
echo "[verify-generate-live] FAILED after $MAX_ATTEMPTS attempts (season=$SEASON)" >&2
exit 1
