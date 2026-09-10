// Issue #246 — export table header wraps: PLATFORMS renders as PLATFOR MS.
// Acceptance: header reads PLATFORMS on one line at 1440px and 375px.
// Proof chain (all against the REAL page, no mocks):
//   1. at desktop width the thead cells are white-space:nowrap and single-line;
//   2. at 375px the thead is still rendered (not display:none) and single-line.
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
    assert(st.theadDisplay !== "none", `${width}px: thead rendered (display=${st.theadDisplay})`);
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
