// Issue #254 — favicon 404s live despite merged files (deploy sync gap).
// Acceptance: favicon.ico, favicon.svg, and apple-touch-icon.png all return
// 200 on a clean load; no 404 among icon responses.
// Root cause was scripts/deploy-frontier.sh, not the markup: the files were
// merged (#214) and linked in <head>, but the deploy FILES list never shipped
// root files. This test guards the served result; the deploy include set is
// pinned by tests/vitest/deploy-asset-coverage.test.mjs.
import { assert, gotoLocal } from "../lib.mjs";

export const issue = 254;
export const title = "favicon set serves 200, zero icon 404s";

export async function run(page, { baseUrl } = {}) {
  const bad = [];
  const seen = {};
  page.on("response", (r) => {
    const url = r.url();
    if (/favicon|apple-touch-icon/.test(url)) {
      seen[url.split("/").pop().split("?")[0]] = r.status();
      if (r.status() >= 400) bad.push(`${r.status()} ${url}`);
    }
  });
  await gotoLocal(page, baseUrl);
  await page.waitForTimeout(1500);

  // Explicitly request each icon URL the head references so the test does not
  // depend on browser favicon-fetch heuristics.
  for (const icon of ["favicon.svg", "favicon.ico", "apple-touch-icon.png"]) {
    const st = await page.evaluate(async (f) => {
      const r = await fetch(f, { cache: "no-store" });
      return r.status;
    }, icon);
    assert(st === 200, `${icon} fetches 200 (got ${st})`);
  }
  assert(bad.length === 0, `no icon 404s in network log (got: ${bad.join(", ") || "none"})`);
}
