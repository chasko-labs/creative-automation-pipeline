# Kodiak frontier frontend — file architecture + atomization conventions

> canonical home for how the `web/kodiak-posts-for-todays-frontier/` app is structured on disk and why.
> read this before you edit index.html or add a new frontend behavior. it is the frontend analogue of
> `docs/design-system-inventory.md` (which owns the token + component visual layer).

## the shape after the atomization (PR #142, 0.1.016)

index.html used to be a 3761-line monolith — all markup, all inline JS, and a 731-line inline `<style>`
block in one file. two people (or two agents) could not touch it at once without colliding, and one bad
edit could corrupt behavior anywhere in the file. the atomization split it into a thin shell plus siblings:

- `index.html` — now ~296 lines. markup, the `<head>` links, and the ordered list of `<script src>` tags.
  nothing else. it is a shell.
- `js/*.js` — each self-contained behavior lives in its own classic-script sibling.
- `design/components.css` — the hand-authored component + page styles, extracted from the old inline
  `<style>` block. linked in `<head>` right after the Panda-generated `design/styles.css`.

## why classic `<script src>`, not ES modules

the app relies on a **shared global lexical scope** — behaviors reference each other and shared data by
bare name (`places`, `skuList`, `marketLangsOffline`, helper functions). classic `<script src>` tags all
execute in that one global scope, so a bare name defined in `data-core.js` is visible in `generate.js`.

ES modules do **not** share global scope — each module is its own scope, and cross-references need explicit
`import`/`export`. converting to modules would mean rewriting every bare-name reference across the whole
app. rejected. classic scripts stay.

a bundler was also rejected: it breaks offline-first `file://` loading (the app must open straight from disk
with no build step) and the wholesale S3 sync that `deploy-frontier.sh` does.

## load order is a contract

the `<script src>` tags load in dependency order. do not reorder them without checking who depends on whom:

```
data-core        # shared data + helpers — everything downstream reads these
generate         # the generate/preview ladder
product-combobox # product picker
prompt-chips     # sample-prompt chips
market-disclosure
scroll-swap
debug-overlay
autocomplete
lifecycle-persist
campaign-sections
```

`data-core.js` must load first — it defines the shared data (`places[]`, `skuList`, `marketLangsOffline`)
that later scripts read at parse time. a downstream script that runs before `data-core` sees `undefined`.

## data stays inline in data-core.js — on purpose

the `places[]` array (73 US market codes), `skuList`, and `marketLangsOffline` live as JS literals inside
`data-core.js`. they are **not** extracted to `data/*.json`. reason: the app must work from `file://`, and a
`file://` page cannot `fetch()` a sibling JSON file (browsers block it as a cross-origin request). keeping
the data as inline JS literals is the offline-first fallback. rejected extracting to JSON.

> if you add or remove a market, edit `places[]` in `js/data-core.js`. a test parses that file for the
> `market:"US-..."` codes and asserts the count — see the "tests that read the frontend by path" note below.

## IIFE boundaries are load-bearing

each extracted behavior is wrapped in an IIFE (`(function(){ ... })();`). when you extract a block from
index.html into a sibling, the IIFE open/close must match exactly. a miscut — grabbing one brace too few or
too many — over-runs the `</script>` boundary and silently corrupts the adjacent block. after any extraction:

```
node --check js/<file>.js     # syntax must be clean
```

verify the extracted bytes are identical to what left index.html, and run `node --check` immediately. do not
batch several extractions and check at the end — check each one as you cut it.

## css: two files, two owners

- `design/styles.css` — **Panda-generated. never hand-edit.** produced by `npm run tokens:css`
  (panda cssgen) from the token layer. any hand edit is clobbered on the next token regen.
- `design/components.css` — **hand-authored.** the component + page styles that are not token output.

both are linked in `<head>`, styles.css first (tokens/base), then components.css (components consume the
token custom properties). they carry a `?v=<version>` cache-buster that `scripts/bump-version.sh` stamps.

> known drift, flagged not fixed: `.header__inner` still hardcodes `#382316` (an off-brand near-brown, 3 hex
> off bearBrown `#3B2316`). changing it is a visible pixel change, out of scope for a hygiene sprint. tracked
> in `docs/design-system-inventory.md` standard S1.

## tests that read the frontend by path

some tests parse frontend files directly to enforce a contract — e.g. `tests/test_regional_scoreboard.py`
reads the market codes out of the frontend and asserts there are 73. when you **split a frontend file**, any
test that parsed the old path breaks (it finds 0). the atomization moved `places[]` from index.html into
`js/data-core.js`, so that test's `FRONTEND_DATA` path was repointed to `js/data-core.js`. if you move data
between frontend files again, grep `tests/` for the old path and repoint it in the same change.

## deploy (frontend)

```
./scripts/bump-version.sh 0.1.0NN   # stamp the next build id across all version sinks
./scripts/bump-version.sh --check   # read-only: confirm all sinks agree
./scripts/deploy-frontier.sh        # sync to S3 + CloudFront invalidation (refuses on git drift)
```

`deploy-frontier.sh` refuses if the working tree is dirty — commit first. its `DIRS` list already includes
`js` and `design`, so the siblings and both css files sync wholesale. it re-puts `.js` with the
`application/javascript` content-type.

## still a monolith

`details.html` (~101KB) has not been atomized yet. it follows the same inline pattern index.html used to.
the same split applies when someone takes it on: classic-script siblings, IIFE-boundary discipline, keep
data inline for `file://`.
