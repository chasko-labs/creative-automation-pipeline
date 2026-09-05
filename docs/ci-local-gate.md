# ci is a local pre-push gate

CI for this repo runs on the developer machine as a git pre-push hook. there is
no server-side CI.

## why

- CodeBuild made every PR sit UNSTABLE waiting on a webhook status check and
  burned build minutes. with no branch protection (free-tier repo) it was only
  a soft check anyway, never a hard gate
- GitHub Actions is forbidden on this repo (zero budget). do not add
  `.github/workflows/` anything
- a local pre-push hook gives the same three gates instantly, offline, with no
  wait and no cost, and stops bad code before it ever leaves the machine

## the gates

the hook (`scripts/hooks/pre-push`) mirrors `buildspec.yml` gate-for-gate,
fail-fast, cheapest first:

- gate 1  `uvx ruff@0.15.12 check .`            lint
- gate 2  `uv run --with pytest pytest -x -q`   fast unit tests (RUN_SLOW=false posture)
- gate 3  `cfn-lint infra/template.yaml`        cloudformation template safety

any gate failure exits non-zero and aborts the push. `buildspec.yml` stays in
the tree as the canonical command spec the hook is kept in sync with -- it is
not GitHub Actions, just the reference command list.

## activate after clone (one command)

```
scripts/hooks/install.sh
```

this runs `git config core.hooksPath scripts/hooks` for this repo only (it does
not touch your global hooks path). every clone must run it once.

## emergency bypass

```
git push --no-verify
```

use sparingly, never on shared branches.

## the one manual operator step -- disconnect CodeBuild

the CodeBuild webhook is an AWS/GitHub-app binding, not a repo file, so it
cannot be removed by a commit. an operator disconnects it once so CodeBuild
stops triggering on push:

```
aws codebuild delete-webhook --project-name kodiak-creatives-ci --profile aerospaceug-admin --region us-east-1
```

the status check context was `kodiak-creatives-ci` (account 946179428633,
aerospaceug-admin). confirm the exact project name first:

```
aws codebuild list-projects --profile aerospaceug-admin --region us-east-1
```

after the webhook is deleted, pushes and PRs no longer trigger CodeBuild and no
status check is posted. the local pre-push gate is the only CI.
