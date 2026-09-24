#!/usr/bin/env node
// Live proof for the frontier preview path: POSTs one preview request shaped
// like the frontend's and asserts it lands ABOVE rung D (no wall-timeout
// fallthrough). Saves a JSON evidence record under docs/qa-evidence/.
// Usage: node scripts/frontier-live-render.mjs [--url FUNCTION_URL] [--prompt "..."]
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const raw = process.argv.slice(2);
const args = {};
for (let i = 0; i < raw.length; i++) {
  const m = raw[i].match(/^--([^=]+)(?:=(.*))?$/);
  if (m && m[2] !== undefined) args[m[1]] = m[2];
  else if (m && raw[i + 1] && !raw[i + 1].startsWith("--")) args[m[1]] = raw[++i];
  else if (m) args[m[1]] = true;
}
const url =
  args.url ||
  "https://ipswy2mfu25qebueq24346rm2u0mypjs.lambda-url.us-east-1.on.aws/";
const body = {
  prompt:
    args.prompt ||
    "the box on top of a surf board with a sunset and christmas lights and santa's sleigh in the distance",
  market: "US-W-SD",
  product: "banana-muffin-quick-bread-mix",
  season: "December",
  scope: "local",
  layers: {},
  mode: "preview",
};

const t0 = Date.now();
const ctrl = new AbortController();
const killer = setTimeout(() => ctrl.abort(), 110000);
let resp, json;
try {
  resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: ctrl.signal,
  });
  json = await resp.json();
} finally {
  clearTimeout(killer);
}
const elapsedS = (Date.now() - t0) / 1000;
const prov = (json && json.provenance) || {};
const record = {
  stamp: new Date().toISOString(),
  url,
  http: resp.status,
  elapsed_s: Math.round(elapsedS * 10) / 10,
  source: json && json.source,
  rung: prov.rung,
  engine: prov.engine,
  fallthrough_reason: prov.fallthrough_reason || null,
  ratios: prov.ratios || null,
  renders: Array.isArray(json && json.renders) ? json.renders.length : 0,
  prompt_kept: prov.incoming_prompt === body.prompt || undefined,
};
const outDir = resolve(root, "docs/qa-evidence");
mkdirSync(outDir, { recursive: true });
const stamp = record.stamp.replace(/[:.]/g, "-").slice(0, 19);
const outPath = resolve(outDir, `${stamp}-live-render.json`);
writeFileSync(outPath, JSON.stringify(record, null, 1) + "\n");
console.log(JSON.stringify(record, null, 1));
console.log("evidence:", outPath);
const ok =
  resp.status === 200 &&
  prov.rung &&
  prov.rung !== "D" &&
  prov.fallthrough_reason !== "wall-timeout";
console.log(ok ? "LIVE RENDER: PASS (above rung D)" : "LIVE RENDER: MISS (rung D / wall-timeout)");
process.exit(ok ? 0 : 1);
