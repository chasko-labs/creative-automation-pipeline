# ci is a local gate

CI for this repo runs on the developer machine. there is no server-side CI.

## why

- CodeBuild made every PR sit UNSTABLE waiting on a webhook status check and
  burned build minutes. with no branch protection (free-tier repo) it was only
  a soft check anyway
- GitHub Actions is forbidden on this repo (zero budget). do not add
  `.github/workflows/` anything

## two tiers -- fast on every push, full before merge

per-push hook (`scripts/hooks/pre-push`) runs ONE fast gate so a push never
waits:

- `uvx ruff@0.15.12 check .`   lint, ~1s

the full suite is a deliberate pre-merge checkpoint, not a per-push tax. run it
yourself before opening or merging a PR:

```
scripts/hooks/full-check.sh
```

which runs `pytest -x -q` (fast unit tests) then `cfn-lint infra/template.yaml`.

`buildspec.yml` stays in the tree as the canonical full command spec. a heavy
per-push hook just gets `--no-verify`'d into uselessness, so the push gate is
kept to lint only.

## activate after clone (one command)

```
scripts/hooks/install.sh
```

sets `git config core.hooksPath scripts/hooks` for this repo only. every clone
runs it once.

## emergency bypass

```
git push --no-verify
```

## disconnect CodeBuild (one manual operator step)

the CodeBuild webhook is an AWS/GitHub-app binding, not a repo file. an operator
deletes it once so CodeBuild stops triggering:

```
aws codebuild list-projects --profile aerospaceug-admin --region us-east-1
aws codebuild delete-webhook --project-name kodiak-creatives-ci --profile aerospaceug-admin --region us-east-1
```

after the webhook is deleted, pushes and PRs no longer trigger CodeBuild. the
local gate is the only CI.
