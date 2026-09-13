# local browser testing runbook

## purpose

The repository provides two local browser checks for explicit on-demand boutique testing

- `scripts/browser-check.py` checks generated `preview.html` files at the three campaign viewports, probes the rendered images, and writes structured evidence
- `tests/browser/harness.mjs` runs issue-scoped Playwright scenarios against a local static server, recording ignored video evidence

Neither check uses a hosted origin, a remote browser service, agent visual verification, cloud storage, or campaign generation

## generated preview evidence

Generate a preview only when a campaign output is needed for review:

```bash
uv run python -m creative_automation.cli --brief briefs/kodiak.yaml --assets input_assets --out /tmp/verify-kodiak
```

Run the local evidence checker:

```bash
uv run python scripts/browser-check.py --preview /tmp/verify-kodiak/preview.html --out /tmp/browser-report.json
```

Use `--all` to discover the committed `output_kodiak*/preview.html` files. Use `--mode mock` for pixel and markup checks without Chromium. The default `auto` mode selects local Playwright when its Python package is available, otherwise it uses the deterministic mock checks

The report records the selected mode, viewport results, creative checks, generated screenshots, and pass or fail details. Screenshots land under `/tmp/browser-<retailer>-<viewport>.png`

## local web scenarios

Run all scenarios or one issue locally:

```bash
npm run test:browser
npm run test:browser -- --issue 250
```

The runner starts a local static server on `127.0.0.1`, opens the page with headless Chromium, and records scenario video evidence under `tests/browser/videos/`. Add a scenario under `tests/browser/issues/issue-<number>.mjs` when a frontend regression needs a repeatable interaction check

## boundaries

- local browser checks are explicit boutique testing, not a hosted service gate
- the browser checks do not invoke agent visual verification
- Kodiak generation is a separate manual command, never a validation prerequisite
- data synchronization is a separate manual command and may use `AWS_PROFILE=bryanchasko-kiro` when cloud storage access is required
- the pre-push hook and full local gate remain runnable without cloud credentials
