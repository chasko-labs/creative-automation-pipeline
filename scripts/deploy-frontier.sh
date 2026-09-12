#!/usr/bin/env bash
set -euo pipefail
# Deploy the Kodiak frontier web UI to a selected S3 bucket and CloudFront distribution.
# The target is required and must match the branch: main -> prod, every other named
# branch -> dev. Development resource identifiers are never guessed here.
#
# Usage:
#   ./scripts/deploy-frontier.sh prod
#   ./scripts/deploy-frontier.sh dev
#   DRY_RUN=1 ./scripts/deploy-frontier.sh dev
#
# A dirty worktree is rejected by default. A controlled local emergency may set
# ALLOW_DIRTY_WORKTREE=1.
# AWS_PROFILE must select an existing local operator profile.

TARGET="${1:-}"
if [[ "$#" -ne 1 || ( "$TARGET" != "prod" && "$TARGET" != "dev" ) ]]; then
	echo "[deploy-frontier] usage: $0 <prod|dev>" >&2
	exit 2
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_SRC="${WEB_SRC:-$REPO_ROOT/web/kodiak-posts-for-todays-frontier}"
export WEB_SRC

BRANCH="$(git -C "$REPO_ROOT" symbolic-ref --quiet --short HEAD || true)"
if [[ -z "$BRANCH" || "$BRANCH" == "HEAD" ]]; then
	echo "[deploy-frontier] abort: local checkout must be on a named branch" >&2
	exit 1
fi

EXPECTED_TARGET="dev"
[[ "$BRANCH" == "main" ]] && EXPECTED_TARGET="prod"
if [[ "$TARGET" != "$EXPECTED_TARGET" ]]; then
	echo "[deploy-frontier] abort: branch '$BRANCH' requires target '$EXPECTED_TARGET', not '$TARGET'" >&2
	exit 1
fi

ALLOW_DIRTY_WORKTREE="${ALLOW_DIRTY_WORKTREE:-0}"
if [[ "$ALLOW_DIRTY_WORKTREE" != "1" && -n "$(git -C "$REPO_ROOT" status --porcelain --untracked-files=all)" ]]; then
	echo "[deploy-frontier] abort: worktree is dirty; commit or set ALLOW_DIRTY_WORKTREE=1 for a controlled local emergency" >&2
	exit 1
fi

PROD_BUCKET="frontier-bryanchasko-com"
PROD_DISTRO="E3GEX8LSRX6OYS"
PROD_HOSTNAME="kodiak.bryanchasko.com"
WEBSITE_REGION="us-east-1"

if [[ "$TARGET" == "prod" ]]; then
	BUCKET="$PROD_BUCKET"
	DISTRO="$PROD_DISTRO"
	HOSTNAME="$PROD_HOSTNAME"
else
	: "${KODIAK_DEV_BUCKET:?KODIAK_DEV_BUCKET is required for a dev deploy}"
	: "${KODIAK_DEV_DISTRO:?KODIAK_DEV_DISTRO is required for a dev deploy}"
	: "${KODIAK_DEV_HOSTNAME:?KODIAK_DEV_HOSTNAME is required for a dev deploy}"
	BUCKET="$KODIAK_DEV_BUCKET"
	DISTRO="$KODIAK_DEV_DISTRO"
	HOSTNAME="$KODIAK_DEV_HOSTNAME"
fi

VERSION_CHECK_SOURCE="https://${HOSTNAME}/index.html"
DRY_RUN="${DRY_RUN:-0}"
AWS_ARGS=(--region "$WEBSITE_REGION")
if [[ -z "${AWS_PROFILE:-}" ]]; then
	echo "[deploy-frontier] abort: AWS_PROFILE must be explicitly set for local deployment" >&2
	exit 1
fi
PROFILE="$AWS_PROFILE"
AWS_ARGS+=(--profile "$PROFILE")
AWS_AUTH_CONTEXT="local profile $PROFILE"

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
	"favicon.ico|favicon.ico|image/x-icon"
	"favicon.svg|favicon.svg|image/svg+xml"
	"apple-touch-icon.png|apple-touch-icon.png|image/png"
	"robots.txt|robots.txt|text/plain"
)

# asset directories to sync wholesale. `aws s3 sync` copies whatever is present
# (and only what changed), so new files ship without touching this script. This
# is the durable fix for prod 404s — the page references assets/, data/, fonts/,
# design/tokens/, js/, input_assets/ that the per-file list above never uploaded.
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

echo "[deploy-frontier] branch:  $BRANCH"
echo "[deploy-frontier] target:  $TARGET"
echo "[deploy-frontier] source:  $WEB_SRC"
echo "[deploy-frontier] version source: $VERSION_CHECK_SOURCE"
echo "[deploy-frontier] target storage: s3://$BUCKET (CloudFront $DISTRO)"
echo "[deploy-frontier] auth: $AWS_AUTH_CONTEXT / $WEBSITE_REGION"
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

# preflight: AWS identity must be valid before any remote mutation
if ! aws sts get-caller-identity "${AWS_ARGS[@]}" >/dev/null 2>&1; then
	echo "[deploy-frontier] abort: AWS credentials are not valid for $AWS_AUTH_CONTEXT" >&2
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
		"${AWS_ARGS[@]}" --only-show-errors
done

# sync whole asset directories. sync sets content-type via the runner's mimetypes
# DB; that DB varies across local execution environments, so after each bulk sync we
# re-put the fragile types (.svg, .woff2, .json) with an explicit --content-type
# and --metadata-directive REPLACE. A deployed-but-mistyped file (e.g. svg served
# as application/octet-stream) fails to render even though it 200s — the re-puts
# make correctness independent of the runner. .png/.css/.html guess reliably.
for dir in "${DIRS[@]}"; do
	echo "[deploy-frontier] sync $dir/ -> s3://$BUCKET/$dir/"
	run aws s3 sync "$WEB_SRC/$dir" "s3://$BUCKET/$dir" \
		"${AWS_ARGS[@]}" --only-show-errors

	# re-put the types where a wrong guess breaks loading/rendering
	for ext_ct in "svg|image/svg+xml" "woff2|font/woff2" "json|application/json" "js|application/javascript"; do
		IFS='|' read -r ext ct <<<"$ext_ct"
		echo "[deploy-frontier]   fix content-type *.$ext -> $ct in $dir/"
		run aws s3 cp "s3://$BUCKET/$dir" "s3://$BUCKET/$dir" \
			--recursive --exclude "*" --include "*.$ext" \
			--content-type "$ct" --metadata-directive REPLACE \
			"${AWS_ARGS[@]}" --only-show-errors
	done
done

# invalidate the selected distribution so the selected hostname serves the new files
echo "[deploy-frontier] invalidate CloudFront $DISTRO /*"
if [[ "$DRY_RUN" == "1" ]]; then
	echo "[dry-run] aws cloudfront create-invalidation --distribution-id $DISTRO --paths '/*' ${AWS_ARGS[*]}"
else
	inv_id="$(aws cloudfront create-invalidation \
		--distribution-id "$DISTRO" --paths "/*" \
		"${AWS_ARGS[@]}" \
		--query 'Invalidation.Id' --output text)"
	echo "[deploy-frontier] invalidation: $inv_id"
fi

echo "[deploy-frontier] done: $TARGET on $BRANCH"
echo "[deploy-frontier] verify: curl -fsS \"$VERSION_CHECK_SOURCE\" | grep -o '0\\.[0-9.]*-[0-9a-f]*-[0-9]*' | head -1"
