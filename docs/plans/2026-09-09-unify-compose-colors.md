## Goal

De-redden the interface around the approved ember CTA, give the secondary buttons a real system, and reunify section 4 so each creative concept owns its compose consequence in one visible row — no separate "Compose" sub-language, no mystery checkbox counts. All color work flows through the Panda token toolchain; no hand-slapped hex, no inline styles.

## Success Criteria

- No signal-red (`--colors-brand-signal-red` / `#B51E14` / `var(--red)`) remains in decorative UI: disclosure chevrons, timeline badges, secondary buttons, focus rings. Red survives only in the Create Campaign Preview ember gradient, true error/alert states, and links (grandfathered pending a link-color pass).
- Timeline reads `1–5 Setup · 6 Preview · 7 Generate · 8 Assets` with distinguishable earth-tone states and no red anywhere.
- Section 4 shows every compose flag pinned to the concept that drives it: retailer chips + retailer-mark flag in one row, partner chip + partner-mark flag in one row, product-image flag on the products row. The retailer dropdown is gone (the chips already carry the value). Both "Compose" subheadings are gone.
- Zero new raw-hex literals in `components.css`; recent raw-hex drift (`#F5EAD3`, `#B53E09`, `#93300A`, `#F2E2C6`, …) is replaced with generated token refs.
- `generate()` produces identical `layers{}` output for equivalent selections before and after.
- Vitest 115+ passes, Playwright desktop render verified, deploy verified live.

## Context And Current Facts

- Design-system ground truth, verified this run:
  - Token source of truth is `design/tokens/kodiak.json` (W3C DTFM) → `panda.config.ts` (emitTokensOnly) → `design/styles.css` via `npm run tokens:css`. `styles.css` is generated and must never be hand-edited (`docs/frontend-architecture.md`:77-78; `package.json` scripts `tokens:config` / `tokens:css`; `@pandacss/dev 1.12.0` in devDependencies).
  - `design/components.css` is hand-authored but must consume token refs only — the toolchain exists explicitly "so agents cannot slop raw-hex CSS" (`package.json` description).
  - Brand tokens: Bear Brown `#3B2316`, Blaze Orange `#E8530E`, Frontier Green `#1A3C34` (`design/tokens/kodiak.json`, `/kodiak/color/brand/*`).
  - Adobe Spectrum posture per `docs/design-system-inventory.md`: token-bridged, never token-replacing (standard S15, :452-455). No spectrum-web-components runtime in the repo; controls stay native HTML on kodiak tokens (:497-499). Spectrum informs disclosure/checkbox semantics (e.g. `sp-accordion-item` model for the product-chooser disclosure, :467) — it does not supply new components for this work.
  - The inventory flags `var(--red)` #B51E14 as D1 drift (:483); the canonical root `design/tokens/kodiak.json` sanctions `signalRed` as accent/link/cta. Unit 0 narrows that sanction to alert/error/links in the token metadata (links grandfathered) and de-reddens everything else; `--colors-brand-signal-red` remains available for genuine alerts.
- Offending red today (`design/components.css`): chevron rules :336, :374, :390, :625, :627; timeline active badge :939; `.btn.orange` flat red fill :175 (the Generate Campaign button); focus-visible rings (e.g. :417).
- Timeline: active badge red, done badge frontier green, todo/locked bear-brown/grey.
- Secondary buttons have no system: `ff-assets-trigger` pale outline pill (:1018), `ff-products-random` smaller pale box (:727).
- Section 4 reality: the requested merge already exists in logic, not in layout. `js/prompt-chips.js` two-way syncs chips ⇄ compose checkboxes (`syncLayersFromChips` :206, `syncChipsFromLayers` :294); `js/generate.js` :216-220 reads `layerProduct` / `layerRetailer`+`layerRetailerSelect` / `layerPartner`. All three flags exist in markup (`index.html` :300, :306, :341) — nothing was lost; they render in two visual languages under two "Compose" subheadings, with the retailer `<select>` duplicating what the chips already know.
- Dead code in the blast radius: `generate.js` :228/231 references retired `#layerPicker` (guarded/empty, harmless).

## Constraints And Non-goals

- Create Campaign Preview button untouched (approved). Copy untouched ("composed under the grain", "never center-pasted", sidecar note).
- Numbering stays 4.1/4.2/4.3. No backend, asset store, or copy changes. Share-gate untouched.
- No new Spectrum runtime, no new dependencies, no bundler. Token-bridge `--mod-*` seam in `styles.css` left intact.
- Assumption (reversible): frontier-green replaces red as the interactive-marker hue; bear-brown carries filled secondary buttons.

## Key Decisions

1. **All color via tokens, regen included.** New earth-tone values (warm box parchment, deepened CTA-adjacent tones, pine marker, badge states) are added to `kodiak.json` first, then `npm run tokens:css` regenerates `styles.css`, then `components.css` references only the new `var(--…)`. Unit 0 converts recent raw-hex drift to these tokens.
2. **Pine, not brown, for markers.** Chevrons and active-timeline state go frontier-green: it already means go/active (done states, kickers), stays legible apart from chocolate body text, and reads calm at small sizes.
3. **Timeline badges become outline/fill states.** Todo = tan outline, active = pine fill, done = bear-brown fill, locked = grey. Four states, zero red.
4. **One primary per row for buttons.** Add new assets = bear-brown solid; Browse past assets = kraft outline; Random 3 = small outline; Generate Campaign primary = bear-brown solid (replacing `.btn.orange` red). CTA remains the only ember element.
5. **Focus rings go pine;** error/alert rings stay red.
6. **Concept rows, not a compose section.** Each 4.1/4.2 row pairs selector chip(s) with its compose flag inline through the existing sync functions and ids. Retailer `<select>` deleted; `generate.js` reads the retailer from the active chip (`data-theme`), select kept as fallback until removal is verified.

## Recommended Approach

Token groundwork first (unit 0, unblocks everything), CSS-only de-red + button system next (units 1–2, independently shippable), then the section-4 row restructure reusing existing sync functions and ids (unit 3) so the only behavioral code change is the retailer value source in `generate.js`.

## Work Plan

- **Unit 0 — token groundwork.** Add missing earth values to `design/tokens/kodiak.json`; run `npm run tokens:config` + `npm run tokens:css`; replace raw-hex drift in `components.css` with new refs. Separate commit.
- **Unit 1 — de-red pass (tokens + test pins).** Chevrons ×6 → pine token; timeline 4-state earth badges; focus-visible rings → pine; `.btn.orange` → bear-brown. Pin in `star-button`/`campaign-sections` tests; assert signal-red no longer appears in chevron/timeline/button selectors.
- **Unit 2 — secondary button system (token refs only).** Solid vs outline hierarchy per Decision 4; hover/pressed/disabled from existing elevation tiers.
- **Unit 3 — concept rows (markup + token-ref CSS + 2 small JS edits).** Retailer row (3 chips + retailer-mark flag, select deleted); partner row (chip + partner-mark flag + mark preview inline); mark-less concepts chip-only; product-image flag stays on 4.2 restyled to match; both "Compose" subheadings deleted; dead `#layerPicker` refs removed; `generate.js` retailer source → active chip. Chip/checkbox ids unchanged.
- **Unit 4 — verify + ship.** Vitest, Playwright render past gate (desktop + 390px mobile), functional pass (chip→flag, flag→chip, retailer switch, Random 3, tray), bump/deploy/curl, commit + push as one commit per unit.

## Validation Plan

- `npm run tokens:css` regenerates cleanly; `git diff --stat` shows `styles.css` regenerated, never hand-touched mid-unit.
- `npx vitest run` — 115+ pass, including new de-red pins, a no-raw-hex scan on added `components.css` lines, and a retailer-source test (chip-selected Costco ⇒ `layers.retailer === 'costco'` with no select in DOM).
- Playwright: desktop + mobile screenshots; eyeball chevrons, timeline states, button hierarchy, concept rows; zero `pageerror`.
- Equivalence script toggling each concept pre/post change shape; diff of `layers{}` must be empty.
- Live: `curl` new selectors present in served CSS/HTML post-invalidation.

## Risks / Rollback

- Risk: chip↔flag sync regression. Mitigation: ids and sync functions preserved; equivalence check plus existing prompt-chips/campaign-sections suites gate it. Rollback: one-commit revert per unit.
- Risk: token regen churns `styles.css` beyond the new values. Mitigation: diff regen output before use; if unrelated drift appears, pin the file to the new tokens only and report.

## Open Questions

None — repo, toolchain, and inventory answered the structural questions; remaining choices are stated assumptions overturnable at approval.
