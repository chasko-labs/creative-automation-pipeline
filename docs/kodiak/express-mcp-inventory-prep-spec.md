# adobe express mcp + kodiak frontend inventory — prep spec

> prep artifact authored 2026-09-05 ahead of a fresh session. everything here is staged so the
> next session comes up with express mcp available and the team executes the inventory plan
> without rediscovering any of this. no src/ or tests/ code was written — this is spec + wiring only.

## findings first

- **express developer mcp is real, wired, and verified.** `npx -y @adobe/express-developer-mcp@latest --yes`
  launches clean: `Adobe Express Developer MCP Server 1.0.0 started, using STDIO transport`, pulls
  `@adobe/ccweb-add-on-sdk-types 1.40.0`. stdio, no auth, no secrets, no container.
- **the itemization bryan asked for already exists** — `docs/design-system-inventory.md` (239 lines).
  it labels every frontend element with an adobe-express-friendly name, selector, surface, and state,
  built explicitly for the express prototyping loop. it is missing two axes (below).
- **RTCDP mcp is evaluated and excluded.** the adobe real-time cdp mcp (`rtcdp-mcp.adobe.io/mcp`) is a
  customer-data-platform monitoring surface — 18 read-only tools for audiences, destinations, activation
  flows, identity namespaces. it requires a real-time cdp license, org allowlisting by an adobe rep
  (invitation-only beta), `imsOrgId` + `sandboxName` per session, and uses type:http remote transport with
  browser oauth. none of it touches frontend layout, design tokens, or creative generation. it does not
  belong in the inventory plan. recorded here so the team does not chase it.
- **the lab the wiring came from:** `chasko-labs/adobe-express-mcp-lab` — cloned fresh to
  `~/code/heraldstack/adobe-express-mcp-lab` (the prior local dir was empty). the lab already shipped one
  real use case: the cloud del norte aws builder center banner, generated from design-system tokens via
  this mcp. that is the "making outlines/banners from tokens" workflow bryan remembered.

## what express mcp actually does (and does not do)

it is a **documentation librarian**, not a canvas renderer. it gives the llm:

- semantic search over `developer.adobe.com/express/add-ons` docs
- typescript definitions from `@adobe/ccweb-add-on-sdk-types` (`editor.createRectangle`,
  `editor.makeColorFill`, `insertionParent.children.append`, manifestVersion 2 schema)

so the llm produces token-accurate svg / real add-on code instead of inventing `adobe.addOn.*` apis.

what it does **not** do: it does not render or screenshot the live kodiak screen. seeing the actual
rendered 4-view layout still needs headless screenshots (ghost-liora-headless-verifier) at the four
breakpoints. express mcp grounds what we _generate_; screenshots capture what _exists_.

## the inventory loop — how express mcp gets us to the itemized frontend

the loop, with `design-system-inventory.md` as the hinge:

- **label** — every element has an express-friendly name pinned to a token (already done in the inventory)
- **prototype** — prototype the element in adobe express, mcp-grounded + fed the kodiak tokens, so the
  output is real sdk code / token-accurate svg
- **pin** — pin the express output back to the token layer (`design/tokens/kodiak.json` -> panda -> styles.css)
- **update** — update the element's inventory row in the same change

express mcp is not a detour from the itemization — it is the tool that operationalizes it. the inventory
is the map; express mcp is how we draw new territory on that map without going off-token.

## what is wired (staged, needs deploy + restart to activate)

| artifact        | path                                                        | purpose                                                                                        |
| --------------- | ----------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| bridge launcher | `heraldstack-mcp/launchers/bridges/adobe-express-bridge.sh` | `exec npx -y @adobe/express-developer-mcp@latest --yes`, resolves by bare name via run.sh      |
| mcp fragment    | `haunting-kiro-cli/mcp/mcp-adobe-express.json`              | `_family mcp-adobe-express`, `_loaded_by_default false`, bare-name stdio entry                 |
| template family | `haunting-kiro-cli/mcp.json.template`                       | `mcp-adobe-express` added to `_optional_families`                                              |
| registry entry  | `heraldstack-mcp/registry.yaml`                             | `adobe-express-developer`, runtime npx, status active, session_wired haunting, transport stdio |
| project overlay | `creative-automation-pipeline/.kiro/mcp.overlay.json`       | opts this project into `mcp-adobe-express`                                                     |

it is an **opt-in family**, not default-loaded — only projects doing creative/design work pull it, via the
per-project overlay. respects tier discipline, does not bloat every session.

**activation:** run `deploy.sh` on rocm-aibox (renders `mcp.json` via kiro-render-mcp from template +
fragments + overlay), then restart the session. the fresh session's `adobe-express-developer` server comes
up under the project overlay.

## what the inventory still needs (the addendum the team executes next session)

`design-system-inventory.md` covers element form / function / state / token. it is missing two axes bryan
named this session:

1. **the 4-view responsive dimension** — each element's form + function at mobile / tablet / desktop /
   ultrawide. the doc is viewport-agnostic today.
2. **the market vs featured-frontier taxonomy** — the location control reclassified under the new vocabulary:
   - **market** = has retail footprint (costco / target / publix / heb) — where you can buy kodiak cakes.
     maps to schema `classification` metro + regional + frontier (any region whose `retailers[]` has a
     home/primary chain-grocer).
   - **featured frontier** = no retail footprint, recipe-source (farmers markets, seasonal ingredients).
     maps to schema `classification` frontier-gap (DTC/subscription only).
   - derive a `location_class` (market | featured-frontier) from `retailers[]` presence rather than
     migrating the four-value `classification` — keeps the rich schema, gives the clean two-bucket product
     language. the dropdown groups by class first, then alphabetizes by state within each.
3. **translation as a first-class element** — the site advertises localization everywhere (manifest
   `languages`, control row `localized in: English, Spanish, Portuguese`, chips, create button) but renders
   NO actual localized copy. `renderLangChips()` is a deliberate no-op stub. translation is not partially
   missing — it is entirely missing as rendered output. it is the highest-value functional gap.

## next-session execution plan (3 waves)

- **wave 0 — activate + verify.** deploy.sh + restart. confirm `adobe-express-developer` shows connected.
  run one dispatch-health probe. confirm the stale-transport pile-up cleared (nova/aws/github back).
- **wave 1 — complete the itemization (read-only, ghost-stratia-ux-research).** read the existing
  inventory + live index.html, add the three missing axes above. output: updated inventory doc. this is
  the itemization bryan asked for, finished.
- **wave 2 — prototype in express (mcp-grounded).** with express mcp live, prototype the drift-resolution
  elements + the reclassified dropdown, token-accurate, then pin to the token layer.
- **wave 3 — build (ghost-liora-css-repair).** execute token-drift resolutions the inventory flags +
  dropdown market/featured-frontier reorg + the translation feature. each row prototyped in express first,
  then pinned. version-bump every deploy. verify live (content-md5 + stamp + cache), not deploy-green.

## two open decisions (bryan's call, carried from this session)

1. **the `--red #B51E14` drift** (inventory standard S1/S6). the inventory has held this open: make it a
   real token `color.brand.signalRed`, or replace with blazeOrange `#E8530E`? the rizz-up notes lean
   signal-red `#b51e14`. confirming signal-red resolves the single most-flagged drift and unblocks wave 3.
2. **market/featured-frontier as derived vs explicit.** derive `location_class` from `retailers[]`
   (recommended, no schema migration) vs add an explicit field to all 73 records (bigger data task).

## security follow-up (must not be lost)

during this session's diagnostics, `ps` exposed two github personal access tokens in plaintext on process
command lines (stale supergateway + github-mcp docker processes, ages up to 3 days). the five carrying
processes were killed (exposure stopped, verified clean). BUT the tokens remain valid on github's side and
must be treated as compromised:

- rotate both `gho_` PATs in github settings — non-skippable, `docker logout` / process-kill does not
  invalidate a token server-side
- change the github-mcp launcher so it sources the token at runtime instead of passing it inline as
  `-e GITHUB_PERSONAL_ACCESS_TOKEN=` on `docker run` (visible to any `ps`). per secret-handling rule,
  tokens live in aws ssm, injected at runtime
- owner: poltergeist-tarn-mcp-forge + secret-handling. separate from kodiak, but active — do first.
