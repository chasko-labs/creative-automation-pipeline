#!/usr/bin/env bash
set -euo pipefail
# Build the reviewer zip: a clean copy of main + an offline-rendered README + a
# START-HERE launcher that opens the live site and the rendered README.
#
# Produces a self-contained package a reviewer can unzip and browse offline —
# README opens as rendered HTML (not raw markdown), START-HERE opens both windows.
#
# Usage:
#   ./scripts/build-reviewer-package.sh                 # -> /tmp/kodiak-reviewer/kodiak-reviewer-package.zip
#   OUT_DIR=/some/dir ./scripts/build-reviewer-package.sh
#
# Env:
#   REF        git ref to export      (default: origin/main)
#   OUT_DIR    staging + zip dir       (default: /tmp/kodiak-reviewer)
#   LIVE_URL   site the launcher opens (default: https://kodiak.bryanchasko.com/)

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REF="${REF:-origin/main}"
OUT_DIR="${OUT_DIR:-/tmp/kodiak-reviewer}"
LIVE_URL="${LIVE_URL:-https://kodiak.bryanchasko.com/}"
PREFIX="creative-automation-pipeline"
STAGE="$OUT_DIR/$PREFIX"

# The 2:55 walkthrough is a REQUIRED artifact. It lives in S3 (stable source),
# not /tmp (ephemeral — the old /tmp-only path warned+skipped and shipped a ZIP
# with START-HERE video links but zero MP4 entries). Fetch fails closed below.
REVIEWER_VIDEO_S3_URI="${REVIEWER_VIDEO_S3_URI:-s3://frontier-bryanchasko-com/kodiak-demo-2m55.mp4}"
AWS_PROFILE_PKG="${AWS_PROFILE:-bryanchasko-kiro}"
AWS_REGION_PKG="${AWS_REGION:-us-east-1}"
VIDEO_NAME="kodiak-demo-2m55.mp4"

echo "[pkg] ref=$REF  out=$OUT_DIR"
cd "$REPO_ROOT"
git fetch origin --quiet || true

rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"

# 1. clean export of the ref (tracked files only — no .git, no local cruft)
git archive "$REF" --prefix="$PREFIX/" -o "$OUT_DIR/repo.tar"
tar -xf "$OUT_DIR/repo.tar" -C "$OUT_DIR"
rm "$OUT_DIR/repo.tar"
echo "[pkg] exported $(find "$STAGE" -type f | wc -l | tr -d ' ') files"

# 2. render the WHOLE markdown doc tree -> .html (offline, self-contained, cross-linked
#    locally) inside the staged copy. Rewrites private-GitHub + relative .md links to
#    local .html so reviewers navigate the entire doc set through the zip, no network.
python3 "$REPO_ROOT/scripts/gen-doc-site.py" \
	"$STAGE" \
	"$REPO_ROOT/scripts/vendor/marked.min.js"

# 2b. patch the demo's password gate for the LOCAL package only — a file:// page is
#     the reviewer's offline copy, so auto-unlock instead of prompting. The hosted
#     https:// site keeps its gate; only the packaged file:// copy is patched.
python3 - "$STAGE/web/kodiak-posts-for-todays-frontier/index.html" <<'PY'
import sys
from pathlib import Path

p = Path(sys.argv[1])
if not p.exists():
    print(f"[pkg] gate patch skipped — no index.html at {p}", file=sys.stderr)
    raise SystemExit(0)

html = p.read_text(encoding="utf-8")
marker = "if(sessionStorage.getItem('kodiak_gate')==='cakes') return;"
inject = (
    "if(location.protocol==='file:'){try{sessionStorage.setItem('kodiak_gate','cakes')}"
    "catch(e){} return;}  // offline reviewer package — no gate\n    "
    + marker
)
if marker in html and "offline reviewer package" not in html:
    html = html.replace(marker, inject, 1)
    p.write_text(html, encoding="utf-8")
    print("[pkg] patched demo gate: file:// copy auto-unlocks (hosted site untouched)")
else:
    print("[pkg] gate patch: marker not found or already patched — no change")
PY

# 3. write the START-HERE launcher pointing at the RENDERED readme.
#    Source the palette from the SAME derived :root block the doc-site uses, so the
#    launcher and the rendered docs never drift from design/tokens/kodiak.json (the
#    single source of truth). gen-doc-site.py --emit-root-css reads the staged token
#    file and prints the canonical :root block; if that ever fails, fall back to the
#    CORRECTED canonical literals (parch #FFF8F0, kraft #F4EDE6 — never the old
#    drifted #faf6ef/#efe7db).
ROOT_CSS="$(python3 "$REPO_ROOT/scripts/gen-doc-site.py" --emit-root-css "$STAGE" 2>/dev/null || true)"
if [ -z "$ROOT_CSS" ]; then
	ROOT_CSS=$':root {\n  --bear: #3B2316; --blaze: #E8530E; --pine: #1A3C34;\n  --kraft: #F4EDE6; --parch: #FFF8F0; --ink: #1A1110; --muted: #6B5A53;\n}'
fi
cat >"$STAGE/START-HERE.html" <<HTML
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Kodiak Cakes Creative Automation Pipeline — Reviewer Package</title>
<style>
  /* Palette derived from design/tokens/kodiak.json at package-build time (shared
     with the doc-site via gen-doc-site.py --emit-root-css) — no drift, no duplicated hex. */
  $ROOT_CSS
  * { box-sizing:border-box; }
  body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
    background:linear-gradient(160deg,var(--parch),var(--kraft)); color:var(--bear);
    min-height:100vh; display:flex; align-items:center; justify-content:center; padding:2rem; }
  .card { max-width:720px; background:#fff; border:1px solid #e4d8c6; border-radius:14px;
    box-shadow:0 10px 40px rgba(59,35,22,.12); overflow:hidden; }
  .hdr { background:var(--bear); color:var(--parch); padding:1.6rem 2rem; }
  .hdr h1 { margin:0 0 .3rem; font-size:1.35rem; }
  .hdr p { margin:0; opacity:.82; font-size:.95rem; }
  .bar { height:6px; background:var(--blaze); }
  .body { padding:2rem; }
  .body h2 { font-size:1rem; text-transform:uppercase; letter-spacing:.06em; color:var(--pine); margin:0 0 .8rem; }
  .btns { display:flex; gap:1rem; flex-wrap:wrap; margin:0 0 1.6rem; }
  a.btn { display:inline-block; padding:.85rem 1.3rem; border-radius:9px; text-decoration:none; font-weight:700; font-size:.98rem; }
  a.live { background:var(--blaze); color:#fff; }
  a.readme { background:var(--parch); color:var(--bear); border:1px solid #d8c8b2; }
  a.btn:hover { filter:brightness(1.06); }
  ul { margin:.4rem 0 0; padding-left:1.2rem; line-height:1.6; font-size:.94rem; }
  code { background:var(--kraft); padding:.1rem .35rem; border-radius:4px; font-size:.88em; }
  .note { margin-top:1.6rem; padding:1rem 1.2rem; background:var(--parch); border-left:3px solid var(--blaze); border-radius:6px; font-size:.9rem; line-height:1.55; }
</style>
</head>
<body>
  <div class="card">
    <div class="hdr">
      <h1>Kodiak Cakes &mdash; Creative Automation Pipeline</h1>
      <p>Reviewer package. Two windows open automatically: the live site and the README.</p>
    </div>
    <div class="bar"></div>
    <div class="body">
      <h2>Start here</h2>
      <div class="btns">
        <a class="btn live" href="$LIVE_URL" target="_blank" rel="noopener">Open the live site &rarr;</a>
        <a class="btn readme" href="README.html" target="_blank" rel="noopener">Open the README &rarr;</a>
        <a class="btn readme" href="kodiak-demo-2m55.mp4" target="_blank" rel="noopener">Watch the 2:55 demo &rarr;</a>
      </div>
      <h2>2-minute walkthrough</h2>
      <video controls preload="metadata" style="width:100%;border-radius:10px;border:1px solid #e4d8c6;margin-bottom:1rem"><source src="kodiak-demo-2m55.mp4" type="video/mp4">Your browser can't play embedded video &mdash; <a href="kodiak-demo-2m55.mp4">download the walkthrough</a>.</video>
      <h2>What makes it novel</h2>
      <ul>
        <li><strong>Amazon-first agentic pipeline</strong> &mdash; one brief fans out to hundreds of localized, on-brand ads. Every model call is Amazon Bedrock (no third-party), enforced at the IAM layer.</li>
        <li><strong>Nova Pro vision composition</strong> &mdash; the hero step reads your real product pack shots with Nova Pro (Converse, vision) and composes headline + layout from the actual asset, not a text-to-image guess. Real assets in, on-brand creative out.</li>
        <li><strong>Nova multimodal embeddings + S3 Vectors</strong> &mdash; 3,000+ real assets embedded (<code>nova-2-multimodal-embeddings</code>, 1024-dim) into managed S3 Vectors, so each market retrieves what already worked there.</li>
        <li><strong>76-market localization</strong> &mdash; per-market top-2 languages (21 total), Nova Micro &rarr; dialect swap &rarr; Amazon Translate, BCP-47 tagged. Data-driven, not hardcoded.</li>
        <li><strong>Panda CSS design tokens</strong> &mdash; brand palette, spacing, and aspect ratios live as W3C design tokens (<code>design/tokens/kodiak.json</code>) generated into type-safe CSS; the compose step is deterministic from those same tokens (bear at 24,24, 68% message bar, 8px Blaze border).</li>
        <li><strong>Full AWS backbone</strong> &mdash; S3 DAM (KMS, versioned), DynamoDB market memory, CloudFront delivery, local quality checks, X-Ray + CloudWatch observability, Bedrock model-invocation logging.</li>
      </ul>
      <h2>How it works &mdash; open during the walkthrough</h2>
      <ul>
        <li><a href="web/kodiak-posts-for-todays-frontier/details.html" target="_blank" rel="noopener">Design System Inventory</a> &mdash; tokens, type, logo law, Spectrum bridge</li>
        <li><a href="web/kodiak-posts-for-todays-frontier/pipeline.html" target="_blank" rel="noopener">Creative generation, localization, and AI</a> &mdash; briefs, contracts, Pillow compose</li>
        <li><a href="web/kodiak-posts-for-todays-frontier/infrastructure.html" target="_blank" rel="noopener">Secure hosting and delivery</a> &mdash; Bedrock batch, local dialing to AWS transfer, S3 + CloudFront</li>
        <li>Layout is code: <code>src/creative_automation/compose.py</code> pastes cutouts verbatim with Pillow; the model never touches logo or type.</li>
        <li>Looks dial free, then transfer: the frozen SDXL ComfyUI recipe (<code>docs/local-comfyui-recipe-art.md</code>) moves to Bedrock Stable Image Core with the same prompt tails (<code>src/creative_automation/recipe_art.py</code>).</li>
        <li>Logo default is <code>input_assets/brand/logo.png</code>; the header bear crossfades to the alt logo past 40px scroll (<code>web/kodiak-posts-for-todays-frontier/js/scroll-swap.js</code>).</li>
      </ul>
      <h2>What's in this package</h2>
      <ul>
        <li><code>README.html</code> &mdash; the project readme, rendered; every in-project link opens the local rendered doc (fully navigable offline, no GitHub)</li>
        <li><code>src/</code> + <code>rust/</code> &mdash; the full pipeline codebase</li>
        <li><code>tests/</code>, <code>infra/</code>, <code>docs/archive/buildspec-retired.md</code> &mdash; tests + infrastructure-as-code + CI</li>
        <li><code>docs/architecture/</code> &mdash; system overview (6 diagrams) + literal inventory</li>
        <li><code>docs/assets/previews/</code> &mdash; real branded images the pipeline produced</li>
      </ul>
      <div class="note">
        <strong>North star:</strong> a prompt in &rarr; a customized, on-brand campaign out &mdash; localized,
        compliance-checked, in all three ratios. The full pipeline is live and proven today: retrieve brand
        context (S3 Vectors) &rarr; Amazon Nova Pro vision composes the hero from your real product photography
        &rarr; localize across 73 markets &rarr; deterministic Panda-token compose &rarr; brand + legal gate,
        all exercised by the test suite and running Amazon-first on Bedrock end to end. Heroes are grounded in
        your 3,000+ real brand assets and composed by Nova Pro &mdash; on-brand and rights-clean by design,
        not hallucinated pixels. The hosted one-button demo at
        <a href="$LIVE_URL">kodiak.bryanchasko.com</a> is wired end-to-end: type a brief, pick a product
        (e.g. power-cakes), click Create &mdash; the button POSTs to the live generate endpoint, Nova Pro
        composes a real branded hero, and the page shows it with a <code>source: Nova Pro</code> badge.
      </div>

      </div>
    </div>
  </div>
  <script>
    try {
      window.open("$LIVE_URL", "_blank", "noopener");
      window.open("README.html", "_blank", "noopener");
    } catch (e) { /* buttons are the fallback */ }
  </script>
</body>
</html>
HTML
echo "[pkg] wrote START-HERE.html + README.html"

# 3b. fetch the REQUIRED demo video from S3 into the staged package (before zip).
#     Fail closed: a missing/empty video is a hard error, never a warn+skip. The
#     old /tmp-only path shipped a broken ZIP (video links, no MP4). Never again.
echo "[pkg] fetching required video: $REVIEWER_VIDEO_S3_URI (profile $AWS_PROFILE_PKG region $AWS_REGION_PKG)"
if ! aws s3 cp "$REVIEWER_VIDEO_S3_URI" "$STAGE/$VIDEO_NAME" \
	--profile "$AWS_PROFILE_PKG" --region "$AWS_REGION_PKG"; then
	echo "[pkg] FATAL: could not fetch required video from $REVIEWER_VIDEO_S3_URI" >&2
	echo "[pkg]        the reviewer package is not shippable without the walkthrough." >&2
	exit 1
fi
if [ ! -s "$STAGE/$VIDEO_NAME" ]; then
	echo "[pkg] FATAL: fetched video is missing or zero bytes: $STAGE/$VIDEO_NAME" >&2
	exit 1
fi
echo "[pkg] bundled demo video ($(wc -c <"$STAGE/$VIDEO_NAME" | tr -d ' ') bytes)"

# 4. zip it
cd "$OUT_DIR"
rm -f kodiak-reviewer-package.zip
zip -rq kodiak-reviewer-package.zip "$PREFIX" -x "*.pyc" -x "*__pycache__*" -x "*.DS_Store"
echo "[pkg] built $OUT_DIR/kodiak-reviewer-package.zip ($(du -h kodiak-reviewer-package.zip | cut -f1))"

# 4b. fail-closed ZIP verification: the video entry MUST exist and be non-empty
#     inside the archive. This is the gate that catches the exact failure mode
#     that shipped before — START-HERE video links with no MP4 in the ZIP.
python3 - "$OUT_DIR/kodiak-reviewer-package.zip" "$PREFIX/$VIDEO_NAME" <<'PY'
import sys
import zipfile

zip_path, entry = sys.argv[1], sys.argv[2]
with zipfile.ZipFile(zip_path) as z:
    try:
        info = z.getinfo(entry)
    except KeyError:
        print(f"[pkg] FATAL: required entry missing from ZIP: {entry}", file=sys.stderr)
        raise SystemExit(1)
    if info.file_size <= 0:
        print(f"[pkg] FATAL: required entry is zero bytes in ZIP: {entry}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[pkg] verified video in ZIP: {entry} = {info.file_size} bytes")
PY

# The canonical package key is served by CloudFront from the adobechallenge/ PREFIX,
# not the bucket root. Upload MUST target s3://frontier-bryanchasko-com/adobechallenge/...
# or the refresh lands at a dead key and never goes live. The canonical key is
# uploaded no-cache so a re-push is served immediately; invalidate after upload
# (distribution E3GEX8LSRX6OYS). A content-addressed versioned key is also emitted
# so emergency links can bypass any stale canonical cache — that key is immutable.
SHORT_SHA="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || date -u +%Y%m%d%H%M%S)"
echo "[pkg] canonical upload:  aws s3 cp $OUT_DIR/kodiak-reviewer-package.zip s3://frontier-bryanchasko-com/adobechallenge/kodiak-reviewer-package.zip --content-type application/zip --cache-control 'no-cache, max-age=0, must-revalidate' --profile $AWS_PROFILE_PKG --region $AWS_REGION_PKG"
echo "[pkg] versioned upload:  aws s3 cp $OUT_DIR/kodiak-reviewer-package.zip s3://frontier-bryanchasko-com/adobechallenge/kodiak-reviewer-package-$SHORT_SHA.zip --content-type application/zip --cache-control 'public, max-age=31536000, immutable' --profile $AWS_PROFILE_PKG --region $AWS_REGION_PKG"
echo "[pkg] invalidate:        aws cloudfront create-invalidation --distribution-id E3GEX8LSRX6OYS --paths '/adobechallenge/kodiak-reviewer-package.zip' --profile $AWS_PROFILE_PKG --region $AWS_REGION_PKG"
