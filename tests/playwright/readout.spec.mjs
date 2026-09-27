// Readout framing spec — the output readout follows the active season and
// never repeats the language list.
//
// The framing cue used to render the market's static cue verbatim (September
// peaches in October) while #marketLangLine named the same languages a second
// time as "localized reach". Both are pinned here against the real page.
//
// Run: npm run test:render (NOT in the fast push gate).

import { test, expect } from "playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const page_url = pathToFileURL(
	resolve("web/kodiak-posts-for-todays-frontier/index.html"),
).href;

test.setTimeout(120000);

async function gotoUnlocked(page) {
	await page.goto(page_url);
	await page.fill("#kodiak-gate input", "cakes");
	await page.click("#kodiak-gate button");
	await expect(page.locator("#kodiak-gate")).toBeHidden({ timeout: 10000 });
	await page.waitForFunction(() => {
		const ridge = document.querySelector(".wrap > .ff-ridge");
		if (!ridge) return false;
		const style = getComputedStyle(ridge);
		return style.marginBottom === "0px" && style.marginLeft === "16px";
	});
	await page.waitForSelector("#generateCampaignSection", { timeout: 60000 });
}

// October framing over Park City: the cue must come down the seasonal tier
// ladder (pairs line or engine line), never the stale static September cue —
// and the language names live once in the lang line, never in the framing.
test("framing follows the season without repeating the language list", async ({
	page,
}) => {
	await gotoUnlocked(page);
	await page.evaluate(() => {
		const loc = document.getElementById("locality");
		loc.value = "US-MW-PARKCITY-84098";
		loc.dispatchEvent(new Event("change", { bubbles: true }));
		const sea = document.getElementById("seasonalSelect");
		sea.value = "October";
		sea.dispatchEvent(new Event("change", { bubbles: true }));
		window.__activeSeason = "October";
	});
	await page.waitForTimeout(500);
	const readout = await page.evaluate(() => ({
		featured: document.getElementById("featuredFrontier").textContent,
		langs: document.getElementById("marketLangLine").textContent,
	}));
	expect(readout.featured).not.toMatch(/september/i);
	expect(readout.featured).toMatch(/october|apples|pumpkin|fall/i);
	const names = (readout.langs.match(/[A-Z][a-z]+/g) || []).filter(
		(word) => !["Localized", "In", "Languages"].includes(word),
	);
	expect(names.length).toBeGreaterThan(0);
	for (const name of names)
		expect(
			readout.featured,
			`framing repeats the lang line (${name})`,
		).not.toContain(name);
	expect(readout.featured).not.toMatch(/localized reach/i);
});
