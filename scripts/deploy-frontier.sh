#!/usr/bin/env bash
set -euo pipefail
# Deploy the Kodiak frontier web UI to S3 + invalidate CloudFront.
# One command replaces the manual `aws s3 cp` + invalidation dance.
# Idempotent, local-first. Deploys the committed web source, not a worktree.
#
# Deploys the 8 core top-level files (index.html, details.html, pipeline.html, infrastructure.html, design/styles.css,
# webmcp.json, glimmer-proxy.js, llms.txt) AND the asset directories the page references:
# assets/ (logos, textures, partners/), data/ (localization, products, ...),
# fonts/ (NotoSans *.woff2), design/ (tokens/), js/ (extracted classic scripts),
# input_assets/ (default heroes referenced by generate.js + preloaded in index.html).
# Directory syncs use `aws s3 sync`
# so newly added files ship automatically without editing this script — this is
# the root-cause fix for prod 404s where referenced assets were never uploaded.
#
# Invariant: the app version must be stamped via scripts/bump-version.sh.
# Deploy refuses on version drift — if index.html / glimmer-proxy / webmcp.json
# disagree (content changed without a bump), the deploy aborts and tells you to
# run ./scripts/bump-version.sh. Deploy never auto-bumps (that would hide intent).
#
# Usage:
#   ./scripts/deploy-frontier.sh              # deploy to production
#   DRY_RUN=1 ./scripts/deploy-frontier.sh    # show what would deploy, touch nothing
#
# Env overrides (production defaults baked in):
#   FRONTIER_BUCKET   S3 bucket            (default: frontier-bryanchasko-com)
#   FRONTIER_DISTRO   CloudFront dist id   (default: E3GEX8LSRX6OYS)
#   AWS_PROFILE       SSO profile          (default: bryanchasko-kiro)
#   AWS_REGION        region               (default: us-east-1)
#   WEB_SRC           web source dir       (default: web/kodiak-posts-for-todays-frontier)

BUCKET="${FRONTIER_BUCKET:-frontier-bryanchasko-com}"
DISTRO="${FRONTIER_DISTRO:-E3GEX8LSRX6OYS}"
PROFILE="${AWS_PROFILE:-bryanchasko-kiro}"
REGION="${AWS_REGION:-us-east-1}"
DRY_RUN="${DRY_RUN:-0}"

# resolve web source relative to repo root (script lives in scripts/)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_SRC="${WEB_SRC:-$REPO_ROOT/web/kodiak-posts-for-todays-frontier}"

# files to deploy: local relative path -> s3 key -> content-type
# keep this list in sync with what index.html references
FILES=(
	"index.html|index.html|text/html"
	"details.html|details.html|text/html"
	"pipeline.html|pipeline.html|text/html"
	"infrastructure.html|infrastructure.html|text/html"
	"design/styles.css|design/styles.css|text/css"
	"webmcp.json|webmcp.json|application/json"
	"glimmer-proxy.js|glimmer-proxy.js|application/javascript"
	"llms.txt|llms.txt|text/markdown"
)

# asset directories to sync wholesale. `aws s3 sync` copies whatever is present
# (and only what changed), so new files ship without touching this script. This
# is the durable fix for prod 404s — the page references assets/, data/, fonts/,
# design/tokens/, js/ that the per-file list above never uploaded.
DIRS=(
	"assets"
	"data"
	"fonts"
	"design"
	"js"
	"input_assets"
)

run() {
	if [[ "$DRY_RUN" == "1" ]]; then
		echo "[dry-run] $*"
	else
		"$@"
	fi
}

echo "[deploy-frontier] source:  $WEB_SRC"
echo "[deploy-frontier] target:  s3://$BUCKET  (CloudFront $DISTRO)"
echo "[deploy-frontier] profile: $PROFILE / $REGION"
[[ "$DRY_RUN" == "1" ]] && echo "[deploy-frontier] DRY RUN — no changes will be made"

# preflight: every source file must exist, or we abort before touching prod
missing=0
for entry in "${FILES[@]}"; do
	IFS='|' read -r rel _key _ctype <<<"$entry"
	if [[ ! -f "$WEB_SRC/$rel" ]]; then
		echo "[deploy-frontier] MISSING: $WEB_SRC/$rel"
		missing=1
	fi
done
if [[ "$missing" == "1" ]]; then
	echo "[deploy-frontier] abort: one or more source files missing" >&2
	exit 1
fi

# preflight: every asset directory must exist too, or the dir syncs below are
# silent no-ops that leave the page 404ing on assets. Fail fast instead.
for dir in "${DIRS[@]}"; do
	if [[ ! -d "$WEB_SRC/$dir" ]]; then
		echo "[deploy-frontier] MISSING dir: $WEB_SRC/$dir"
		missing=1
	fi
done
if [[ "$missing" == "1" ]]; then
	echo "[deploy-frontier] abort: one or more source directories missing" >&2
	exit 1
fi

# preflight: SSO creds must be live, fail fast with a clear message
if ! aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" >/dev/null 2>&1; then
	echo "[deploy-frontier] abort: AWS creds not valid for profile $PROFILE" >&2
	echo "[deploy-frontier] run: ~/.kiro/bin/check-sso-status" >&2
	exit 1
fi

# preflight: version must be consistent across all sinks. If content changed
# without a bump the sinks drift — refuse rather than ship a stale/split version.
# Honors DRY_RUN (still checks; a dry run of a drifted tree should surface the drift).
if ! "$REPO_ROOT/scripts/bump-version.sh" --check; then
	echo "[deploy-frontier] abort: version drift across index.html / glimmer-proxy / webmcp.json — run ./scripts/bump-version.sh before deploying" >&2
	exit 1
fi

# push each file with its content-type; index.html gets no-cache so updates show
for entry in "${FILES[@]}"; do
	IFS='|' read -r rel key ctype <<<"$entry"
	cache="max-age=300"
	[[ "$key" == "index.html" ]] && cache="no-cache"
	echo "[deploy-frontier] cp $rel -> s3://$BUCKET/$key ($ctype)"
	run aws s3 cp "$WEB_SRC/$rel" "s3://$BUCKET/$key" \
		--content-type "$ctype" --cache-control "$cache" \
		--profile "$PROFILE" --region "$REGION" --only-show-errors
done

# sync whole asset directories. sync sets content-type via the runner's mimetypes
# DB; that DB varies across hosts (local vs CodeBuild), so after each bulk sync we
# re-put the fragile types (.svg, .woff2, .json) with an explicit --content-type
# and --metadata-directive REPLACE. A deployed-but-mistyped file (e.g. svg served
# as application/octet-stream) fails to render even though it 200s — the re-puts
# make correctness independent of the runner. .png/.css/.html guess reliably.
for dir in "${DIRS[@]}"; do
	echo "[deploy-frontier] sync $dir/ -> s3://$BUCKET/$dir/"
	run aws s3 sync "$WEB_SRC/$dir" "s3://$BUCKET/$dir" \
		--profile "$PROFILE" --region "$REGION" --only-show-errors

	# re-put the types where a wrong guess breaks loading/rendering
	for ext_ct in "svg|image/svg+xml" "woff2|font/woff2" "json|application/json" "js|application/javascript"; do
		IFS='|' read -r ext ct <<<"$ext_ct"
		echo "[deploy-frontier]   fix content-type *.$ext -> $ct in $dir/"
		run aws s3 cp "s3://$BUCKET/$dir" "s3://$BUCKET/$dir" \
			--recursive --exclude "*" --include "*.$ext" \
			--content-type "$ct" --metadata-directive REPLACE \
			--profile "$PROFILE" --region "$REGION" --only-show-errors
	done
done

# invalidate CloudFront so the new files serve immediately. We now push whole
# directories (assets/, data/, fonts/, design/) whose membership changes over
# time, so enumerating exact paths is brittle. "/*" invalidates everything and
# counts as a single invalidation path — clean and cheap for a deploy this size.
echo "[deploy-frontier] invalidate CloudFront /*"
if [[ "$DRY_RUN" == "1" ]]; then
	echo "[dry-run] aws cloudfront create-invalidation --distribution-id $DISTRO --paths /*"
else
	inv_id="$(aws cloudfront create-invalidation \
		--distribution-id "$DISTRO" --paths "/*" \
		--profile "$PROFILE" --region "$REGION" \
		--query 'Invalidation.Id' --output text)"
	echo "[deploy-frontier] invalidation: $inv_id"
	# Edge settle (~3 min): wait for completion so the verify below reads the
	# new build, not stale edge cache. See docs/fleet-build-deploy-notes.md.
	echo "[deploy-frontier] waiting for invalidation $inv_id to complete..."
	aws cloudfront wait invalidation-completed \
		--distribution-id "$DISTRO" --id "$inv_id" \
		--profile "$PROFILE" --region "$REGION"
	echo "[deploy-frontier] edge settled."
fi

echo "[deploy-frontier] done. verify: curl -sSI https://kodiak.bryanchasko.com/index.html | head -3"
