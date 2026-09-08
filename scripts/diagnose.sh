#!/usr/bin/env bash
# diagnose.sh — visual inspector + lint + glimmer vision ping-pong
# - Lint (htmlhint, ruff) → chromium screenshot (local 8099 ?cakes=1 + remote d37333 ?cakes=1) → glimmer vision diagnose → patch → sync
# - NOTE (#234): ?cakes=1 is inert (URL bypass removed) — screenshots now capture the courtesy screen, curl checks unaffected (still 200).
# - Zero CodeBuild minutes: all local ops (s3 sync + /* invalidate)
# Usage: ./scripts/diagnose.sh [--local-only] [--remote-only]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WEB="$ROOT/web/kodiak-posts-for-todays-frontier/index.html"
SNAP_DIR="$HOME/snap/chromium/3507"
GLIMMER_URL="${GLIMMER_URL:-http://127.0.0.1:8181/v1}"
CF_ID="${CF_ID:-E3GEX8LSRX6OYS}"
CF_ORIGIN="${CF_ORIGIN:-https://d37333alc7ojpl.cloudfront.net}"

echo "=== diagnose.sh — lint + screenshot → glimmer vision ==="
echo "Web: $WEB  Glimmer: $GLIMMER_URL  CF: $CF_ID"

# 1. Lint local (no cloud)
echo "--- htmlhint ---"
if command -v npx >/dev/null 2>&1; then npx --yes htmlhint "$WEB" || true; else echo "npx not found, skip htmlhint"; fi
echo "--- ruff ---"
if command -v uv >/dev/null 2>&1; then uv run ruff check src/creative_automation/ 2>&1 | head -n 20 || true; fi

# 2. Ensure local http
if ! curl -s http://127.0.0.1:8099/?cakes=1 >/dev/null 2>&1; then
  echo "Starting local http://127.0.0.1:8099 ..."
  setsid -f python3 -m http.server 8099 --directory "$ROOT/web/kodiak-posts-for-todays-frontier" </dev/null >>/tmp/visual-http.log 2>&1 || true
  sleep 2
fi

# 3. Screenshots (chromium snap writes to SNAP_DIR)
mkdir -p "$HOME/snap/chromium/3507" 2>/dev/null || true
LOCAL_PNG="$SNAP_DIR/kodiak-diagnose-local.png"
REMOTE_PNG="$SNAP_DIR/kodiak-diagnose-remote.png"
if command -v chromium >/dev/null 2>&1; then
  echo "--- chromium local ---"
  chromium --headless --no-sandbox --disable-gpu --window-size=1280,900 --screenshot="$LOCAL_PNG" "http://127.0.0.1:8099/?cakes=1" 2>&1 | tail -n 3 || true
  ls -lh "$LOCAL_PNG" 2>/dev/null | head -n 1 || true
  echo "--- chromium remote ---"
  chromium --headless --no-sandbox --disable-gpu --window-size=1280,900 --screenshot="$REMOTE_PNG" "$CF_ORIGIN/?cakes=1" 2>&1 | tail -n 3 || true
  ls -lh "$REMOTE_PNG" 2>/dev/null | head -n 1 || true
else
  echo "chromium not found — skip screenshots"
fi

# 4. Glimmer vision diagnose (if 8181 up, else fallback to Nova unlimited note)
echo "--- glimmer diagnose (local 8181, else Nova fallback) ---"
HTML_SNIP=$(head -c 2000 "$WEB" 2>/dev/null || echo "")
if curl -s "$GLIMMER_URL/models" >/dev/null 2>&1; then
  echo "Glimmer 8181 up — calling vision diagnose..."
  # Use python glimmer client if httpx available
  PYTHONPATH="$ROOT/src" python3 - <<PY || true
from creative_automation.glimmer import glimmer_diagnose_frontpage
import pathlib
html = pathlib.Path("$WEB").read_text()[:2000]
res = glimmer_diagnose_frontpage(html, "brand red #B51E14/#382316, brown 20pt URB, Bear 24,24, gin headings, museo-sans body")
print(res or "(no glimmer response, check supervisor)")
PY
else
  echo "Glimmer 8181 not reachable (CPU NGL=0 fallback or supervisor down) — hosted will use Nova unlimited (Canvas/Micro/Translate/Embeddings per-image/per-translate/per-char + CloudFront per-GB documented, not degraded). Start glimmer via: python3 muse-code/glimmer/run-supervisor.sh"
  echo "HTML snippet (first 200 chars): ${HTML_SNIP:0:200}"
fi

# 5. Cost doc reminder (always document, never degrade Nova)
echo "--- Nova cost doc (always, unlimited) ---"
echo "Canvas per-image + Micro per-translate + Translate per-char + CloudFront per-GB — unlimited budget, go ham on amazon.nova-2-multimodal-embeddings-v1:0 1024"

echo "=== done — if fixes needed: edit $WEB, then: AWS_PROFILE=bryanchasko-kiro aws s3 sync web/kodiak-posts-for-todays-frontier/ s3://frontier-bryanchasko-com/ --delete && aws s3 cp data/localization/market-languages.json s3://frontier-bryanchasko-com/data/localization/market-languages.json && aws cloudfront create-invalidation --distribution-id $CF_ID --paths '/*' ==="
