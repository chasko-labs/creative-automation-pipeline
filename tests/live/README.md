# Live-browser harness (tests/live)

One runner, parametrized per issue. Headless, CI-safe (chromium headless +
`--no-sandbox`, local static server, no mocks, no stubs).

Run:

- `npm run test:live -- --issue 250` — single issue against a local server
- `npm run test:live` — every scenario in `issues/`
- `npm run test:live -- --issue 250 --base-url https://d37333alc7ojpl.cloudfront.net`
  — same scenario against the deployed site (post-deploy proof)

Videos land in `tests/live/videos/` (gitignored). The receipt for an issue
names the harness file (`tests/live/issues/issue-<n>.mjs`) plus the video.

Extend: add `tests/live/issues/issue-<n>.mjs` exporting
`{ issue, title, run(page, { baseUrl }) }` — throw on failure via the `assert`
helper in `lib.mjs`. Never invent a new repro file elsewhere.

Environment-gated scenarios (backend endpoints or backend-driven surfaces a
static server cannot provide) call `skip(reason)` from `lib.mjs` — the
harness reports `SKIP #<n>: <reason>` and stays green. A skip must name the
run that would cover it (e.g. `--base-url https://kodiak.bryanchasko.com`).
Skips never substitute for product assertions: assert everything the local
page can prove, skip only what it cannot reach.
