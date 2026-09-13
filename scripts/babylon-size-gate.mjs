// babylon-size-gate — LOCAL / OPT-IN size ceiling for the committed Babylon
// ENTRY module.
//
// The bundle is now built as an ECMAScript module with esbuild code-splitting
// (see scripts/build-ember.mjs): the entry emits as
// vendor/kodiak-ember.esm.js and the WebGL OpenGL-Shading-Language shader
// modules emit as SEPARATE same-origin chunk files (vendor/chunk-*.js) that the
// engine fetches lazily at runtime. So this gate measures the ENTRY module only.
// The shader chunks are intentionally out of the entry — they are lazy
// same-origin assets, not part of the main module weight, and are covered by the
// deploy-asset-coverage anti-rot guard instead of a byte ceiling here.
//
// It computes minified bytes and gzipped bytes of the entry, prints both against
// the budget, and exits non-zero if either exceeds the hard ceiling. This is the
// taste test that the entry never quietly bloats.
//
// NOT wired into scripts/hooks/full-check.sh — the fast push gate stays
// Python-only and never touches Babylon. Run this by hand or from a dedicated
// opt-in local check:
//
//   node scripts/babylon-size-gate.mjs
//
// Exit 0 = within budget, 1 = over ceiling or artifact missing.

import { gzipSync } from "node:zlib";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const ARTIFACT = join(
	REPO,
	"web",
	"kodiak-posts-for-todays-frontier",
	"vendor",
	"kodiak-ember.esm.js",
);

// ENTRY budget (shaders split into separate same-origin chunks, so the entry no
// longer carries shader weight). Measured entry at the shaders-split conversion:
// ~619KB minified / ~155KB gzipped. Ceilings are set with headroom above the
// measured entry so ordinary harness growth passes but a regression that welds a
// shader set back into the entry (or otherwise doubles it) trips the gate.
// The gzip ceiling stays at the section-11-signed 320KB upper bound.
const MIN_CEILING = 900 * 1024; // 921,600 bytes — headroom over the ~619KB entry
const GZIP_CEILING = 320 * 1024; // 327,680 bytes — section-11 upper bound retained

function kb(bytes) {
	return `${(bytes / 1024).toFixed(1)}KB`;
}

let raw;
try {
	raw = readFileSync(ARTIFACT);
} catch {
	console.log(`FAIL babylon-size-gate: entry missing at ${ARTIFACT}`);
	console.log("       run the build first: npm run build:ember");
	process.exit(1);
}

const minBytes = raw.length;
const gzipBytes = gzipSync(raw, { level: 9 }).length;

const minOver = minBytes > MIN_CEILING;
const gzipOver = gzipBytes > GZIP_CEILING;

console.log(
	`entry min  : ${minBytes} bytes (${kb(minBytes)}) — ceiling ${MIN_CEILING} bytes (${kb(MIN_CEILING)}) — ${minOver ? "OVER" : "ok"}`,
);
console.log(
	`entry gzip : ${gzipBytes} bytes (${kb(gzipBytes)}) — ceiling ${GZIP_CEILING} bytes (${kb(GZIP_CEILING)}) — ${gzipOver ? "OVER" : "ok"}`,
);
console.log(
	"note: WebGL shader modules are separate same-origin vendor/chunk-*.js assets, not part of this entry.",
);

if (minOver || gzipOver) {
	console.log("babylon-size-gate FAIL — entry exceeds ceiling");
	process.exit(1);
}
console.log("babylon-size-gate PASS — entry within budget");
process.exit(0);
