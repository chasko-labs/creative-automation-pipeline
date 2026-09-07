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

Every change must pass these checks:

1. **Quick local checks** — from the project folder:

   ```
   uv run pytest -q
   uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/verify-kodiak
   uv run python scripts/nova-act-check.py --preview /tmp/verify-kodiak/preview.html --out /tmp/nova.json
   ```

   All should say pass.

2. **End to end through the cloud** — with `AWS_PROFILE=bryanchasko-kiro` and `DAM_S3_BUCKET` set:

   ```
   ./scripts/sync-dam.sh pull
   DAM_S3_BUCKET=chasko-creative-dam-946179428633-us-east-1 uv run python -m creative_automation.cli --brief briefs/kodiak-on-the-go.yaml --assets input_assets --out output_kodiak-on-the-go
   ./scripts/sync-dam.sh push-renders output_kodiak-on-the-go
   ```

   Then check the style library loaded from cloud, not just your laptop.

3. **Cloud formation safety** before any deploy:
   ```
   cfn-lint infra/template.yaml
   cfn-guard validate --template infra/template.yaml --rules cfn-guard-rules/
   aws cloudformation create-change-set --stack-name kodiak-creatives --template-body file://infra/template.yaml --capabilities CAPABILITY_NAMED_IAM
   aws cloudformation describe-events --stack-name kodiak-creatives --filters FailedEvents=true --region us-east-1
   ```

### How to add something new — dispatched development

When you want to add a new channel (for example, a diner menu board or a subscription email) or a new region (for example, Las Cruces green chile):

1. Add a one-page brief at `briefs/kodiak-your-idea.yaml` with at least two products, a place, an audience, and one line of message. Write it in human words — no short forms.
2. Add a row to `data/localization/localization-training-data.jsonl` and `data/localization/localization-table-seed.json` for that place, or let the pipeline add it automatically after the first run succeeds.
3. Add your test to `tests/` that proves the new brief produces three sizes, shows the line, and passes the bear and color check.
4. Run the quick local checks above. If your change touched cloud storage, run the cloud end to end.
5. Open a small pull request with just those files. Keep it under 500 lines so marketing can review the words and engineering can review the logic.

### What we expect in every pull request

- Human description: who is this for (Maya the brand manager, Diego the field ambassador, Priya the paid media lead), what place and store does it serve, and what will marketing see?
- No short forms in docs or code comments — write "cloud storage," "photo library," "style tokens" instead of initials.
- Updated human docs if you changed the experience: `docs/ux-persona-kodiak.md`, `docs/kodiak-brand-explained.md`, or `docs/regional-cultural-database.md`.
- Screenshots of `preview.html` for the new campaign (one per size) attached to the pull request — the reviewer should not need to run the code to see the result.

### Daily flow

- Work on the main branch is continuous — we commit small and push often to the private repository at https://github.com/chasko-labs/creative-automation-pipeline .
- The cloud bucket `chasko-creative-dam-946179428633-us-east-1` always holds the latest approved style tokens, references, and renders under `brands/kodiak/`. Pull before you branch, push after your change is approved.
- worktrees: three teams share one clone — see [docs/architecture/worktree-workflow.md](docs/architecture/worktree-workflow.md)

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

- Coders (human or agent) do not commit feature work directly — commits go through the CI/git owner (`ghost-orin-ci-cd`) on a branch, then a pull request. Never push to `main`.
- Keep pull requests under 500 lines and one lane where possible, so the reviewer sees a coherent change and the other teams are not surprised.
- The slow path (full render, browser visual check, the multi-thousand-item embedding corpus run) stays behind `RUN_SLOW=true` — nightly or manual, never the per-push gate. Do not move a slow or networked step into the fast gate.

### Need help?

Open an issue with the place, store group, and the line you want to try. Label it with the persona it serves (brand, field, media) and the team lane it touches (pipeline, frontend, platform).
