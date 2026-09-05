# zac-efron-persona-card — the CBO business card + reusable persona-card content spec

content/copy + UX-spec doc for the frontend team. this defines WHAT populates the persona card and the field schema athletes reuse — it does not implement the component. the frontend/CSS owners build the `.persona-card` markup + styles described in `kodiak-site-rizz-up-notes.md` section 4; this doc feeds them the content, the schema, and the CBO business-card treatment.

companions in this dir:

- `kodiak-site-rizz-up-notes.md` section 4 — the reusable `.persona-card` component suggestion (photo + name + role + narrative), generalizing the existing `#ussPartnerMark` reveal pattern
- `zac-efron-campaign-fix-spec.md` — established the serve-the-real-licensed-still contract (never synthesize his face) + the `persona_card` field slot in the asset manifest + the LTO data-preselect wiring
- `kodiak-brand-concept-inventory.md` concepts 3-4 — Zac CBO + athlete roster brand facts

## guardrail (inherited, non-negotiable)

the persona card displays a REAL licensed still, served verbatim. never a synthesized face, never a generated likeness, never img2img of a face. this is the same structural guardrail as the campaign fix spec: Zac is Chief Brand Officer — his real image is a brand asset to serve, exactly like a product box. the card's `photo_key` resolves to a licensed DAM asset and is pasted as-is.

real assets staged in the DAM at `brands/kodiak/zac-efron/`:

- `zac-cooking-2023.jpg` — primary card photo
- `zac-waffle-nachos-2024.jpg` — secondary / alternate

## 1. the Zac CBO card content

the content that populates the card when the zac-efron chip is active:

| field      | value                                                                                                                                                                                                                                                                           |
| ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| name       | Zac Efron                                                                                                                                                                                                                                                                       |
| role/title | Chief Brand Officer                                                                                                                                                                                                                                                             |
| photo      | `brands/kodiak/zac-efron/zac-cooking-2023.jpg` (real licensed still, served verbatim, never synthesized)                                                                                                                                                                        |
| narrative  | Kodiak Chief Brand Officer, board member + shareholder since 2022. food with a purpose — backs Keep It Wild and Vital Ground grizzly-habitat conservation. crafted the Apple Brown Sugar Pecan Fruit & Nuts oatmeal (chia, pumpkin + cranberry seeds), a Walmart-exclusive LTO. |
| signature  | signature graphic slot — placeholder, pending the ceros browser-grab. leave `signature_asset` null until the real signature still lands at `brands/kodiak/zac-efron/`.                                                                                                          |

### campaign brief / chip copy (corrected)

pulled verbatim from `zac-efron-campaign-fix-spec.md` section 4, option A (the recommended framing — reads as HIS fuel, carries the CBO role and the crafted-with-Zac LTO context):

```
Zac Efron, Kodiak Chief Brand Officer — his athletic-morning fuel: high-protein pre-trail energy, aspirational active lifestyle, crafted with Zac. Keep It Wild.
```

this replaces the stale `data-brief` on the chip at `index.html:480` ("Zac Efron athletic-morning energy...") which read as if the campaign IS his energy rather than his fuel.

### narrative one-liner (tight card variant)

when the card only has room for a single line under name + role, use the compressed form:

```
Kodiak CBO + board member since 2022 — food with a purpose, Keep It Wild conservation, crafted the Apple Brown Sugar Pecan LTO oatmeal.
```

## 2. the reusable persona-card field schema

so every athlete reuses the same shape. this is the content contract the frontend maps onto the `.persona-card` component from the rizz-up notes. it also matches the `persona_card` field slot already reserved in the zac-efron asset manifest.

| field                | required | type          | meaning                                                                                                                          |
| -------------------- | -------- | ------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| `name`               | yes      | string        | display name, rendered Bear Brown in gin                                                                                         |
| `role_or_discipline` | yes      | string        | "Chief Brand Officer" for Zac; the sport/discipline for athletes (ultrarunning, climbing, cycling) — rendered museo-sans caption |
| `photo_key`          | yes      | string        | DAM key of the REAL licensed still, served verbatim as the card photo + composite foreground                                     |
| `narrative`          | yes      | string        | one line, true, on-brand — their real story with Kodiak                                                                          |
| `signature_asset`    | optional | string / null | signature graphic DAM key; null until sourced. CBO-tier flourish, not expected on athlete cards                                  |
| `default_product`    | optional | string        | product NAME to preselect when this card is active (Zac -> the LTO oatmeal); soft default, user overrides freely                 |

### how it maps to the frontend component

the `.persona-card` markup from `kodiak-site-rizz-up-notes.md` section 4:

```html
<div class="persona-card" id="personaCard" hidden>
  <img class="persona-card__photo" src="" alt="" />
  <div class="persona-card__meta">
    <b class="persona-card__name"></b>
    <span class="persona-card__role"></span>
  </div>
</div>
```

field-to-slot mapping:

- `name` -> `.persona-card__name`
- `role_or_discipline` -> `.persona-card__role`
- `photo_key` -> `.persona-card__photo` `src` (resolved to the served licensed still; `alt` set to name + role)
- `narrative` -> subtitle line (extend the meta block with a `.persona-card__narrative` span, or feed the active `data-brief`)
- `signature_asset` -> optional signature overlay slot (CBO business-card variant only, section 3)
- `default_product` -> drives the chip `data-preselect` (section 4)

reveal behavior reuses the existing `#ussPartnerMark` show/hide pattern: the card is `hidden` until a persona chip is active, then populated + revealed.

### how it feeds the composite

the card photo and the rendered-creative foreground are the same served asset. the composite pastes `photo_key` verbatim as the foreground layer over a brand background via `compose.py :: compose_creative(..., product_layer=<still>)` — drop shadow, no cover-fit, no scrim, no enhance, no generative model on the face. the card is the UI-visible expression of the same serve-verbatim path the campaign fix spec defined.

### athlete roster (same card shape, real stills)

each athlete gets a card of this exact schema, populated with their real licensed still — never a generated face:

| name                | role_or_discipline |
| ------------------- | ------------------ |
| Courtney Dauwalter  | ultrarunning       |
| Emily Harrington    | climbing           |
| Alex Howes          | cycling            |
| Caleb Olson         | ultrarunning       |
| Christopher Blevins | cycling            |
| Natalia Grossman    | climbing           |

athlete cards use the lighter treatment (kraft surface, name in gin, discipline in museo-sans caption). the CBO business-card treatment (section 3) is reserved for Zac / CBO-tier personas.

## 3. the CBO business-card treatment

Zac is Chief Brand Officer, so his persona card gets a literal business-card-styled variant — an on-brand flourish that distinguishes CBO-tier from the lighter athlete card. this is the visual treatment spec for the frontend; content stays the section 1 card content.

business-card variant elements:

- name — Zac Efron, Bear Brown (`#382316`) in gin, the primary line
- title — "Chief Brand Officer", museo-sans caption beneath the name
- mark — the Kodiak growling bear-head mark (the `assets/kodiak-bear-head.png` from rizz-up notes suggestion 1) as the card's corner/left lockup, the way a logo sits on a business card
- palette — the frontier palette: kraft/parchment (`#f8eddf`) card surface, Bear Brown text, signal-red (`#b51e14`) rule or accent edge (matches the live-site CTA reconciliation in rizz-up notes suggestion 2)
- signature — Zac's signature graphic in the signature slot (`signature_asset`), placed as a business card carries a signature; placeholder until the ceros grab lands the real asset
- photo — the served licensed still (`zac-cooking-2023.jpg`) as the card portrait, served verbatim

treatment framing: the business-card layout applies to CBO-level personas as a heavier, more formal card. athlete personas keep the lighter card. both draw from the same field schema (section 2) — the difference is purely the visual treatment class the frontend applies (e.g. `.persona-card--business` vs the default `.persona-card`).

all decorative brand art (bear-head mark) stays `aria-hidden` / `alt=""` and `pointer-events:none` per the rizz-up notes a11y rule so the flourish does not affect the tool's screen-reader flow or click targets.

## 4. LTO default-product note

when Zac's card is active, the default featured product is the LTO oatmeal he crafted — the Apple Brown Sugar Pecan Fruit & Nuts oatmeal — until the user changes it.

this reuses the `data-preselect` wiring from `zac-efron-campaign-fix-spec.md` section 3:

- `default_product` in the card schema drives the chip's `data-preselect` attribute
- the chip click handler checks the matching product row in `#productChooser` after setting the theme
- the preselect is soft — a manual product change or brief edit clears it via the existing `__clearActiveTheme` / productChooser change handlers; the user overrides freely
- SKU flag (carried from the fix spec): the exact "Apple Brown Sugar Pecan Fruit & Nuts" LTO SKU is not yet in `kodiak-full-catalog.json`. interim preselect is `Maple Pecan Overnight Oats` (pecan-adjacent, real SKU); the correct long-term wiring adds the real LTO entry then flips `default_product` to that name.

## summary

- Zac CBO card: name Zac Efron, role Chief Brand Officer, real licensed photo served verbatim, true one-line narrative (CBO + board member since 2022, food with a purpose, Keep It Wild / Vital Ground conservation, crafted the Apple Brown Sugar Pecan LTO oatmeal), corrected chip copy (fix-spec option A), signature slot placeholder pending the ceros grab
- reusable schema: `name`, `role_or_discipline`, `photo_key`, `narrative`, optional `signature_asset`, optional `default_product` — maps onto the `.persona-card` component, feeds the composite as the verbatim foreground layer, athlete roster reuses the same shape with their real stills
- business-card treatment: heavier CBO-tier card variant — name + Chief Brand Officer + bear-head mark + frontier palette + signature, on-brand flourish distinguishing CBO from the lighter athlete card
- LTO default: Zac's card preselects the crafted-with-Zac LTO oatmeal via the fix-spec `data-preselect` wiring, soft default, user overrides
- guardrail confirmed: real licensed stills served verbatim, never synthesized
