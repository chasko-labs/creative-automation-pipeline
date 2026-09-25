// Issue #246 — export table header wraps: PLATFORMS renders as PLATFOR MS.
// NOTE (2026-09-25): the side platform matrix was retired by design —
// renderPlatformMatrix() now only removes the duplicated panel and platforms
// live once on the tile caps (.rt-platforms in each render-cap). This scenario
// asserts the same "never wraps mid-word" contract on the current surface.
// Acceptance: every tile cap carries a non-empty platform line whose wrapping
// never breaks a platform name mid-word (word-break normal, no break-all /
// anywhere). Proof chain (all against the REAL page, no mocks):
//   1. drive a real preview generate (backend-backed) so tiles exist;
//   2. every tile cap has a non-empty .rt-platforms line;
//   3. computed word-break is normal at 1440px and 375px.
// Run with:
//   npm run test:live -- --issue 246 --base-url https://kodiak.bryanchasko.com
import { assert, gotoLive, isLocalBase, skip } from "../lib.mjs";

export const issue = 246;
export const title = "platform names never wrap mid-word";

async function capState(page) {
  return page.evaluate(() => {
    const caps = [...document.querySelectorAll("#preview .render-tile .render-cap")].map((cap) => {
      const line = cap.querySelector(".rt-platforms");
      const cs = line ? getComputedStyle(line) : null;
      return {
        text: line ? line.textContent.trim() : "",
        wordBreak: cs ? cs.wordBreak : "missing",
        overflowWrap: cs ? cs.overflowWrap : "missing",
      };
    });
    return caps;
  });
}

export async function run(page, { baseUrl } = {}) {
  if (isLocalBase(baseUrl)) {
    skip("platform chips render post-generate via backend — needs a backend-backed generate flow, not a static server");
  }
  await gotoLive(page, baseUrl);
  await page.evaluate(() => { document.getElementById("previewCard").open = true; });
  await page.waitForTimeout(600);
  // Tiles (and their platform chips) render post-generate: drive a real
  // preview first (defaults). Cold models + one warm retry can take a few
  // minutes, hence the generous budget.
  await page.evaluate(() => document.getElementById("generateCampaign")?.click());
  await page.waitForFunction(
    () => document.querySelectorAll("#preview .render-tile img").length > 0 ||
      document.querySelector("#preview .ff-render-miss") !== null,
    null,
    { timeout: 240000 },
  );
  await page.waitForTimeout(1500);
  const missed = await page.evaluate(() => !!document.querySelector("#preview .ff-render-miss"));
  assert(!missed, "preview render landed tiles (double render miss: cold or throttled backend, no tiles to assert)");

  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(500);
    const caps = await capState(page);
    assert(caps.length > 0, `${width}px: tile caps present`);
    for (const c of caps) {
      assert(c.text.length > 0, `${width}px: tile carries a platform line`);
      assert(c.wordBreak === "normal", `${width}px: "${c.text.slice(0, 40)}" word-break=normal (got ${c.wordBreak})`);
      assert(c.overflowWrap !== "anywhere", `${width}px: "${c.text.slice(0, 40)}" overflow-wrap is not anywhere (got ${c.overflowWrap})`);
    }
  }
  await page.evaluate(() => document.querySelector("#preview .ff-filmstrip")?.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(800);
}
