// Issue #246 — export table header wraps: PLATFORMS renders as PLATFOR MS.
// Acceptance: PLATFORMS never wraps mid-word. Where the thead is shown it is
// white-space:nowrap and single-line; on narrow viewports the matrix may switch
// to the stacked card layout (thead display:none, cells rendered as blocks) —
// wrapping is moot there because the header row is not laid out as a table row.
// Proof chain (all against the REAL page, no mocks):
//   1. at desktop width the thead cells are white-space:nowrap and single-line;
//   2. at 375px either the thead is single-line, or the matrix is in card mode
//      (thead display:none) — both satisfy "never wraps mid-word".
// Run with:
//   npm run test:live -- --issue 246
import { assert, gotoLive } from "../lib.mjs";

export const issue = 246;
export const title = "export table header never wraps mid-word";

async function headerState(page) {
  return page.evaluate(() => {
    const ths = [...document.querySelectorAll(".platform-matrix thead th")].map((th) => {
      const r = th.getBoundingClientRect();
      return {
        text: th.textContent.trim(),
        h: Math.round(r.height),
        singleLine: th.scrollHeight <= th.clientHeight + 1,
        whiteSpace: getComputedStyle(th).whiteSpace,
      };
    });
    const thead = document.querySelector(".platform-matrix thead");
    return { ths, theadDisplay: thead ? getComputedStyle(thead).display : "missing" };
  });
}

export async function run(page, { baseUrl } = {}) {
  await gotoLive(page, baseUrl);
  await page.evaluate(() => { document.getElementById("previewCard").open = true; });
  await page.waitForTimeout(600);

  for (const width of [1440, 375]) {
    await page.setViewportSize({ width, height: 900 });
    await page.waitForTimeout(500);
    const st = await headerState(page);
    // Card-mode (thead hidden, cells stacked) is a valid narrow-viewport layout:
    // there is no table header row to wrap, so "never wraps mid-word" holds.
    if (st.theadDisplay === "none") {
      assert(width < 1024, `${width}px: card-mode layout (thead display:none) only at narrow widths`);
      continue;
    }
    const plats = st.ths.find((t) => /platforms/i.test(t.text));
    assert(!!plats, `${width}px: PLATFORMS header present (${st.ths.map((t) => t.text).join("|")})`);
    for (const th of st.ths) {
      assert(th.whiteSpace === "nowrap", `${width}px: "${th.text}" white-space=nowrap`);
      assert(th.singleLine, `${width}px: "${th.text}" on one line (h=${th.h})`);
    }
  }
  await page.evaluate(() => document.querySelector(".platform-matrix")?.scrollIntoView({ block: "center" }));
  await page.waitForTimeout(800);
}
