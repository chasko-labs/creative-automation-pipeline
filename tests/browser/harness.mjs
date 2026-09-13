// Local browser harness: one runner, parametrized per issue
//   npm run test:browser -- --issue 250
//   npm run test:browser
// Videos land in tests/browser/videos/<issue>-<stamp>.webm (gitignored artifacts).
// A new issue needing a local interaction repro adds tests/browser/issues/issue-<n>.mjs
// exporting {issue, title, run(page)} — never a hosted-origin scenario.
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
  else if (m && raw[i + 1] && !raw[i + 1].startsWith("--")) args[m[1]] = raw[++i];
  else if (m) args[m[1]] = true;
}

const only = args.issue ? String(args.issue) : null;
const files = readdirSync(join(root, "tests", "browser", "issues"))
  .filter((f) => /^issue-\d+\.mjs$/.test(f))
  .filter((f) => !only || f === `issue-${only}.mjs`);
if (!files.length) { console.error("no local scenarios match"); process.exit(2); }

const port = Number(args.port || 8901);
const staticSrv = serveStatic(join(root, "web", "kodiak-posts-for-todays-frontier"), port);
const baseUrl = staticSrv.baseUrl;
console.log("serving local", baseUrl);
try {
  for (let i = 0; i < 20; i++) {
    const result = spawnSync("curl", ["-s", "-o", "/dev/null", "-m", "3", "-w", "%{http_code}", `${baseUrl}/index.html`]);
    if (String(result.stdout).trim() === "200") break;
    await new Promise((resolveDelay) => setTimeout(resolveDelay, 500));
  }

  const videos = join(root, "tests", "browser", "videos");
  mkdirSync(videos, { recursive: true });
  const browser = await launch(videos);
  let failed = 0;
  for (const file of files) {
    const mod = await import(join(root, "tests", "browser", "issues", file));
    const context = await browser.newContext({
      viewport: { width: 1280, height: 900 },
      recordVideo: { dir: videos, size: { width: 1280, height: 900 } },
    });
    const page = await context.newPage();
    console.log(`\n### local issue #${mod.issue}: ${mod.title}`);
    try {
      await mod.run(page, { baseUrl });
      console.log(`PASS #${mod.issue}`);
    } catch (error) {
      failed++;
      console.error(`FAIL #${mod.issue}: ${error.message}`);
    }
    await context.close();
  }
  await browser.close();
  console.log(failed ? `\n${failed} scenario(s) failed` : "\nall local scenarios passed");
  process.exitCode = failed ? 1 : 0;
} finally {
  staticSrv.stop();
}
