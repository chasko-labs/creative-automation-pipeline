// Spacing rhythm spec — rendered-geometry gate for the frontier page.
// DOM-presence tests cannot see layout: this spec measures the actual boxes
// in headless Chromium and pins the vertical-rhythm invariants, so a CSS edit
// that glues a divider to a card (or drifts a summary padding) goes RED here.
//
// Run: npm run test:render (NOT in the fast push gate).

import { test, expect } from "playwright/test";
import { pathToFileURL } from "node:url";
import { resolve } from "node:path";

const page_url = pathToFileURL(
	resolve("web/kodiak-posts-for-todays-frontier/index.html"),
).href;

async function gotoUnlocked(page) {
	await page.goto(page_url);
	await page.fill("#kodiak-gate input", "cakes");
	await page.click("#kodiak-gate button");
	await expect(page.locator("#kodiak-gate")).toBeHidden({ timeout: 10000 });
}

async function gaps(page) {
	return page.evaluate(() => {
		const kids = [...document.querySelectorAll(".wrap > *")].filter(
			(el) => el.getBoundingClientRect().height > 0,
		);
		return kids.map((el) => ({
			key:
				(el.id ? `#${el.id}` : el.tagName.toLowerCase()) +
				`.${String(el.className).split(" ")[0]}`,
			top: Math.round(el.getBoundingClientRect().top + scrollY),
			bottom: Math.round(el.getBoundingClientRect().bottom + scrollY),
		}));
	});
}

// dividers sit mid-gap: equal breathing room above and below, one token (24px).
test("ridge/forest dividers are centered in a uniform 24px rhythm", async ({
	page,
}) => {
	await gotoUnlocked(page);
	const rows = await gaps(page);
	for (let i = 0; i < rows.length; i++) {
		if (!rows[i].key.includes("ff-ridge") && !rows[i].key.includes("ff-forest"))
			continue;
		const above = rows[i].top - rows[i - 1].bottom;
		const below = rows[i + 1].top - rows[i].bottom;
		expect(
			above,
			`${rows[i].key} gap above (${above}) must equal --spacing-lg (24)`,
		).toBe(24);
		expect(
			below,
			`${rows[i].key} gap below (${below}) must equal --spacing-lg (24)`,
		).toBe(24);
	}
});

// the status strip is a section like the rest: same 24px below it.
test("timeline strip keeps the same bottom rhythm as cards", async ({
	page,
}) => {
	await gotoUnlocked(page);
	const rows = await gaps(page);
	const strip = rows.findIndex((r) => r.key.includes("ff-timeline"));
	expect(strip).toBeGreaterThan(-1);
	expect(rows[strip + 1].top - rows[strip].bottom).toBe(24);
});

// every top-level step summary paints the same inner padding.
test("step summaries share one padding value", async ({ page }) => {
	await gotoUnlocked(page);
	const pads = await page.evaluate(() => {
		const out = {};
		for (const id of [
			"brainstormAll",
			"scopeWrap",
			"locationSection",
			"season",
		]) {
			const summary = document.querySelector(`#${id} > summary`);
			const style = getComputedStyle(summary);
			out[id] = style.paddingTop + " " + style.paddingRight;
		}
		return out;
	});
	const values = new Set(Object.values(pads));
	expect(
		values.size,
		`step summaries drift: ${JSON.stringify(pads)}`,
	).toBe(1);
});

// section margins resolve to whole pixels — no rem-at-18px fractions.
test("section block margins are whole pixels", async ({ page }) => {
	await gotoUnlocked(page);
	const fracs = await page.evaluate(() => {
		const bad = [];
		for (const el of document.querySelectorAll(
			".wrap > .card, .wrap > .ff-output, .wrap > .ff-timeline, .wrap > .ff-ridge, .wrap > .ff-forest",
		)) {
			const style = getComputedStyle(el);
			for (const prop of ["marginTop", "marginBottom"]) {
				const px = Number.parseFloat(style[prop]);
				if (!Number.isInteger(px))
					bad.push(`${el.id || el.className} ${prop}=${style[prop]}`);
			}
		}
		return bad;
	});
	expect(fracs, `fractional margins: ${fracs.join(", ")}`).toEqual([]);
});
