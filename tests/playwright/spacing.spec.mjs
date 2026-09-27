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

// the full frontier page (vendor 3D bundle under software WebGL) loads slowly;
// the default 30s test timeout kills healthy runs at whatever step is pending.
test.setTimeout(120000);

async function gotoUnlocked(page) {
	await page.goto(page_url);
	await page.fill("#kodiak-gate input", "cakes");
	await page.click("#kodiak-gate button");
	await expect(page.locator("#kodiak-gate")).toBeHidden({ timeout: 10000 });
	// measure only once the authored stylesheet is live: unstyled file://
	// races read zero margins and flake the geometry below.
	await page.waitForFunction(() => {
		const ridge = document.querySelector(".wrap > .ff-ridge");
		if (!ridge) return false;
		const style = getComputedStyle(ridge);
		return style.marginBottom === "0px" && style.marginLeft === "16px";
	});
	// the Generate section is mounted by JS after load; measuring before it
	// lands silently re-pairs every divider below it and flakes the gaps.
	await page.waitForSelector("#generateCampaignSection", { timeout: 60000 });
}

async function gaps(page) {
	return page.evaluate(() => {
		// the timeline strip deliberately lives outside .wrap (under-header),
		// so rhythm measurement includes it explicitly, sorted by paint order.
		const kids = [
			...document.querySelectorAll(".wrap > *, #progressTimeline"),
		]
			.filter((el) => el.getBoundingClientRect().height > 0)
			.sort(
				(firstEl, secondEl) =>
					firstEl.getBoundingClientRect().top -
					secondEl.getBoundingClientRect().top,
			);
		return kids.map((el) => {
			const rect = el.getBoundingClientRect();
			return {
				key:
					(el.id ? `#${el.id}` : el.tagName.toLowerCase()) +
					`.${String(el.className).split(" ")[0]}`,
				top: Math.round(rect.top + scrollY),
				bottom: Math.round(rect.bottom + scrollY),
			};
		});
	});
}

// dividers are extensions of the card tops below them: breathing room above
// (one token, 24px), FLUSH below (0px), and inset horizontally so the square
// art ends where the card's corner curve begins (--radii-lg, 16px each side).
// Geometry reads through Math.round on fractional paint positions, so gap
// assertions allow +-1px: a glued divider (0) or a doubled rhythm (48) still
// goes red, subpixel rounding does not.
/**
 * @param {number} actual measured gap
 * @param {number} want token gap
 * @param {string} what assertion label
 */
function expectGap(actual, want, what) {
	expect(
		Math.abs(actual - want),
		`${what} (got ${actual}, want ${want} +-1 subpixel)`,
	).toBeLessThanOrEqual(1);
}
test("ridge/forest dividers integrate flush with the card top below", async ({
	page,
}) => {
	await gotoUnlocked(page);
	const rows = await gaps(page);
	const boxes = await page.evaluate(() => {
		const out = {};
		for (const el of document.querySelectorAll(
			".wrap > .ff-ridge, .wrap > .ff-forest, .wrap > .ff-about-art",
		)) {
			const rect = el.getBoundingClientRect();
			const next = el.nextElementSibling.getBoundingClientRect();
			out[
				(el.id ? `#${el.id}` : el.tagName.toLowerCase()) +
					`.${String(el.className).split(" ")[0]}`
			] = {
				left: Math.round(rect.left),
				right: Math.round(rect.right),
				card_left: Math.round(next.left),
				card_right: Math.round(next.right),
			};
		}
		return out;
	});
	for (let i = 0; i < rows.length; i++) {
		if (
			!rows[i].key.includes("ff-ridge") &&
			!rows[i].key.includes("ff-forest") &&
			!rows[i].key.includes("ff-about-art")
		)
			continue;
		const above = rows[i].top - rows[i - 1].bottom;
		const below = rows[i + 1].top - rows[i].bottom;
		expectGap(above, 24, `${rows[i].key} gap above must equal --spacing-lg`);
		expectGap(below, 0, `${rows[i].key} must sit flush on its card`);
		const box = boxes[rows[i].key];
		expectGap(
			box.left - box.card_left,
			16,
			`${rows[i].key} art must end at the card curve (left inset)`,
		);
		expectGap(
			box.card_right - box.right,
			16,
			`${rows[i].key} art must end at the card curve (right inset)`,
		);
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
	expectGap(
		rows[strip + 1].top - rows[strip].bottom,
		24,
		"timeline strip keeps the same bottom rhythm as cards",
	);
});

// the pipeline plate shares the logo row at and below 1400px: it shrinks
// beside the badge, never drops to its own line under it and never slides
// under the absolutely-positioned desktop badge (the 1280-1400 overlap band
// is why the switch sits at 1400). Above 1400 the badge floats over the
// viewport margin, clear of the row.
for (const narrowWidth of [1300, 900]) {
	test(`headline plate shares the logo row at ${narrowWidth}px`, async ({
		page,
	}) => {
		await page.setViewportSize({ width: narrowWidth, height: 800 });
		await gotoUnlocked(page);
		const layout = await page.evaluate(() => {
			const box = (selector) => {
				const el = document.querySelector(selector);
				if (!el) return null;
				const b = el.getBoundingClientRect();
				return { top: b.top, bottom: b.bottom, left: b.left, right: b.right };
			};
			return {
				logos: box(".kodiak-header__logos"),
				plate: box(".kodiak-header .kodiak-headline-plate"),
			};
		});
		expect(layout.logos && layout.plate).toBeTruthy();
		// vertical overlap: beside the badge, not under it.
		expect(layout.plate.top).toBeLessThan(layout.logos.bottom - 2);
		expect(layout.plate.bottom).toBeGreaterThan(layout.logos.top + 2);
		// horizontal order with no visual collision.
		expect(layout.plate.left).toBeGreaterThanOrEqual(layout.logos.right - 1);
	});
}

// narrow timeline: the four steps settle into an even 2x2 — two tidy rows,
// never a 3+1 orphan pileup.
test("timeline steps form an even grid on phones", async ({ page }) => {
	await page.setViewportSize({ width: 400, height: 800 });
	await gotoUnlocked(page);
	const rows = await page.evaluate(() =>
		[...document.querySelectorAll("#progressTimeline .ff-timeline-steps > li")].map(
			(step) => Math.round(step.getBoundingClientRect().top),
		),
	);
	expect(rows).toHaveLength(4);
	const firstRow = rows.filter((top) => Math.abs(top - rows[0]) <= 2);
	const secondRow = rows.filter((top) => Math.abs(top - rows[0]) > 2);
	expect(firstRow).toHaveLength(2);
	expect(secondRow).toHaveLength(2);
	// air between the rows: no crushed 4px pileup.
	expect(Math.min(...secondRow) - Math.max(...firstRow)).toBeGreaterThanOrEqual(8);
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

// after generate the resting hero is wiped and the strip becomes #preview's
// first child: the gap under the readout must stay one rhythm unit (the
// readout's own margin), not readout-margin + strip-margin stacked into a
// blank band. resting keeps the strip's own 16px because the hero still
// precedes it there.
test("generated strip sits one rhythm unit under the readout", async ({
	page,
}) => {
	await gotoUnlocked(page);
	await page.evaluate(() => {
		document.getElementById("previewCard")?.setAttribute("open", "");
	});
	const layout = await page.evaluate(() => {
		const readout = document.querySelector(".ff-output-readout");
		const preview = document.getElementById("preview");
		if (!readout || !preview) return null;
		// mirror showRenderSet: wipe #preview, mount the strip first.
		preview.innerHTML = "";
		const strip = document.createElement("div");
		strip.className = "ff-filmstrip";
		preview.appendChild(strip);
		const gap = strip.getBoundingClientRect().top - readout.getBoundingClientRect().bottom;
		const readoutMargin = Number.parseFloat(
			getComputedStyle(readout).marginBottom,
		);
		const stripMargin = getComputedStyle(strip).marginTop;
		// resting control: with the hero ahead of it the strip keeps its margin.
		const hero = document.createElement("figure");
		preview.insertBefore(hero, strip);
		const restingMargin = getComputedStyle(strip).marginTop;
		return { gap, readoutMargin, stripMargin, restingMargin };
	});
	expect(layout).toBeTruthy();
	expect(layout.stripMargin).toBe("0px");
	expect(layout.restingMargin).toBe("16px");
	expectGap(
		layout.gap,
		layout.readoutMargin,
		"post-generate strip must sit one readout-margin under the readout",
	);
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
