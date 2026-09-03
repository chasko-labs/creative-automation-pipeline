#!/usr/bin/env bash
set -euo pipefail
# Deploy the Kodiak frontier web UI to S3 + invalidate CloudFront.
# One command replaces the manual `aws s3 cp` + invalidation dance.
# Idempotent, local-first. Deploys the committed web source, not a worktree.
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
	"design/styles.css|design/styles.css|text/css"
	"webmcp.json|webmcp.json|application/json"
	"glimmer-proxy.js|glimmer-proxy.js|application/javascript"
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

# preflight: SSO creds must be live, fail fast with a clear message
if ! aws sts get-caller-identity --profile "$PROFILE" --region "$REGION" >/dev/null 2>&1; then
	echo "[deploy-frontier] abort: AWS creds not valid for profile $PROFILE" >&2
	echo "[deploy-frontier] run: ~/.kiro/bin/check-sso-status" >&2
	exit 1
fi

# push each file with its content-type; index.html gets no-cache so updates show
paths=()
for entry in "${FILES[@]}"; do
	IFS='|' read -r rel key ctype <<<"$entry"
	cache="max-age=300"
	[[ "$key" == "index.html" ]] && cache="no-cache"
	echo "[deploy-frontier] cp $rel -> s3://$BUCKET/$key ($ctype)"
	run aws s3 cp "$WEB_SRC/$rel" "s3://$BUCKET/$key" \
		--content-type "$ctype" --cache-control "$cache" \
		--profile "$PROFILE" --region "$REGION" --only-show-errors
	paths+=("/$key")
done

# invalidate CloudFront so the new files serve immediately
echo "[deploy-frontier] invalidate CloudFront ${paths[*]}"
if [[ "$DRY_RUN" == "1" ]]; then
	echo "[dry-run] aws cloudfront create-invalidation --distribution-id $DISTRO --paths ${paths[*]}"
else
	inv_id="$(aws cloudfront create-invalidation \
		--distribution-id "$DISTRO" --paths "${paths[@]}" \
		--profile "$PROFILE" --region "$REGION" \
		--query 'Invalidation.Id' --output text)"
	echo "[deploy-frontier] invalidation: $inv_id"
fi

echo "[deploy-frontier] done. verify: curl -sSI https://kodiak.bryanchasko.com/index.html | head -3"
