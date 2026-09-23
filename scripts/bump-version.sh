#!/usr/bin/env bash
set -euo pipefail
# Stamp a single build version across every version-shaped token in the Kodiak
# frontier web app, so the version is bumped mechanically on change — not by memory.
#
# The version string format is:  v<SEMVER>-<gitshort>-<YYYYMMDD>
#   SEMVER    release number, default "0.1.021" (build-metadata stamp, not a release bump).
#             Override by passing an arg:  ./scripts/bump-version.sh 0.1.013
#   gitshort  `git rev-parse --short=7 HEAD` — used as the build id.
#   YYYYMMDD  `date -u +%Y%m%d` — UTC date.
#
# CHICKEN-AND-EGG NOTE (read before questioning the SHA):
#   gitshort is derived from HEAD *at stamp time*. The commit that carries this
#   stamp is the NEXT commit, so the embedded SHA points at the parent of the
#   deploy commit — not at itself. That is fine and intentional. The invariant we
#   actually enforce is not "SHA == self" but "date + build id change on every
#   bump, and all sinks agree". The git short SHA is the monotonic build id; the
#   UTC date guarantees movement even for two bumps on the same commit is rare —
#   if you bump twice on one commit in one day the string is identical, which is
#   correct (nothing changed) and keeps the script idempotent.
#
# Sinks (every version-shaped token is swept, not just one occurrence per file):
#   web/kodiak-posts-for-todays-frontier/index.html
#       - <link ... styles.css?v=...>        (cache-bust query)
#       - <title>... — v...</title>          (human-visible)
#       - <meta name="kodiak-version" ...>   (machine-readable)
#       - inline #webmcp-manifest JSON "version"
#       - <div id="buildStamp">build ...</div>
#       - <script src="glimmer-proxy.js?v=..."> (cache-bust query)
#   web/kodiak-posts-for-todays-frontier/webmcp.json   "version"
#   web/kodiak-posts-for-todays-frontier/llms.txt      version doc line
#   web/kodiak-posts-for-todays-frontier/pipeline.html <meta name="kodiak-version" ...>
#   web/kodiak-posts-for-todays-frontier/infrastructure.html (same meta)
#
# Usage:
#   ./scripts/bump-version.sh            # stamp with existing semver 0.1.021
#   ./scripts/bump-version.sh 0.1.013    # stamp with a new semver
#   ./scripts/bump-version.sh --check    # read-only: exit 0 if all sinks agree, 1 on drift
#
# Portability: writes use `perl -pi -e`. GNU sed (-i) and BSD/macOS sed (-i '')
# take incompatible in-place flags; perl -pi is identical on linux rocm-aibox and
# macos and perl ships on both by default. No new dependency.

# ---- config -------------------------------------------------------------------
DEFAULT_SEMVER="0.1.021"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB_SRC="${WEB_SRC:-$REPO_ROOT/web/kodiak-posts-for-todays-frontier}"

INDEX="$WEB_SRC/index.html"
WEBMCP="$WEB_SRC/webmcp.json"
LLMS="$WEB_SRC/llms.txt"
PIPELINE="$WEB_SRC/pipeline.html"
INFRA="$WEB_SRC/infrastructure.html"
RECIPES="$WEB_SRC/recipes.html"
DETAILS="$WEB_SRC/details.html"
SINKS=("$INDEX" "$WEBMCP" "$LLMS" "$PIPELINE" "$INFRA" "$RECIPES" "$DETAILS")

# A version-shaped token: MAJOR.MINOR.PATCH, -buildid, -YYYYMMDD (the optional
# leading v is captured separately in the replace so it is preserved, never doubled).
#   semver  = three numeric release components ([0-9]+\.[0-9]+\.[0-9]+)
#   buildid = 7+ hexadecimal git token          ([0-9a-fA-F]{7,})
#   date    = 8 digits                           ([0-9]{8})
# Kept anchored to the token shape so surrounding markup is never touched.
VER_RE='[0-9]+\.[0-9]+\.[0-9]+-[0-9a-fA-F]{7,}-[0-9]{8}'

# ---- helpers ------------------------------------------------------------------

# print every version-shaped token found in a file, one per line (leading v stripped)
tokens_in() {
	local f="$1"
	[[ -f "$f" ]] || return 0
	perl -ne 'while (/(v?[0-9]+\.[0-9]+\.[0-9]+-[0-9a-fA-F]{7,}-[0-9]{8})/g) { my $t=$1; $t =~ s/^v//; print "$t\n"; }' "$f"
}

# --check: read all sinks, collect every distinct token, agree => 0, drift => 1
check_mode() {
	local all found
	all="$(for f in "${SINKS[@]}"; do tokens_in "$f"; done)"
	if [[ -z "$all" ]]; then
		echo "[bump-version] --check: no version tokens found in any sink" >&2
		return 1
	fi
	found="$(printf '%s\n' "$all" | sort -u)"
	local n
	n="$(printf '%s\n' "$found" | grep -c .)"
	if [[ "$n" -eq 1 ]]; then
		echo "[bump-version] --check: OK — all sinks agree at $found"
		return 0
	fi
	echo "[bump-version] --check: DRIFT — sinks disagree, distinct versions:" >&2
	local f ft
	for f in "${SINKS[@]}"; do
		ft="$(tokens_in "$f" | sort -u | paste -sd',' -)"
		echo "[bump-version]   $(basename "$f"): ${ft:-<none>}" >&2
	done
	return 1
}

# ---- main ---------------------------------------------------------------------

# --check short-circuits before any write
if [[ "${1:-}" == "--check" ]]; then
	check_mode
	exit $?
fi

SEMVER="${1:-$DEFAULT_SEMVER}"
if ! [[ "$SEMVER" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
	echo "[bump-version] abort: semver arg '$SEMVER' is not X.Y.Z" >&2
	exit 1
fi

GITSHORT="$(git -C "$REPO_ROOT" rev-parse --short=7 HEAD)"
DATE="$(date -u +%Y%m%d)"
NEW="v${SEMVER}-${GITSHORT}-${DATE}"

echo "[bump-version] new version: $NEW"
echo "[bump-version]   semver=$SEMVER gitshort=$GITSHORT date=$DATE (UTC)"

# preflight: every sink must exist
missing=0
for f in "${SINKS[@]}"; do
	if [[ ! -f "$f" ]]; then
		echo "[bump-version] MISSING: $f" >&2
		missing=1
	fi
done
[[ "$missing" == "1" ]] && { echo "[bump-version] abort: sink file missing" >&2; exit 1; }

# Some tokens carry a leading v (title, buildStamp, cache-bust queries use bare;
# title/buildStamp use vNNN). We replace the whole token INCLUDING an optional
# leading v, and re-emit with the leading v only where the source had one — to
# stay surgical we let perl capture the leading v and preserve it.
stamped=0
for f in "${SINKS[@]}"; do
	before="$(tokens_in "$f" | sort -u | paste -sd',' -)"
	# Replace token, preserving an optional leading 'v' exactly as it appeared.
	VER_RE="$VER_RE" SEMVER="$SEMVER" GITSHORT="$GITSHORT" DATE="$DATE" \
		perl -pi -e '
			my $re = $ENV{VER_RE};
			my $body = "$ENV{SEMVER}-$ENV{GITSHORT}-$ENV{DATE}";
			s/(v?)$re/$1 . $body/ge;
		' "$f"
	after="$(tokens_in "$f" | sort -u | paste -sd',' -)"
	echo "[bump-version] $(basename "$f"): ${before:-<none>} -> ${after:-<none>}"
	stamped=$((stamped + 1))
done

echo "[bump-version] stamped $stamped sinks"

# verify consistency after write; if this fails the regex missed something
if ! check_mode >/dev/null 2>&1; then
	echo "[bump-version] WARNING: post-stamp --check reports drift; inspect sinks" >&2
	check_mode || true
	exit 1
fi
echo "[bump-version] verified: all sinks agree at ${SEMVER}-${GITSHORT}-${DATE}"
