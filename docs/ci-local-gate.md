# local checks

this repository owns its checks. no server-side continuous integration service is part of the project workflow. every check runs from the repository with the pinned local tools and the committed fixtures

## fast push check

`scripts/hooks/pre-push` runs the fast local lint check:

```bash
uvx ruff@0.15.12 check .
```

Install the hook after cloning:

```bash
scripts/hooks/install.sh
```

## full local gate

Run this before opening or merging a pull request:

```bash
scripts/hooks/full-check.sh
```

The full gate runs, in order, local lint, token tests, data-mirror parity, Python unit and integration tests, deterministic accessibility and render checks, local Playwright browser scenarios, and infrastructure template lint. It does not contact a hosted browser, invoke a remote validation service, publish artifacts, sync data, or generate campaign output

## boutique browser testing

The browser scenarios are explicit on-demand testing for changes that affect the web surface. They start a local static server, use headless Chromium, and write video evidence under the ignored `tests/browser/videos/` directory

```bash
npm run test:browser
npm run test:browser -- --issue 250
```

For generated retailer previews, the local evidence checker emits structured JSON plus viewport screenshots:

```bash
uv run python scripts/browser-check.py --preview /tmp/verify-kodiak/preview.html --out /tmp/browser-report.json
uv run python scripts/browser-check.py --all --out /tmp/browser-report.json
```

These checks are local deterministic or boutique checks. They do not use agent visual verification, hosted browser sessions, or a remote origin

## generation-only workflow

Campaign output generation is manual and separate from validation. It is not a gate, not agent visual verification, and not required for ordinary local tests

```bash
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/verify-kodiak
```

The optional Kodiak generation reference workflow may use the project’s configured model or data library. Keep it behind an explicit generation command. Data synchronization remains manual and requires the project’s existing AWS profile only when the command needs cloud storage access

```bash
AWS_PROFILE=bryanchasko-kiro ./scripts/sync-asset-store.sh pull
AWS_PROFILE=bryanchasko-kiro uv run python scripts/embed-social-corpus.py --out data/vectors
```

Do not add either command to the pre-push hook or full local gate

## bypass

For an urgent local branch-only push, the hook can be bypassed explicitly:

```bash
git push --no-verify
```
