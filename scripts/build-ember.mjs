// build-ember — build the Kodiak ambient-effects BabylonJS bundle as an
// ECMAScript module with esbuild code-splitting.
//
// WHY A SCRIPT INSTEAD OF THE RAW esbuild COMMAND-LINE INTERFACE:
// esbuild code-splitting (a dynamic import() target becoming its own separately
// fetchable chunk file) requires the combination format="esm" + splitting=true
// + an output directory. That combination is awkward to express and easy to get
// wrong on the command line, and it is NOT supported with the older
// immediately-invoked-function-expression output format (format="iife"), where a
// dynamic import() is instead inlined into the entry file. So the shaders would
// stay welded into the one bundle. This script pins the correct build() options
// in one place.
//
// WHAT SPLITTING BUYS US HERE:
// @babylonjs/core StandardMaterial dynamic-imports two shader sets on first use:
//   - the WebGL OpenGL-Shading-Language set under ../Shaders/default.*
//   - the WebGPU shading-language set under the ShadersWGSL directory
//     (../ShadersWGSL/default.*)
// Under format="esm" + splitting=true those dynamic imports become separate
// chunk files emitted alongside the entry. The WebGL shader chunk then loads at
// runtime from the SAME ORIGIN as the entry module (the project's own Simple
// Storage Service static site behind CloudFront, the same origin everything else
// in deploy-frontier.sh ships to). This is self-hosted and version-pinned — it
// is NOT a third-party content-delivery network, and there is no shader
// repository Uniform Resource Locator to set. The engine we construct is a plain
// WebGL Engine (never a WebGPUEngine), so the WebGPU shading-language set is dead
// code: the stub plugin below resolves it to an empty module so it neither
// bundles into the entry nor emits a wasted chunk.
//
// SAME-ORIGIN CHUNK RESOLUTION:
// esbuild-emitted ECMAScript-module chunks are imported by a path relative to
// the importing module's own Uniform Resource Locator. When the entry lives at
// /vendor/kodiak-ember.esm.js and the chunks live at /vendor/chunk-*.js on the
// same origin, the relative import "just works" once the browser resolves the
// entry module Uniform Resource Locator — no publicPath override is required.
// We deliberately do NOT set publicPath: leaving it unset keeps chunk imports
// relative to the entry, which is exactly the same-origin vendor/ layout the
// deploy ships. (publicPath would only be needed to force an absolute prefix,
// which we do not want here.)
//
// TRADEOFF (accepted by the plan owner): the three-dimensional board layer now
// loads as an ECMAScript module with same-origin shader chunks, so that layer
// requires an http(s) origin (the deployed CloudFront site) to fetch its chunks
// — it does not run the three-dimensional path from a file:// Uniform Resource
// Locator. The static Scalable-Vector-Graphics fallback remains the default and
// still works from file:// and on any chunk-fetch failure.
//
// esbuild is pinned to 0.25.9 in package.json devDependencies; keep it pinned so
// the babylon-integrity hash stays reproducible.

import { build } from "esbuild";
import { fileURLToPath } from "node:url";
import { dirname, join, resolve } from "node:path";

const REPO = resolve(dirname(fileURLToPath(import.meta.url)), "..");
// Deployed output goes to the project's vendor/ directory. babylon-integrity
// overrides this with KODIAK_EMBER_OUTDIR to build into a throwaway temp
// directory for a reproducibility hash compare without touching the committed
// artifacts.
const OUTDIR =
	process.env.KODIAK_EMBER_OUTDIR ||
	join(REPO, "web", "kodiak-posts-for-todays-frontier", "vendor");

// stub ONLY the dead WebGPU shading-language set. The onResolve filter matches
// any import path that traverses the ShadersWGSL directory; onLoad returns an
// empty module so those 146 dead modules neither bundle nor emit a chunk. The
// WebGL /Shaders/ set is deliberately NOT matched — those must emit as real
// same-origin chunks the engine fetches at runtime.
const stubDeadWebgpuShaders = {
	name: "stub-dead-webgpu-shaders",
	setup(pluginBuild) {
		pluginBuild.onResolve({ filter: /\/ShadersWGSL\// }, (args) => ({
			path: args.path,
			namespace: "dead-webgpu-shader",
		}));
		pluginBuild.onLoad(
			{ filter: /.*/, namespace: "dead-webgpu-shader" },
			() => ({ contents: "", loader: "js" }),
		);
	},
};

// entryNames "[name].esm" -> the entry emits as vendor/kodiak-ember.esm.js
// (stable, no hash) so details.html and the gates can reference it by a fixed
// name. chunkNames carries a content hash so a changed shader set produces a new
// chunk filename (cache-correct) without touching the entry name.
const result = await build({
	absWorkingDir: REPO,
	entryPoints: { "kodiak-ember": "src/kodiak-ember.js" },
	bundle: true,
	format: "esm",
	splitting: true,
	minify: true,
	target: "es2019",
	legalComments: "none",
	outdir: OUTDIR,
	entryNames: "[name].esm",
	chunkNames: "chunk-[name]-[hash]",
	plugins: [stubDeadWebgpuShaders],
	metafile: true,
});

// report what was emitted so the build is auditable from its own output.
const outputs = Object.keys(result.metafile.outputs);
const entry = outputs.find((p) => p.endsWith("kodiak-ember.esm.js"));
const chunks = outputs.filter((p) => p.endsWith(".js") && p !== entry);
console.log("build-ember: emitted");
console.log(`  entry : ${entry}`);
console.log(`  chunks: ${chunks.length}`);
for (const c of chunks) console.log(`    - ${c}`);
