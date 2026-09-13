# Frontend delegation contract — Glimmer (design judgment) + deterministic gates

Local model serving: Glimmer 30B on `http://127.0.0.1:8181/v1`
(supervisor `~/code/heraldstack/heraldstack-firecracker/muse-code/glimmer/`).
Cold-start ~8s, idle-teardown 300s, serializes on the fc-pool `gpu_lock`.

## Stack order (deterministic checks first, model judgment second)

1. Vitest — `npm run test:vitest` (pinned exact in package.json, no browser,
   token-CSS assertions, milliseconds).
2. Targeted Playwright Chromium — `scripts/check-spectrum.mjs`,
   `scripts/check-brand-render.mjs` (repo-local ms-playwright binary via
   executablePath; Firefox/WebKit binaries intentionally absent).
3. Full local gate before merge — pytest full suite plus the repository-owned
   local browser scenarios. Boutique browser evidence stays explicit and local,
   never a hosted service or agent visual verifier.

## Delegation rule

Scripts own numeric verdicts. Glimmer handles design judgment and triage of
gate failures (which failure is load-bearing, what fix preserves intent) and
NEVER overrides a failing deterministic check — a red gate is red until the
code or the (wrong) expectation changes, with the change committed.

Precedent gaps, fixed: Vitest pinned exact; Firefox/WebKit binaries
dropped (Chromium-only gate, documented in both .mjs scripts);
headed-Chromium loop kept for interactive debug (`headless=False` locally,
never in gates).

## Escalation rubric

Proceed alone: token-compliant fixes, single-site deletions, layout fixes
without copy changes.
Escalate to Bryan: palette, typeface, logo, theme, new/shared components,
cross-site/routing changes, user-visible copy, new Kodiak voice/badge/image
rules. An explicit direct instruction from Bryan overrides the rubric for
the named item only.
