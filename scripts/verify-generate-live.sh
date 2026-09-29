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
    echo "$body" > "${VERIFY_BODY_FILE:-/tmp/verify-generate-live-body.json}"
    break
  fi
  attempt=$((attempt + 1))
  [[ "$attempt" -le "$MAX_ATTEMPTS" ]] && sleep "$SLEEP_S"
done
if [[ "$verdict" != "pass" ]]; then
  echo "[verify-generate-live] FAILED after $MAX_ATTEMPTS attempts (season=$SEASON)" >&2
  exit 1
fi

# Tall-tile extend path (the 503 Bryan caught live came from here — the old
# script only proved the main prompt path). Reuse the fresh 1x1 hero's s3_uri
# so the probe outpaints a real render, not a hand-made key. Retry 3x: a
# single failed fetch must never strand tiles in "preparing" unnoticed.
hero_uri="$(VERIFY_BODY_FILE="${VERIFY_BODY_FILE:-/tmp/verify-generate-live-body.json}" python3 -c "
import json, os
d = json.load(open(os.environ['VERIFY_BODY_FILE']))
for r in d.get('renders', []):
    if r.get('ratio') == '1x1' and r.get('s3_uri'):
        print(r['s3_uri'])
        break
")"
if [[ -z "$hero_uri" ]]; then
  echo "[verify-generate-live] FAILED: no 1x1 s3_uri in main response" >&2
  exit 1
fi
ext_attempt=1
while [[ "$ext_attempt" -le 3 ]]; do
  ext_body="$(curl -s -m 150 -X POST "$API_URL" \
    -H 'Content-Type: application/json' \
    -d "{\"mode\":\"extend\",\"ratio\":\"4x5\",\"hero_s3_uri\":\"$hero_uri\",\"subject\":\"deploy-verify\",\"product\":\"power-cakes\",\"region\":\"Manhattan\"}")" || ext_body=""
  ext_verdict="$(EXT_BODY="$ext_body" python3 -c "
import json, os
try:
    d = json.loads(os.environ.get('EXT_BODY') or '')
except Exception:
    print('unparseable')
    raise SystemExit
print('pass' if d.get('ok') is True else ('error: %s' % d.get('error')))
")"
  echo "[verify-generate-live] extend 4x5 attempt $ext_attempt/3 -> $ext_verdict"
  if [[ "$ext_verdict" == "pass" ]]; then
    break
  fi
  ext_attempt=$((ext_attempt + 1))
  [[ "$ext_attempt" -le 3 ]] && sleep 10
done
if [[ "$ext_verdict" != "pass" ]]; then
  echo "[verify-generate-live] FAILED: extend path: $ext_verdict" >&2
  exit 1
fi

# Scenic-background path: same deploy-verify idea serves seeded or paints
# fresh (long timeout — a Core paint takes minutes on a cold endpoint).
scenic_body="$(curl -s -m 280 -X POST "$API_URL" \
  -H 'Content-Type: application/json' \
  -d '{"mode":"scenic-bg","prompt":"deploy-verify scenic probe","market":"Manhattan, New York"}')" || scenic_body=""
scenic_verdict="$(SCENIC_BODY="$scenic_body" python3 -c "
import json, os
try:
    d = json.loads(os.environ.get('SCENIC_BODY') or '')
except Exception:
    print('unparseable')
    raise SystemExit
print('pass' if d.get('ok') is True and d.get('key') else ('error: %s' % d.get('error')))
")"
echo "[verify-generate-live] scenic-bg -> $scenic_verdict"
if [[ "$scenic_verdict" != "pass" ]]; then
  echo "[verify-generate-live] FAILED: scenic-bg path: $scenic_verdict" >&2
  exit 1
fi
echo "[verify-generate-live] ALL LIVE: main + extend + scenic-bg"
