# Kodiak Frontier — Living Element Inventory + Design Standards

> living document. label every "thing" on the frontend so it can be prototyped in adobe express, then
> pinned back to the token layer. maintained as the frontend evolves — when an element changes, update
> its row here in the same change.
>
> scope: `web/kodiak-posts-for-todays-frontier/` (index.html + details.html + shared design/styles.css)
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
| kraft gradients | gradient.kraft                   | built | pure-css, zero rasters (cloud-del-norte precedent): surface / background / surfaceHover |
| shadow scale    | shadow.\*                        | built | none/sm/md/lg + warm `bear` #3B231633 + `text`                                          |
| radii           | radius.\*                        | built | none 0 (creative full-bleed) ... pill 999 (protein badge)                               |
| typography      | typography.\*                    | built | per-ratio headline/body/caption sizes; families: gin, museo-sans, Roar, kodiak_sans     |

## 2. the drift finding (why standards are needed, not just an inventory)

the token layer is mature. the two HTML files do **not** fully consume it. each `<style>` block redeclares
an ad-hoc palette that diverges from the tokens:

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

**standard S2 — no ad-hoc palette per file.** the inline `:root{}` palette block is duplicated across
index.html and details.html. it should be deleted in favor of the shared styles.css token layer, or reduced
to only the mappings that styles.css does not yet provide.

---

## 3. shared elements (define once, apply everywhere)

these appear on both pages. prototype them once in adobe express as reusable components.

### 3.1 page ground

| label               | selector        | surface                                                                          | state |
| ------------------- | --------------- | -------------------------------------------------------------------------------- | ----- |
| Page Background     | `body`          | `--gradients-kraft.background` (corrugated kraft box) over parchment             | built |
| Paper Fiber Overlay | `body::before`  | inline svg hairlines, opacity .18, multiply                                      | built |
| Kraft Grain Overlay | `#paperGrain`   | `assets/kraft-paper-texture.png` tiled 256px, opacity .025, multiply, fixed z900 | built |
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
