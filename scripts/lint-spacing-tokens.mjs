// lint:css — static spacing-token gate for the frontier page CSS.
// Catches the bug class behind the uneven page rhythm without a browser:
// fractional-pixel literals, glue-zero divider margins, and drifted
// step-summary paddings. Run: npm run lint:css. Exit nonzero on violation.
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

const css_path = resolve(
	"web/kodiak-posts-for-todays-frontier/design/components.css",
);
const raw = readFileSync(css_path, "utf8");
const css = raw.replace(/\/\*[\s\S]*?\*\//g, "");
const failures = [];

// 1. no fractional pixels inside margin/padding (e.g. 22.5px from
// rem-at-18px math). font sizes and gradient stops are out of scope.
for (const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
	for (const decl of rule[2].matchAll(/(margin|padding)[^:;]*:\s*([^;}]+)/g)) {
		const frac = decl[2].match(/\d+\.\d+px/);
		if (frac) {
			failures.push(
				`fractional spacing ${frac[0]} in ${rule[1].trim().split(",")[0].trim()} { ${decl[1]} }`,
			);
			if (failures.length > 5) break;
		}
	}
	if (failures.length > 5) break;
}

// 2. collect padding values per step-summary selector group.
const step_selectors = [
	".ff-brainstorm-all__summary",
	".ff-setup .ff-scope-summary",
	"#locationSection>summary",
	".ff-season-details>summary",
];
const paddings = new Map();
for (const rule of css.matchAll(/([^{}]+)\{([^{}]*)\}/g)) {
	const selectors = rule[1].split(",").map((s) => s.trim());
	for (const sel of selectors) {
		if (!step_selectors.includes(sel)) continue;
		const pad = rule[2].match(/padding\s*:\s*([^;}]+)/);
		if (pad) paddings.set(sel, pad[1].trim());
	}
}
const distinct = new Set(paddings.values());
if (distinct.size !== 1) {
	failures.push(
		`step-summary paddings drift: ${JSON.stringify(Object.fromEntries(paddings))}`,
	);
}

// 3. dividers integrate flush with the card below (bottom margin 0) and end
// at the card's corner curve (horizontal inset, one radius token each side).
for (const cls of [".ff-ridge", ".ff-forest"]) {
	const rule = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].find((r) =>
		r[1].split(",").map((s) => s.trim()).includes(cls),
	);
	const body = rule ? rule[2] : "";
	const shorthand = body.match(/margin\s*:\s*([^;}]+)/);
	const parts = shorthand ? shorthand[1].trim().split(/\s+/) : [];
	const top = parts[0] || null;
	const sides = parts.length === 4 ? parts[1] : parts.length >= 2 ? parts[1] : null;
	const bottom = parts.length <= 2 ? parts[0] : parts.length === 3 ? parts[2] : parts[3] || null;
	if (bottom !== "0" && bottom !== "0px") {
		failures.push(`${cls} must sit flush on its card (margin-bottom ${bottom || "missing"})`);
	}
	if (sides !== "var(--radii-lg)") {
		failures.push(`${cls} art must end at the card curve (side margin ${sides || "missing"})`);
	}
	if (top !== "0" && top !== "0px" && top !== "auto") {
		failures.push(`${cls} top margin must be 0/auto (card above supplies the gap), got ${top}`);
	}
}

if (failures.length > 0) {
	console.error("lint:css FAILED");
	for (const f of failures) console.error(` - ${f}`);
	process.exit(1);
}
console.log(
	`lint:css ok — step summaries share ${[...distinct][0]}; dividers flush + curve-inset; no fractional px.`,
);
