# Persona flows — how each group uses the Frontier tool, and the bar

Source cards: `docs/ux-personas-kodiak-complete.md` (23 cards, 5 groups).
Each flow follows the app's real path: Setup (1–5) → Create Campaign
Preview (6) → Generate Campaign (7) → Assets (8). The bar is what "done"
means for them. Where the app fails the bar today, it says so.

## 1. Brand Management (Aaron, Madison/Rebecka, Eli, Sarah, Emily, Elizabeth, Nina)

Flow: open the tool → pick market + season (their market plan) → check the
brand-safe angles only → Create Campaign Preview → read every tile + the
How-it-was-made panel → approve or kill.
Bar: KODIAK® spelled right everywhere, no paraphrased slogans, no off-brand
imagery, provenance visible so they can audit what made each pixel.
Fails today: fallback copy paraphrases and drops marks; one tile is real and
four are stretched, so there is nothing honest to approve.

## 2. Creative, Design, Ops (Brett, Arnoldo, Sam, Amber)

Flow: stage assets (riff on past content) → set creative direction →
preview → inspect seed, scene prompt, engine, rung per tile → download the
asset pack → hand off.
Bar: the staged asset drives the pixels; every tile reports its seed and
engine truthfully; downloads match the preview exactly.
Fails today: staged picks were ignored by the backend (fixed, needs dev
receipt); panel showed no engine/origin (fixed, needs dev receipt).

## 3. Growth and Digital Commerce (Cory, Casi, John, Landon, Micah)

Flow: choose scope (single market → nationwide → full campaign) → preview →
verify per-platform copy, publish pills, retailer + subscription variants →
generate full campaign → publish targets light up.
Bar: copy identical across cart, ad, and inbox; tall story ad carries the
same promo line as the cart banner; screenshots verify at all three ratios
before handoff.
Fails today: platform copy is template fallback with no brand voice; tall
tiles are stretched squares, so the handoff gate cannot pass.

## 4. Community and Brand Partnerships (Boman, Mackenzie, Julie, Ella, Kelly)

Flow: pick frontier/market → preview voice and imagery → check Keep It Wild
marks, athlete/pack shared frame, repost crop behavior → download → post.
Bar: voice reads adventurous/nourishing/rugged, never tech slop; bear and
marks follow reversal rules; repost crops stay recognizable.
Fails today: voice agent dark, fallback copy is generic; imagery can drift
from seed with no gate (gate now merged, needs dev receipt).

## 5. Shopper Marketing and Sales Hubs (Ali, Ashley, Quin)

Flow: pick market + retailer (Costco, Kroger, H-E-B, Target…) → preview with
the retailer mark → verify co-brand lockup + locality → download the
retailers pack → field/shelf.
Bar: the partner mark sits on the image correctly; file names carry
market-chain-ratio; works offline on a field phone.
Fails today: four marks ingested, three missing; overlay wiring merged but
not dev-verified; offline path untested this sprint.

## 6. Technical Integration (John, Landon/Micah, Arnoldo, agency partners, Adam, Ryan, Drew)

Flow: drive the tool or the API (`POST /pipeline/run`, MCP tools) → read
Swagger/report/preview as the contract → integrate downstream.
Adam deploys it into a new market with a brief YAML and a place row, no code;
Ryan verifies the output against the persona bars and files misses with market
tags; Drew approves the contract shape before it lands.
Bar: if a line isn't callable it isn't shippable; same JSON in CLI, API,
and MCP; no mock reported as success.
Fails today: 16 skips on system python (fixed: project venv runs 787/0/0);
mock-as-success fallbacks still present in retrieve paths.

## The fix this goal demands

Item 4 of the parity spec, closed for real: every preview tile composed,
none stretched. Design: preview returns the 1:1 immediately; the page then
polls one lightweight extend call per tall/wide tile (each fits the wall)
and swaps tiles as composed pixels land. Pads remain only as the loading
state, never the delivered state.
