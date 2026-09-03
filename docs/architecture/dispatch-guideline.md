# dispatch guideline — creative-automation-pipeline

> quick reference for every team member (human or agent) working this repo on rocm-aibox. the git-agent roster, tooling standards, dispatch rules, and the lint-discipline learned the hard way. keep this open in a tab.

## the environment (once, read at start)

- host: rocm-aibox (linux). shared venv managed by `uv`. python 3.11. rust via cargo + maturin.
- repo: `chasko-labs/creative-automation-pipeline` (private). all BryanChasko/_ and chasko-labs/_ repos are private — never web_fetch github, read from the local clone or use @github mcp.
- ci: aws codebuild only. no github actions. buildspec.yml is the gate.
- aws: account bryanchasko-kiro (946179428633), region us-east-1. amazon first-party + custom models freely (nova, titan, nova canvas). third-party models (anthropic etc) are forbidden in the product. cost is not a decision input — capability fit is.
- secrets: aws ssm only. never write secrets to disk, never `docker login ghcr`.

## agent roster — who does what

dispatch by DOMAIN, not by "who has bash". overusing one agent because it can run shell is a dispatch failure.

| agent slug                        | domain                | use for                                                                                | does NOT do                       |
| --------------------------------- | --------------------- | -------------------------------------------------------------------------------------- | --------------------------------- |
| ghost-hcom-python-coder           | python + bash         | pipeline modules, cli, embeddings, spin, ingest, scripts, tests, lint fixes            | rust, git commits, infra          |
| ghost-solan-rust-coder            | rust                  | rust/kodiak-local crate, pyo3, clippy, cargo tests                                     | python surface, git               |
| ghost-orin-ci-cd                  | git + ci + host shell | commits, branches, PRs, buildspec, running long host jobs (embedding batches), s3 sync | writing feature code              |
| ghost-myrren-edge-fallback        | amazon inference      | nova/titan model selection, embedding body shapes, bedrock probes                      | host shell runs (no execute_bash) |
| poltergeist-stratia-aws-infra     | aws infra             | codebuild project, s3 vectors index, iam, cloudformation                               | feature code                      |
| poltergeist-stratia-bedrock-arch  | bedrock orchestration | agentcore agents, knowledge bases, guardrails                                          | frontend                          |
| poltergeist-liora-moodle-ux / css | frontend + css        | web ui, css, dom, responsive                                                           | pipeline internals                |
| ghost-kerouac-research-analyst    | web research          | source analysis, competitive imagery study                                             | code                              |
| ghost-stratia-code-mapper         | architecture mapping  | read-only codebase mapping, planning                                                   | writing code                      |

## the lint discipline (learned 2026-09-03, non-negotiable)

waiting on a slow agent round-trip just to discover a lint failure is wasted wall-time. the rule:

- assume lint failure is likely on any diff touching new files. do not dispatch a run/commit and hope the diff is clean.
- the dispatching anchor runs `uv run ruff check .` (the FULL tree — `.` not `src/`, the ci gate checks tests/ and scripts/ too) itself, immediately, before the commit dispatch. if it's dirty, fix it inline (governance/docs) or fire a fast focused lint-fix dispatch — do not block the pipeline on it.
- every coder dispatch prompt MUST include: "run `uv run ruff check .` and `uv run pytest -x -q` yourself before reporting done; report both results." a coder that reports done without a clean ruff line has not finished.
- next-go enforcement: coders sweep for the recurring offenders on every diff — F541 (f-string no placeholder), F401 (unused import), E401 (multi-import line), E402 (import not at top), F841 (unused local), E741 (ambiguous name `l`). these have bitten us repeatedly. a coder that leaves one of these is re-doing the work.

## tooling standards

- python: `uv run <cmd>`. line-length 100 (ruff config in pyproject). tests in `tests/`, `uv run pytest -x -q` (fail-fast).
- rust: `cargo test --manifest-path rust/kodiak-local/Cargo.toml`, `cargo clippy -- -D warnings`, `cargo fmt`. build the ext with `uv run maturin develop -m rust/kodiak-local/Cargo.toml`.
- rust accelerator is OPT-IN: `KODIAK_RUST=1` + compiled ext, else pillow fallback. ci runs without the ext and stays green.
- bedrock image editing is OPT-IN: `KODIAK_BEDROCK_EDIT=1`, else pillow fallback offline.
- no third-party image libs (no rembg, no remove.bg). amazon-first: nova canvas + rekognition, pillow fallback.
- no text baked into generated imagery. the ONLY exception is a retailer logo lockup (e.g. costco logo + local store address) as an explicit separate op. brand signal: `in_image_text=false`.
- iso naming: one regex in `naming.py`, imported everywhere. never a second pattern.
- prettier / bash-gate deadlock (resolved 2026-09-03): the global pre-commit hook prettier-checks staged `.md`/`.json`/`.yaml`, while the kiro bash-gate blocks bare `npx prettier`. `ghost-orin-ci-cd` already has a full bash-gate exemption, but kiro #2365 makes the PreToolUse hook fire with the PARENT PO/anchor name on a dispatch, so a dispatched orin lint command was evaluated as the poltergeist parent and blocked. fix landed in haunting-kiro-cli (`hooks/harald-bash-gate.sh`, PR #2409): a carve-out — same shape as the existing aws/pytest/cdk #2365 exemptions — lets `npx prettier|markdownlint|biome|eslint|tsc` through when the parent is a PO/anchor. no workaround needed anymore; a poltergeist running lint OUTSIDE a dispatch is still blocked. the cleaner long-term root fix is upstream kiro (#2365, subagent-identity propagation).

## ci gate (fail fast)

buildspec.yml runs cheap-to-expensive with hard fail-fast:

1. `uv run ruff check .` — ~1s, dies first on any lint
2. `uv run pytest -x -q` — stop on first test failure
3. `cfn-lint infra/template.yaml` — cheap, no aws calls

slow path (full nova render, nova-act browser check, the ~3000-item embedding corpus run) is gated behind `RUN_SLOW=true` — nightly / manual only, never the per-push gate. keep it that way: do not move a slow/networked step into the per-push gate.

## dispatch rules

- route by domain (table above). one agent per domain.
- read before you write. never propose changes to code you haven't read.
- coders do NOT commit — they report changed files; commits go through ghost-orin-ci-cd on a branch + PR. never push to main.
- read-only shell counts toward your budget — if understanding the problem needs >3 file reads or >5 diagnostics, dispatch ghost-stratia-code-mapper instead of exploring inline.
- long host jobs (embedding batches, s3 sync) go to orin (has execute_bash); inference-design goes to myrren (no shell). do not ask a shell-less agent to run a batch.
- a read-only/search agent claiming "X was never built" must be grep-verified against live git before acting — the search index lags.

## the rule in one sentence

dispatch by domain, run ruff yourself before you wait on anyone, keep the slow path out of the per-push gate, and let orin own every commit on a branch + PR
