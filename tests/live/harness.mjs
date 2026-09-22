// Committed live-browser harness: ONE runner, parametrized per issue.
//   npm run test:live -- --issue 250          # single issue, local static server
//   npm run test:live -- --issue 250 --base-url https://d37333alc7ojpl.cloudfront.net
//   npm run test:live                          # all scenarios in issues/
// Videos land in tests/live/videos/<issue>-<stamp>.webm (gitignored artifacts).
// A new issue needing a live repro adds tests/live/issues/issue-<n>.mjs
// exporting {issue, title, run(page)} — never a new file elsewhere.
import { spawnSync } from "node:child_process";
import { readdirSync, mkdirSync } from "node:fs";
import { dirname, resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { launch, serveStatic } from "./lib.mjs";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const raw = process.argv.slice(2);
const args = {};
for (let i = 0; i < raw.length; i++) {
  const m = raw[i].match(/^--([^=]+)(?:=(.*))?$/);
  if (m && m[2] !== undefined) args[m[1]] = m[2];
  else if (m && raw[i + 1] && !raw[i + 1].startsWith("--")) { args[m[1]] = raw[++i]; }
  else if (m) args[m[1]] = true;
}

const only = args.issue ? String(args.issue) : null;
const files = readdirSync(join(root, "tests", "live", "issues"))
  .filter((f) => /^issue-\d+\.mjs$/.test(f))
  .filter((f) => !only || f === `issue-${only}.mjs`);
if (!files.length) { console.error("no scenarios match"); process.exit(2); }

let staticSrv = null;
let baseUrl = args["base-url"];
if (!baseUrl) {
  const port = Number(args.port || 8901);
  staticSrv = serveStatic(join(root, "web", "kodiak-posts-for-todays-frontier"), port);
  baseUrl = staticSrv.baseUrl;
  console.log("serving", baseUrl);
}
// wait for the server (local or remote) to answer
for (let i = 0; i < 20; i++) {
  const r = spawnSync("curl", ["-s", "-o", "/dev/null", "-m", "3", "-w", "%{http_code}", baseUrl + "/index.html"]);
  if (String(r.stdout).trim() === "200") break;
  await new Promise((r2) => setTimeout(r2, 500));
}

const videos = join(root, "tests", "live", "videos");
mkdirSync(videos, { recursive: true });
const browser = await launch(videos);
let failed = 0;
for (const f of files) {
  const mod = await import(join(root, "tests", "live", "issues", f));
  const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
  const ctx = await browser.newContext({
    viewport: { width: 1280, height: 900 },
    recordVideo: { dir: videos, size: { width: 1280, height: 900 } },
  });
  const page = await ctx.newPage();
  console.log(`\n### issue #${mod.issue}: ${mod.title}`);
  try {
    await mod.run(page, { baseUrl });
    console.log(`PASS #${mod.issue}`);
  } catch (e) {
    if (e && e.skip) {
      console.log(`SKIP #${mod.issue}: ${e.skip}`);
    } else {
      failed++;
      console.error(`FAIL #${mod.issue}: ${e.message}`);
    }
  }
  await ctx.close();
}
await browser.close();
if (staticSrv) staticSrv.stop();
// rename the recorded videos per issue for the receipt
console.log(failed ? `\n${failed} scenario(s) failed` : "\nall scenarios passed");
process.exit(failed ? 1 : 0);
