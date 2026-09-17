# Working together on the Kodiak creative pipeline

This guide is for anyone who helps build the pipeline — designers, marketers, and engineers — and it keeps the whole system in one connected place.

## How we work in plain language

We keep everything together. One cloud setup, one photo and style library, one growing table that remembers what worked per place. Nothing is split across hidden accounts.

### One cloud setup that holds it all

We describe the whole system in a single cloud formation file at `infra/template.yaml`. That file creates:

- the cloud storage buckets where style and photos live
- the versioned style library (tokens, logos, photo directions)
- the regional knowledge base (places, audiences, messages)
- the table that remembers what worked per place

But our current live bucket was built with the earlier style library template at `infra/s3-dam.tf` — that template already created `chasko-creative-dam-946179428633-us-east-1` in us-east-1 with versioning, blocked public access, and lifecycle rules. The new single file at `infra/template.yaml` wraps that plus the tables and knowledge base so future deploys stay one file.

### How we test before we ship

The repository owns its checks. The fast pre-push hook runs local lint only. The full local gate runs before a pull request is opened or merged:

```bash
scripts/hooks/install.sh
uvx ruff@0.15.12 check .
scripts/hooks/full-check.sh
```

The full gate covers token tests, data-mirror parity, Python unit and integration tests, deterministic accessibility and render checks, local Playwright browser scenarios, and local infrastructure template lint. It never contacts a hosted browser, invokes agent visual verification, syncs data, publishes artifacts, or generates campaign output

### explicit boutique browser testing

Run local browser checks when a web or preview change needs screenshot or interaction evidence:

```bash
npm run test:browser
npm run test:browser -- --issue 250
uv run python scripts/browser-check.py --preview /tmp/verify-kodiak/preview.html --out /tmp/browser-report.json
```

The browser checks use local Chromium or deterministic markup and pixel probes. Reports record viewport checks, creative checks, and evidence paths. They are explicit on-demand boutique testing, not a hosted service gate

### generation and data sync are manual

Campaign generation is separate from validation and is not required for ordinary local tests:

```bash
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/verify-kodiak
```

The Kodiak generation reference workflow remains generation-only. Data synchronization remains manual and may use the existing AWS profile when cloud storage access is required:

```bash
AWS_PROFILE=bryanchasko-kiro ./scripts/sync-dam.sh pull
AWS_PROFILE=bryanchasko-kiro uv run python scripts/embed-social-corpus.py --out data/vectors
```

Do not add generation or synchronization commands to the pre-push hook or full local gate

### infrastructure review

Run infrastructure lint locally before an infrastructure change:

```bash
cfn-lint infra/template.yaml
cfn-guard validate --template infra/template.yaml --rules cfn-guard-rules/
```

### Frontend verify + ship loop (the frontier app)

The hosted demo at `https://kodiak.bryanchasko.com` serves `web/kodiak-posts-for-todays-frontier/` as static files — no build step. Every frontend change must pass these before it ships:

```
npx vitest run                                        # 29 files / 127 tests
python3 scripts/build-frontier-mapping.py --check    # backend JSON mirrors agree with data-core.js
python3 scripts/check-panda-tokens.py                # panda-parity PASS
node scripts/check-brand-render.mjs                  # pixel baselines guard the real app UI
```

The render gate steps through the share-gate (word `cakes` — a courtesy screen, not security) before capture, so baselines in `tests/fixtures/brand-baseline/` guard the campaign UI, not the gate overlay. Re-capture with `--update-baselines` only for an intended visual change you have eyeballed — never to silence red.

Ship it through the operator-driven branch process described in [`docs/kodiak-environments.md`](docs/kodiak-environments.md). Run the deterministic local gates first, then deploy from a clean checkout with an explicit local profile:

```bash
scripts/hooks/full-check.sh
AWS_PROFILE=<local-profile> ./scripts/deploy-frontier.sh dev  # named development branch only
AWS_PROFILE=<local-profile> ./scripts/deploy-frontier.sh prod # main only, after approval
DRY_RUN=1 AWS_PROFILE=<local-profile> ./scripts/deploy-frontier.sh dev # local no-mutation preview
curl -s https://kodiak-dev.bryanchasko.com/design/components.css | grep -c "<your-marker>"
```

A named development branch deploys to the shared development hostname, where the latest successful branch deployment wins. Main deploys remain explicit operator actions after approved changes merge into a clean main checkout. Git push alone does not deploy a site. Deployment remains an explicit operator action

The deploy script rejects a dirty worktree, derives the expected target from the local branch, requires an explicit `AWS_PROFILE`, uses the selected target for storage, distribution, version source, and verification output, and keeps development identifiers fail-closed through environment variables

### Types as documentation

The frontier page scripts carry their shapes in plain comments so the checker can verify them. Values from outside — backend responses, page elements — arrive unchecked and pass through a named check before use. Fixed sets like tile sizes stay closed: only the listed values are valid. Whenever a type annotation does something subtle, the reason sits on the line next to it, not in a separate doc.

### Reviewer zip

Clean `origin/main` export + rendered docs + auto-unlocking file:// copy + the required 2:55 walkthrough video:

The builder fetches the walkthrough video from S3 as a **required** artifact — it fails closed (nonzero exit) if the video is missing or zero bytes, and verifies the entry exists inside the built ZIP before emitting upload commands. The source defaults to `s3://frontier-bryanchasko-com/kodiak-demo-2m55.mp4` and is overridable with `REVIEWER_VIDEO_S3_URI`. The old `/tmp`-only path warned and skipped, which shipped a broken ZIP (START-HERE video links, no MP4) — never again.

```
./scripts/build-reviewer-package.sh
# canonical key — no-cache so a re-push is served immediately:
aws s3 cp /tmp/kodiak-reviewer/kodiak-reviewer-package.zip s3://frontier-bryanchasko-com/adobechallenge/kodiak-reviewer-package.zip --content-type application/zip --cache-control 'no-cache, max-age=0, must-revalidate' --profile bryanchasko-kiro --region us-east-1
# versioned key — content-addressed, immutable; emergency link that bypasses stale canonical cache:
aws s3 cp /tmp/kodiak-reviewer/kodiak-reviewer-package.zip s3://frontier-bryanchasko-com/adobechallenge/kodiak-reviewer-package-<short-sha>.zip --content-type application/zip --cache-control 'public, max-age=31536000, immutable' --profile bryanchasko-kiro --region us-east-1
aws cloudfront create-invalidation --distribution-id E3GEX8LSRX6OYS --paths '/adobechallenge/kodiak-reviewer-package.zip' --profile bryanchasko-kiro --region us-east-1
```

The builder emits the exact upload/invalidation commands (with the resolved git short SHA in the versioned key) at the end of its run — copy them from the output rather than transcribing by hand.

The reviewer URL (`https://kodiak.bryanchasko.com/adobechallenge/kodiak-reviewer-package.zip`) is served by CloudFront from the `adobechallenge/` prefix — upload to the bucket root lands at a dead key and never goes live. Always upload to the `adobechallenge/` prefix and invalidate after, or the refresh is invisible.

Local visual check without deploying: serve the app dir statically and screenshot past the gate (see `scripts/check-brand-render.mjs` for the stepping-through pattern). Never pixel-sample PNGs by hand — read computed styles and look at real screenshots.

### Data contract — uncertainty flags are load-bearing

`js/data-core.js` + `js/season-flavors.js` are frontend truth; `data/localization/*.json` and `data/platforms/*.json` are mirrors. Change both sides together so `--check` agrees. Rules:

- Never present an unconfirmed month/season as fact. `m:[]` + a `research dispatch` note means "can never render as in-season" — that is the correct state for unverified data, not a gap to fill with a guess. UNCONFIRMED beats guess.
- Month arrays use 0-based months in `season-flavors.js` FRONTIER_CAL and 1-based months in the JSON mirrors — check both when editing seasons.

### Design law — token-sovereign CSS only

- `var()` refs with hex fallbacks (e.g. `var(--colors-brand-box-parchment,#F5EAD3)`). No raw hex, no inline styles for surfaces.
- `design/styles.css` is Panda-generated — never hand-edit. Hand styles go in `design/components.css`.
- Below-fold surfaces never go near-white: box-parchment token, never neutral-50. The page background is one base `body` rule (house wash + kraft token) — no later `body` override, or the wash dies in the cascade.
- Gotcha (paid for 2026-09-09): the kraft token expands to 3 layers, so `background-size`/`background-repeat` lists on `body` must stay 5 long. A short list cycles and strands the tan base at the top, leaving flat parchment below the fold. The comment in `components.css` says so — believe it.
- Keep the ember CTA white-on-ember, keep `prefers-reduced-motion` coverage, no flashing or rapid animation anywhere. Resting first-impression content stays exempt from `content-visibility` deferral.
- `#preview` innerHTML is wiped on Create — anything that must survive (resume card) lives outside it.

### How to add something new — dispatched development

When you want to add a new channel (for example, a diner menu board or a subscription email) or a new region (for example, Las Cruces green chile):

1. Add a one-page brief at `briefs/kodiak-your-idea.yaml` with at least two products, a place, an audience, and one line of message. Write it in human words — no short forms.
2. Add a row to `data/localization/localization-training-data.jsonl` and `data/localization/localization-table-seed.json` for that place, or let the pipeline add it automatically after the first run succeeds.
3. Add your test to `tests/` that proves the new brief produces three sizes, shows the line, and passes the bear and color check.
4. Run the quick local checks above. If your change touched cloud storage, run the cloud end to end.
5. Open a small pull request with just those files. Keep it under 500 lines so marketing can review the words and engineering can review the logic.

### What we expect in every pull request

- Human description: who is this for (Maya the brand manager, Diego the field ambassador, Priya the paid media lead), what place and store does it serve, and what will marketing see?
- No short forms in human-facing docs — write "cloud storage," "photo library," "style tokens" instead of initials. Code identifiers and comments may use standard technical abbreviations (DOM, CSS, URL, JSON).
- Updated human docs if you changed the experience: `docs/ux-persona-kodiak.md`, `docs/kodiak-brand-explained.md`, or `docs/regional-cultural-database.md`.
- Screenshots of `preview.html` for the new campaign (one per size) attached to the pull request — the reviewer should not need to run the code to see the result.

### Daily flow

- Work on the main branch is continuous — we commit small and push often to the private repository at https://github.com/chasko-labs/creative-automation-pipeline .
- The cloud bucket `chasko-creative-dam-946179428633-us-east-1` always holds the latest approved style tokens, references, and renders under `brands/kodiak/`. Pull before you branch, push after your change is approved.
- worktrees: three teams share one clone — one worktree per team off the same clone (commands below), separate branches, shared host venv; remove a worktree when its branch merges

## Three teams, one repo — how we avoid collisions

As of this sprint, three teams work this repository in parallel on the same rocm-aibox environment:

- **pipeline + agentic core** — the engine: training data, Amazon Bedrock AgentCore, the python and rust tooling that drives generation
- **app frontend** — the surface: web ui, css, the sample-prompt browser, preview rendering
- **infra + data platform** — the ground: aws infrastructure, the local pre-push CI gate, the style-library bucket, the vector index, dns and cloudfront


Full ownership map is in `docs/architecture/team-lanes.md`. The dispatch roster and tooling standards are in `docs/architecture/dispatch-guideline.md`. Read your lane before you touch a file.

### The situation we are solving

Three teams editing one working tree at once causes three failure modes: two teams edit the same file and one overwrites the other; a shared dependency bump breaks the other teams' venv; and a slow commit round-trip blocks everyone behind a lint error that should have died in one second. The rules below exist to prevent each.

### Use git worktrees — one tree per team

Do not have three teams committing from the same working directory. Each team works in its own git worktree off the same clone, so branches never stomp each other's uncommitted files:

```
# from the primary clone (main checked out)
git worktree add ../cap-pipeline  feat/pipeline-<topic>
git worktree add ../cap-frontend  feat/frontend-<topic>
git worktree add ../cap-platform  feat/platform-<topic>
```

Each worktree is a full checkout on its own branch sharing one `.git`. Team-pipeline works in `../cap-pipeline`, frontend in `../cap-frontend`, platform in `../cap-platform`. The shared `uv` venv and rust build cache stay on the host; only the source trees are separate. Remove a worktree when its branch merges: `git worktree remove ../cap-<team>`.

### Branch naming

`feat/<team>-<topic>` — e.g. `feat/pipeline-blog-corpus`, `feat/frontend-prompt-browser`, `feat/platform-vector-index`. The team prefix tells everyone which lane a branch belongs to at a glance.

### Stay in your lane; cross a seam by announcement

- Edit only paths your team owns (see `team-lanes.md`). A change to another lane's file is a dispatch to that team's coder, not a direct edit.
- Shared contracts are **seams**: design tokens, the api response shape, the sample-prompt schema, the iso naming regex, the dam bucket layout, the vector index dimension, and the dependency lockfiles. Changing one side of a seam without the other breaks the other team. Announce a seam change in the PR description and to the owning team before you merge it.
- Dependency changes (`pyproject.toml`, `Cargo.toml`) touch every team's shared venv. Announce before `uv add`; other teams re-run `uv sync` after the merge.

### The frontend is atomized — keep it that way

The web app used to be one 3761-line `index.html`. Two people could not touch it at once without colliding —
exactly the failure mode the team lanes exist to prevent. As of this sprint it is split: `index.html` is a
thin shell (markup + an ordered list of `<script src>` tags), each behavior lives in its own `js/` file, and
the hand-authored styles live in `design/components.css`. Full rationale and the rules are in
[docs/frontend-architecture.md](docs/frontend-architecture.md) — read it before you touch the frontend. The
load-bearing parts:

- **Add a behavior as a new `js/` sibling**, not as more inline script in `index.html`. Wrap it in an IIFE.
- **Classic `<script src>`, never ES modules.** The app shares one global scope by design; modules break it.
- **Script load order is a contract.** `data-core.js` loads first (it holds the shared data). Do not reorder.
- **Data stays inline in `js/data-core.js`** (the `places[]`/`skuList` literals) so the app works from
  `file://`. Do not extract it to a JSON file — a `file://` page cannot fetch a sibling JSON.
- **Two CSS files, two owners.** `design/styles.css` is Panda-generated — never hand-edit it (a token regen
  clobbers your change). Hand-authored styles go in `design/components.css`.
- **After extracting a block, run `node --check js/<file>.js` immediately.** A miscut IIFE over-runs the
  `</script>` boundary and corrupts the next block silently.
- **If you move data between frontend files, grep `tests/` for the old path.** Some tests parse the frontend
  by file path (e.g. the 73-market-code count) and break when a file splits.

### Run ruff before you wait on anyone

The local pre-push gate runs `ruff check .` first and dies in about one second on any lint error. Do not discover that after a slow commit round-trip. Before you hand a change to the CI/commit agent, run it yourself from your worktree:

```
uv run ruff check .        # the whole tree — tests/ and scripts/ count
uv run pytest -x -q        # fail-fast, stop on first failure
```

If ruff is dirty, fix it before the handoff. The recurring offenders that have bitten us — unused imports, f-strings without placeholders, multi-import lines, ambiguous variable names — get swept on every diff. A change handed off with a known lint error is unfinished work that comes straight back.

### Commits and merges

- Multi-team feature work goes up on a branch as a pull request — never push another lane's work to `main` directly. Solo frontier-app work (web demo + its data mirrors) may commit and push to `main` directly once every gate in the Frontend verify loop above is green, then deploy; each deploy is one `git revert` + redeploy away from a rollback.
- Keep pull requests under 500 lines and one lane where possible, so the reviewer sees a coherent change and the other teams are not surprised.
- The slow path (full render, browser visual check, the multi-thousand-item embedding corpus run) stays behind `RUN_SLOW=true` — nightly or manual, never the per-push gate. Do not move a slow or networked step into the fast gate.

### Need help?

Open an issue with the place, store group, and the line you want to try. Label it with the persona it serves (brand, field, media) and the team lane it touches (pipeline, frontend, platform).
