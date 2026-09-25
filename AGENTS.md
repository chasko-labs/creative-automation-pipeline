# AGENTS.md — working in this repo

- Mixed JS + Python pipeline (`package.json` scripts, `pyproject.toml` via `uv run python`).
- Design tokens are generated (`tokens:config`, `tokens:css`); edit sources, not generated CSS.
- Typecheck frontiers with `npm run check:frontier`, lint tokens with `npm run lint:css`, both before pushing.
- Test locally following code completion, in order: `npm run test:vitest`, `npm run test:live`, `npm run test:render`. No shared CI system.
- Visual judging goes through our not-nova-act extension library: the `browser_assert_visual_tool` MCP server on `localhost:8171` (see `src/creative_automation/param_sweep.py`). Extend it with custom logic as needed.
- Secrets live in AWS SSM, never on disk. Recipe art and raw ingest are regenerable, not precious.
