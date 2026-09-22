// Issue #217 — retailer chip cluster offered only Localized Costco.
// Acceptance: Costco, Publix, Target plus Kodiak subscription are selectable
// directions, each threading its own brief text like the Costco chip does.
// Local-safe: chip taps + brief/theme assertions only, no backend calls.
import { assert, gotoLive } from "../lib.mjs";

export const issue = 217;
export const title = "retailer cluster offers costco publix target subscription";

const CHIPS = [
  { theme: "localized-costco", label: "Localized Costco" },
  { theme: "localized-publix", label: "Localized Publix" },
  { theme: "localized-target", label: "Localized Target" },
  { theme: "kodiak-subscription", label: "Kodiak Cakes subscription" },
];

export async function run(page, { baseUrl } = {}) {
  await gotoLive(page, baseUrl);
  for (const c of CHIPS) {
    const st = await page.evaluate((theme) => {
      const chip = document.querySelector(`#promptChips .ff-chip[data-theme="${theme}"]`);
      if (!chip) return null;
      chip.click();
      const input = chip.querySelector(".ff-check-card__input");
      return {
        // Theme cards are label+checkbox since the check-card migration — the
        // native checked state (not aria-pressed, which nothing sets here)
        // is the activation signal, mirrored in window.__activeTheme.
        checked: !!(input && input.checked),
        brief: document.getElementById("campaignBrief")?.value || "",
        activeTheme: window.__activeTheme || null,
      };
    }, c.theme);
    assert(st, `chip present: ${c.theme}`);
    assert(st.checked, `${c.theme} activates (native checkbox state)`);
    assert(
      st.brief.toLowerCase().includes(c.label.toLowerCase()),
      `${c.theme} threads its brief text`,
    );
    assert(st.activeTheme === c.theme, `${c.theme} rides window.__activeTheme`);
    // toggle back off so each chip is proven from a clean slate
    await page.evaluate((theme) => {
      document.querySelector(`#promptChips .ff-chip[data-theme="${theme}"]`)?.click();
    }, c.theme);
  }
  const rest = await page.evaluate(() => ({
    activeTheme: window.__activeTheme,
    checked: document.querySelectorAll("#promptChips .ff-check-card__input:checked").length,
  }));
  assert(rest.activeTheme === null && rest.checked === 0, "all chips toggle clean off");
}
