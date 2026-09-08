// Issue #250 — stuck product chips (Apple Cinnamon / Banana Nut Peak Oatmeal).
// Mechanism (proven live): a host re-filter destroys checked checkbox nodes
// without events, leaving stale tray chips; toggleSku then silently no-ops
// (box absent) and reset never re-syncs the tray.
// Acceptance, all three, against the REAL page:
//   1. X removes the chip and its SKU permanently;
//   2. Restore defaults leaves zero products staged;
//   3. a reload after restore stays clean.
import {
  assert, checkProductBox, clickChipX, clickResetDefaults,
  gotoLive, pageState, searchProducts,
} from "../lib.mjs";

const A = "Apple Cinnamon Oatmeal Packets";
const B = "Banana Nut Peak Oatmeal Packets";

export const issue = 250;
export const title = "stuck product chips remove permanently";

export async function run(page, { baseUrl } = {}) {
  await gotoLive(page, baseUrl);
  let s = await pageState(page);
  assert(s.chips.length === 0, "starts clean: no chips");

  // Stage both through the combobox search (they live at catalog idx 72/73,
  // never in the unfiltered first 12), then clear the filter — this destroys
  // the checked nodes and leaves the stale chips the bug is about.
  await searchProducts(page, "oatmeal");
  await page.waitForTimeout(400);
  assert((await checkProductBox(page, A)) === "checked", "staged A via search");
  assert((await checkProductBox(page, B)) === "checked", "staged B via search");
  await searchProducts(page, "");
  await page.waitForTimeout(400);
  s = await pageState(page);
  assert(s.chips.includes(A) && s.chips.includes(B), "both chips staged");

  // 1. X removes the chip and its SKU permanently.
  assert((await clickChipX(page, A)) === "clicked", "X on A clicks");
  await page.waitForTimeout(500);
  s = await pageState(page);
  assert(!s.chips.includes(A), "A chip gone after X");
  assert(s.chips.includes(B), "B chip untouched by A's X");

  // 2. Restore defaults leaves zero products staged.
  assert((await clickResetDefaults(page)) === "clicked", "Restore defaults clicks");
  await page.waitForTimeout(500);
  s = await pageState(page);
  assert(s.chips.length === 0, "zero chips staged after restore");
  assert(!s.skus || s.skus.length === 0, "snapshot skus empty after restore");

  // 3. A reload after restore stays clean.
  await page.reload({ waitUntil: "networkidle" });
  await page.waitForTimeout(3000);
  s = await pageState(page);
  assert(s.chips.length === 0, "no chips after reload");
  assert(s.checked.length === 0, "no boxes checked after reload");
  assert(!s.skus || s.skus.length === 0, "snapshot skus still empty after reload");
}
