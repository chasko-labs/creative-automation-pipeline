# kodiak-site-rizz-up-notes

concrete, PR-able suggestions to bring our front end (`web/kodiak-posts-for-todays-frontier/index.html`) into tighter alignment with the real Kodiak Cakes brand. this is a SUGGESTIONS doc for the frontend/CSS owners — we are not editing their CSS here. orin surfaces these as PRs.

- our front end: `chasko-labs/creative-automation-pipeline/web/kodiak-posts-for-todays-frontier/index.html`
- token source: `web/kodiak-posts-for-todays-frontier/design/tokens/kodiak.json`, compiled `design/styles.css`
- brand facts + citations: see companion `kodiak-brand-concept-inventory.md` in this dir
- read-only. selectors below are quoted from the live `index.html` this pass. line hints are approximate

## framing

good news first: the front end is ALREADY substantially on-brand. it loads the real Kodiak typekit (`zjt4wyq.css`), uses Bear Brown headers (`#382316`), kraft procedural textures, gin headlines, museo-sans body, a `--colors-brand-*` token layer, and it already has `bears` / `keep-it-wild-program` / `zac-efron` starting-point chips. compose.py already stamps a "Keep It Wild" footer on rendered canvases.

so these are TIGHTENING suggestions, not a rebuild. they close the remaining gaps between what the tool renders and what kodiakcakes.com actually looks like. ordered by impact.

## suggestions matrix (impact-ordered)

| #   | suggestion                                                         | brand basis                                               | target selector/component                                  | effort | impact |
| --- | ------------------------------------------------------------------ | --------------------------------------------------------- | ---------------------------------------------------------- | ------ | ------ |
| 1   | apply the real growling bear-head mark as a page + preview motif   | bear-head is the core mark; "bear sightings" voice        | `.kodiak-header__logos`, new `.bear-sighting` overlay      | low    | high   |
| 2   | reconcile accent color — blaze orange vs live signal red           | live CTA is `#b51e14`, we mix `#E8530E` and `--red`       | `.ff-inputwrap:focus-within`, `.ff-go`, `.ff-chip .ff-dot` | low    | high   |
| 3   | add a Keep It Wild footer lockup to the PAGE (not just the canvas) | KIW is a persistent nav + footer element on the real site | new `<footer class="kodiak-footer">`                       | low    | high   |
| 4   | CBO / athlete persona card treatment                               | Zac CBO + athlete roster front the brand                  | new `.persona-card` component + chip enrichment            | med    | high   |
| 5   | fix stale typography token so tokens match the rendered faces      | token says Rockwell/Inter, site renders gin/museo-sans    | `design/tokens/kodiak.json` typography block               | low    | med    |
| 6   | strengthen the "bear sightings" playful voice in UI copy           | newsletter voice: "recent bear sightings at Kodiak"       | chip labels, `#promptChipsLabel`, hints                    | low    | med    |
| 7   | frontier headline type treatment on the H1                         | epic uppercase tracked gin, mountain-town rugged          | `.kodiak-headline-plate h1`                                | low    | med    |
| 8   | Vital Ground co-badge slot for conservation campaigns              | KIW co-brands with Vital Ground                           | `keep-it-wild-program` chip -> co-badge reveal             | med    | med    |

## 1. apply the real growling bear-head mark (highest visual-identity win)

what the real brand does: the growling bear-head is Kodiak's core mark, and the brand treats the bear as a recurring character ("recent bear sightings at Kodiak" in every newsletter signup). see `kodiak-brand-concept-inventory.md` concept 1.

what our front end does today: the header (`index.html`, header block ~L460) loads `assets/kodiak-primary-logo_optimized.png` as `.kodiak-header__logo--primary` and `assets/kodiak-parkcity-alt-logo.svg` as `.kodiak-header__logo--secondary` (sticky crossfade). there is no standalone bear-head mark anywhere, and no "bear sightings" motif.

PR-able suggestions:

- add the real full-res bear-head as a committed asset: pull `https://media.ceros.com/kodiak-cakes/images/2024/12/19/ed9cbf26e4db9cc44cfe014316fb0841/bear-head.png` (drop `&width` for full res) into `assets/kodiak-bear-head.png`
- add a subtle "bear sighting" motif — a large, low-opacity bear-head watermark peeking from a corner of the `.ff-prompt` card or the `.wrap`, echoing the playful newsletter voice. suggested CSS on a new `.bear-sighting::after`:
  ```css
  .bear-sighting {
    position: relative;
    overflow: hidden;
  }
  .bear-sighting::after {
    content: "";
    position: absolute;
    right: -24px;
    bottom: -24px;
    width: 140px;
    height: 140px;
    background: url("assets/kodiak-bear-head.png") no-repeat center/contain;
    opacity: 0.06;
    pointer-events: none;
    mix-blend-mode: multiply;
  }
  ```
- keep it decorative-only (`pointer-events:none`, `aria-hidden` on any inline element) so it does not affect the tool's a11y
- confidence: bear-head URL confirmed; placement is a design suggestion

## 2. reconcile the accent color (blaze orange vs live signal red)

what the real brand does: the LIVE kodiakcakes.com LTO page inline CSS uses a signal RED `#b51e14` for primary buttons/CTA, on Bear Brown `#382316` text and parchment `#f8eddf` background (confirmed, scraped `pages/135_pages_lto-oatmeal.html`). Blaze Orange `#E8530E` is a real Kodiak accent (protein/energy, packaging) but is NOT the live web CTA color.

what our front end does today (a genuine inconsistency): the front end MIXES both accents:

- `.ff-inputwrap:focus-within` uses `border-color:var(--orange, #E8530E)` and an orange focus ring (`index.html` `<style>`, ~L165)
- `.ff-go` (the Create button) uses `background:var(--orange, #E8530E)` (~L166)
- `.ff-chip .ff-dot` uses `background:var(--orange, #E8530E)`
- but `.btn.orange` uses `background:var(--red)` and links/`a` use `--red`, and the preview-card summary marker uses `var(--red)`
- so the primary CTA (`.ff-go`) is orange while other CTAs (`.btn.orange`) are red — inconsistent, and the orange one does not match the live site's CTA red

PR-able suggestions:

- pick ONE web CTA accent for parity with the live site: signal red `#b51e14` (already tokenized in `index.html` `:root` as `--red` -> `--colors-brand-signal-red`). retarget `.ff-go` and `.ff-inputwrap:focus-within` to `var(--red)` so the primary Create button matches the rest of the CTAs and the live site
- reserve blaze orange `#E8530E` for its real role — protein/energy accents and the 8px accent bar on rendered creatives (compose.py already does this correctly) — not for web CTA chrome
- if the team prefers to keep orange as the tool's signature, that is a defensible deviation, but it should be CONSISTENT (all CTAs orange, not a mix) and documented as an intentional divergence from live
- confidence: live signal red `#b51e14` confirmed; the mix is confirmed in our CSS

## 3. add a Keep It Wild footer lockup to the PAGE

what the real brand does: "Keep It Wild" is a persistent nav item and appears in the site footer alongside the socials and legal (confirmed, scraped mission/keepitwild pages). it is a brand pillar, not just a campaign.

what our front end does today: "Keep It Wild" only appears as (a) chip briefs and (b) the footer stamped ONTO rendered canvases by compose.py. the HTML PAGE itself has no footer lockup — it ends at the build stamp (`#buildStamp`, ~L590). the page has no brand footer at all.

PR-able suggestions:

- add a real page footer after `#buildStamp`, matching the live site's footer structure (Keep It Wild, socials, legal). minimal on-brand version:
  ```html
  <footer class="kodiak-footer" role="contentinfo">
    <div class="kodiak-footer__lockup">
      <img
        src="assets/kodiak-bear-head.png"
        alt=""
        width="28"
        height="28"
        aria-hidden="true"
      />
      <span class="kodiak-footer__tag"
        >KODIAK &bull; kodiakcakes.com &bull; Keep It Wild</span
      >
    </div>
    <!-- optional: conservation line when a KIW campaign is active -->
  </footer>
  ```
  ```css
  .kodiak-footer {
    margin-top: 32px;
    padding: 18px;
    background: var(--brown-kodiak);
    color: var(--parchment);
    display: flex;
    align-items: center;
    gap: 10px;
    border-top: 4px solid var(--red);
  }
  .kodiak-footer__tag {
    font:
      700 11px/1 "kodiak_sans",
      "museo-sans",
      sans-serif;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #ffdcc3;
  }
  ```
- this mirrors the exact footer string compose.py already stamps on canvases (`KODIAK - kodiakcakes.com - Keep It Wild`), so the page and the output agree
- confidence: KIW-in-footer confirmed on live site; the exact lockup art is a suggestion

## 4. CBO / athlete persona card treatment

what the real brand does: Kodiak fronts campaigns with Zac Efron (Chief Brand Officer) and a real athlete roster, each presented with name + role/discipline + a real photo (confirmed, `kodiak-brand-concept-inventory.md` concepts 3-4).

what our front end does today: the `zac-efron` chip (`index.html` chips block, ~L548) has a generic brief ("Zac Efron athletic-morning energy...") and NO CBO framing, NO photo, NO persona card. same for athletes — there is no athlete chip or card at all. the only partner treatment is the US Ski & Snowboard partner mark (`#ussPartnerMark`, ~L555), which is a good pattern to generalize.

PR-able suggestions:

- generalize the existing `#ussPartnerMark` reveal pattern into a reusable `.persona-card` that appears when a CBO/athlete chip is active. structure:
  ```html
  <div class="persona-card" id="personaCard" hidden>
    <img class="persona-card__photo" src="" alt="" />
    <div class="persona-card__meta">
      <b class="persona-card__name"></b>
      <span class="persona-card__role"></span>
    </div>
  </div>
  ```
- enrich the `zac-efron` chip with CBO framing (aligns with `zac-efron-campaign-fix-spec.md` section 4 copy options). suggested `data-brief`:
  `Zac Efron, Kodiak Chief Brand Officer — his athletic-morning fuel: high-protein pre-trail energy, crafted with Zac. Keep It Wild.`
- add athlete chips (Courtney Dauwalter, Emily Harrington, Alex Howes, etc.) that populate the persona card with the real stills already in our corpus (`Courtney-Dauwalter.jpg`, `Emily_El_Cap_Climb_...jpg`, etc. — see inventory concept 4)
- serve the real photo verbatim (never a generated face) — the persona card displays the licensed still; the composite uses the serve-verbatim path from `zac-efron-campaign-fix-spec.md`
- style the card on-brand: kraft surface, Bear Brown name in gin, discipline in museo-sans caption
- confidence: CBO/athlete facts + real stills confirmed; card is a suggestion

## 5. fix the stale typography token

what is wrong (confirmed): `design/tokens/kodiak.json` typography block declares headline = `Rockwell, Clarendon, American Typewriter, Georgia, serif` and body = `Inter, Helvetica Neue, Arial`. but the live site AND our `index.html` actually render `gin` (headline) + `museo-sans` (body) + `Roar`/`kodiak_sans` (emphasis/UI) from the typekit kit `zjt4wyq.css`. the token font stack is stale relative to what ships.

why it matters: compose.py reads type INTENT from the tokens. if tokens say Rockwell/Inter, server-side composites may fall back to those faces while the front end shows gin/museo-sans — a visible brand-face mismatch between the interactive preview and the rendered asset.

PR-able suggestion (token file, not CSS):

- update `kodiak.json` -> `typography.fontFamily.headline` to lead with `gin`, and `fontFamily.body` to lead with `museo-sans`, matching the live typekit:
  ```json
  "headline": { "$value": ["gin", "Rockwell", "Clarendon", "Georgia", "serif"] },
  "body":     { "$value": ["museo-sans", "Inter", "Helvetica Neue", "Arial", "sans-serif"] }
  ```
- keep the slab-serif + Inter entries as SERVER-SIDE FALLBACKS (compose.py may not have typekit), but the primary must be the real brand faces
- confidence: both the live faces and the stale token are directly confirmed

## 6. strengthen the "bear sightings" playful voice in UI copy

what the real brand does: the voice is bear-forward and playful — every newsletter signup promises "recent bear sightings at Kodiak" (confirmed across scraped pages). culture pillars are bear puns (leave the growl behind, bear together, forge a fresh trail).

what our front end does today: copy is competent but neutral ("Or start from a campaign option", "Type a campaign idea"). the bear voice is not present in the tool chrome.

PR-able suggestions (copy only, low risk):

- `#promptChipsLabel` (~L542): "Or start from a campaign option" -> "Or track a bear sighting" / "Or start from a Kodiak campaign"
- the `bears` chip could carry the growl voice more explicitly in its `data-brief`
- a small playful microcopy line near the footer bear-head motif (suggestion 1): "recent bear sightings" as a section label
- keep it light — this is a B2B tool, so the voice should be a garnish, not a takeover
- confidence: voice confirmed; specific copy is a suggestion

## 7. frontier headline type treatment on the H1

what the real brand does: rugged, epic, uppercase tracked slab/gin headlines (the `.epic-tracking` treatment — `letter-spacing:0.45em` uppercase gin — already exists in our CSS but is unused on the H1).

what our front end does today: `.kodiak-headline-plate h1` (~L462) renders "Nourishing Today's Frontier: Kodiak Cakes Creative Automation Pipeline". it inherits the global h1 gin style (good) but reads as a tool title, not a frontier statement.

PR-able suggestions:

- shorten the H1 to a frontier statement and let the tool subtitle carry the rest: e.g. H1 "NOURISHMENT FOR TODAY'S FRONTIER" (a confirmed real tagline) with a `<small>` subtitle "Kodiak Cakes creative automation pipeline"
- this matches the real mission line ("inspire healthier eating and active living with nourishment for today's frontier") and reads on-brand rather than as a filename
- optionally apply `.epic-tracking` to a short eyebrow above the H1
- confidence: tagline confirmed; H1 rewrite is a suggestion

## 8. Vital Ground co-badge slot for conservation campaigns

what the real brand does: Keep It Wild co-brands with the Vital Ground Foundation (grizzly habitat), and rotating artists like Aaron Draplin (confirmed, inventory concept 2).

what our front end does today: the `keep-it-wild-program` chip (~L551) sets a KIW brief but shows no co-badge. the US Ski & Snowboard chip already demonstrates the partner-mark reveal pattern (`#ussPartnerMark`).

PR-able suggestions:

- when the `keep-it-wild-program` (or `bears`) chip is active, reveal a Vital Ground co-badge using the SAME reveal pattern as `#ussPartnerMark`
- SOURCING GAP (honest flag): the Vital Ground mark is NOT in our corpus and has no captured URL — it must be sourced as a co-brand asset request before this can ship. do not fabricate it
- confidence: KIW/Vital Ground partnership confirmed; the co-badge asset is not yet sourced

## a11y + non-regression notes (so PRs land clean)

- all decorative brand art (bear-head motif, co-badges) must be `aria-hidden` / `alt=""` and `pointer-events:none` so it does not affect the tool's screen-reader flow or click targets
- the accent-color change (suggestion 2) must preserve WCAG AA contrast: signal red `#b51e14` on white passes for large text/UI; verify the Create button label contrast if the background flips from orange to red (`#b51e14` on `#fff` ~4.9:1 — passes AA for the 12px bold uppercase label; confirm with the team's contrast gate)
- the footer (suggestion 3) uses parchment-on-bear-brown which the header already proves passes (~12:1 per the R1 contrast note in index.html)
- typography token change (suggestion 5) is a data-only change; verify compose.py still resolves a valid fallback face when typekit is absent

## summary for orin (PR surfacing)

highest-impact, lowest-effort first:

1. bear-head mark + "bear sightings" motif (visual identity)
2. reconcile accent to live signal red `#b51e14` (consistency + parity)
3. Keep It Wild page footer lockup (brand pillar presence)

then, higher-effort brand depth: 4. CBO/athlete persona card (generalize the existing partner-mark pattern) 5. typography token fix (tokens must match rendered faces)

the front end is already on-brand at the foundation; these close the last-mile gaps. none of them require rearchitecting — most are additive CSS/HTML or a token data fix.
