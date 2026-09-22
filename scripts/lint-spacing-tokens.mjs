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

// 3. dividers must carry bottom margin (mid-gap, never glued to the card below).
for (const cls of [".ff-ridge", ".ff-forest"]) {
	const rule = [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].find((r) =>
		r[1].split(",").map((s) => s.trim()).includes(cls),
	);
	const body = rule ? rule[2] : "";
	const shorthand = body.match(/margin\s*:\s*([^;}]+)/);
	const mb = body.match(/margin-bottom\s*:\s*([^;}]+)/);
	const bottom = mb ? mb[1].trim() : shorthand ? shorthand[1].trim().split(/\s+/) : null;
	const bottom_val = Array.isArray(bottom)
		? bottom.length === 1 ? bottom[0] : bottom.length === 3 ? bottom[2] : bottom[3]
		: bottom;
	if (!bottom_val || bottom_val === "0" || bottom_val === "0px") {
		failures.push(`${cls} has no bottom margin (glued divider)`);
	}
}

if (failures.length > 0) {
	console.error("lint:css FAILED");
	for (const f of failures) console.error(` - ${f}`);
	process.exit(1);
}
console.log(
	`lint:css ok — step summaries share ${[...distinct][0]}; dividers carry bottom margin; no fractional px.`,
);
