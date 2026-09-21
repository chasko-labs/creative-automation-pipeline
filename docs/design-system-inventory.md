# Kodiak Frontier — Living Element Inventory + Design Standards

> living document. label every "thing" on the frontend so it can be prototyped in adobe express, then
> pinned back to the token layer. maintained as the frontend evolves — when an element changes, update
> its row here in the same change.
>
> scope: `web/kodiak-posts-for-todays-frontier/` (index.html + details.html + `design/styles.css` +
> `design/components.css`). as of the 0.1.016 atomization, index.html's inline `<style>` block was
> extracted to hand-authored `design/components.css`; details.html still carries its inline block.
> file architecture (js/ siblings, css split, load order) lives in `docs/frontend-architecture.md`.
> token source of truth: `design/tokens/kodiak.json` (W3C DTFM) -> `panda.config.ts` (emitTokensOnly) ->
> `web/.../design/styles.css` (css custom properties, `--colors-*`, `--gradients-kraft.*`, `--shadows-*`)
> companion docs: `docs/kodiak-style-guide.md` (7-part), `docs/kodiak-shading.json` (tint/shade ladders + wcag)

## how to read this

- **label** — the adobe-express-friendly name for the element. use this exact name when prototyping.
- **selector** — the css class / id / tag that renders it today
- **surface** — what sits behind it (background rule)
- **state** — `built` (shipped + on-token), `built-drift` (shipped but hardcodes hex off-token), `stub` (shape only, no behavior), `undocumented` (exists, no standard written until now)

---

## 1. token layer state (the foundation everything else grades against)

| token group     | source                           | state | notes                                                                                   |
| --------------- | -------------------------------- | ----- | --------------------------------------------------------------------------------------- |
| brand colors    | kodiak.json color.brand          | built | bearBrown #3B2316, blazeOrange #E8530E, frontierGreen #1A3C34                           |
| neutral ramp    | kodiak.json color.neutral 0-1000 | built | warm ramp: 50 parchment #FFF8F0 ... 900 ink #1A1110                                     |
| semantic        | color.semantic                   | built | background / foreground / border / overlay — the layer components SHOULD consume        |
| kraft gradients | gradient.kraft                   | built | pure-css, zero rasters: surface / background / surfaceHover |
| shadow scale    | shadow.\*                        | built | none/sm/md/lg + warm `bear` #3B231633 + `text`                                          |
| radii           | radius.\*                        | built | none 0 (creative full-bleed) ... pill 999 (protein badge)                               |
| typography      | typography.\*                    | built | per-ratio headline/body/caption sizes; families: gin, museo-sans, Roar, kodiak_sans     |

## 2. the drift finding (why standards are needed, not just an inventory)

the token layer is mature. the two HTML files do **not** fully consume it. after the 0.1.016 atomization,
index.html's styles moved into hand-authored `design/components.css` — the ad-hoc palette described below now
lives at the top of `components.css` (and still inline in details.html). the drift is unchanged by the move;
extraction relocated it, it did not resolve it. each style layer redeclares an ad-hoc palette that diverges
from the tokens:

| inline var       | inline value | token equivalent             | verdict                                                                             |
| ---------------- | ------------ | ---------------------------- | ----------------------------------------------------------------------------------- |
| `--chocolate`    | `#382316`    | bearBrown `#3B2316`          | off-token — 3-hex drift, reads identical but is not the token                       |
| `--brown`        | `#382316`    | bearBrown `#3B2316`          | off-token — same drift                                                              |
| `--brown-kodiak` | `#3B2316`    | bearBrown `#3B2316`          | on-token (correct)                                                                  |
| `--red`          | `#B51E14`    | (none)                       | NOT a brand token — blazeOrange is `#E8530E`; this red is invented for CTAs + links |
| `--parchment`    | `#FFF8F0`    | neutral.50                   | on-token value, but hardcoded not `var(--colors-neutral-50)`                        |
| `--stone`        | `#D9CFC6`    | neutral.300 / border.default | on-token value, hardcoded                                                           |
| `--oat`          | `#F4EDE6`    | neutral.100                  | on-token value, hardcoded                                                           |

gradients and shadows ARE consumed on-token (`var(--gradients-kraft\.surface)`, `var(--shadows-md)`).
colors are the drift surface.

**standard S1 — color source.** every color reference resolves to a token var. no raw hex in element
styles except where a token does not yet exist. the `--red #B51E14` CTA/link color must either become a
token (`color.brand.signalRed` or similar) or be replaced by blazeOrange `#E8530E`. decision pending; until
then, flag every use.

**standard S2 — no ad-hoc palette per file.** the inline `:root{}` palette block was duplicated across
index.html and details.html. index.html's copy now lives in `design/components.css` after the atomization;
details.html still has its inline copy. both should be deleted in favor of the shared styles.css token layer,
or reduced to only the mappings that styles.css does not yet provide.

---

## 3. shared elements (define once, apply everywhere)

these appear on both pages. prototype them once in adobe express as reusable components.

### 3.1 page ground

| label               | selector        | surface                                                                          | state |
| ------------------- | --------------- | -------------------------------------------------------------------------------- | ----- |
| Page Background     | `body`          | `--gradients-kraft.background` (corrugated kraft box) over parchment             | built |
| Paper Fiber Overlay | `body::before`  | inline svg hairlines, opacity .18, multiply                                      | built |
| Kraft Grain Overlay | `#paperGrain`   | inline SVG feTurbulence data-URI tiled 240px, opacity .05, multiply, fixed z900 (PNG retired: 261KB for an invisible texture) | built |
| Edge Vignette       | `#edgeVignette` | radial darkening at far corners only, fixed z901                                 | built |

**standard S3 — decorative overlays never intercept events.** every fixed decorative layer carries
`pointer-events:none` + `aria-hidden="true"`. this is already enforced in comments; keep it a hard rule.
also: no `filter`/`backdrop-filter` on `html`/`body` (breaks position:fixed for these overlays — the
classic filter-containing-block trap; contrast bump is applied to `.wrap`/header instead).

### 3.2 header cluster

| label            | selector                          | surface                                     | state       |
| ---------------- | --------------------------------- | ------------------------------------------- | ----------- |
| Top Strip        | `.kodiak-topstrip`                | bearBrown `#382316` (drift)                 | built-drift |
| Header Bar       | `header.kodiak-header`            | bearBrown `#382316` + kraft surface overlay | built-drift |
| Logo Disc        | `.kodiak-header__logos`           | kraft-tan radial + circular mask            | built       |
| Logo (primary)   | `.kodiak-header__logo--primary`   | bear PNG, swaps to wordmark on sticky       | built       |
| Logo (secondary) | `.kodiak-header__logo--secondary` | wordmark, opacity 0 until sticky            | built       |
| Title Block      | `header h1` in red block          | `--red #B51E14` (NOT a token)               | built-drift |

**standard S4 — logo determinism.** bear PNG at 140w @ 24,24 offset, clearSpace 0.25x width, min 32h/80w,
reversal only on bearBrown/frontierGreen/ink/black (never on blazeOrange or busy photo without scrim).
sourced from `docs/kodiak-style-guide.md` section 2. the header title block currently sits on invented red
`#B51E14` — flag against S1.

**standard S5 — heading contrast guard.** the global `h1,h2,h3{color:var(--chocolate)}` rule renders
brown-on-brown (~1.01:1) on the brown header. header headings are force-set to parchment (~12:1, AA).
any new heading placed on a dark surface must repeat this override.

### 3.3 buttons

| label             | selector        | surface / fill                   | state       |
| ----------------- | --------------- | -------------------------------- | ----------- |
| Button (primary)  | `.btn`          | bearBrown fill, parchment text   | built-drift |
| Button (accent)   | `.btn.orange`   | `--red #B51E14` fill (NOT blaze) | built-drift |
| Button (ghost)    | `.btn.ghost`    | parchment fill, bearBrown text   | built-drift |
| Button (disabled) | `.btn:disabled` | opacity .5                       | built       |

**standard S6 — CTA fill.** primary = bearBrown. accent/CTA should be blazeOrange `#E8530E` per style guide
("accent / CTA / alert"). the `.btn.orange` currently uses invented red `#B51E14`. this is the single most
visible drift — the brand's signature accent is orange, not red. flag against S1; recommend resolving to
blazeOrange or formally adopting the red as a token with a documented rationale.

### 3.4 primitives

| label        | selector       | surface                                  | state |
| ------------ | -------------- | ---------------------------------------- | ----- |
| Badge        | `.badge`       | bearBrown fill, `#FFDCC3` warm text      | built |
| Keycap       | `.kbd`         | oat fill, stone border, mono font        | built |
| Field Label  | `.field label` | none — uppercase tracked caption         | built |
| Offline Note | `.offline`     | kraft surface, dashed stone border       | built |
| Hint Text    | `.hint`        | none — muted `#6B5A53` (AA on parchment) | built |

---

## 4. elevation + card system (the "cards" the brief asks about)

kodiak cards are kraft-paper surfaces with warm-tinted depth. three elevation levels map to the shadow scale.

| elevation | shadow token     | value                 | used by                                | surface                                               |
| --------- | ---------------- | --------------------- | -------------------------------------- | ----------------------------------------------------- |
| flat      | `--shadows-none` | 0                     | inline fields, chips                   | inherits page                                         |
| raised    | `--shadows-sm`   | 0 2px 8px ink 15%     | `.tile`, `.render-tile`, `.provenance` | `--gradients-kraft.surface`                           |
| card      | `--shadows-md`   | 0 8px 24px ink 20%    | `.card`                                | `--gradients-kraft.surface`, hover -> `.surfaceHover` |
| floating  | `--shadows-lg`   | 0 16px 48px ink 25%   | (reserved — billboard/modal)           | —                                                     |
| bear      | `--shadows-bear` | 0 12px 32px brown 20% | `.ff-prompt` (the hero prompt bar)     | kraft surface                                         |

**standard S7 — elevation semantics.** raised = passive containers (preview tiles). card = interactive
grouped content (the main panels). bear = the single hero element on a page (warm brown-tinted lift draws
the eye to the primary action). do not stack two `bear`-shadowed elements on one screen.

**standard S8 — card anatomy.** a `.card` is: kraft surface + 1px stone border + 4px radius + `--shadows-md`

- a `.card::before` wood-grain overlay at 6% + optional `.hd` header strip (`#FFFBF6` + kraft hairline,
  stone bottom border) + `.body` (16px pad). hover swaps surface to `.surfaceHover` (adds blazeOrange 12%
  bloom top-right).

| label           | selector      | surface                                        | state |
| --------------- | ------------- | ---------------------------------------------- | ----- |
| Card            | `.card`       | kraft surface + wood grain + md shadow         | built |
| Card Header     | `.card .hd`   | `#FFFBF6` + kraft hairline                     | built |
| Card Body       | `.card .body` | inherits card                                  | built |
| Hero Prompt Bar | `.ff-prompt`  | kraft surface + `--shadows-bear` + 16px radius | built |

## 5. page-specific elements — index.html (the app)

| label                  | selector                               | surface / fill                                                 | state |
| ---------------------- | -------------------------------------- | -------------------------------------------------------------- | ----- |
| Campaign Prompt Bar    | `.ff-prompt`                           | kraft surface, bear shadow                                     | built |
| Guided Setup Step      | `.ff-setup` + `data-step` badges (1-4) | neutral-100 panel; numbered badges pure CSS, no a11y DOM       | built |
| Prompt Input Wrap      | `.ff-inputwrap`                        | white, stone border; focus-within -> blazeOrange ring          | built |
| Prompt Textarea        | `#campaignBrief`                       | transparent inside wrap                                        | built |
| Upload Icon Button     | `.ff-iconbtn` `#promptUpload`          | white, stone border, oat hover                                 | built |
| Create Button          | `.ff-go` `#generateCampaign`           | blazeOrange fill (uses `--orange` fallback #E8530E — ON TOKEN) | built |
| Suggestion Chips       | `.ff-chip` (x6)                        | white pill, stone border; pressed -> bearBrown fill            | built |
| Chip Accent Dot        | `.ff-dot`                              | blazeOrange dot                                                | built |
| Product Chooser        | `#productChooser`                      | grid of SKU checkboxes                                         | built |
| Product Search         | `#productSearch`                       | field input                                                    | built |
| Preview Grid           | `.preview` `#preview`                  | auto-fill 240px tiles                                          | built |
| Preview Tile           | `.tile`                                | kraft surface, sm shadow                                       | built |
| Preview Canvas         | `.tile canvas`                         | bearBrown fill (renders composed creative)                     | built |
| Render Set             | `.render-set`                          | auto-fit 220px, 3 labeled ratio tiles                          | built |
| Render Tile            | `.render-tile` (r-1x1 / r-4x5 / r-2x3) | aspect-ratio-locked frame                                      | built |
| Provenance Panel       | `.provenance`                          | native details/summary, kraft surface                          | built |
| Provenance Pills       | `.prov-pill` (primary/outpaint/on/off) | brown/oat/green fills                                          | built |
| Mountain Ridge Divider | inline `--mountain` svg                | frontier-green ridge silhouette                                | built |
| About Tool Disclosure  | `#aboutTool`                           | card, details/summary                                          | built |
| Build Stamp            | `#buildStamp`                          | muted mono version string                                      | built |

> note: `.ff-go` (Create) reads `var(--orange, #E8530E)` — this is the ONE CTA already on the correct
> blazeOrange. it proves the accent should be orange everywhere; `.btn.orange` using red is the outlier.

**cross-cutting index.html:** the interactive prompt bar (Firefly-style) is the intended focal point. the
`bear` elevation is correctly reserved for it. suggestion chips are the secondary affordance.

## 6. page-specific elements — details.html (design system + details)

| label                    | selector              | surface                                          | state |
| ------------------------ | --------------------- | ------------------------------------------------ | ----- |
| Back Link                | `.backlink`           | in header, parchment text                        | built |
| Frontier Toggle Card     | `#frontierToggleCard` | card, frontier-green left rule                   | built |
| Design System Scorecards | `#design-system`      | card holding a live grid                         | built |
| Scorecard Tile           | `#scoreGrid > div`    | white, stone border, 12px radius                 | built |
| Score Progress Bar       | inline in scorecard   | frontier-green (pass) / blazeOrange (needs work) | built |

**standard S9 — the scorecards are the existing self-audit.** details.html already grades the app against
tokens on 12 axes (brand-token fidelity, typography, paper texture, logo, spacing, tool-focus, offline,
image-path, a11y, perf, localization, data). this inventory doc is the human-readable companion to that
machine grader. keep them aligned: a new element added here should get a scorecard axis if it is
brand-load-bearing.

---

## 7. adobe express prototyping key

when rebuilding an element in adobe express, use these exact values (all resolve from tokens):

| need               | value                                                                   |
| ------------------ | ----------------------------------------------------------------------- |
| page background    | kraft-tan `#E8D5BE` -> `#DFC9AC` gradient (or flat `#FFF8F0` parchment) |
| card surface       | kraft-tan `#F0E4D4` -> `#EAD9C4` gradient                               |
| primary text       | bearBrown `#3B2316` (10.2:1 on parchment, AAA)                          |
| muted text         | canyon `#6B5A53` (~6:1, AA)                                             |
| primary fill       | bearBrown `#3B2316`                                                     |
| accent / CTA       | blazeOrange `#E8530E` (large text/CTA only — 3.1:1, fails body)         |
| secondary / nature | frontierGreen `#1A3C34` (12.1:1, AAA)                                   |
| card radius        | 4px (creative edges) / 8px (soft card) / 16px (button+chip)             |
| card shadow        | 0 8px 24px `#1A1110` at 20%                                             |
| headline font      | gin / Rockwell / Clarendon, extraBold 800, uppercase, tracked           |
| body font          | museo-sans / Inter, 400-500                                             |
| accent bar         | 8px solid blazeOrange at bottom edge (brand signature)                  |

**standard S10 — the iconic-box principle** (from `kodiak-shading.json`): bearBrown is ALWAYS primary
bg/text/logo-backdrop. orange is ONLY the 8px bar, CTA, protein callout, and glow overlay (<=18% opacity
or tint >=30%). green is secondary — borders, panels, wasatch dawn — never large enough to outshine the
brown pack. tints for backgrounds, shades for hover/pressed/depth.

---

## 8. open standards decisions (flag, do not silently fix)

- **D1 — the invented red `#B51E14`.** used for links, `.btn.orange`, and the header title block. it is not
  a brand token and it competes with blazeOrange as "the accent." decide: adopt as a token, or replace with
  blazeOrange. blocks S1 closure.
- **D2 — inline palette duplication.** the `:root{}` block is copied into both HTML files. decide: delete in
  favor of styles.css, or keep as a documented per-file shim.
- **D3 — chocolate `#382316` vs bearBrown `#3B2316`.** 3-hex drift, visually identical. decide: normalize to
  the token everywhere, retire `--chocolate`.

these are design-system governance calls, not mechanical fixes. they belong to the product owner.

---

## 9. axis A — the 4-view responsive dimension (form + function per viewport)

> appended 2026-09-05 by ghost-stratia-ux-research from live index.html
> (`web/kodiak-posts-for-todays-frontier/index.html`), grounding the responsive axis the
> prep spec named. this section grades each element's form + function across four viewports:
> mobile 375 / tablet 768 / desktop 1440 / ultrawide 2560.

**live CSS breakpoint reality (read before trusting any wide-view row).** the prior pass
reported "only ONE layout breakpoint @860px." that is not accurate against the live file. the
content-layout media queries are actually TWO, plus two non-layout queries:

| media query                     | line region | what it restructures                                                              |
| ------------------------------- | ----------- | --------------------------------------------------------------------------------- |
| `@media(max-width:860px)`       | L119        | `.grid` 2-col -> 1-col (the main two-panel split)                                  |
| `@media(max-width:860px)`       | L156        | `.kodiak-header__logos` shrinks to `clamp(64px,16vw,88px)`                         |
| `@media(max-width:860px)`       | L177        | `.ff-inputwrap` wraps, textarea goes full-width, `.ff-go` stretches               |
| `@media(max-width:640px)`       | ~L437       | `.ff-controlrow` -> column, `.ff-market>summary`/`.ff-season select` full-width   |
| `@media(prefers-reduced-motion)`| L140, L157  | disables transitions (not a layout query)                                         |

so the true finding: TWO layout breakpoints (860 for the main grid + prompt row, 640 for the
control row), and NO breakpoint above 860px. desktop (1440) and ultrawide (2560) share the exact
same ruleset — nothing differentiates them. that is the real form gap on the wide end. mobile
(375) and tablet (768) both sit below 860 AND below 640, so they share BOTH collapsed rulesets;
nothing differentiates 375 from 768 either. the design has effectively two states — "narrow"
(<=640) and "wide" (>860) — with a thin 641-860 band where the grid is single-col but the control
row is still a row. four named viewports, two actual layouts.

**standard S11 — four-view form+function parity.** every brand-load-bearing element must have a
defined form at mobile 375, tablet 768, desktop 1440, ultrawide 2560. where the current CSS cannot
differentiate two named viewports (the 375/768 pair and the 1440/2560 pair), that is a gap to be
flagged, not a pass. wide-end behavior (does the prompt card stretch edge-to-edge at 2560, does the
preview grid reflow to more columns, does line length exceed comfortable measure) is UNKNOWN from
CSS reading alone — it requires a rendered screenshot pass. those rows are marked TBD-verify.

> TBD-verify is EXPECTED and CORRECT here. a headless screenshot pass at the four breakpoints
> (ghost-liora-headless-verifier) is currently BLOCKED on a session MCP failure. do not treat the
> absence of screenshots as a defect in this inventory — treat every wide-reflow claim as a
> hypothesis pending that pass. express mcp grounds what we generate; it does not render the live
> screen, so it cannot close these rows either.

### 9.1 per-element narrow-vs-wide table

| element                    | selector             | narrow (<=640 / 375+768)                                              | wide (>860 / 1440+2560)                                             | flag                                                                 |
| -------------------------- | -------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------- | -------------------------------------------------------------------- |
| Main two-panel grid        | `.grid`              | single column, panels stack                                           | two columns `1fr 1fr`                                               | TBD-verify: no >860 rule — 1440 and 2560 identical, wide whitespace  |
| Header logo disc           | `.kodiak-header__logos` | `clamp(64px,16vw,88px)`                                            | native size                                                         | ok — the one element with a fluid clamp                              |
| Prompt input wrap          | `.ff-inputwrap`      | wraps; textarea `flex:1 1 100%`; `.ff-go` stretches full-width        | single row, textarea + button inline                               | ok narrow; TBD-verify wide max-width at 2560                         |
| Control row                | `.ff-controlrow`     | `flex-direction:column` @640; market button + season full-width       | single wrapping row of pills                                        | ok narrow; TBD-verify wrap behavior in 641-860 band                  |
| Market disclosure summary  | `.ff-market>summary` | full-width, `justify-content:space-between` @640                       | intrinsic-width pill                                                | ok                                                                   |
| Market disclosure panel    | `.ff-market-panel`   | `left:0;right:0` (full-bleed) @640                                      | `min-width:280px;max-width:min(92vw,420px)` popover                 | ok narrow; TBD-verify: 340px max-height scroll on tall 2560          |
| Seasonal select            | `.ff-season select`  | full-width @640                                                        | intrinsic pill                                                      | ok                                                                   |
| Featured + langs detail    | `.ff-detail`         | `flex:1 1 220px` stacks under controls                                 | inline third cell of the row                                        | TBD-verify: langs line wrap at 375                                   |
| Preview grid               | `.preview` `#preview`| `auto-fill minmax(240px,...)` -> 1 col at 375                           | auto-fill, more columns as width grows                             | TBD-verify: column count at 1440 vs 2560 (auto-fill IS fluid — likely the ONE element that uses ultrawide width, needs screenshot to confirm count) |
| Render set                 | `.render-set`        | `auto-fit minmax(220px,...)` -> stacks                                  | up to 3 ratio tiles inline                                          | TBD-verify: does auto-fit add a 4th phantom track at 2560            |
| Card                       | `.card`              | full-width in stacked grid                                             | half-width in 2-col grid                                            | TBD-verify: measure/line-length at 2560 half-column                  |
| Product chooser disclosure | `.ff-products`       | full-width summary line                                                | intrinsic disclosure                                                | ok — closed by default, one summary line at rest all viewports       |
| Selection tray             | `.ff-tray`           | wraps chips, collapses when empty                                     | wraps chips                                                        | ok — flex-wrap handles all widths                                    |

**form gaps that are certain (no screenshot needed):**

- no >860px breakpoint exists, so 1440 and 2560 render byte-identical CSS. any intended
  ultrawide-specific treatment (max content width, multi-column reflow of the main grid beyond
  2 columns, larger creative previews) is simply absent. the layout will grow whitespace, not
  structure, past ~1400px unless an element uses an intrinsically-fluid track.
- `.preview` and `.render-set` use `auto-fill`/`auto-fit minmax()` — these ARE intrinsically
  fluid and are the only elements that will use extra ultrawide width by adding columns. exact
  column counts at 1440 vs 2560 are TBD-verify.
- mobile 375 and tablet 768 are undifferentiated (both below both breakpoints). a tablet-specific
  layout (e.g. 2-col control row but stacked main grid) does not exist.

---

## 10. axis B — translation as a first-class element (THE highest-value gap)

> appended 2026-09-05 by ghost-stratia-ux-research. this is the single highest-value functional
> gap in the frontend: the site advertises localization on every surface but renders ZERO
> per-market translated copy. the data to do it exists and is rich; the render path is a
> deliberate no-op.

**the core finding, grounded in the live file.** `renderLangChips()` at index.html L748 is not a
partial implementation — it is a hard no-op that actively REMOVES its own target from the DOM:

```
function renderLangChips(){
  // declutter — lang-chips removed from the app page (non-interactive, hardcoded markets).
  // kept as a safe no-op so fillSelects/change-listener/setTimeout/async-fetch callers never throw.
  const el = document.getElementById('lang-chips');
  if(el && el.parentNode) el.parentNode.removeChild(el);
}
document.addEventListener('change', e=>{ if(e.target && e.target.id==='locality') renderLangChips(); });
```

so every caller (the `#locality` change listener at L754, plus the async market-file upgrade
fetch) invokes a function whose entire behavior is to delete `#lang-chips`. no localized copy is
ever produced client-side. translation is entirely missing as rendered output.

**the data is present and abundant — the gap is purely render.** `data/localization/` carries:

- `market-languages.json` — 74 markets, top-2 non-English language per market with real ACS
  S1601 percentages, `translate_code` per language, 222 total localized variants
  (74 markets x 3 variants EN + top2). metadata declares `auto_produce:true`, `nova_proven:true`.
- `localization-training-data.jsonl` + `localization-table-seed.json` — seeded localized copy.
- `local-flavor.json`, `dialect/`, regional dirs — per-market cue/message localization.
- the manifest (L10-12) advertises a `localize` mcp tool and `"languages":"EN + top2 per market
  (ACS 2022)"`.

**standard S12 — translation is a first-class rendered element, not a badge.** any surface that
claims localization must render actual localized copy for the selected market, sourced from
`market-languages.json` (or the live `localize` tool), not a static string. the deliverable is
preview/render of localized captions per market + language, driven by the selected market's
`top_languages[]`. a hardcoded language list that never changes with market selection is a
violation of S12.

### 10.1 every surface that SHOULD render localized copy — each MISSING

| surface                    | selector / location            | what it claims                                                    | what it renders today                                                  | state    |
| -------------------------- | ------------------------------ | ----------------------------------------------------------------- | ---------------------------------------------------------------------- | -------- |
| Manifest tools list        | `<meta mcp:tools>` L10          | advertises `localize` tool                                        | tool listed, never invoked client-side                                 | MISSING  |
| Manifest languages field   | webmcp-manifest JSON L12         | `"EN + top2 per market (ACS 2022)"`                               | static string in manifest, no runtime binding                          | MISSING  |
| Language chips             | `#lang-chips` (via renderLangChips) | per-market localized language chips                            | function DELETES the node — no-op stub                                  | MISSING  |
| Market languages line      | `#marketLangLine` `.ff-langs` L658 | localized-in language list for the chosen market               | hardcoded `English, Spanish, Portuguese` — never changes with market   | MISSING  |
| Featured-frontier note     | `#featuredFrontier` `.ff-featured` L657 | localized frontier/featured copy per market               | empty `aria-live` region, no localized fill wired                      | MISSING  |
| Localized font faces       | `@font-face` block L565+        | self-hosted Noto per-script (CJK/Cyrillic/etc), unicode-range split | `@font-face` rules present but woff2 binaries NOT in repo (`./fonts/`) | MISSING (binaries absent) |
| Create button variant fan  | `#generateCampaign` `.ff-go` L623 | "fans to all formats + localized variants"                     | button label promises localized variants; no localized render path     | MISSING  |
| Preview tile captions      | `.tile` / `.render-tile` copy   | localized caption per rendered creative                           | canvas renders composed creative; caption localization absent          | MISSING  |
| Provenance localization    | `.provenance` / `.prov-pill`    | provenance of the localization/translate step                     | no localize provenance pill                                            | MISSING  |

**the core deliverable (wave 2/3):** wire the selected market -> its `top_languages[]` from
`market-languages.json` -> render localized caption previews on the preview/render tiles AND
update `#marketLangLine` + `#featuredFrontier` to the selected market's real languages. replace
`renderLangChips()` from a delete-stub to a real per-market chip renderer, or fold its job into
the market-disclosure selection handler. this is the highest-value gap because the entire
data + provenance layer already exists (222 variants, Nova-proven) and only the render path is
stubbed out.

---

## 11. axis C — market vs featured-frontier taxonomy (derived, grouped, alpha-by-state)

> appended 2026-09-05 by ghost-stratia-ux-research. reclassifies the location control under the
> two-bucket product vocabulary the prep spec named, derived from live data shape.

**the two buckets, grounded in the two data files that back the 74 markets:**

- **market** = has a commercial retail footprint. in `store-finder-markets.json` every record
  carries a `retailer` field naming chain grocers (e.g. Park City: `Target (Kimball Junction),
  Walmart (Kimball Junction), Smith's Food & Drug`). where you can buy Kodiak Cakes on a shelf.
- **featured frontier** = no commercial retail chain — general store / farmers-market /
  subscription only. in `frontier-gaps.json` every record carries `retail_gap` (e.g. Timberon:
  `No grocery chain; nearest full grocer 45min... General Store limited SKU`), plus
  `frontier:true` and `subscriber_variant:true`. recipe-source and DTC/subscription markets.

**standard S13 — location_class is DERIVED, not a schema field.** do not add a `location_class`
field to the 73 records and do not migrate the four-value `classification` (metro / regional /
frontier / frontier-gap). derive at render time:

```
location_class = has_commercial_retail(record) ? "market" : "featured-frontier"

has_commercial_retail(record):
  true  if record.retailer names a chain grocer (Target/Walmart/Smith's/Costco/Publix/HEB/Kroger/...)
  false if record.retail_gap is present, OR retailer is only a general-store / farmers-market,
        OR the record originates from frontier-gaps.json (frontier:true + subscriber_variant:true)
```

this keeps the rich schema intact (`classification`, ACS language data, retailer strings, cross-
promo) while giving the clean two-bucket product language. the mapping the prep spec named holds:
metro + regional + frontier (with a chain grocer in `retailer[]`) => market; frontier-gap
(retail_gap / general-store / farmers-market, DTC-only) => featured-frontier.

**standard S14 — group by class first, then alphabetize by state within each group.** the
selector renders two labeled groups ("Markets" then "Featured Frontier"), and within each group
sorts alphabetically by state (AK, AZ, CA, ..., UT, VT, WA). this replaces the current flat,
unsorted, ungrouped ordering (raw file order). ordering rule is: class bucket (markets before
featured-frontier) -> state alpha -> place alpha within a state.

### 11.1 controls that should surface the market / featured-frontier label

| control                    | selector             | today                                                              | should                                                                 | verdict                        |
| -------------------------- | -------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------ |
| Market disclosure listbox  | `#marketListbox` `.ff-market-panel` L634 | accessible `role=listbox` of 78 places, flat        | grouped into Markets / Featured Frontier headers, alpha-by-state each   | RIGHT HOME — apply S13 + S14   |
| Market option row          | `[role=option]` + `.ff-opt-sub` | option with sublabel slot (`.ff-opt-sub`) available    | sublabel shows class + state ("Market — UT" / "Featured Frontier — NM") | RIGHT HOME — sublabel is built for this |
| Selected option state      | `[role=option][aria-selected=true]` | frontier-green fill on selected                     | plus class-aware summary label on the button                           | apply                          |
| Market button label        | `#marketButtonLabel` `.ff-market-name` L630 | shows place name (`Park City, Utah`)               | may prefix/annotate with class when useful                             | apply                          |
| Featured-frontier note     | `#featuredFrontier` `.ff-featured` L657 | empty                                             | render the featured-frontier framing when a featured-frontier market picked | apply (also an S12 surface) |
| Flat locality select       | `#locality` <select>  | populated in raw `places[]` order, no grouping, no sort (change listener at L754 still bound) | DEPRECATE — the flat select is the migration target, not the home | DEPRECATION TARGET             |

the `.ff-market` disclosure listbox is the correct home for the reclassified selector: it already
has `role=listbox`, `role=option` rows, `aria-selected`, and a `.ff-opt-sub` sublabel slot purpose-
built to carry the class + state annotation. the flat `#locality` select is the deprecation target
— it renders in raw order with no grouping or sort and cannot express the two-bucket taxonomy.

---

## 12. spectrum migration candidates (token-bridged, not token-replacing)

> appended 2026-09-05 by ghost-stratia-ux-research. ranks which bespoke `.ff-*` controls are the
> best candidates to migrate onto adobe spectrum `sp-*` web components, WITHOUT replacing the
> kodiak token layer — spectrum components are token-bridged: their custom properties are fed the
> existing `--colors-* / --radii-* / --shadows-*` kodiak tokens so brand fidelity is preserved.

**standard S15 — spectrum adoption is token-bridged, not token-replacing.** a migrated control
keeps the kodiak look by mapping kodiak tokens onto the spectrum component's theming custom
properties (e.g. feed `--colors-brand-frontier-green`, `--radii-lg`, `--shadows-sm` into the
`sp-*` element's exposed vars). never let a spectrum default palette override a kodiak token. the
migration is worth it only where the `sp-*` component removes bespoke a11y/interaction code we
currently hand-maintain. bridge, do not replace.

### 12.1 ranked sp-* replacement table

| rank | current control            | selector             | sp-* target                     | why migrate                                                                                          | token bridge (kodiak -> sp)                                                                                 |
| ---- | -------------------------- | -------------------- | ------------------------------- | ---------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| 1    | Market disclosure listbox  | `.ff-market` / `#marketListbox` | `sp-picker` + `sp-menu-group`   | TOP candidate — `sp-menu-group` gives grouped-with-header + accessible listbox for free, which ALSO delivers S14 (group-by-class, alpha-by-state) with zero hand-rolled grouping code; retires the bespoke disclosure + manual `role=option`/`aria-selected` wiring | `--radii-lg`, `--shadows-md`, `--colors-brand-frontier-green` (selected), `--colors-brand-bear-brown` (open), `--colors-neutral-50/100`, `--colors-foreground-*` |
| 2    | Seasonal select            | `.ff-season select`  | `sp-picker`                     | native `<select>` styling is browser-inconsistent; `sp-picker` normalizes it + keyboard nav          | `--radii-lg`, `--colors-brand-blaze-orange` (border), `--shadows-sm`, `--colors-neutral-50/100`             |
| 3    | Product search combobox    | `#productSearch` `.ff-products-search` | `sp-combobox`                   | **FUTURE — control not yet in page.** No such combobox exists in index.html today; this is an aspirational target only. `sp-combobox` is confirmed-shipped, but the kodiak product-search control is not built yet. When built, the hand-rolled `role=combobox` + `#productResults` listbox + autocomplete is exactly what `sp-combobox` ships tested | `--radii-sm`, `--colors-border-default`, `--colors-brand-signal-red` (focus), `--colors-foreground-default` |
| 4    | Suggestion / theme chips   | `.ff-chip` (x6)      | `sp-action-group` + `sp-action-button` (toggle) | pressed-state chips map cleanly to toggle action buttons; frees the manual `aria-pressed` handling   | `--colors-brand-bear-brown` (pressed), `--colors-brand-blaze-orange` (dot), `--radii-*`                     |
| 5    | Product chooser disclosure | `.ff-products` **(FUTURE — control not yet in page)** | `sp-accordion` / `sp-accordion-item` (NOTE: `sp-disclosure` is not a real package) | `.ff-products` does not exist as a control in index.html today. Native `<details>` would work; migration is lowest urgency — only if consolidating on spectrum primitives. Disclosure functionality lives in `sp-accordion` / `sp-accordion-item` — there is no `sp-disclosure` package | `--radii-lg`, `--colors-neutral-100/200`, `--colors-brand-signal-red` (caret)                              |
| 6    | Use-my-location button     | `.ff-geo`            | `sp-action-button` (quiet) + `sp-icon`          | low value — small bespoke button; migrate only for icon-system consistency                            | `--colors-border-default`, `--radii-lg`, `--colors-brand-signal-red` (pin fill — already on-token)          |

**top candidate rationale.** `.ff-market -> sp-picker + sp-menu-group` is ranked #1 because it is
the only migration that solves TWO standards at once: it modernizes the control (S15) AND its
`sp-menu-group` primitive natively provides the grouped-header + within-group ordering that S14
requires, deleting the bespoke grouping/sort code before it is even written. it is the highest-
leverage single migration on the board.

**do-not-migrate (keep bespoke).** the hero prompt bar (`.ff-prompt`, `bear` elevation), the
preview/render tiles (`.tile`/`.render-tile`, brand-specific kraft surfaces + aspect-ratio locks),
and all decorative overlays are brand-signature surfaces with no spectrum equivalent — they stay
bespoke and on-token. spectrum is for the generic form controls, not the creative canvas.

> note on S15 + S1 interaction: three `.ff-*` controls above reference `--colors-brand-signal-red`
> (`.ff-geo-pin`, `.ff-products` caret/focus, `.ff-pending-remove` hover). the global focus ring at
> L281 still uses the invented `var(--red)` (#B51E14, non-token per S1/D1). any spectrum migration
> that touches focus styling must resolve to the eventual signal-red TOKEN, not the raw `--red`
> var — do not carry the drift into the sp-* bridge. this keeps S15 aligned with the pending D1
> decision.

---

## 13 — S15 migration record (Option A, token-bridged)

> appended by ghost-orin-ci-cd on branch `feat/kodiak-community-review-langs`. records why kodiak
> bridges its tokens INTO spectrum `--mod-*` rather than adopting the spectrum-web-components
> runtime, plus the changelog of what shipped on this branch.

this branch chose **Option A — a token BRIDGE, not a component swap**. the six `.ff-*` controls stay
native HTML on kodiak tokens; a spectrum `--mod-*` alias layer was published in `design/styles.css`
so a future spectrum adoption has a ready seam. no spectrum-web-components runtime was introduced —
repo tooling is Panda CSS only (`@pandacss/dev 1.12.0`, no bundler/Lit).

### 13.1 why Option A

| element                     | fact                                                                                                                                                                                                                                                        | source                                                                                                                                                                                                                          | confidence         |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------ |
| Panda emitTokensOnly        | with tokens-only emission Panda emits ONLY the token css-variable layer; patterns, utilities, recipes, and animation-styles are NOT emitted (inert)                                                                                                          | <https://github.com/chakra-ui/panda/blob/main/website/content/docs/references/config.mdx> — Emit Tokens Only: "only emit the tokens directory, excluding other generated files"                                                 | CONFIRMED HIGH     |
| composite typography        | under tokens-only, primitive font vars (font-size, and any line-height/weight/letter-spacing modeled as tokens) survive, but the COMPOSITE textStyle utility that binds them into a usable text style is NOT emitted. not overstated as "drops to fontSizes only" | follows from emitTokensOnly excluding the utility layer (not a verbatim Panda doc claim)                                                                                                                                       | INFERENCE / MEDIUM |
| spectrum theming contract   | component custom properties layer as `var(--highcontrast-*, var(--mod-<comp>-<prop>, var(--spectrum-<comp>-<prop>)))`; `--mod-*` is the intended per-component CONSUMER override layer, `--spectrum-*` is the system default                                    | <https://github.com/adobe/spectrum-web-components/blob/main/CONTRIBUTOR-DOCS/02_style-guide/01_css/05_anti-patterns.md> + <https://github.com/adobe/spectrum-css/wiki/Ongoing-updates-and-refactoring>                          | CONFIRMED HIGH     |
| nuance (strengthens Option A) | SWC deprecates authoring NEW `--mod-*` chains INTERNALLY (component-authoring guidance), but `--mod-*` remains the documented external CONSUMER override contract — so bridging kodiak tokens into `--mod-*` targets the right seam                            | <https://github.com/adobe/spectrum-web-components/blob/main/CONTRIBUTOR-DOCS/02_style-guide/01_css/05_anti-patterns.md>                                                                                                         | HIGH               |
| sp-combobox                 | `@spectrum-web-components/combobox` is a real, shipped, documented package (`<sp-combobox>`). upgraded from prior low confidence                                                                                                                              | <https://opensource.adobe.com/spectrum-web-components/components/combobox/>                                                                                                                                                     | CONFIRMED HIGH     |

### 13.2 what shipped on this branch

| commit             | change                                                                                                                                                                                                                                                                                                                                                     |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| D2 (`115a507`)     | details.html specimen cards — swatches, type scale, spacing, elevation, anatomy, do/dont                                                                                                                                                                                                                                                                  |
| D3 (this branch)   | S15 spectrum `--mod-*` bridge token layer appended to design/styles.css — additive; every alias resolves to an existing kodiak `--colors-*`/`--radii-*`/`--shadows-*` token; every focus-indicator resolves to `var(--colors-brand-signal-red)`; no markup or runtime change                                                                               |
| D5 (this branch)   | details.html section 9 rewritten as a MEASURED three-view dimensioned drawing (375/768/1440) — ASCII wireframe + per-element form/function + %-of-space; corrected top-level layout truth (.wrap flex-column stack, NO .grid 1fr 1fr); closed the prior tbd-verify rows for .preview cols / .wrap max-1100 / border-radii; flagged .render-set/.provenance/.platform-copy as interaction-pass follow-ups (not closeable at load) |
| D6 (this branch)   | index.html rizz pass — .ff-controlrow align-items stretch->center (uniform control heights), .ff-prompt radius 16px->`--radii-lg` (on-token hygiene), .ff-geo:focus-visible -> signal-red (focus-ring consistency). tokens only                                                                                                                            |

### 13.3 S15 note

> migration is token-bridged not token-replacing; the do-not-migrate list held (.ff-prompt hero
> elevation, .tile/.render-tile, decorative overlays stay bespoke and on-token); focus styling
> resolves to `var(--colors-brand-signal-red)`, never raw `--red`.
