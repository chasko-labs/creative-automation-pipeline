# local browser harness (tests/browser)

This runner provides explicit on-demand boutique testing for frontend interaction changes. It starts a local static server, uses headless Chromium, and records ignored video evidence. It never accepts a hosted origin

Run one scenario or all local scenarios:

```bash
npm run test:browser -- --issue 250
npm run test:browser
```

Videos land in `tests/browser/videos/` (gitignored). The receipt names the local scenario file plus the video

Extend the harness by adding `tests/browser/issues/issue-<number>.mjs` exporting `{ issue, title, run(page, { baseUrl }) }`. Use the `assert` helper in `lib.mjs`. Do not add remote-origin or hosted-browser options
