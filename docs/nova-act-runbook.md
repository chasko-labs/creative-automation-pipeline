# Nova Act / AgentCore Browser Visual QA — Kodiak Retailer Previews

> Gates brand compliance before S3 publish / retailer handoff. Opens each `preview.html` at 3 viewports, verifies logo, palette, accent bar, and headline legibility, then emits `nova-act-report.json`.

## What exists today (research)

| Retailer dir | `preview.html` | Creatives | Pass | Notes |
|---|---|---|---|---|
| `output_kodiak/` | ✅ `output_kodiak/preview.html` | 9 (power-cakes dam + bear-bites/oatmeal-cup mock) | 9/9 | US-MW baseline — Keep It Wild · Frontier Breakfast |
| `output_kodiak-target/` | ✅ `output_kodiak-target/preview.html` | 9 | 9/9 | Target Midwest Gen Z — same template, localized audience |
| `output_kodiak-costco/` | ✅ `output_kodiak-costco/preview.html` | 9 | 9/9 | Costco bulk variant |
| `output_kodiak-publix/` | ✅ `output_kodiak-publix/preview.html` | 9 | 9/9 | Publix SE |
| `output_kodiak_se/` | ✅ `output_kodiak_se/preview.html` | 9 | 9/9 | `briefs/kodiak-se.yaml` — southern porch localization |

All previews share the same 6-piece template (`references/templates/social-3ratio.json` via `design/tokens/kodiak.json`): blurred Wasatch cover + hero `contain @ (W-fw)/2, 8%` + scrim bar `@ 68% H` + logo `140w @ 24,24` + footer + 8px Blaze Orange bar. 1:1 = 1080×1080, 9:16 = 1080×1920 (Stories), 16:9 = 1920×1080 (landscape feed).

Brand source of truth: `design/tokens/kodiak.json` + `docs/kodiak-style-guide.md` §2–4.

## Design — Nova Act / AgentCore Browser flow

```
                     ┌─────────────────────────────────────────────┐
                     │  Pipeline out: output_kodiak*/preview.html   │
                     │  + 9 PNGs/product + report.json             │
                     └──────────────┬──────────────────────────────┘
                                    │
                     ┌──────────────▼──────────────────────────────┐
                     │  scripts/nova-act-check.py                   │
                     │  --all  (discovers output_kodiak*/preview.html)│
                     │  --preview <single> --viewport 1080x1080 ...  │
                     └──────────────┬──────────────────────────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
   ┌──────────▼─────┐  ┌───────────▼──────┐  ┌───────────▼──────┐
   │  Nova Act      │  │  Playwright      │  │  Mock (PIL+HTML) │
   │  + AgentCore   │  │  local chromium  │  │  always available│
   │  Browser       │  │  (no AWS creds)  │  │  (CI fallback)   │
   └──────────┬─────┘  └───────────┬──────┘  └───────────┬──────┘
              │                     │                     │
              └─────────────────────┼─────────────────────┘
                                    ▼
                     ┌───────────────────────────────────┐
                     │  For each preview × 3 viewports:   │
                     │  1080×1080  1080×1920  1920×1080    │
                     │  1. Open preview.html              │
                     │  2. Assert .card count == 9       │
                     │  3. Screenshot (Nova/Playwright)   │
                     │  4. Probe each creative PNG:       │
                     │     - logo @24,24 variance>28     │
                     │       clearSpace 0.25x=35px ring   │
                     │       min 80w / default 140w       │
                     │     - accent bar 8px #E8530E bottom│
                     │     - palette #3B2316/#1A3C34 probe│
                     │     - scrim #1A1110CC @68% dark    │
                     │     - headline white-on-scrim      │
                     │       contrast delta>80 max>150    │
                     │  5. Emit viewport + creative results│
                     └──────────────┬───────────────────┘
                                    ▼
                     ┌───────────────────────────────────┐
                     │  nova-act-report.json per retailer │
                     │  + aggregated nova-act-report.json │
                     │  summary.overall_passed gates push │
                     └──────────────┬───────────────────┘
                                    ▼
                     ┌───────────────────────────────────┐
                     │  Gate: exit 0 pass / exit 2 fail   │
                     │  Block: ./scripts/sync-dam.sh push │
                     │  and retailer handoff on fail      │
                     └───────────────────────────────────┘
```

### Viewports — why these 3

| Label | W×H | Maps to | Use |
|---|---|---|---|
| `1080x1080` | 1080×1080 | 1:1 square | Instagram feed, Kodiak product grid |
| `1080x1920` | 1080×1920 | 9:16 story | Reels/Stories — taller bar, 64px headline |
| `1920x1080` | 1920×1080 | 16:9 wide | Landscape feed / video thumb — 72px headline |

Responsive `preview.html` uses `grid-template-columns: repeat(auto-fill, minmax(320px,1fr))` so the 3 viewports visibly reflow; Nova Act re-opens at each size to catch truncation or logo overlap that pixel-only checks would miss.

### Checks in detail

| # | Check | Expected | How verified |
|---|---|---|---|
| 1 | **Logo presence** | `input_assets/brand/logo.png` composited at `24,24`, `140w` (min `80w`) | Crop top-left `24,24 → 164, ~87`; variance `>28` ⇒ logo present, not flat bg |
| 2 | **Logo clearSpace** | `0.25×` logo width = `35px` on all sides (style guide §2) | Ring `35px` around logo bbox not clipped at canvas edge |
| 3 | **Accent bar** | `8px` Blaze Orange `#E8530E` full-width at `H-8 … H` | Bottom 12px strip: `>45%` pixels within `Δ90` of `#E8530E` |
| 4 | **Palette Bear Brown** | `#3B2316` present somewhere in creative | Downsample `64×64`, sample every 8th pixel within `Δ180` |
| 5 | **Palette Frontier Green** | `#1A3C34` present | Same probe |
| 6 | **Scrim** | `#1A1110CC` (≈80% ink) fills `0, 68%H → W, H` | Center scrim sample avg brightness `<95` |
| 7 | **Headline legibility** | White headline `56/64/72px`, `stroke 2`, center, `≤3` lines, on scrim | Text-area brightness range `delta>80` and `max>150` |
| 8 | **Preview structure** | 9 cards, 9/9 `PASS` badges, 9 PNGs exist | HTML parse: `.card` count, `.badge pass/fail`, `img src` existence |
| 9 | **Dims** | PNG matches ratio: `1080×1080 / 1080×1920 / 1920×1080` | PIL `Image.size` vs `RATIO_DIMS` |

`overall_passed` for a retailer = every viewport's structure passes **and** every creative passes every pixel check. A single failing creative fails the retailer, which blocks promotion.

### Execution modes (auto-detected)

1. **Nova Act + AgentCore Browser** — `pip install nova-act` + `AWS_PROFILE` set. Session per [AgentCore Browser docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html) and [Nova Act announcement](https://aws.amazon.com/blogs/aws/introducing-amazon-nova-act/): `async with NovaAct(starting_page=preview_uri) as nova: await nova.page.set_viewport_size(...) ; await nova.act("Verify logo at 24,24 ...")`. Also captures `nova.page.screenshot(full_page=True)`.

2. **Playwright** — `pip install playwright && playwright install chromium`. Same 3 viewports via `browser.new_context(viewport={w,h})` + `page.goto(preview_uri)` + DOM asserts + screenshot to `/tmp/playwright-<retailer>-<WxH>.png`.

3. **Mock (PIL + HTML)** — no deps beyond `pillow` (already in `pyproject.toml`). Parses `preview.html` with regex, opens PNGs, probes pixels. This is the **default in CI / for reviewers with no AWS creds**, per `docs/agentcore.md` ("poc runs locally with mock fallback"). Brand gate is still enforced — mock failures exit `2`.

Mode is chosen by `detect_mode()`; override with `--mode mock|playwright|nova-act`.

## Script

**Path:** `scripts/nova-act-check.py` (executable, `chmod +x`).

Dependencies: Python ≥3.11 + `pillow` (existing). Optional: `playwright`, `nova_act`.

## How it gates brand compliance

```
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak
uv run python scripts/nova-act-check.py --all          # or --preview output_kodiak/preview.html
# exit 0 → ok to promote; exit 2 → block
./scripts/sync-dam.sh push-renders output_kodiak       # only on pass
```

CI example (`.github/workflows/creative.yml`):

```yaml
- run: uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak
- run: uv run python scripts/nova-act-check.py --all --out nova-act-report.json
- run: ./scripts/sync-dam.sh push-renders output_kodiak
  if: success()
```

The report JSON includes `summary.overall_passed`, `summary.gates_brand_compliance`, and `next_step_if_fail` so downstream tooling can gate without parsing exit codes.

## How it would run with `AWS_PROFILE=bryanchasko-kiro`

Live path uses the `bryanchasko-kiro` SSO profile (which has Bedrock + AgentCore + DAM S3 access). The mock fallback still passes locally, but with creds the script attempts Nova Act first and records screenshots.

```bash
# 1. Ensure profile + region (us-east-1 holds Nova Canvas + AgentCore Browser)
export AWS_PROFILE=bryanchasko-kiro
export BEDROCK_REGION=us-east-1
export DAM_S3_BUCKET=chasko-creative-dam-946179428633-us-east-1
export DAM_S3_PREFIX=brands/kodiak/

# 2. Verify Bedrock access (Nova Canvas + Nova Micro must be enabled)
aws bedrock list-foundation-models --region us-east-1 | grep -E "nova-canvas|nova-micro"
aws sts get-caller-identity --profile bryanchasko-kiro   # sanity

# 3. Pull style library (optional — check is local, but parity matters)
./scripts/sync-dam.sh pull

# 4. (Re)render previews if needed — or use existing output_kodiak*/
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out output_kodiak
uv run python -m creative_automation.cli --brief briefs/kodiak-se.yaml --assets input_assets --out output_kodiak_se
# Retailer sprints already in output_kodiak-{target,costco,publix}/ — re-render via their briefs if needed

# 5. Install browser automation deps (one-time)
pip install nova-act playwright
playwright install chromium --with-deps
# nova-act ships its own AgentCore Browser tool; no extra infra needed

# 6. Run visual QA across all retailers at 3 viewports
uv run python scripts/nova-act-check.py --all
# Per-retailer reports:
#   output_kodiak/nova-act-report.json
#   output_kodiak-target/nova-act-report.json
#   output_kodiak-costco/nova-act-report.json
#   output_kodiak-publix/nova-act-report.json
#   output_kodiak_se/nova-act-report.json
# Aggregated:
#   ./nova-act-report.json  (or --out /tmp/nova-act-report.json)

# 7. Single-retailer or single-viewport drill-down
uv run python scripts/nova-act-check.py --preview output_kodiak-target/preview.html --viewport 1080x1920
uv run python scripts/nova-act-check.py --preview output_kodiak/preview.html --mode nova-act --json | jq .summary

# 8. Gate: only publish if exit 0
uv run python scripts/nova-act-check.py --all && ./scripts/sync-dam.sh push-renders output_kodiak
# With aggregated JSON gate:
# uv run python scripts/nova-act-check.py --all --json | jq -e '.summary.overall_passed' && echo "gate PASS"

# 9. Inspect outputs
cat output_kodiak/nova-act-report.json | jq .summary
cat nova-act-report.json | jq '.previews[] | {retailer, overall_passed: .summary.overall_passed}'
open output_kodiak/preview.html          # human spot-check
ls -lh /tmp/nova-act-*.png /tmp/playwright-*.png  # browser screenshots (Nova/Playwright modes)
```

**Without creds / in CI** the same command works — `detect_mode()` falls back to `mock`:

```bash
uv run python scripts/nova-act-check.py --all
# [nova-act-check] no AWS_PROFILE — using mock/playwright fallback (reviewer-friendly)
# [nova-act-check] output_kodiak PASS — 9/9 creatives, 3/3 viewports (mock)
```

**Exit codes:** `0` all retailers pass, `2` any retailer fails brand compliance (block publish), `1` I/O error (missing preview, bad viewport).

## Report schema (abridged)

```json
{
  "preview": "output_kodiak/preview.html",
  "retailer": "output_kodiak",
  "generated_at": "2026-09-02T...",
  "viewports": [
    {
      "viewport": "1080x1080",
      "width": 1080, "height": 1080,
      "mode": "mock",
      "passed": true,
      "checks": [{"check": "preview.cardCount", "passed": true, "detail": "..."}],
      "creatives": [{"product": "power-cakes", "ratio": "1x1", "passed": true, "checks": [...]}]
    }
  ],
  "summary": {
    "overall_passed": true,
    "creatives_passed": 9, "creatives_total": 9,
    "viewports_passed": 3, "viewports_total": 3,
    "palette": {"bearBrown": "#3B2316", "blazeOrange": "#E8530E", "frontierGreen": "#1A3C34"},
    "logo": {"offset": 24, "defaultW": 140, "clearSpacePx": 35},
    "gates_brand_compliance": true
  }
}
```

## References

- `design/tokens/kodiak.json` — W3C DTFM single source for palette/spacing/typography
- `docs/kodiak-style-guide.md` §2 (logo clearSpace 0.25×), §3–4 (palette/typography)
- `docs/agentcore.md` — promotion path poc→AgentCore Runtime, Nova Act browser QA step
- `src/creative_automation/compose.py` — deterministic compose (logo `@24,24`, accent `8px`, scrim `#1A1110CC`, `barTop 68%`)
- `src/creative_automation/compliance.py` — lightweight palette/logo/legal probes (extended by Nova Act visual QA)
- Bedrock AgentCore Browser: https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/browser-tool.html
- Nova Act: https://aws.amazon.com/blogs/aws/introducing-amazon-nova-act/ · https://github.com/aws/nova-act
