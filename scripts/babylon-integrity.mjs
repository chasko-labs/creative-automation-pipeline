// babylon-integrity — LOCAL / OPT-IN staleness guard for the committed Babylon
// ENTRY module.
//
// The bundle is now built as an ECMAScript module with esbuild code-splitting
// (see scripts/build-ember.mjs): the entry emits as vendor/kodiak-ember.esm.js
// and the WebGL OpenGL-Shading-Language shader modules emit as SEPARATE
// same-origin chunk files (vendor/chunk-*.js). This check rebuilds via the SAME
// build script to a temporary output directory, hashes the fresh ENTRY, and
// compares it against a hash of the committed vendor/kodiak-ember.esm.js. If
// they differ, the committed entry is stale (source changed but the bundle was
// not rebuilt+committed) and this exits non-zero, printing both hashes.
//
// It also asserts the fresh build emitted at least one shader chunk (a
// default.fragment chunk) — a build that fails to split shaders, or a stub that
// wrongly removed the WebGL set, is a defect this catches.
//
// NOT wired into scripts/hooks/full-check.sh — local / opt-in only:
//
//   node scripts/babylon-integrity.mjs
//
// REPRODUCIBILITY: esbuild --minify output can vary by esbuild version, so the
// hash is only stable when the build host uses the pinned esbuild. This repo
// pins esbuild 0.25.9 in package.json devDependencies. If esbuild is upgraded,
// rebuild + recommit the artifacts and the new hash becomes canonical.
//
// Exit 0 = committed entry matches a fresh build (and shader chunks emit),
// 1 = drift, missing shader chunk, or build failure.

import { createHash } from "node:crypto";
import { execFileSync } from "node:child_process";
import { mkdtempSync, readFileSync, readdirSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BUILD_SCRIPT = join(REPO, "scripts", "build-ember.mjs");
const ENTRY_NAME = "kodiak-ember.esm.js";
const ARTIFACT = join(
	REPO,
	"web",
	"kodiak-posts-for-todays-frontier",
	"vendor",
	ENTRY_NAME,
);
const ESBUILD = join(REPO, "node_modules", ".bin", "esbuild");
const PINNED_ESBUILD = "0.25.9";

function sha256(buf) {
	return createHash("sha256").update(buf).digest("hex");
}

// confirm the resolved esbuild matches the pinned version the hash assumes.
let esbuildVersion = "";
try {
	esbuildVersion = execFileSync(ESBUILD, ["--version"]).toString().trim();
} catch {
	console.log(`FAIL babylon-integrity: esbuild not found at ${ESBUILD}`);
	console.log("       run: npm install --legacy-peer-deps");
	process.exit(1);
}
if (esbuildVersion !== PINNED_ESBUILD) {
	console.log(
		`WARN babylon-integrity: esbuild ${esbuildVersion} != pinned ${PINNED_ESBUILD} — hash may drift on version alone`,
	);
}

let committed;
try {
	committed = readFileSync(ARTIFACT);
} catch {
	console.log(`FAIL babylon-integrity: committed entry missing at ${ARTIFACT}`);
	process.exit(1);
}

// Rebuild via the same build script into a temp output directory. build-ember.mjs
// hard-codes the deployed outdir, so we override it for this reproducibility
// build using KODIAK_EMBER_OUTDIR (honored by the build script).
const tmp = mkdtempSync(join(tmpdir(), "kodiak-ember-"));
let fresh;
let freshChunks = [];
try {
	execFileSync("node", [BUILD_SCRIPT], {
		stdio: ["ignore", "ignore", "ignore"],
		env: { ...process.env, KODIAK_EMBER_OUTDIR: tmp },
	});
	fresh = readFileSync(join(tmp, ENTRY_NAME));
	freshChunks = readdirSync(tmp).filter(
		(f) => f.endsWith(".js") && f !== ENTRY_NAME,
	);
} catch (err) {
	console.log(`FAIL babylon-integrity: fresh build failed — ${err.message}`);
	rmSync(tmp, { recursive: true, force: true });
	process.exit(1);
} finally {
	rmSync(tmp, { recursive: true, force: true });
}

// a fresh build must split the WebGL shader set into at least one shader chunk.
const hasShaderChunk = freshChunks.some((f) => /\.fragment-|\.vertex-/.test(f));
if (!hasShaderChunk) {
	console.log(
		"babylon-integrity FAIL — fresh build emitted no shader chunk (the WebGL shader set failed to split)",
	);
	console.log(`  chunks seen: ${freshChunks.length}`);
	process.exit(1);
}

const committedHash = sha256(committed);
const freshHash = sha256(fresh);

if (committedHash !== freshHash) {
	console.log(
		"babylon-integrity FAIL — committed entry is stale (does not match a fresh build)",
	);
	console.log(`  committed sha256: ${committedHash}`);
	console.log(`  fresh     sha256: ${freshHash}`);
	console.log("  fix: npm run build:ember && git add the vendor artifacts");
	process.exit(1);
}

console.log("babylon-integrity PASS — committed entry matches a fresh build");
console.log(
	`  entry sha256: ${committedHash}  (esbuild ${esbuildVersion}, ${freshChunks.length} chunks, shader chunk present)`,
);
process.exit(0);
