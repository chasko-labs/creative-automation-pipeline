# Kodiak Style Guide — 7-part (tokens + S3 style library)

> consumable by humans and by `src/creative_automation/*` via `design/tokens/kodiak.json` (W3C DTFM, S3-backed). local mirror `design/tokens/kodiak.json` <-> `s3://$ASSET_STORE_S3_BUCKET/brands/kodiak/tokens/kodiak.tokens.json` with fallback. single-line sync: `./scripts/sync-asset-store.sh pull|push`.

## 1. brand story
Park City UT, Wasatch Mountains — 1982 Joel Clark red wagon heirloom whole wheat, 1995 incorporation by brother Jon, 2014 Shark Tank $3.6m->$6.7m beating Aunt Jemima 20% at Target, 26k doors, 2021 L Catterton majority. purpose: "Nourishment for Today's Frontier" — heirloom recipe, 100% whole grains, 14g protein per serving. promise: rugged nourishment for active families + cubs.

## 2. logo usage — bear + wordmark
- **mark:** grizzly silhouette / KODIAK wordmark in slab, bundled `input_assets/brand/logo.png` -> `s3://.../logos/kodiak-bear.png|.svg`
- **clear space:** 0.25x logo width (35px at 140w default) on all sides; no text, product, or edge intrusion.
- **min size:** digital 32px h / 80px w (default 140w in compose.py @24,24 offset); print 0.5in wide.
- **reversal:** allowed only on Bear Brown #3B2316, Frontier Green #1A3C34, Ink #1A1110, Black. not on blaze orange or busy photography — add scrim.
- **prohibited:** stretch/rotate/skew, color-lock to non-palette, busy background without scrim, shadow/glow, rotating bear, separating bear from wordmark in co-badge with Vital Ground.
- **co-badge:** Vital Ground Foundation tiny grizzly track mark only at footer; see `references/keep-it-wild/photography-direction.json` grizzly-safe note.

Tokens: `kodiak.logo.clearSpace, minSize, reversal, prohibited` in `design/tokens/kodiak.json`.

## 3. palette — multi-format, single source `kodiak.color` + `kodiak.brand`
| name | hex | rgb | cmyk~ | pantone~ | usage |
|------|-----|-----|-------|----------|-------|
| Bear Brown | #3B2316 | 59,35,22 | 0/41/63/77 | 4975 C / 19-0712 TCX Seal Brown | primary, headings, inverse bg |
| Blaze Orange | #E8530E | 232,83,14 | 0/64/94/9 | 1655 C / 16-1364 | accent, CTA, 8px bar, protein callout |
| Frontier Green | #1A3C34 | 26,60,52 | 57/0/13/76 | 5463 C / 19-5420 Deep Teal | secondary, evergreen, borders |
| Parchment | #FFF8F0 | — | — | — | page bg (`semantic.background.default`) |
| Scrim | #1A1110CC (80% ink) / #0000008C legacy | — | — | — | bottom message bar (`semantic.overlay.scrim`) |

Print: verify coated swatch before spot. neutrals #FFFFFF..#1A1110 warm scale derived from Bear Brown + parchment — `kodiak.color.neutral.*`.

## 4. typography
- **headline slab:** Rockwell / Clarendon / American Typewriter -> Georgia fallback; extraBold 800, tracking -0.02em, tight leading 1.05-1.08, centered, 3-line clamp. sizes per ratio via tokens: 56px@1x1, 64px@9x16, 72px@16x9 (compose.py `_load_font` maps to DejaVu Bold until webfont wired).
- **body:** Inter / Helvetica Neue, 400, 1.5lh, 28/30/32px per ratio.
- **caption/footer:** Inter 500, uppercase 0.06em tracking, 22/24px — maps to `KODIAK • kodiakcakes.com • Keep It Wild` footer at bottom.
Mono JetBrains for SKU/14g badges.

Tokens: `kodiak.typography.*` + `kodiak.spacing.canvasPad 48, logoOffset 24, accentBar 8, messageBarTop 68%`.

## 5. photography direction — `references/keep-it-wild/photography-direction.json`
- **Wasatch dawn:** alpenglow pine/boulder wide, sky negative space at top for text — blurred cover bg in compose C01.
- **Rugged pioneers:** modern family (25-45 + cubs, diverse, flannel/beanies/canvas tote, red wagon callback) flipping flapjacks on cast iron, not costume.
- **Grizzly Keep It Wild:** safe-distance meadow/river or tracks/silhouette only — no captive close-up (PETA 2022 precedent). Vital Ground habitat corridor.
- **High-protein active families:** post-hike steam stack 14g, Bear Bites for cubs, oatmeal trail cup, enamel mug on wood.
- **Product hero:** centered pack on clean light bg, soft shadow, 1024x1024, no text/logo (overlaid in rendering) — Nova Canvas prompts `kodiak-01..08` in `nova-canvas-prompts.json`.

## 6. packaging / illustration
Whole grain craft cues: kraft parchment + wood + enamel, minimal flat bear line-art. no generic bento/hand-drawn mascot slop; keep frontier illustration purposeful (red wagon, grizzly track). ratio-aware: 9x16 safe inset 5% extra for stories; 16x9 wide hero box 1574x626.

## 7. voice & templates — `voice-tone.json` + `references/templates/social-3ratio.json`
- **voice:** adventurous (verbs-forward "Fuel your frontier"), nourishing (whole-grain honesty, 14g purpose), rugged (Wasatch short sentences). guardrail: approved claim "Protein-packed whole grains for today's frontier." — avoid % protein claims without substantiation (17% class action).
- **localization:** US-MW Wasatch snow/trail haze vs US-SE Publix porch family humidity-green — same system, different hero prompt (kodiak-02 vs kodiak-07).
- **templates (C01-C06):** blurred cover bg + 0.18 scrim, hero contain min(W*0.82/hw,H*0.58/hh)@ (W-fw)/2,8%, safe 48/24/8, message bar 32%@68%, logo 140w@24,24, type hierarchy. seed in S3 `brands/kodiak/references/templates/social-3ratio.json`, consumed by compose.py via tokens.

## S3 style library — how to use

```
design/tokens/kodiak.json                <-> s3://$ASSET_STORE_S3_BUCKET/brands/kodiak/tokens/kodiak.tokens.json
input_assets/brand/logo.png              <-> s3://.../logos/kodiak-bear.png
input_assets/<product>/hero.png          <-> s3://.../heroes/{product}/hero.png
references/keep-it-wild/*.json            <-> s3://.../references/keep-it-wild/
references/templates/social-3ratio.json  <-> s3://.../references/templates/
output_kodiak/*                           -> s3://.../renders/{product}/{ratio}/
```

```bash
./scripts/sync-asset-store.sh pull        # s3 -> local (tokens/heroes/logos/references) before run
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak
./scripts/sync-asset-store.sh push        # publish style library
./scripts/sync-asset-store.sh push-renders output_kodiak
# seed once:
./scripts/seed-kodiak-s3.sh       # needs ASSET_STORE_S3_BUCKET set
```

Pipeline reads tokens via `src/creative_automation/token_loader.py` — S3 first if `ASSET_STORE_S3_BUCKET` + creds, else local `design/tokens/kodiak.json` else `src/.../tokens/kodiak.tokens.json`. no hard-coded colors/fonts/dims in compose/compliance/generate — all via tokens.

## verification

```bash
uv run pytest -q
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/kodiak-verify
# expect 9 creatives, palette #3B2316/#E8530E/#1A3C34, logo @24,24, message bar scrim #1A1110CC
```
